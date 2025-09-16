#include "Cyclops.h"

// --- Configuration ---

// Define the input pins
const int labjackPin = 18; // SDA pin for the square wave input
const int flybackPin = 3;     // TRIG0 pin for the 1KHz trigger input (for Cyclops CH0)

// Define the brightness for the "ON" state (4095 is 100% for the 12-bit DAC)
const uint16_t ledBrightness = 4095;

// --- Global Objects ---

// Create a Cyclops object for the first channel (CH0).
// The trigger pin (3) and LED output are associated with this channel.
Cyclops cyclops0(CH0, 1000);

// --- Interrupt Service Routine (ISR) ---

// This function is called automatically whenever a state change is detected
// on either of the input pins. It must be as fast as possible.
void handleInputChange() {
  // Read the current state of both input pins
  bool labjackState = digitalRead(labjackPin);
  bool flybackState = digitalRead(flybackPin);

  // Perform the logical AND operation
  if (labjackState && flybackState) {
    // If BOTH inputs are HIGH, turn the LED ON to full brightness
    cyclops0.dac_load_voltage(ledBrightness);
    //Serial.println("Both inputs are HIGH");
  } else {
    // Otherwise (if one or both are LOW), turn the LED OFF
    cyclops0.dac_load_voltage(0);
  }
}

// --- Main Program ---

void setup() {
  Serial.begin(9600);
  // Initialize the Cyclops driver system (starts SPI and safety timers)
  Cyclops::begin();

  // Ensure the LED starts in the OFF state
  cyclops0.dac_load_voltage(0);

  // Configure our two signal pins as inputs
  pinMode(labjackPin, INPUT);
  pinMode(flybackPin, INPUT);

  // Attach the interrupts.
  // The 'handleInputChange' function will be called whenever the state of
  // either pin changes (from LOW to HIGH or HIGH to LOW).
  attachInterrupt(digitalPinToInterrupt(labjackPin), handleInputChange, CHANGE);
  attachInterrupt(digitalPinToInterrupt(flybackPin), handleInputChange, CHANGE);
}

void loop() {
  // The main loop is intentionally left empty.
  // All the logic is handled by the hardware interrupts, which is much faster
  // and more reliable for high-frequency signals. The Teensy can perform
  // other tasks here if needed.
}
