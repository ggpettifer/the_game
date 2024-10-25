import os

import eventlet
eventlet.monkey_patch()  # Patching required for eventlet to work properly with asyncio

from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

# postgresql://the_game_db_user:InuhOv6YBd23etlSHq6QD3SupxIWLZEv@dpg-csdr6olsvqrc7393v970-a.frankfurt-postgres.render.com/the_game_db

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///the_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=False)
    player1_time = db.Column(db.Integer, default=0)
    player2_time = db.Column(db.Integer, default=0)
    limit = db.Column(db.Integer, default=60)
    current_player = db.Column(db.Integer, default=1)

def init_db():
    with app.app_context():
        db.create_all()
        if Game.query.count() == 0:
            game = Game()
            db.session.add(game)
            db.session.commit()

def increment_current_player_time(game):

    if game.is_active:
        if game.current_player == 1:
            game.player1_time += 1
        elif game.current_player == 2:
            game.player2_time += 1
        else:
            print("current_player is not 1 or 2, something has gone wrong")
        db.session.commit()

def switch(game):
    
    if game.is_active:
        if game.current_player == 1:
            game.current_player = 2
        elif game.current_player == 2:
            game.current_player = 1
        else:
            print("current player is not 1 or 2 - this shouldn't happen")
        db.session.commit()
            
def set_status(game, status):
    game.is_active = status
    db.session.commit()

def reset_game(game):
    game.is_active = False
    game.player1_time = 0
    game.player2_time = 0
    game.current_player = 1
    db.session.commit()

def timer_worker():

    with app.app_context():

        while True:
            
            eventlet.sleep(1) # this serves as both a timer interval (if game is active) and a delay until checking if the game is active (if the game is not active)
            
            with lock:
                game = Game.query.first()
                db.session.refresh(game)

                if not game.is_active:
                    continue
                
                increment_current_player_time(game)

                if game.player1_time >= game.limit:
                    socketio.emit('winner_update', {'winner': '2'})
                    set_status(game, False)
                elif game.player2_time >= game.limit:
                    socketio.emit('winner_update', {'winner': '1'})
                    set_status(game, False)

                # Broadcast the times to all connected users
                socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time, 'current_player': game.current_player})


@app.route('/')
def index():
    game = Game.query.first()
    return render_template('index.html', game=game)

@app.route('/switch_player', methods=['POST'])
def switch_player():
    with lock:
        game = Game.query.first()
        switch(game)
    return redirect(url_for('index'))

@app.route('/start_game', methods=['POST'])
def start():
    with lock:
        game = Game.query.first()
        set_status(game, True)
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset():
    with lock:    
        game = Game.query.first()
        reset_game(game)
        socketio.emit('winner_update', {'winner': ''})
        socketio.emit('timer_update', {'player1_time': game.player1_time, 'player2_time': game.player2_time, 'current_player': 0})
    return redirect(url_for('index'))

@app.route('/set_limit', methods=['POST'])
def set_limit():
    limit = request.form.get('limit')
    if limit.isdigit():
        with lock:
            game = Game.query.first()
            game.limit = int(limit)
            db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    lock = eventlet.lock.Lock() # Lock to avoid race conditions - Both the timer_worker and the app (which handles HTTP requests) need to access game data from the game object concurrently
    init_db()
    socketio.start_background_task(target=timer_worker) # seperate thread
    socketio.run(app) # note if debug=true it runs the application twice which causes 2 timer_worker theads, causing it to count up twice a second!