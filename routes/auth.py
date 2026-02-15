from flask import Blueprint, request, jsonify, session
import database, hashlib
from datetime import datetime
from bson import ObjectId
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    user = database.db.users.find_one({'email': email, 'password': password})
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401
    session['user_id'] = str(user['_id'])
    session['name']    = user.get('name', '')
    session['role']    = user.get('role', 'user')
    return jsonify({'success': True, 'name': user.get('name', ''), 'role': user.get('role', 'user')})

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({'user_id': session['user_id'], 'name': session['name'], 'role': session['role']})

@auth_bp.route('/users', methods=['GET'])
@login_required
def list_users():
    users = list(database.db.users.find({}, {'password': 0}))
    for u in users: u['_id'] = str(u['_id'])
    return jsonify({'users': users})

@auth_bp.route('/users', methods=['POST'])
@login_required
def create_user():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    if database.db.users.find_one({'email': email}):
        return jsonify({'error': 'Email already exists'}), 400
    database.db.users.insert_one({
        'email': email,
        'password': hashlib.sha256(data.get('password', 'pass123').encode()).hexdigest(),
        'name': data.get('name', ''),
        'role': data.get('role', 'user'),
        'created_at': datetime.utcnow()
    })
    return jsonify({'success': True})

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    old_pw = hashlib.sha256(data.get('old_password', '').encode()).hexdigest()
    user = database.db.users.find_one({'_id': ObjectId(session['user_id']), 'password': old_pw})
    if not user:
        return jsonify({'error': 'Wrong current password'}), 400
    new_pw = hashlib.sha256(data.get('new_password', '').encode()).hexdigest()
    database.db.users.update_one({'_id': user['_id']}, {'$set': {'password': new_pw}})
    return jsonify({'success': True})
