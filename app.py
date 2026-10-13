import streamlit as st
import pandas as pd
import sqlite3
import os
import shutil
import glob
import json
from datetime import datetime, timedelta
from PIL import Image
import pypdfium2 as pdfium
from google import genai
from google.genai import types
import hashlib
import urllib.parse
import streamlit.components.v1 as components
import random

DB_FILE = "medical_store.db"
BACKUP_DIR = "cloud_backups"

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def trigger_dual_backup():
    try:
        backup_filename = os.path.join(BACKUP_DIR, "medical_store_mirror.db")
        shutil.copyfile(DB_FILE, backup_filename)
    except Exception as e:
        print(f"Backup error: {e}")

def restore_from_mirror_if_needed():
    mirror_file = os.path.join(BACKUP_DIR, "medical_store_mirror.db")
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        if os.path.exists(mirror_file):
            shutil.copyfile(mirror_file, DB_FILE)
    elif os.path.exists(mirror_file) and os.path.getsize(DB_FILE) < 1000:
        if os.path.getsize(mirror_file) > os.path.getsize(DB_FILE):
            shutil.copyfile(mirror_file, DB_FILE)

restore_from_mirror_if_needed()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("CREATE TABLE IF NOT EXISTS system_config (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT DEFAULT 'Neelam Technologies', super_admin_username TEXT DEFAULT 'admin', super_admin_password_hash TEXT DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', upi_id TEXT DEFAULT 'neelamtech@upi', admin_phone TEXT DEFAULT '919876543210', monthly_fee REAL DEFAULT 599.0, yearly_fee REAL DEFAULT 5999.0, enterprise_monthly_fee REAL DEFAULT 999.0, enterprise_yearly_fee REAL DEFAULT 9999.0, client_backup_target TEXT DEFAULT 'https://s3.amazonaws.com/neelam-technologies-backup-bucket', gemini_api_key TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
    conn.commit()

    c.execute("CREATE TABLE IF NOT EXISTS account_masters (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, account_name TEXT NOT NULL, group_type TEXT, opening_balance REAL DEFAULT 0.0, current_balance REAL DEFAULT 0.0, phone TEXT, address TEXT, gst_in TEXT);")
    c.execute("CREATE TABLE IF NOT EXISTS hsn_masters (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, hsn_code TEXT NOT NULL, description TEXT, gst_rate REAL DEFAULT 12.0);")
    c.execute("CREATE TABLE IF NOT EXISTS manufacturers (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, manufacturer_name TEXT NOT NULL, short_code TEXT);")
    c.execute("CREATE TABLE IF NOT EXISTS day_book (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, entry_date DATE, voucher_type TEXT, particulars TEXT, debit REAL DEFAULT 0.0, credit REAL DEFAULT 0.0, narration TEXT);")
    conn.commit()

    c.execute("PRAGMA table_info(system_config);")
    columns = [col[1] for col in c.fetchall()]
    if "admin_phone" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN admin_phone TEXT DEFAULT '919876543210';")
    if "monthly_fee" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN monthly_fee REAL DEFAULT 599.0;")
    if "yearly_fee" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN yearly_fee REAL DEFAULT 5999.0;")
    if "enterprise_monthly_fee" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN enterprise_monthly_fee REAL DEFAULT 999.0;")
    if "enterprise_yearly_fee" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN enterprise_yearly_fee REAL DEFAULT 9999.0;")
    if "client_backup_target" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN client_backup_target TEXT DEFAULT 'https://s3.amazonaws.com/neelam-technologies-backup-bucket';")
    if "gemini_api_key" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN gemini_api_key TEXT DEFAULT '';")
    conn.commit()

    c.execute("SELECT COUNT(*) FROM system_config;")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO system_config (company_name, super_admin_username, super_admin_password_hash, upi_id, admin_phone, monthly_fee, yearly_fee, enterprise_monthly_fee, enterprise_yearly_fee, client_backup_target, gemini_api_key) VALUES ('Neelam Technologies', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'neelamtech@upi', '919876543210', 599.0, 5999.0, 999.0, 9999.0, 'https://s3.amazonaws.com/neelam-technologies-backup-bucket', '');")
        conn.commit()

    c.execute("CREATE TABLE IF NOT EXISTS wholesalers (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, commission_rate REAL DEFAULT 10.0, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
    
    c.execute("CREATE TABLE IF NOT EXISTS retailers (id INTEGER PRIMARY KEY AUTOINCREMENT, wholesaler_id INTEGER, store_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, store_type TEXT DEFAULT 'SINGLE', subscription_status TEXT DEFAULT 'TRIAL', plan_expiry_date TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes', '+7 days')), payment_status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')), FOREIGN KEY(wholesaler_id) REFERENCES wholesalers(id) ON DELETE SET NULL);")

    c.execute("PRAGMA table_info(retailers);")
    r_columns = [col[1] for col in c.fetchall()]
    if "store_type" not in r_columns:
        c.execute("ALTER TABLE retailers ADD COLUMN store_type TEXT DEFAULT 'SINGLE';")
    conn.commit()

    c.execute("CREATE TABLE IF NOT EXISTS store_terminals (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, terminal_name TEXT NOT NULL, terminal_type TEXT DEFAULT 'CLIENT', username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')), FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE);")

    c.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, name TEXT NOT NULL, batch TEXT, quantity INTEGER, min_stock INTEGER DEFAULT 5, expiry_date DATE, price REAL DEFAULT 0.0, discount_percent REAL DEFAULT 0.0, gst_percent REAL DEFAULT 12.0, is_schedule_h INTEGER DEFAULT 0, FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE);")

    c.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, invoice_number TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, total_amount REAL NOT NULL, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')), FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE);")
    conn.commit()

    c.execute("SELECT COUNT(*) FROM wholesalers;")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO wholesalers (company_name, owner_name, email, phone, username, password_hash, commission_rate) VALUES ('Neelam Pharma Distributors', 'Rameshwar Ji', 'distributor@neelamtech.in', '9876543210', 'dist1', ?, 10.0);", (hash_password("dist123"),))
        conn.commit()

    c.execute("SELECT COUNT(*) FROM retailers;")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, store_type, username, password_hash, subscription_status, payment_status, plan_expiry_date) VALUES (1, 'Test1 Medical Store', 'Manoj Kumar', 'retailer@neelamtech.in', '6204313058', 'SINGLE', 'teststore', ?, 'ACTIVE', 'ACTIVE', datetime('now', '+5 hours', '+30 minutes', '+30 days'));", (hash_password("store123"),))
        conn.commit()

    conn.close()
    trigger_dual_backup()

init_db()

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
if "last_invoice" not in st.session_state:
    st.session_state.last_invoice = None

if "reset_otp_sent" not in st.session_state:
    st.session_state.reset_otp_sent = False
if "generated_otp" not in st.session_state:
    st.session_state.generated_otp = ""
if "reset_target_user" not in st.session_state:
    st.session_state.reset_target_user = ""
if "reset_target_role" not in st.session_state:
    st.session_state.reset_target_role = ""
if "reset_new_pass" not in st.session_state:
    st.session_state.reset_new_pass = ""
if "reset_wa_link" not in st.session_state:
    st.session_state.reset_wa_link = ""

conn = get_db_connection()
config_query = "SELECT company_name, super_admin_username, super_admin_password_hash, upi_id, admin_phone, monthly_fee, yearly_fee, enterprise_monthly_fee, enterprise_yearly_fee, client_backup_target, gemini_api_key FROM system_config LIMIT 1;"
config_df = pd.read_sql_query(config_query, conn)
conn.close()

if not config_df.empty:
    COMPANY_NAME = config_df.iloc[0]["company_name"]
    ADMIN_USER = config_df.iloc[0]["super_admin_username"]
    ADMIN_PASS_HASH = config_df.iloc[0]["super_admin_password_hash"]
    OWNER_UPI = config_df.iloc[0]["upi_id"]
    ADMIN_PHONE = str(config_df.iloc[0]["admin_phone"])
    MONTHLY_FEE = float(config_df.iloc[0]["monthly_fee"])
    YEARLY_FEE = float(config_df.iloc[0]["yearly_fee"])
    ENT_MONTHLY_FEE = float(config_df.iloc[0]["enterprise_monthly_fee"])
    ENT_YEARLY_FEE = float(config_df.iloc[0]["enterprise_yearly_fee"])
    CLIENT_BACKUP_TARGET = str(config_df.iloc[0]["client_backup_target"]).strip()
    MASTER_GEMINI_KEY = str(config_df.iloc[0]["gemini_api_key"]).strip()
else:
    COMPANY_NAME = "Neelam Technologies"
    ADMIN_USER = "admin"
    ADMIN_PASS_HASH = hash_password("admin")
    OWNER_UPI = "neelamtech@upi"
    ADMIN_PHONE = "919876543210"
    MONTHLY_FEE = 599.0
    YEARLY_FEE = 5999.0
    ENT_MONTHLY_FEE = 999.0
    ENT_YEARLY_FEE = 9999.0
    CLIENT_BACKUP_TARGET = "https://s3.amazonaws.com/neelam-technologies-backup-bucket"
    MASTER_GEMINI_KEY = ""

if not st.session_state.authenticated:
    st.title(f"💊 {COMPANY_NAME} - Enterprise ERP Portal")
    
    auth_tab1, auth_tab2 = st.tabs(["🔑 Login", "🔄 Secure Forgot / Reset Password"])
    
    with auth_tab1:
        with st.form("login_form"):
            username = st.text_input("Username (Admin / Distributor / Server / Counter)")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                conn = get_db_connection()
                if username == ADMIN_USER and hash_password(password) == ADMIN_PASS_HASH:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.role = "SUPER_ADMIN"
                    conn.close()
                    st.success("Admin Login Successful!")
                    st.rerun()
                else:
                    w_df = pd.read_sql_query("SELECT id, company_name, password_hash FROM wholesalers WHERE username = ?;", conn, params=(username,))
                    if not w_df.empty and hash_password(password) == w_df.iloc[0]["password_hash"]:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.role = "WHOLESALER"
                        st.session_state.user_id = int(w_df.iloc[0]["id"])
                        conn.close()
                        st.success("Distributor Login Successful!")
                        st.rerun()
                    else:
                        r_df = pd.read_sql_query("SELECT id, store_name, password_hash, store_type FROM retailers WHERE username = ?;", conn, params=(username,))
                        if not r_df.empty and hash_password(password) == r_df.iloc[0]["password_hash"]:
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.role = "RETAILER"
                            st.session_state.user_id = int(r_df.iloc[0]["id"])
                            st.session_state.terminal_type = "SERVER"
                            conn.close()
                            st.success("Retailer Server Login Successful!")
                            st.rerun()
                        else:
                            t_df = pd.read_sql_query("SELECT id, retailer_id, terminal_name, terminal_type, password_hash FROM store_terminals WHERE username = ?;", conn, params=(username,))
                            if not t_df.empty and hash_password(password) == t_df.iloc[0]["password_hash"]:
                                st.session_state.authenticated = True
                                st.session_state.username = username
                                st.session_state.role = "RETAILER"
                                st.session_state.user_id = int(t_df.iloc[0]["retailer_id"])
                                st.session_state.terminal_type = t_df.iloc[0]["terminal_type"]
                                conn.close()
                                st.success(f"Billing Counter ({t_df.iloc[0]['terminal_name']}) Login Successful!")
                                st.rerun()
                conn.close()
                st.error("Invalid Username or Password!")

    with auth_tab2:
        st.markdown("### 🔒 Secure Password Reset with User-Specific WhatsApp OTP")
        
        if not st.session_state.reset_otp_sent:
            with st.form("request_otp_form"):
                f_role = st.selectbox("Select Account Type", ["Retailer (Medical Store Server)", "Billing Counter Terminal", "Distributor (Wholesaler)", "Super Admin"])
                f_user = st.text_input("Username / Email")
                f_new_pass = st.text_input("New Password", type="password")
                f_confirm = st.text_input("Confirm New Password", type="password")
                
                req_otp_btn = st.form_submit_button("💬 Send OTP to User's WhatsApp")
                
                if req_otp_btn:
                    if not f_user or not f_new_pass:
                        st.warning("Please fill in all fields.")
                    elif f_new_pass != f_confirm:
                        st.error("Passwords do not match!")
                    else:
                        conn = get_db_connection()
                        c = conn.cursor()
                        target_phone = None
                        exists = False
                        
                        if f_role == "Super Admin":
                            if f_user == ADMIN_USER:
                                exists = True
                                target_phone = ADMIN_PHONE
                        elif f_role == "Distributor (Wholesaler)":
                            c.execute("SELECT phone FROM wholesalers WHERE username = ? OR email = ?;", (f_user, f_user))
                            row = c.fetchone()
                            if row and row[0] and str(row[0]).strip() != "":
                                exists = True
                                target_phone = str(row[0]).strip()
                        elif f_role == "Billing Counter Terminal":
                            c.execute("SELECT r.phone FROM store_terminals st JOIN retailers r ON st.retailer_id = r.id WHERE st.username = ?;", (f_user,))
                            row = c.fetchone()
                            if row and row[0] and str(row[0]).strip() != "":
                                exists = True
                                target_phone = str(row[0]).strip()
                        else:
                            c.execute("SELECT phone FROM retailers WHERE username = ? OR email = ?;", (f_user, f_user))
                            row = c.fetchone()
                            if row and row[0] and str(row[0]).strip() != "":
                                exists = True
                                target_phone = str(row[0]).strip()
                        conn.close()
                        
                        if exists and target_phone:
                            generated = str(random.randint(100000, 999999))
                            st.session_state.generated_otp = generated
                            st.session_state.reset_target_user = f_user
                            st.session_state.reset_target_role = f_role
                            st.session_state.reset_new_pass = f_new_pass
                            
                            otp_msg = f"🔐 *Password Reset OTP*\nYour verification OTP for {COMPANY_NAME} account ({f_user}) is: *{generated}*\nDo not share this OTP with anyone."
                            encoded_otp_msg = urllib.parse.quote(otp_msg)
                            clean_target_phone = "".join(filter(str.isdigit, target_phone))
                            st.session_state.reset_wa_link = f"https://wa.me/{clean_target_phone}?text={encoded_otp_msg}"
                            
                            st.session_state.reset_otp_sent = True
                            st.success(f"📲 OTP generated for user phone ({target_phone})! Click the WhatsApp button below to open chat and send OTP.")
                            st.rerun()
                        else:
                            st.error("❌ User not found OR registered mobile number is missing for this user!")
        else:
            st.warning("⚠️ **Step 2:** Click the button below to open WhatsApp with the user's registered number:")
            st.markdown(
                f'<div style="margin-bottom: 20px; text-align: center;">'
                f'<a href="{st.session_state.reset_wa_link}" target="_blank" style="text-decoration: none;">'
                f'<button style="background-color:#25D366; color:white; padding:12px 24px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:16px;">'
                f'💬 Click here to open WhatsApp & get OTP</button></a></div>',
                unsafe_allow_html=True
            )
            
            st.info(f"💡 **Developer Note / Quick Test OTP:** `{st.session_state.generated_otp}`")
            
            with st.form("verify_otp_form"):
                entered_otp = st.text_input("Enter 6-Digit WhatsApp OTP", placeholder="Enter 6-digit code")
                verify_btn = st.form_submit_button("✅ Verify OTP & Update Password", type="primary")
                
                if verify_btn:
                    if entered_otp.strip() == st.session_state.generated_otp:
                        conn = get_db_connection()
                        c = conn.cursor()
                        
                        if st.session_state.reset_target_role == "Super Admin":
                            c.execute("UPDATE system_config SET super_admin_password_hash = ? WHERE id = 1;", (hash_password(st.session_state.reset_new_pass),))
                        elif st.session_state.reset_target_role == "Distributor (Wholesaler)":
                            c.execute("UPDATE wholesalers SET password_hash = ? WHERE username = ? OR email = ?;", (hash_password(st.session_state.reset_new_pass), st.session_state.reset_target_user, st.session_state.reset_target_user))
                        elif st.session_state.reset_target_role == "Billing Counter Terminal":
                            c.execute("UPDATE store_terminals SET password_hash = ? WHERE username = ?;", (hash_password(st.session_state.reset_new_pass), st.session_state.reset_target_user))
                        else:
                            c.execute("UPDATE retailers SET password_hash = ? WHERE username = ? OR email = ?;", (hash_password(st.session_state.reset_new_pass), st.session_state.reset_target_user, st.session_state.reset_target_user))
                            
                        conn.commit()
                        conn.close()
                        trigger_dual_backup()
                        
                        st.session_state.reset_otp_sent = False
                        st.session_state.generated_otp = ""
                        st.success("🎉 Password successfully reset and updated securely via WhatsApp OTP verification!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid OTP! Please enter the correct 6-digit code.")
            
            if st.button("🔄 Cancel / Restart Reset"):
                st.session_state.reset_otp_sent = False
                st.rerun()
                
    st.stop()

st.sidebar.title(f"User: {st.session_state.username}")
sidebar_info_text = f"Role: {st.session_state.role} | Terminal: {st.session_state.terminal_type}"
st.sidebar.info(sidebar_info_text)
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.cart = []
    st.session_state.terminal_type = "SERVER"
    st.rerun()

# ==============================================================================
# 📦 WHOLESALER / DISTRIBUTOR DASHBOARD
# ==========================================
elif st.session_state.role == "WHOLESALER":
    conn = get_db_connection()
    w_info = pd.read_sql_query("SELECT company_name, commission_rate FROM wholesalers WHERE id = ?;", conn, params=(st.session_state.user_id,))
    w_name = w_info.iloc[0]["company_name"]
    w_comm = w_info.iloc[0]["commission_rate"]
    
    st.title(f"📦 Distributor Support Portal: {w_name}")
    st.info(f"Your Commission Share: **{w_comm}%** | Role: Ground Support & Retailer Management")

    tab1, tab2, tab3, tab4 = st.tabs(["📂 My Network Retailers", "➕ Register New Retailer", "✅ Payment Approvals", "✏️ Edit Store Details"])

    with tab1:
        st.markdown("### Retailers assigned under your support network")
        my_ret = pd.read_sql_query("SELECT id, store_name, owner_name, email, phone, store_type, subscription_status, payment_status, plan_expiry_date, created_at FROM retailers WHERE wholesaler_id = ? ORDER BY store_name ASC;", conn, params=(st.session_state.user_id,))
        if not my_ret.empty:
            st.dataframe(my_ret, use_container_width=True)
        else:
            st.info("No retailers registered under your network yet.")

    with tab2:
        st.markdown("### Register New Medical Store (Trial Setup)")
        with st.form("add_retailer_form"):
            s_name = st.text_input("Medical Store Name")
            o_name = st.text_input("Retailer Owner Name")
            email = st.text_input("Retailer Email (Unique)")
            phone = st.text_input("Phone Number (for WhatsApp OTP)")
            s_type = st.selectbox("Store Architecture / System Type (Trial Phase Choice)", ["SINGLE (Single System Setup)", "ENTERPRISE (Multi System Server/Client Setup)"])
            r_user = st.text_input("Main Server Username")
            r_pass = st.text_input("Main Server Password", type="password")
            
            submit_ret = st.form_submit_button("Register Store (7-Days Free Trial)")
            if submit_ret:
                if s_name and email and r_user and r_pass and phone:
                    try:
                        c = conn.cursor()
                        store_category = "ENTERPRISE" if "ENTERPRISE" in s_type else "SINGLE"
                        c.execute("INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, store_type, username, password_hash, subscription_status, payment_status,
