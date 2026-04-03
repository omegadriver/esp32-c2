#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid     = "wifi";
const char* password = "pass";
const char* baseUrl      = "url";

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);

  // avisa o Python que está pronto
  Serial.println("PRONTO");
}

void loop() {
  if (Serial.available()) {
    String heartbeat = Serial.readStringUntil('\n');
    heartbeat.trim();

    if (heartbeat.startsWith("//")) {
      String url = String(baseUrl) + "?id=" + heartbeat;

      HTTPClient http;
      http.begin(url);
      int code = http.GET();

      if (code > 0) {
        Serial.printf("HTTP %d - %s\n", code);
      } else {
        Serial.printf("Erro: %s\n", http.errorToString(code).c_str());
      }

      http.end();
    }
  }
}
