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



Servo servo;

#define MIN_ANGLE 0
#define MAX_ANGLE 180
#define MID_POINT 90


BottleState CURRENT_BOTTLE_STATE = UNKNOWN_STATE;





void initBottleMechanism() {
  //servo.attach(A1, MIN_ANGLE, MAX_ANGLE);              // Servo an A1 😈
//  resetBottleState();
CURRENT_BOTTLE_STATE = INIT_STATE;

}



void resetBottleState() {
  // moveInit();

}

BottleState getBottleState() {
  return CURRENT_BOTTLE_STATE;
}

// TODO Maybe make a non blocking move function like the one for the tray

void moveDrop() {



  CURRENT_BOTTLE_STATE = MOVING_STATE;

  int current = servo.read(); // Aktueller Servo-Winkel
  int target = MID_POINT * 2;
  if (current < target) {

    for (int pos = current; pos <= target; pos++) {
      servo.write(pos);
      delay(15); // Geschwindigkeit anpassen (größer = langsamer)
    }
  } else {
    for (int pos = current; pos >= target; pos--) {
      servo.write(pos);
      delay(15);
    }
  }
  CURRENT_BOTTLE_STATE = DROP_STATE;
}

void moveInit() {
  CURRENT_BOTTLE_STATE = MOVING_STATE;
  int current = servo.read();
  int target = MID_POINT;
  if (current < target) {
    for (int pos = current; pos <= target; pos++) {
      servo.write(pos);
      delay(15);
    }
  } else {
    for (int pos = current; pos >= target; pos--) {
      servo.write(pos);
      delay(15);
    }
  }
  CURRENT_BOTTLE_STATE = INIT_STATE;
}