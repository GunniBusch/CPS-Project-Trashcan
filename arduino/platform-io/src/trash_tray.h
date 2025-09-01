enum TrashTrayState
{
    READY,
    CALIBRATING,
    MOVING,
    UNAVAILABLE,
    ESTOP_STATE
};

// ENUM to represent the possible trash states of glas plastik and cans
enum TrashType
{
    PLASTIC,
    GLAS,

    CAN
};
void initTrashTray();
bool selectTrashType(TrashType type);
TrashType getCurrentTrashType();
TrashTrayState getTrashTrayState();

// This is moving + calling isInPosition.
bool moveToTargetPosition();

bool isTrayLoaded();
void initTrashTray();
bool calibrateTrashTray();
