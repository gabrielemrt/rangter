from flask import Flask, render_template
import RPi.GPIO as GPIO
import time

app = Flask(__name__)

# Setup dei pin GPIO per il controllo dei motori
GPIO.setmode(GPIO.BOARD)
motors = {
    'motor1a': 11,
    'motor1b': 15,
    'motor2a': 16,
    'motor2b': 18
}
for pin in motors.values():
    GPIO.setup(pin, GPIO.OUT)

def set_motor_pins(motor1a, motor1b, motor2a, motor2b):
    GPIO.output(motors['motor1a'], motor1a)
    GPIO.output(motors['motor1b'], motor1b)
    GPIO.output(motors['motor2a'], motor2a)
    GPIO.output(motors['motor2b'], motor2b)

def move(direction):
    movements = {
        'forward': (GPIO.HIGH, GPIO.LOW, GPIO.HIGH, GPIO.LOW),
        'backward': (GPIO.LOW, GPIO.HIGH, GPIO.LOW, GPIO.HIGH),
        'right': (GPIO.LOW, GPIO.HIGH, GPIO.HIGH, GPIO.LOW),
        'left': (GPIO.HIGH, GPIO.LOW, GPIO.LOW, GPIO.HIGH),
        'stop': (GPIO.LOW, GPIO.LOW, GPIO.LOW, GPIO.LOW)
    }
    set_motor_pins(*movements.get(direction, (GPIO.LOW, GPIO.LOW, GPIO.LOW, GPIO.LOW)))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move/<direction>')
def control(direction):
    if direction in ['forward', 'backward', 'left', 'right', 'stop']:
        move(direction)
        return 'OK'
    else:
        return 'Invalid command', 400

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)
    finally:
        GPIO.cleanup()
