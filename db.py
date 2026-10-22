import sqlite3
import os
import hashlib

def setup_local_environment():
    try:
        folder_path = r"C:\PharmaFlow_Data"
        os.makedirs(folder_path, exist_ok=True)
    except Exception:
        folder_path = os.path.join(os.path.expanduser("~"), "PharmaFlow_Data")
        os.makedirs(folder_path, exist_ok=True)
    return folder_path

LOCAL_FOLDER = setup_local_environment()
DB_FILE = os.path.join(LOCAL_FOLDER, "medical_store.db")

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            company_name TEXT DEFAULT 'Neelam Technologies', 
            super_admin_username TEXT DEFAULT 'admin', 
            super_admin_password_hash TEXT DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 
            upi_id TEXT DEFAULT 'neelamtech@upi', 
            admin_phone TEXT DEFAULT '919876543210',
            gemini_api_key TEXT DEFAULT ''
        );""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS hierarchy_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        );""")

        c.execute("""CREATE TABLE IF NOT EXISTS retailers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            assigned_sse_id INTEGER, 
            store_name TEXT NOT NULL, 
            owner_name TEXT, 
            email TEXT UNIQUE NOT NULL, 
            phone TEXT, 
            username TEXT UNIQUE NOT NULL, 
            password_hash TEXT NOT NULL, 
            store_type TEXT DEFAULT 'SINGLE', 
            subscription_status TEXT DEFAULT 'TRIAL', 
            plan_expiry_date TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes', '+30 days')), 
            payment_status TEXT DEFAULT 'ACTIVE',
            gstin TEXT DEFAULT '27AAAAA0000A1Z5'
        );""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS store_terminals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            retailer_id INTEGER, 
            terminal_name TEXT NOT NULL, 
            terminal_type TEXT DEFAULT 'CLIENT', 
            username TEXT UNIQUE NOT NULL, 
            password_hash TEXT NOT NULL
        );""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            retailer_id INTEGER, 
            name TEXT NOT NULL, 
            batch TEXT, 
            quantity INTEGER, 
            price REAL DEFAULT 0.0,
            barcode TEXT DEFAULT '',
            gst_rate REAL DEFAULT 12.0
        );""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            retailer_id INTEGER, 
            invoice_number TEXT NOT NULL, 
            total_amount REAL NOT NULL, 
            cgst REAL DEFAULT 0.0,
            sgst REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        );""")

        c.execute("""CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            retailer_id INTEGER,
            supplier_name TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT,
            gstin TEXT,
            outstanding_balance REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        );""")

        c.execute("""CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            retailer_id INTEGER,
            supplier_id INTEGER,
            po_number TEXT NOT NULL,
            items_summary TEXT NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        );""")

        # Schedule H1 Register Table for Legal Compliance
        c.execute("""CREATE TABLE IF NOT EXISTS schedule_h1_register (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            retailer_id INTEGER,
            patient_name TEXT NOT NULL,
            patient_address TEXT,
            doctor_name TEXT NOT NULL,
            doctor_qualification TEXT,
            medicine_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            prescription_date TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        );""")
        
        conn.commit()

        c.execute("SELECT COUNT(*) FROM system_config;")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO system_config (company_name, super_admin_username, super_admin_password_hash) VALUES ('Neelam Technologies', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918');")
            conn.commit()

        conn.close()
    except Exception as e:
        print(f"Database Init Error: {e}")
