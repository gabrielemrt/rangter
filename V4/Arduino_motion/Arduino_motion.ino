// RoverControl_NoEN_Neo.ino
// L298N (solo N1..N4, senza ENA/ENB) + strip NeoPixel su D3 (9 LED).
// Protocollo seriale: F n, B n, L n, R n, S, LED ON/OFF, LED RGB r g b, LED BR n

#include <Adafruit_NeoPixel.h>

// ------------------ PIN MOTORI (L298N) ------------------
// Assunzione: N1,N2 = canale sinistro | N3,N4 = canale destro
// Collega N1->D8, N2->D9, N3->D10, N4->D11
const int L1 = 8;   // N1 sinistro
const int L2 = 9;   // N2 sinistro
const int R1 = 10;  // N3 destro
const int R2 = 11;  // N4 destro

// ------------------ LED STRIP ------------------
#define LED_PIN    3
#define LED_COUNT  9
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

uint8_t ledR = 255, ledG = 180, ledB = 100; // colore “bianco caldo”
uint8_t ledBrightness = 60;                  // 0–255
bool     leds_are_on = false;

// ------------------ WATCHDOG MOTORI ------------------
const unsigned long WATCHDOG_MS = 1000; // se non arrivano comandi, stop
unsigned long lastCmdMs = 0;

// =====================================================
// SETUP
// =====================================================
void setup() {
  pinMode(L1, OUTPUT); pinMode(L2, OUTPUT);
  pinMode(R1, OUTPUT); pinMode(R2, OUTPUT);
  stopMotors();

  strip.begin();
  strip.setBrightness(ledBrightness);
  ledsOff();

  Serial.begin(115200);
  while (!Serial) { /* attende seriale su alcuni cloni */ }
  Serial.println("READY");
  lastCmdMs = millis();
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    handleCommand(line);
    lastCmdMs = millis();
  }

  // watchdog sicurezza
  if (millis() - lastCmdMs > WATCHDOG_MS) {
    stopMotors();
  }
}

// =====================================================
// PARSER COMANDI
// =====================================================
void handleCommand(const String &cmd) {
  if (cmd.length() == 0) return;

  // --- LED commands ---
  if (cmd.startsWith("LED")) { handleLED(cmd); return; }

  // --- Motor commands ---
  char c = cmd.charAt(0);
  int spd = 0;
  if (cmd.length() > 1) spd = constrain(cmd.substring(1).toInt(), 0, 255);

  switch (c) {
    case 'F': forward(spd);  Serial.println("OK F"); break;
    case 'B': backward(spd); Serial.println("OK B"); break;
    case 'L': turnLeft(spd); Serial.println("OK L"); break;
    case 'R': turnRight(spd);Serial.println("OK R"); break;
    case 'S': stopMotors();  Serial.println("OK S"); break;
    default:  Serial.println("ERR");
  }
}

// =====================================================
// MOTORS (PWM direttamente sugli IN del ponte H)
// =====================================================

// Avanti: PWM su L1/R1, L2/R2 LOW
void forward(int spd) {
  analogWrite(L1, spd); digitalWrite(L2, LOW);
  analogWrite(R1, spd); digitalWrite(R2, LOW);
}

// Indietro: PWM su L2/R2, L1/R1 LOW
void backward(int spd) {
  digitalWrite(L1, LOW); analogWrite(L2, spd);
  digitalWrite(R1, LOW); analogWrite(R2, spd);
}

// Rotazioni (corrette: L = sinistra, R = destra)
void turnLeft(int spd) {
  // sinistro avanti, destro indietro
  analogWrite(L1, spd);  digitalWrite(L2, LOW); // sinistro avanti
  digitalWrite(R1, LOW); analogWrite(R2, spd);  // destro indietro
}

void turnRight(int spd) {
  // sinistro indietro, destro avanti
  digitalWrite(L1, LOW); analogWrite(L2, spd);  // sinistro indietro
  analogWrite(R1, spd);  digitalWrite(R2, LOW); // destro avanti
}

void stopMotors() {
  analogWrite(L1, 0); analogWrite(L2, 0);
  analogWrite(R1, 0); analogWrite(R2, 0);
  // “coast”: tutti LOW. Per freno attivo puoi impostare coppie opposte.
  digitalWrite(L1, LOW); digitalWrite(L2, LOW);
  digitalWrite(R1, LOW); digitalWrite(R2, LOW);
}

// =====================================================
// LEDS
// =====================================================
void ledsApply(bool on) {
  strip.setBrightness(ledBrightness); // applica brightness corrente
  for (int i=0; i<LED_COUNT; i++) {
    if (on) strip.setPixelColor(i, strip.Color(ledR, ledG, ledB));
    else    strip.setPixelColor(i, 0);
  }
  strip.show();
  leds_are_on = on;
}

void ledsOn()  { ledsApply(true); }
void ledsOff() { ledsApply(false); }

// Parser LED:
//  - "LED ON" / "LED OFF"
//  - "LED RGB r g b" (accende con quel colore)
//  - "LED BR n" (0–255) mantiene stato ON/OFF
void handleLED(const String &cmd) {
  if (cmd.equalsIgnoreCase("LED ON"))  { ledsOn();  Serial.println("OK LED ON");  return; }
  if (cmd.equalsIgnoreCase("LED OFF")) { ledsOff(); Serial.println("OK LED OFF"); return; }

  if (cmd.startsWith("LED RGB")) {
    // formato: LED RGB r g b
    int i1 = cmd.indexOf(' ', 3);          // dopo "LED"
    int i2 = cmd.indexOf(' ', i1 + 1);     // dopo "RGB"
    if (i2 > 0) {
      String rest = cmd.substring(i2 + 1); rest.trim();
      int a=0, b=0, c=0;
      int p1 = rest.indexOf(' ');
      int p2 = rest.lastIndexOf(' ');
      if (p1 > 0 && p2 > p1) {
        a = constrain(rest.substring(0, p1).toInt(), 0, 255);
        b = constrain(rest.substring(p1 + 1, p2).toInt(), 0, 255);
        c = constrain(rest.substring(p2 + 1).toInt(), 0, 255);
        ledR = a; ledG = b; ledB = c;
        ledsOn();
        Serial.println("OK LED RGB");
        return;
      }
    }
    Serial.println("ERR LED RGB");
    return;
  }

  if (cmd.startsWith("LED BR")) {
    // formato: LED BR n
    int i = cmd.lastIndexOf(' ');
    if (i > 0) {
      ledBrightness = constrain(cmd.substring(i + 1).toInt(), 0, 255);
      ledsApply(leds_are_on);
      Serial.println("OK LED BR");
      return;
    }
    Serial.println("ERR LED BR");
    return;
  }

  Serial.println("ERR LED");
}
