import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from datetime import datetime, timedelta
from PIL import Image
from google import genai
from google.genai import types
import hashlib
import urllib.parse
import random

# ================= AUTOMATIC C DRIVE & DESKTOP SETUP =================
def setup_local_environment(store_name="PharmaFlow"):
    try:
        # 1. C Drive mein secure folder banana
        folder_path = r"C:\PharmaFlow_Data"
        os.makedirs(folder_path, exist_ok=True)
    except Exception:
        # Cloud ya permission restricted environment ke liye fallback path
        folder_path = os.path.join(os.path.expanduser("~"), "PharmaFlow_Data")
        os.makedirs(folder_path, exist_ok=True)
        
    # 2. Desktop par shortcut URL icon automatically create karna
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.exists(desktop):
            shortcut_path = os.path.join(desktop, f"PharmaFlow - {store_name}.url")
            app_url = "https://share.streamlit.io"  # Yahan apna live app URL daal sakte hain
            shortcut_content = f"""[InternetShortcut]
URL={app_url}
IconIndex=0
"""
            if not os.path.exists(shortcut_path):
                with open(shortcut_path, "w") as f:
                    f.write(shortcut_content)
    except Exception:
        pass
        
    return folder_path

# Local database path setup
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
        
        c.execute("CREATE TABLE IF NOT EXISTS system_config (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT DEFAULT 'Neelam Technologies', super_admin_username TEXT DEFAULT 'admin', super_admin_password_hash TEXT DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', upi_id TEXT DEFAULT 'neelamtech@upi', admin_phone TEXT DEFAULT '919876543210', monthly_fee REAL DEFAULT 599.0, yearly_fee REAL DEFAULT 5999.0, enterprise_monthly_fee REAL DEFAULT 999.0, enterprise_yearly_fee REAL DEFAULT 9999.0, client_backup_target TEXT DEFAULT 'https://s3.amazonaws.com/neelam-technologies-backup-bucket', gemini_api_key TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
        conn.commit()

        c.execute("CREATE TABLE IF NOT EXISTS account_masters (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, account_name TEXT NOT NULL, group_type TEXT, opening_balance REAL DEFAULT 0.0, current_balance REAL DEFAULT 0.0, phone TEXT, address TEXT, gst_in TEXT);")
        c.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, name TEXT NOT NULL, batch TEXT, quantity INTEGER, min_stock INTEGER DEFAULT 5, expiry_date DATE, price REAL DEFAULT 0.0, discount_percent REAL DEFAULT 0.0, gst_percent REAL DEFAULT 12.0, is_schedule_h INTEGER DEFAULT 0);")
        c.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, invoice_number TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, total_amount REAL NOT NULL, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
        c.execute("CREATE TABLE IF NOT EXISTS wholesalers (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, commission_rate REAL DEFAULT 10.0, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
        c.execute("CREATE TABLE IF NOT EXISTS retailers (id INTEGER PRIMARY KEY AUTOINCREMENT, wholesaler_id INTEGER, store_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, store_type TEXT DEFAULT 'SINGLE', subscription_status TEXT DEFAULT 'TRIAL', plan_expiry_date TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes', '+7 days')), payment_status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
        conn.commit()
        conn.close()
    except Exception as e:
        pass

init_db()

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None
    st.session_state.terminal_type = "SERVER"

if "cart" not in st.session_state:
    st.session_state.cart = []
if "scanned_data" not in st.session_state:
    st.session_state.scanned_data = None

# ================= BRANDED HEADER FUNCTION =================
def render_header():
    st.markdown("""
        <div style="text-align: center; padding: 10px; background-color: #f8f9fa; border-radius: 10px; margin-bottom: 15px;">
            <h1 style="color: #1f77b4; margin-bottom: 0px; font-size: 32px;">💊 PharmaFlow</h1>
            <p style="font-size: 10px; color: #6c757d; margin-top: 2px; letter-spacing: 1.5px; font-weight: 600;">POWERED BY NEELAM TECHNOLOGIES</p>
        </div>
    """, unsafe_allow_html=True)

if not st.session_state.authenticated:
    render_header()
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if username == "admin" and hash_password(password) == hash_password("admin"):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "SUPER_ADMIN"
                
                # Auto trigger desktop shortcut & C drive folder creation on login
                setup_local_environment("Admin_Portal")
                st.success("Login Successful! Desktop shortcut & C Drive data folder ready.")
                st.rerun()
            else:
                st.error("Invalid Credentials")
    st.stop()
else:
    render_header()
    st.sidebar.title(f"User: {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()
    st.write("Welcome to PharmaFlow Dashboard! Data is securely synced to your local C Drive folder.")
