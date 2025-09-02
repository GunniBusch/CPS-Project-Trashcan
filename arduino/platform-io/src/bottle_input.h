

enum BottleState {
  INIT_STATE,
  DROP_STATE,
  MOVING_STATE,
  UNKNOWN_STATE,
  
};

void resetBottleState();
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
