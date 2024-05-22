var joystick = document.getElementById('joystick');
var active = false;

function startControl(event) {
    event.preventDefault();
    active = true;
    moveJoystick(event);
}

function moveControl(event) {
    if (active) {
        moveJoystick(event);
    }
}

function stopControl() {
    active = false;
    joystick.style.top = '50%';
    joystick.style.left = '50%';
    fetch('/move/stop');
}

function moveJoystick(event) {
    var rect = joystick.parentNode.getBoundingClientRect();
    var x = (event.touches ? event.touches[0].clientX : event.clientX) - rect.left;
    var y = (event.touches ? event.touches[0].clientY : event.clientY) - rect.top;
    var centerX = rect.width / 2;
    var centerY = rect.height / 2;
    var dx = x - centerX;
    var dy = y - centerY;
    var angle = Math.atan2(dy, dx);
    var direction = '';

    if (Math.abs(dx) > Math.abs(dy)) {
        direction = dx > 0 ? 'right' : 'left';
    } else {
        direction = dy > 0 ? 'backward' : 'forward';
    }

    joystick.style.left = `${x}px`;
    joystick.style.top = `${y}px`;

    fetch('/move/' + direction).catch(error => console.error('Failed to send the move command:', error));
}

document.addEventListener('mouseup', stopControl);
document.addEventListener('touchend', stopControl);
