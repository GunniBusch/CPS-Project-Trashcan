#include <Servo.h>
#include <cmath>

Servo myServo;

const int MIN_ANGLE = 0;

const int MAX_ANGLE= 10;

const int MID_POINT = 90;

int buttonRight = 2;   // Knopf für Rechts
int buttonLeft  = 3;   // Knopf für Links



void setup() {
  myServo.attach(A1, MIN_ANGLE, MAX_ANGLE);              // Servo an A1
  pinMode(buttonRight, INPUT_PULLUP); // Knöpfe mit Pullup
  pinMode(buttonLeft, INPUT_PULLUP);
  myServo.write(MID_POINT);              // Servo auf Mitte stellen

  attachInterrupt(digitalPinToInterrupt(buttonRight), moveDrop, CHANGE);
  attachInterrupt(digitalPinToInterrupt(buttonLeft), moveInit, CHANGE);

}

void loop() {
  // Wenn rechter Knopf gedrückt → nach rechts bewegen
 
lerp

}


void moveDrop() {

  myServo.write(MID_POINT*2);

}

void moveInit() {

  myServo.write(MID_POINT);

}