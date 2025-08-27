// RoverControl_MotorsServos_Neo.ino
// - L298N senza ENA/ENB con pin ottimizzati per coesistenza Servo
// - 4 Servi (Base, Spalla, Gomito, Pinza)
// - NeoPixel su D3 (già esistente)

#include <Adafruit_NeoPixel.h>
#include <Servo.h>

// ------------------ PIN MOTORI (L298N) ------------------
// Sinistra: due PWM (D5, D6) — Destra: 1x LOW (D8) + 1x PWM (D11)
const int L_A = 5;   // sinistro, direz A (PWM per AVANTI)
const int L_B = 6;   // sinistro, direz B (PWM per INDIETRO)
const int R_A = 8;   // destro, direz A (sempre LOW/HIGH)
const int R_B = 11;  // destro, direz B (PWM in entrambe le direzioni)

// Se dopo i cambi cablaggio noti ancora inversioni, puoi cambiare questi flag:
bool INVERT_FORWARD  = false; // inverte avanti<->indietro
bool INVERT_TURN     = false; // inverte sinistra<->destra

// ------------------ LED STRIP ------------------
#define LED_PIN    3
#define LED_COUNT  9
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
uint8_t ledR=255, ledG=180, ledB=100;
uint8_t ledBrightness=60;
bool     leds_are_on=false;

// ------------------ SERVI ------------------
const int SERVO_PINS[4] = {4, 7, A0, A1}; // Base, Spalla, Gomito, Pinza
Servo servos[4];
bool  servos_attached = false;

// Angoli correnti e HOME (puoi cambiarli dopo i test)
int servoAngles[4]   = {90, 90, 90, 90};
int servoHome[4]     = {90, 90, 90, 90};

// ------------------ WATCHDOG ------------------
const unsigned long WATCHDOG_MS = 1000;
unsigned long lastCmdMs = 0;

// =====================================================
// SETUP
// =====================================================
void setup() {
  // Motori
  pinMode(L_A, OUTPUT); pinMode(L_B, OUTPUT);
  pinMode(R_A, OUTPUT); pinMode(R_B, OUTPUT);
  stopMotors();

  // LED
  strip.begin();
  strip.setBrightness(ledBrightness);
  ledsOff();

  // Servi (non attacco subito, puoi usare SV ATTACH)
  // attachServos(); // se vuoi attaccarli all'avvio, scommenta

  Serial.begin(115200);
  while (!Serial) {}
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
  if (millis() - lastCmdMs > WATCHDOG_MS) {
    stopMotors();
  }
}

// =====================================================
// PARSER COMANDI
// =====================================================
void handleCommand(const String &cmd) {
  if (cmd.length() == 0) return;

  if (cmd.startsWith("LED")) { handleLED(cmd); return; }
  if (cmd.startsWith("SV"))  { handleServo(cmd); return; }

  // Motori
  char c = cmd.charAt(0);
  int spd = 0;
  if (cmd.length() > 1) spd = constrain(cmd.substring(1).toInt(), 0, 255);

  // Applica inversioni richieste
  char op = c;
  if (INVERT_FORWARD && (c=='F' || c=='B')) op = (c=='F') ? 'B' : 'F';
  if (INVERT_TURN    && (c=='L' || c=='R')) op = (c=='L') ? 'R' : 'L';

  switch (op) {
    case 'F': forward(spd);  Serial.println("OK F"); break;
    case 'B': backward(spd); Serial.println("OK B"); break;
    case 'L': turnLeft(spd); Serial.println("OK L"); break;
    case 'R': turnRight(spd);Serial.println("OK R"); break;
    case 'S': stopMotors();  Serial.println("OK S"); break;
    default:  Serial.println("ERR");
  }
}

// =====================================================
// MOTORS  (L298N: PWM su un pin, LOW sull'altro)
// =====================================================

void forward(int spd) {
  // Sinistra AVANTI: L_A PWM, L_B LOW
  analogWrite(L_A, spd); digitalWrite(L_B, LOW);
  // Destra AVANTI: R_A LOW, R_B PWM
  digitalWrite(R_A, LOW); analogWrite(R_B, spd);
}

void backward(int spd) {
  // Sinistra INDIETRO: L_A LOW, L_B PWM
  digitalWrite(L_A, LOW); analogWrite(L_B, spd);
  // Destra INDIETRO: R_A HIGH, R_B PWM (inverte corrente)
  digitalWrite(R_A, HIGH); analogWrite(R_B, spd);
}

void turnLeft(int spd) {
  // sinistra indietro, destra avanti
  digitalWrite(L_A, LOW); analogWrite(L_B, spd);
  digitalWrite(R_A, LOW); analogWrite(R_B, spd);
}

void turnRight(int spd) {
  // sinistra avanti, destra indietro
  analogWrite(L_A, spd); digitalWrite(L_B, LOW);
  digitalWrite(R_A, HIGH); analogWrite(R_B, spd);
}

void stopMotors() {
  analogWrite(L_A, 0); analogWrite(L_B, 0);
  analogWrite(R_B, 0);
  digitalWrite(L_A, LOW); digitalWrite(L_B, LOW);
  digitalWrite(R_A, LOW); // freno “coast” lato R_B già 0
}

// =====================================================
// LEDS
// =====================================================
void ledsApply(bool on) {
  strip.setBrightness(ledBrightness);
  for (int i=0;i<LED_COUNT;i++) {
    if (on) strip.setPixelColor(i, strip.Color(ledR, ledG, ledB));
    else    strip.setPixelColor(i, 0);
  }
  strip.show();
  leds_are_on = on;
}
void ledsOn()  { ledsApply(true); }
void ledsOff() { ledsApply(false); }

void handleLED(const String &cmd) {
  if (cmd.equalsIgnoreCase("LED ON"))  { ledsOn();  Serial.println("OK LED ON");  return; }
  if (cmd.equalsIgnoreCase("LED OFF")) { ledsOff(); Serial.println("OK LED OFF"); return; }

  if (cmd.startsWith("LED RGB")) {
    int i1 = cmd.indexOf(' ', 3);
    int i2 = cmd.indexOf(' ', i1+1);
    if (i2 > 0) {
      String rest = cmd.substring(i2+1); rest.trim();
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
    Serial.println("ERR LED RGB"); return;
  }

  if (cmd.startsWith("LED BR")) {
    int i = cmd.lastIndexOf(' ');
    if (i>0) {
      ledBrightness = constrain(cmd.substring(i+1).toInt(), 0, 255);
      ledsApply(leds_are_on);
      Serial.println("OK LED BR");
      return;
    }
    Serial.println("ERR LED BR"); return;
  }

  Serial.println("ERR LED");
}

// =====================================================
// SERVI
// =====================================================
void attachServos(){
  if (servos_attached) return;
  for (int i=0;i<4;i++){
    servos[i].attach(SERVO_PINS[i]);
    servos[i].write(constrain(servoAngles[i], 0, 180));
  }
  servos_attached = true;
}
void detachServos(){
  if (!servos_attached) return;
  for (int i=0;i<4;i++) servos[i].detach();
  servos_attached = false;
}
void setServo(int idx, int ang){
  if (idx<0 || idx>3) return;
  servoAngles[idx] = constrain(ang, 0, 180);
  if (servos_attached) servos[idx].write(servoAngles[idx]);
}
void goHome(){
  for (int i=0;i<4;i++){
    servoAngles[i] = constrain(servoHome[i], 0, 180);
    if (servos_attached) servos[i].write(servoAngles[i]);
  }
}

void handleServo(const String &cmd){
  if (cmd.equalsIgnoreCase("SV ATTACH")) { attachServos(); Serial.println("OK SV ATTACH"); return; }
  if (cmd.equalsIgnoreCase("SV DETACH")) { detachServos(); Serial.println("OK SV DETACH"); return; }
  if (cmd.equalsIgnoreCase("SV HOME"))   { goHome();      Serial.println("OK SV HOME");   return; }

  // "SV i a"
  // es: "SV 2 135"
  int sp1 = cmd.indexOf(' ');
  int sp2 = cmd.lastIndexOf(' ');
  if (sp1>0 && sp2>sp1) {
    int idx = cmd.substring(sp1+1, sp2).toInt();
    int ang = cmd.substring(sp2+1).toInt();
    setServo(idx, ang);
    Serial.print("OK SV "); Serial.print(idx); Serial.print(' '); Serial.println(ang);
    return;
  }

  Serial.println("ERR SV");
}
