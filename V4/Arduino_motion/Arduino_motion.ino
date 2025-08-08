// RoverControl_NoEN.ino
// Controllo L298N solo con N1..N4 (niente ENA/ENB). PWM direttamente sugli IN.

const int L1 = 8;   // N1 sinistro
const int L2 = 9;   // N2 sinistro
const int R1 = 10;  // N3 destro
const int R2 = 11;  // N4 destro

const unsigned long WATCHDOG_MS = 1000;
unsigned long lastCmdMs = 0;

void setup() {
  pinMode(L1, OUTPUT); pinMode(L2, OUTPUT);
  pinMode(R1, OUTPUT); pinMode(R2, OUTPUT);
  stopMotors();
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
  char c = cmd.charAt(0);
  int spd = 0;
  if (cmd.length() > 1) spd = constrain(cmd.substring(1).toInt(), 0, 255);

  switch (c) {
    case 'F': forward(spd); Serial.println("OK F"); break;
    case 'B': backward(spd); Serial.println("OK B"); break;
    case 'L': turnLeft(spd); Serial.println("OK L"); break;
    case 'R': turnRight(spd); Serial.println("OK R"); break;
    case 'S': stopMotors(); Serial.println("OK S"); break;
    default: Serial.println("ERR");
  }
}

// --- Motori ---
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

// Gira a sinistra (pivot): sinistro indietro, destro avanti
void turnLeft(int spd) {
  digitalWrite(L1, LOW); analogWrite(L2, spd);  // sinistro indietro
  analogWrite(R1, spd);  digitalWrite(R2, LOW); // destro avanti
}

// Gira a destra (pivot): sinistro avanti, destro indietro
void turnRight(int spd) {
  analogWrite(L1, spd);  digitalWrite(L2, LOW); // sinistro avanti
  digitalWrite(R1, LOW); analogWrite(R2, spd);  // destro indietro
}

// Stop: rilascia (coast). Per "freno" metti HIGH/LOW opposti su ogni lato.
void stopMotors() {
  analogWrite(L1, 0); analogWrite(L2, 0);
  analogWrite(R1, 0); analogWrite(R2, 0);
  // coast: tutti LOW
  digitalWrite(L1, LOW); digitalWrite(L2, LOW);
  digitalWrite(R1, LOW); digitalWrite(R2, LOW);
}
