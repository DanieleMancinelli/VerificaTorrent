from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chiave_segreta_per_la_session'

client = MongoClient("mongodb+srv://mancinellidaniele_db_user:pyfuEgnCo3gGIFw4@cluster0.4ovwsmg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["torrent_db"]

# Route principale
@app.route("/")
def home():
    return render_template("index.html")

# API per i torrent (JSON)
@app.route("/api/torrents")
def api_torrents():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = {}
    if search:
        query['$or'] = [
            {'title': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}}
        ]
    if category:
        query['categories'] = category
    
    torrents = list(db.torrents.find(query))
    
    # Converti _id in stringa
    for torrent in torrents:
        torrent['_id'] = str(torrent['_id'])
        if 'uploader_id' in torrent:
            torrent['uploader_id'] = str(torrent['uploader_id'])
    
    return jsonify(torrents)

# Pagina HTML per la ricerca
@app.route("/search")
def search_page():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = {}
    if search:
        query['$or'] = [
            {'title': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}}
        ]
    if category:
        query['categories'] = category
    
    torrents = list(db.torrents.find(query))
    
    # Converti _id in stringa
    for torrent in torrents:
        torrent['_id'] = str(torrent['_id'])
        if 'uploader_id' in torrent:
            torrent['uploader_id'] = str(torrent['uploader_id'])
    
    return render_template("search_results.html", torrents=torrents, search=search, category=category)

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
                return render_template('login.html', error='Account sospeso - Contatta un amministratore')
            
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

# Route per creare un moderatore (solo per testing)
@app.route("/create-moderator")
def create_moderator():
    # Controlla se esiste già
    if not db.users.find_one({'username': 'moderator'}):
        user = {
            'username': 'moderator',
            'email': 'moderator@email.com',
            'password_hash': generate_password_hash('mod123'),
            'user_type': 'moderator',
            'registration_date': datetime.utcnow(),
            'is_banned': False
        }
        db.users.insert_one(user)
    return "Moderatore creato: username=moderator, password=mod123"

# Route per creare un admin (solo per testing)
@app.route("/create-admin")
def create_admin():
    # Controlla se esiste già
    if not db.users.find_one({'username': 'admin'}):
        user = {
            'username': 'admin',
            'email': 'admin@email.com',
            'password_hash': generate_password_hash('admin123'),
            'user_type': 'admin',
            'registration_date': datetime.utcnow(),
            'is_banned': False
        }
        db.users.insert_one(user)
    return "Admin creato: username=admin, password=admin123"

# Panel moderatore/admin
@app.route("/admin")
@login_required
def admin_panel():
    user_type = session.get('user_type')
    
    if user_type not in ['moderator', 'admin']:
        return "Accesso negato: solo moderatori e admin possono accedere", 403
    
    # Statistiche per admin
    stats = {}
    if user_type == 'admin':
        stats['total_users'] = db.users.count_documents({})
        stats['total_torrents'] = db.torrents.count_documents({})
        stats['total_comments'] = db.comments.count_documents({}) if 'comments' in db.list_collection_names() else 0
    
    # Ultimi torrent caricati
    recent_torrents = list(db.torrents.find().sort('upload_date', -1).limit(5))
    for torrent in recent_torrents:
        torrent['_id'] = str(torrent['_id'])
    
    # Utenti bannati
    banned_users = list(db.users.find({'is_banned': True}))
    for user in banned_users:
        user['_id'] = str(user['_id'])
    
    return render_template("admin_panel.html", 
                         user_type=user_type,
                         stats=stats,
                         recent_torrents=recent_torrents,
                         banned_users=banned_users)

# Lista tutti gli utenti (per moderatori/admin)
@app.route("/admin/users")
@login_required
def admin_users():
    user_type = session.get('user_type')
    
    if user_type not in ['moderator', 'admin']:
        return "Accesso negato", 403
    
    # Ottieni tutti gli utenti
    users = list(db.users.find({}))
    for user in users:
        user['_id'] = str(user['_id'])
    
    return render_template("admin_users.html", users=users, user_type=user_type)

# Banna utente - VERSIONE SEMPLIFICATA SENZA BSON
@app.route("/admin/ban-user/<username>")
@login_required
def ban_user(username):
    if session.get('user_type') not in ['moderator', 'admin']:
        return "Accesso negato", 403
    
    # NON permettere di bannare te stesso
    if username == session.get('username'):
        return "Non puoi bannare te stesso", 400
    
    # Ottieni l'utente per controllare il tipo
    user_to_ban = db.users.find_one({'username': username})
    if not user_to_ban:
        return "Utente non trovato", 404
    
    # Non permettere di bannare altri admin/moderatori (solo admin può farlo)
    if user_to_ban['user_type'] in ['admin', 'moderator'] and session.get('user_type') != 'admin':
        return "Non puoi bannare altri moderatori o admin", 403
    
    db.users.update_one({'username': username}, {'$set': {'is_banned': True}})
    return redirect(url_for('admin_users'))

# Sbanna utente - VERSIONE SEMPLIFICATA SENZA BSON
@app.route("/admin/unban-user/<username>")
@login_required
def unban_user(username):
    if session.get('user_type') not in ['moderator', 'admin']:
        return "Accesso negato", 403
    
    db.users.update_one({'username': username}, {'$set': {'is_banned': False}})
    return redirect(url_for('admin_users'))

# Download torrent (solo utenti registrati)
@app.route("/download/<torrent_id>")
@login_required
def download_torrent(torrent_id):
    torrent = db.torrents.find_one({'_id': torrent_id})
    
    if not torrent:
        return "Torrent non trovato", 404
    
    # Incrementa contatore download
    db.torrents.update_one({'_id': torrent_id}, {'$inc': {'download_count': 1}})
    
    return f"Download del torrent: {torrent['title']}"

if __name__ == "__main__":
    app.run(debug=True)