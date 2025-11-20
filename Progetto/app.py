from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
from bson import ObjectId  # AGGIUNTO BSON PER LE CANCELLAZIONI

app = Flask(__name__)
app.secret_key = 'chiave_segreta_per_la_session'

client = MongoClient("mongodb+srv://mancinellidaniele_db_user:pyfuEgnCo3gGIFw4@cluster0.4ovwsmg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["torrent_db"]

# Funzione per creare commenti di prova
def create_sample_comments():
    if db.comments.count_documents({}) == 0:
        # Trova alcuni torrent e utenti esistenti
        torrents = list(db.torrents.find().limit(2))
        users = list(db.users.find().limit(2))
        
        if torrents and users:
            sample_comments = [
                {
                    'torrent_id': str(torrents[0]['_id']),
                    'user_id': str(users[0]['_id']),
                    'text': 'Ottimo torrent, qualità eccellente!',
                    'rating': 5,
                    'comment_date': datetime.utcnow()
                },
                {
                    'torrent_id': str(torrents[1]['_id']),
                    'user_id': str(users[1]['_id']),
                    'text': 'Qualità video scadente, non lo consiglio',
                    'rating': 2,
                    'comment_date': datetime.utcnow()
                }
            ]
            db.comments.insert_many(sample_comments)

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
        
        if db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
            return render_template('register.html', error='Utente già esistente')
        
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
            
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            
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

# Protezione route
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Solo moderatore/admin
def moderator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('user_type') not in ['moderator', 'admin']:
            return "Accesso negato: solo moderatori e admin", 403
        return f(*args, **kwargs)
    return decorated_function

# Solo admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('user_type') != 'admin':
            return "Accesso negato: solo admin", 403
        return f(*args, **kwargs)
    return decorated_function

# Route per creare moderatore e admin (solo testing)
@app.route("/create-moderator")
def create_moderator():
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

@app.route("/create-admin")
def create_admin():
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

# Crea commenti di prova
@app.route("/create-sample-comments")
def create_sample_comments_route():
    create_sample_comments()
    return "Commenti di prova creati!"

# PANEL MODERATORE/ADMIN
@app.route("/admin")
@moderator_required
def admin_panel():
    user_type = session.get('user_type')
    
    # Statistiche per admin
    stats = {}
    if user_type == 'admin':
        stats['total_users'] = db.users.count_documents({})
        stats['total_torrents'] = db.torrents.count_documents({})
        stats['total_comments'] = db.comments.count_documents({}) if 'comments' in db.list_collection_names() else 0
        
        # Statistiche avanzate per admin
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        stats['new_torrents_week'] = db.torrents.count_documents({'upload_date': {'$gte': one_week_ago}})
    
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

# GESTIONE UTENTI
@app.route("/admin/users")
@moderator_required
def admin_users():
    users = list(db.users.find({}))
    for user in users:
        user['_id'] = str(user['_id'])
    
    return render_template("admin_users.html", users=users, user_type=session.get('user_type'))

@app.route("/admin/ban-user/<username>")
@moderator_required
def ban_user(username):
    current_user_type = session.get('user_type')
    user_to_ban = db.users.find_one({'username': username})
    
    if not user_to_ban:
        return "Utente non trovato", 404
    
    # Controlli di sicurezza
    if username == session.get('username'):
        return "Non puoi bannare te stesso", 400
    
    # Moderatore non può bannare admin
    if user_to_ban['user_type'] == 'admin' and current_user_type != 'admin':
        return "Non puoi bannare un admin", 403
    
    # Moderatore non può bannare altri moderatori
    if user_to_ban['user_type'] == 'moderator' and current_user_type != 'admin':
        return "Solo admin può bannare moderatori", 403
    
    db.users.update_one({'username': username}, {'$set': {'is_banned': True}})
    return redirect(url_for('admin_users'))

@app.route("/admin/unban-user/<username>")
@moderator_required
def unban_user(username):
    db.users.update_one({'username': username}, {'$set': {'is_banned': False}})
    return redirect(url_for('admin_users'))

# GESTIONE TORRENT (cancellazione per copyright) - VERSIONE CORRETTA
@app.route("/admin/torrents")
@moderator_required
def admin_torrents():
    torrents = list(db.torrents.find().sort('upload_date', -1))
    for torrent in torrents:
        torrent['_id'] = str(torrent['_id'])
        if 'uploader_id' in torrent:
            try:
                uploader = db.users.find_one({'_id': ObjectId(torrent['uploader_id'])})
                torrent['uploader_name'] = uploader['username'] if uploader else 'Utente sconosciuto'
            except:
                torrent['uploader_name'] = 'Utente sconosciuto'
        else:
            torrent['uploader_name'] = 'Utente sconosciuto'
    
    return render_template("admin_torrents.html", torrents=torrents)

@app.route("/admin/delete-torrent/<torrent_id>")
@moderator_required
def delete_torrent(torrent_id):
    try:
        # Converti l'ID in ObjectId
        torrent_object_id = ObjectId(torrent_id)
        
        # Cancella il torrent
        result = db.torrents.delete_one({'_id': torrent_object_id})
        
        if result.deleted_count == 1:
            # Cancella anche i commenti associati (se esistono)
            if 'comments' in db.list_collection_names():
                db.comments.delete_many({'torrent_id': torrent_id})
            return redirect(url_for('admin_torrents'))
        else:
            return "Torrent non trovato", 404
            
    except Exception as e:
        return f"Errore nella cancellazione: {str(e)}", 500

# GESTIONE COMMENTI - VERSIONE CORRETTA
@app.route("/admin/comments")
@moderator_required
def admin_comments():
    # Assicurati che ci siano commenti
    create_sample_comments()
    
    comments = list(db.comments.find().sort('comment_date', -1))
    for comment in comments:
        comment['_id'] = str(comment['_id'])
        # Aggiungi info utente e torrent
        try:
            user = db.users.find_one({'_id': ObjectId(comment['user_id'])})
            comment['username'] = user['username'] if user else 'Utente sconosciuto'
        except:
            comment['username'] = 'Utente sconosciuto'
            
        try:
            torrent = db.torrents.find_one({'_id': ObjectId(comment['torrent_id'])})
            comment['torrent_title'] = torrent['title'] if torrent else 'Torrent cancellato'
        except:
            comment['torrent_title'] = 'Torrent cancellato'
    
    return render_template("admin_comments.html", comments=comments)

@app.route("/admin/delete-comment/<comment_id>")
@moderator_required
def delete_comment(comment_id):
    try:
        # Converti l'ID in ObjectId
        comment_object_id = ObjectId(comment_id)
        
        # Cancella il commento
        result = db.comments.delete_one({'_id': comment_object_id})
        
        if result.deleted_count == 1:
            return redirect(url_for('admin_comments'))
        else:
            return "Commento non trovato", 404
            
    except Exception as e:
        return f"Errore nella cancellazione: {str(e)}", 500

# STATISTICHE AVANZATE (solo admin)
@app.route("/admin/statistics")
@admin_required
def admin_statistics():
    # Classifica torrent più popolari (per download)
    popular_torrents = list(db.torrents.find().sort('download_count', -1).limit(10))
    for torrent in popular_torrents:
        torrent['_id'] = str(torrent['_id'])
    
    # Numero torrent per categoria (ultima settimana)
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    category_stats = []
    categories = ["Film", "Serie TV", "Musica", "Software", "Libri", "Documentari", "Giochi"]
    
    for category in categories:
        count = db.torrents.count_documents({
            'categories': category,
            'upload_date': {'$gte': one_week_ago}
        })
        category_stats.append({'category': category, 'count': count})
    
    # Categorie più popolari in assoluto
    all_torrents = list(db.torrents.find({}, {'categories': 1}))
    category_popularity = {}
    for torrent in all_torrents:
        for category in torrent.get('categories', []):
            category_popularity[category] = category_popularity.get(category, 0) + 1
    
    popular_categories = [{'category': k, 'count': v} for k, v in category_popularity.items()]
    popular_categories.sort(key=lambda x: x['count'], reverse=True)
    
    return render_template("admin_statistics.html",
                         popular_torrents=popular_torrents,
                         category_stats=category_stats,
                         popular_categories=popular_categories[:10])

# Download torrent (solo utenti registrati)
@app.route("/download/<torrent_id>")
@login_required
def download_torrent(torrent_id):
    try:
        torrent = db.torrents.find_one({'_id': ObjectId(torrent_id)})
        
        if not torrent:
            return "Torrent non trovato", 404
        
        db.torrents.update_one({'_id': ObjectId(torrent_id)}, {'$inc': {'download_count': 1}})
        return f"Download del torrent: {torrent['title']}"
    except:
        return "Errore nel download", 500

if __name__ == "__main__":
    app.run(debug=True)