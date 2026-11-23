/*
  Anukul room node - ESP32 + SCD41 (CO2/temp/humidity) + LD2410C (presence) + SSD1306 OLED + relay.
  Runs the same Sense -> Decide -> Act loop as the building controller, for one room:
    SENSE  : CO2, temperature, humidity every 5 s; human presence from the mmWave radar
    DECIDE : - room occupied and CO2 > 1000 ppm  -> ventilate (fan ON)
             - room empty for 10 minutes        -> fan OFF and flag "AC can switch off"
             - room occupied and temp < 23 C    -> flag "overcooled: raise AC to 24 C"
    ACT    : drives the relay (LOW-VOLTAGE fan only - never wire mains to this board)
    EXPLAIN: shows the reason on the OLED and serves it as JSON at http://<node-ip>/data
  Libraries (Arduino Library Manager): "Sensirion I2C SCD4x", "Adafruit SSD1306", "Adafruit GFX".
  Board: "ESP32 Dev Module" (Espressif esp32 core 3.x).
  Wiring: SCD41 & OLED -> SDA 21, SCL 22, 3V3, GND | LD2410C OUT -> GPIO 27, VCC 5V, GND | relay IN -> GPIO 26.
*/
#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SensirionI2cScd4x.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const char* WIFI_SSID = "YOUR_WIFI";       // <- change
const char* WIFI_PASS = "YOUR_PASSWORD";   // <- change
const int PIN_PRESENCE = 27, PIN_RELAY = 26;
const float CO2_LIMIT = 1000, CO2_CLEAR = 850, COLD_LIMIT = 23.0;
const unsigned long EMPTY_MS = 10UL * 60UL * 1000UL;

SensirionI2cScd4x scd;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
WebServer server(80);
float co2 = 0, temp = 0, rh = 0;
bool present = false, fanOn = false;
unsigned long lastSeen = 0, lastRead = 0;
String reason = "starting";
float fanMinutes = 0;

void decide() {
  unsigned long now = millis();
  if (present) lastSeen = now;
  bool empty = (now - lastSeen) > EMPTY_MS;
  if (!empty && co2 > CO2_LIMIT) { fanOn = true;  reason = "CO2 high, people in -> ventilate"; }
  else if (fanOn && co2 < CO2_CLEAR) { fanOn = false; reason = "CO2 back to normal -> fan off"; }
  else if (empty) { fanOn = false; reason = "empty 10 min -> AC & fan can switch off"; }
  else if (temp < COLD_LIMIT) { reason = "overcooled -> raise AC to 24 C"; }
  else if (!fanOn) { reason = "all good"; }
  digitalWrite(PIN_RELAY, fanOn ? HIGH : LOW);
}

void show() {
  oled.clearDisplay(); oled.setTextSize(1); oled.setTextColor(SSD1306_WHITE); oled.setCursor(0, 0);
  oled.printf("ANUKUL  %s\n", present ? "occupied" : "empty");
  oled.printf("CO2 %4.0f ppm\nT %4.1f C  RH %2.0f%%\nFan %s\n\n", co2, temp, rh, fanOn ? "ON" : "off");
  oled.println(reason);
  oled.display();
}

void handleData() {
  char buf[300];
  snprintf(buf, sizeof(buf),
           "{\"co2\":%.0f,\"temp\":%.1f,\"rh\":%.0f,\"present\":%s,\"fan\":%s,\"fan_minutes\":%.1f,\"reason\":\"%s\"}",
           co2, temp, rh, present ? "true" : "false", fanOn ? "true" : "false", fanMinutes, reason.c_str());
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", buf);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PRESENCE, INPUT); pinMode(PIN_RELAY, OUTPUT); digitalWrite(PIN_RELAY, LOW);
  Wire.begin(21, 22);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  scd.begin(Wire, SCD41_I2C_ADDR_62);
  scd.stopPeriodicMeasurement(); delay(500);
  scd.startPeriodicMeasurement();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  Serial.print("Anukul node at http://"); Serial.print(WiFi.localIP()); Serial.println("/data");
  server.on("/data", handleData);
  server.begin();
  lastSeen = millis();
}

void loop() {
  server.handleClient();
  present = digitalRead(PIN_PRESENCE) == HIGH;
  if (millis() - lastRead > 5000) {
    bool ready = false;
    scd.getDataReadyStatus(ready);
    if (ready) {
      uint16_t c; float t, h;
      if (scd.readMeasurement(c, t, h) == 0) { co2 = c; temp = t; rh = h; }
    }
    if (fanOn) fanMinutes += 5.0 / 60.0;
    lastRead = millis();
    decide(); show();
    Serial.printf("co2=%.0f temp=%.1f rh=%.0f present=%d fan=%d reason=%s\n", co2, temp, rh, present, fanOn, reason.c_str());
  }
}
