#!/usr/bin/env python3
# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# main.py — Entry point and real-time simulation loop
# ============================================================

import sys
import os
import time
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from bus.can_bus import CANBus
from bus.lin_bus import LINBus
from ecu.sensor_ecu import SensorECU
from ecu.engine_ecu import EngineECU
from ecu.brake_ecu  import BrakeECU
from ecu.body_ecu   import BodyECU
from ecu.car_control_ecu import CarControlECU
from safety.safety_layer import SafetyLayer
from ai.anomaly_detector import AnomalyDetector
from telemetry.blynk_client import BlynkClient
from server import AZIZAServer

BANNER = r"""
  █████╗ ███████╗██╗███████╗ █████╗
 ██╔══██╗╚══███╔╝██║╚══███╔╝██╔══██╗
 ███████║  ███╔╝ ██║  ███╔╝ ███████║
 ██╔══██║ ███╔╝  ██║ ███╔╝  ██╔══██║
 ██║  ██║███████╗██║███████╗██║  ██║
 ╚═╝  ╚═╝╚══════╝╚═╝╚══════╝╚═╝  ╚═╝
 Distributed Automotive ECU Simulation
"""

class LogCapture:
    def __init__(self, original_stdout):
        self._stdout = original_stdout
        self._buf = []

    def write(self, text):
        self._stdout.write(text)
        stripped = text.rstrip('\n')
        if stripped:
            self._buf.append(stripped)

    def flush(self):
        self._stdout.flush()

    def drain(self):
        lines = list(self._buf)
        self._buf.clear()
        return lines


class AZIZASimulation:
    def __init__(self):
        self._log = LogCapture(sys.stdout)
        sys.stdout = self._log

        print(BANNER)
        print(f"{config.LOG_PREFIX['AZIZA']} Initializing AZIZA system...\n")

        self.can_bus      = CANBus()
        self.lin_bus      = LINBus()
        self.sensor_ecu   = SensorECU(self.can_bus)
        self.engine_ecu   = EngineECU()
        self.brake_ecu    = BrakeECU()
        self.body_ecu     = BodyECU(self.lin_bus)
        self.car_control  = CarControlECU(self.can_bus, self.lin_bus)
        self.safety_layer = SafetyLayer(self.engine_ecu, self.brake_ecu)
        self.ai_agent     = AnomalyDetector()
        self.blynk        = BlynkClient(self.engine_ecu)
        self.server       = AZIZAServer(
            engine_ecu=self.engine_ecu,
            brake_ecu=self.brake_ecu,
            car_control=self.car_control,
        )
        self.server.start()

        self._running        = True
        self._cycle          = 0
        self._body_state     = {}
        self._car_ctrl_state = {}

        self.engine_ecu.disable_cruise()

        signal.signal(signal.SIGINT,  self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        print(f"\n{config.LOG_PREFIX['AZIZA']} System ready. Starting simulation loop.")
        print(f"{config.LOG_PREFIX['AZIZA']} Dashboard → http://127.0.0.1:8765\n")

    def run(self):
        while self._running:
            self._cycle += 1
            print(f"\n{'─'*70}\n  AZIZA CYCLE #{self._cycle:04d}\n{'─'*70}")

            self.sensor_ecu.set_manual_target_speed(self.server.get_manual_target_speed())
            self.sensor_ecu.set_manual_brake(self.server.get_manual_brake())
            sensor_data  = self.sensor_ecu.read_and_publish()
            can_messages = self.can_bus.receive_all()

            # --- Process CAN messages in all ECUs ---
            self.engine_ecu.process_can_messages(can_messages)
            self.brake_ecu.process_can_messages(can_messages)
            self.car_control.process_can_messages(can_messages)

            # --- Update ECUs ---
            engine_desired       = self.engine_ecu.update()
            brake_desired        = self.brake_ecu.update()
            self._body_state     = self.body_ecu.update(vehicle_speed=sensor_data["speed"])
            self._car_ctrl_state = self.car_control.update(vehicle_speed=sensor_data["speed"])

            # --- Safety layer (first pass) ---
            approved_state = self.safety_layer.evaluate(
                sensor_data=sensor_data,
                engine_desired=engine_desired,
                brake_desired=brake_desired,
                ai_suggestions=[],
            )

            # --- AI anomaly detection ---
            ai_report = self.ai_agent.analyze(sensor_data, approved_state)

            # --- Safety layer (second pass with AI suggestions) ---
            if ai_report.suggestions:
                approved_state = self.safety_layer.evaluate(
                    sensor_data=sensor_data,
                    engine_desired=engine_desired,
                    brake_desired=brake_desired,
                    ai_suggestions=ai_report.suggestions,
                )

            # --- Telemetry ---
            self.blynk.run_loop()
            self.blynk.send_telemetry(
                speed=approved_state["speed"],
                temperature=approved_state["temperature"],
                brake=approved_state["brake_pressure"],
                engine_state=approved_state["engine_state"],
                ai_risk=ai_report.risk_level,
            )

            self._print_footer(approved_state, ai_report)

            # --- Car control state for dashboard ---
            cc = self._car_ctrl_state
            win_pos   = cc.get("windows",    {}).get("positions", {})
            lgt       = cc.get("lights",     {})
            locks     = cc.get("door_locks", {})

            dashboard_state = {
                **approved_state,
                "ai_risk":    ai_report.risk_level,
                "ai_score":   ai_report.risk_score,
                # Body ECU (legacy HVAC / ambient lighting)
                "lights_on":  self._body_state.get("lighting_on", False),
                "fan_speed":  self._body_state.get("fan_speed", 0),
                # Car Control ECU
                "win_FL":  win_pos.get(0, 0),
                "win_FR":  win_pos.get(1, 0),
                "win_RL":  win_pos.get(2, 0),
                "win_RR":  win_pos.get(3, 0),
                "light_headlights": lgt.get("headlights", "OFF"),
                "light_interior":   lgt.get("interior",   "OFF"),
                "light_hazard":     lgt.get("hazard",     "OFF"),
                "light_fog":        lgt.get("fog",        "OFF"),
                "door_FL":  locks.get("FL",  True),
                "door_FR":  locks.get("FR",  True),
                "door_RL":  locks.get("RL",  True),
                "door_RR":  locks.get("RR",  True),
                "all_locked": locks.get("all_locked", True),
                "cycle":      self._cycle,
            }
            self.server.push_state(dashboard_state, self._log.drain())

            time.sleep(config.SIMULATION_CYCLE_SECONDS)

            if config.SIMULATION_DURATION and self._cycle >= config.SIMULATION_DURATION:
                self._shutdown()

    def _handle_shutdown(self, signum, frame):
        print(f"\n{config.LOG_PREFIX['AZIZA']} Shutting down...")
        self._shutdown()

    def _shutdown(self):
        self._running = False
        self.can_bus.flush()
        sys.stdout = self._log._stdout
        print(f"{config.LOG_PREFIX['AZIZA']} AZIZA stopped. Goodbye.\n")
        sys.exit(0)

    def _print_footer(self, s, ai):
        print(f"\n  ┌─ APPROVED STATE {'─'*49}┐")
        print(f"  │ Speed: {s['speed']:>6.1f} km/h  Temp: {s['temperature']:>6.1f}°C  Throttle: {s['throttle']:.3f}  Brake: {'YES' if s['brake_active'] else 'NO':<3} │")
        print(f"  │ Engine: {s['engine_state']:<10}  AI Risk: {ai.risk_level:<12}  Cruise: {'ON' if s['cruise_active'] else 'OFF':<3}          │")
        for v in s.get("violations", []):
            print(f"  │ ⚠  {v:<65} │")
        print(f"  └{'─'*68}┘")


if __name__ == "__main__":
    AZIZASimulation().run()
