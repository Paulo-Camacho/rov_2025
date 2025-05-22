#include <ArduinoJson.h>
#include <Servo.h>

Servo left, right, leftUp, rightUp;
const byte pins[4] = {26, 24, 22, 28};  // Left, Right, LeftUp, RightUp

Servo claw;
const byte clawPin = 29;

void setup() {
  Serial.begin(9600);

  // Attach thruster servos and set to neutral
  for (int i = 0; i < 4; i++) {
    Servo &s = (i == 0 ? left : i == 1 ? right : i == 2 ? leftUp : rightUp);
    s.attach(pins[i]);
    s.writeMicroseconds(1500);
  }

  // Attach claw servo and set to neutral
  claw.attach(clawPin);
  claw.writeMicroseconds(1500);

  delay(7000);  // Allow ESCs and claw to calibrate
}

void loop() {
  if (!Serial.available()) return;

  // Read a null-terminated JSON string from Serial
  String json = Serial.readStringUntil('\0');
  StaticJsonDocument<200> doc;
  if (deserializeJson(doc, json)) return;  // drop invalid JSON

  // Update thruster servos
  JsonArray axis = doc["axisInfo"];
  left.writeMicroseconds(axis[0]);
  right.writeMicroseconds(axis[1]);
  leftUp.writeMicroseconds(axis[2]);
  rightUp.writeMicroseconds(axis[3]);

  // Control claw if present in message
  if (doc.containsKey("claw")) {
    int cw = doc["claw"];
    claw.writeMicroseconds(cw);
  }

  // Send acknowledgment back to Python
  StaticJsonDocument<50> ack;
  ack["status"] = "OK";
  serializeJson(ack, Serial);
  Serial.print('\n');  // newline for Python readline()
}
