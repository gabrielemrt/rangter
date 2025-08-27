// RoverControl_Safe.ino
// Fail-safe: ARM/DISARM + Heartbeat HB + TTL comandi + E-STOP D2
// Motori L298N senza ENA/ENB, 4 servi, NeoPixel su D3

#include <Adafruit_NeoPixel.h>
#include <Servo.h>

// --------- PINS MOTORI (vedi cablaggio precedente) ---------
const int L_A = 5;   // sinistro AVANTI PWM
const int L_B = 6;   // sinistro INDIETRO PWM
const int R_A = 8;   // destro linea logica
const int R_B = 11;  // destro PWM

bool INVERT_FORWARD  = false;
bool INVERT_TURN     = false;

// --------- E-STOP & SAFETY ---------
const int ESTOP_PIN = 2; // pulsante verso GND, INPUT_PULLUP
const unsigned long HEARTBEAT_TIMEOUT_MS = 400;  // se manca HB -> disarma
const unsigned long MOTION_TTL_MS        = 350;  // se non rinnovi movimento -> stop
const unsigned long WATCHDOG_MS          = 1000; // extra guard

bool armed = false;
unsigned long lastHBms = 0;
unsigned long lastMotionMs = 0;

// --------- LED STRIP ---------
#define LED_PIN    3
#define LED_COUNT  9
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
uint8_t ledR=255, ledG=180, ledB=100;
uint8_t ledBrightness=60;
bool     leds_are_on=false;

// --------- SERVI ---------
const int SERVO_PINS[4] = {4, 7, A0, A1}; // Base, Spalla, Gomito, Pinza
Servo servos[4];
bool  servos_attached = false;
int   servoAngles[4]  = {90, 90, 90, 90};
int   servoHome[4]    = {90, 90, 90, 90};

// --------- SETUP ---------
void setup() {
  pinMode(L_A, OUTPUT); pinMode(L_B, OUTPUT);
  pinMode(R_A, OUTPUT); pinMode(R_B, OUTPUT);
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  stopMotors();

  strip.begin(); strip.setBrightness(ledBrightness); ledsOff();

  Serial.begin(115200);
  while (!Serial) {}
  Serial.println("READY");
  lastHBms = millis();
}

// --------- LOOP ---------
void loop() {
  // Serial commands
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    handleCommand(line);
  }

  unsigned long now = millis();

  // E-STOP o heartbeat mancante -> STOP & DISARM
  if (digitalRead(ESTOP_PIN) == LOW || (armed && (now - lastHBms > HEARTBEAT_TIMEOUT_MS))) {
    stopMotors();
    armed = false;
  }

  // Comando movimento scaduto -> STOP
  if (now - lastMotionMs > MOTION_TTL_MS) {
    stopMotors();
  }

  // Extra watchdog
  static unsigned long lastCmdTouch = now;
  if (Serial.available()) lastCmdTouch = now;
  if (now - lastCmdTouch > WATCHDOG_MS) stopMotors();
}

// --------- PARSER ---------
void handleCommand(const String &cmd) {
  if (cmd.length()==0) return;

  // Safety
  if (cmd.equalsIgnoreCase("ARM"))   { armed = true; lastHBms = millis(); Serial.println("OK ARM"); return; }
  if (cmd.equalsIgnoreCase("DISARM")){ armed = false; stopMotors(); Serial.println("OK DISARM"); return; }
  if (cmd.equalsIgnoreCase("HB"))    { lastHBms = millis(); return; } // nessun echo necessario

  // LED / SERVO
  if (cmd.startsWith("LED")) { handleLED(cmd); return; }
  if (cmd.startsWith("SV"))  { handleServo(cmd); return; }

  // Motori richiedono armed==true e HB fresco
  unsigned long now = millis();
  if (!armed || (now - lastHBms > HEARTBEAT_TIMEOUT_MS)) {
    // ignora comandi movimento se non armato
    if (cmd=="S") stopMotors(); // consenti sempre STOP
    return;
  }

  char c = cmd.charAt(0);
  int spd = 0;
  if (cmd.length()>1) spd = constrain(cmd.substring(1).toInt(), 0, 255);

  char op = c;
  if (INVERT_FORWARD && (c=='F'||c=='B')) op = (c=='F')?'B':'F';
  if (INVERT_TURN    && (c=='L'||c=='R')) op = (c=='L')?'R':'L';

  switch (op) {
    case 'F': forward(spd);  Serial.println("OK F"); lastMotionMs = now; break;
    case 'B': backward(spd); Serial.println("OK B"); lastMotionMs = now; break;
    case 'L': turnLeft(spd); Serial.println("OK L"); lastMotionMs = now; break;
    case 'R': turnRight(spd);Serial.println("OK R"); lastMotionMs = now; break;
    case 'S': stopMotors();  Serial.println("OK S"); lastMotionMs = now; break;
    default:  Serial.println("ERR");
  }
}

// --------- MOTORS ---------
void forward(int spd) {
  analogWrite(L_A, spd); digitalWrite(L_B, LOW);
  digitalWrite(R_A, LOW); analogWrite(R_B, spd);
}
void backward(int spd) {
  digitalWrite(L_A, LOW); analogWrite(L_B, spd);
  digitalWrite(R_A, HIGH); analogWrite(R_B, spd);
}
void turnLeft(int spd) {
  digitalWrite(L_A, LOW); analogWrite(L_B, spd);
  digitalWrite(R_A, LOW); analogWrite(R_B, spd);
}
void turnRight(int spd) {
  analogWrite(L_A, spd); digitalWrite(L_B, LOW);
  digitalWrite(R_A, HIGH); analogWrite(R_B, spd);
}
void stopMotors() {
  analogWrite(L_A,0); analogWrite(L_B,0); analogWrite(R_B,0);
  digitalWrite(L_A,LOW); digitalWrite(L_B,LOW); digitalWrite(R_A,LOW);
}

// --------- LED ---------
void ledsApply(bool on){
  strip.setBrightness(ledBrightness);
  for(int i=0;i<LED_COUNT;i++) strip.setPixelColor(i, on ? strip.Color(ledR,ledG,ledB) : 0);
  strip.show();
  leds_are_on = on;
}
void ledsOn(){ ledsApply(true); }
void ledsOff(){ ledsApply(false); }

void handleLED(const String &cmd){
  if (cmd.equalsIgnoreCase("LED ON"))  { ledsOn();  Serial.println("OK LED ON");  return; }
  if (cmd.equalsIgnoreCase("LED OFF")) { ledsOff(); Serial.println("OK LED OFF"); return; }
  if (cmd.startsWith("LED RGB")){
    int i1=cmd.indexOf(' ',3), i2=cmd.indexOf(' ',i1+1);
    if (i2>0){
      String rest=cmd.substring(i2+1); rest.trim();
      int p1=rest.indexOf(' '), p2=rest.lastIndexOf(' ');
      if (p1>0 && p2>p1){
        ledR=constrain(rest.substring(0,p1).toInt(),0,255);
        ledG=constrain(rest.substring(p1+1,p2).toInt(),0,255);
        ledB=constrain(rest.substring(p2+1).toInt(),0,255);
        ledsOn(); Serial.println("OK LED RGB"); return;
      }
    }
    Serial.println("ERR LED RGB"); return;
  }
  if (cmd.startsWith("LED BR")){
    int i=cmd.lastIndexOf(' ');
    if (i>0){ ledBrightness=constrain(cmd.substring(i+1).toInt(),0,255); ledsApply(leds_are_on); Serial.println("OK LED BR"); return; }
    Serial.println("ERR LED BR"); return;
  }
  Serial.println("ERR LED");
}

// --------- SERVI ---------
void attachServos(){ if (servos_attached) return; for(int i=0;i<4;i++){ servos[i].attach(SERVO_PINS[i]); servos[i].write(constrain(servoAngles[i],0,180)); } servos_attached=true; }
void detachServos(){ if (!servos_attached) return; for(int i=0;i<4;i++) servos[i].detach(); servos_attached=false; }
void setServo(int idx,int ang){ if (idx<0||idx>3) return; servoAngles[idx]=constrain(ang,0,180); if (servos_attached) servos[idx].write(servoAngles[idx]); }
void goHome(){ for(int i=0;i<4;i++){ servoAngles[i]=constrain(servoHome[i],0,180); if (servos_attached) servos[i].write(servoAngles[i]); } }

void handleServo(const String &cmd){
  if (cmd.equalsIgnoreCase("SV ATTACH")) { attachServos(); Serial.println("OK SV ATTACH"); return; }
  if (cmd.equalsIgnoreCase("SV DETACH")) { detachServos(); Serial.println("OK SV DETACH"); return; }
  if (cmd.equalsIgnoreCase("SV HOME"))   { goHome();      Serial.println("OK SV HOME");   return; }
  int sp1=cmd.indexOf(' '), sp2=cmd.lastIndexOf(' ');
  if (sp1>0 && sp2>sp1){ int idx=cmd.substring(sp1+1,sp2).toInt(); int ang=cmd.substring(sp2+1).toInt(); setServo(idx,ang); Serial.print("OK SV "); Serial.print(idx); Serial.print(' '); Serial.println(ang); return; }
  Serial.println("ERR SV");
}
