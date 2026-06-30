void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
}

void loop() {
  int val12 = analogRead(12);
  int val14 = analogRead(14);

  Serial.print("Pin12:");
  Serial.print(val12);
  Serial.print(",Pin14:");
  Serial.println(val14);

  delay(100);
}
