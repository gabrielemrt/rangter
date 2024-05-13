from flask import Flask, render_template
from camera import Camera
import RPi.GPIO as GPIO
import time

app = Flask(__name__)
camera = Camera()

# Setup dei pin GPIO per il controllo dei motori
GPIO.setmode(GPIO.BOARD)
motor1a = 11
motor1b = 15
motor2a = 16
motor2b = 18
GPIO.setup(motor1a, GPIO.OUT)
GPIO.setup(motor1b, GPIO.OUT)
GPIO.setup(motor2a, GPIO.OUT)
GPIO.setup(motor2b, GPIO.OUT)

# Funzioni per il controllo dei motori
def move_forward():
    GPIO.output(motor1a, GPIO.HIGH)
    GPIO.output(motor1b, GPIO.LOW)
    GPIO.output(motor2a, GPIO.HIGH)
    GPIO.output(motor2b, GPIO.LOW)

def move_backward():
    GPIO.output(motor1a, GPIO.LOW)
    GPIO.output(motor1b, GPIO.HIGH)
    GPIO.output(motor2a, GPIO.LOW)
    GPIO.output(motor2b, GPIO.HIGH)

def turn_right():
    GPIO.output(motor1a, GPIO.LOW)
    GPIO.output(motor1b, GPIO.HIGH)
    GPIO.output(motor2a, GPIO.HIGH)
    GPIO.output(motor2b, GPIO.LOW)

def turn_left():
    GPIO.output(motor1a, GPIO.HIGH)
    GPIO.output(motor1b, GPIO.LOW)
    GPIO.output(motor2a, GPIO.LOW)
    GPIO.output(motor2b, GPIO.HIGH)

def stop():
    GPIO.output(motor1a, GPIO.LOW)
    GPIO.output(motor1b, GPIO.LOW)
    GPIO.output(motor2a, GPIO.LOW)
    GPIO.output(motor2b, GPIO.LOW)

# Pagina principale con le frecce di controllo
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint per il controllo del movimento
@app.route('/move/<direction>')
def move(direction):
    if direction == 'forward':
        move_forward()
    elif direction == 'backward':
        move_backward()
    elif direction == 'left':
        turn_left()
    elif direction == 'right':
        turn_right()
    elif direction == 'stop':
        stop()
    return 'OK'


# Route per lo streaming video
@app.route('/video_feed')
def video_feed():
    return Response(camera.stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

