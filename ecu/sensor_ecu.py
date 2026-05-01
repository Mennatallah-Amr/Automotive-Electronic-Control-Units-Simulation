# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# ecu/sensor_ecu.py — Sensor ECU (speed, temperature, brake)
# ============================================================

from config import (
    LOG_PREFIX,
    CAN_ID_TEMPERATURE, CAN_ID_SPEED, CAN_ID_BRAKE,
    SENSOR_SPEED_MIN, SENSOR_SPEED_MAX,
    SENSOR_TEMP_MIN, SENSOR_TEMP_MAX,
    SENSOR_BRAKE_MIN, SENSOR_BRAKE_MAX,
)


class SensorECU:
    """
    AZIZA Sensor ECU.

    Simulates physical vehicle sensors and publishes readings
    onto the CAN bus. All values are deterministic with smooth
    realistic transitions — no random jumps.

    CAN IDs published:
        0x101 → engine temperature (°C)
        0x102 → vehicle speed (km/h)
        0x201 → brake pressure (0.0–1.0)
    """

    def __init__(self, can_bus):
        self.can_bus = can_bus

        # Internal state — smooth simulation
        self._speed: float = 0.0
        self._temperature: float = 80.0
        self._brake: float = 0.0

        # Simulation trajectory helpers
        self._target_speed: float = 60.0
        self._cycle: int = 0
        self._manual_brake: float = 0.0
        self._manual_target_speed: float = 0.0

        print(f"{LOG_PREFIX['SENSOR']} SensorECU initialized.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def read_and_publish(self) -> dict:
        """
        Sample all sensors, publish to CAN bus, and return raw readings.
        Called once per main loop cycle.
        """
        self._cycle += 1
        # Apply brake input first so speed update uses latest pedal state.
        self._update_brake()
        self._update_speed()
        self._update_temperature()

        readings = {
            "speed":       round(self._speed, 1),
            "temperature": round(self._temperature, 1),
            "brake":       round(self._brake, 2),
        }

        # Publish to CAN bus
        self.can_bus.send(CAN_ID_TEMPERATURE, {"temp": readings["temperature"]})
        self.can_bus.send(CAN_ID_SPEED,       {"speed": readings["speed"]})
        self.can_bus.send(CAN_ID_BRAKE,       {"brake": readings["brake"]})

        print(
            f"{LOG_PREFIX['SENSOR']} "
            f"Speed={readings['speed']} km/h  "
            f"Temp={readings['temperature']} °C  "
            f"Brake={readings['brake']}"
        )

        return readings

    @property
    def speed(self) -> float:
        return round(self._speed, 1)

    @property
    def temperature(self) -> float:
        return round(self._temperature, 1)

    @property
    def brake(self) -> float:
        return round(self._brake, 2)

    def set_manual_brake(self, pressure: float) -> None:
        """
        Accept operator/dashboard brake input.
        Any value > 0 immediately overrides random brake simulation.
        """
        self._manual_brake = max(SENSOR_BRAKE_MIN, min(SENSOR_BRAKE_MAX, pressure))

    def set_manual_target_speed(self, target_speed: float) -> None:
        """
        Accept operator/dashboard speed command.
        Vehicle starts from idle and moves only toward this target.
        """
        self._manual_target_speed = max(SENSOR_SPEED_MIN, min(SENSOR_SPEED_MAX, target_speed))

    # ------------------------------------------------------------------
    # Private simulation helpers
    # ------------------------------------------------------------------

    def _update_speed(self) -> None:
        """
        Manual speed simulation:
        - Vehicle moves only toward operator-selected target speed.
        - Brake pressure adds additional deceleration.
        """
        if self._brake > 0.0:
            # While braking, brake dynamics dominate and acceleration is suppressed.
            self._speed -= (3.0 + (14.0 * self._brake))
        else:
            self._target_speed = self._manual_target_speed
            delta = self._target_speed - self._speed
            if delta >= 0:
                self._speed += delta * 0.25
            else:
                self._speed += delta * 0.18

        self._speed = max(SENSOR_SPEED_MIN, min(SENSOR_SPEED_MAX, self._speed))

    def _update_temperature(self) -> None:
        """
        Deterministic thermal behavior from speed/load only.
        """
        load_factor = self._speed / SENSOR_SPEED_MAX
        natural_heat = load_factor * 0.8
        cooling = 0.3 if self._temperature > 90 else 0.0
        self._temperature += natural_heat - cooling
        self._temperature = max(SENSOR_TEMP_MIN, min(SENSOR_TEMP_MAX, self._temperature))

    def _update_brake(self) -> None:
        """
        Manual brake only: no automatic/random brake events.
        """
        if self._manual_brake > 0.0:
            # Manual input has highest priority for immediate response.
            self._brake = self._manual_brake
            return
        self._brake = 0.0
