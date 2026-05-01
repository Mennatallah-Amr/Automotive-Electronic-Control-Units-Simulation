# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# telemetry/blynk_client.py — Blynk telemetry integration
# ============================================================

import threading
from config import (
    LOG_PREFIX,
    BLYNK_AUTH_TOKEN, BLYNK_SERVER, BLYNK_PORT,
    VPIN_SPEED, VPIN_TEMPERATURE, VPIN_BRAKE,
    VPIN_ENGINE_STATE, VPIN_AI_RISK, VPIN_CRUISE_TOGGLE,
)


class BlynkClient:
    """
    AZIZA Telemetry Layer — Blynk integration.

    Responsibilities:
    - Stream live vehicle data to the Blynk cloud dashboard.
    - Accept non-critical commands from Blynk (cruise toggle).
    - Degrade gracefully: system continues if Blynk disconnects.

    Virtual Pins:
        V0 → speed (km/h)
        V1 → temperature (°C)
        V2 → brake pressure (0.0–1.0)
        V3 → engine state string
        V4 → AI risk level string
        V5 → cruise control toggle (input from Blynk)

    Architecture rule:
        Blynk can only toggle cruise control (non-critical).
        It cannot directly command throttle, brakes, or safety limits.
    """

    def __init__(self, engine_ecu):
        self.engine_ecu = engine_ecu
        self._connected = False
        self._blynk = None
        self._thread: threading.Thread | None = None
        self._cruise_toggle_requested: bool = False
        self._last_sent: dict = {}

        self._init_blynk()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def send_telemetry(
        self,
        speed: float,
        temperature: float,
        brake: float,
        engine_state: str,
        ai_risk: str,
    ) -> None:
        """
        Push current vehicle telemetry to Blynk virtual pins.
        Safe to call even when disconnected (silently skips).
        """
        if not self._connected or self._blynk is None:
            print(f"{LOG_PREFIX['BLYNK']} Not connected — telemetry skipped.")
            return

        try:
            self._blynk.virtual_write(int(VPIN_SPEED[1:]),        speed)
            self._blynk.virtual_write(int(VPIN_TEMPERATURE[1:]),  temperature)
            self._blynk.virtual_write(int(VPIN_BRAKE[1:]),        brake)
            self._blynk.virtual_write(int(VPIN_ENGINE_STATE[1:]), engine_state)
            self._blynk.virtual_write(int(VPIN_AI_RISK[1:]),      ai_risk)

            self._last_sent = {
                "speed": speed, "temperature": temperature,
                "brake": brake, "engine_state": engine_state,
                "ai_risk": ai_risk,
            }

            print(
                f"{LOG_PREFIX['BLYNK']} TX → "
                f"V0={speed}  V1={temperature}  V2={brake}  "
                f"V3={engine_state}  V4={ai_risk}"
            )

        except Exception as exc:
            self._connected = False
            print(f"{LOG_PREFIX['BLYNK']} Send error: {exc} — marked disconnected.")

    def run_loop(self) -> None:
        """
        Process Blynk event loop (incoming commands).
        Call once per simulation cycle.
        """
        if not self._connected or self._blynk is None:
            return
        try:
            self._blynk.run()
        except Exception as exc:
            self._connected = False
            print(f"{LOG_PREFIX['BLYNK']} Loop error: {exc}")

    def is_connected(self) -> bool:
        return self._connected

    def get_last_sent(self) -> dict:
        return dict(self._last_sent)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_blynk(self) -> None:
        """
        Attempt to initialize and connect the Blynk client.
        Falls back gracefully if blynklib is not installed or token is invalid.
        """
        if BLYNK_AUTH_TOKEN == "YOUR_BLYNK_TOKEN_HERE":
            print(f"{LOG_PREFIX['BLYNK']} No token configured — running in offline mode.")
            return

        try:
            import blynklib
            self._blynk = blynklib.Blynk(
                BLYNK_AUTH_TOKEN,
                server=BLYNK_SERVER,
                port=BLYNK_PORT,
                ssl_cert=None,
                heartbeat=10,
                rcv_buffer=1024,
                log=None,
            )
            self._register_handlers()
            self._connected = True
            print(f"{LOG_PREFIX['BLYNK']} Connected to Blynk cloud.")

        except ImportError:
            print(
                f"{LOG_PREFIX['BLYNK']} blynklib not installed — "
                "running in offline mode. Install with: pip install blynklib"
            )
        except Exception as exc:
            print(f"{LOG_PREFIX['BLYNK']} Connection failed: {exc} — offline mode.")

    def _register_handlers(self) -> None:
        """Register Blynk virtual pin read handlers."""
        if self._blynk is None:
            return

        @self._blynk.handle_event(f"write {VPIN_CRUISE_TOGGLE[1:]}")
        def cruise_toggle_handler(pin, value):
            """
            V5 write handler — Blynk cruise control toggle.
            This is the only Blynk-originated command allowed.
            """
            state = str(value[0]).strip()
            print(f"{LOG_PREFIX['BLYNK']} Cruise toggle received from Blynk: {state}")
            if state == "1":
                self.engine_ecu.enable_cruise()
            else:
                self.engine_ecu.disable_cruise()
