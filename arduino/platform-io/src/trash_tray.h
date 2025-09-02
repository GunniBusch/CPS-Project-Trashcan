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
void trayStopImmediate();

// Positionen pro Typ setzen/abfragen (in Steps)
bool setTrayPositionForType(TrashType type, int steps);
int getTrayPositionForType(TrashType type);

// Diagnose
long getTrayCurrentPosition();
long getTrayTargetPosition();
long getTrayDistanceToGo();
float getTraySpeed();
bool isCalibrated();

// This is moving + calling isInPosition.
bool moveToTargetPosition();

bool isTrayLoaded();
void initTrashTray();
bool calibrateTrashTray();
