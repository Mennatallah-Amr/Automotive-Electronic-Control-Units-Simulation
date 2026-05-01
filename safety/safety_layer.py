# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# safety/safety_layer.py — Safety Layer (final authority)
# ============================================================

from config import (
    LOG_PREFIX,
    SAFETY_MAX_SPEED, SAFETY_MAX_TEMP,
    ENGINE_TEMP_WARN, ENGINE_TEMP_LIMIT,
    AI_HIGH_SPEED_THRESHOLD,
)
from ecu.engine_ecu import EngineState


class SafetyViolation:
    """Describes a single safety constraint violation."""

    def __init__(self, code: str, description: str, severity: str = "WARNING"):
        self.code = code
        self.description = description
        self.severity = severity     # "WARNING" | "CRITICAL"

    def __repr__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.description}"


class SafetyLayer:
    """
    AZIZA Safety Layer — the final authority in the system.

    Responsibilities:
    1. Validate sensor readings (detect implausible values).
    2. Enforce hard physical constraints (speed cap, temp cap).
    3. Arbitrate between Engine ECU and Brake ECU outputs.
    4. Validate AI advisor suggestions before forwarding to ECUs.
    5. Log all violations.

    Architecture rule: No other component overrides the Safety Layer.
    The AI Agent is observer + advisor only; its suggestions are
    validated here before any action is taken.
    """

    def __init__(self, engine_ecu, brake_ecu):
        self.engine_ecu = engine_ecu
        self.brake_ecu = brake_ecu

        self._violations: list[SafetyViolation] = []
        self._cycle_violations: list[SafetyViolation] = []

        print(f"{LOG_PREFIX['SAFETY']} SafetyLayer initialized — AUTHORITY ACTIVE.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate(
        self,
        sensor_data: dict,
        engine_desired: dict,
        brake_desired: dict,
        ai_suggestions: list[str],
    ) -> dict:
        """
        Main evaluation entry point called each simulation cycle.

        Args:
            sensor_data:     Raw sensor readings dict.
            engine_desired:  Desired state from EngineECU.update().
            brake_desired:   Override request from BrakeECU.update().
            ai_suggestions:  List of suggestion strings from AI agent.

        Returns:
            Approved system state dict after all constraints applied.
        """
        self._cycle_violations = []

        # Step 1: Validate sensor plausibility
        clean_data = self._validate_sensors(sensor_data)

        # Step 2: Apply brake override (unconditional physical law)
        throttle = engine_desired.get("throttle", 0.0)
        if brake_desired.get("brake_active", False):
            throttle = 0.0
            self._record("BRAKE_OVERRIDE", "Brake active → throttle forced to 0", "WARNING")

        # Step 3: Enforce engine temperature constraints
        engine_state = engine_desired.get("engine_state", EngineState.NORMAL)
        temp = clean_data.get("temperature", 80.0)

        if temp > ENGINE_TEMP_LIMIT:
            engine_state = EngineState.LIMITED
            throttle = min(throttle, 0.2)
            self._record("OVERHEAT_LIMITED", f"Temp={temp}°C → Engine LIMITED", "CRITICAL")
            self.engine_ecu.apply_safety_override("LIMIT")
            print(f"{LOG_PREFIX['SAFETY']} Engine LIMITED — temp critical ({temp}°C)")

        elif temp > ENGINE_TEMP_WARN:
            if engine_state == EngineState.NORMAL:
                engine_state = EngineState.REDUCED
                throttle = min(throttle, 0.5)
                self._record("OVERHEAT_REDUCED", f"Temp={temp}°C → Throttle reduced", "WARNING")
                self.engine_ecu.apply_safety_override("REDUCE")

        # Step 4: Hard speed cap (physical limit)
        speed = clean_data.get("speed", 0.0)
        if speed > SAFETY_MAX_SPEED:
            throttle = 0.0
            self._record("SPEED_CAP", f"Speed={speed} exceeds max {SAFETY_MAX_SPEED} km/h", "CRITICAL")
            print(f"{LOG_PREFIX['SAFETY']} Speed cap enforced — throttle cut.")

        # Step 5: Process validated AI suggestions
        self._process_ai_suggestions(ai_suggestions, speed)

        # Step 6: Log cycle summary
        approved_state = {
            "throttle":      round(throttle, 3),
            "engine_state":  engine_state,
            "cruise_active": engine_desired.get("cruise_active", False),
            "brake_active":  brake_desired.get("brake_active", False),
            "brake_pressure": brake_desired.get("brake_pressure", 0.0),
            "speed":         speed,
            "temperature":   temp,
            "violations":    [str(v) for v in self._cycle_violations],
        }

        if self._cycle_violations:
            for v in self._cycle_violations:
                print(f"{LOG_PREFIX['SAFETY']} {v}")

        return approved_state

    def get_all_violations(self) -> list[SafetyViolation]:
        """Return all recorded violations across all cycles."""
        return list(self._violations)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_sensors(self, sensor_data: dict) -> dict:
        """
        Check for implausible sensor values.
        Clamps out-of-range readings and logs violations.
        """
        clean = dict(sensor_data)

        speed = sensor_data.get("speed", 0.0)
        if not (0 <= speed <= 250):
            self._record("INVALID_SPEED", f"Implausible speed={speed}", "CRITICAL")
            clean["speed"] = max(0, min(250, speed))

        temp = sensor_data.get("temperature", 80.0)
        if not (40 <= temp <= 200):
            self._record("INVALID_TEMP", f"Implausible temp={temp}", "CRITICAL")
            clean["temperature"] = max(40, min(200, temp))

        brake = sensor_data.get("brake", 0.0)
        if not (0.0 <= brake <= 1.0):
            self._record("INVALID_BRAKE", f"Implausible brake={brake}", "WARNING")
            clean["brake"] = max(0.0, min(1.0, brake))

        return clean

    def _process_ai_suggestions(self, suggestions: list[str], speed: float) -> None:
        """
        Validate and act on AI suggestions.
        Each suggestion is validated against current state before forwarding.
        """
        for suggestion in suggestions:
            if suggestion == "disable_cruise":
                # Safe to apply unconditionally
                self.engine_ecu.disable_cruise()
                print(f"{LOG_PREFIX['SAFETY']} AI suggestion APPROVED: disable_cruise")

            elif suggestion == "reduce_speed":
                # Only enforce if speed is genuinely high
                if speed > AI_HIGH_SPEED_THRESHOLD:
                    self.engine_ecu.apply_safety_override("REDUCE")
                    print(f"{LOG_PREFIX['SAFETY']} AI suggestion APPROVED: reduce_speed (speed={speed})")
                else:
                    print(f"{LOG_PREFIX['SAFETY']} AI suggestion REJECTED: reduce_speed not warranted (speed={speed})")

            else:
                print(f"{LOG_PREFIX['SAFETY']} AI suggestion UNKNOWN/REJECTED: '{suggestion}'")

    def _record(self, code: str, description: str, severity: str = "WARNING") -> None:
        violation = SafetyViolation(code, description, severity)
        self._cycle_violations.append(violation)
        self._violations.append(violation)
