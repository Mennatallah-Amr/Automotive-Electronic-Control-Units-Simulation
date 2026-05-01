# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# ai/anomaly_detector.py — Rule-based AI anomaly detector
# ============================================================

from collections import deque
from config import (
    LOG_PREFIX,
    AI_TEMP_RISE_THRESHOLD,
    AI_HIGH_SPEED_THRESHOLD,
    AI_RISK_CRITICAL,
    AI_RISK_SUSPICIOUS,
)


class RiskLevel:
    NORMAL     = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    CRITICAL   = "CRITICAL"


class AnomalyReport:
    """
    Result of one AI analysis cycle.

    Contains:
        risk_level:   NORMAL | SUSPICIOUS | CRITICAL
        risk_score:   Numeric score (0+)
        anomalies:    List of triggered anomaly descriptions
        suggestions:  List of advisory strings for Safety Layer
    """

    def __init__(self, risk_level: str, risk_score: int, anomalies: list, suggestions: list):
        self.risk_level  = risk_level
        self.risk_score  = risk_score
        self.anomalies   = anomalies
        self.suggestions = suggestions

    def __repr__(self) -> str:
        return (
            f"AnomalyReport(level={self.risk_level}, score={self.risk_score}, "
            f"anomalies={self.anomalies}, suggestions={self.suggestions})"
        )


class AnomalyDetector:
    """
    AZIZA AI Agent — Rule-based anomaly detector and risk scorer.

    Architecture contract:
    - OBSERVER only: reads sensor data and system state.
    - ADVISOR only:  returns suggestions, never commands actuators.
    - Final authority belongs to the Safety Layer.

    Risk scoring rules:
        +2  Rapid temperature increase (≥ threshold per cycle)
        +2  Brake applied at high speed (≥ AI_HIGH_SPEED_THRESHOLD km/h)
        +3  Inconsistent sensor data (speed/brake contradiction)

    Risk levels:
        score < SUSPICIOUS  → NORMAL
        score ≥ SUSPICIOUS  → SUSPICIOUS
        score ≥ CRITICAL    → CRITICAL

    Suggestions it may return:
        "disable_cruise"  — when risk is elevated
        "reduce_speed"    — when speed is high with anomalies
    """

    HISTORY_SIZE = 10   # How many cycles of temperature history to keep

    def __init__(self):
        self._temp_history: deque[float] = deque(maxlen=self.HISTORY_SIZE)
        self._report_history: list[AnomalyReport] = []

        print(f"{LOG_PREFIX['AI']} AnomalyDetector initialized (rule-based engine).")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze(self, sensor_data: dict, system_state: dict) -> AnomalyReport:
        """
        Analyze current sensor data and system state.

        Args:
            sensor_data:   Raw dict {speed, temperature, brake}
            system_state:  Approved state from Safety Layer

        Returns:
            AnomalyReport with risk level, score, and suggestions.
        """
        speed       = sensor_data.get("speed", 0.0)
        temperature = sensor_data.get("temperature", 80.0)
        brake       = sensor_data.get("brake", 0.0)

        self._temp_history.append(temperature)

        risk_score = 0
        anomalies: list[str] = []
        suggestions: list[str] = []

        # --- Rule 1: Rapid temperature rise ---
        if self._detect_temp_spike():
            risk_score += 2
            anomalies.append(f"RapidTempRise: temp={temperature}°C")

        # --- Rule 2: Brake + high speed ---
        if brake > 0 and speed >= AI_HIGH_SPEED_THRESHOLD:
            risk_score += 2
            anomalies.append(f"BrakeAtHighSpeed: brake={brake:.2f}, speed={speed} km/h")

        # --- Rule 3: Inconsistent sensor data ---
        if self._detect_sensor_inconsistency(speed, brake, system_state):
            risk_score += 3
            anomalies.append("InconsistentSensorData: throttle+brake contradiction")

        # --- Derive risk level ---
        if risk_score >= AI_RISK_CRITICAL:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= AI_RISK_SUSPICIOUS:
            risk_level = RiskLevel.SUSPICIOUS
        else:
            risk_level = RiskLevel.NORMAL

        # --- Build advisory suggestions ---
        if risk_level in (RiskLevel.SUSPICIOUS, RiskLevel.CRITICAL):
            if system_state.get("cruise_active", False):
                suggestions.append("disable_cruise")
        if risk_level == RiskLevel.CRITICAL and speed >= AI_HIGH_SPEED_THRESHOLD:
            suggestions.append("reduce_speed")

        # --- Build report ---
        report = AnomalyReport(risk_level, risk_score, anomalies, suggestions)
        self._report_history.append(report)

        self._log_report(report)
        return report

    def get_report_history(self) -> list[AnomalyReport]:
        """Return all analysis reports across all cycles."""
        return list(self._report_history)

    # ------------------------------------------------------------------
    # Private detection helpers
    # ------------------------------------------------------------------

    def _detect_temp_spike(self) -> bool:
        """
        Returns True if temperature rose faster than the threshold
        between the two most recent recorded cycles.
        """
        if len(self._temp_history) < 2:
            return False
        recent_rise = self._temp_history[-1] - self._temp_history[-2]
        return recent_rise >= AI_TEMP_RISE_THRESHOLD

    def _detect_sensor_inconsistency(
        self, speed: float, brake: float, system_state: dict
    ) -> bool:
        """
        Returns True if throttle > 0 while brake is active (contradiction).
        This can indicate a sensor fault or unintended acceleration.
        """
        throttle = system_state.get("throttle", 0.0)
        return brake > 0 and throttle > 0.05

    def _log_report(self, report: AnomalyReport) -> None:
        level_str = report.risk_level
        anomaly_str = ", ".join(report.anomalies) if report.anomalies else "none"
        suggest_str = ", ".join(report.suggestions) if report.suggestions else "none"

        print(
            f"{LOG_PREFIX['AI']} Risk={level_str:<10} "
            f"Score={report.risk_score}  "
            f"Anomalies=[{anomaly_str}]  "
            f"Suggestions=[{suggest_str}]"
        )
