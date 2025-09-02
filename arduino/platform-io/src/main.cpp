#include <Servo.h>
#include <Arduino.h>
#include <trash_tray.h>
#include <bottle_input.h>

// Forward declaration so it can be used before its definition.
void handleSerialCommand(const String& cmd);
void sendCommandResponse(const String& cmd, const String& returnValue);
// Helpers
const char* stateToString(int s);
const char* trayStateToString(TrashTrayState s);
const char* trashTypeToString(TrashType t);
bool parseTrashType(const String& raw, TrashType &out);
void raiseError(const char* code);
const char* getLastError();
/**
 * This will control the whole trash can, by using the code from the trash_tray and bottle_input files.
 */

enum TrashCanState
{
  LOADING, // Starting up and initializing
  IDLE,
  CONTAINS_BOTTLE,
  WAITING_FOR_TRAY,
  TRAY_IN_POSITION,
  MOVING_BOTTLE_TO_TRAY,
  BOTTLE_IN_TRAY,
  MOVING_TO_IDLE,
  // ERROR STATES
  EMO_MOOD,

};

TrashCanState currentTrashState = LOADING;


const int TRAY_LIMIT_SWITCH_PIN = 12;

// Timing & Timeouts
static unsigned long g_stateStartMs = 0;
static const unsigned long TRAY_MOVE_TIMEOUT_MS = 15000;   // 15s Timeout fürs Tray
static const unsigned long BOTTLE_MOVE_TIMEOUT_MS = 8000;   // 8s Timeout fürs Rohr
static const unsigned long DROP_DWELL_MS = 1000;            // 1s Wartezeit über Loch

// Now that TrashCanState is defined, declare setState
void setState(TrashCanState s);

void setup()
{
  Serial.begin(9600);
  pinMode(TRAY_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  initTrashTray();
  initBottleMechanism();
  // Initial State Event
  Serial.println(String("event::state::") + stateToString(currentTrashState));
}



void loop()
{
 


  switch (currentTrashState)
  {
  case LOADING:
    // Handle loading state
    if (calibrateTrashTray()) {
      setState(IDLE);
    }
    break;

  case IDLE:

    // Just Chill.


    // Serielle Eingabe prüfen
    if (Serial.available()) {
      String input = Serial.readStringUntil('\n');
      input.trim();
      if (input.length() > 0) {
        handleSerialCommand(input);
      }
    }

    // Tray-Limit-Switch prüfen
    if (digitalRead(TRAY_LIMIT_SWITCH_PIN) == LOW) {
      // Tray ist am Limit, ggf. Status setzen
      // Hier könnte man z.B. einen Kalibrierstatus setzen oder Stepper stoppen
      // Aktuell: nur Info
      Serial.println("Tray-Limit erreicht!");
    }
    break;

  // NEXT STATES WILL NEVER OCCURE OUT OF ORDER.
  case CONTAINS_BOTTLE:

    // This state does nothing, but is important since it makes sure that all follwing states are only switch in the loop function, to avoid that drunken idiots manually interfear with the automated process.
    // So just chill and wait for the next state.
    // AND NEVER EVER PUT ME IN ANY BELOW STATES FROM OUTSIDE THIS FUNCTION.
    // ALSO THE TRAY SHOULD

    // OH One thing it does is doing some boring things to make sure every component is in working state and its safe to continue.

    if (isTrayLoaded() && getBottleState() == INIT_STATE && getTrashTrayState() == READY)
    {
  setState(WAITING_FOR_TRAY);
    }
    else
    {
  raiseError("PRECONDITIONS_FAIL");
      break;
    }

    break;
  case WAITING_FOR_TRAY:
    // Tray-Limit-Switch prüfen
    if (digitalRead(TRAY_LIMIT_SWITCH_PIN) == LOW) {
      // Tray ist am Limit, ggf. Status setzen
      Serial.println("Tray-Limit erreicht! (WAITING_FOR_TRAY)");
      // Hier könnte man Stepper stoppen oder Tray neu kalibrieren
    }
    // Tray zur Zielposition bewegen
    if (moveToTargetPosition()) {
      setState(TRAY_IN_POSITION);
    }
    // Timeout prüfen
    if (millis() - g_stateStartMs > TRAY_MOVE_TIMEOUT_MS) {
      raiseError("TRAY_TIMEOUT");
    }
    break;
  case TRAY_IN_POSITION:
    // Handle tray in position state

    // Double check if the tray is indeed in position
    if (getTrashTrayState() == READY)
    {
      setState(MOVING_BOTTLE_TO_TRAY);
    }
    else
    {
      raiseError("TRAY_NOT_READY");
    }
    break;
  case MOVING_BOTTLE_TO_TRAY:
    // Non-blocking Bewegung der Flasche zum Ziel-Loch
    if (getBottleState() == INIT_STATE) {
      // Start nur einmal anstoßen
      int targetAngle = (getCurrentTrashType() == GLAS) ? 180 : 0;
      moveBottleToAngleNonBlockingStart(targetAngle, DROP_STATE);
    }
    if (moveBottleToNonBlockingTick()) {
      setState(BOTTLE_IN_TRAY);
    } else if (millis() - g_stateStartMs > BOTTLE_MOVE_TIMEOUT_MS) {
      raiseError("BOTTLE_TIMEOUT");
    }
    break;
  case BOTTLE_IN_TRAY:
    // Wartezeit, damit die Flasche sicher fallen kann
    if (millis() - g_stateStartMs >= DROP_DWELL_MS) {
      setState(MOVING_TO_IDLE);
    }
    break;
  case MOVING_TO_IDLE:
    // Non-blocking zurück zur Home-Position (90°)
    if (getBottleState() != INIT_STATE) {
      moveBottleToAngleNonBlockingStart(90, INIT_STATE);
    }
    if (moveBottleToNonBlockingTick()) {
      setState(IDLE);
    } else if (millis() - g_stateStartMs > BOTTLE_MOVE_TIMEOUT_MS) {
      raiseError("BOTTLE_HOME_TIMEOUT");
    }
    
  break;
  case EMO_MOOD:

  // TODO: Implement error handling and recovery
    // Handle emo mood state -> our error state
    break;
  }
}

void recvBottleIn(TrashType type)
{
  // Handle the event when a bottle is detected
  Serial.print(">bottle");
  Serial.println(type);

  selectTrashType(type);
  setState(CONTAINS_BOTTLE);
}


void estop()
{

  // TODO: Implement emergency stop functionality
  // This should immediately stop all movements and electroshok the idiot who pressed the emergency stop button
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
    recvBottleIn(t);
    sendCommandResponse("mTray", "OK");
  }
  else if (func == "start") {
    // Startet den kompletten Ablauf für einen Type (Tray bewegen, Flasche bewegen, zurück nach Idle)
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
    if (val.toInt() == 1) {
      moveDrop();
    } else if (val.toInt() == 2) {
      moveInit();
    }
    BottleState pos = getBottleState();
    sendCommandResponse("mPosBottle", String(pos));
  }
  else if (func == "gLimitTray") {
    // Gibt den Status des Limit-Switches zurück
    int limit = digitalRead(TRAY_LIMIT_SWITCH_PIN);
    sendCommandResponse("gLimitTray", String(limit == LOW ? "PRESSED" : "RELEASED"));
  }
  else if (func == "gState") {
    sendCommandResponse("gState", stateToString(currentTrashState));
  }
  else if (func == "gType") {
    sendCommandResponse("gType", trashTypeToString(getCurrentTrashType()));
  }
  else if (func == "estop") {
    estop();
    sendCommandResponse("estop", "OK");
  }
  else if (func == "ping") {
    sendCommandResponse("ping", "pong");
  }
  else if (func == "recover") {
    // Recovery: Stoppen, neu kalibrieren, Rohr in Home und IDLE setzen
    trayStopImmediate();
    if (!calibrateTrashTray()) { sendCommandResponse("recover", "ERR_CAL"); return; }
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
  else if (func == "gBottleAngle") {
    // Gibt den aktuellen Servo-Winkel (0-180) zurück
    sendCommandResponse("gBottleAngle", String(getBottleAngle()));
  }
  else if (func == "mBottleAngle") {
    // Setzt den Servo manuell auf einen Winkel: mBottleAngle::<deg>
    int deg = val.toInt();
    if (deg < 0 || deg > 180) {
      sendCommandResponse("mBottleAngle", "ERR_RANGE");
      return;
    }
    moveBottleToAngleBlocking(deg, UNKNOWN_STATE);
    sendCommandResponse("mBottleAngle", String(getBottleAngle()));
  }
  else if (func == "setTrayPos") {
    // Format: setTrayPos::<type>=<steps>
    int eq = val.indexOf('=');
    if (eq < 1) { sendCommandResponse("setTrayPos", "ERR_BAD_ARG"); return; }
    String tStr = val.substring(0, eq);
    String pStr = val.substring(eq+1);
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
  // Weitere Funktionen können hier ergänzt werden
}

void sendCommandResponse(const String& cmd, const String& returnValue)
{
  // TODO: Implement command response sending in form of command::ack::return_value
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
      case GLAS: return "GLAS"; // Note: deutsch
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
    // Unterstützt Zahlen (0/1/2) und Strings (plastic, glas/glass, can)
    if (raw.length() == 1 && isDigit(raw[0])) {
      int v = raw.toInt();
      if (v == 0) { out = PLASTIC; return true; }
      if (v == 1) { out = GLAS; return true; }
      if (v == 2) { out = CAN; return true; }
      return false;
    }
    String s = raw; s.toLowerCase();
    if (s == "plastic" || s == "plastik") { out = PLASTIC; return true; }
    if (s == "glass" || s == "glas") { out = GLAS; return true; }
    if (s == "can" || s == "dose") { out = CAN; return true; }
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

// TODO: Implement error handling and recovery
// TODO: Communicate with Raspberry Pi and interrupt when it detects an error
// TODO: add timeouts for moving function. this needed since too long delays maybe related to issues eg obstacles


