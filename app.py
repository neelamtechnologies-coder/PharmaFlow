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

# ==============================================================================
# 🗄️ DATABASE SETUP & SAFE MIGRATION
# ==============================================================================
DB_FILE = "medical_store.db"

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT DEFAULT 'Neelam Technologies',
            super_admin_username TEXT DEFAULT 'admin',
            super_admin_password_hash TEXT DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',
            upi_id TEXT DEFAULT 'neelamtech@upi',
            monthly_fee REAL DEFAULT 999.0,
            yearly_fee REAL DEFAULT 9999.0,
            client_backup_target TEXT DEFAULT '',
            gemini_api_key TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()

    c.execute("PRAGMA table_info(system_config);")
    columns = [col[1] for col in c.fetchall()]
    if "monthly_fee" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN monthly_fee REAL DEFAULT 999.0;")
    if "yearly_fee" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN yearly_fee REAL DEFAULT 9999.0;")
    if "client_backup_target" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN client_backup_target TEXT DEFAULT '';")
    if "gemini_api_key" not in columns:
        c.execute("ALTER TABLE system_config ADD COLUMN gemini_api_key TEXT DEFAULT '';")
    conn.commit()

    c.execute("SELECT COUNT(*) FROM system_config;")
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO system_config (company_name, super_admin_username, super_admin_password_hash, upi_id, monthly_fee, yearly_fee, client_backup_target, gemini_api_key)
            VALUES ('Neelam Technologies', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'neelamtech@upi', 999.0, 9999.0, '', '');
        ''')
        conn.commit()

    c.execute('''
        CREATE TABLE IF NOT EXISTS wholesalers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            owner_name TEXT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            commission_rate REAL DEFAULT 10.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS retailers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wholesaler_id INTEGER,
            store_name TEXT NOT NULL,
            owner_name TEXT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            subscription_status TEXT DEFAULT 'TRIAL',
            plan_expiry_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payment_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(wholesaler_id) REFERENCES wholesalers(id) ON DELETE SET NULL
        );
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
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
            is_schedule_h INTEGER DEFAULT 0,
            FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE
        );
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            retailer_id INTEGER,
            invoice_number TEXT NOT NULL,
            customer_name TEXT,
            customer_phone TEXT,
            total_amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(retailer_id) REFERENCES retailers(id) ON DELETE CASCADE
        );
    ''')
    conn.commit()
    conn.close()

init_db()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None

if "cart" not in st.session_state:
    st.session_state.cart = []
if "scanned_data" not in st.session_state:
    st.session_state.scanned_data = None

conn = get_db_connection()
config_df = pd.read_sql_query("SELECT company_name, super_admin_username, super_admin_password_hash, upi_id, monthly_fee, yearly_fee, client_backup_target, gemini_api_key FROM system_config LIMIT 1;", conn)
conn.close()

if not config_df.empty:
    COMPANY_NAME = config_df.iloc[0]["company_name"]
    ADMIN_USER = config_df.iloc[0]["super_admin_username"]
    ADMIN_PASS_HASH = config_df.iloc[0]["super_admin_password_hash"]
    OWNER_UPI = config_df.iloc[0]["upi_id"]
    MONTHLY_FEE = float(config_df.iloc[0]["monthly_fee"])
    YEARLY_FEE = float(config_df.iloc[0]["yearly_fee"])
    CLIENT_BACKUP_TARGET = str(config_df.iloc[0]["client_backup_target"]).strip()
    MASTER_GEMINI_KEY = str(config_df.iloc[0]["gemini_api_key"]).strip()
else:
    COMPANY_NAME = "Neelam Technologies"
    ADMIN_USER = "admin"
    ADMIN_PASS_HASH = hash_password("admin")
    OWNER_UPI = "neelamtech@upi"
    MONTHLY_FEE = 999.0
    YEARLY_FEE = 9999.0
    CLIENT_BACKUP_TARGET = ""
    MASTER_GEMINI_KEY = ""

# ==============================================================================
# 🔐 LOGIN & FORGOT PASSWORD SCREEN
# ==============================================================================
if not st.session_state.authenticated:
    st.title(f"💊 {COMPANY_NAME} - ERP Portal")
    
    auth_tab1, auth_tab2 = st.tabs(["🔑 Login", "🔄 Forgot / Reset Password"])
    
    with auth_tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
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
                        r_df = pd.read_sql_query("SELECT id, store_name, password_hash FROM retailers WHERE username = ?;", conn, params=(username,))
                        if not r_df.empty and hash_password(password) == r_df.iloc[0]["password_hash"]:
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.role = "RETAILER"
                            st.session_state.user_id = int(r_df.iloc[0]["id"])
                            conn.close()
                            st.success("Retailer Login Successful!")
                            st.rerun()
                conn.close()
                st.error("Invalid Username or Password!")

    with auth_tab2:
        st.markdown("### Reset Account Password")
        with st.form("forgot_pass_form"):
            f_role = st.selectbox("Select Account Type", ["Retailer (Medical Store)", "Distributor (Wholesaler)", "Super Admin"])
            f_user = st.text_input("Username / Email")
            f_new_pass = st.text_input("New Password", type="password")
            f_confirm = st.text_input("Confirm New Password", type="password")
            
            reset_btn = st.form_submit_button("Update Password")
            
            if reset_btn:
                if not f_user or not f_new_pass:
                    st.warning("Please fill in all fields.")
                elif f_new_pass != f_confirm:
                    st.error("Passwords do not match!")
                else:
                    conn = get_db_connection()
                    c = conn.cursor()
                    success_flag = False
                    
                    if f_role == "Super Admin":
                        if f_user == ADMIN_USER:
                            c.execute("UPDATE system_config SET super_admin_password_hash = ? WHERE id = 1;", (hash_password(f_new_pass),))
                            conn.commit()
                            success_flag = True
                    elif f_role == "Distributor (Wholesaler)":
                        c.execute("SELECT id FROM wholesalers WHERE username = ? OR email = ?;", (f_user, f_user))
                        row = c.fetchone()
                        if row:
                            c.execute("UPDATE wholesalers SET password_hash = ? WHERE id = ?;", (hash_password(f_new_pass), row[0]))
                            conn.commit()
                            success_flag = True
                    else:
                        c.execute("SELECT id FROM retailers WHERE username = ? OR email = ?;", (f_user, f_user))
                        row = c.fetchone()
                        if row:
                            c.execute("UPDATE retailers SET password_hash = ? WHERE id = ?;", (hash_password(f_new_pass), row[0]))
                            conn.commit()
                            success_flag = True
                            
                    conn.close()
                    if success_flag:
                        st.success("Password successfully reset! You can now login with your new password.")
                    else:
                        st.error("User not found with provided Username/Email!")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title(f"User: {st.session_state.username}")
st.sidebar.info(f"Role: {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.cart = []
    st.rerun()

# ==============================================================================
# 🛡️ SUPER ADMIN (OWNER) DASHBOARD
# ==============================================================================
if st.session_state.role == "SUPER_ADMIN":
    st.title(f"💊 PharmaFlow - Owner Administration Panel")
    st.subheader(f"🛡️ {COMPANY_NAME} | Central Control & Franchise Management")

    if not CLIENT_BACKUP_TARGET or CLIENT_BACKUP_TARGET == "":
        st.error("🚨 **CRITICAL CONFIGURATION WARNING:** Client Backup Storage ID is mandatory! Until you configure a valid backup storage URL or Google Drive ID, system operations are restricted.")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📂 All Distributors", 
        "➕ Add Distributor", 
        "🏥 All Retailers",
        "✏️ Edit / Delete Users",
        "🔄 Renewals & Pricing",
        "⚙️ White-Label & Backup Settings"
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
            
            if st.form_submit_button("Create Distributor"):
                if c_name and email and w_user and w_pass:
                    try:
                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO wholesalers (company_name, owner_name, email, phone, username, password_hash, commission_rate)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (c_name, o_name, email, phone, w_user, hash_password(w_pass), comm))
                        conn.commit()
                        st.success(f"Distributor '{c_name}' successfully added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Please fill in all required fields.")

    with tab3:
        st.markdown("### All Medical Stores (Retailers in Network)")
        r_df = pd.read_sql_query("""
            SELECT r.id, r.store_name, r.owner_name, r.email, r.phone, r.subscription_status, r.payment_status, r.plan_expiry_date, w.company_name as assigned_distributor
            FROM retailers r
            LEFT JOIN wholesalers w ON r.wholesaler_id = w.id
            ORDER BY r.store_name ASC;
        """, conn)
        if not r_df.empty:
            st.dataframe(r_df, use_container_width=True)
        else:
            st.info("No retailers registered yet.")

    with tab4:
        st.markdown("### ✏️ Edit or Delete Distributors & Retailers")
        user_type_sel = st.radio("Select User Category", ["Distributor (Wholesaler)", "Retailer (Medical Store)"], horizontal=True)
        
        if user_type_sel == "Distributor (Wholesaler)":
            dist_list = pd.read_sql_query("SELECT id, company_name, username, commission_rate FROM wholesalers ORDER BY company_name ASC;", conn)
            if not dist_list.empty:
                d_opts = {f"{row['company_name']} (User: {row['username']})": row['id'] for _, row in dist_list.iterrows()}
                sel_d_str = st.selectbox("Select Distributor to Edit/Delete", list(d_opts.keys()))
                sel_d_id = d_opts[sel_d_str]
                
                curr_d = dist_list[dist_list['id'] == sel_d_id].iloc[0]
                
                with st.form("edit_dist_form"):
                    ed_cname = st.text_input("Agency Name", value=curr_d['company_name'])
                    ed_comm = st.number_input("Commission Share (%)", value=float(curr_d['commission_rate']))
                    ed_pass = st.text_input("New Password (leave blank to keep current)", type="password")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        update_d = st.form_submit_button("Update Distributor")
                    with col2:
                        delete_d = st.form_submit_button("🗑️ Delete Distributor")
                        
                    if update_d:
                        c = conn.cursor()
                        if ed_pass:
                            c.execute("UPDATE wholesalers SET company_name = ?, commission_rate = ?, password_hash = ? WHERE id = ?;", (ed_cname, ed_comm, hash_password(ed_pass), sel_d_id))
                        else:
                            c.execute("UPDATE wholesalers SET company_name = ?, commission_rate = ? WHERE id = ?;", (ed_cname, ed_comm, sel_d_id))
                        conn.commit()
                        st.success("Distributor updated successfully!")
                        st.rerun()
                        
                    if delete_d:
                        c = conn.cursor()
                        c.execute("DELETE FROM wholesalers WHERE id = ?;", (sel_d_id,))
                        conn.commit()
                        st.success("Distributor deleted successfully!")
                        st.rerun()
            else:
                st.info("No distributors available to edit.")
        else:
            ret_list = pd.read_sql_query("SELECT id, store_name, username FROM retailers ORDER BY store_name ASC;", conn)
            if not ret_list.empty:
                r_opts = {f"{row['store_name']} (User: {row['username']})": row['id'] for _, row in ret_list.iterrows()}
                sel_r_str = st.selectbox("Select Retailer to Edit/Delete", list(r_opts.keys()))
                sel_r_id = r_opts[sel_r_str]
                
                curr_r = ret_list[ret_list['id'] == sel_r_id].iloc[0]
                
                with st.form("edit_ret_form"):
                    ed_sname = st.text_input("Store Name", value=curr_r['store_name'])
                    ed_rpass = st.text_input("New Password (leave blank to keep current)", type="password")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        update_r = st.form_submit_button("Update Retailer")
                    with col2:
                        delete_r = st.form_submit_button("🗑️ Delete Retailer")
                        
                    if update_r:
                        c = conn.cursor()
                        if ed_rpass:
                            c.execute("UPDATE retailers SET store_name = ?, password_hash = ? WHERE id = ?;", (ed_sname, hash_password(ed_rpass), sel_r_id))
                        else:
                            c.execute("UPDATE retailers SET store_name = ? WHERE id = ?;", (ed_sname, sel_r_id))
                        conn.commit()
                        st.success("Retailer updated successfully!")
                        st.rerun()
                        
                    if delete_r:
                        c = conn.cursor()
                        c.execute("DELETE FROM retailers WHERE id = ?;", (sel_r_id,))
                        conn.commit()
                        st.success("Retailer deleted successfully!")
                        st.rerun()
            else:
                st.info("No retailers available to edit.")

    with tab5:
        st.markdown("### Subscription Pricing & Instant Renewal")
        st.info(f"Official Central Payment UPI ID: **{OWNER_UPI}**\n* Current Fixed Pricing — Monthly: **₹ {MONTHLY_FEE}** | Yearly: **₹ {YEARLY_FEE}**")
        
        retailers_list = pd.read_sql_query("SELECT id, store_name FROM retailers ORDER BY store_name ASC;", conn)
        if not retailers_list.empty:
            r_opts = {row["store_name"]: row["id"] for _, row in retailers_list.iterrows()}
            sel_r = st.selectbox("Select Retailer for Plan Renewal", list(r_opts.keys()))
            r_id = r_opts[sel_r]
            
            period = st.radio("Select Fixed Subscription Plan", [f"1 Month (₹ {MONTHLY_FEE})", f"1 Year (₹ {YEARLY_FEE})"])
            
            if st.button("Confirm Payment Received & Extend Plan"):
                c = conn.cursor()
                if "1 Month" in period:
                    c.execute("UPDATE retailers SET plan_expiry_date = datetime('now', '+1 month'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (r_id,))
                else:
                    c.execute("UPDATE retailers SET plan_expiry_date = datetime('now', '+1 year'), payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = ?;", (r_id,))
                conn.commit()
                st.success("Retailer plan successfully extended!")
                st.rerun()
        else:
            st.info("Please register a retailer before processing renewals.")

    with tab6:
        st.markdown("### ⚙️ White-Label Settings, Fixed Pricing & Master AI Key")
        with st.form("settings_form"):
            new_comp = st.text_input("Company / Brand Name", value=COMPANY_NAME)
            new_user = st.text_input("Admin Username", value=ADMIN_USER)
            new_pwd = st.text_input("New Admin Password (leave blank to keep current)", type="password")
            new_upi = st.text_input("Official Business UPI ID (for direct payments)", value=OWNER_UPI)
            
            st.markdown("---")
            st.markdown("#### 💰 Fixed Subscription Pricing Control")
            new_monthly = st.number_input("Monthly Subscription Fee (₹)", value=MONTHLY_FEE)
            new_yearly = st.number_input("Yearly Subscription Fee (₹)", value=YEARLY_FEE)
            
            st.markdown("---")
            st.markdown("#### 🤖 Master Gemini API Key (Central Scanner Key)")
            new_gemini_key = st.text_input("Gemini API Key", value=MASTER_GEMINI_KEY, type="password", help="Enter your Google AI Studio API key here so all retailers can use the AI bill scanner automatically.")

            st.markdown("---")
            st.markdown("#### ☁️ MANDATORY Client Backup Storage Configuration")
            new_backup_target = st.text_input("Client Backup Storage URL or Google Drive ID / Webhook *", value=CLIENT_BACKUP_TARGET, help="Mandatory field. Client must provide their storage ID or Google Drive link.")
            
            if st.form_submit_button("Save All Settings"):
                if not new_backup_target or new_backup_target.strip() == "":
                    st.error("Error: Client Backup Storage ID is mandatory and cannot be left blank!")
                else:
                    try:
                        c = conn.cursor()
                        if new_pwd:
                            c.execute("""
                                UPDATE system_config 
                                SET company_name = ?, super_admin_username = ?, super_admin_password_hash = ?, upi_id = ?, monthly_fee = ?, yearly_fee = ?, client_backup_target = ?, gemini_api_key = ? 
                                WHERE id = 1;
                            """, (new_comp, new_user, hash_password(new_pwd), new_upi, new_monthly, new_yearly, new_backup_target.strip(), new_gemini_key.strip()))
                        else:
                            c.execute("""
                                UPDATE system_config 
                                SET company_name = ?, super_admin_username = ?, upi_id = ?, monthly_fee = ?, yearly_fee = ?, client_backup_target = ?, gemini_api_key = ? 
                                WHERE id = 1;
                            """, (new_comp, new_user, new_upi, new_monthly, new_yearly, new_backup_target.strip(), new_gemini_key.strip()))
                        conn.commit()
                        st.success("Settings updated successfully! Rebooting application...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    conn.close()

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

    tab1, tab2, tab3 = st.tabs(["📂 My Network Retailers", "➕ Register New Retailer", "✏️ Edit Retailer Details"])

    with tab1:
        st.markdown("### Retailers assigned under your support network")
        my_ret = pd.read_sql_query("""
            SELECT id, store_name, owner_name, email, phone, subscription_status, payment_status, plan_expiry_date, created_at 
            FROM retailers WHERE wholesaler_id = ? ORDER BY store_name ASC;
        """, conn, params=(st.session_state.user_id,))
        
        if not my_ret.empty:
            st.dataframe(my_ret, use_container_width=True)
        else:
            st.info("No retailers registered under your network yet.")

    with tab2:
        st.markdown("### Register New Medical Store (Retailer)")
        with st.form("add_retailer_form"):
            s_name = st.text_input("Medical Store Name")
            o_name = st.text_input("Retailer Owner Name")
            email = st.text_input("Retailer Email (Unique)")
            phone = st.text_input("Phone Number")
            r_user = st.text_input("Retailer Login Username")
            r_pass = st.text_input("Retailer Login Password", type="password")
            
            if st.form_submit_button("Register Store"):
                if s_name and email and r_user and r_pass:
                    try:
                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, username, password_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, s_name, o_name, email, phone, r_user, hash_password(r_pass)))
                        conn.commit()
                        st.success(f"Retailer '{s_name}' successfully added to your support network!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Please fill in all required fields.")

    with tab3:
        st.markdown("### ✏️ Edit Retailer Details in Your Network")
        my_ret_list = pd.read_sql_query("SELECT id, store_name, username FROM retailers WHERE wholesaler_id = ? ORDER BY store_name ASC;", conn, params=(st.session_state.user_id,))
        if not my_ret_list.empty:
            r_opts = {f"{row['store_name']} (User: {row['username']})": row['id'] for _, row in my_ret_list.iterrows()}
            sel_r_str = st.selectbox("Select Retailer to Edit", list(r_opts.keys()))
            sel_r_id = r_opts[sel_r_str]
            
            curr_r = my_ret_list[my_ret_list['id'] == sel_r_id].iloc[0]
            
            with st.form("dist_edit_ret_form"):
                ed_sname = st.text_input("Store Name", value=curr_r['store_name'])
                ed_rpass = st.text_input("New Password (leave blank to keep current)", type="password")
                
                if st.form_submit_button("Update Retailer Details"):
                    c = conn.cursor()
                    if ed_rpass:
                        c.execute("UPDATE retailers SET store_name = ?, password_hash = ? WHERE id = ? AND wholesaler_id = ?;", (ed_sname, hash_password(ed_rpass), sel_r_id, st.session_state.user_id))
                    else:
                        c.execute("UPDATE retailers SET store_name = ? WHERE id = ? AND wholesaler_id = ?;", (ed_sname, sel_r_id, st.session_state.user_id))
                    conn.commit()
                    st.success("Retailer details updated successfully!")
                    st.rerun()
        else:
            st.info("No retailers in your network to edit.")
    conn.close()

# ==============================================================================
# 🏥 RETAILER / MEDICAL STORE FULL ERP DASHBOARD
# ==============================================================================
elif st.session_state.role == "RETAILER":
    conn = get_db_connection()
    r_info = pd.read_sql_query("""
        SELECT r.store_name, r.subscription_status, r.plan_expiry_date, r.payment_status, w.company_name as support_partner, w.phone as support_phone
        FROM retailers r
        LEFT JOIN wholesalers w ON r.wholesaler_id = w.id
        WHERE r.id = ?;
    """, conn, params=(st.session_state.user_id,))
    conn.close()
    
    r_store = r_info.iloc[0]["store_name"]
    r_status = r_info.iloc[0]["subscription_status"]
    r_expiry = r_info.iloc[0]["plan_expiry_date"]
    support_partner = r_info.iloc[0]["support_partner"] or "Direct Neelam Technologies"
    support_phone = r_info.iloc[0]["support_phone"] or "N/A"
    
    st.title(f"🏥 {r_store} - Medical Store Management System")
    st.success(f"Subscription Status: **{r_status}** | Valid Till: **{r_expiry}**")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"🛠️ **Ground Support Partner:**\n{support_partner}\n📞 Contact: {support_phone}")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📸 Scan & Upload Bill",
        "🛒 Customer Billing", 
        "📊 Dashboard & Alerts", 
        "📦 90-Day Expiry Return",
        "📥 Excel/CSV Import", 
        "💳 Subscription & Renewal"
    ])
    
    conn = get_db_connection()
    c = conn.cursor()

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
                    
                    c.execute("""
                        SELECT id, quantity FROM inventory 
                        WHERE retailer_id = ? AND batch = ? AND name = ?;
                    """, (st.session_state.user_id, batch_no, med_name))
                    existing_item = c.fetchone()
                    
                    if existing_item:
                        item_id, current_qty = existing_item[0], existing_item[1]
                        new_qty = current_qty + qty_add
                        c.execute("""
                            UPDATE inventory 
                            SET quantity = ?, price = ?, expiry_date = ?, discount_percent = ?, gst_percent = ?, is_schedule_h = ? 
                            WHERE id = ?;
                        """, (new_qty, price_val, exp_dt, disc_val, gst_val, sched_val, item_id))
                    else:
                        c.execute("""
                            INSERT INTO inventory (retailer_id, name, batch, quantity, expiry_date, price, discount_percent, gst_percent, is_schedule_h)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, med_name, batch_no, qty_add, exp_dt, price_val, disc_val, gst_val, sched_val))
                
                conn.commit()
                st.session_state.scanned_data = None
                st.success("🎉 Stock successfully saved and updated without duplicates!")
                st.rerun()

    with tab2:
        st.subheader("🛒 Customer Billing Counter")
        
        # Customer & Reference Details Inputs
        col_b1, col_b2, col_b3 = st.columns([2, 1.5, 1.5])
        with col_b1:
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            cust_phone = st.text_input("Customer Phone", value="")
        with col_b2:
            ref_type = st.radio("Reference Type", ["Self (OTC)", "Doctor Prescription"], horizontal=True)
        with col_b3:
            if ref_type == "Doctor Prescription":
                raw_doc = st.text_input("Doctor Name (Enter name only)", value="", placeholder="e.g. Sharma")
                doctor_ref = f"Dr. {raw_doc.strip()}" if raw_doc.strip() else ""
            else:
                doctor_ref = "Self (OTC Sale)"

        st.markdown("---")

        df_active = pd.read_sql_query("SELECT * FROM inventory WHERE retailer_id = ? AND quantity > 0 ORDER BY name ASC, expiry_date ASC", conn, params=(st.session_state.user_id,))
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
            
            # Item details card & Quantity/Discount inputs
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
                    discounted_price = unit_price * (1 - (item_disc / 100.0))
                    total_amt = sell_qty * discounted_price
                    st.session_state.cart.append({
                        "batch": selected_batch, 
                        "name": med_details['name'], 
                        "mrp": unit_price, 
                        "discount_percent": item_disc,
                        "qty": sell_qty, 
                        "is_schedule_h": int(med_details['is_schedule_h']),
                        "net_total": total_amt
                    })
                    st.success("Added!")
                    st.rerun()
            
            if st.session_state.cart:
                st.markdown("### 🧾 Current Bill Items")
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df, use_container_width=True)
                grand_total = cart_df['net_total'].sum()
                st.markdown(f"### Grand Total: ₹ {grand_total:.2f}")
                
                # Check if any item in cart is Schedule H and Doctor name is missing
                has_schedule_h_items = any(item.get('is_schedule_h', 0) == 1 for item in st.session_state.cart)
                missing_doctor = (ref_type == "Doctor Prescription" and (not raw_doc or not raw_doc.strip()))
                
                if has_schedule_h_items and missing_doctor:
                    st.error("🚨 **Mandatory Requirement:** Your cart contains Schedule H (Rx) medicine(s). You MUST select 'Doctor Prescription' and enter the Doctor's name before completing the sale and printing the bill!")
                
                if st.button("🖨️ Complete Sale & Print Bill", type="primary", disabled=(has_schedule_h_items and missing_doctor)):
                    invoice_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    c.execute("""
                        INSERT INTO sales (retailer_id, invoice_number, customer_name, customer_phone, total_amount) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (st.session_state.user_id, invoice_no, cust_name, f"{cust_phone} | Ref: {ref_type} ({doctor_ref})", grand_total))
                    
                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE retailer_id = ? AND batch = ?;", (item['qty'], st.session_state.user_id, item['batch']))
                    conn.commit()
                    st.session_state.cart = []
                    st.success(f"Sale completed successfully! Invoice Number: {invoice_no}")
                    st.balloons()
        else:
            st.info("No active stock available in inventory.")

    with tab3:
        st.subheader("📊 Inventory Dashboard & Direct Editing")
        st.markdown("💡 *Tip: Click on any cell to edit values directly, then click 'Save Database Changes'. Sorted alphabetically by medicine name, with nearest expiry batches shown first.*")
        
        df_inv = pd.read_sql_query("SELECT id, name, batch, quantity, min_stock, expiry_date, price, discount_percent, gst_percent, is_schedule_h FROM inventory WHERE retailer_id = ? ORDER BY name ASC, expiry_date ASC;", conn, params=(st.session_state.user_id,))
        if not df_inv.empty:
            edited_inv_df = st.data_editor(
                df_inv, 
                use_container_width=True, 
                key="inventory_editor",
                column_config={"id": None}
            )
            
            if st.button("💾 Save Database Changes", type="primary"):
                try:
                    for _, row in edited_inv_df.iterrows():
                        c.execute("""
                            UPDATE inventory 
                            SET name = ?, batch = ?, quantity = ?, min_stock = ?, price = ?, discount_percent = ?, gst_percent = ?, is_schedule_h = ?, expiry_date = ?
                            WHERE id = ? AND retailer_id = ?;
                        """, (str(row['name']).upper(), str(row['batch']).upper(), int(row['quantity']), int(row['min_stock']), float(row['price']), float(row['discount_percent']), float(row['gst_percent']), int(row['is_schedule_h']), str(row['expiry_date']), int(row['id']), st.session_state.user_id))
                    conn.commit()
                    st.success("Inventory updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving changes: {e}")
        else:
            st.info("No inventory items found.")

    with tab4:
        st.subheader("📦 90-Day Near Expiry Stock")
        expiry_limit = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        df_exp = pd.read_sql_query("SELECT name, batch, quantity, expiry_date, price, is_schedule_h FROM inventory WHERE retailer_id = ? AND expiry_date <= ? AND quantity > 0 ORDER BY expiry_date ASC, name ASC;", conn, params=(st.session_state.user_id, expiry_limit))
        if not df_exp.empty:
            st.dataframe(df_exp, use_container_width=True)
            st.warning("⚠️ Near expiry items identified for distributor return.")
        else:
            st.success("No near-expiry items found.")

    with tab5:
        st.subheader("📥 Bulk Import Inventory via Excel / CSV")
        uploaded_csv = st.file_uploader("Upload CSV/Excel file", type=["csv", "xlsx"])
        if uploaded_csv is not None:
            st.success("File uploaded successful!")

    with tab6:
        st.subheader("💳 Subscription & Fixed Plan Renewal")
        st.markdown(f"To renew your subscription plan, please pay the fixed plan fee using the official owner UPI ID.")
        st.info(f"🛡️ **Official Owner UPI ID:** `{OWNER_UPI}`\n* **Monthly Plan:** ₹ {MONTHLY_FEE}\n* **Yearly Plan:** ₹ {YEARLY_FEE}")
        st.markdown(f"☁️ **Configured Client Backup Target:** `{CLIENT_BACKUP_TARGET}`")
        st.warning("Note: For day-to-day assistance and technical support, please contact your assigned support partner (Distributor).")

    conn.close()
