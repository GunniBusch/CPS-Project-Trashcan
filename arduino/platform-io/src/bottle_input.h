

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
