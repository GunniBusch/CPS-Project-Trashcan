// Expose TrashType for mapping APIs
#pragma once
#ifndef BOTTLE_INPUT_H
#define BOTTLE_INPUT_H
#include "trash_types.h"


enum BottleState {
  INIT_STATE,
  DROP_HOLE1_STATE, // Drop über Loch 1 (0°)
  DROP_HOLE2_STATE, // Drop über Loch 2 (180°)
  MOVING_STATE,
  UNKNOWN_STATE,
};

enum Hole {
  HOLE1,
  HOLE2
};

static const int HOLE1_ANGLE = 0;    // Plastic/Can
static const int HOLE2_ANGLE = 135;  // Glass
static const int HOME_ANGLE  = 45;   // Normal
void resetBottleState();
void moveDrop(Hole hole);
void moveDrop();
void moveInit();
void initBottleMechanism();
BottleState getBottleState();
int getBottleAngle();

// Non-Blocking API (optional):
void setBottleSpeedDelay(int ms);
void moveBottleToAngleNonBlockingStart(int targetAngle, BottleState doneState);
// returns true when finished; false when still moving
bool moveBottleToNonBlockingTick();
// Convenience: blockierend auf Winkel fahren
void moveBottleToAngleBlocking(int targetAngle, BottleState doneState);

// Startet eine Drop-Bewegung je nach aktuellem TrashType (nicht-blockierend)
void startDropMoveForCurrentType();

// Configurable mapping: which hole is used for each TrashType
Hole getHoleForType(TrashType t);
int getAngleForHole(Hole hole);
int getAngleForType(TrashType t);

#endif // BOTTLE_INPUT_H
