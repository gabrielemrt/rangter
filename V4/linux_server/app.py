# --- Video capture robusto (USB cam) ---
import cv2, time

def open_camera():
    # Prova indici 0..3 con backend V4L2, preferendo MJPEG se supportato
    for idx in range(4):
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap or not cap.isOpened():
            if cap: cap.release()
            continue
        # set base
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 20)
        # prova a forzare MJPEG (alcune USB lo richiedono per andare fluide)
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        # test lettura
        ok, frame = cap.read()
        if ok and frame is not None:
            print(f"[cam] aperta su index {idx} (size: {frame.shape[1]}x{frame.shape[0]})")
            return cap
        cap.release()
    print("[cam] nessuna camera disponibile")
    return None

cap = open_camera()

def gen_frames():
    global cap
    while True:
        if cap is None or not cap.isOpened():
            # tenta reopen ogni 2s
            time.sleep(2.0)
            cap = open_camera()
            continue
        ok, frame = cap.read()
        if not ok or frame is None:
            # prova a riaprire
            cap.release()
            cap = None
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        jpg = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')

@app.route('/health')
def health():
    video_ok = (cap is not None and cap.isOpened())
    serial_ok = (ser is not None and ser.is_open)
    return jsonify(video=video_ok, serial=serial_ok, ok=(video_ok and serial_ok))

@app.route('/vr')
def vr():
    return render_template('vr.html')
