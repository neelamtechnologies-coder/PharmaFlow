import sqlite3
import os
import hashlib
import base64

def setup_local_environment():
    try:
        folder_path = r"C:\PharmaFlow_Data"
        os.makedirs(folder_path, exist_ok=True)
    except Exception:
        folder_path = os.path.join(os.path.expanduser("~"), "PharmaFlow_Data")
        os.makedirs(folder_path, exist_ok=True)
    
    # Generate a valid .ico file using base64 so Windows recognizes it properly
    ico_path = os.path.join(folder_path, "icon.ico")
    if not os.path.exists(ico_path):
        try:
            # Valid minimal 16x16 ICO file encoded in base64
            ico_base64 = (
                "AAABAAEAEBAQAAEABAAoAQAAFgAAACgAAAAQAAAAIAAAAAEAABAAAAAAAAAA"
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAP//////////////////////////////////"
                "////////////////////////////////////////////////////////////////////"
                "////////////////////////////////////////////////////////////////////"
                "////////////////////////////////////////////////////////////////////"
                "////////////////////////////////////////////////////////////////////"
                "//////////////////////////////////8="
            )
            with open(ico_path, "wb") as f:
                f.write(base64.b64decode(ico_base64))
        except Exception:
            pass

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
            subscription_status TEXT DEFAULT 'ACTIVE', 
            plan_expiry_date TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes', '+30 days')), 
            payment_status TEXT DEFAULT 'ACTIVE'
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
            price REAL DEFAULT 0.0
        );""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            retailer_id INTEGER, 
            invoice_number TEXT NOT NULL, 
            total_amount REAL NOT NULL, 
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
