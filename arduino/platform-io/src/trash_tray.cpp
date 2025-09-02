#include <Arduino.h>
#include <AccelStepper.h>
#include <trash_tray.h>

/**
 * This file controls the trash tray mechanism. 
 */

#define dirPin 4
#define stepPin 5
AccelStepper stepper(AccelStepper::DRIVER, stepPin, dirPin);


// Limit-Switch für Home-Position (aktiv LOW)
static const int TRAY_LIMIT_SWITCH_PIN = 12;

TrashTrayState CURRENT_TRAY_STATE = UNAVAILABLE;


TrashType targetTrashType=GLAS;

// Konfigurierbare Zielpositionen (Steps)
static int glassPosition = 10000;
static int plasticPosition = 11000;
static int canPosition = 1200;




void initTrashTray() {
  pinMode(TRAY_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  stepper.setMaxSpeed(3000);
  stepper.setAcceleration(100);

  // Startzustand
  CURRENT_TRAY_STATE = UNAVAILABLE;
}

bool isCalibrated() {
  // Check if the trash tray is calibrated
  return stepper.currentPosition() == 0;
}



bool selectTrashType(TrashType type) {
    targetTrashType = type;
     switch (targetTrashType) {
    case PLASTIC:
      stepper.moveTo(plasticPosition);
      break;
    case GLAS:
      stepper.moveTo(glassPosition);
      break;
    case CAN:
      stepper.moveTo(canPosition);
      break;
  }
    return true;
}
TrashType getCurrentTrashType(){
    // TODO Finish
  return targetTrashType;
}
TrashTrayState getTrashTrayState(){
  return CURRENT_TRAY_STATE;
}

// This is running the stepper
bool moveToTargetPosition() {
  // Move the stepper to the target position
  // Sicherheit: Wenn Endschalter gedrückt ist und wir in Richtung Home fahren, stoppe und setze Position auf 0.
  if (digitalRead(TRAY_LIMIT_SWITCH_PIN) == LOW && stepper.speed() < 0) {
    stepper.stop();
    stepper.setCurrentPosition(0);
    stepper.moveTo(0);
    CURRENT_TRAY_STATE = READY;
    return true;
  }

  // Prüfe, ob Ziel erreicht ist
  if (stepper.distanceToGo() == 0) {
    CURRENT_TRAY_STATE = READY;
    return true;
  }

  // Einen Schritt vorwärts bringen
  stepper.run();
  CURRENT_TRAY_STATE = MOVING;
  return false;

}

bool isTrayLoaded() {

    // Todo implement
    return true;
}

bool calibrateTrashTray() {
  // Calibrate the trash tray by moving it until limit switch is triggered
  CURRENT_TRAY_STATE = CALIBRATING;

  // Stelle moderate Geschwindigkeit ein für sichere Kalibrierung
  stepper.setMaxSpeed(800);
  stepper.setAcceleration(400);
  stepper.setSpeed(-300); // Richtung Endschalter (Home)

  // Fahre, bis der Endschalter auslöst (aktiv LOW)
  unsigned long start = millis();
  const unsigned long timeoutMs = 10000; // 10s Timeout
  while (digitalRead(TRAY_LIMIT_SWITCH_PIN) == HIGH) {
    stepper.runSpeed();
    if (millis() - start > timeoutMs) {
      // Kalibrierung fehlgeschlagen
      CURRENT_TRAY_STATE = UNAVAILABLE;
      return false;
    }
  }

  delay(20);
  // Setze aktuelle Position als 0 (Home)
  stepper.setCurrentPosition(0);
  // Nach Kalibrierung Standard-Geschwindigkeiten wiederherstellen
  stepper.setMaxSpeed(3000);
  stepper.setAcceleration(100);
  // Leichter Off-Home-Move, um vom Schalter zu entlasten (optional)
  stepper.moveTo(50);
  while (stepper.distanceToGo() != 0) {
    stepper.run();
  }
  CURRENT_TRAY_STATE = READY;
  return true;
}

// --- Utility API ---
void trayStopImmediate() {
  stepper.stop();
  CURRENT_TRAY_STATE = ESTOP_STATE;
}

bool setTrayPositionForType(TrashType type, int steps) {
  switch (type) {
    case PLASTIC: plasticPosition = steps; return true;
    case GLAS: glassPosition = steps; return true;
    case CAN: canPosition = steps; return true;
  }
  return false;
}

int getTrayPositionForType(TrashType type) {
  switch (type) {
    case PLASTIC: return plasticPosition;
    case GLAS: return glassPosition;
    case CAN: return canPosition;
  }
  return 0;
}

long getTrayCurrentPosition() {
  return stepper.currentPosition();
}

long getTrayTargetPosition() {
  return stepper.targetPosition();
}

long getTrayDistanceToGo() {
  return stepper.distanceToGo();
}

float getTraySpeed() {
  return stepper.speed();
}
