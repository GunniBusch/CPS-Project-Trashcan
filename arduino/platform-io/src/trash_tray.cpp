#include <Arduino.h>
#include <AccelStepper.h>
#include <trash_tray.h>

/**
 * This file controls the trash tray mechanism. 
 */

#define dirPin 4
#define stepPin 5
AccelStepper stepper(AccelStepper::DRIVER, stepPin, dirPin);


TrashTrayState CURRENT_TRAY_STATE = UNAVAILABLE;


TrashType targetTrashType=GLAS;

// Todo real
int glassPosition = 10000;
int plasticPosition = 11000;
int canPosition = 1200;




void initTrashTray() {
  stepper.setMaxSpeed(3000);
  stepper.setAcceleration(100);

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
  return !stepper.run();

}

bool isTrayLoaded() {

    // Todo implement
    return true;
}

bool calibrateTrashTray() {
  // Calibrate the trash tray by moving it until limit switch is triggered
  CURRENT_TRAY_STATE = CALIBRATING;
  CURRENT_TRAY_STATE = READY;
  stepper.moveTo(1000);
  stepper.run();
  CURRENT_TRAY_STATE = READY;
  return 1;
}
