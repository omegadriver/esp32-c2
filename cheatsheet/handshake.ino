// ════════════════════════════════════════════
// Handshake - Implementação de um protocolo de handshake simples
// ════════════════════════════════════════════

void handshake() {
    if (!Serial.available()) return;
    
    Serial.setTimeout(10000);

    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line == "Hello?") {
        Serial.println("Hi!");
    } else {
        Serial.println("Unknown message");
    }
    return;
}

void setup() {
    Serial.begin(9600);
}

void loop() {
    handshake();
}
