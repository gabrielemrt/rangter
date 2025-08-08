import cv2
import serial
import serial.tools.list_ports
from flask import Flask, render_template, Response, request, jsonify

app = Flask(__name__)

# --- Serial Arduino: prova auto-detect, altrimenti imposta manualmente /dev/ttyUSB0 ---
def open_arduino():
    # Prova a trovare un device con "Arduino" nel nome; fallback ttyUSB0/ACM0
    for p in serial.tools.list_ports.comports():
        if "Arduino" in (p.description or "") or "ttyACM" in p.device or "ttyUSB" in p.device:
            try:
                return serial.Serial(p.device, 115200, timeout=0.1)
            except Exception:
                pass
    # fallback hardcoded
    try:
        return serial.Serial("/dev/ttyACM0", 115200, timeout=0.1)
    except Exception:
        try:
            return serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
        except Exception:
            return None

ser = open_arduino()

# --- Video capture (webcam index 0) ---
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 20)

def gen_frames():
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        # opzionale: overlay stato
        # cv2.putText(frame, "Rover Stream", (10,20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        jpg = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/cmd', methods=['POST'])
def cmd():
    data = request.get_json(silent=True) or {}
    c = data.get('c', '').strip()
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
    ok = (cap.isOpened() and ser is not None and ser.is_open)
    return jsonify(video=cap.isOpened(), serial=(ser is not None and ser.is_open), ok=ok)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
