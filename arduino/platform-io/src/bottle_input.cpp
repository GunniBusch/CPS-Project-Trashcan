/**
 * This file handles the bottle moving mechanism.
 * It controlles the tube that moves the bottle over the trash tray.
 * 
 * 
 * And its not explosive, sort of ...
 */


#include <Servo.h>
#include <Arduino.h>
#include <bottle_input.h>
#include "trash_tray.h"



Servo servo;

#define MIN_ANGLE 0
#define MAX_ANGLE 280
#define MID_POINT 90

// Winkel-Mapping:
// PLASTIC & CAN -> Loch 1 bei 0°
// GLAS          -> Loch 2 bei 180°
// Normal        -> 90°



BottleState CURRENT_BOTTLE_STATE = UNKNOWN_STATE;

// Configurable mapping: default PLASTIC/CAN -> HOLE1, GLAS -> HOLE2
static Hole g_holeForPlastic = HOLE1;
static Hole g_holeForGlas = HOLE1;
static Hole g_holeForCan = HOLE2;

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

// Move to drop hole

void moveDrop(Hole hole) {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  int target = (hole == HOLE2) ? HOLE2_ANGLE : HOLE1_ANGLE;
  moveBottleToAngleNonBlockingStart(target, (hole == HOLE2) ? DROP_HOLE2_STATE : DROP_HOLE1_STATE);
}

void moveDrop() {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  int target = HOME_ANGLE;
  BottleState done = UNKNOWN_STATE;
  TrashType t = getCurrentTrashType();
  Hole h = getHoleForType(t);
  if (h == HOLE2) {
    target = HOLE2_ANGLE;
    done = DROP_HOLE2_STATE;
  } else {
    target = HOLE1_ANGLE;
    done = DROP_HOLE1_STATE;
  }
  moveBottleToAngleNonBlockingStart(target, done);
  // Blocking drive using the non-blocking tick
  while (!moveBottleToNonBlockingTick()) {
    // yield
  }
}

void startDropMoveForCurrentType() {
  // Initialize a non-blocking drop move based on current TrashType
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  TrashType t = getCurrentTrashType();
  Hole h = getHoleForType(t);
  if (h == HOLE2) {
    moveBottleToAngleNonBlockingStart(HOLE2_ANGLE, DROP_HOLE2_STATE);
  } else {
    moveBottleToAngleNonBlockingStart(HOLE1_ANGLE, DROP_HOLE1_STATE);
  }
}

void moveInit() {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  moveBottleToAngleNonBlockingStart(HOME_ANGLE, INIT_STATE);
  while (!moveBottleToNonBlockingTick()) {
    // yield this ......... ..... ... .. -> why?????
  }
}

void setBottleSpeedDelay(int ms) {
  if (ms < 1) ms = 1;
  g_speedDelayMs = ms;
}

void moveBottleToAngleNonBlockingStart(int targetAngle, BottleState doneState) {
  g_targetAngle = constrain(targetAngle, MIN_ANGLE, MAX_ANGLE);
  g_doneState = doneState;
  // Markiere Bewegung gestartet, um Mehrfach-Initialisierung im State-Machine-Tick zu vermeiden
  CURRENT_BOTTLE_STATE = MOVING_STATE;
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

// --- Configurable mapping helpers ---
Hole getHoleForType(TrashType t) {
  switch (t) {
    case PLASTIC: return g_holeForPlastic;
    case GLAS:    return g_holeForGlas;
    case CAN:     return g_holeForCan;
  }
  return HOLE1;
}



int getAngleForHole(Hole hole) {
  return (hole == HOLE2) ? HOLE2_ANGLE : HOLE1_ANGLE;
}

int getAngleForType(TrashType t) {
  return getAngleForHole(getHoleForType(t));
}