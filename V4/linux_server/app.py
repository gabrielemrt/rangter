import time
import cv2
import serial
import serial.tools.list_ports
from flask import Flask, render_template, Response, request, jsonify

# ---------------- Flask app PRIMA di tutto ----------------
app = Flask(__name__)

# ---------------- Serial Arduino ----------------
def open_arduino():
    for p in serial.tools.list_ports.comports():
        if "Arduino" in (p.description or "") or "ttyACM" in p.device or "ttyUSB" in p.device:
            try:
                return serial.Serial(p.device, 115200, timeout=0.1)
            except Exception:
                pass
    # fallback
    for dev in ("/dev/ttyACM0", "/dev/ttyUSB0"):
        try:
            return serial.Serial(dev, 115200, timeout=0.1)
        except Exception:
            pass
    return None

ser = open_arduino()

# ---------------- Camera (robusto) ----------------
def try_open_index(idx, fourcc_pref=None):
    # prova con backend V4L2
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap or not cap.isOpened():
        if cap: cap.release()
        return None

    # dimensioni e fps
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 20)

    # eventualmente forza FOURCC (MJPG o YUY2)
    if fourcc_pref:
        cap.set(cv2.CAP_PROP_FOURCC, fourcc_pref)

    # test lettura
    ok, frame = cap.read()
    if ok and frame is not None:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[cam] aperta su index {idx} ({w}x{h})")
        return cap

    cap.release()
    return None

def open_camera():
    # tenta MJPG prima (più leggero), poi YUY2, su indici 0..3
    for idx in range(4):
        cap = try_open_index(idx, cv2.VideoWriter_fourcc(*'MJPG'))
        if cap: return cap
    for idx in range(4):
        cap = try_open_index(idx, cv2.VideoWriter_fourcc(*'YUY2'))
        if cap: return cap
    print("[cam] nessuna camera disponibile")
    return None

cap = open_camera()

def gen_frames():
    global cap
    while True:
        if cap is None or not cap.isOpened():
            # tenta di riaprire ogni 2s se non disponibile
            time.sleep(2.0)
            cap = open_camera()
            continue

        ok, frame = cap.read()
        if not ok or frame is None:
            # prova a riaprire
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

# ---------------- Routes ----------------
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
    try:
        ser.write((c + "\n").encode('ascii'))
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route('/health')
def health():
    video_ok = (cap is not None and cap.isOpened())
    serial_ok = (ser is not None and ser.is_open)
    return jsonify(video=video_ok, serial=serial_ok, ok=(video_ok and serial_ok))

if __name__ == '__main__':
    # ascolta sulla rete locale
    app.run(host='0.0.0.0', port=8080, threaded=True)
