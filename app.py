from flask import Flask, render_template, session, redirect, url_for, jsonify
from flask_cors import CORS
import os, hashlib, time
from datetime import datetime
import database

# ── Routes ──────────────────────────────────────────────────────────────────
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# ── DB init ─────────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/autoparts')

for i in range(30):
    try:
        database.init_db(MONGO_URI)
        break
    except Exception as e:
        print(f"⏳ Waiting for DB ({i+1}/30)...")
        time.sleep(2)

# ── Seed admin ───────────────────────────────────────────────────────────────
try:
    if not database.db.users.find_one({'email': 'admin@autoparts.com'}):
        database.db.users.insert_one({
            'email': 'admin@autoparts.com',
            'password': hashlib.sha256('admin123'.encode()).hexdigest(),
            'name': 'Admin',
            'role': 'admin',
            'created_at': datetime.utcnow()
        })
        print("✅ Admin created: admin@autoparts.com / admin123")
except Exception as e:
    print(f"Seed error: {e}")

# ── Blueprints ───────────────────────────────────────────────────────────────
app.register_blueprint(auth_bp,      url_prefix='/api/auth')
app.register_blueprint(products_bp,  url_prefix='/api/products')
app.register_blueprint(orders_bp,    url_prefix='/api/orders')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

# ── Pages ────────────────────────────────────────────────────────────────────
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
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
