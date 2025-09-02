#ifndef CPS_TRASH_TRAY_H
#define CPS_TRASH_TRAY_H

#include "trash_types.h"

enum TrashTrayState
{
    READY,
    CALIBRATING,
    MOVING,
    UNAVAILABLE,
    ESTOP_STATE
};

// TrashType now defined in trash_types.h

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
bool calibrateTrashTray();

#endif // CPS_TRASH_TRAY_H
