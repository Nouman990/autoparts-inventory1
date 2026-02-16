from flask import Flask, render_template, session, redirect, jsonify
from flask_cors import CORS
import os, hashlib, time
from datetime import datetime
import database

from routes.auth     import auth_bp
from routes.products import products_bp
from routes.orders   import orders_bp
from routes.dashboard import dashboard_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'autoparts-secret-2024')
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Print ALL env variables to find the right one
print("=== ALL ENV VARS ===")
for key, val in os.environ.items():
    if 'MONGO' in key.upper() or 'DB' in key.upper():
        print(f"{key} = {val[:60]}")
print("===================")

MONGO_URI = (
    os.environ.get('MONGODB_URI') or
    os.environ.get('MONGO_URL') or
    os.environ.get('MONGO_PUBLIC_URL') or
    os.environ.get('MONGODB_URL') or
    os.environ.get('MONGO_URI') or
    'mongodb://localhost:27017/autoparts'
)

if '/autoparts' not in MONGO_URI:
    MONGO_URI = MONGO_URI.rstrip('/') + '/autoparts'

print(f"USING URI: {MONGO_URI[:80]}")

db_connected = False
for i in range(30):
    try:
        database.init_db(MONGO_URI)
        db_connected = True
        print("DB CONNECTED!")
        break
    except Exception as e:
        print(f"Waiting for DB ({i+1}/30)... {str(e)[:80]}")
        time.sleep(2)

if db_connected and database.db is not None:
    try:
        if not database.db.users.find_one({'email': 'admin@autoparts.com'}):
            database.db.users.insert_one({
                'email': 'admin@autoparts.com',
                'password': hashlib.sha256('admin123'.encode()).hexdigest(),
                'name': 'Admin',
                'role': 'admin',
                'created_at': datetime.utcnow()
            })
            print("Admin created!")
        else:
            print("Admin exists!")
    except Exception as e:
        print(f"Seed error: {e}")

app.register_blueprint(auth_bp,       url_prefix='/api/auth')
app.register_blueprint(products_bp,   url_prefix='/api/products')
app.register_blueprint(orders_bp,     url_prefix='/api/orders')
app.register_blueprint(dashboard_bp,  url_prefix='/api/dashboard')

def require_login():
    return 'user_id' not in session

@app.route('/')
def index():
    if require_login(): return redirect('/login')
    return render_template('dashboard.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/products')
def products_page():
    if require_login(): return redirect('/login')
    return render_template('products.html')

@app.route('/products/add')
def add_product_page():
    if require_login(): return redirect('/login')
    return render_template('add_product.html')

@app.route('/products/<product_id>')
def product_detail_page(product_id):
    if require_login(): return redirect('/login')
    return render_template('product_detail.html', product_id=product_id)

@app.route('/orders')
def orders_page():
    if require_login(): return redirect('/login')
    return render_template('orders.html')

@app.route('/settings')
def settings_page():
    if require_login(): return redirect('/login')
    return render_template('settings.html')

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'db': 'connected' if db_connected else 'disconnected',
        'mongo_uri_set': bool(os.environ.get('MONGODB_URI')),
        'mongo_url_set': bool(os.environ.get('MONGO_URL')),
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
