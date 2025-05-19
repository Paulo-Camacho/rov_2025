#include <ArduinoJson.h>
#include <Servo.h>

Servo left, right, leftUp, rightUp;
const byte pins[4] = {26, 27, 22, 28}; // Left, Right, LeftUp, RightUp
// 26, 29, 22, 28

void setup() {
  Serial.begin(9600);
  for(int i=0; i<4; i++) {
    (i==0 ? left : i==1 ? right : i==2 ? leftUp : rightUp).attach(pins[i]);
    (i==0 ? left : i==1 ? right : i==2 ? leftUp : rightUp).writeMicroseconds(1500);
  }
  delay(7000); // ESC init
}

void loop() {
  if(Serial.available()) {
    String json = Serial.readStringUntil('\0');
    StaticJsonDocument<200> doc;
    deserializeJson(doc, json);
    
    JsonArray axis = doc["axisInfo"];
    left.writeMicroseconds(axis[0]);
    right.writeMicroseconds(axis[1]);
    leftUp.writeMicroseconds(axis[2]);
    rightUp.writeMicroseconds(axis[3]);
    
    // Send acknowledgment
    StaticJsonDocument<50> ack;
    ack["status"] = "OK";
    serializeJson(ack, Serial);
  }
}
