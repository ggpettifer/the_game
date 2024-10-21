import eventlet
eventlet.monkey_patch()  # Patching required for eventlet to work properly with asyncio

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO
import redis

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
r = redis.Redis(host='localhost', port=6379, db=0)

# redis runs on Unix based systems - so probs best to use a docker container hmmm

# keys for redis
IS_ACTIVE_KEY = 'is_active'
PLAYER1_TIME_KEY = 'player1_time'
PLAYER2_TIME_KEY = 'player2_time'
LIMIT_KEY = 'limit'
CURRENT_PLAYER_KEY = 'current_player'

class Game:
    def __init__(self) -> None:
        # set initial redis values if they don't already exist in redis
        if not r.exists(IS_ACTIVE_KEY):
            r.set(IS_ACTIVE_KEY, False)
        if not r.exists(PLAYER1_TIME_KEY):
            r.set(PLAYER1_TIME_KEY, 0)
        if not r.exists(PLAYER2_TIME_KEY):
            r.set(PLAYER2_TIME_KEY, 0)
        if not r.exists(LIMIT_KEY):
            r.set(LIMIT_KEY, 60)
        if not r.exists(CURRENT_PLAYER_KEY):
            r.set(CURRENT_PLAYER_KEY, 1)

        # set game attributes to redis values
        self.is_active = r.get(IS_ACTIVE_KEY)
        self.player1_time = r.get(PLAYER1_TIME_KEY)
        self.player2_time = r.get(PLAYER2_TIME_KEY)
        self.limit = r.get(LIMIT_KEY)
        self.current_player = r.get(CURRENT_PLAYER_KEY)

    def increment_current_player_time(self):
        if self.current_player == 1:
            self.player1_time += 1
            r.incr(PLAYER1_TIME_KEY, 1)
        else:
            self.player2_time += 1
            r.incr(PLAYER2_TIME_KEY, 1)

    def switch(self):
        if self.is_active:
            if self.current_player == 1:
                self.current_player = 2
                r.set(CURRENT_PLAYER_KEY, 2)
            elif self.current_player == 2:
                self.current_player = 1
                r.set(CURRENT_PLAYER_KEY, 2)
            else:
                print("current player is not 1 or 2 - this shouldn't happen")
            

    def set_status(self, status):
        self.is_active = status
        r.set(IS_ACTIVE_KEY, status)

    def reset(self):
        self.set_status(False)
        self.player1_time = 0
        self.player2_time = 0
        self.current_player = 1
        r.set(PLAYER1_TIME_KEY, 0)
        r.set(PLAYER2_TIME_KEY, 0)
        r.set(CURRENT_PLAYER_KEY, 1)

    def set_limit(self, limit):
        self.limit = int(limit)
        r.set(LIMIT_KEY, int(limit))

def timer_worker():

    while True:

        eventlet.sleep(1) # this serves as both a timer interval (if game is active) and a delay until checking if the game is active (if the game is not active)

        with lock:
            if not game.is_active:
                continue
            
            game.increment_current_player_time()

            if game.player1_time >= game.limit:
                socketio.emit('winner_update', {'winner': '2'})
                game.set_status(False)
            elif game.player2_time >= game.limit:
                socketio.emit('winner_update', {'winner': '1'})
                game.set_status(False)

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
        game.set_status(True)
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset():
    with lock:
        game.reset()
        socketio.emit('winner_update', {'winner': ''})
        socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time, 'current_player': 0})
    return redirect(url_for('index'))

@app.route('/set_limit', methods=['POST'])
def set_limit():
    limit = request.form.get('limit')
    if limit.isdigit():
        with lock:
            game.set_limit(limit)
    return redirect(url_for('index'))

if __name__ == '__main__':
    game = Game()
    lock = eventlet.lock.Lock() # Lock to avoid race conditions - Both the timer_worker and the app (which handles HTTP requests) need to access game data from the game object concurrently
    socketio.start_background_task(target=timer_worker) # seperate thread
    socketio.run(app, debug=True)