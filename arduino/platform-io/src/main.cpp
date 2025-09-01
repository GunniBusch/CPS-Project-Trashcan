#include <Servo.h>
#include <Arduino.h>
#include <trash_tray.h>
#include <bottle_input.h>

// Forward declaration so it can be used before its definition.
void handleSerialCommand(const String& cmd);

/**
 * This will control the whole trash can, by using the code from the trash_tray and bottle_input files.
 */

enum TrashCanState
{
  LOADING, // Starting up and initializing
  IDLE,
  CONTAINS_BOTTLE,
  WAITING_FOR_TRAY,
  TRAY_IN_POSITION,
  MOVING_BOTTLE_TO_TRAY,
  BOTTLE_IN_TRAY,
  MOVING_TO_IDLE,
  // ERROR STATES
  EMO_MOOD,

};

TrashCanState currentTrashState = LOADING;

void setup()
{
  Serial.begin(9600);

  initTrashTray();
  initBottleMechanism();
}



void loop()
{
 

  switch (currentTrashState)
  {
  case LOADING:
    // Handle loading state

    if (calibrateTrashTray())
    {
      currentTrashState = IDLE;
    }
    else
    {
      // Doesnt work if calibrated. Is jsut the loop thingy idk
      
    }
     currentTrashState = IDLE;
    break;
  case IDLE:

    // Just Chill.

    // TODO: COMMUNICATE WITH RASPBERRY PI

    // Handle idle state
     // Serielle Eingabe prüfen
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      handleSerialCommand(input);
    }
  }
    break;

  // NEXT STATES WILL NEVER OCCURE OUT OF ORDER.
  case CONTAINS_BOTTLE:

    // This state does nothing, but is important since it makes sure that all follwing states are only switch in the loop function, to avoid that drunken idiots manually interfear with the automated process.
    // So just chill and wait for the next state.
    // AND NEVER EVER PUT ME IN ANY BELOW STATES FROM OUTSIDE THIS FUNCTION.
    // ALSO THE TRAY SHOULD

    // OH One thing it does is doing some boring things to make sure every component is in working state and its safe to continue.

    if (isTrayLoaded() && getBottleState() == INIT_STATE && getTrashTrayState() == READY)
    {
      currentTrashState = WAITING_FOR_TRAY;
    }
    else
    {
      currentTrashState = EMO_MOOD; // Something is wrong.  TODO: Maybe some 100db alarm to inform the neighbors that our trash can is moody.
      break;
    }

    break;
  case WAITING_FOR_TRAY:

    // We move the tray to the targeted position, since target should have been set outside this abomination.

    // The `moveToTargetPosition` function actaully also moves the tray.
    if (moveToTargetPosition())
    {
      currentTrashState = TRAY_IN_POSITION;
    }

    // Handle waiting for tray state
    break;
  case TRAY_IN_POSITION:
    // Handle tray in position state

    // Double check if the tray is indeed in position
    if (getTrashTrayState() == READY)
    {
      currentTrashState = MOVING_BOTTLE_TO_TRAY;
    }
    else
    {
      currentTrashState = EMO_MOOD;
    }
    break;
  case MOVING_BOTTLE_TO_TRAY:
    // Handle moving bottle to tray state

    // This is blocking
    moveDrop();

    if (getBottleState() == DROP_STATE)
    {
      currentTrashState = BOTTLE_IN_TRAY;
    }
    break;
  case BOTTLE_IN_TRAY:

    // This state is reached when the bottle is over the hole, but since we do not know if the bottle is already fully dropped, we wait.
    delay(1000); 

    currentTrashState = MOVING_TO_IDLE;
    break;
  case MOVING_TO_IDLE:
    // Handle moving to idle state
    moveInit();

    
    if (getBottleState() == INIT_STATE)
    {
      currentTrashState = IDLE;
    }
    
    break;
  case EMO_MOOD:

  // TODO: Implement error handling and recovery
    // Handle emo mood state -> our error state
    break;
  }
}

void recvBottleIn(TrashType type)
{
  // Handle the event when a bottle is detected
  Serial.print(">bottle");
  Serial.println(type);

  selectTrashType(type);
  currentTrashState = CONTAINS_BOTTLE;
}


void estop()
{

  // TODO: Implement emergency stop functionality
  // This should immediately stop all movements and electroshok the idiot who pressed the emergency stop button
  currentTrashState = EMO_MOOD;
}
void handleSerialCommand(const String& cmd) {
  int sep = cmd.indexOf("::");
  if (sep == -1) return;
  String func = cmd.substring(0, sep);
  String val = cmd.substring(sep + 2);
  if (func == "m") {
    int value = val.toInt();
    // Beispiel: Servo-Position setzen (hier Dummyfunktion)

    recvBottleIn(TrashType(value));
    Serial.print("Servo move to: ");
    Serial.println(value);
  
  }
  // Weitere Funktionen können hier ergänzt werden
}
// TODO: Implement error handling and recovery
// TODO: Communicate with Raspberry Pi and interrupt when it detects an error
// TODO: add timeouts for moving function. this needed since too long delays maybe related to issues eg obstacles


