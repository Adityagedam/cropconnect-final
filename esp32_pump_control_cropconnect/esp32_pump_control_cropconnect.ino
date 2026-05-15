#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

// ======================================================
// WIFI
// ======================================================

const char* ssid = "motorola edge 20 fusion_2684";
const char* password = "12345678";

// CropConnect backend API.
const char* RELAY_COMMAND_URL = "https://cropconnect01-production.up.railway.app/api/esp32/relay-command";
const char* RELAY_STATUS_URL = "https://cropconnect01-production.up.railway.app/api/esp32/relay-status";

// Use the same device id and one shared ESP32 key on both boards:
// 1. sensor ESP32 telemetry board
// 2. pump relay ESP32 board
const char* DEVICE_ID = "ccdev_1778791706_eaa27e63fdcbc077";
const char* SHARED_ESP32_API_KEY = "cc_esp32_user_2026_5b91f3c7a8d04e6bb2f9a41c0d73e852_7e4a9d1c";

// Local browser control is still available at:
// http://ESP32_IP/on, /off, /status
// http://ESP32_IP/1on, /1off, /allon, /alloff
WiFiServer server(80);

// Direct pump mode: website/browser talks to this ESP32 over local WiFi.
// Keep this false when you do not want the pump board to poll Railway.
const bool ENABLE_BACKEND_SYNC = false;

// Your relay pins (active LOW). Do not change unless wiring changes.
int relays[8] = {19, 18, 5, 17, 32, 33, 25, 14};
bool relayStates[8] = {false, false, false, false, false, false, false, false};

unsigned long lastPollMs = 0;
const unsigned long POLL_INTERVAL_MS = 3000;

void applyRelay(int index, bool on) {
  if (index < 0 || index >= 8) return;
  relayStates[index] = on;
  digitalWrite(relays[index], on ? LOW : HIGH);
  Serial.println("Relay " + String(index + 1) + (on ? " ON" : " OFF"));
}

void setAll(bool on) {
  for (int i = 0; i < 8; i++) {
    applyRelay(i, on);
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

String commandUrl() {
  return String(RELAY_COMMAND_URL) + "?device_id=" + String(DEVICE_ID);
}

String relayStatusJson() {
  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"relays\":{";
  for (int i = 0; i < 8; i++) {
    if (i > 0) payload += ",";
    payload += "\"r" + String(i + 1) + "\":";
    payload += relayStates[i] ? "true" : "false";
  }
  payload += "}}";
  return payload;
}

void postRelayStatus() {
  if (!ENABLE_BACKEND_SYNC) return;
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.begin(client, RELAY_STATUS_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", SHARED_ESP32_API_KEY);

  String payload = relayStatusJson();
  int code = http.POST(payload);

  Serial.print("Relay status POST: ");
  Serial.println(code);
  if (code > 0) {
    Serial.println(http.getString());
  }

  http.end();
}

void applyCommandToken(String token) {
  token.trim();
  token.toLowerCase();
  if (token.length() < 3) return;

  for (int relayNumber = 1; relayNumber <= 8; relayNumber++) {
    String onToken = String(relayNumber) + "on";
    String offToken = String(relayNumber) + "off";

    if (token == onToken) {
      applyRelay(relayNumber - 1, true);
      return;
    }

    if (token == offToken) {
      applyRelay(relayNumber - 1, false);
      return;
    }
  }
}

void applyCommandText(String commands) {
  commands.trim();
  if (!commands.length()) return;

  Serial.print("Backend command: ");
  Serial.println(commands);

  int start = 0;
  while (start < commands.length()) {
    int space = commands.indexOf(' ', start);
    if (space == -1) space = commands.length();
    applyCommandToken(commands.substring(start, space));
    start = space + 1;
  }

  postRelayStatus();
}

void pollBackendRelayCommands() {
  if (!ENABLE_BACKEND_SYNC) return;
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.begin(client, commandUrl());
  http.addHeader("X-API-Key", SHARED_ESP32_API_KEY);

  int code = http.GET();
  Serial.print("Relay command GET: ");
  Serial.println(code);

  if (code == 200) {
    applyCommandText(http.getString());
  } else if (code > 0) {
    Serial.println(http.getString());
  }

  http.end();
}

String localStatusJson() {
  String payload = "{";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"relays\":{";
  for (int i = 0; i < 8; i++) {
    if (i > 0) payload += ",";
    payload += "\"r" + String(i + 1) + "\":";
    payload += relayStates[i] ? "true" : "false";
  }
  payload += "}}";
  return payload;
}

void sendLocalResponse(WiFiClient& client, String body, String contentType = "text/plain") {
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: " + contentType);
  client.println("Access-Control-Allow-Origin: *");
  client.println("Access-Control-Allow-Methods: GET, OPTIONS");
  client.println("Access-Control-Allow-Headers: Content-Type");
  client.println("Connection: close");
  client.println();
  client.println(body);
}

void handleLocalHttpControl() {
  WiFiClient client = server.available();
  if (!client) return;

  String request = client.readStringUntil('\r');
  client.flush();

  request.toLowerCase();
  Serial.println("Local request: " + request);

  if (request.indexOf("options ") == 0) {
    sendLocalResponse(client, "OK");
    return;
  }

  bool changed = false;

  if (request.indexOf("get /on") != -1 || request.indexOf("get /pump-on") != -1) {
    applyRelay(0, true);
    changed = true;
  }

  if (request.indexOf("get /off") != -1 || request.indexOf("get /pump-off") != -1) {
    applyRelay(0, false);
    changed = true;
  }

  for (int i = 0; i < 8; i++) {
    String onCmd = "get /" + String(i + 1) + "on";
    String offCmd = "get /" + String(i + 1) + "off";

    if (request.indexOf(onCmd) != -1) {
      applyRelay(i, true);
      changed = true;
    }

    if (request.indexOf(offCmd) != -1) {
      applyRelay(i, false);
      changed = true;
    }
  }

  if (request.indexOf("get /allon") != -1) {
    setAll(true);
    changed = true;
  }

  if (request.indexOf("get /alloff") != -1) {
    setAll(false);
    changed = true;
  }

  if (changed) {
    postRelayStatus();
  }

  if (request.indexOf("get /status") != -1) {
    sendLocalResponse(client, localStatusJson(), "application/json");
    return;
  }

  String response = "pump1=";
  response += relayStates[0] ? "on" : "off";
  response += "\npump2=";
  response += relayStates[1] ? "on" : "off";
  sendLocalResponse(client, response);
}

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < 8; i++) {
    pinMode(relays[i], OUTPUT);
    digitalWrite(relays[i], HIGH); // OFF for active LOW relay module.
  }

  connectWiFi();
  server.begin();
  Serial.println("Local relay server started");
  Serial.print("Open this in browser: http://");
  Serial.println(WiFi.localIP());

  pollBackendRelayCommands();
}

void loop() {
  connectWiFi();
  handleLocalHttpControl();

  if (millis() - lastPollMs >= POLL_INTERVAL_MS) {
    lastPollMs = millis();
    pollBackendRelayCommands();
  }
}
