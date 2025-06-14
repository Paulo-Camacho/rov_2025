#include <ArduinoJson.h>
#include <Servo.h>

// Defining servos for discrete thruster control
Servo leftThruster;
Servo rightThruster;
Servo leftUpThruster;
Servo rightUpThruster;

// Claw servos (new naming)
Servo claw;         // This servo is controlled by "claw_trigger"
const byte clawPin = 29; // J9

Servo claw2;        // This servo is controlled by "claw_bumper"
const byte claw2Pin = 25; 

// Explicit thruster pin assignments
const byte leftThrusterPin = 26;
const byte rightThrusterPin = 24;
const byte leftUpThrusterPin = 22;
const byte rightUpThrusterPin = 28;

void setup() {
  Serial.begin(9600);

  // Attach each thruster individually
  leftThruster.attach(leftThrusterPin);
  leftThruster.writeMicroseconds(1500);

  rightThruster.attach(rightThrusterPin);
  rightThruster.writeMicroseconds(1500);

  leftUpThruster.attach(leftUpThrusterPin);
  leftUpThruster.writeMicroseconds(1500);

  rightUpThruster.attach(rightUpThrusterPin);
  rightUpThruster.writeMicroseconds(1500);

  // Setup claw servos
  claw.attach(clawPin);
  claw.writeMicroseconds(1500);

  claw2.attach(claw2Pin);
  claw2.writeMicroseconds(1500); // Neutral position

  delay(7000);  // Calibration delay for ESCs and claws
}

void loop() {
  if (!Serial.available()) return;

  String json = Serial.readStringUntil('\0');
  StaticJsonDocument<300> doc;
  if (deserializeJson(doc, json)) return;

  // Set thruster outputs from the "axisInfo" array, if available.
  JsonArray axis = doc["axisInfo"];
  if (axis.size() >= 4) { 
    leftThruster.writeMicroseconds(axis[0]);
    rightThruster.writeMicroseconds(axis[1]);
    leftUpThruster.writeMicroseconds(axis[2]);
    rightUpThruster.writeMicroseconds(axis[3]);
  }
  
  // Use new key names for claw control.
  if (doc.containsKey("claw_trigger")) {
    claw.writeMicroseconds(doc["claw_trigger"]);
  }

  if (doc.containsKey("claw_bumper")) {  
    claw2.writeMicroseconds(doc["claw_bumper"]);
  }

  StaticJsonDocument<50> ack;
  ack["status"] = "OK";
  serializeJson(ack, Serial);
  Serial.print('\n');
}
