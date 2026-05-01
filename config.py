# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# config.py — Central configuration for the AZIZA system
# ============================================================

PROJECT_NAME = "AZIZA"

# --- Blynk ---
BLYNK_AUTH_TOKEN = "YOUR_BLYNK_TOKEN_HERE"  # Replace with your Blynk token
BLYNK_SERVER = "blynk.cloud"
BLYNK_PORT = 80

# --- Simulation ---
SIMULATION_CYCLE_SECONDS = 1
SIMULATION_DURATION = None        # None = run forever

# --- CAN Message IDs (existing) ---
CAN_ID_TEMPERATURE = 0x101
CAN_ID_SPEED       = 0x102
CAN_ID_BRAKE       = 0x201

# --- Car Control CAN IDs (commands IN) ---
CAN_ID_WINDOW_CMD       = 0x300
CAN_ID_LIGHT_CMD        = 0x310
CAN_ID_DOOR_LOCK_CMD    = 0x320
CAN_ID_GEARBOX_CMD      = 0x330

# --- Car Control CAN IDs (status OUT) ---
CAN_ID_WINDOW_STATUS    = 0x301
CAN_ID_LIGHT_STATUS     = 0x311
CAN_ID_DOOR_LOCK_STATUS = 0x321
CAN_ID_GEARBOX_STATUS   = 0x331

# --- LIN Bus ---
LIN_MASTER_ID = "BODY_MASTER"

# --- LIN Slave Node IDs ---
LIN_SLAVE_WINDOWS   = "LIN_WINDOWS"
LIN_SLAVE_LIGHTS    = "LIN_LIGHTS"
LIN_SLAVE_DOOR_LOCK = "LIN_DOOR_LOCK"
LIN_SLAVE_GEARBOX   = "LIN_GEARBOX"

# --- Window Constants ---
WIN_FL, WIN_FR, WIN_RL, WIN_RR = 0, 1, 2, 3
WIN_STOP, WIN_UP, WIN_DOWN     = 0, 1, 2

# --- Light Mask Bits ---
LIGHT_HEAD     = 0b0001
LIGHT_INTERIOR = 0b0010
LIGHT_HAZARD   = 0b0100
LIGHT_FOG      = 0b1000

# --- Light States ---
LIGHT_OFF, LIGHT_ON, LIGHT_DIM = 0, 1, 2

# --- Door Mask Bits ---
DOOR_FL  = 0b0001
DOOR_FR  = 0b0010
DOOR_RL  = 0b0100
DOOR_RR  = 0b1000
DOOR_ALL = 0b1111

# --- Door Lock Commands ---
DOOR_UNLOCK, DOOR_LOCK = 0, 1

# --- Gearbox Modes ---
GEAR_PARK    = "P"
GEAR_REVERSE = "R"
GEAR_NEUTRAL = "N"
GEAR_DRIVE   = "D"
GEAR_SEQUENCE = (GEAR_PARK, GEAR_REVERSE, GEAR_NEUTRAL, GEAR_DRIVE)

# --- Sensor Ranges ---
SENSOR_SPEED_MIN        = 0
SENSOR_SPEED_MAX        = 150
SENSOR_TEMP_MIN         = 70
SENSOR_TEMP_MAX         = 130
SENSOR_BRAKE_MIN        = 0.0
SENSOR_BRAKE_MAX        = 1.0

# --- Engine Thresholds ---
ENGINE_TEMP_WARN        = 100
ENGINE_TEMP_LIMIT       = 120

# --- Safety Thresholds ---
SAFETY_MAX_SPEED        = 150
SAFETY_MAX_TEMP         = 125
SAFETY_MIN_BRAKE        = 0.0

# --- AI Risk Scoring ---
AI_TEMP_RISE_THRESHOLD  = 5
AI_HIGH_SPEED_THRESHOLD = 100
AI_RISK_CRITICAL        = 5
AI_RISK_SUSPICIOUS      = 2

# --- Blynk Virtual Pins ---
VPIN_SPEED         = "V0"
VPIN_TEMPERATURE   = "V1"
VPIN_BRAKE         = "V2"
VPIN_ENGINE_STATE  = "V3"
VPIN_AI_RISK       = "V4"
VPIN_CRUISE_TOGGLE = "V5"

# --- Logging ---
LOG_PREFIX = {
    "CAN":     "[CAN]   ",
    "LIN":     "[LIN]   ",
    "ENGINE":  "[ENGINE]",
    "BRAKE":   "[BRAKE] ",
    "SENSOR":  "[SENSOR]",
    "BODY":    "[BODY]  ",
    "CARCTRL": "[CARCTL]",
    "SAFETY":  "[SAFETY]",
    "AI":      "[AI]    ",
    "BLYNK":   "[BLYNK] ",
    "AZIZA":   "[AZIZA] ",
}
