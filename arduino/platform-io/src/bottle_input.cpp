/**
 * This file handles the bottle moving mechanism.
 * It controlles the tube that moves the bottle over the trash tray.
 * 
 * 
 * 
 */


#include <Servo.h>
#include <Arduino.h>
#include <bottle_input.h>
#include <trash_tray.h> // Für getCurrentTrashType / TrashType



Servo servo;

#define MIN_ANGLE 0
#define MAX_ANGLE 280
#define MID_POINT 90

// Winkel-Mapping:
// PLASTIC & CAN -> Loch 1 bei 0°
// GLAS          -> Loch 2 bei 180°
// Normal        -> 90°
static const int HOLE1_ANGLE = 0;    // Plastic/Can
static const int HOLE2_ANGLE = 180;  // Glass
static const int HOME_ANGLE  = 90;   // Normal


BottleState CURRENT_BOTTLE_STATE = UNKNOWN_STATE;

// Non-Blocking internals
static int g_targetAngle = HOME_ANGLE;
static BottleState g_doneState = INIT_STATE;
static int g_speedDelayMs = 15; // default speed





void initBottleMechanism() {
  // Achtung: attach(pin, min, max) erwartet Pulsbreiten in µs, nicht Winkel!
  // Deshalb hier nur attach(pin) verwenden, damit die Standard-Pulsbreiten gelten.
  servo.attach(A1);              // Servo an A1
  resetBottleState();
  CURRENT_BOTTLE_STATE = INIT_STATE;

}



void resetBottleState() {
  moveInit();

}

BottleState getBottleState() {
  return CURRENT_BOTTLE_STATE;
}

int getBottleAngle() {
  return servo.read();
}

// TODO Maybe make a non blocking move function like the one for the tray

void moveDrop() {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  int target = HOME_ANGLE;
  TrashType t = getCurrentTrashType();
  target = (t == GLAS) ? HOLE2_ANGLE : HOLE1_ANGLE;
  moveBottleToAngleNonBlockingStart(target, DROP_STATE);
  // Blocking drive using the non-blocking tick
  while (!moveBottleToNonBlockingTick()) {
    // yield
  }
}

void moveInit() {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  moveBottleToAngleNonBlockingStart(HOME_ANGLE, INIT_STATE);
  while (!moveBottleToNonBlockingTick()) {
    // yield
  }
}

void setBottleSpeedDelay(int ms) {
  if (ms < 1) ms = 1;
  g_speedDelayMs = ms;
}

void moveBottleToAngleNonBlockingStart(int targetAngle, BottleState doneState) {
  g_targetAngle = constrain(targetAngle, MIN_ANGLE, MAX_ANGLE);
  g_doneState = doneState;
}

bool moveBottleToNonBlockingTick() {
  int current = servo.read();
  if (current == g_targetAngle) {
    CURRENT_BOTTLE_STATE = g_doneState;
    return true;
  }
  if (current < g_targetAngle) {
    servo.write(current + 1);
  } else {
    servo.write(current - 1);
  }
  delay(g_speedDelayMs);
  return false;
}

void moveBottleToAngleBlocking(int targetAngle, BottleState doneState) {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  moveBottleToAngleNonBlockingStart(targetAngle, doneState);
  while (!moveBottleToNonBlockingTick()) {
    // busy-wait mit Schrittverzögerung in Tick
  }
}