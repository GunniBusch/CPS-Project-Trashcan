// CPS Trashcan main controller
// Orchestrates: state machine, serial protocol, tray (stepper), bottle (servo)

#include <Arduino.h>
#include <trash_tray.h>
#include <bottle_input.h>

// High-level states for the overall system
enum TrashCanState {
  LOADING,            // Startup and tray calibration
  IDLE,
  CONTAINS_BOTTLE,
  WAITING_FOR_TRAY,
  TRAY_IN_POSITION,
  MOVING_BOTTLE_TO_TRAY,
  BOTTLE_IN_TRAY,
  MOVING_TO_IDLE,
  // Error
  EMO_MOOD,
};

// Forward declarations used before their definitions
void handleSerialCommand(const String& cmd);
void sendCommandResponse(const String& cmd, const String& returnValue);
const char* stateToString(int s);
const char* trayStateToString(TrashTrayState s);
const char* trashTypeToString(TrashType t);
bool parseTrashType(const String& raw, TrashType &out);
void raiseError(const char* code);
const char* getLastError();
void setState(enum TrashCanState s);
void recvBottleIn(TrashType type);
void estop();


static TrashCanState currentTrashState = LOADING;

// Digital input for tray limit switch (active LOW)
const int TRAY_LIMIT_SWITCH_PIN = 12;
// Tray enable/disable (when disabled, the cycle runs without moving the tray)
static bool g_trayEnabled = false;

// Timers & timeouts
static unsigned long g_stateStartMs = 0;
static const unsigned long TRAY_MOVE_TIMEOUT_MS = 15000;   // 15s timeout for tray moves
static const unsigned long BOTTLE_MOVE_TIMEOUT_MS = 8000;  // 8s timeout for bottle moves
static const unsigned long DROP_DWELL_MS = 1000;           // 1s dwell over the hole

void setup() {
  Serial.begin(9600);
  pinMode(TRAY_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  initTrashTray();
  initBottleMechanism();
  // Emit initial state event
  Serial.println(String("event::state::") + stateToString(currentTrashState));
}

void loop() {
  switch (currentTrashState) {
    case LOADING: {
      // Startup: calibrate tray unless tray is disabled
      if (!g_trayEnabled) {
        setState(IDLE);
      } else if (calibrateTrashTray()) {
        setState(IDLE);
      }
      break;
    }

    case IDLE: {
      // Idle: wait for commands
      // Read serial input (line-based: name::value)
      if (Serial.available()) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        if (input.length() > 0) {
          handleSerialCommand(input);
        }
      }
      // Optional: log tray limit switch press
      if (digitalRead(TRAY_LIMIT_SWITCH_PIN) == LOW) {
        Serial.println("Tray limit reached!");
      }
      break;
    }

    case CONTAINS_BOTTLE: {
      // Preconditions gate: make sure components are ready/safe before proceeding

  // Tray disabled? → ensure bottle is at home (HOME_ANGLE), then continue
      if (!g_trayEnabled) {
        if (getBottleState() != INIT_STATE) {
          if (getBottleState() != MOVING_STATE) {
    moveBottleToAngleNonBlockingStart(HOME_ANGLE, INIT_STATE);
          }
          if (!moveBottleToNonBlockingTick()) {
            break; // still moving
          }
        }
        setState(TRAY_IN_POSITION);
        break;
      }

      // Auto-heal preconditions: tray READY, bottle INIT
      // 1) Tray READY? If not, try calibration
      if (getTrashTrayState() != READY) {
        if (!calibrateTrashTray()) {
          raiseError("PRECONDITIONS_FAIL");
          break;
        }
      }
    // 2) Bottle INIT? If not, drive to home (HOME_ANGLE) non-blocking and tick
      if (getBottleState() != INIT_STATE) {
        if (getBottleState() != MOVING_STATE) {
      moveBottleToAngleNonBlockingStart(HOME_ANGLE, INIT_STATE);
        }
        if (!moveBottleToNonBlockingTick()) {
          break; // still moving
        }
      }
      // 3) Optional load presence check (placeholder), currently always true
      if (!isTrayLoaded()) {
        raiseError("PRECONDITIONS_FAIL");
        break;
      }
      // All preconditions met → continue
      setState(WAITING_FOR_TRAY);
      break;
    }

    case WAITING_FOR_TRAY: {
      if (!g_trayEnabled) {
        setState(TRAY_IN_POSITION);
        break;
      }
      // Check tray limit switch (home)
      if (digitalRead(TRAY_LIMIT_SWITCH_PIN) == LOW) {
        Serial.println("Tray limit reached! (WAITING_FOR_TRAY)");
      }
      // Move tray to target position
      if (moveToTargetPosition()) {
        setState(TRAY_IN_POSITION);
      }
      // Timeout check
      if (millis() - g_stateStartMs > TRAY_MOVE_TIMEOUT_MS) {
        raiseError("TRAY_TIMEOUT");
      }
      break;
    }

    case TRAY_IN_POSITION: {
      // Double-check tray readiness (or skip when tray is disabled)
      if (!g_trayEnabled || getTrashTrayState() == READY) {
        setState(MOVING_BOTTLE_TO_TRAY);
      } else {
        raiseError("TRAY_NOT_READY");
      }
      break;
    }

    case MOVING_BOTTLE_TO_TRAY: {
      // Non-blocking bottle move to the target hole using bottle_input API
      if (getBottleState() == INIT_STATE) {
        // Kick off movement once (done state set internally)
        startDropMoveForCurrentType();
      }
      if (moveBottleToNonBlockingTick()) {
        setState(BOTTLE_IN_TRAY);
      } else if (millis() - g_stateStartMs > BOTTLE_MOVE_TIMEOUT_MS) {
        raiseError("BOTTLE_TIMEOUT");
      }
      break;
    }

    case BOTTLE_IN_TRAY: {
      // Dwell to let the object fall safely
      if (millis() - g_stateStartMs >= DROP_DWELL_MS) {
        setState(MOVING_TO_IDLE);
      }
      break;
    }

    case MOVING_TO_IDLE: {
      // Non-blocking move back to home (HOME_ANGLE)
      if (getBottleState() != INIT_STATE) {
        moveBottleToAngleNonBlockingStart(HOME_ANGLE, INIT_STATE);
      }
      if (moveBottleToNonBlockingTick()) {
        setState(IDLE);
      } else if (millis() - g_stateStartMs > BOTTLE_MOVE_TIMEOUT_MS) {
        raiseError("BOTTLE_HOME_TIMEOUT");
      }
      break;
    }

    case EMO_MOOD: {
      // Error state; waiting for recover or reset
      break;
    }
  }
}

void recvBottleIn(TrashType type) {
  // Handle the event when a bottle is detected (or a start command)
  Serial.print(">bottle");
  Serial.println(type);
  // Always record the target type using the provided API
  selectTrashType(type);
  setState(CONTAINS_BOTTLE);
}

void estop() {
  // Emergency stop: stop tray and enter error state
  trayStopImmediate();
  raiseError("ESTOP");
}

void handleSerialCommand(const String& cmd) {
  int sep = cmd.indexOf("::");
  if (sep == -1) return;
  String func = cmd.substring(0, sep);
  String val = cmd.substring(sep + 2);

  if (func == "mTray") {
    TrashType t;
    if (!parseTrashType(val, t)) { sendCommandResponse("mTray", "ERR_BAD_TYPE"); return; }
    if (currentTrashState != IDLE) { sendCommandResponse("mTray", "ERR_BUSY"); return; }
    recvBottleIn(t);
    sendCommandResponse("mTray", "OK");
  }
  else if (func == "start") {
    // Start complete cycle for a type (tray move, bottle move, return to idle)
    TrashType t;
    if (!parseTrashType(val, t)) { sendCommandResponse("start", "ERR_BAD_TYPE"); return; }
    if (currentTrashState != IDLE) { sendCommandResponse("start", "ERR_BUSY"); return; }
    recvBottleIn(t);
    sendCommandResponse("start", "OK");
  }
  else if (func == "gPosBottle") {
    BottleState pos = getBottleState();
    sendCommandResponse("gPosBottle", String(pos));
  }
  else if (func == "mPosBottle") {
    int m = val.toInt();
    if (m == 1) moveDrop();
    else if (m == 2) moveInit();
    BottleState pos = getBottleState();
    sendCommandResponse("mPosBottle", String(pos));
  }
  else if (func == "gLimitTray") {
    // Return limit switch status
    int limit = digitalRead(TRAY_LIMIT_SWITCH_PIN);
    sendCommandResponse("gLimitTray", String(limit == LOW ? "PRESSED" : "RELEASED"));
  }
  else if (func == "gState") {
    sendCommandResponse("gState", stateToString(currentTrashState));
  }
  else if (func == "gType") {
    sendCommandResponse("gType", trashTypeToString(getCurrentTrashType()));
  }
  else if (func == "gTrayEnabled") {
    sendCommandResponse("gTrayEnabled", String(g_trayEnabled ? 1 : 0));
  }
  else if (func == "setTrayEnabled") {
    String s = val; s.toLowerCase();
    bool newVal;
    if (s == "1" || s == "on" || s == "true") newVal = true;
    else if (s == "0" || s == "off" || s == "false") newVal = false;
    else { sendCommandResponse("setTrayEnabled", "ERR_BAD_ARG"); return; }
    g_trayEnabled = newVal;
    sendCommandResponse("setTrayEnabled", "OK");
  }
  else if (func == "estop") {
    estop();
    sendCommandResponse("estop", "OK");
  }
  else if (func == "ping") {
    sendCommandResponse("ping", "pong");
  }
  else if (func == "recover") {
    // Recovery: stop tray, recalibrate (if tray enabled), bottle to home, go to IDLE
    trayStopImmediate();
    if (g_trayEnabled && !calibrateTrashTray()) { sendCommandResponse("recover", "ERR_CAL"); return; }
    moveInit();
    setState(IDLE);
    sendCommandResponse("recover", "OK");
  }
  else if (func == "gLastError") {
    sendCommandResponse("gLastError", getLastError());
  }
  else if (func == "gDiagTray") {
    String diag = String("pos=") + getTrayCurrentPosition() +
                  ",target=" + getTrayTargetPosition() +
                  ",dtg=" + getTrayDistanceToGo() +
                  ",speed=" + getTraySpeed() +
                  ",state=" + trayStateToString(getTrashTrayState());
    sendCommandResponse("gDiagTray", diag);
  }
  else if (func == "gDiagBottle") {
    String diag = String("state=") + getBottleState();
    sendCommandResponse("gDiagBottle", diag);
  }
  else if (func == "gHoleMap") {
    // gHoleMap::<type>
    TrashType t;
    if (!parseTrashType(val, t)) { sendCommandResponse("gHoleMap", "ERR_BAD_TYPE"); return; }
    Hole h = getHoleForType(t);
    String out = (h == HOLE2) ? "HOLE2" : "HOLE1";
    out += ",angle=";
    out += String(getAngleForType(t));
    sendCommandResponse("gHoleMap", out);
  }
  else if (func == "gBottleAngle") {
    // Return current servo angle (0-180)
    sendCommandResponse("gBottleAngle", String(getBottleAngle()));
  }
  else if (func == "mBottleAngle") {
    // Manually set servo angle: mBottleAngle::<deg>
    int deg = val.toInt();
    if (deg < 0 || deg > 180) { sendCommandResponse("mBottleAngle", "ERR_RANGE"); return; }
    moveBottleToAngleBlocking(deg, UNKNOWN_STATE);
    sendCommandResponse("mBottleAngle", String(getBottleAngle()));
  }
  else if (func == "setTrayPos") {
    // Format: setTrayPos::<type>=<steps>
    int eq = val.indexOf('=');
    if (eq < 1) { sendCommandResponse("setTrayPos", "ERR_BAD_ARG"); return; }
    String tStr = val.substring(0, eq);
    String pStr = val.substring(eq + 1);
    TrashType t;
    if (!parseTrashType(tStr, t)) { sendCommandResponse("setTrayPos", "ERR_BAD_TYPE"); return; }
    int steps = pStr.toInt();
    if (!setTrayPositionForType(t, steps)) { sendCommandResponse("setTrayPos", "ERR_FAIL"); return; }
    sendCommandResponse("setTrayPos", "OK");
  }
  else if (func == "setBottleSpeed") {
    // setBottleSpeed::<ms>
    int ms = val.toInt();
    setBottleSpeedDelay(ms);
    sendCommandResponse("setBottleSpeed", "OK");
  }

}

void sendCommandResponse(const String& cmd, const String& returnValue) {
  String response = cmd + "::ack::" + returnValue;
  Serial.println(response);
}

// --- Helpers ---
const char* stateToString(int s) {
  switch ((TrashCanState)s) {
    case LOADING: return "LOADING";
    case IDLE: return "IDLE";
    case CONTAINS_BOTTLE: return "CONTAINS_BOTTLE";
    case WAITING_FOR_TRAY: return "WAITING_FOR_TRAY";
    case TRAY_IN_POSITION: return "TRAY_IN_POSITION";
    case MOVING_BOTTLE_TO_TRAY: return "MOVING_BOTTLE_TO_TRAY";
    case BOTTLE_IN_TRAY: return "BOTTLE_IN_TRAY";
    case MOVING_TO_IDLE: return "MOVING_TO_IDLE";
    case EMO_MOOD: return "EMO_MOOD";
  }
  return "UNKNOWN";
}

const char* trashTypeToString(TrashType t) {
  switch (t) {
    case PLASTIC: return "PLASTIC";
    case GLAS: return "GLAS"; // German spelling retained to match prior logic
    case CAN: return "CAN";
  }
  return "UNKNOWN";
}

const char* trayStateToString(TrashTrayState s) {
  switch (s) {
    case READY: return "READY";
    case CALIBRATING: return "CALIBRATING";
    case MOVING: return "MOVING";
    case UNAVAILABLE: return "UNAVAILABLE";
    case ESTOP_STATE: return "ESTOP_STATE";
  }
  return "UNKNOWN";
}

bool parseTrashType(const String& raw, TrashType &out) {
  // Supports numbers (0/1/2) and strings (plastic, glas/glass, can)
  if (raw.length() == 1 && isDigit(raw[0])) {
    int v = raw.toInt();
    if (v == 0) { out = (TrashType)PLASTIC; return true; }
    if (v == 1) { out = (TrashType)GLAS; return true; }
    if (v == 2) { out = (TrashType)CAN; return true; }
    return false;
  }
  String s = raw; s.toLowerCase();
  if (s == "plastic" || s == "plastik") { out = (TrashType)PLASTIC; return true; }
  if (s == "glass" || s == "glas") { out = (TrashType)GLAS; return true; }
  if (s == "can" || s == "dose") { out = (TrashType)CAN; return true; }
  return false;
}

void setState(TrashCanState s) {
  if (currentTrashState == s) return;
  currentTrashState = s;
  g_stateStartMs = millis();
  Serial.println(String("event::state::") + stateToString(currentTrashState));
}

// Error reason support
static const char* g_lastError = "NONE";
void raiseError(const char* code) {
  g_lastError = code;
  Serial.println(String("event::error::") + code);
  setState(EMO_MOOD);
}
const char* getLastError() { return g_lastError; }


