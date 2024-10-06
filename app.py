from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chess_clock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database model
class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1_time = db.Column(db.Integer, default=0)  # Time in seconds
    player2_time = db.Column(db.Integer, default=0)
    limit = db.Column(db.Integer, default=60)  # Default limit of 60 seconds
    current_player = db.Column(db.String(20), default='player1')

# Create the database
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    game = Game.query.first()
    if game is None:
        game = Game()  # Create a new game if none exists
        db.session.add(game)
        db.session.commit()
    return render_template('index.html', game=game)

@app.route('/update_time', methods=['POST'])
def update_time():
    game = Game.query.first()
    if game:
        if game.current_player == 'player1':
            game.player1_time += 1
        else:
            game.player2_time += 1
        db.session.commit()
    return jsonify({'player1_time': game.player1_time, 'player2_time': game.player2_time})

@app.route('/switch_player', methods=['POST'])
def switch_player():
    game = Game.query.first()
    if game:
        game.current_player = 'player2' if game.current_player == 'player1' else 'player1'
        db.session.commit()
    return jsonify({'current_player': game.current_player})

@app.route('/reset', methods=['POST'])
def reset():
    game = Game.query.first()
    if game:
        game.player1_time = 0
        game.player2_time = 0
        game.current_player = 'player1'
        db.session.commit()
    return jsonify({'player1_time': 0, 'player2_time': 0})

@app.route('/set_limit', methods=['POST'])
def set_limit():
    limit = request.form.get('limit')
    game = Game.query.first()
    if game and limit.isdigit():
        game.limit = int(limit)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/check_winner', methods=['GET'])
def check_winner():
    game = Game.query.first()
    if game:
        if game.player1_time >= game.limit:
            return jsonify({'winner': 'Player 2'})
        elif game.player2_time >= game.limit:
            return jsonify({'winner': 'Player 1'})
    return jsonify({'winner': None})

if __name__ == '__main__':
    app.run(debug=True)
