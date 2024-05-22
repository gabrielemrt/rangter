function startMoving(direction) {
    fetch('/move/' + direction)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
        })
        .catch(error => console.error('Error during move command:', error));
}

function stopMoving() {
    fetch('/move/stop')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
        })
        .catch(error => console.error('Error during stop command:', error));
}
