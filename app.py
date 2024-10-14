import eventlet
eventlet.monkey_patch()  # Patching required for eventlet to work properly with asyncio

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO
from threading import Lock

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

class Game:
    def __init__(self) -> None:
        self.is_active = False
        self.player1_time = 0
        self.player2_time = 0
        self.limit = 60
        self.current_player = 1

    def increment_current_player_time(self):
        if self.current_player == 1:
            self.player1_time += 1
        else:
            self.player2_time += 1

    def switch(self):
        if self.is_active:
            self.current_player = 2 if self.current_player == 1 else 1

def timer_worker():

    while True:

        eventlet.sleep(1) # this serves as both a timer interval (if game is active) and a delay until checking if the game is active (if the game is not active)

        with lock:
            if not game.is_active:
                continue
            
            game.increment_current_player_time()

            if game.player1_time >= game.limit:
                socketio.emit('winner_update', {'winner': '2'})
                game.is_active = False
            elif game.player2_time >= game.limit:
                socketio.emit('winner_update', {'winner': '1'})
                game.is_active = False

            # Broadcast the times to all connected users
            socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time, 'current_player': game.current_player})


@app.route('/')
def index():
    with lock:
        return render_template('index.html', game=game)

@app.route('/switch_player', methods=['POST'])
def switch_player():
    with lock:
        game.switch()
    return redirect(url_for('index'))

@app.route('/start_game', methods=['POST'])
def start():
    with lock:
        game.is_active = True
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset():
    with lock:
        game.is_active = False
        game.player1_time = 0
        game.player2_time = 0
        game.current_player = 1
        socketio.emit('winner_update', {'winner': ''})
        socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time, 'current_player': 0})
    return redirect(url_for('index'))

@app.route('/set_limit', methods=['POST'])
def set_limit():
    limit = request.form.get('limit')
    if limit.isdigit():
        with lock:
            game.limit = int(limit)
    return redirect(url_for('index'))

if __name__ == '__main__':
    game = Game()
    lock = Lock()  # Lock to avoid race conditions - Both the timer_worker and the app (which handles HTTP requests) need to access game data from the game object concurrently
    socketio.start_background_task(target=timer_worker) # seperate thread
    socketio.run(app, debug=True)