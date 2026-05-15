#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <DHT.h>
#include <ModbusMaster.h>

// ======================================================
// WIFI
// ======================================================

const char* ssid = "motorola edge 20 fusion_2684";
const char* password = "12345678";

// CropConnect backend API.
const char* serverName = "https://cropconnect01-production.up.railway.app/api/telemetry/ingest";

// Use the same device id and one shared ESP32 key on both boards:
// 1. sensor ESP32 telemetry board
// 2. pump relay ESP32 board
const char* DEVICE_ID = "ccdev_1778791706_eaa27e63fdcbc077";
const char* SHARED_ESP32_API_KEY = "cc_esp32_user_2026_5b91f3c7a8d04e6bb2f9a41c0d73e852_7e4a9d1c";

// ======================================================
// DHT22
// GPIO18
// ======================================================

#define DHTPIN 18
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

// ======================================================
// SOIL MOISTURE
// GPIO35
// ======================================================

#define MOISTURE_PIN 35

int dryValue = 3800;
int wetValue = 1200;

// ======================================================
// pH SENSOR
// GPIO34
// ======================================================

#define PH_PIN 34

float neutralVoltage = 1.835;
float phVoltageStep = 0.18;

// ======================================================
// NPK SENSOR
// RX = GPIO16
// TX = GPIO17
// RE/DE = GPIO4
// ======================================================

#define RE_DE 4

ModbusMaster node;

// ======================================================
// RS485 CONTROL
// ======================================================

void preTransmission() {
  digitalWrite(RE_DE, HIGH);
  delay(2);
}

void postTransmission() {
  delay(2);
  digitalWrite(RE_DE, LOW);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

float readPhValue(float voltage) {
  float phValue = 7.0 + ((neutralVoltage - voltage) / phVoltageStep);
  return constrain(phValue, 0.0, 14.0);
}

// ======================================================
// SETUP
// ======================================================

void setup() {
  Serial.begin(115200);

  // ======================================================
  // WIFI CONNECT
  // ======================================================

  connectWiFi();

  // ======================================================
  // DHT22
  // ======================================================

  dht.begin();

  // ======================================================
  // ADC
  // ======================================================

  analogReadResolution(12);

  // ======================================================
  // NPK SENSOR
  // ======================================================

  pinMode(RE_DE, OUTPUT);
  digitalWrite(RE_DE, LOW);

  Serial2.begin(4800, SERIAL_8N1, 16, 17);

  node.begin(1, Serial2);
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);

  Serial.println("All Sensors Started");
}

// ======================================================
// LOOP
// ======================================================

void loop() {
  connectWiFi();

  // ======================================================
  // NPK SENSOR
  // ======================================================

  int nitrogen = 0;
  int phosphorus = 0;
  int potassium = 0;

  uint8_t result;

  result = node.readHoldingRegisters(30, 3);

  if (result == node.ku8MBSuccess) {
    nitrogen = node.getResponseBuffer(0);
    phosphorus = node.getResponseBuffer(1);
    potassium = node.getResponseBuffer(2);
  }

  // ======================================================
  // MOISTURE
  // ======================================================

  int moistureADC = analogRead(MOISTURE_PIN);

  int moisturePercent = map(moistureADC, dryValue, wetValue, 0, 100);
  moisturePercent = constrain(moisturePercent, 0, 100);

  // ======================================================
  // DHT22
  // ======================================================

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temperature)) {
    temperature = 0;
  }

  if (isnan(humidity)) {
    humidity = 0;
  }

  // ======================================================
  // pH SENSOR
  // ======================================================

  long totalADC = 0;

  for (int i = 0; i < 100; i++) {
    totalADC += analogRead(PH_PIN);
    delay(10);
  }

  float avgADC = totalADC / 100.0;
  float voltage = avgADC * (3.3 / 4095.0);
  float phValue = readPhValue(voltage);

  String phType = "NEUTRAL";

  if (voltage > 1.870) {
    phType = "ACIDIC";
  } else if (voltage < 1.800) {
    phType = "BASIC";
  }

  // ======================================================
  // SERIAL MONITOR
  // ======================================================

  Serial.println("\n========== SENSOR DATA ==========");

  Serial.print("Device ID: ");
  Serial.println(DEVICE_ID);

  Serial.print("Nitrogen: ");
  Serial.println(nitrogen);

  Serial.print("Phosphorus: ");
  Serial.println(phosphorus);

  Serial.print("Potassium: ");
  Serial.println(potassium);

  Serial.print("Moisture: ");
  Serial.print(moisturePercent);
  Serial.println("%");

  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" C");

  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.println("%");

  Serial.print("pH Voltage: ");
  Serial.println(voltage, 3);

  Serial.print("pH Value: ");
  Serial.println(phValue, 2);

  Serial.print("pH Type: ");
  Serial.println(phType);

  // ======================================================
  // SEND DATA TO CROPCONNECT
  // ======================================================

  if (WiFi.status() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    http.begin(client, serverName);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", SHARED_ESP32_API_KEY);

    String payload = "{";
    payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
    payload += "\"soil_moisture\":" + String(moisturePercent) + ",";
    payload += "\"temperature\":" + String(temperature, 2) + ",";
    payload += "\"humidity\":" + String(humidity, 2) + ",";
    payload += "\"ph\":" + String(phValue, 2) + ",";
    payload += "\"nitrogen\":" + String(nitrogen) + ",";
    payload += "\"phosphorus\":" + String(phosphorus) + ",";
    payload += "\"potassium\":" + String(potassium);
    payload += "}";

    Serial.print("POST ");
    Serial.println(serverName);
    Serial.print("Payload: ");
    Serial.println(payload);

    int httpResponseCode = http.POST(payload);

    Serial.print("HTTP Response Code: ");
    Serial.println(httpResponseCode);

    if (httpResponseCode > 0) {
      Serial.print("Response: ");
      Serial.println(http.getString());
    }

    http.end();
  }

  Serial.println("=================================");

  // Upload every 30 seconds
  delay(30000);
}
