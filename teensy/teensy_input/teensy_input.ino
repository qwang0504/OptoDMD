#include <Cyclops.h>

const int pulsePin = 18; // SDA pin is pin 18 on Teensy 3.2
Cyclops cyclops0(CH0, 1000);

void setup() {
  Serial.begin(9600);
  pinMode(pulsePin, INPUT); // Configure the SDA pin as a digital input
}

void loop() {
  int pulseState = digitalRead(pulsePin); // Read the state of the pin

  if (pulseState == HIGH) {
    Serial.println("Pulse detected!");
  }

  delay(100); // Small delay to prevent spamming the serial monitor
}