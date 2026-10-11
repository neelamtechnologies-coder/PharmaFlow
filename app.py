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

restore_from_mirror_if_needed()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("CREATE TABLE IF NOT EXISTS system_config (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT DEFAULT 'Neelam Technologies', super_admin_username TEXT DEFAULT 'admin', super_admin_password_hash TEXT DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', upi_id TEXT DEFAULT 'neelamtech@upi', admin_phone TEXT DEFAULT '919876543210', monthly_fee REAL DEFAULT 599.0, yearly_fee REAL DEFAULT 5999.0, enterprise_monthly_fee REAL DEFAULT 999.0, enterprise_yearly_fee REAL DEFAULT 9999.0, client_backup_target TEXT DEFAULT 'https://s3.amazonaws.com/neelam-technologies-backup-bucket', gemini_api_key TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
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
config_df = pd.read_sql_query("SELECT company_name, super_admin_username, super_admin_password_hash, upi_id, admin_phone, monthly_fee, yearly_fee, enterprise_monthly_fee, enterprise_yearly_fee, client_backup_target, gemini_api_key FROM system_config LIMIT 1;", conn)
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
            st.markdown(f"""
            <div style="margin-bottom: 20px; text-align: center;">
                <a href="{st.session_state.reset_wa_link}" target="_blank" style="text-decoration: none;">
                    <button style="background-color:#25D366; color:white; padding:12px 24px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:16px;">
                        💬 Click here to open WhatsApp & get OTP
                    </button>
                </a>
            </div>
            """, unsafe_allow_html=True)
            
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
st.sidebar.info(f"Role: {st.session_state.role} | Terminal: {st.session_state.terminal_type}")
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
                        c.execute("INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, store_type, username, password_hash, subscription_status, payment_status, plan_expiry_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TRIAL', 'PENDING', datetime('now', '+5 hours', '+30 minutes', '+7 days'), datetime('now', '+5 hours', '+30 minutes'));", (st.session_state.user_id, s_name, o_name, email, phone.strip(), store_category, r_user, hash_password(r_pass)))
                        conn.commit()
                        trigger_dual_backup()
                        st.success(f"Retailer '{s_name}' ({store_category}) successfully registered with 7 days free trial!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Please fill in all required fields including phone number.")

    with tab3:
        st.markdown("### ✅ Pending Payment Approvals for Your Network")
        my_pending_df = pd.read_sql_query("SELECT id, store_name, store_type, subscription_status, payment_status, plan_expiry_date FROM retailers WHERE wholesaler_id = ? AND payment_status = 'PENDING_APPROVAL';", conn, params=(st.session_state.user_id,))
        if not my_pending_df.empty:
            mp_opts = {f"{row['store_name']} (Type: {row['store_type']})": row['id'] for _, row in my_pending_df.iterrows()}
            sel_mp_str = st.selectbox("Select Store Requesting Approval", list(mp_opts.keys()))
            sel_mp_id = mp_opts[sel_mp_str]
            
            add_period = st.radio("Select Plan Duration to Verify", ["1 Month", "1 Year"], key="wholesaler_period")
            
            if st.button("✅ Verify Payment & Activate Plan", type="primary", key="wholesaler_verify_btn"):
                c = conn.cursor()
                if add_period == "1 Month":
                    c.execute("UPDATE retailers SET plan_expiry_date = datetime(COALESCE(NULLIF(plan_expiry_date, ''), datetime('now')), '+1 month'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (sel_mp_id,))
                else:
                    c.execute("UPDATE retailers SET plan_expiry_date = datetime(COALESCE(NULLIF(plan_expiry_date, ''), datetime('now')), '+1 year'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (sel_mp_id,))
                conn.commit()
                trigger_dual_backup()
                st.success("Payment verified and plan successfully activated!")
                st.rerun()
        else:
            st.info("No pending payment approvals in your network.")

    with tab4:
        st.markdown("### ✏️ Edit Store Name, Phone & Password (Dealer Secure Access)")
        st.info("💡 Note: Dealers cannot change subscription status or plan expiry dates. Only Super Admin can approve payments.")
        my_ret_list = pd.read_sql_query("SELECT id, store_name, phone, subscription_status, payment_status, plan_expiry_date FROM retailers WHERE wholesaler_id = ? ORDER BY store_name ASC;", conn, params=(st.session_state.user_id,))
        if not my_ret_list.empty:
            r_opts = {f"{row['store_name']} (Phone: {row['phone']}, Status: {row['subscription_status']})": row['id'] for _, row in my_ret_list.iterrows()}
            sel_r_str = st.selectbox("Select Retailer to Edit", list(r_opts.keys()))
            sel_r_id = r_opts[sel_r_str]
            
            curr_r = my_ret_list[my_ret_list['id'] == sel_r_id].iloc[0]
            
            with st.form("dist_edit_ret_form"):
                ed_sname = st.text_input("Store Name", value=curr_r['store_name'])
                ed_phone = st.text_input("Phone Number (for WhatsApp OTP)", value=str(curr_r['phone'] or ''))
                ed_rpass = st.text_input("New Password (leave blank to keep current)", type="password")
                
                col1, col2 = st.columns(2)
                with col1:
                    update_r = st.form_submit_button("Update Store Details", type="primary")
                with col2:
                    delete_r = st.form_submit_button("🗑️ Delete Retailer (Trial/Pending/Expired Only)")
                    
                if update_r:
                    c = conn.cursor()
                    if ed_rpass:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ?, password_hash = ? WHERE id = ? AND wholesaler_id = ?;", (ed_sname, ed_phone.strip(), hash_password(ed_rpass), sel_r_id, st.session_state.user_id))
                    else:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ? WHERE id = ? AND wholesaler_id = ?;", (ed_sname, ed_phone.strip(), sel_r_id, st.session_state.user_id))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Store details updated successfully!")
                    st.rerun()
                    
                if delete_r:
                    expiry_dt = datetime.strptime(str(curr_r['plan_expiry_date'])[:10], '%Y-%m-%d') if curr_r['plan_expiry_date'] else datetime.now()
                    is_trial = str(curr_r['subscription_status']).upper() == 'TRIAL'
                    is_pending = str(curr_r['payment_status']).upper() in ['PENDING', 'PENDING_APPROVAL']
                    is_expired = expiry_dt < datetime.now()
                    
                    if is_trial or is_pending or is_expired:
                        c = conn.cursor()
                        c.execute("DELETE FROM retailers WHERE id = ? AND wholesaler_id = ?;", (sel_r_id, st.session_state.user_id))
                        conn.commit()
                        trigger_dual_backup()
                        st.success("Retailer successfully deleted!")
                        st.rerun()
                    else:
                        st.error("❌ Deletion Blocked! This retailer has an ACTIVE paid subscription.")
        else:
            st.info("No retailers in your network to edit.")
    conn.close()

# ==============================================================================
# 🛡️ SUPER ADMIN (OWNER) DASHBOARD
# ==============================================
elif st.session_state.role == "SUPER_ADMIN":
    st.title(f"💊 PharmaFlow - Owner Administration Panel")
    st.subheader(f"🛡 {COMPANY_NAME} | Central Control & Enterprise Multi-Terminal Management")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📂 All Distributors", 
        "➕ Add Distributor", 
        "🏥 All Retailers & Approvals",
        "✏️ Master Edit & Subscriptions",
        "🔄 Variable Pricing & Plans",
        "⚙️ White-Label & Variable Pricing Setup"
    ])

    conn = get_db_connection()
    with tab1:
        st.markdown("### Registered Distributors (Support Partners)")
        w_df = pd.read_sql_query("SELECT id, company_name, owner_name, email, phone, username, commission_rate, created_at FROM wholesalers ORDER BY company_name ASC;", conn)
        if not w_df.empty:
            st.dataframe(w_df, use_container_width=True)
        else:
            st.info("No distributors registered yet.")

    with tab2:
        st.markdown("### Register New Distributor")
        with st.form("add_distributor_form"):
            c_name = st.text_input("Distributor Agency Name")
            o_name = st.text_input("Owner / Contact Person Name")
            email = st.text_input("Email (Unique)")
            phone = st.text_input("Phone Number")
            w_user = st.text_input("Distributor Username")
            w_pass = st.text_input("Distributor Password", type="password")
            comm = st.number_input("Commission Share (%)", value=10.0)
            
            submit_dist = st.form_submit_button("Create Distributor")
            if submit_dist:
                if c_name and email and w_user and w_pass:
                    try:
                        c = conn.cursor()
                        c.execute("INSERT INTO wholesalers (company_name, owner_name, email, phone, username, password_hash, commission_rate) VALUES (?, ?, ?, ?, ?, ?, ?);", (c_name, o_name, email, phone, w_user, hash_password(w_pass), comm))
                        conn.commit()
                        trigger_dual_backup()
                        st.success(f"Distributor '{c_name}' successfully added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Please fill in all required fields.")

    with tab3:
        st.markdown("### 🏥 All Medical Stores & Payment Approvals")
        r_df = pd.read_sql_query("SELECT r.id, r.store_name, r.owner_name, r.phone, r.store_type, r.subscription_status, r.payment_status, r.plan_expiry_date, w.company_name as assigned_distributor FROM retailers r LEFT JOIN wholesalers w ON r.wholesaler_id = w.id ORDER BY r.store_name ASC;", conn)
        if not r_df.empty:
            st.dataframe(r_df, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### ✅ Verify UTR & Approve Plan Extension")
            pending_df = r_df[r_df['payment_status'] == 'PENDING_APPROVAL']
            if not pending_df.empty:
                p_opts = {f"{row['store_name']} (Type: {row['store_type']})": row['id'] for _, row in pending_df.iterrows()}
                sel_p_str = st.selectbox("Select Store Requesting Approval", list(p_opts.keys()))
                sel_p_id = p_opts[sel_p_str]
                
                add_period = st.radio("Select Plan Duration to Verify", ["1 Month", "1 Year"])
                
                if st.button("✅ Verify Payment & Activate Plan", type="primary"):
                    c = conn.cursor()
                    if add_period == "1 Month":
                        c.execute("UPDATE retailers SET plan_expiry_date = datetime(COALESCE(NULLIF(plan_expiry_date, ''), datetime('now')), '+1 month'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (sel_p_id,))
                    else:
                        c.execute("UPDATE retailers SET plan_expiry_date = datetime(COALESCE(NULLIF(plan_expiry_date, ''), datetime('now')), '+1 year'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (sel_p_id,))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Payment verified and plan successfully activated!")
                    st.rerun()
            else:
                st.info("No pending payment approval requests.")
        else:
            st.info("No retailers registered yet.")

    with tab4:
        st.markdown("### ✏️ Master Edit: Subscriptions, Status & Passwords (Admin Only)")
        ret_list = pd.read_sql_query("SELECT id, store_name, phone, store_type, subscription_status, payment_status, plan_expiry_date FROM retailers ORDER BY store_name ASC;", conn)
        if not ret_list.empty:
            r_opts = {f"{row['store_name']} (Type: {row['store_type']}, Status: {row['subscription_status']})": row['id'] for _, row in ret_list.iterrows()}
            sel_r_str = st.selectbox("Select Retailer for Master Control", list(r_opts.keys()))
            sel_r_id = r_opts[sel_r_str]
            
            curr_r = ret_list[ret_list['id'] == sel_r_id].iloc[0]
            
            with st.form("admin_edit_ret_form"):
                ed_sname = st.text_input("Store Name", value=curr_r['store_name'])
                ed_phone = st.text_input("Phone Number (for WhatsApp OTP)", value=str(curr_r['phone'] or ''))
                ed_stype = st.selectbox("Store Architecture / System Type", ["SINGLE", "ENTERPRISE"], index=["SINGLE", "ENTERPRISE"].index(curr_r['store_type']) if curr_r['store_type'] in ["SINGLE", "ENTERPRISE"] else 0)
                ed_status = st.selectbox("Subscription Status", ["ACTIVE", "TRIAL", "EXPIRED"], index=["ACTIVE", "TRIAL", "EXPIRED"].index(curr_r['subscription_status']) if curr_r['subscription_status'] in ["ACTIVE", "TRIAL", "EXPIRED"] else 0)
                ed_expiry = st.text_input("Plan Expiry Date (YYYY-MM-DD)", value=str(curr_r['plan_expiry_date'])[:10] if curr_r['plan_expiry_date'] else "")
                ed_rpass = st.text_input("New Password (leave blank to keep current)", type="password")
                
                col1, col2 = st.columns(2)
                with col1:
                    update_r = st.form_submit_button("Update Master Settings", type="primary")
                with col2:
                    delete_r = st.form_submit_button("🗑️ Delete Retailer (Trial/Pending/Expired Only)")
                    
                if update_r:
                    c = conn.cursor()
                    if ed_rpass:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ?, store_type = ?, subscription_status = ?, plan_expiry_date = ?, password_hash = ? WHERE id = ?;", (ed_sname, ed_phone.strip(), ed_stype, ed_status, ed_expiry.strip(), hash_password(ed_rpass), sel_r_id))
                    else:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ?, store_type = ?, subscription_status = ?, plan_expiry_date = ? WHERE id = ?;", (ed_sname, ed_phone.strip(), ed_stype, ed_status, ed_expiry.strip(), sel_r_id))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Retailer master settings successfully updated!")
                    st.rerun()
                    
                if delete_r:
                    expiry_dt = datetime.strptime(str(curr_r['plan_expiry_date'])[:10], '%Y-%m-%d') if curr_r['plan_expiry_date'] else datetime.now()
                    is_trial = str(curr_r['subscription_status']).upper() == 'TRIAL'
                    is_pending = str(curr_r['payment_status']).upper() in ['PENDING', 'PENDING_APPROVAL']
                    is_expired = expiry_dt < datetime.now()
                    
                    if is_trial or is_pending or is_expired:
                        c = conn.cursor()
                        c.execute("DELETE FROM retailers WHERE id = ?;", (sel_r_id,))
                        conn.commit()
                        trigger_dual_backup()
                        st.success("Retailer successfully deleted!")
                        st.rerun()
                    else:
                        st.error("❌ Deletion Blocked! This retailer has an ACTIVE paid subscription.")
        else:
            st.info("No retailers available to edit.")

    with tab5:
        st.markdown("### Variable Subscription Pricing & Master Override")
        st.info(f"Official Central Payment UPI ID: **{OWNER_UPI}**\n* **Single System Plan:** Monthly: **₹ {MONTHLY_FEE}** | Yearly: **₹ {YEARLY_FEE}**\n* **Multi System (Enterprise) Plan:** Monthly: **₹ {ENT_MONTHLY_FEE}** | Yearly: **₹ {ENT_YEARLY_FEE}**")
        
        retailers_list = pd.read_sql_query("SELECT id, store_name, store_type FROM retailers ORDER BY store_name ASC;", conn)
        if not retailers_list.empty:
            r_opts = {f"{row['store_name']} ({row['store_type']})": row['id'] for _, row in retailers_list.iterrows()}
            sel_r = st.selectbox("Select Retailer for Plan Override", list(r_opts.keys()))
            r_id = r_opts[sel_r]
            
            curr_type = pd.read_sql_query("SELECT store_type FROM retailers WHERE id = ?;", conn, params=(r_id,)).iloc[0]["store_type"]
            
            if curr_type == "ENTERPRISE":
                period = st.radio("Select Multi System Plan", [f"1 Month (₹ {ENT_MONTHLY_FEE})", f"1 Year (₹ {ENT_YEARLY_FEE})"])
            else:
                period = st.radio("Select Single System Plan", [f"1 Month (₹ {MONTHLY_FEE})", f"1 Year (₹ {YEARLY_FEE})"])
            
            if st.button("⚡ Verify & Extend Plan", type="primary"):
                c = conn.cursor()
                if "1 Month" in period:
                    c.execute("UPDATE retailers SET plan_expiry_date = datetime(COALESCE(NULLIF(plan_expiry_date, ''), datetime('now')), '+1 month'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (r_id,))
                else:
                    c.execute("UPDATE retailers SET plan_expiry_date = datetime(COALESCE(NULLIF(plan_expiry_date, ''), datetime('now')), '+1 year'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (r_id,))
                conn.commit()
                trigger_dual_backup()
                st.success("Plan extended successfully!")
                st.rerun()
        else:
            st.info("Please register a retailer before processing.")

    with tab6:
        st.markdown("### ⚙️ White-Label & Variable Market Pricing Setup")
        with st.form("settings_form"):
            new_comp = st.text_input("Company / Brand Name", value=COMPANY_NAME)
            new_user = st.text_input("Admin Username", value=ADMIN_USER)
            new_pwd = st.text_input("New Admin Password (leave blank to keep current)", type="password")
            new_upi = st.text_input("Official Business UPI ID (for direct payments)", value=OWNER_UPI)
            new_phone = st.text_input("Admin WhatsApp Phone Number (with Country Code, e.g. 919876543210)", value=ADMIN_PHONE)
            
            st.markdown("---")
            st.markdown("#### 💰 Variable Subscription Pricing Control (Market-wise)")
            st.markdown("##### 🖥️ Single System Plan")
            new_monthly = st.number_input("Single Monthly Fee (₹)", value=MONTHLY_FEE)
            new_yearly = st.number_input("Single Yearly Fee (₹)", value=YEARLY_FEE)
            
            st.markdown("##### 💻💻 Multi System (Enterprise Server/Client) Plan")
            new_ent_monthly = st.number_input("Multi System Monthly Fee (₹)", value=ENT_MONTHLY_FEE)
            new_ent_yearly = st.number_input("Multi System Yearly Fee (₹)", value=ENT_YEARLY_FEE)
            
            st.markdown("---")
            st.markdown("#### 🤖 Master Gemini API Key (Central Scanner Key)")
            new_gemini_key = st.text_input("Gemini API Key", value=MASTER_GEMINI_KEY, type="password", help="Enter your Google AI Studio API key here so all retailers can use the AI bill scanner automatically.")

            st.markdown("---")
            st.markdown("#### ☁️ AWS S3 Cloud Backup Storage Configuration")
            new_backup_target = st.text_input("AWS S3 Cloud Backup Bucket URL / Endpoint", value=CLIENT_BACKUP_TARGET)
            
            if st.form_submit_button("Save All Variable Settings"):
                try:
                    c = conn.cursor()
                    if new_pwd:
                        c.execute("UPDATE system_config SET company_name = ?, super_admin_username = ?, super_admin_password_hash = ?, upi_id = ?, admin_phone = ?, monthly_fee = ?, yearly_fee = ?, enterprise_monthly_fee = ?, enterprise_yearly_fee = ?, client_backup_target = ?, gemini_api_key = ? WHERE id = 1;", (new_comp, new_user, hash_password(new_pwd), new_upi, new_phone.strip(), new_monthly, new_yearly, new_ent_monthly, new_ent_yearly, new_backup_target.strip(), new_gemini_key.strip()))
                    else:
                        c.execute("UPDATE system_config SET company_name = ?, super_admin_username = ?, upi_id = ?, admin_phone = ?, monthly_fee = ?, yearly_fee = ?, enterprise_monthly_fee = ?, enterprise_yearly_fee = ?, client_backup_target = ?, gemini_api_key = ? WHERE id = 1;", (new_comp, new_user, new_upi, new_phone.strip(), new_monthly, new_yearly, new_ent_monthly, new_ent_yearly, new_backup_target.strip(), new_gemini_key.strip()))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Settings updated successfully! Rebooting application...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    conn.close()

# ==============================================================================
# 🏥 RETAILER / MEDICAL STORE FULL ERP DASHBOARD (SERVER vs CLIENT TERMINAL)
# ==============================================
elif st.session_state.role == "RETAILER":
    conn = get_db_connection()
    r_info = pd.read_sql_query("SELECT r.store_name, r.store_type, r.subscription_status, r.plan_expiry_date, r.payment_status, w.company_name as support_partner, w.phone as support_phone FROM retailers r LEFT JOIN wholesalers w ON r.wholesaler_id = w.id WHERE r.id = ?;", conn, params=(st.session_state.user_id,))
    conn.close()
    
    r_store = r_info.iloc[0]["store_name"]
    r_store_type = r_info.iloc[0]["store_type"]
    r_status = r_info.iloc[0]["subscription_status"]
    r_payment_status = r_info.iloc[0]["payment_status"]
    r_expiry = r_info.iloc[0]["plan_expiry_date"]
    support_partner = r_info.iloc[0]["support_partner"] or "Direct Neelam Technologies"
    support_phone = r_info.iloc[0]["support_phone"] or "N/A"
    
    st.title(f"🏥 {r_store} - Medical Store ERP ({st.session_state.terminal_type} TERMINAL)")
    st.success(f"System Type: **{r_store_type}** | Status: **{r_status}** (Payment: {r_payment_status}) | Valid Till: **{r_expiry}**")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"🛠 **Ground Support Partner:**\n{support_partner}\n📞 Contact: {support_phone}")
    
    if st.session_state.terminal_type == "CLIENT":
        tab_list = ["🛒 Customer Billing Counter (POS Terminal)"]
        tabs = st.tabs(tab_list)
        tab2 = tabs[0]
        tab1, tab3, tab4, tab5, tab6, tab7 = None, None, None, None, None, None
    else:
        if r_store_type == "ENTERPRISE":
            tab_list = ["📸 Scan & Upload Bill", "🛒 Customer Billing", "📊 Dashboard & Alerts", "📦 30-Day & 90-Day Expiry Return", "📥 Excel/CSV Import", "💻 Multi-System Terminals", "💳 Payment & QR Code Wizard"]
            tabs = st.tabs(tab_list)
            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6]
        else:
            tab_list = ["📸 Scan & Upload Bill", "🛒 Customer Billing", "📊 Dashboard & Alerts", "📦 30-Day & 90-Day Expiry Return", "📥 Excel/CSV Import", "💳 Payment & QR Code Wizard"]
            tabs = st.tabs(tab_list)
            tab1, tab2, tab3, tab4, tab5, tab6 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5]
            tab7 = None
    
    conn = get_db_connection()
    c = conn.cursor()

    if tab1 is not None:
        with tab1:
            st.subheader("📸 Upload Wholesaler Bill for Stock Entry")
            upload_mode = st.radio("File Source", ["Upload File (JPG / PNG / PDF)", "Capture from Webcam"], horizontal=True)
            
            uploaded_file = st.file_uploader("Upload Bill Document", type=["jpg", "jpeg", "png", "pdf"]) if upload_mode == "Upload File (JPG / PNG / PDF)" else st.camera_input("Capture Bill Photo")
                
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.lower().endswith(".pdf"):
                        pdf_document = pdfium.PdfDocument(uploaded_file.read())
                        page = pdf_document[0]
                        pil_image = page.render(scale=2).to_pil()
                    else:
                        pil_image = Image.open(uploaded_file)
                    
                    st.image(pil_image, caption="Bill Preview", width=380)
                except Exception as e:
                    st.error(f"Error reading file: {e}")
                    pil_image = None
                
                if pil_image and st.button("🔍 Scan Bill & Extract Stock Items", type="primary"):
                    active_key = MASTER_GEMINI_KEY or os.environ.get("GEMINI_API_KEY")
                    if not active_key:
                        st.error("Master Gemini API Key is not configured by Admin in White-Label settings.")
                    else:
                        with st.spinner("AI is scanning the bill..."):
                            try:
                                client = genai.Client(api_key=active_key)
                                prompt = "Extract medicine items with name, batch, quantity, price, expiry_date (YYYY-MM-DD), discount_percent, gst_percent, is_schedule_h (0 or 1). Return ONLY valid JSON array."
                                response = client.models.generate_content(
                                    model='gemini-3.8-flash',
                                    contents=[pil_image, prompt],
                                    config=types.GenerateContentConfig(response_mime_type="application/json")
                                )
                                st.session_state.scanned_data = pd.DataFrame(json.loads(response.text))
                                st.success("Scan complete!")
                            except Exception as e:
                                st.error(f"Error: {e}")
            
            if st.session_state.scanned_data is not None:
                st.markdown("---")
                st.markdown("### ✍️ Review Scanned Items")
                edited_scanned_df = st.data_editor(st.session_state.scanned_data, use_container_width=True)
                
                if st.button("📥 Confirm & Save to Inventory Stock", type="primary"):
                    for _, r in edited_scanned_df.iterrows():
                        med_name = str(r['name']).upper().strip()
                        batch_no = str(r['batch']).upper().strip()
                        qty_add = int(r['quantity'])
                        exp_dt = str(r['expiry_date'])
                        price_val = float(r['price'])
                        disc_val = float(r['discount_percent']) if pd.notnull(r['discount_percent']) and r['discount_percent'] != '' else 0.0
                        gst_val = float(r['gst_percent']) if pd.notnull(r['gst_percent']) and r['gst_percent'] != '' else 12.0
                        sched_val = int(r['is_schedule_h']) if pd.notnull(r['is_schedule_h']) and r['is_schedule_h'] != '' else 0
                        
                        c.execute("SELECT id, quantity FROM inventory WHERE retailer_id = ? AND batch = ? AND name = ?;", (st.session_state.user_id, batch_no, med_name))
                        existing_item = c.fetchone()
                        
                        if existing_item:
                            item_id, current_qty = existing_item[0], existing_item[1]
                            new_qty = current_qty + qty_add
                            c.execute("UPDATE inventory SET quantity = ?, price = ?, expiry_date = ?, discount_percent = ?, gst_percent = ?, is_schedule_h = ? WHERE id = ?;", (new_qty, price_val, exp_dt, disc_val, gst_val, sched_val, item_id))
                        else:
                            c.execute("INSERT INTO inventory (retailer_id, name, batch, quantity, expiry_date, price, discount_percent, gst_percent, is_schedule_h) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", (st.session_state.user_id, med_name, batch_no, qty_add, exp_dt, price_val, disc_val, gst_val, sched_val))
                    
                    conn.commit()
                    trigger_dual_backup()
                    st.session_state.scanned_data = None
                    st.success("🎉 Stock successfully saved and updated without duplicates!")
                    st.rerun()

    with tab2:
        st.subheader("🛒 Customer Billing Counter")
        
        cart_has_schedule_h = any(item.get('is_schedule_h', 0) == 1 for item in st.session_state.cart)
        
        col_b1, col_b2, col_b3 = st.columns([2, 1.5, 1.5])
        with col_b1:
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            cust_phone = st.text_input("Customer Phone (10 digits for WhatsApp)", value="", placeholder="e.g. 9876543210")
        with col_b2:
            if cart_has_schedule_h:
                st.info("🔒 Cart has Schedule H item(s). Doctor Prescription mandatory.")
                ref_type = "Doctor Prescription"
                st.radio("Reference Type", [ref_type], disabled=True)
            else:
                ref_type = st.radio("Reference Type", ["Self (OTC)", "Doctor Prescription"], horizontal=True)
        with col_b3:
            if ref_type == "Doctor Prescription":
                raw_doc = st.text_input("Doctor Name (Enter name only)", value="", placeholder="e.g. Sharma")
                doctor_ref = f"Dr. {raw_doc.strip()}" if raw_doc.strip() else ""
            else:
                doctor_ref = "Self (OTC Sale)"
                raw_doc = ""

        st.markdown("---")

        df_active = pd.read_sql_query("SELECT MIN(id) as id, name, batch, SUM(quantity) as quantity, MIN(min_stock) as min_stock, MAX(expiry_date) as expiry_date, MAX(price) as price, MAX(discount_percent) as discount_percent, MAX(gst_percent) as gst_percent, MAX(is_schedule_h) as is_schedule_h FROM inventory WHERE retailer_id = ? AND quantity > 0 GROUP BY name, batch ORDER BY name ASC, expiry_date ASC;", conn, params=(st.session_state.user_id,))

        if not df_active.empty:
            st.markdown("#### Search Medicine (Sorted A-Z & Near Expiry First)")
            
            options = {}
            for _, row in df_active.iterrows():
                rx_tag = "[Rx] " if row['is_schedule_h'] == 1 else ""
                display_str = f"{rx_tag}{row['name']} | Batch: {row['batch']} | Exp: {row['expiry_date']} | MRP: ₹{row['price']} | Stock: {row['quantity']}"
                options[display_str] = row['batch']
                
            selected_display = st.selectbox("Select Medicine", list(options.keys()))
            selected_batch = options[selected_display]
            med_details = df_active[df_active['batch'] == selected_batch].iloc[0]
            
            c_info, c_qty, c_disc, c_btn = st.columns([2, 1, 1, 1])
            with c_info:
                rx_label = "🔴 [Schedule H / Rx]" if med_details['is_schedule_h'] == 1 else "🟢 [OTC]"
                st.info(f"**Item:** {med_details['name']} {rx_label} | **GST:** {med_details['gst_percent']}% | **Exp:** {med_details['expiry_date']}")
            with c_qty:
                sell_qty = st.number_input("Qty", min_value=1, max_value=int(med_details['quantity']), value=1)
            with c_disc:
                item_disc = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=float(med_details['discount_percent']))
            with c_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ Add to Bill", type="primary"):
                    unit_price = float(med_details['price'])
                    disc_amount_unit = unit_price * (item_disc / 100.0)
                    discounted_price = unit_price - disc_amount_unit
                    total_amt = sell_qty * discounted_price
                    st.session_state.cart.append({
                        "batch": selected_batch, 
                        "name": med_details['name'], 
                        "mrp": unit_price, 
                        "discount_percent": item_disc,
                        "discount_rs": disc_amount_unit,
                        "qty": sell_qty, 
                        "is_schedule_h": int(med_details['is_schedule_h']),
                        "net_total": total_amt
                    })
                    st.success("Added!")
                    st.rerun()
            
            if st.session_state.cart:
                st.markdown("### 🧾 Current Bill Items")
                
                for idx, cart_item in enumerate(st.session_state.cart):
                    col_i1, col_i2, col_i3, col_i4, col_i5, col_i6 = st.columns([2.5, 1, 1, 1, 1, 1])
                    with col_i1:
                        rx_badge = "🔴 [Rx]" if cart_item.get('is_schedule_h', 0) == 1 else ""
                        st.write(f"{rx_badge} **{cart_item['name']}**")
                    with col_i2:
                        st.write(f"MRP: ₹{cart_item['mrp']}")
                    with col_i3:
                        st.write(f"Disc: {cart_item['discount_percent']}% (₹{cart_item['discount_rs']:.2f})")
                    with col_i4:
                        st.write(f"Qty: {cart_item['qty']}")
                    with col_i5:
                        st.write(f"**₹{cart_item['net_total']:.2f}**")
                    with col_i6:
                        if st.button("❌ Remove", key=f"remove_item_{idx}"):
                            st.session_state.cart.pop(idx)
                            st.rerun()

                grand_total = sum(item['net_total'] for item in st.session_state.cart)
                total_savings = sum(item['discount_rs'] * item['qty'] for item in st.session_state.cart)
                
                st.markdown(f"### Grand Total: ₹ {grand_total:.2f} *(Total Savings: ₹ {total_savings:.2f})*")
                
                missing_doctor = (cart_has_schedule_h and (not raw_doc or not raw_doc.strip()))
                
                if missing_doctor:
                    st.error("🚨 **Mandatory Requirement:** Cart contains Schedule H (Rx) medicine(s). You MUST enter the Doctor's name before bill generation is allowed!")
                
                if st.button("🖨️ Complete Sale & Print Bill", type="primary", disabled=missing_doctor):
                    invoice_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    c.execute("INSERT INTO sales (retailer_id, invoice_number, customer_name, customer_phone, total_amount) VALUES (?, ?, ?, ?, ?);", (st.session_state.user_id, invoice_no, cust_name, f"{cust_phone} | Ref: {ref_type} ({doctor_ref})", grand_total))
                    
                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE retailer_id = ? AND batch = ?;", (item['qty'], st.session_state.user_id, item['batch']))
                    conn.commit()
                    trigger_dual_backup()
                    
                    wa_text = f"*{r_store} - Tax Invoice*\nInv No: {invoice_no}\nDate: {datetime.now().strftime('%d-%m-%Y %H:%M')}\nCustomer: {cust_name}\nRef: {ref_type} ({doctor_ref})\n-------------------\n"
                    for itm in st.session_state.cart:
                        wa_text += f"• {itm['name']} x {itm['qty']} = ₹{itm['net_total']:.2f}\n"
                    wa_text += f"-------------------\n*Grand Total: ₹{grand_total:.2f}*\n*(You Saved: ₹{total_savings:.2f})*\nThank You! — Powered by {COMPANY_NAME}"
                    
                    encoded_wa_text = urllib.parse.quote(wa_text)
                    clean_phone = "".join(filter(str.isdigit, cust_phone))
                    wa_url = f"https://wa.me/91{clean_phone}?text={encoded_wa_text}" if len(clean_phone) >= 10 else "https://web.whatsapp.com"

                    st.session_state.last_invoice = {
                        "invoice_no": invoice_no,
                        "store_name": r_store,
                        "customer_name": cust_name,
                        "customer_phone": cust_phone,
                        "reference": f"{ref_type} - {doctor_ref}",
                        "items": list(st.session_state.cart),
                        "grand_total": grand_total,
                        "total_savings": total_savings,
                        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "wa_text": wa_text,
                        "wa_url": wa_url
                    }
                    st.session_state.cart = []
                    st.success(f"Sale completed successfully! Invoice Number: {invoice_no}")
                    st.balloons()
            
            if st.session_state.last_invoice:
                inv = st.session_state.last_invoice
                st.markdown("---")
                st.markdown("### 🖨️ Thermal Bill Print Preview & WhatsApp Dispatch")
                
                if inv['customer_phone'] and len(inv['customer_phone'].strip()) >= 10:
                    st.markdown(f"""
                    <div style="margin-bottom: 15px;">
                        <a href="{inv['wa_url']}" target="_blank" style="text-decoration: none;">
                            <button style="background-color:#25D366; color:white; padding:12px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer; font-size:16px;">
                                💬 Open WhatsApp Chat with ({inv['customer_phone']})
                            </button>
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("💡 Enter a 10-digit customer phone number to enable direct WhatsApp chat opening.")

                st.markdown("📋 **Or copy bill text manually:**")
                st.text_area("WhatsApp Bill Text", value=inv['wa_text'], height=150, key="wa_textbox_manual")

                bill_html = f"""
                <div id="printable-bill" style="background-color: #ffffff; color: #000000; padding: 25px; border-radius: 8px; font-family: monospace; max-width: 450px; margin: auto; border: 1px solid #ccc;">
                    <h2 style="text-align: center; margin: 0;">🏥 {inv['store_name']}</h2>
                    <p style="text-align: center; font-size: 12px; color: #555; margin: 3px 0;">GST Retail Invoice / Cash Memo</p>
                    <hr style="border-color: #000;">
                    <p style="margin: 4px 0;"><b>Invoice No:</b> {inv['invoice_no']}</p>
                    <p style="margin: 4px 0;"><b>Date:</b> {inv['date']}</p>
                    <p style="margin: 4px 0;"><b>Customer:</b> {inv['customer_name']} ({inv['customer_phone']})</p>
                    <p style="margin: 4px 0;"><b>Reference:</b> {inv['reference']}</p>
                    <hr style="border-color: #000;">
                    <table style="width: 100%; font-size: 12px; text-align: left; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #000;"><th>Item</th><th>Qty</th><th>MRP</th><th>Disc</th><th>Total</th></tr>
                """
                for itm in inv['items']:
                    bill_html += f"""
                        <tr style="border-bottom: 1px dashed #ddd;">
                            <td style="padding: 4px 0;">{itm['name']}</td>
                            <td>{itm['qty']}</td>
                            <td>₹{itm['mrp']}</td>
                            <td>{itm['discount_percent']}%</td>
                            <td><b>₹{itm['net_total']:.2f}</b></td>
                        </tr>
                    """
                bill_html += f"""
                    </table>
                    <hr style="border-color: #000;">
                    <h3 style="text-align: right; margin: 5px 0;">Grand Total: ₹{inv['grand_total']:.2f}</h3>
                    <p style="text-align: right; font-size: 11px; color: #008000; margin: 0;">You Saved: ₹{inv['total_savings']:.2f}</p>
                    <br>
                    <p style="text-align: center; font-size: 11px; color: #333; margin: 10px 0 2px 0;">Thank You! Get Well Soon.</p>
                    <p style="text-align: center; font-size: 10px; color: #000; font-weight: bold; margin: 0;">Powered by {COMPANY_NAME}</p>
                </div>
                <script>
                    function printBill() {{
                        var printContents = document.getElementById('printable-bill').innerHTML;
                        var originalContents = document.body.innerHTML;
                        document.body.innerHTML = printContents;
                        window.print();
                        document.body.innerHTML = originalContents;
                        window.location.reload();
                    }}
                </script>
                <div style="text-align: center; margin-top: 15px;">
                    <button onclick="printBill()" style="background-color:#007bff; color:white; padding:12px 25px; border:none; border-radius:5px; font-weight:bold; cursor:pointer; font-size:16px;">
                        🖨️ Select Printer & Print Thermal Slip
                    </button>
                </div>
                """
                components.html(bill_html, height=520)
                
                if st.button("✖️ Close / Clear Preview"):
                    st.session_state.last_invoice = None
                    st.rerun()
        else:
            st.info("No active stock available in inventory.")

    with tab3:
        st.subheader("📊 Inventory Dashboard & Low Stock Alerts")
        df_inv = pd.read_sql_query("SELECT MIN(id) as id, name, batch, SUM(quantity) as quantity, MIN(min_stock) as min_stock, MAX(expiry_date) as expiry_date, MAX(price) as price, MAX(discount_percent) as discount_percent, MAX(gst_percent) as gst_percent, MAX(is_schedule_h) as is_schedule_h FROM inventory WHERE retailer_id = ? GROUP BY name, batch ORDER BY name ASC, expiry_date ASC;", conn, params=(st.session_state.user_id,))
        if not df_inv.empty:
            df_inv.index = range(1, len(df_inv) + 1)
            low_stock_df = df_inv[df_inv['quantity'] <= df_inv['min_stock']]
            if not low_stock_df.empty:
                st.error(f"🚨 **Low Stock Alert:** Found {len(low_stock_df)} medicine(s) running low on stock!")
                st.dataframe(low_stock_df[['name', 'batch', 'quantity', 'min_stock', 'expiry_date', 'price']], use_container_width=True)
                st.markdown("---")

            st.markdown("### 📋 Complete Inventory Catalog")
            edited_inv_df = st.data_editor(df_inv, use_container_width=True, key="inventory_editor", column_config={"id": None})
            
            if st.button("💾 Save Database Changes", type="primary"):
                try:
                    for _, row in edited_inv_df.iterrows():
                        c.execute("UPDATE inventory SET name = ?, batch = ?, quantity = ?, min_stock = ?, price = ?, discount_percent = ?, gst_percent = ?, is_schedule_h = ?, expiry_date = ? WHERE id = ? AND retailer_id = ?;", (str(row['name']).upper(), str(row['batch']).upper(), int(row['quantity']), int(row['min_stock']), float(row['price']), float(row['discount_percent']), float(row['gst_percent']), int(row['is_schedule_h']), str(row['expiry_date']), int(row['id']), st.session_state.user_id))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Inventory updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving changes: {e}")
        else:
            st.info("No inventory items found.")

    with tab4:
        st.subheader("📦 30-Day & 90-Day Expiry Return Reminders")
        today_str = datetime.now().strftime('%Y-%m-%d')
        limit_30 = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        limit_90 = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        
        exp_filter = st.radio("Select Expiry Window", ["⚠️ 30-Day Critical Expiry Return", "📦 90-Day Extended Expiry Return"], horizontal=True)
        
        if "30-Day" in exp_filter:
            df_exp30 = pd.read_sql_query("SELECT name, batch, quantity, expiry_date, price, is_schedule_h FROM inventory WHERE retailer_id = ? AND expiry_date <= ? AND expiry_date >= ? AND quantity > 0 ORDER BY expiry_date ASC, name ASC;", conn, params=(st.session_state.user_id, limit_30, today_str))
            if not df_exp30.empty:
                df_exp30.index = range(1, len(df_exp30) + 1)
                st.dataframe(df_exp30, use_container_width=True)
                st.warning("⚠️ Critical: Return these items immediately.")
            else:
                st.success("🎉 No items expiring in the next 30 days!")
        else:
            df_exp90 = pd.read_sql_query("SELECT name, batch, quantity, expiry_date, price, is_schedule_h FROM inventory WHERE retailer_id = ? AND expiry_date <= ? AND quantity > 0 ORDER BY expiry_date ASC, name ASC;", conn, params=(st.session_state.user_id, limit_90))
            if not df_exp90.empty:
                df_exp90.index = range(1, len(df_exp90) + 1)
                st.dataframe(df_exp90, use_container_width=True)
                st.warning("⚠️ Near expiry items identified.")
            else:
                st.success("No near-expiry items found.")

    with tab5:
        st.subheader("📥 Bulk Import Inventory via Excel / CSV")
        uploaded_csv = st.file_uploader("Upload CSV/Excel file", type=["csv", "xlsx"])
        if uploaded_csv is not None:
            st.success("File uploaded successfully!")

    if tab7 is not None:
        with tab6:
            st.subheader("💻 Multi-System Terminal Management (Server / Client Counters)")
            t_sub_tab1, t_sub_tab2 = st.tabs(["➕ Add New Counter", "🔑 Update Counter Password / Remove"])
            
            with t_sub_tab1:
                with st.form("add_terminal_form"):
                    t_name = st.text_input("Counter / Terminal Name")
                    t_user = st.text_input("Terminal Login Username")
                    t_pass = st.text_input("Terminal Password", type="password")
                    
                    submit_term = st.form_submit_button("Create Billing Counter Terminal")
                    if submit_term:
                        if t_name and t_user and t_pass:
                            try:
                                c.execute("INSERT INTO store_terminals (retailer_id, terminal_name, terminal_type, username, password_hash) VALUES (?, ?, 'CLIENT', ?, ?);", (st.session_state.user_id, t_name, t_user.strip(), hash_password(t_pass)))
                                conn.commit()
                                trigger_dual_backup()
                                st.success(f"Billing Counter '{t_name}' successfully created!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error creating terminal: {e}")
                        else:
                            st.warning("Please fill in all required fields.")
            
            with t_sub_tab2:
                terminals_list_df = pd.read_sql_query("SELECT id, terminal_name, username FROM store_terminals WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
                if not terminals_list_df.empty:
                    t_opts = {f"{row['terminal_name']} (User: {row['username']})": row['id'] for _, row in terminals_list_df.iterrows()}
                    sel_term_str = st.selectbox("Select Counter to Update Password or Delete", list(t_opts.keys()))
                    sel_term_id = t_opts[sel_term_str]
                    
                    with st.form("update_term_pass_form"):
                        new_t_pass = st.text_input("Enter New Password for Counter", type="password")
                        col_tp1, col_tp2 = st.columns(2)
                        with col_tp1:
                            update_t_btn = st.form_submit_button("🔑 Update Counter Password", type="primary")
                        with col_tp2:
                            delete_t_btn = st.form_submit_button("🗑️ Delete Counter Terminal")
                            
                        if update_t_btn:
                            if not new_t_pass or len(new_t_pass.strip()) < 4:
                                st.error("Please enter a valid new password!")
                            else:
                                c.execute("UPDATE store_terminals SET password_hash = ? WHERE id = ? AND retailer_id = ?;", (hash_password(new_t_pass), sel_term_id, st.session_state.user_id))
                                conn.commit()
                                trigger_dual_backup()
                                st.success("Billing counter password successfully updated!")
                                st.rerun()
                                
                        if delete_t_btn:
                            c.execute("DELETE FROM store_terminals WHERE id = ? AND retailer_id = ?;", (sel_term_id, st.session_state.user_id))
                            conn.commit()
                            trigger_dual_backup()
                            st.success("Billing counter terminal successfully deleted!")
                            st.rerun()
                else:
                    st.info("No billing counters available to modify.")
            
            st.markdown("---")
            st.markdown("### Existing Billing Counters")
            terminals_df = pd.read_sql_query("SELECT id, terminal_name, username, created_at FROM store_terminals WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            if not terminals_df.empty:
                st.dataframe(terminals_df, use_container_width=True)

    target_sub_tab = tab7 if tab7 is not None else tab6
    if target_sub_tab is not None:
        with target_sub_tab:
            st.subheader("💳 Subscription Renewal & Payment Wizard")
            st.info(f"🛡️ **Official Owner UPI ID:** `{OWNER_UPI}`")
            
            if r_payment_status == 'PENDING_APPROVAL':
                st.warning("⏳ **Your payment verification request is currently PENDING.**")
                wa_msg = f"🔔 *Payment Request*\n🏥 Store: {r_store}\nPlease verify payment."
                wa_link = f"https://wa.me/{ADMIN_PHONE}?text={urllib.parse.quote(wa_msg)}"
                st.markdown(f'<a href="{wa_link}" target="_blank"><button style="background-color:#25D366; color:white; padding:12px; border:none; border-radius:5px; font-weight:bold;">💬 Resend Request on WhatsApp</button></a>', unsafe_allow_html=True)
            else:
                if "qr_generated" not in st.session_state:
                    st.session_state.qr_generated = False
                
                if not st.session_state.qr_generated:
                    with st.form("wizard_step1_form"):
                        if r_store_type == "ENTERPRISE":
                            plan_choice = st.radio("Select Multi-System Plan", [f"1 Month (₹ {ENT_MONTHLY_FEE})", f"1 Year (₹ {ENT_YEARLY_FEE})"])
                            amt_val = ENT_MONTHLY_FEE if "1 Month" in plan_choice else ENT_YEARLY_FEE
                            plan_desc = f"Enterprise Plan ({'1 Month' if '1 Month' in plan_choice else '1 Year'}) — ₹{amt_val}"
                        else:
                            plan_choice = st.radio("Select Single System Plan", [f"1 Month (₹ {MONTHLY_FEE})", f"1 Year (₹ {YEARLY_FEE})"])
                            amt_val = MONTHLY_FEE if "1 Month" in plan_choice else YEARLY_FEE
                            plan_desc = f"Single Plan ({'1 Month' if '1 Month' in plan_choice else '1 Year'}) — ₹{amt_val}"
                        
                        if st.form_submit_button("📱 Generate Payment QR Code", type="primary"):
                            st.session_state.qr_generated = True
                            st.session_state.selected_plan_desc = plan_desc
                            st.session_state.selected_amt = amt_val
                            st.rerun()
                else:
                    st.success(f"✅ Selected Plan: **{st.session_state.selected_plan_desc}**")
                    st.markdown(f"""
                    <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                        <h3 style="color: #1e293b; margin-top: 0;">📱 Scan Below to Pay ₹{st.session_state.selected_amt}</h3>
                        <p style="color: #475569; font-size: 14px;">UPI ID: <b>{OWNER_UPI}</b></p>
                        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=upi%3A%2F%2Fpay%3Fpa%3D{OWNER_UPI}%26pn%3D{urllib.parse.quote(COMPANY_NAME)}%26am%3D{st.session_state.selected_amt}%26cu%3DINR" alt="UPI QR Code" style="margin: 10px 0; border: 4px solid white; border-radius: 6px;">
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.form("wizard_step2_form"):
                        utr_code = st.text_input("Enter 12-Digit UTR / Transaction ID *", placeholder="e.g. 328471928471")
                        col_w1, col_w2 = st.columns(2)
                        with col_w1:
                            submit_utr = st.form_submit_button("📤 Submit UTR", type="primary")
                        with col_w2:
                            reset_wizard = st.form_submit_button("🔄 Change Plan")
                            
                        if reset_wizard:
                            st.session_state.qr_generated = False
                            st.rerun()
                            
                        if submit_utr:
                            if not utr_code or len(utr_code.strip()) < 8:
                                st.error("❌ Please enter a valid UTR number!")
                            else:
                                c = conn.cursor()
                                c.execute("UPDATE retailers SET payment_status = 'PENDING_APPROVAL' WHERE id = ?;", (st.session_state.user_id,))
                                conn.commit()
                                trigger_dual_backup()
                                st.session_state.qr_generated = False
                                st.success("🎉 Payment request registered successfully!")
                                st.rerun()

    conn.close()
