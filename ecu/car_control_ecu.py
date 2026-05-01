# ============================================================
# AZIZA - Car Control ECU (Body Control Module Simulation)
# Handles: windows, lights, door locks (LIN domain)
# ============================================================

import config


class CarControlECU:
    def __init__(self, can_bus, lin_bus):
        self.can_bus = can_bus
        self.lin_bus = lin_bus

        # --- Vehicle state from CAN ---
        self.vehicle_speed = 0.0

        # --- Windows (0 = closed, 100 = fully open) ---
        self.windows = {
            "positions": {0: 0, 1: 0, 2: 0, 3: 0},  # FL, FR, RL, RR
            "targets":   {0: 0, 1: 0, 2: 0, 3: 0}
        }

        # --- Lights ---
        self.lights = {
            "headlights": "OFF",
            "interior":   "OFF",
            "hazard":     "OFF",
            "fog":        "OFF",
        }

        # --- Door locks ---
        self.door_locks = {
            "FL": True,
            "FR": True,
            "RL": True,
            "RR": True,
            "all_locked": True,
        }
        self.gearbox = {
            "mode": config.GEAR_PARK,
            "last_change_ts": 0.0,
        }

        # --- Commands from external system (server / UI) ---
        self._commands = []

    # ========================================================
    # WebSocket / dashboard API (called by AZIZAServer)
    # ========================================================
    def command_window(self, window: int, direction: int, speed_pct: int = 50):
        """
        direction: WIN_STOP (0), WIN_UP (1), WIN_DOWN (2)
        Position 0 = fully closed (glass up), 100 = fully open (glass down).
        """
        window = int(max(0, min(3, window)))
        direction = int(direction)
        pos = self.windows["positions"].get(window, 0)
        step = max(10, min(40, int(speed_pct) // 2 or 20))

        if direction == config.WIN_STOP:
            self.windows["targets"][window] = pos
        elif direction == config.WIN_UP:
            self.windows["targets"][window] = max(0, pos - step)
        elif direction == config.WIN_DOWN:
            self.windows["targets"][window] = min(100, pos + step)

    def command_lights(self, mask: int, state: int):
        """mask: LIGHT_HEAD | LIGHT_INTERIOR | …  state: LIGHT_OFF / ON / DIM"""
        mask = int(mask)
        state = int(state)
        val = {config.LIGHT_OFF: "OFF", config.LIGHT_ON: "ON", config.LIGHT_DIM: "DIM"}.get(
            state, "OFF"
        )
        if mask & config.LIGHT_HEAD:
            self.lights["headlights"] = val
        if mask & config.LIGHT_INTERIOR:
            self.lights["interior"] = val
        if mask & config.LIGHT_HAZARD:
            self.lights["hazard"] = val
        if mask & config.LIGHT_FOG:
            self.lights["fog"] = val

    def command_door_lock(self, doors: int, command: int):
        """doors: bitmask (DOOR_FL | …). command: DOOR_UNLOCK (0) or DOOR_LOCK (1)."""
        locked = int(command) == config.DOOR_LOCK
        doors = int(doors)
        pairs = (
            (config.DOOR_FL, "FL"),
            (config.DOOR_FR, "FR"),
            (config.DOOR_RL, "RL"),
            (config.DOOR_RR, "RR"),
        )
        for bit, name in pairs:
            if doors & bit:
                self.door_locks[name] = locked
        self.door_locks["all_locked"] = all(
            self.door_locks[k] for k in ("FL", "FR", "RL", "RR")
        )

    def command_gearbox(self, mode: str):
        mode = str(mode).upper()
        if mode not in config.GEAR_SEQUENCE:
            return
        self.gearbox["mode"] = mode
        self.lin_bus_request(config.LIN_SLAVE_GEARBOX, {"mode": mode})

    # ========================================================
    # CAN MESSAGE PROCESSING
    # ========================================================
    def process_can_messages(self, messages):
        for msg in messages:
            if hasattr(msg, "msg_id"):
                msg_id = msg.msg_id
            elif hasattr(msg, "id"):
                msg_id = msg.id
            elif hasattr(msg, "arbitration_id"):            
                msg_id = msg.arbitration_id
            else:
                continue  # unknown format

            if hasattr(msg, "data"):
                data = msg.data
            elif hasattr(msg, "payload"):
                data = msg.payload
            else:
                continue

        # --- YOUR LOGIC ---
            if msg_id == 0x102:
                self.vehicle_speed = data

    # ========================================================
    # EXTERNAL COMMAND INTERFACE (called by server)
    # ========================================================
    def apply_command(self, command: dict):
        """
        Example commands:
        {"type": "window", "index": 0, "target": 100}
        {"type": "lock", "action": "unlock_all"}
        {"type": "light", "name": "headlights", "value": "ON"}
        """
        self._commands.append(command)

    # ========================================================
    # UPDATE LOOP
    # ========================================================
    def update(self, vehicle_speed=None):
        if vehicle_speed is not None:
            self.vehicle_speed = vehicle_speed

        # 1) Apply external commands
        self._process_commands()

        # 2) Automatic behaviors (realistic features)
        self._auto_lock_doors()
        # Headlights are controlled from the dashboard only (no speed override).

        # 3) Update actuators (LIN simulation)
        self._update_windows()

        return {
            "windows": self.windows,
            "lights": self.lights,
            "door_locks": self.door_locks,
            "gearbox": self.gearbox,
        }

    # ========================================================
    # COMMAND HANDLING
    # ========================================================
    def _process_commands(self):
        while self._commands:
            cmd = self._commands.pop(0)

            if cmd["type"] == "window":
                idx = cmd.get("index", 0)
                target = max(0, min(100, cmd.get("target", 0)))
                self.windows["targets"][idx] = target

            elif cmd["type"] == "lock":
                if cmd.get("action") == "lock_all":
                    self._set_all_locks(True)
                elif cmd.get("action") == "unlock_all":
                    self._set_all_locks(False)

            elif cmd["type"] == "light":
                name = cmd.get("name")
                value = cmd.get("value", "OFF")
                if name in self.lights:
                    self.lights[name] = value

    # ========================================================
    # AUTOMATIC LOGIC (REALISTIC BEHAVIOR)
    # ========================================================
    def _auto_lock_doors(self):
        # Lock all doors if speed > 20 km/h
        if self.vehicle_speed > 20 and not self.door_locks["all_locked"]:
            self._set_all_locks(True)

    # ========================================================
    # WINDOW CONTROL (SIMULATED MOTOR)
    # ========================================================
    def _update_windows(self):
        for idx in self.windows["positions"]:
            current = self.windows["positions"][idx]
            target  = self.windows["targets"][idx]

            step = 12
            if current < target:
                current = min(target, current + step)
            elif current > target:
                current = max(target, current - step)

            self.windows["positions"][idx] = max(0, min(100, current))

            # Simulate sending command over LIN
            self.lin_bus_request(f"window_{idx}", current)

    # ========================================================
    # DOOR LOCK HELPERS
    # ========================================================
    def _set_all_locks(self, locked: bool):
        self.door_locks["FL"] = locked
        self.door_locks["FR"] = locked
        self.door_locks["RL"] = locked
        self.door_locks["RR"] = locked
        self.door_locks["all_locked"] = locked

    # ========================================================
    # LIN BUS SIMULATION
    # ========================================================
    def lin_bus_request(self, device, value):
        """
        Simulate sending command to LIN slave device
        """
        try:
            self.lin_bus.request(device, value)
        except Exception:
            pass
