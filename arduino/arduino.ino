#include <ArduinoJson.h>
#include <Servo.h>

// Defining servos for discrete thruster control
Servo leftThruster;
Servo rightThruster;
Servo leftUpThruster;
Servo rightUpThruster;

// Claw servo
Servo claw;
const byte clawPin = 29; // J9

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

  // Claw setup
  claw.attach(clawPin);
  claw.writeMicroseconds(1500);

  delay(7000);  // ESC and claw calibration time
}

void loop() {
  if (!Serial.available()) return;

  String json = Serial.readStringUntil('\0');
  StaticJsonDocument<300> doc;
  if (deserializeJson(doc, json)) return;

  JsonArray axis = doc["axisInfo"];
  if (axis.size() >= 4) { // Adjusted for only four thrusters
    leftThruster.writeMicroseconds(axis[0]);
    rightThruster.writeMicroseconds(axis[1]);
    leftUpThruster.writeMicroseconds(axis[2]);
    rightUpThruster.writeMicroseconds(axis[3]);
  }

  if (doc.containsKey("claw")) {
    claw.writeMicroseconds(doc["claw"]);
  }

  StaticJsonDocument<50> ack;
  ack["status"] = "OK";
  serializeJson(ack, Serial);
  Serial.print('\n');
}
