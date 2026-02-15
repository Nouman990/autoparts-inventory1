from flask import Blueprint, jsonify, session
import database
from datetime import datetime, timedelta
from functools import wraps

dashboard_bp = Blueprint('dashboard', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

@dashboard_bp.route('/stats', methods=['GET'])
@login_required
def stats():
    total_products  = database.db.products.count_documents({})
    total_orders    = database.db.orders.count_documents({})
    out_of_stock    = database.db.products.count_documents({'quantity': 0})

    # Low stock (qty > 0 but <= threshold)
    all_products = list(database.db.products.find({}, {'quantity': 1, 'low_stock_threshold': 1}))
    low_stock = sum(1 for p in all_products
                    if 0 < p.get('quantity', 0) <= p.get('low_stock_threshold', 3))

    # Total inventory value
    pipeline = [{'$group': {'_id': None, 'value': {'$sum': {'$multiply': ['$price', '$quantity']}}}}]
    val = list(database.db.products.aggregate(pipeline))
    total_value = val[0]['value'] if val else 0

    # Recent orders (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_order_count = database.db.orders.count_documents({'created_at': {'$gte': week_ago}})

    # Recent products
    recent_products = list(database.db.products.find()
        .sort('created_at', -1).limit(5))
    recent_list = [{
        '_id':   str(p['_id']),
        'title': p.get('title', ''),
        'part_name': p.get('part_name', ''),
        'quantity': p.get('quantity', 0),
        'price': p.get('price', 0),
        'image': (p.get('images') or [''])[0],
        'link_count': len(p.get('ebay_links', []))
    } for p in recent_products]

    # Low stock alert list
    low_stock_list = list(database.db.products.find(
        {'$expr': {'$and': [
            {'$gt': ['$quantity', 0]},
            {'$lte': ['$quantity', '$low_stock_threshold']}
        ]}}
    ).limit(10))
    low_list = [{
        '_id':   str(p['_id']),
        'title': p.get('title', ''),
        'quantity': p.get('quantity', 0),
        'low_stock_threshold': p.get('low_stock_threshold', 3),
        'image': (p.get('images') or [''])[0]
    } for p in low_stock_list]

    # Out of stock list
    oos_list = list(database.db.products.find({'quantity': 0}).limit(10))
    oos = [{
        '_id':   str(p['_id']),
        'title': p.get('title', ''),
        'image': (p.get('images') or [''])[0]
    } for p in oos_list]

    # Recent orders
    recent_orders = list(database.db.orders.find().sort('created_at', -1).limit(5))
    r_orders = [{
        '_id':           str(o['_id']),
        'product_title': o.get('product_title', ''),
        'product_image': o.get('product_image', ''),
        'quantity_sold': o.get('quantity_sold', 1),
        'sale_price':    o.get('sale_price', 0),
        'account':       o.get('account', ''),
        'created_at':    o.get('created_at', datetime.utcnow()).isoformat()
    } for o in recent_orders]

    return jsonify({
        'success': True,
        'stats': {
            'total_products': total_products,
            'total_orders': total_orders,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'total_value': round(total_value, 2),
            'recent_orders_7d': recent_order_count,
        },
        'recent_products': recent_list,
        'low_stock_list': low_list,
        'out_of_stock_list': oos,
        'recent_orders': r_orders
    })
