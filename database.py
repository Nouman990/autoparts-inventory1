from pymongo import MongoClient, TEXT
import os

client = None
db = None

def init_db(uri):
    global client, db
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    # Force connection test
    client.admin.command('ping')
    db_name = uri.split('/')[-1].split('?')[0]
    if not db_name or db_name == '27017':
        db_name = 'autoparts'
    db = client[db_name]
    print(f"DB connected: {db_name}")
    _create_indexes()
    return db

def _create_indexes():
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
        pass
    try:
        db.products.create_index('created_at')
        db.orders.create_index('product_id')
        db.orders.create_index('created_at')
        db.users.create_index('email', unique=True)
    except:
        pass
    print("Indexes ready")
