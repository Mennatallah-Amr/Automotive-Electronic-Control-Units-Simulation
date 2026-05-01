# AZIZA — Distributed Automotive ECU Simulation

```
  █████╗ ███████╗██╗███████╗ █████╗
 ██╔══██╗╚══███╔╝██║╚══███╔╝██╔══██╗
 ███████║  ███╔╝ ██║  ███╔╝ ███████║
 ██╔══██║ ███╔╝  ██║ ███╔╝  ██╔══██║
 ██║  ██║███████╗██║███████╗██║  ██║
 ╚═╝  ╚═╝╚══════╝╚═╝╚══════╝╚═╝  ╚═╝
```

> A complete, runnable distributed automotive ECU simulation with CAN bus, LIN bus, AI anomaly detection, a hard-constraint safety layer, and Blynk mobile telemetry — all in pure Python, no hardware required.

---

## Table of Contents

1. [Project Description](#project-description)
2. [Architecture](#architecture)
3. [CAN vs LIN](#can-vs-lin)
4. [Project Structure](#project-structure)
5. [How to Run](#how-to-run)
6. [Configuration](#configuration)
7. [Example Output](#example-output)
8. [Why AI is Used](#why-ai-is-used)
9. [Future Improvements](#future-improvements)

---

## Project Description

AZIZA simulates a modern automotive embedded system composed of multiple Electronic Control Units (ECUs) communicating over CAN and LIN buses. It models the full software stack of a vehicle's real-time control system:

- **Multiple ECUs** with deterministic, domain-specific logic
- **CAN bus** for high-priority, safety-critical communication
- **LIN bus** for low-cost, non-critical body functions
- **Safety Layer** that acts as the final authority — no other component can override it
- **AI Agent** that observes the system and advises the Safety Layer (never controls directly)
- **Blynk integration** for mobile monitoring and non-critical remote control

---

## Architecture

AZIZA uses a strict five-layer architecture. Data flows top-down; authority flows bottom-up through the Safety Layer.

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — ECUs  (deterministic logic only)                 │
│   SensorECU  │  EngineECU  │  BrakeECU  │  BodyECU         │
└──────────────────────┬──────────────────────────────────────┘
                       │  CAN Bus (priority queue)
                       │  LIN Bus (master-slave)
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 2 — Communication Bus                                │
│   CANBus (broadcast, priority)  │  LINBus (master-slave)    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 3 — Safety Layer  (FINAL AUTHORITY)                  │
│  Validates sensors · Enforces hard constraints              │
│  Validates AI suggestions · Arbitrates ECU conflicts        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 4 — AI Agent  (observer + advisor ONLY)              │
│  Rule-based anomaly detection · Risk scoring                │
│  Returns suggestions → Safety Layer validates them          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 5 — Telemetry  (Blynk)                               │
│  Streams data to mobile  │  Non-critical cruise toggle      │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Rules

| Rule | Description |
|------|-------------|
| **Safety Layer is sovereign** | It overrides all ECU outputs. No component bypasses it. |
| **AI is advisory only** | The AI agent can suggest actions but never command actuators. |
| **Blynk is non-critical only** | Blynk can toggle cruise control; it cannot touch brakes, throttle, or safety limits. |
| **ECUs are deterministic** | Each ECU runs pure logic with no I/O side effects — ideal for embedded targets. |

---

## CAN vs LIN

### CAN Bus (Controller Area Network)
- **Purpose**: Safety-critical, high-speed communication
- **Topology**: Broadcast — every node receives every message
- **Priority**: Lower message ID = higher arbitration priority (automotive standard)
- **Used by**: SensorECU, EngineECU, BrakeECU
- **Message IDs in AZIZA**:
  - `0x101` — engine temperature (highest priority after brakes)
  - `0x102` — vehicle speed
  - `0x201` — brake pressure

### LIN Bus (Local Interconnect Network)
- **Purpose**: Low-cost, non-critical body functions
- **Topology**: Master-slave — one master (BodyECU) controls multiple slaves
- **Mechanism**: Synchronous request/response — master polls each slave
- **Used by**: BodyECU (lighting, HVAC, door locks)
- **Why LIN here**: Body functions do not require CAN's speed or reliability; LIN reduces wiring cost and complexity.

| Feature | CAN | LIN |
|---------|-----|-----|
| Speed | Up to 1 Mbit/s | Up to 20 kbit/s |
| Topology | Multi-master broadcast | Single master |
| Cost | Higher | Lower |
| Use case | Safety-critical | Body/comfort |

---

## Project Structure

```
aziza/
├── config.py                   # Central configuration
├── main.py                     # Entry point + simulation loop
├── requirements.txt
├── README.md
│
├── bus/
│   ├── can_bus.py              # CAN bus (broadcast, priority queue)
│   └── lin_bus.py              # LIN bus (master-slave)
│
├── ecu/
│   ├── sensor_ecu.py           # Speed, temperature, brake simulation
│   ├── engine_ecu.py           # Cruise control + overheat protection
│   ├── brake_ecu.py            # Brake override (throttle = 0 when braking)
│   └── body_ecu.py             # LIN master: lighting, HVAC, doors
│
├── safety/
│   └── safety_layer.py         # Final authority — validates everything
│
├── ai/
│   └── anomaly_detector.py     # Rule-based risk scorer + advisor
│
└── telemetry/
    └── blynk_client.py         # Blynk cloud telemetry + cruise toggle
```

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> `blynklib` is the only external dependency. If you don't configure a Blynk token, AZIZA runs in offline mode automatically.

### 2. (Optional) Configure Blynk

Edit `config.py`:

```python
BLYNK_AUTH_TOKEN = "your_actual_blynk_token_here"
```

Set up your Blynk dashboard with these virtual pins:
| Pin | Data |
|-----|------|
| V0 | Speed (km/h) |
| V1 | Temperature (°C) |
| V2 | Brake pressure |
| V3 | Engine state |
| V4 | AI risk level |
| V5 | Cruise toggle (button) |

### 3. Run

```bash
cd aziza
python main.py
```

Press `Ctrl+C` to stop gracefully.

---

## Configuration

All parameters are in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SIMULATION_CYCLE_SECONDS` | `1.0` | Sleep between cycles |
| `ENGINE_TEMP_WARN` | `100` | °C — throttle reduction threshold |
| `ENGINE_TEMP_LIMIT` | `120` | °C — engine LIMITED threshold |
| `AI_TEMP_RISE_THRESHOLD` | `5` | °C/cycle — rapid rise trigger |
| `AI_HIGH_SPEED_THRESHOLD` | `100` | km/h — brake+speed risk threshold |

---

## Example Output

```
──────────────────────────────────────────────────────────────────────
  AZIZA CYCLE #0042
──────────────────────────────────────────────────────────────────────
[SENSOR] Speed=112.3 km/h  Temp=108.7 °C  Brake=0.65
[CAN]    TX  id=0x101  data={'temp': 108.7}
[CAN]    TX  id=0x102  data={'speed': 112.3}
[CAN]    TX  id=0x201  data={'brake': 0.65}
[ENGINE] Overheat WARNING (108.7°C) → reducing throttle
[ENGINE] State=REDUCED   Throttle=0.41  Cruise=ON
[BRAKE]  BRAKE ACTIVE (pressure=0.65) → throttle forced 0
[LIN]    MASTER→LIN_LIGHTING  REQ={'command': 'STATUS', 'speed': 112.3}
[LIN]    LIN_LIGHTING→MASTER  RSP={'lights_on': True}
[BODY]   Lights=ON  Doors=LOCKED  Fan=2
[SAFETY] [WARNING] BRAKE_OVERRIDE: Brake active → throttle forced to 0
[SAFETY] [WARNING] OVERHEAT_REDUCED: Temp=108.7°C → Throttle reduced
[AI]     Risk=SUSPICIOUS  Score=4  Anomalies=[BrakeAtHighSpeed: brake=0.65, speed=112.3 km/h, RapidTempRise: temp=108.7°C]  Suggestions=[disable_cruise]
[SAFETY] AI suggestion APPROVED: disable_cruise
[ENGINE] Cruise DISABLED
[BLYNK]  TX → V0=112.3  V1=108.7  V2=0.65  V3=REDUCED  V4=SUSPICIOUS

  ┌─ APPROVED STATE ──────────────────────────────────────────┐
  │ Speed:        112.3 km/h   │ Temp:      108.7 °C  │
  │ Throttle:       0.000      │ Brake:      YES        │
  │ Engine State: REDUCED      │ AI Risk:  SUSPICIOUS   │
  │ ⚠  [WARNING] BRAKE_OVERRIDE: Brake active → throttle 0   │
  └──────────────────────────────────────────────────────────────┘
```

---

## Why AI is Used

Modern vehicles generate continuous streams of sensor data that no human operator monitors in real time. The AI agent in AZIZA addresses three problems:

1. **Temporal anomaly detection**: A sudden temperature spike may not individually exceed any threshold but may indicate a failing cooling system when combined with the rate of increase over time. A simple threshold check misses this.

2. **Cross-signal correlation**: Brake pressure + high speed + throttle > 0 simultaneously is a contradiction that no single ECU detects alone — it requires a system-wide observer.

3. **Risk aggregation**: Multiple weak signals combine into a meaningful risk score. A single anomaly might not warrant action; three simultaneous anomalies almost certainly do.

The AI agent is deliberately **advisory only**. This is a core safety principle: AI introduces statistical uncertainty, while the Safety Layer enforces deterministic constraints. Mixing them would weaken safety guarantees. The AI informs the Safety Layer; the Safety Layer decides.

---

## Future Improvements

| Area | Improvement |
|------|-------------|
| **AI** | Replace rule-based scoring with a lightweight ML model (Isolation Forest, LSTM) trained on real CAN bus traces |
| **CAN** | Add message checksums and error frames to simulate bus faults |
| **ECUs** | Add ABS (Anti-lock Braking System) and ESC (Electronic Stability Control) ECUs |
| **Safety** | Add a watchdog timer to detect unresponsive ECUs |
| **Telemetry** | Add MQTT support as a Blynk alternative for industrial deployments |
| **Simulation** | Load real drive-cycle data (WLTP, EPA) for reproducible test scenarios |
| **Testing** | Add pytest unit tests for each ECU and the Safety Layer |
| **Visualization** | Add a local web dashboard (FastAPI + Chart.js) for offline monitoring |

---

*AZIZA — Built for correctness, safety, and clarity.*
