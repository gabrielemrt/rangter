from flask import Flask, render_template, Response, request
import cv2
import serial
import time

# Setup seriale verso Arduino
arduino = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
time.sleep(2)  # Attesa iniziale per connessione seriale

# Setup Flask
app = Flask(_name_)

# Inizializza la webcam (0 = prima USB cam disponibile)
camera = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Codifica frame in JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            # Streaming multipart per il browser
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Route per pagina principale
@app.route('/')
def index():
    return render_template('index.html')

# Route per lo stream video
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Route per comandi movimento
@app.route('/move', methods=['POST'])
def move():
    command = request.form.get('command', '')
    if command in ['F', 'B', 'L', 'R', 'S']:
        arduino.write(command.encode())
    return ('', 204)

if _name_ == '_main_':
    app.run(host='0.0.0.0', port=5000)