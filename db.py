import sqlite3
import os
import hashlib

BACKUP_DIR = "cloud_backups"
os.makedirs(BACKUP_DIR, exist_ok=True)
DB_FILE = os.path.join(BACKUP_DIR, "medical_store.db")

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # System Config Table
    c.execute("""CREATE TABLE IF NOT EXISTS system_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_name TEXT DEFAULT 'Neelam Technologies', 
        super_admin_username TEXT DEFAULT 'admin', 
        super_admin_password_hash TEXT DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 
        upi_id TEXT DEFAULT 'neelamtech@upi', 
        admin_phone TEXT DEFAULT '919876543210', 
        monthly_fee REAL DEFAULT 599.0, 
        yearly_fee REAL DEFAULT 5999.0, 
        enterprise_monthly_fee REAL DEFAULT 999.0, 
        enterprise_yearly_fee REAL DEFAULT 9999.0, 
        client_backup_target TEXT DEFAULT 'https://s3.amazonaws.com/neelam-technologies-backup-bucket', 
        gemini_api_key TEXT DEFAULT '', 
        updated_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
    );""")
    
    # Account Masters Table
    c.execute("""CREATE TABLE IF NOT EXISTS account_masters (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        retailer_id INTEGER, 
        account_name TEXT NOT NULL, 
        group_type TEXT, 
        opening_balance REAL DEFAULT 0.0, 
        current_balance REAL DEFAULT 0.0, 
        phone TEXT, 
        address TEXT, 
        gst_in TEXT
    );""")
    
    # Inventory Table
    c.execute("""CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        retailer_id INTEGER, 
        name TEXT NOT NULL, 
        batch TEXT, 
        quantity INTEGER, 
        min_stock INTEGER DEFAULT 5, 
        expiry_date DATE, 
        price REAL DEFAULT 0.0, 
        discount_percent REAL DEFAULT 0.0, 
        gst_percent REAL DEFAULT 12.0, 
        is_schedule_h INTEGER DEFAULT 0
    );""")
    
    # Sales Table
    c.execute("""CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        retailer_id INTEGER, 
        invoice_number TEXT NOT NULL, 
        customer_name TEXT, 
        customer_phone TEXT, 
        total_amount REAL NOT NULL, 
        created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
    );""")
    
    # Wholesalers Table
    c.execute("""CREATE TABLE IF NOT EXISTS wholesalers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_name TEXT NOT NULL, 
        owner_name TEXT, 
        email TEXT UNIQUE NOT NULL, 
        phone TEXT, 
        username TEXT UNIQUE NOT NULL, 
        password_hash TEXT NOT NULL, 
        commission_rate REAL DEFAULT 10.0, 
        created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
    );""")
    
    # Retailers Table
    c.execute("""CREATE TABLE IF NOT EXISTS retailers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        wholesaler_id INTEGER, 
        store_name TEXT NOT NULL, 
        owner_name TEXT, 
        email TEXT UNIQUE NOT NULL, 
        phone TEXT, 
        username TEXT UNIQUE NOT NULL, 
        password_hash TEXT NOT NULL, 
        store_type TEXT DEFAULT 'SINGLE', 
        subscription_status TEXT DEFAULT 'TRIAL', 
        plan_expiry_date TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes', '+7 days')), 
        payment_status TEXT DEFAULT 'PENDING', 
        created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
    );""")
    
    conn.commit()
    conn.close()
