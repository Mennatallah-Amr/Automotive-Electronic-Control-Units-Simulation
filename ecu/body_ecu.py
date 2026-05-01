# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# ecu/body_ecu.py — Body ECU (LIN master, non-critical functions)
# ============================================================

import random
from config import LOG_PREFIX


class BodyECU:
    """
    AZIZA Body ECU.

    Controls non-critical body functions via LIN bus (master role):
        - Interior lighting
        - Door lock status
        - HVAC fan speed

    LIN slaves are registered at startup. The Body ECU polls them
    each cycle and reacts to their responses.

    This ECU deliberately operates on the LIN bus (not CAN) because
    its functions are non-critical and do not require the high
    reliability/priority of CAN.
    """

    def __init__(self, lin_bus):
        self.lin_bus = lin_bus
        self.lighting_on: bool = False
        self.doors_locked: bool = True
        self.fan_speed: int = 1        # 0–3

        self._cycle: int = 0
        self._register_slaves()
        print(f"{LOG_PREFIX['BODY']} BodyECU initialized (LIN master).")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self, vehicle_speed: float = 0.0) -> dict:
        """
        Poll LIN slaves and update body state.
        Returns current body state dict.
        """
        self._cycle += 1

        # Auto-lock doors at speed > 10 km/h
        if vehicle_speed > 10.0 and not self.doors_locked:
            self.doors_locked = True
            print(f"{LOG_PREFIX['BODY']} Speed lock engaged — doors locked.")

        # Poll lighting slave
        light_response = self.lin_bus.master_request(
            "LIN_LIGHTING",
            {"command": "STATUS", "speed": vehicle_speed}
        )
        if light_response:
            self.lighting_on = light_response.get("lights_on", self.lighting_on)

        # Poll HVAC slave every 3 cycles
        if self._cycle % 3 == 0:
            hvac_response = self.lin_bus.master_request(
                "LIN_HVAC",
                {"command": "STATUS"}
            )
            if hvac_response:
                self.fan_speed = hvac_response.get("fan_speed", self.fan_speed)

        state = {
            "lighting_on":   self.lighting_on,
            "doors_locked":  self.doors_locked,
            "fan_speed":     self.fan_speed,
        }

        print(
            f"{LOG_PREFIX['BODY']} Lights={'ON' if self.lighting_on else 'OFF'}  "
            f"Doors={'LOCKED' if self.doors_locked else 'UNLOCKED'}  "
            f"Fan={self.fan_speed}"
        )

        return state

    # ------------------------------------------------------------------
    # LIN slave registration
    # ------------------------------------------------------------------

    def _register_slaves(self) -> None:
        """Register LIN slave handlers for body subsystems."""

        def lighting_handler(request: dict) -> dict:
            """Simulated lighting slave: turns on lights at night (random)."""
            speed = request.get("speed", 0)
            # Simulate ambient light sensor — randomly toggle
            lights = random.random() < 0.3 or speed > 80
            return {"lights_on": lights}

        def hvac_handler(request: dict) -> dict:
            """Simulated HVAC slave: adjusts fan speed randomly."""
            fan = random.randint(0, 3)
            return {"fan_speed": fan}

        self.lin_bus.register_slave("LIN_LIGHTING", lighting_handler)
        self.lin_bus.register_slave("LIN_HVAC", hvac_handler)
