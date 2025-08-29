#include <Servo.h>

Servo myServo;

int buttonRight = 2;   // Knopf für Rechts
int buttonLeft  = 3;   // Knopf für Links
int pos = 90;          // Startposition in der Mitte

void setup() {
  myServo.attach(A1);              // Servo an A1
  pinMode(buttonRight, INPUT_PULLUP); // Knöpfe mit Pullup
  pinMode(buttonLeft, INPUT_PULLUP);
  myServo.write(pos);              // Servo auf Mitte stellen
}

void loop() {
  // Wenn rechter Knopf gedrückt → nach rechts bewegen
  if (digitalRead(buttonRight) == LOW) {
    if (pos < 180) {               // nur solange kleiner als 180°
      pos++;
      myServo.write(pos);
      delay(15);                   // Geschwindigkeit einstellen
    }
  }

  // Wenn linker Knopf gedrückt → nach links bewegen
  if (digitalRead(buttonLeft) == LOW) {
    if (pos > 0) {                 // nur solange größer als 0°
      pos--;
      myServo.write(pos);
      delay(15);
    }
  }

}
