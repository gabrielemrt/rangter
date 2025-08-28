# -*- coding: utf-8 -*-
import time
import threading
import serial
import serial.tools.list_ports

class SerialBridge:
    """
    Gestisce:
    - apertura seriale verso Arduino
    - attesa READY dopo reset
    - applicazione settaggi (LED/servi) con ordine: BR, RGB, ON/OFF, SV
    - inoltro comandi singoli (write_line)
    - flag applied_once per applicazione iniziale avvenuta
    """
    def __init__(self):
        self.port = None
        self.applied_once = False
        self._lock = threading.Lock()

    # --- proprietà comode ---
    @property
    def is_open(self):
        return bool(self.port and self.port.is_open)

    # --- apertura & READY ---
    def _open_first_available(self):
        # 1) scan porte con descrizione
        for p in serial.tools.list_ports.comports():
            if "Arduino" in (p.description or "") or "CDC" in (p.description or "") \
               or "ttyACM" in p.device or "ttyUSB" in p.device:
                try:
                    print(f"[serial] provo {p.device}")
                    return serial.Serial(p.device, 115200, timeout=0.1)
                except Exception as e:
                    print(f"[serial] fail {p.device}: {e}")
        # 2) fallback
        for dev in ("/dev/ttyACM0", "/dev/ttyUSB0", "/dev/ttyUSB1"):
            try:
                print(f"[serial] provo {dev}")
                return serial.Serial(dev, 115200, timeout=0.1)
            except Exception:
                pass
        print("[serial] nessuna porta trovata")
        return None

    def _wait_ready(self, timeout=5.0):
        if not self.is_open:
            return False
        try:
            self.port.reset_input_buffer()
        except Exception:
            pass
        t0 = time.time()
        buf = b""
        while time.time() - t0 < timeout:
            try:
                if self.port.in_waiting:
                    buf += self.port.readline()
                    if b"READY" in buf:
                        print("[serial] READY ricevuto")
                        return True
            except Exception:
                pass
            time.sleep(0.05)
        print("[serial] READY non ricevuto entro timeout")
        return False

    def open(self):
        self.port = self._open_first_available()
        if not self.is_open:
            self.applied_once = False
            return
        ready = self._wait_ready(timeout=5.0)
        # Schedula applicazione settaggi anche se READY non visto (delay maggiore)
        delay = 0.2 if ready else 1.5
        threading.Timer(delay, self._apply_scheduled).start()

    # --- applicazione settaggi iniziale pianificata ---
    def _apply_scheduled(self):
        # chiamata asincrona all'avvio
        if hasattr(self, "_scheduled_settings"):
            self.apply_settings_now(self._scheduled_settings)
        # Se non impostato ancora, non fa nulla; sarà la UI o /settings ad applicare

    # --- API pubbliche ---
    def apply_settings_now(self, s):
        """Applica BR, RGB, ON/OFF, angoli servi. Marca applied_once=True se ok."""
        if not self.is_open:
            # memorizzo per quando si aprirà
            self._scheduled_settings = s
            return False
        ok = True
        try:
            r, g, b = s.get("led_color", [255,180,100])
            br = int(s.get("led_brightness", 60))
            on = bool(s.get("led_on", False))
            # 1) parametri senza accendere
            self.port.write(f"LED BR {br}\n".encode('ascii')); time.sleep(0.02)
            self.port.write(f"LED RGB {r} {g} {b}\n".encode('ascii')); time.sleep(0.02)
            # 2) stato finale
            self.port.write(( "LED ON\n" if on else "LED OFF\n").encode('ascii')); time.sleep(0.02)
            # Servi
            angles = s.get("servo_angles", [90,90,90,90])
            if isinstance(angles, (list, tuple)) and len(angles) == 4:
                for i, a in enumerate(angles):
                    self.port.write(f"SV {i} {int(a)}\n".encode('ascii'))
                    time.sleep(0.01)
            with self._lock:
                self.applied_once = True
            print("[settings] applicate (iniziale/manuale)")
        except Exception as e:
            print("[settings] apply error:", e)
            ok = False
        return ok

    def write_line(self, text):
        """Scrive una riga (con newline). Ritorna (ok, err)."""
        if not self.is_open:
            return False, "port closed"
        try:
            self.port.write((text + "\n").encode('ascii'))
            return True, None
        except Exception as e:
            return False, str(e)
