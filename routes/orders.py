from flask import Blueprint, request, jsonify, session
import database
from datetime import datetime
from bson import ObjectId
from functools import wraps

orders_bp = Blueprint('orders', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

def serialize(o):
    return {
        '_id':        str(o['_id']),
        'product_id': o.get('product_id', ''),
        'product_title': o.get('product_title', ''),
        'product_image': o.get('product_image', ''),
        'quantity_sold': o.get('quantity_sold', 1),
        'sale_price':   o.get('sale_price', 0),
        'account':      o.get('account', ''),        # PMC / Powergen
        'ebay_order_id': o.get('ebay_order_id', ''),
        'buyer_name':   o.get('buyer_name', ''),
        'note':         o.get('note', ''),
        'added_by':     o.get('added_by', ''),
        'created_at':   o.get('created_at', datetime.utcnow()).isoformat(),
    }

# ─── Add order (manually) ─────────────────────────────────────────────────────
@orders_bp.route('/add', methods=['POST'])
@login_required
def add_order():
    data = request.get_json()
    pid  = data.get('product_id', '')
    qty  = int(data.get('quantity_sold', 1))

    if not pid:
        return jsonify({'error': 'product_id required'}), 400

    # Get product info
    try:
        product = database.db.products.find_one({'_id': ObjectId(pid)})
    except:
        return jsonify({'error': 'Invalid product id'}), 400

    if not product:
        return jsonify({'error': 'Product not found'}), 404

    current_qty = product.get('quantity', 0)
    new_qty     = max(0, current_qty - qty)

    # Insert order
    order_id = database.db.orders.insert_one({
        'product_id':    pid,
        'product_title': product.get('title', ''),
        'product_image': (product.get('images') or [''])[0],
        'quantity_sold': qty,
        'sale_price':    float(data.get('sale_price', product.get('price', 0))),
        'account':       data.get('account', ''),
        'ebay_order_id': data.get('ebay_order_id', ''),
        'buyer_name':    data.get('buyer_name', ''),
        'note':          data.get('note', ''),
        'added_by':      session.get('name', ''),
        'created_at':    datetime.utcnow()
    }).inserted_id

    # Reduce quantity on product
    database.db.products.update_one(
        {'_id': product['_id']},
        {'$set': {'quantity': new_qty, 'updated_at': datetime.utcnow()},
         '$inc': {'total_sold': qty}}
    )

    return jsonify({
        'success':      True,
        'order_id':     str(order_id),
        'new_quantity': new_qty,
        'qty_reduced':  qty
    })

# ─── List orders ───────────────────────────────────────────────────────────────
@orders_bp.route('/list', methods=['GET'])
@login_required
def list_orders():
    pid      = request.args.get('product_id')
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    query = {}
    if pid: query['product_id'] = pid

    total  = database.db.orders.count_documents(query)
    orders = list(database.db.orders.find(query)
        .sort('created_at', -1)
        .skip((page - 1) * per_page)
        .limit(per_page))

    return jsonify({
        'success': True,
        'orders':  [serialize(o) for o in orders],
        'total':   total
    })

# ─── Delete order (and restore qty) ──────────────────────────────────────────
@orders_bp.route('/<oid>', methods=['DELETE'])
@login_required
def delete_order(oid):
    order = database.db.orders.find_one({'_id': ObjectId(oid)})
    if not order:
        return jsonify({'error': 'Not found'}), 404

    qty = order.get('quantity_sold', 1)
    pid = order.get('product_id', '')

    # Restore quantity
    try:
        database.db.products.update_one(
            {'_id': ObjectId(pid)},
            {'$inc': {'quantity': qty, 'total_sold': -qty},
             '$set': {'updated_at': datetime.utcnow()}}
        )
    except: pass

    database.db.orders.delete_one({'_id': ObjectId(oid)})
    return jsonify({'success': True, 'qty_restored': qty})
