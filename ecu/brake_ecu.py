# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# ecu/brake_ecu.py — Brake ECU (brake override logic)
# ============================================================

from config import LOG_PREFIX, CAN_ID_BRAKE, CAN_ID_SPEED


class BrakeECU:
    """
    AZIZA Brake ECU.

    Safety-critical rule:
        If brake pressure > 0  →  force throttle = 0  (engine cannot
        accelerate while braking — prevents unintended acceleration).

    Also monitors speed during braking for anomaly reporting.

    Reads from CAN:
        0x201 — brake pressure
        0x102 — vehicle speed

    Reports desired throttle override to Safety Layer.
    """

    def __init__(self):
        self.brake_pressure: float = 0.0
        self.brake_active: bool = False
        self._current_speed: float = 0.0
        print(f"{LOG_PREFIX['BRAKE']} BrakeECU initialized.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_can_messages(self, messages: list) -> None:
        """Parse relevant CAN messages."""
        for msg in messages:
            if msg.msg_id == CAN_ID_BRAKE:
                self.brake_pressure = msg.data.get("brake", self.brake_pressure)
            elif msg.msg_id == CAN_ID_SPEED:
                self._current_speed = msg.data.get("speed", self._current_speed)

    def update(self) -> dict:
        """
        Run one brake control cycle.

        Returns desired override dict for Safety Layer.
        """
        self.brake_active = self.brake_pressure > 0.0

        override = {
            "brake_active":    self.brake_active,
            "brake_pressure":  round(self.brake_pressure, 2),
            "throttle_force":  0.0 if self.brake_active else None,  # None = no override
        }

        if self.brake_active:
            print(
                f"{LOG_PREFIX['BRAKE']} BRAKE ACTIVE "
                f"(pressure={self.brake_pressure:.2f}) → throttle forced 0"
            )
        else:
            print(f"{LOG_PREFIX['BRAKE']} Brake released.")

        return override

    @property
    def is_braking(self) -> bool:
        return self.brake_active

    @property
    def speed_during_brake(self) -> float:
        """Speed at time of braking — used by AI for risk scoring."""
        return self._current_speed if self.brake_active else 0.0
