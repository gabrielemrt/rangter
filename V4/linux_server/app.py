#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import threading
from pathlib import Path

import cv2
import serial
import serial.tools.list_ports
from flask import Flask, render_template, Response, request, jsonify

# flag per capire se abbiamo applicato i settaggi con successo
applied_once = False
applied_lock = threading.Lock()

def wait_arduino_ready(port, timeout=5.0):
    """Legge la seriale finché non vede 'READY' (o timeout)."""
    try:
        port.reset_input_buffer()
    except Exception:
        pass
    t0 = time.time()
    buf = b""
    while time.time() - t0 < timeout:
        try:
            if port.in_waiting:
                buf += port.readline()
                if b"READY" in buf:
                    print("[serial] READY ricevuto")
                    return True
        except Exception:
            pass
        time.sleep(0.05)
    print("[serial] READY non ricevuto entro timeout")
    return False


# ============== Flask app (prima di tutto!) ==============
app = Flask(__name__)

# ============== Settings persistenti =====================
BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"
DEFAULT_SETTINGS = {
    "led_color": [255, 180, 100],      # R,G,B
    "led_brightness": 60,              # 0-255
    "motor_default_speed": 150,        # slider di default lato UI
    "servo_angles": [90, 90, 90, 90],  # Base, Spalla, Gomito, Pinza
}
settings = {}  # popolato da load_settings()

def load_settings():
    global settings
    if SETTINGS_PATH.exists():
        try:
            disk = json.loads(SETTINGS_PATH.read_text())
        except Exception:
            disk = {}
        settings = {**DEFAULT_SETTINGS, **disk}
    else:
        settings = DEFAULT_SETTINGS.copy()

def save_settings():
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
    except Exception as e:
        print("[settings] write error:", e)

# ============== Serial Arduino ===========================
def open_arduino():
    """Prova ad aprire la seriale dell'Arduino."""
    # 1) scan porte note
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

ser = None  # inizializzato dopo load_settings()

# ============== Camera (robusta, auto-detect) ============
def try_open_index(idx, fourcc_pref=None):
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap or not cap.isOpened():
        if cap: cap.release()
        return None
    # Parametri base
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 20)
    if fourcc_pref:
        cap.set(cv2.CAP_PROP_FOURCC, fourcc_pref)
    # Test lettura
    ok, frame = cap.read()
    if ok and frame is not None:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[cam] aperta index {idx} ({w}x{h})")
        return cap
    cap.release()
    return None

def open_camera():
    # Prova MJPG prima, poi YUY2, su index 0..3
    for idx in range(4):
        cap = try_open_index(idx, cv2.VideoWriter_fourcc(*'MJPG'))
        if cap: return cap
    for idx in range(4):
        cap = try_open_index(idx, cv2.VideoWriter_fourcc(*'YUY2'))
        if cap: return cap
    print("[cam] nessuna camera disponibile")
    return None

cap = None  # inizializzato dopo load_settings()

def gen_frames():
    """Generator per stream MJPEG."""
    global cap
    while True:
        if cap is None or not cap.isOpened():
            time.sleep(2.0)
            cap = open_camera()
            continue

        ok, frame = cap.read()
        if not ok or frame is None:
            try:
                cap.release()
            except Exception:
                pass
            cap = None
            continue

        # JPEG encode
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        jpg = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')

# ============== Applicazione settings all'avvio ==========
def apply_settings_to_arduino():
    """Invia a Arduino le impostazioni persistite (LED/servi) e marca applied_once."""
    global applied_once
    if ser is None or not ser.is_open:
        print("[settings] seriale non disponibile: skip apply")
        return
    ok = False
    try:
        r, g, b = settings.get("led_color", DEFAULT_SETTINGS["led_color"])
        br = int(settings.get("led_brightness", DEFAULT_SETTINGS["led_brightness"]))
        ser.write(f"LED BR {br}\n".encode('ascii')); time.sleep(0.02)
        ser.write(f"LED RGB {r} {g} {b}\n".encode('ascii')); time.sleep(0.02)
        angles = settings.get("servo_angles", DEFAULT_SETTINGS["servo_angles"])
        if isinstance(angles, (list, tuple)) and len(angles) == 4:
            for i, a in enumerate(angles):
                ser.write(f"SV {i} {int(a)}\n".encode('ascii'))
                time.sleep(0.01)
        ok = True
        print("[settings] applicate")
    except Exception as e:
        print("[settings] apply error:", e)
    if ok:
        with applied_lock:
            applied_once = True

# ============== Routes ===================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vr')
def vr():
    return render_template('vr.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/cmd', methods=['POST'])
def cmd():
    data = request.get_json(silent=True) or {}
    c = (data.get('c') or '').strip()

    if not c:
        return jsonify(ok=False, err="missing command"), 400
    if ser is None or not ser.is_open:
        return jsonify(ok=False, err="serial not available"), 503

    # --- se è LED ON e non abbiamo ancora applicato i settaggi, applicali ora ---
    if c.upper() == "LED ON":
        with applied_lock:
            pending = not applied_once
        if pending:
            apply_settings_to_arduino()
            # piccolo delay per garantire ordine dei comandi
            time.sleep(0.02)

    try:
        ser.write((c + "\n").encode('ascii'))
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500


@app.route('/apply_settings_now', methods=['POST'])
def apply_settings_now():
    threading.Thread(target=apply_settings_to_arduino, daemon=True).start()
    return jsonify(ok=True)


@app.route('/health')
def health():
    video_ok = (cap is not None and cap.isOpened())
    serial_ok = (ser is not None and ser.is_open)
    return jsonify(video=video_ok, serial=serial_ok, ok=(video_ok and serial_ok))

# ---- settings persistenti ----
@app.route('/settings', methods=['GET'])
def get_settings():
    return jsonify(settings)

@app.route('/settings', methods=['POST'])
def set_settings():
    data = request.get_json(silent=True) or {}
    changed = False
    for k in ("led_color", "led_brightness", "motor_default_speed", "servo_angles"):
        if k in data:
            settings[k] = data[k]
            changed = True
    if changed:
        save_settings()
    if data.get("apply"):
        # applica subito a Arduino (senza ARM)
        threading.Thread(target=apply_settings_to_arduino, daemon=True).start()
    return jsonify(ok=True, settings=settings)

# ============== Bootstrap =================================
def bootstrap():
    global ser, cap, applied_once
    load_settings()
    ser = open_arduino()
    cap = open_camera()
    # Attendi che l'Arduino annunci READY (reset auto su apertura seriale)
    if ser and ser.is_open:
        ready = wait_arduino_ready(ser, timeout=5.0)
        # anche se non lo vediamo, proviamo ad applicare dopo un attimo
        delay = 0.2 if ready else 1.5
        threading.Timer(delay, apply_settings_to_arduino).start()
    else:
        applied_once = False


bootstrap()

# ============== Main ======================================
if __name__ == '__main__':
    # ascolta su tutta la LAN
    app.run(host='0.0.0.0', port=8080, threaded=True)
