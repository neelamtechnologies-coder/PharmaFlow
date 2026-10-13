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
                                st.success(f"Billing Counter Login Successful!")
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
                        conn = get_db_connection()
                        c = conn.cursor()
                        target_phone = "919876543210"
                        
                        generated = str(random.randint(100000, 999999))
                        st.session_state.generated_otp = generated
                        st.session_state.reset_target_user = f_user
                        st.session_state.reset_target_role = f_role
                        st.session_state.reset_new_pass = f_new_pass
                        
                        otp_msg = f"🔐 OTP: {generated}"
                        st.session_state.reset_wa_link = f"https://wa.me/{target_phone}?text={urllib.parse.quote(otp_msg)}"
                        st.session_state.reset_otp_sent = True
                        conn.close()
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
st.sidebar.info(f"Role: {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.rerun()

# ================= RETAILER DASHBOARD =================
elif st.session_state.role == "RETAILER":
    conn = get_db_connection()
    r_query = "SELECT store_name, store_type, subscription_status, plan_expiry_date, payment_status FROM retailers WHERE id = ?;"
    r_info = pd.read_sql_query(r_query, conn, params=(st.session_state.user_id,))
    conn.close()
    
    r_store = r_info.iloc[0]["store_name"]
    r_store_type = r_info.iloc[0]["store_type"]
    
    st.title(f"🏥 {r_store} - Medical Store ERP")
    
    tab_list = ["🛒 Customer Billing", "📒 Account Master", "📖 Day Book"]
    tabs = st.tabs(tab_list)
    tab_bill, tab_acc, tab_day = tabs[0], tabs[1], tabs[2]
    
    conn = get_db_connection()
    c = conn.cursor()

    with tab_bill:
        st.subheader("🛒 Customer Billing Counter")
        cust_name = st.text_input("Customer Name", value="Walk-in Customer")
        cust_phone = st.text_input("Customer Phone", value="")
        
        active_query = "SELECT name, batch, quantity, price FROM inventory WHERE retailer_id = ? AND quantity > 0;"
        df_active = pd.read_sql_query(active_query, conn, params=(st.session_state.user_id,))
        
        if not df_active.empty:
            options = {f"{row['name']} | Batch: {row['batch']} | MRP: ₹{row['price']} | Stock: {row['quantity']}": row['batch'] for _, row in df_active.iterrows()}
            sel_disp = st.selectbox("Select Medicine", list(options.keys()))
            sel_batch = options[sel_disp]
            med_row = df_active[df_active['batch'] == sel_batch].iloc[0]
            
            qty = st.number_input("Quantity", min_value=1, max_value=int(med_row['quantity']), value=1)
            if st.button("➕ Add to Cart", type="primary"):
                st.session_state.cart.append({"name": med_row['name'], "batch": sel_batch, "price": med_row['price'], "qty": qty, "total": med_row['price'] * qty})
                st.success("Added to cart!")
                st.rerun()
                
            if st.session_state.cart:
                st.markdown("### Cart Items")
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df, use_container_width=True)
                g_total = cart_df['total'].sum()
                st.markdown(f"### Grand Total: ₹{g_total:.2f}")
                
                if st.button("🖨️ Complete Sale", type="primary"):
                    inv_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    c.execute("INSERT INTO sales (retailer_id, invoice_number, customer_name, customer_phone, total_amount) VALUES (?, ?, ?, ?, ?);", (st.session_state.user_id, inv_no, cust_name, cust_phone, g_total))
                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE retailer_id = ? AND batch = ?;", (item['qty'], st.session_state.user_id, item['batch']))
                    conn.commit()
                    st.session_state.cart = []
                    st.success(f"Sale completed successfully! Invoice: {inv_no}")
                    st.rerun()
        else:
            st.info("No stock available in inventory.")

    with tab_acc:
        st.subheader("📒 Account Master & Ledgers")
        with st.form("create_account_form"):
            acc_name = st.text_input("Account Name (Customer / Supplier)")
            acc_group = st.selectbox("Group", ["Sundry Debtors", "Sundry Creditors", "Bank Accounts", "Cash"])
            op_bal = st.number_input("Opening Balance (₹)", value=0.0)
            if st.form_submit_button("Save Account"):
                c.execute("INSERT INTO account_masters (retailer_id, account_name, group_type, opening_balance, current_balance) VALUES (?, ?, ?, ?, ?);", (st.session_state.user_id, acc_name, acc_group, op_bal, op_bal))
                conn.commit()
                st.success("Account created successfully!")
                st.rerun()
        
        acc_df = pd.read_sql_query("SELECT account_name, group_type, current_balance FROM account_masters WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
        if not acc_df.empty:
            st.dataframe(acc_df, use_container_width=True)

    with tab_day:
        st.subheader("📖 Day Book")
        with st.form("daybook_form"):
            v_date = st.date_input("Date", value=datetime.now())
            v_type = st.selectbox("Voucher Type", ["Receipt", "Payment", "Journal"])
            v_part = st.text_input("Particulars")
            v_deb = st.number_input("Debit (₹)", value=0.0)
            v_cred = st.number_input("Credit (₹)", value=0.0)
            if st.form_submit_button("Post Entry"):
                c.execute("INSERT INTO day_book (retailer_id, entry_date, voucher_type, particulars, debit, credit) VALUES (?, ?, ?, ?, ?, ?);", (st.session_state.user_id, v_date.strftime('%Y-%m-%d'), v_type, v_part, v_deb, v_cred))
                conn.commit()
                st.success("Entry posted!")
                st.rerun()
                
        db_df = pd.read_sql_query("SELECT entry_date, voucher_type, particulars, debit, credit FROM day_book WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
        if not db_df.empty:
            st.dataframe(db_df, use_container_width=True)

    conn.close()

elif st.session_state.role == "SUPER_ADMIN":
    st.title("🛡️ Super Admin Panel")
    ret_df = pd.read_sql_query("SELECT id, store_name, store_type, subscription_status FROM retailers;", get_db_connection())
    if not ret_df.empty:
        st.dataframe(ret_df, use_container_width=True)
    else:
        st.info("No retailers registered.")
