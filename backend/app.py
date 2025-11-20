from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chiave_segreta_per_la_session'  # Importante per le sessioni

client = MongoClient("mongodb://localhost:27017/")
db = client["torrent_db"]

# Route esistenti...

# Registrazione utente
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Controlla se l'utente esiste già
        if db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
            return render_template('register.html', error='Utente già esistente')
        
        # Crea nuovo utente
        user = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'user_type': 'registered',
            'registration_date': datetime.utcnow(),
            'is_banned': False
        }
        
        db.users.insert_one(user)
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Login utente
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = db.users.find_one({'username': username})
        
        if user and check_password_hash(user['password_hash'], password):
            if user.get('is_banned'):
                return render_template('login.html', error='Account sospeso')
            
            # Salva in sessione
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            
            # Aggiorna ultimo login
            db.users.update_one({'_id': user['_id']}, {'$set': {'last_login': datetime.utcnow()}})
            
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Credenziali errate')
    
    return render_template('login.html')

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))

# Protezione route (decoratore)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Aggiungi anche questo import in alto
from functools import wraps
from datetime import datetime