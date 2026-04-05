#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Arduino_JSON.h>

// ── configuração ─────────────────────────────────────────────────────
const char* WIFI_SSID         = "SSID";
const char* WIFI_PASSWORD     = "PASSWORD";
const char* SERVER_URL        = "SERVER_URL";
const char* DEVICE_ID         = "DEVICE_ID";

const int   SERIAL_BAUD       = 115200;
const int   POLL_DELAY_MS     = 3000;
const int   RESULT_TIMEOUT_MS = 30000;

// ── FSM ──────────────────────────────────────────────────────────────
enum Phase {
    CONNECT,
    FETCH_COMMAND,
    FORWARD_TO_CLIENT,
    WAIT_RESULT,
    FORWARD_TO_SERVER,
};

// ── contexto ─────────────────────────────────────────────────────────
struct Context {
    String command_json = "";
    String result_json  = "";
};

// ── handlers ─────────────────────────────────────────────────────────

Phase handle_connect() {
    Serial.println("[esp32] conectando ao Wi-Fi...");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    delay(5000);

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[esp32] falha no Wi-Fi, tentando novamente...");
        delay(2000);
        return CONNECT;
    }

    Serial.print("[esp32] conectado: ");
    Serial.println(WiFi.localIP());
    return FETCH_COMMAND;
}

Phase handle_fetch_command(Context& ctx) {
    if (WiFi.status() != WL_CONNECTED) return CONNECT;

    HTTPClient http;
    http.begin(String(SERVER_URL) + "/command?deviceid=" + DEVICE_ID);
    int code = http.GET();

    if (code == 200) {
        String body = http.getString();
        http.end();

        JSONVar doc = JSON.parse(body);
        if (JSON.typeof(doc) != "undefined" && strcmp((const char*)doc["type"], "command") == 0) {
            ctx.command_json = body;
            Serial.println("[esp32] comando recebido do servidor: " + String((const char*)doc["command"]));
            return FORWARD_TO_CLIENT;
        }
    }

    http.end();
    Serial.println("[esp32] sem comando pendente, aguardando...");
    delay(POLL_DELAY_MS);
    return FETCH_COMMAND;
}

Phase handle_forward_to_client(Context& ctx) {
    Serial.println(ctx.command_json);
    Serial.flush();
    Serial.println("[esp32] comando enviado ao client via serial");
    return WAIT_RESULT;
}

Phase handle_wait_result(Context& ctx) {
    Serial.println("[esp32] aguardando resultado do client...");
    unsigned long start = millis();

    while (millis() - start < RESULT_TIMEOUT_MS) {
        if (Serial.available()) {
            String line = Serial.readStringUntil('\n');
            line.trim();
            if (line.length() == 0) continue;

            JSONVar doc = JSON.parse(line);
            if (JSON.typeof(doc) != "undefined" && strcmp((const char*)doc["type"], "command_result") == 0) {
                ctx.result_json = line;
                Serial.println("[esp32] resultado recebido do client");
                return FORWARD_TO_SERVER;
            }
        }
        delay(10);
    }

    Serial.println("[esp32] timeout aguardando client, resetando...");
    ctx = Context();
    return CONNECT;
}

Phase handle_forward_to_server(Context& ctx) {
    if (WiFi.status() != WL_CONNECTED) return CONNECT;

    HTTPClient http;
    http.begin(String(SERVER_URL) + "/result");
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(ctx.result_json);
    http.end();

    Serial.printf("[esp32] resultado enviado: HTTP %d\n", code);
    ctx = Context();
    return FETCH_COMMAND;
}

// ── setup + loop ──────────────────────────────────────────────────────

Context ctx;
Phase   phase = CONNECT;

void setup() {
    Serial.begin(115200);
    Serial.println("[esp32] iniciando...");
}

void loop() {
    switch (phase) {
        case CONNECT:           phase = handle_connect();              break;
        case FETCH_COMMAND:     phase = handle_fetch_command(ctx);     break;
        case FORWARD_TO_CLIENT: phase = handle_forward_to_client(ctx); break;
        case WAIT_RESULT:       phase = handle_wait_result(ctx);       break;
        case FORWARD_TO_SERVER: phase = handle_forward_to_server(ctx); break;
    }
}
