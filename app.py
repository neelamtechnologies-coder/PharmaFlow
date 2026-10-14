import streamlit as st
import pandas as pd
import sqlite3
import os
import shutil
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

BACKUP_DIR = "cloud_backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

DB_FILE = os.path.join(BACKUP_DIR, "medical_store.db")

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def trigger_dual_backup():
    try:
        mirror_filename = os.path.join(BACKUP_DIR, "medical_store_mirror.db")
        if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
            shutil.copyfile(DB_FILE, mirror_filename)
    except Exception as e:
        print(f"Backup error: {e}")

def restore_from_mirror_if_needed():
    mirror_file = os.path.join(BACKUP_DIR, "medical_store_mirror.db")
    if (not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0) and os.path.exists(mirror_file) and os.path.getsize(mirror_file) > 0:
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

    c.execute("CREATE TABLE IF NOT EXISTS wholesalers (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, commission_rate REAL DEFAULT 10.0, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')));")
    
    c.execute("CREATE TABLE IF NOT EXISTS retailers (id INTEGER PRIMARY KEY AUTOINCREMENT, wholesaler_id INTEGER, store_name TEXT NOT NULL, owner_name TEXT, email TEXT UNIQUE NOT NULL, phone TEXT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, store_type TEXT DEFAULT 'SINGLE', subscription_status TEXT DEFAULT 'TRIAL', plan_expiry_date TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes', '+7 days')), payment_status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')), FOREIGN KEY(wholesaler_id) REFERENCES wholesalers(id) ON DELETE SET NULL);")

    c.execute("CREATE TABLE IF NOT EXISTS store_terminals (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, terminal_name TEXT NOT NULL, terminal_type TEXT DEFAULT 'CLIENT', username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')), FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE);")

    c.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, name TEXT NOT NULL, batch TEXT, quantity INTEGER, min_stock INTEGER DEFAULT 5, expiry_date DATE, price REAL DEFAULT 0.0, discount_percent REAL DEFAULT 0.0, gst_percent REAL DEFAULT 12.0, is_schedule_h INTEGER DEFAULT 0, FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE);")

    c.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, retailer_id INTEGER, invoice_number TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, total_amount REAL NOT NULL, created_at TIMESTAMP DEFAULT (datetime('now', '+5 hours', '+30 minutes')), FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE);")
    conn.commit()

    c.execute("SELECT COUNT(*) FROM system_config;")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO system_config (company_name, super_admin_username, super_admin_password_hash, upi_id, admin_phone, monthly_fee, yearly_fee, enterprise_monthly_fee, enterprise_yearly_fee, client_backup_target, gemini_api_key) VALUES ('Neelam Technologies', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'neelamtech@upi', '919876543210', 599.0, 5999.0, 999.0, 9999.0, 'https://s3.amazonaws.com/neelam-technologies-backup-bucket', '');")
        conn.commit()

    c.execute("SELECT COUNT(*) FROM wholesalers;")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO wholesalers (company_name, owner_name, email, phone, username, password_hash, commission_rate) VALUES ('Neelam Pharma Distributors', 'Rameshwar Ji', 'distributor@neelamtech.in', '9876543210', 'dist1', ?, 10.0);", (hash_password("dist123"),))
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
                                st.success("Billing Counter Login Successful!")
                                st.rerun()
                conn.close()
                st.error("Invalid Username or Password!")

    with auth_tab2:
        st.markdown("### 🔒 Secure Password Reset with WhatsApp OTP")
        if not st.session_state.reset_otp_sent:
            with st.form("request_otp_form"):
                f_role = st.selectbox("Select Account Type", ["Retailer", "Counter Terminal", "Distributor", "Super Admin"])
                f_user = st.text_input("Username / Email")
                f_new_pass = st.text_input("New Password", type="password")
                f_confirm = st.text_input("Confirm New Password", type="password")
                
                req_otp_btn = st.form_submit_button("💬 Send OTP to WhatsApp")
                if req_otp_btn:
                    if not f_user or not f_new_pass:
                        st.warning("Please fill in all fields.")
                    elif f_new_pass != f_confirm:
                        st.error("Passwords do not match!")
                    else:
                        generated = str(random.randint(100000, 999999))
                        st.session_state.generated_otp = generated
                        st.session_state.reset_target_user = f_user
                        st.session_state.reset_target_role = f_role
                        st.session_state.reset_new_pass = f_new_pass
                        
                        otp_msg = f"🔐 OTP: {generated}"
                        st.session_state.reset_wa_link = f"https://wa.me/919876543210?text={urllib.parse.quote(otp_msg)}"
                        st.session_state.reset_otp_sent = True
                        st.success("OTP generated!")
                        st.rerun()
        else:
            st.markdown(f'<a href="{st.session_state.reset_wa_link}" target="_blank">Open WhatsApp for OTP</a>', unsafe_allow_html=True)
            with st.form("verify_otp_form"):
                entered_otp = st.text_input("Enter 6-Digit OTP")
                verify_btn = st.form_submit_button("Verify & Update Password")
                if verify_btn:
                    if entered_otp.strip() == st.session_state.generated_otp:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("UPDATE retailers SET password_hash = ? WHERE username = ?;", (hash_password(st.session_state.reset_new_pass), st.session_state.reset_target_user))
                        conn.commit()
                        conn.close()
                        st.session_state.reset_otp_sent = False
                        st.success("Password updated successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid OTP!")
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

# ================= WHOLESALER DASHBOARD =================
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
                        ins_q = "INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, store_type, username, password_hash, subscription_status, payment_status, plan_expiry_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TRIAL', 'PENDING', datetime('now', '+5 hours', '+30 minutes', '+7 days'), datetime('now', '+5 hours', '+30 minutes'));"
                        c.execute(ins_q, (st.session_state.user_id, s_name, o_name, email, phone.strip(), store_category, r_user, hash_password(r_pass)))
                        conn.commit()
                        trigger_dual_backup()
                        st.success(f"Retailer '{s_name}' ({store_category}) successfully registered!")
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
        st.markdown("### ✏️ Edit Store Name, Phone & Password")
        my_ret_list = pd.read_sql_query("SELECT id, store_name, phone, subscription_status, payment_status, plan_expiry_date FROM retailers WHERE wholesaler_id = ? ORDER BY store_name ASC;", conn, params=(st.session_state.user_id,))
        if not my_ret_list.empty:
            r_opts = {f"{row['store_name']} (Phone: {row['phone']})": row['id'] for _, row in my_ret_list.iterrows()}
            sel_r_str = st.selectbox("Select Retailer to Edit", list(r_opts.keys()))
            sel_r_id = r_opts[sel_r_str]
            curr_r = my_ret_list[my_ret_list['id'] == sel_r_id].iloc[0]
            
            with st.form("dist_edit_ret_form"):
                ed_sname = st.text_input("Store Name", value=curr_r['store_name'])
                ed_phone = st.text_input("Phone Number", value=str(curr_r['phone'] or ''))
                ed_rpass = st.text_input("New Password (leave blank to keep current)", type="password")
                if st.form_submit_button("Update Store Details", type="primary"):
                    c = conn.cursor()
                    if ed_rpass:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ?, password_hash = ? WHERE id = ? AND wholesaler_id = ?;", (ed_sname, ed_phone.strip(), hash_password(ed_rpass), sel_r_id, st.session_state.user_id))
                    else:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ? WHERE id = ? AND wholesaler_id = ?;", (ed_sname, ed_phone.strip(), sel_r_id, st.session_state.user_id))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Store details updated successfully!")
                    st.rerun()
        else:
            st.info("No retailers in your network to edit.")
    conn.close()

# ================= SUPER ADMIN DASHBOARD =================
elif st.session_state.role == "SUPER_ADMIN":
    st.title(f"💊 PharmaFlow - Owner Administration Panel")
    st.subheader(f"🛡 {COMPANY_NAME} | Central Control & Enterprise Multi-Terminal Management")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📂 All Distributors", 
        "➕ Add Distributor", 
        "🏥 All Retailers & Approvals",
        "✏️ Master Edit & Subscriptions",
        "🔄 Variable Pricing & Plans",
        "⚙️ White-Label & Setup"
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
            o_name = st.text_input("Owner Name")
            email = st.text_input("Email (Unique)")
            phone = st.text_input("Phone Number")
            w_user = st.text_input("Username")
            w_pass = st.text_input("Password", type="password")
            comm = st.number_input("Commission Share (%)", value=10.0)
            
            if st.form_submit_button("Create Distributor"):
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
            pending_df = pd.read_sql_query("SELECT id, store_name, store_type, subscription_status, payment_status, plan_expiry_date FROM retailers WHERE payment_status = 'PENDING_APPROVAL';", conn)
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
        st.markdown("### ✏️ Master Edit: Subscriptions, Status & Passwords")
        ret_list = pd.read_sql_query("SELECT id, store_name, phone, store_type, subscription_status, payment_status, plan_expiry_date FROM retailers ORDER BY store_name ASC;", conn)
        if not ret_list.empty:
            r_opts = {f"{row['store_name']} (Type: {row['store_type']}, Status: {row['subscription_status']})": row['id'] for _, row in ret_list.iterrows()}
            sel_r_str = st.selectbox("Select Retailer for Master Control", list(r_opts.keys()))
            sel_r_id = r_opts[sel_r_str]
            curr_r = ret_list[ret_list['id'] == sel_r_id].iloc[0]
            
            with st.form("admin_edit_ret_form"):
                ed_sname = st.text_input("Store Name", value=curr_r['store_name'])
                ed_phone = st.text_input("Phone Number", value=str(curr_r['phone'] or ''))
                store_types_list = ["SINGLE", "ENTERPRISE"]
                ed_stype = st.selectbox("Store Architecture", store_types_list, index=store_types_list.index(curr_r['store_type']) if curr_r['store_type'] in store_types_list else 0)
                status_list = ["ACTIVE", "TRIAL", "EXPIRED"]
                ed_status = st.selectbox("Subscription Status", status_list, index=status_list.index(curr_r['subscription_status']) if curr_r['subscription_status'] in status_list else 0)
                ed_expiry = st.text_input("Plan Expiry Date (YYYY-MM-DD)", value=str(curr_r['plan_expiry_date'])[:10] if curr_r['plan_expiry_date'] else "")
                ed_rpass = st.text_input("New Password (leave blank to keep current)", type="password")
                
                if st.form_submit_button("Update Master Settings", type="primary"):
                    c = conn.cursor()
                    if ed_rpass:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ?, store_type = ?, subscription_status = ?, plan_expiry_date = ?, password_hash = ? WHERE id = ?;", (ed_sname, ed_phone.strip(), ed_stype, ed_status, ed_expiry.strip(), hash_password(ed_rpass), sel_r_id))
                    else:
                        c.execute("UPDATE retailers SET store_name = ?, phone = ?, store_type = ?, subscription_status = ?, plan_expiry_date = ? WHERE id = ?;", (ed_sname, ed_phone.strip(), ed_stype, ed_status, ed_expiry.strip(), sel_r_id))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Retailer master settings successfully updated!")
                    st.rerun()
        else:
            st.info("No retailers available to edit.")

    with tab5:
        st.markdown("### Variable Subscription Pricing & Master Override")
        st.info(f"Official UPI ID: **{OWNER_UPI}**\n* **Single Plan:** Monthly: ₹{MONTHLY_FEE} | Yearly: ₹{YEARLY_FEE}\n* **Enterprise Plan:** Monthly: ₹{ENT_MONTHLY_FEE} | Yearly: ₹{ENT_YEARLY_FEE}")
        retailers_list = pd.read_sql_query("SELECT id, store_name, store_type FROM retailers ORDER BY store_name ASC;", conn)
        if not retailers_list.empty:
            r_opts = {f"{row['store_name']} ({row['store_type']})": row['id'] for _, row in retailers_list.iterrows()}
            sel_r = st.selectbox("Select Retailer for Plan Override", list(r_opts.keys()))
            r_id = r_opts[sel_r]
            curr_type = pd.read_sql_query("SELECT store_type FROM retailers WHERE id = ?;", conn, params=(r_id,)).iloc[0]["store_type"]
            period = st.radio("Select Plan", [f"1 Month (₹{ENT_MONTHLY_FEE if curr_type=='ENTERPRISE' else MONTHLY_FEE})", f"1 Year (₹{ENT_YEARLY_FEE if curr_type=='ENTERPRISE' else YEARLY_FEE})"])
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

    with tab6:
        st.markdown("### ⚙️ White-Label & Market Pricing Setup")
        with st.form("settings_form"):
            new_comp = st.text_input("Brand Name", value=COMPANY_NAME)
            new_user = st.text_input("Admin Username", value=ADMIN_USER)
            new_pwd = st.text_input("New Admin Password", type="password")
            new_upi = st.text_input("Business UPI ID", value=OWNER_UPI)
            new_phone = st.text_input("Admin WhatsApp Phone", value=ADMIN_PHONE)
            new_monthly = st.number_input("Single Monthly Fee", value=MONTHLY_FEE)
            new_yearly = st.number_input("Single Yearly Fee", value=YEARLY_FEE)
            new_ent_monthly = st.number_input("Enterprise Monthly Fee", value=ENT_MONTHLY_FEE)
            new_ent_yearly = st.number_input("Enterprise Yearly Fee", value=ENT_YEARLY_FEE)
            new_gemini_key = st.text_input("Gemini API Key", value=MASTER_GEMINI_KEY, type="password")
            new_backup_target = st.text_input("AWS S3 Backup URL", value=CLIENT_BACKUP_TARGET)
            
            if st.form_submit_button("Save All Settings"):
                c = conn.cursor()
                if new_pwd:
                    up_q = "UPDATE system_config SET company_name = ?, super_admin_username = ?, super_admin_password_hash = ?, upi_id = ?, admin_phone = ?, monthly_fee = ?, yearly_fee = ?, enterprise_monthly_fee = ?, enterprise_yearly_fee = ?, client_backup_target = ?, gemini_api_key = ? WHERE id = 1;"
                    params = (new_comp, new_user, hash_password(new_pwd), new_upi, new_phone.strip(), new_monthly, new_yearly, new_ent_monthly, new_ent_yearly, new_backup_target.strip(), new_gemini_key.strip())
                else:
                    up_q = "UPDATE system_config SET company_name = ?, super_admin_username = ?, upi_id = ?, admin_phone = ?, monthly_fee = ?, yearly_fee = ?, enterprise_monthly_fee = ?, enterprise_yearly_fee = ?, client_backup_target = ?, gemini_api_key = ? WHERE id = 1;"
                    params = (new_comp, new_user, new_upi, new_phone.strip(), new_monthly, new_yearly, new_ent_monthly, new_ent_yearly, new_backup_target.strip(), new_gemini_key.strip())
                c.execute(up_q, params)
                conn.commit()
                trigger_dual_backup()
                st.success("Settings updated! Rebooting...")
                st.rerun()
    conn.close()

# ================= RETAILER DASHBOARD =================
elif st.session_state.role == "RETAILER":
    conn = get_db_connection()
    r_info = pd.read_sql_query("SELECT r.store_name, r.store_type, r.subscription_status, r.plan_expiry_date, r.payment_status, w.company_name as support_partner, w.phone as support_phone FROM retailers r LEFT JOIN wholesalers w ON r.wholesaler_id = w.id WHERE r.id = ?;", conn, params=(st.session_state.user_id,))
    conn.close()
    
    r_store = r_info.iloc[0]["store_name"]
    r_store_type = r_info.iloc[0]["store_type"]
    r_status = r_info.iloc[0]["subscription_status"]
    r_payment_status = r_info.iloc[0]["payment_status"]
    r_expiry = r_info.iloc[0]["plan_expiry_date"]
    support_partner = r_info.iloc[0]["support_partner"] or "Direct Support"
    support_phone = r_info.iloc[0]["support_phone"] or "N/A"
    
    st.title(f"🏥 {r_store} - Medical Store ERP ({st.session_state.terminal_type})")
    st.success(f"Type: **{r_store_type}** | Status: **{r_status}** | Valid Till: **{r_expiry}**")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"Support Partner:\n{support_partner}\nContact: {support_phone}")
    
    if st.session_state.terminal_type == "CLIENT":
        tabs = st.tabs(["🛒 POS Terminal", "📒 Account Master", "📖 Day Book", "💵 Receipts & Payments", "📊 GSTR Reports"])
        tab2, tab_acc, tab_day, tab_rp, tab_gst = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4]
        tab1, tab3, tab4, tab5, tab6, tab7 = None, None, None, None, None, None
    else:
        if r_store_type == "ENTERPRISE":
            tabs = st.tabs(["📸 Scan Bill", "🛒 Billing", "📊 Dashboard", "📦 Expiry", "📒 Accounts", "📖 Day Book", "💵 Receipts & Payments", "📊 GSTR Reports", "📥 Import", "💻 Terminals", "💳 Payment"])
            tab1, tab2, tab3, tab4, tab_acc, tab_day, tab_rp, tab_gst, tab5, tab6, tab7 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7], tabs[8], tabs[9], tabs[10]
        else:
            tabs = st.tabs(["📸 Scan Bill", "🛒 Billing", "📊 Dashboard", "📦 Expiry", "📒 Accounts", "📖 Day Book", "💵 Receipts & Payments", "📊 GSTR Reports", "📥 Import", "💳 Payment"])
            tab1, tab2, tab3, tab4, tab_acc, tab_day, tab_rp, tab_gst, tab5, tab6 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7], tabs[8], tabs[9]
            tab7 = None
    
    conn = get_db_connection()
    c = conn.cursor()

    if tab1 is not None:
        with tab1:
            st.subheader("📸 Upload Wholesaler Bill")
            up_mode = st.radio("Source", ["Upload File", "Webcam"], horizontal=True)
            uploaded_file = st.file_uploader("Choose Bill", type=["jpg", "png", "pdf"]) if up_mode=="Upload File" else st.camera_input("Capture")
            if uploaded_file is not None:
                pil_image = Image.open(uploaded_file)
                st.image(pil_image, width=300)
                if st.button("Scan Bill via AI", type="primary"):
                    active_key = MASTER_GEMINI_KEY or os.environ.get("GEMINI_API_KEY")
                    if active_key:
                        client = genai.Client(api_key=active_key)
                        prompt = "Extract items with name, batch, quantity, price, expiry_date (YYYY-MM-DD), discount_percent, gst_percent, is_schedule_h (0/1). Return JSON array."
                        response = client.models.generate_content(model='gemini-3.8-flash', contents=[pil_image, prompt], config=types.GenerateContentConfig(response_mime_type="application/json"))
                        st.session_state.scanned_data = pd.DataFrame(json.loads(response.text))
                        st.success("Scanned successfully!")
            if st.session_state.scanned_data is not None:
                edited_scanned = st.data_editor(st.session_state.scanned_data)
                if st.button("Save to Inventory"):
                    for _, r in edited_scanned.iterrows():
                        c.execute("INSERT INTO inventory (retailer_id, name, batch, quantity, expiry_date, price, discount_percent, gst_percent, is_schedule_h) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", (st.session_state.user_id, r['name'], r['batch'], int(r['quantity']), r['expiry_date'], float(r['price']), float(r['discount_percent']), float(r['gst_percent']), int(r['is_schedule_h'])))
                    conn.commit()
                    trigger_dual_backup()
                    st.session_state.scanned_data = None
                    st.success("Stock saved!")
                    st.rerun()

    with tab2:
        st.subheader("🛒 Customer Billing Counter")
        cust_name = st.text_input("Customer Name", value="Walk-in")
        cust_phone = st.text_input("Phone", value="")
        df_active = pd.read_sql_query("SELECT name, batch, quantity, price, is_schedule_h FROM inventory WHERE retailer_id = ? AND quantity > 0;", conn, params=(st.session_state.user_id,))
        if not df_active.empty:
            options = {f"{r['name']} | Batch: {r['batch']} | MRP: ₹{r['price']} | Stock: {r['quantity']}": r['batch'] for _, r in df_active.iterrows()}
            sel_disp = st.selectbox("Select Item", list(options.keys()))
            sel_batch = options[sel_disp]
            med = df_active[df_active['batch'] == sel_batch].iloc[0]
            qty = st.number_input("Qty", min_value=1, max_value=int(med['quantity']), value=1)
            if st.button("Add to Cart", type="primary"):
                st.session_state.cart.append({"name": med['name'], "batch": sel_batch, "price": med['price'], "qty": qty, "total": med['price']*qty})
                st.success("Added!")
                st.rerun()
            if st.session_state.cart:
                st.dataframe(pd.DataFrame(st.session_state.cart))
                g_tot = sum(i['total'] for i in st.session_state.cart)
                st.markdown(f"### Total: ₹{g_tot:.2f}")
                if st.button("Complete Sale & Print", type="primary"):
                    inv_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    c.execute("INSERT INTO sales (retailer_id, invoice_number, customer_name, customer_phone, total_amount) VALUES (?, ?, ?, ?, ?);", (st.session_state.user_id, inv_no, cust_name, cust_phone, g_tot))
                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE retailer_id = ? AND batch = ?;", (item['qty'], st.session_state.user_id, item['batch']))
                    conn.commit()
                    trigger_dual_backup()
                    st.session_state.cart = []
                    st.success(f"Invoice {inv_no} generated!")
                    st.rerun()

    with tab3:
        st.subheader("📊 Inventory Dashboard")
        df_inv = pd.read_sql_query("SELECT name, batch, quantity, min_stock, expiry_date, price FROM inventory WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
        if not df_inv.empty:
            st.dataframe(df_inv, use_container_width=True)
        else:
            st.info("Inventory is empty.")

    with tab4:
        st.subheader("📦 Expiry Returns")
        lim = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        exp_df = pd.read_sql_query("SELECT name, batch, quantity, expiry_date FROM inventory WHERE retailer_id = ? AND expiry_date <= ?;", conn, params=(st.session_state.user_id, lim))
        if not exp_df.empty:
            st.dataframe(exp_df, use_container_width=True)
        else:
            st.success("No items expiring soon!")

    if tab_acc is not None:
        with tab_acc:
            st.subheader("📒 Account Master")
            with st.form("acc_form"):
                an = st.text_input("Account Name")
                ag = st.selectbox("Group", ["Sundry Debtors", "Sundry Creditors", "Bank", "Cash"])
                op = st.number_input("Opening Balance", value=0.0)
                if st.form_submit_button("Save Account"):
                    c.execute("INSERT INTO account_masters (retailer_id, account_name, group_type, opening_balance, current_balance) VALUES (?, ?, ?, ?, ?);", (st.session_state.user_id, an, ag, op, op))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Account saved!")
                    st.rerun()
            acc_list = pd.read_sql_query("SELECT account_name, group_type, current_balance FROM account_masters WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            if not acc_list.empty:
                st.dataframe(acc_list, use_container_width=True)

    if tab_day is not None:
        with tab_day:
            st.subheader("📖 Day Book")
            with st.form("day_form"):
                dt = st.date_input("Date", value=datetime.now())
                vt = st.selectbox("Type", ["Receipt", "Payment", "Journal"])
                pt = st.text_input("Particulars")
                db = st.number_input("Debit", value=0.0)
                cr = st.number_input("Credit", value=0.0)
                if st.form_submit_button("Post"):
                    c.execute("INSERT INTO day_book (retailer_id, entry_date, voucher_type, particulars, debit, credit) VALUES (?, ?, ?, ?, ?, ?);", (st.session_state.user_id, dt.strftime('%Y-%m-%d'), vt, pt, db, cr))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Posted!")
                    st.rerun()
            db_list = pd.read_sql_query("SELECT entry_date, voucher_type, particulars, debit, credit FROM day_book WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            if not db_list.empty:
                st.dataframe(db_list, use_container_width=True)

    if tab_rp is not None:
        with tab_rp:
            st.subheader("💵 Receipts & Payments")
            rp_t1, rp_t2 = st.tabs(["Receipt", "Payment"])
            with rp_t1:
                with st.form("rec_f"):
                    rd = st.date_input("Date", value=datetime.now(), key="rd")
                    rn = st.text_input("Received From", key="rn")
                    ra = st.number_input("Amount", value=0.0, key="ra")
                    if st.form_submit_button("Save Receipt"):
                        c.execute("INSERT INTO day_book (retailer_id, entry_date, voucher_type, particulars, debit, credit) VALUES (?, ?, 'Receipt', ?, ?, 0);", (st.session_state.user_id, rd.strftime('%Y-%m-%d'), rn, ra))
                        conn.commit()
                        trigger_dual_backup()
                        st.success("Saved receipt!")
                        st.rerun()
            with rp_t2:
                with st.form("pay_f"):
                    pd_d = st.date_input("Date", value=datetime.now(), key="pd")
                    pn = st.text_input("Paid To", key="pn")
                    pa = st.number_input("Amount", value=0.0, key="pa")
                    if st.form_submit_button("Save Payment"):
                        c.execute("INSERT INTO day_book (retailer_id, entry_date, voucher_type, particulars, debit, credit) VALUES (?, ?, 'Payment', ?, 0, ?);", (st.session_state.user_id, pd_d.strftime('%Y-%m-%d'), pn, pa))
                        conn.commit()
                        trigger_dual_backup()
                        st.success("Saved payment!")
                        st.rerun()

    if tab_gst is not None:
        with tab_gst:
            st.subheader("📊 GSTR Reports (GSTR-1, 2, 3B)")
            gstr_t1, gstr_t2, gstr_t3 = st.tabs(["GSTR-1", "GSTR-2", "GSTR-3B"])
            with gstr_t1:
                s_df = pd.read_sql_query("SELECT invoice_number, customer_name, total_amount, created_at FROM sales WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
                if not s_df.empty:
                    s_df['Taxable'] = s_df['total_amount'] / 1.12
                    s_df['GST'] = s_df['total_amount'] - s_df['Taxable']
                    st.dataframe(s_df, use_container_width=True)
                else:
                    st.info("No sales data.")
            with gstr_t2:
                i_df = pd.read_sql_query("SELECT name, batch, quantity, price, gst_percent FROM inventory WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
                if not i_df.empty:
                    i_df['Purchase_Val'] = i_df['quantity'] * i_df['price']
                    i_df['Input_GST'] = i_df['Purchase_Val'] * (i_df['gst_percent'] / 100.0)
                    st.dataframe(i_df, use_container_width=True)
                else:
                    st.info("No purchase data.")
            with gstr_t3:
                st.markdown("### GSTR-3B Summary")
                st.info("Calculations active based on sales and inventory.")

    with tab5:
        st.subheader("📥 Excel/CSV Import")
        st.info("Upload file feature available.")

    if tab7 is not None:
        with tab6:
            st.subheader("💻 Multi-System Terminals")
            with st.form("term_form"):
                tn = st.text_input("Terminal Name")
                tu = st.text_input("Username")
                tp = st.text_input("Password", type="password")
                if st.form_submit_button("Create Counter"):
                    c.execute("INSERT INTO store_terminals (retailer_id, terminal_name, username, password_hash) VALUES (?, ?, ?, ?);", (st.session_state.user_id, tn, tu, hash_password(tp)))
                    conn.commit()
                    trigger_dual_backup()
                    st.success("Counter created!")
                    st.rerun()

    target_sub_tab = tab7 if tab7 is not None else tab6
    if target_sub_tab is not None:
        with target_sub_tab:
            st.subheader("💳 Payment & Subscription")
            if r_payment_status == 'PENDING_APPROVAL':
                st.warning("Payment verification pending.")
            else:
                amt = 999.0 if r_store_type=="ENTERPRISE" else 599.0
                st.markdown(f"Pay ₹{amt} to UPI: `{OWNER_UPI}`")
                with st.form("utr_form"):
                    utr = st.text_input("Enter 12-Digit UTR")
                    if st.form_submit_button("Submit UTR"):
                        c.execute("UPDATE retailers SET payment_status = 'PENDING_APPROVAL' WHERE id = ?;", (st.session_state.user_id,))
                        conn.commit()
                        trigger_dual_backup()
                        st.success("UTR submitted!")
                        st.rerun()

    conn.close()
