# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# ecu/engine_ecu.py — Engine ECU (cruise control + overheat)
# ============================================================

from config import (
    LOG_PREFIX,
    CAN_ID_TEMPERATURE, CAN_ID_SPEED,
    ENGINE_TEMP_WARN, ENGINE_TEMP_LIMIT,
)


class EngineState:
    NORMAL  = "NORMAL"
    REDUCED = "REDUCED"       # Overheat warning — throttle reduced
    LIMITED = "LIMITED"       # Critical overheat — engine limited
    OFF     = "OFF"


class EngineECU:
    """
    AZIZA Engine ECU.

    Responsibilities:
    - Cruise control: maintain a target speed by adjusting throttle.
    - Overheat protection:
        temp > 100°C  → reduce throttle (REDUCED state)
        temp > 120°C  → engine LIMITED (maximum restriction)

    Reads from CAN bus:
        0x101 — temperature
        0x102 — speed

    Does NOT write to actuators directly — reports desired state
    to the Safety Layer for final authority.
    """

    def __init__(self):
        self.state: str = EngineState.NORMAL
        self.throttle: float = 0.0        # 0.0 – 1.0
        self.cruise_enabled: bool = False
        self.target_speed: float = 80.0   # km/h

        self._current_speed: float = 0.0
        self._current_temp: float = 80.0

        print(f"{LOG_PREFIX['ENGINE']} EngineECU initialized. State={self.state}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_can_messages(self, messages: list) -> None:
        """Parse relevant CAN messages and update internal state."""
        for msg in messages:
            if msg.msg_id == CAN_ID_TEMPERATURE:
                self._current_temp = msg.data.get("temp", self._current_temp)
            elif msg.msg_id == CAN_ID_SPEED:
                self._current_speed = msg.data.get("speed", self._current_speed)

    def update(self) -> dict:
        """
        Run one ECU control cycle.

        Returns a desired-state dict for the Safety Layer to validate.
        """
        self._apply_overheat_protection()

        if self.state != EngineState.OFF:
            self._apply_cruise_control()

        desired = {
            "throttle":      round(self.throttle, 3),
            "engine_state":  self.state,
            "cruise_active": self.cruise_enabled,
        }

        self._log_state()
        return desired

    def enable_cruise(self, target_speed: float | None = None) -> None:
        """Enable cruise control, optionally setting a new target speed."""
        self.cruise_enabled = True
        if target_speed is not None:
            self.target_speed = target_speed
        print(f"{LOG_PREFIX['ENGINE']} Cruise ENABLED — target={self.target_speed} km/h")

    def disable_cruise(self) -> None:
        """Disable cruise control (from safety layer or Blynk)."""
        self.cruise_enabled = False
        print(f"{LOG_PREFIX['ENGINE']} Cruise DISABLED")

    def apply_safety_override(self, command: str) -> None:
        """
        Accept a command from the Safety Layer.
        Valid commands: 'LIMIT', 'REDUCE', 'OFF', 'RESET'
        """
        if command == "LIMIT":
            self.state = EngineState.LIMITED
            self.throttle = min(self.throttle, 0.2)
            self.cruise_enabled = False
        elif command == "REDUCE":
            self.state = EngineState.REDUCED
            self.throttle = min(self.throttle, 0.5)
        elif command == "OFF":
            self.state = EngineState.OFF
            self.throttle = 0.0
            self.cruise_enabled = False
        elif command == "RESET":
            if self._current_temp < ENGINE_TEMP_WARN:
                self.state = EngineState.NORMAL

    # ------------------------------------------------------------------
    # Private control logic
    # ------------------------------------------------------------------

    def _apply_overheat_protection(self) -> None:
        """Enforce temperature-based engine protection rules."""
        if self._current_temp > ENGINE_TEMP_LIMIT:
            if self.state != EngineState.LIMITED:
                print(f"{LOG_PREFIX['ENGINE']} Overheat CRITICAL ({self._current_temp}°C) → engine LIMITED")
                self.state = EngineState.LIMITED
                self.throttle = min(self.throttle, 0.2)
                self.cruise_enabled = False

        elif self._current_temp > ENGINE_TEMP_WARN:
            if self.state == EngineState.NORMAL:
                print(f"{LOG_PREFIX['ENGINE']} Overheat WARNING ({self._current_temp}°C) → reducing throttle")
                self.state = EngineState.REDUCED
                self.throttle = min(self.throttle, 0.5)

        else:
            # Temperature back in safe zone
            if self.state == EngineState.REDUCED:
                self.state = EngineState.NORMAL

    def _apply_cruise_control(self) -> None:
        """
        Simple proportional cruise controller.
        Adjusts throttle to maintain target speed.
        """
        if not self.cruise_enabled:
            return

        error = self.target_speed - self._current_speed
        adjustment = error * 0.02   # Proportional gain

        self.throttle = max(0.0, min(1.0, self.throttle + adjustment))

        # Apply state-based throttle caps
        if self.state == EngineState.LIMITED:
            self.throttle = min(self.throttle, 0.2)
        elif self.state == EngineState.REDUCED:
            self.throttle = min(self.throttle, 0.5)

    def _log_state(self) -> None:
        state_str = self.state
        cruise_str = f"Cruise={'ON' if self.cruise_enabled else 'OFF'}"
        print(
            f"{LOG_PREFIX['ENGINE']} State={state_str:<8}  "
            f"Throttle={self.throttle:.2f}  {cruise_str}"
        )
