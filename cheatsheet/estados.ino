// ════════════════════════════════════════════
// FSM - Sistema simples de estados 
// ════════════════════════════════════════════
// Implementação de uma Máquina de Estados Finita
// (FSM - Finite State Machine)
// Cicla por 4 estados sequenciais, cada um 
// executando uma ação específica
// ════════════════════════════════════════════

// DEFINE ESTADOS
// Enum que representa os 4 estados possíveis
enum State {PRIMEIRO, SEGUNDO, TERCEIRO, QUARTO};

// VARIÁVEL GLOBAL DE ESTADO
// Rastreia qual estado a FSM está no momento
State state = PRIMEIRO;

// ════════════════════════════════════════════
// FUNÇÕES DOS ESTADOS
// ════════════════════════════════════════════

// Estado 1: Imprime mensagem e transiciona
void primeiro() {
    Serial.println("Primeiro estado");
    delay(1000);
    state = SEGUNDO;    // Transição para o próximo estado
}

// Estado 2: Imprime mensagem e transiciona
void segundo() {
    Serial.println("Segundo estado");
    delay(1000);
    state = TERCEIRO;   // Transição para o próximo estado
}

// Estado 3: Imprime mensagem e transiciona
void terceiro() {
    Serial.println("Terceiro estado");
    delay(1000);
    state = QUARTO; // Transição para o próximo estado
}

// Estado 4: Imprime mensagem e reinicia ciclo
void quarto() {
    Serial.println("Quarto estado");
    delay(1000);
    Serial.println("Fim do ciclo, voltando para o primeiro estado...");
    state = PRIMEIRO; // Reinicia o ciclo para o primeiro estado
}

// ════════════════════════════════════════════
// SETUP E LOOP PRINCIPAL
// ════════════════════════════════════════════

void setup() {
    Serial.begin(9600);
}

void loop() {
    switch (state) {
        case PRIMEIRO:
            primeiro();
            break;
        case SEGUNDO:
            segundo();
            break;
        case TERCEIRO:
            terceiro();
            break;
        case QUARTO:
            quarto();
            break;
    }
}
