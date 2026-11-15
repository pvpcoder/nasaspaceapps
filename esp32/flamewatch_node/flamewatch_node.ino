/*
  FlameWatch sensor box - Habitat Fire Safety Node
  ------------------------------------------------
  Sends readings to the FlameWatch backend (POST /api/reading) once a second and
  drives the traffic light + vent servo from the reply {"level","mode","vent"}.

  Board:   Tools > Board > ESP32 Wrover Module   (ESP32 Arduino core 3.x)
  Libs:    Library Manager > install "OneWire" and "DallasTemperature"
  Partition (for wireless uploads): Tools > Partition Scheme >
           "Minimal SPIFFS (1.9MB APP with OTA/190KB SPIFFS)"
  Secrets: copy secrets.example.h to secrets.h (same folder) and fill it in.
           secrets.h is git-ignored, so WiFi passwords never reach GitHub.

  Wiring (matches the breadboard diagram):
    Potentiometer  middle pin -> GPIO34   (outer pins: 3.3V, GND)
    DS18B20        DATA       -> GPIO32   (+ 4.7k resistor DATA->3.3V)
    Servo          signal     -> GPIO25   (power from 6V battery, GND shared)
    Traffic light  G -> 23, Y -> 22, R -> 21, GND -> GND
    PIR            OUT        -> GPIO19   (VCC 5V, GND)
    Ultrasonic     TRIG -> GPIO5, ECHO -> 1k -> GPIO18 (2k from GPIO18 to GND)
    Switch         GPIO4 <-> GND

  Any part that is not plugged in is simply reported as "null" -
  the rest keeps working, so you can add parts one at a time.
*/

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoOTA.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#include "secrets.h"   // WiFi + OTA settings (see secrets.example.h)

const char* SERVER_URL = "https://flamewatch.onrender.com/api/reading";
#define ENABLE_OTA 1                                 // wireless uploads

// ---------- Pins ----------
const int PIN_POT    = 34;
const int PIN_TEMP   = 32;
const int PIN_SERVO  = 25;
const int PIN_LED_G  = 23;
const int PIN_LED_Y  = 22;
const int PIN_LED_R  = 21;
const int PIN_PIR    = 19;
const int PIN_TRIG   = 5;
const int PIN_ECHO   = 18;
const int PIN_SWITCH = 4;

// ---------- Tuning ----------
const int   SERVO_OPEN_US    = 1500;   // vent open position  (adjust to taste)
const int   SERVO_CLOSED_US  = 2100;   // vent closed position
const float O2_MIN           = 21.0;   // pot fully left  = Earth air
const float O2_MAX           = 40.0;   // pot fully right = very O2-rich
const float HATCH_CLOSED_CM  = 8.0;    // ultrasonic: object closer than this = hatch closed
const unsigned long SEND_INTERVAL_MS   = 1000;
const unsigned long SERVER_FRESH_MS    = 5000;   // trust server answer for this long
const unsigned long LOCAL_SUPPRESS_MS  = 15000;  // offline suppression duration
const unsigned long TEMP_CONVERSION_MS = 800;

// ---------- Globals ----------
OneWire oneWire(PIN_TEMP);
DallasTemperature tempSensor(&oneWire);
WiFiClientSecure tlsClient;
HTTPClient http;

float o2Percent  = O2_MIN;
float tempC      = NAN;
float distanceCm = -1;
bool  crewPresent = false;
bool  suppressPending = false;       // switch pressed, not yet told the server

String serverRisk = "green";
String serverMode = "normal";
bool   serverVentClosed = false;
unsigned long lastServerOk = 0;

String risk = "green";               // what we actually show
String mode = "normal";
bool   ventClosed = false;
unsigned long localSuppressUntil = 0;

unsigned long lastSend = 0;
unsigned long lastWifiRetry = 0;
unsigned long tempRequestedAt = 0;
bool tempRequested = false;
bool otaStarted = false;

int switchReading = HIGH, switchStable = HIGH;
unsigned long switchChangedAt = 0;

// ================= Helpers =================
void setServoUs(int us) {
  // 50 Hz, 14-bit resolution: 20000 us period = 16384 counts
  ledcWrite(PIN_SERVO, (uint32_t)us * 16384UL / 20000UL);
}

void setLeds(bool g, bool y, bool r) {
  digitalWrite(PIN_LED_G, g);
  digitalWrite(PIN_LED_Y, y);
  digitalWrite(PIN_LED_R, r);
}

float readO2() {
  long sum = 0;
  for (int i = 0; i < 8; i++) sum += analogRead(PIN_POT);
  float raw = sum / 8.0;
  return O2_MIN + (raw / 4095.0) * (O2_MAX - O2_MIN);
}

float readDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long dur = pulseIn(PIN_ECHO, HIGH, 25000UL);  // ~4 m max
  if (dur == 0) return -1;                               // nothing / not connected
  return dur * 0.0343f / 2.0f;
}

void updateTemp() {                  // non-blocking DS18B20 read
  unsigned long now = millis();
  if (!tempRequested) {
    tempSensor.requestTemperatures();
    tempRequestedAt = now;
    tempRequested = true;
  } else if (now - tempRequestedAt >= TEMP_CONVERSION_MS) {
    float t = tempSensor.getTempCByIndex(0);
    tempC = (t == DEVICE_DISCONNECTED_C || t < -50) ? NAN : t;
    tempRequested = false;
  }
}

void updateSwitch() {                // debounced, fires once per press
  int r = digitalRead(PIN_SWITCH);
  if (r != switchReading) { switchReading = r; switchChangedAt = millis(); }
  if (millis() - switchChangedAt > 40 && r != switchStable) {
    switchStable = r;
    if (switchStable == LOW) {
      suppressPending = true;
      localSuppressUntil = millis() + LOCAL_SUPPRESS_MS;
      Serial.println("[switch] suppression triggered");
    }
  }
}

// Same formula as risk() in backend/app.py, used when the server can't be reached.
// Oxygen: 0 at 21% -> 60 at 40%.  Heat: 0 at 30 C -> 15 at 60 C.
String localRisk() {
  float atmo = constrain((o2Percent - 21.0f) / 19.0f * 60.0f, 0.0f, 60.0f);
  float heat = isnan(tempC) ? 0 : constrain((tempC - 30.0f) / 30.0f * 15.0f, 0.0f, 15.0f);
  float score = atmo + heat;
  if (score >= 60) return "red";
  if (score >= 30) return "yellow";
  return "green";
}

String jsonValue(const String& s, const char* key) {   // tiny JSON reader
  String k = String("\"") + key + "\":";
  int i = s.indexOf(k);
  if (i < 0) return "";
  i += k.length();
  while (i < (int)s.length() && s[i] == ' ') i++;
  if (i < (int)s.length() && s[i] == '"') {
    int e = s.indexOf('"', i + 1);
    return s.substring(i + 1, e);
  }
  int e = i;
  while (e < (int)s.length() && s[e] != ',' && s[e] != '}') e++;
  return s.substring(i, e);
}

// ================= Networking =================
void wifiBegin() {
#if USE_EDUROAM
  // WPA2-Enterprise (PEAP). ESP32 radios are 2.4 GHz only; eduroam usually
  // broadcasts 2.4 GHz too, so this works even if your laptop shows 5 GHz.
  WiFi.begin(EAP_SSID, WPA2_AUTH_PEAP, EAP_IDENTITY, EAP_USERNAME, EAP_PASSWORD);
#else
  WiFi.begin(WIFI_SSID, WIFI_PASS);
#endif
}

void connectWifi(unsigned long waitMs) {
  if (WiFi.status() == WL_CONNECTED) return;
#if USE_EDUROAM
  Serial.printf("[wifi] connecting to %s (enterprise)\n", EAP_SSID);
#else
  Serial.printf("[wifi] connecting to %s\n", WIFI_SSID);
#endif
  WiFi.mode(WIFI_STA);
  wifiBegin();
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < waitMs) delay(250);
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("[wifi] connected, IP %s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("[wifi] not connected yet - running offline");
}

void startOta() {
#if ENABLE_OTA
  if (otaStarted || WiFi.status() != WL_CONNECTED) return;
  ArduinoOTA.setHostname("fire-node");
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { setLeds(true, true, true); setServoUs(SERVO_OPEN_US); });
  ArduinoOTA.begin();
  otaStarted = true;
  Serial.println("[ota] ready - look for 'fire-node' under Tools > Port");
#endif
}

// Matches the FlameWatch "ESP32 contract" (README). Missing sensors send null,
// and the backend ignores null fields.
String buildJson() {
  String b = "{";
  b += "\"o2_pct\":";    b += String(o2Percent, 1);
  b += ",\"temp_c\":";   b += isnan(tempC) ? String("null") : String(tempC, 1);
  b += ",\"hatch_cm\":"; b += (distanceCm < 0) ? String("null") : String(distanceCm, 1);
  b += ",\"crew\":";     b += crewPresent ? "true" : "false";
  b += ",\"suppress\":"; b += suppressPending ? "true" : "false";
  b += "}";
  return b;
}

void sendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return;
  String body = buildJson();
  if (!http.begin(tlsClient, SERVER_URL)) { Serial.println("[http] bad URL"); return; }
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  if (code == 200) {
    String resp = http.getString();
    String r = jsonValue(resp, "level");
    if (r.length()) serverRisk = r;
    String m = jsonValue(resp, "mode");
    if (m.length()) serverMode = m;
    serverVentClosed = (jsonValue(resp, "vent") == "closed");
    lastServerOk = millis();
    suppressPending = false;         // server got the button press
    Serial.printf("[http] sent %s -> %s\n", body.c_str(), resp.c_str());
  } else {
    Serial.printf("[http] error %d (Render may be waking up)\n", code);
  }
  http.end();
}

// ================= Outputs =================
void applyOutputs() {
  unsigned long now = millis();
  bool serverFresh = lastServerOk && (now - lastServerOk < SERVER_FRESH_MS);

  if (serverFresh) {
    risk = serverRisk; mode = serverMode; ventClosed = serverVentClosed;
  } else {                                   // offline fallback
    bool suppressing = now < localSuppressUntil;
    risk = suppressing ? "yellow" : localRisk();
    mode = suppressing ? "suppressing" : "normal";
    ventClosed = suppressing || risk == "red";
  }

  bool blinkFast = (now / 150) % 2;          // red alarm
  bool blinkSlow = (now / 400) % 2;          // suppression
  if (mode == "suppressing")  setLeds(false, blinkSlow, false);
  else if (risk == "red")     setLeds(false, false, blinkFast);
  else if (risk == "yellow")  setLeds(false, true, false);
  else                        setLeds(true, false, false);

  setServoUs(ventClosed ? SERVO_CLOSED_US : SERVO_OPEN_US);
}

// ================= Setup / loop =================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== Habitat Fire Safety Node ===");

  pinMode(PIN_LED_G, OUTPUT); pinMode(PIN_LED_Y, OUTPUT); pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_TRIG, OUTPUT);  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_SWITCH, INPUT_PULLUP);
  analogReadResolution(12);

  ledcAttach(PIN_SERVO, 50, 14);
  setServoUs(SERVO_OPEN_US);

  tempSensor.begin();
  tempSensor.setWaitForConversion(false);
  Serial.printf("[temp] DS18B20 sensors found: %d\n", tempSensor.getDeviceCount());

  // Startup light check: G -> Y -> R
  setLeds(true, false, false); delay(250);
  setLeds(false, true, false); delay(250);
  setLeds(false, false, true); delay(250);
  setLeds(false, false, false);

  tlsClient.setInsecure();       // fine for a hackathon demo
  http.setReuse(true);
  http.setTimeout(8000);

  connectWifi(15000);
  startOta();
  Serial.println("[pir] give the PIR ~30-60 s to settle");
}

void loop() {
#if ENABLE_OTA
  if (otaStarted) ArduinoOTA.handle();
#endif

  // Read inputs
  o2Percent   = readO2();
  crewPresent = digitalRead(PIN_PIR) == HIGH;
  updateTemp();
  updateSwitch();

  // Keep WiFi alive
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiRetry > 10000) {
    lastWifiRetry = millis();
    WiFi.disconnect();
    wifiBegin();
  }
  startOta();

  // Send once per interval
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    distanceCm = readDistanceCm();
    sendTelemetry();
  }

  applyOutputs();
  delay(10);
}
