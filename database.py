from pymongo import MongoClient, TEXT
import os

client = None
db = None

def init_db(uri):
    global client, db
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db_name = uri.split('/')[-1].split('?')[0] or 'autoparts'
    db = client[db_name]
    client.server_info()
    _create_indexes()
    print(f"✅ DB connected: {db_name}")
    return db

def _create_indexes():
    # Full-text search on products
    try:
        db.products.create_index([
            ('title', TEXT),
            ('part_name', TEXT),
            ('part_number', TEXT),
            ('car_make', TEXT),
            ('car_model', TEXT),
            ('car_year', TEXT),
            ('description', TEXT),
        ], name='product_text_search')
    except:
        pass  # index may already exist

    db.products.create_index('created_at')
    db.orders.create_index('product_id')
    db.orders.create_index('created_at')
    db.users.create_index('email', unique=True)
    print("✅ Indexes created")
