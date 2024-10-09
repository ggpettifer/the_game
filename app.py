import eventlet
eventlet.monkey_patch()  # Patching required for eventlet to work properly with asyncio

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from threading import Lock
import time

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
lock = Lock()  # Lock to protect shared resources - avoid race conditions

class Game:
    def __init__(self, is_active, player1_time, player2_time, limit, current_player) -> None:
        self.is_active = is_active
        self.player1_time = player1_time
        self.player2_time = player2_time
        self.limit = limit
        self.current_player = current_player

game = Game(False, 0, 0, 60, 1)

def timer_worker():

    while True:
        print("game.is_active: ", game.is_active)
        with lock:
            if not game.is_active:
                print("game not active")
                time.sleep(1)
                continue
        print("game is active, waiting 1 second")
        time.sleep(1)

        with lock:
            if game.current_player == 1:
                print("increment player 1")
                game.player1_time += 1
            else:
                print("increment player 2")
                game.player2_time += 1

            if game.player1_time >= game.limit:
                socketio.emit('winner_update', {'winner': 'Player 2'})
                game.is_active = False
            elif game.player2_time >= game.limit:
                socketio.emit('winner_update', {'winner': 'Player 1'})
                game.is_active = False

            # Broadcast the times to all connected users
            print(f"player1_time: {game.player1_time} player2_time: {game.player2_time}")
            socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time})

@app.route('/')
def index():
    with lock:
        return render_template('index.html', game=game)

@app.route('/switch_player', methods=['POST'])
def switch_player():
    with lock:
        if game.is_active:
            print("switching")
            game.current_player = 2 if game.current_player == 1 else 1
    return redirect(url_for('index'))

@app.route('/start_game', methods=['POST'])
def start():
    game.is_active = True
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset():
    with lock:
        print("reseting")
        game.is_active = False
        game.player1_time = 0
        game.player2_time = 0
        game.current_player = 1
        socketio.emit('winner_update', {'winner': ''})
        socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time})
    return redirect(url_for('index'))

@app.route('/set_limit', methods=['POST'])
def set_limit():
    limit = request.form.get('limit')
    if limit.isdigit():
        print("setting limit")
        game.limit = int(limit)
    return redirect(url_for('index'))

if __name__ == '__main__':
    socketio.start_background_task(target=timer_worker) # seperate thread
    socketio.run(app, debug=True)

