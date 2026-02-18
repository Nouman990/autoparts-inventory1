from flask import Blueprint, request, jsonify, session, current_app
import database
from datetime import datetime
from bson import ObjectId
from functools import wraps
import os, uuid
from werkzeug.utils import secure_filename

products_bp = Blueprint('products', __name__)

ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def save_image(file):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        return f"/static/uploads/{filename}"
    return None

def serialize(p, include_links=True):
    links = p.get('ebay_links', [])
    return {
        '_id':          str(p['_id']),
        'title':        p.get('title', ''),
        'part_name':    p.get('part_name', ''),
        'part_number':  p.get('part_number', ''),
        'side':         p.get('side', ''),
        'color':        p.get('color', ''),
        'tags':         p.get('tags', []),
        'car_make':     p.get('car_make', ''),
        'car_model':    p.get('car_model', ''),
        'car_year':     p.get('car_year', ''),
        'description':  p.get('description', ''),
        'price':        p.get('price', 0),
        'shipping':     p.get('shipping', 0),
        'quantity':     p.get('quantity', 0),
        'low_stock_threshold': p.get('low_stock_threshold', 3),
        'location_text': p.get('location_text', ''),
        'images':       p.get('images', []),
        'location_images': p.get('location_images', []),
        'ebay_links':   links if include_links else [],
        'link_count':   len(links),
        'is_group':     len(links) > 1,
        'total_sold':   p.get('total_sold', 0),
        'created_at':   p.get('created_at', datetime.utcnow()).isoformat(),
        'updated_at':   p.get('updated_at', datetime.utcnow()).isoformat(),
    }

# ─── Search / List ───────────────────────────────────────────────────────────
@products_bp.route('/search', methods=['GET'])
@login_required
def search():
    q = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    if q:
        query = {'$text': {'$search': q}}
    else:
        query = {}

    total = database.db.products.count_documents(query)
    items = list(database.db.products.find(query)
        .sort('created_at', -1)
        .skip((page - 1) * per_page)
        .limit(per_page))

    return jsonify({
        'success': True,
        'products': [serialize(p, include_links=False) for p in items],
        'total': total,
        'page': page,
        'pages': max(1, -(-total // per_page))
    })

# ─── Check eBay link (new/old decision) ──────────────────────────────────────
@products_bp.route('/check-link', methods=['POST'])
@login_required
def check_link():
    """
    Receives an eBay URL.
    Returns: matches (existing products that already have this or similar links)
    so the frontend can ask user: New or Old?
    """
    data = request.get_json()
    url  = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL required'}), 400

    # check if link already exists
    existing = database.db.products.find_one(
        {'ebay_links.url': url},
        {'title': 1, 'part_name': 1, 'images': 1}
    )
    if existing:
        return jsonify({
            'already_exists': True,
            'product': {
                '_id':       str(existing['_id']),
                'title':     existing.get('title', ''),
                'part_name': existing.get('part_name', ''),
                'image':     (existing.get('images') or [''])[0]
            }
        })

    return jsonify({'already_exists': False})

# ─── Add product (NEW) ────────────────────────────────────────────────────────
@products_bp.route('/add', methods=['POST'])
@login_required
def add_product():
    # multipart/form-data
    title         = request.form.get('title', '').strip()
    part_name     = request.form.get('part_name', '').strip()
    part_number   = request.form.get('part_number', '').strip()
    side          = request.form.get('side', '').strip()
    color         = request.form.get('color', '').strip()
    tags_str      = request.form.get('tags', '').strip()
    car_make      = request.form.get('car_make', '').strip()
    car_model     = request.form.get('car_model', '').strip()
    car_year      = request.form.get('car_year', '').strip()
    description   = request.form.get('description', '').strip()
    price         = float(request.form.get('price', 0) or 0)
    shipping      = float(request.form.get('shipping', 0) or 0)
    quantity      = int(request.form.get('quantity', 1) or 1)
    low_stock     = int(request.form.get('low_stock_threshold', 3) or 3)
    location_text = request.form.get('location_text', '').strip()

    # Parse tags
    tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

    # eBay links (JSON string array from form)
    import json
    try:
        ebay_links = json.loads(request.form.get('ebay_links', '[]'))
    except:
        ebay_links = []

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    # Product images
    product_images = []
    for f in request.files.getlist('images'):
        url = save_image(f)
        if url: product_images.append(url)

    # Location images
    location_images = []
    for f in request.files.getlist('location_images'):
        url = save_image(f)
        if url: location_images.append(url)

    doc = {
        'title':        title,
        'part_name':    part_name,
        'part_number':  part_number,
        'side':         side,
        'color':        color,
        'tags':         tags,
        'car_make':     car_make,
        'car_model':    car_model,
        'car_year':     car_year,
        'description':  description,
        'price':        price,
        'shipping':     shipping,
        'quantity':     quantity,
        'low_stock_threshold': low_stock,
        'location_text': location_text,
        'images':       product_images,
        'location_images': location_images,
        'ebay_links':   ebay_links,   # [{url, account, label}]
        'total_sold':   0,
        'created_at':   datetime.utcnow(),
        'updated_at':   datetime.utcnow(),
        'created_by':   session.get('user_id', '')
    }

    pid = database.db.products.insert_one(doc).inserted_id
    return jsonify({'success': True, 'product_id': str(pid)})

# ─── Get single product ───────────────────────────────────────────────────────
@products_bp.route('/<pid>', methods=['GET'])
@login_required
def get_product(pid):
    try:
        p = database.db.products.find_one({'_id': ObjectId(pid)})
        if not p: return jsonify({'error': 'Not found'}), 404
        return jsonify({'success': True, 'product': serialize(p)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── Update product ───────────────────────────────────────────────────────────
@products_bp.route('/<pid>', methods=['PUT'])
@login_required
def update_product(pid):
    try:
        import json
        # supports both JSON and multipart
        if request.content_type and 'multipart' in request.content_type:
            data = request.form.to_dict()
            price    = float(data.get('price', 0) or 0)
            shipping = float(data.get('shipping', 0) or 0)
            quantity = int(data.get('quantity', 0) or 0)
            
            # Parse tags
            tags_str = data.get('tags', '').strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
            
            try:
                ebay_links = json.loads(data.get('ebay_links', '[]'))
            except:
                ebay_links = None

            upd = {
                'title':        data.get('title', ''),
                'part_name':    data.get('part_name', ''),
                'part_number':  data.get('part_number', ''),
                'side':         data.get('side', ''),
                'color':        data.get('color', ''),
                'tags':         tags,
                'car_make':     data.get('car_make', ''),
                'car_model':    data.get('car_model', ''),
                'car_year':     data.get('car_year', ''),
                'description':  data.get('description', ''),
                'price':        price,
                'shipping':     shipping,
                'quantity':     quantity,
                'low_stock_threshold': int(data.get('low_stock_threshold', 3) or 3),
                'location_text': data.get('location_text', ''),
                'updated_at':   datetime.utcnow()
            }
            if ebay_links is not None:
                upd['ebay_links'] = ebay_links

            # Get existing images
            p = database.db.products.find_one({'_id': ObjectId(pid)})
            existing_images = p.get('images', []) if p else []
            existing_loc    = p.get('location_images', []) if p else []

            # Add new images (append to existing)
            for f in request.files.getlist('images'):
                url = save_image(f)
                if url: existing_images.append(url)
            for f in request.files.getlist('location_images'):
                url = save_image(f)
                if url: existing_loc.append(url)

            upd['images']          = existing_images
            upd['location_images'] = existing_loc
        else:
            data = request.get_json()
            upd = {'updated_at': datetime.utcnow()}
            for field in ['title','part_name','part_number','side','color','tags','car_make','car_model',
                          'car_year','description','price','shipping','quantity',
                          'low_stock_threshold','location_text','ebay_links']:
                if field in data:
                    upd[field] = data[field]

        database.db.products.update_one({'_id': ObjectId(pid)}, {'$set': upd})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── Update quantity only ─────────────────────────────────────────────────────
@products_bp.route('/<pid>/quantity', methods=['PUT'])
@login_required
def update_quantity(pid):
    data = request.get_json()
    qty  = int(data.get('quantity', 0))
    database.db.products.update_one(
        {'_id': ObjectId(pid)},
        {'$set': {'quantity': qty, 'updated_at': datetime.utcnow()}}
    )
    return jsonify({'success': True, 'quantity': qty})

# ─── Add eBay link to existing product ───────────────────────────────────────
@products_bp.route('/<pid>/links', methods=['POST'])
@login_required
def add_link(pid):
    data = request.get_json()
    link = {
        'url':     data.get('url', '').strip(),
        'account': data.get('account', ''),   # PMC or Powergen
        'label':   data.get('label', ''),
        'added_at': datetime.utcnow().isoformat()
    }
    if not link['url']:
        return jsonify({'error': 'URL required'}), 400
    database.db.products.update_one(
        {'_id': ObjectId(pid)},
        {'$push': {'ebay_links': link}, '$set': {'updated_at': datetime.utcnow()}}
    )
    return jsonify({'success': True})

# ─── Remove eBay link ─────────────────────────────────────────────────────────
@products_bp.route('/<pid>/links', methods=['DELETE'])
@login_required
def remove_link(pid):
    data = request.get_json()
    url  = data.get('url', '')
    database.db.products.update_one(
        {'_id': ObjectId(pid)},
        {'$pull': {'ebay_links': {'url': url}}, '$set': {'updated_at': datetime.utcnow()}}
    )
    return jsonify({'success': True})

# ─── Delete product ───────────────────────────────────────────────────────────
@products_bp.route('/<pid>', methods=['DELETE'])
@login_required
def delete_product(pid):
    database.db.products.delete_one({'_id': ObjectId(pid)})
    database.db.orders.delete_many({'product_id': pid})
    return jsonify({'success': True})
