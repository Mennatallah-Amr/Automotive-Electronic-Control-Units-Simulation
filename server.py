# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# server.py — Built-in HTTP + WebSocket server (no dependencies)
# ============================================================

import json
import threading
import time
import hashlib
import base64
import struct
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from config import (
    CAN_ID_WINDOW_CMD, CAN_ID_LIGHT_CMD, CAN_ID_DOOR_LOCK_CMD,
    WIN_FL, WIN_FR, WIN_RL, WIN_RR,
    WIN_STOP, WIN_UP, WIN_DOWN,
    LIGHT_HEAD, LIGHT_INTERIOR, LIGHT_HAZARD, LIGHT_FOG,
    LIGHT_OFF, LIGHT_ON, LIGHT_DIM,
    DOOR_FL, DOOR_FR, DOOR_RL, DOOR_RR, DOOR_ALL,
    DOOR_UNLOCK, DOOR_LOCK, GEAR_PARK,
)


class AZIZAServer:
    def __init__(self, engine_ecu=None, brake_ecu=None, safety_layer=None,
                 car_control=None, port=8765):
        self.engine_ecu   = engine_ecu
        self.brake_ecu    = brake_ecu
        self.safety_layer = safety_layer
        self.car_control  = car_control   # CarControlECU reference
        self._port        = port

        self._manual_target_speed = 0.0
        self._manual_brake        = 0.0

        self._clients        = []
        self._lock           = threading.Lock()
        self._latest_payload = None
        self._server         = None

    def _make_handler(self):
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                pass  # Silence access logs

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    dashboard_path = Path(__file__).parent / "dashboard.html"
                    if dashboard_path.exists():
                        content = dashboard_path.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"dashboard.html not found")

                elif self.path.startswith("/ws"):
                    key = self.headers.get("Sec-WebSocket-Key", "")
                    accept = base64.b64encode(
                        hashlib.sha1(
                            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
                        ).digest()
                    ).decode()

                    self.send_response(101)
                    self.send_header("Upgrade", "websocket")
                    self.send_header("Connection", "Upgrade")
                    self.send_header("Sec-WebSocket-Accept", accept)
                    self.end_headers()

                    with server_ref._lock:
                        server_ref._clients.append(self)

                    if server_ref._latest_payload:
                        try:
                            self._ws_send(server_ref._latest_payload)
                        except Exception:
                            pass

                    try:
                        while True:
                            data = self._ws_recv()
                            if data is None:
                                break
                            try:
                                cmd = json.loads(data)
                                server_ref._handle_command(cmd)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    finally:
                        with server_ref._lock:
                            if self in server_ref._clients:
                                server_ref._clients.remove(self)

                else:
                    self.send_response(404)
                    self.end_headers()

            def _ws_send(self, text):
                payload = text.encode("utf-8")
                length  = len(payload)
                if length <= 125:
                    header = bytes([0x81, length])
                elif length <= 65535:
                    header = bytes([0x81, 126]) + struct.pack(">H", length)
                else:
                    header = bytes([0x81, 127]) + struct.pack(">Q", length)
                self.wfile.write(header + payload)
                self.wfile.flush()

            def _ws_send_pong(self, payload=b""):
                length = len(payload)
                if length <= 125:
                    header = bytes([0x8A, length])
                elif length <= 65535:
                    header = bytes([0x8A, 126]) + struct.pack(">H", length)
                else:
                    header = bytes([0x8A, 127]) + struct.pack(">Q", length)
                self.wfile.write(header + payload)
                self.wfile.flush()

            def _ws_recv(self):
                try:
                    self.connection.settimeout(60)
                    b1, b2 = self.rfile.read(2)
                    opcode = b1 & 0x0F
                    if opcode == 8:
                        return None
                    masked  = b2 & 0x80
                    length  = b2 & 0x7F
                    if length == 126:
                        length = struct.unpack(">H", self.rfile.read(2))[0]
                    elif length == 127:
                        length = struct.unpack(">Q", self.rfile.read(8))[0]
                    mask = self.rfile.read(4) if masked else b"\x00\x00\x00\x00"
                    data = bytearray(self.rfile.read(length))
                    if masked:
                        for i in range(len(data)):
                            data[i] ^= mask[i % 4]
                    # Ping frame => respond with pong and continue.
                    if opcode == 0x9:
                        self._ws_send_pong(bytes(data))
                        return ""
                    # Pong or non-text frame => ignore payload.
                    if opcode in (0xA, 0x2):
                        return ""
                    return data.decode("utf-8")
                except Exception:
                    return None

        return Handler

    # ------------------------------------------------------------------
    # Command dispatcher (called from WebSocket receive thread)
    # ------------------------------------------------------------------
    def _handle_command(self, cmd):
        action = cmd.get("action")

        # ── Engine / cruise ──────────────────────────────────────────
        if action == "cruise_on" and self.engine_ecu:
            self.engine_ecu.enable_cruise(float(cmd.get("target_speed", 80.0)))

        elif action == "cruise_off" and self.engine_ecu:
            self.engine_ecu.disable_cruise()

        elif action == "set_target_speed" and self.engine_ecu:
            value = float(cmd.get("value", 0.0))
            self.engine_ecu.target_speed = value
            self._manual_target_speed = max(0.0, value)

        # ── Brake ────────────────────────────────────────────────────
        elif action == "brake_press":
            pressure = float(cmd.get("pressure", 0.8))
            if self.brake_ecu is not None and hasattr(self.brake_ecu, "manual_pressure"):
                self.brake_ecu.manual_pressure = pressure
            self._manual_brake        = pressure
            self._manual_target_speed = 0.0   # braking cancels speed command

        elif action == "brake_release":
            if self.brake_ecu is not None and hasattr(self.brake_ecu, "manual_pressure"):
                self.brake_ecu.manual_pressure = 0.0
            self._manual_brake = 0.0

        # ── Windows ──────────────────────────────────────────────────
        elif action == "window_cmd" and self.car_control:
            # cmd = {action, window: 0-3, direction: 0/1/2, speed_pct: 0-100}
            self.car_control.command_window(
                window    = int(cmd.get("window",    WIN_FL)),
                direction = int(cmd.get("direction", WIN_STOP)),
                speed_pct = int(cmd.get("speed_pct", 50)),
            )

        # ── Lights ───────────────────────────────────────────────────
        elif action == "light_cmd" and self.car_control:
            # cmd = {action, mask: 0-15, state: 0/1/2}
            self.car_control.command_lights(
                mask  = int(cmd.get("mask",  LIGHT_HEAD)),
                state = int(cmd.get("state", LIGHT_ON)),
            )

        # ── Door locks ───────────────────────────────────────────────
        elif action == "door_lock_cmd" and self.car_control:
            # cmd = {action, doors: bitmask, command: 0=UNLOCK / 1=LOCK}
            self.car_control.command_door_lock(
                doors   = int(cmd.get("doors",   DOOR_ALL)),
                command = int(cmd.get("command", DOOR_LOCK)),
            )

        # ── Gearbox ───────────────────────────────────────────────────
        elif action == "gearbox_cmd" and self.car_control:
            # cmd = {action, mode: "P"/"R"/"N"/"D"}
            self.car_control.command_gearbox(
                mode=str(cmd.get("mode", GEAR_PARK)),
            )

    # ------------------------------------------------------------------
    # Push state to all connected WebSocket clients
    # ------------------------------------------------------------------
    def push_state(self, state: dict, log_lines: list, events: list = None):
        payload = json.dumps({
            "state":  state,
            "log":    log_lines,
            "events": events or [],
        })
        self._latest_payload = payload

        dead = []
        with self._lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client._ws_send(payload)
            except Exception:
                dead.append(client)
        if dead:
            with self._lock:
                for c in dead:
                    if c in self._clients:
                        self._clients.remove(c)

    def get_manual_brake(self) -> float:
        return getattr(self, "_manual_brake", 0.0)

    def get_manual_target_speed(self) -> float:
        return self._manual_target_speed

    def start(self):
        import sys as _sys
        _real_stdout = getattr(_sys.stdout, '_stdout', _sys.stdout)

        try:
            ThreadingHTTPServer.allow_reuse_address = True
            self._server = ThreadingHTTPServer(("0.0.0.0", self._port), self._make_handler())
        except OSError as e:
            _real_stdout.write(f"[SERVER] ERROR: Cannot bind to port {self._port} — {e}\n")
            _real_stdout.flush()
            return

        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.5)
        _real_stdout.write(f"[SERVER] Dashboard → http://localhost:{self._port}\n")
        _real_stdout.write(f"[SERVER] WebSocket → ws://localhost:{self._port}/ws\n")
        _real_stdout.write(f"[SERVER] Bound to 0.0.0.0:{self._port} OK\n")
        _real_stdout.flush()

