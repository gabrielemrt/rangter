// RoverControl_NoEN_Neo.ino
// L298N con N1..N4 (PWM sugli IN) + strip NeoPixel su D3 (9 LED)

#include <Adafruit_NeoPixel.h>

// ---- MOTORS (N1..N4) ----
const int L1 = 8;   // N1 sinistro
const int L2 = 9;   // N2 sinistro
const int R1 = 10;  // N3 destro
const int R2 = 11;  // N4 destro

// ---- LED STRIP ----
#define LED_PIN   3
#define LED_COUNT 9
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
uint8_t ledR=255, ledG=180, ledB=100;  // colore ON (bianco caldo)
bool leds_are_on = false;

const unsigned long WATCHDOG_MS = 1000;
unsigned long lastCmdMs = 0;

void setup() {
  pinMode(L1, OUTPUT); pinMode(L2, OUTPUT);
  pinMode(R1, OUTPUT); pinMode(R2, OUTPUT);
  stopMotors();

  strip.begin();
  strip.setBrightness(60); // regola a piacere (0-255)
  ledsOff();

  Serial.begin(115200);
  while (!Serial) {}
  Serial.println("READY");
  lastCmdMs = millis();
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    handleCommand(line);
    lastCmdMs = millis();
  }
  if (millis() - lastCmdMs > WATCHDOG_MS) {
    stopMotors();
  }
}

void handleCommand(const String &cmd) {
  if (cmd.length() == 0) return;

  // ---- LED commands ----
  if (cmd.startsWith("LED")) {
    handleLED(cmd);
    return;
  }

  // ---- Motor commands ----
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

// ================== MOTORS ==================
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

// *** ROTAZIONI INVERTITE come richiesto ***
// Prima "L" faceva destra e "R" sinistra: le scambio qui.
void turnLeft(int spd) {
  // per girare a SINISTRA: sinistro avanti, destro indietro
  analogWrite(L1, spd);  digitalWrite(L2, LOW); // sinistro avanti
  digitalWrite(R1, LOW); analogWrite(R2, spd);  // destro indietro
}

void turnRight(int spd) {
  // per girare a DESTRA: sinistro indietro, destro avanti
  digitalWrite(L1, LOW); analogWrite(L2, spd);  // sinistro indietro
  analogWrite(R1, spd);  digitalWrite(R2, LOW); // destro avanti
}

void stopMotors() {
  analogWrite(L1, 0); analogWrite(L2, 0);
  analogWrite(R1, 0); analogWrite(R2, 0);
  digitalWrite(L1, LOW); digitalWrite(L2, LOW);
  digitalWrite(R1, LOW); digitalWrite(R2, LOW);
}

// ================== LEDS ==================
void ledsApply(bool on) {
  for (int i=0;i<LED_COUNT;i++) {
    if (on) strip.setPixelColor(i, strip.Color(ledR, ledG, ledB));
    else    strip.setPixelColor(i, 0);
  }
  strip.show();
  leds_are_on = on;
}

void ledsOn()  { ledsApply(true); }
void ledsOff() { ledsApply(false); }

// LED command parser:
// "LED ON"  -> accende (colore predefinito)
// "LED OFF" -> spegne
// "LED R G B" -> setta colore (0-255) e ACCENDE
void handleLED(const String &cmd) {
  if (cmd.equalsIgnoreCase("LED ON")) {
    ledsOn(); Serial.println("OK LED ON"); return;
  }
  if (cmd.equalsIgnoreCase("LED OFF")) {
    ledsOff(); Serial.println("OK LED OFF"); return;
  }

  // prova parse "LED r g b"
  int firstSpace = cmd.indexOf(' ');
  if (firstSpace > 0) {
    String rest = cmd.substring(firstSpace+1); rest.trim();
    int a=0,b=0,c=0;
    int p1 = rest.indexOf(' ');
    int p2 = rest.lastIndexOf(' ');
    if (p1>0 && p2>p1) {
      a = constrain(rest.substring(0,p1).toInt(), 0, 255);
      b = constrain(rest.substring(p1+1,p2).toInt(), 0, 255);
      c = constrain(rest.substring(p2+1).toInt(), 0, 255);
      ledR=a; ledG=b; ledB=c;
      ledsOn();
      Serial.println("OK LED RGB");
      return;
    }
  }
  Serial.println("ERR LED");
}
