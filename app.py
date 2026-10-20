import streamlit as st
import pandas as pd
import sqlite3
import os
import hashlib

# ================= AUTOMATIC C DRIVE & DESKTOP SETUP =================
def setup_local_environment(store_name="TechPharma"):
    try:
        folder_path = r"C:\PharmaFlow_Data"
        os.makedirs(folder_path, exist_ok=True)
    except Exception:
        folder_path = os.path.join(os.path.expanduser("~"), "PharmaFlow_Data")
        os.makedirs(folder_path, exist_ok=True)
        
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.exists(desktop):
            shortcut_path = os.path.join(desktop, f"TechPharma - {store_name}.url")
            app_url = "https://share.streamlit.io" 
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
            admin_phone TEXT DEFAULT '919876543210'
        );""")
        
        # 6-Tier Hierarchy Table (Country Head, State Head, District Head, SSE)
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
        pass

init_db()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None
    st.session_state.terminal_type = "SERVER"

if "cart" not in st.session_state:
    st.session_state.cart = []

# ================= BRANDED HEADER =================
def render_header():
    st.markdown("""
        <div style="text-align: center; padding: 15px; background-color: #f8f9fa; border-radius: 10px; margin-bottom: 20px;">
            <h1 style="color: #1f77b4; margin-bottom: 2px; font-size: 34px;">💊 TechPharma Solutions</h1>
            <p style="font-size: 13px; color: #495057; margin-bottom: 5px; font-style: italic;">“The Smart Way to Manage Your Pharmacy – Fast Billing, Zero Expiry Stress.”</p>
            <p style="font-size: 10px; color: #6c757d; margin-top: 0px; letter-spacing: 1.5px; font-weight: 600;">POWERED BY NEELAM TECHNOLOGIES</p>
        </div>
    """, unsafe_allow_html=True)

if not st.session_state.authenticated:
    render_header()
    with st.form("login_form"):
        username = st.text_input("Username (admin / hierarchy / retailer)")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            conn = get_db_connection()
            if username == "admin" and hash_password(password) == hash_password("admin"):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "SUPER_ADMIN"
                setup_local_environment("Owner_Admin")
                conn.close()
                st.success("Owner Login Successful!")
                st.rerun()
            else:
                h_df = pd.read_sql_query("SELECT id, role, password_hash FROM hierarchy_users WHERE username = ?;", conn, params=(username,))
                if not h_df.empty and hash_password(password) == h_df.iloc[0]["password_hash"]:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.role = h_df.iloc[0]["role"]
                    st.session_state.user_id = int(h_df.iloc[0]["id"])
                    setup_local_environment(h_df.iloc[0]["role"])
                    conn.close()
                    st.success(f"{h_df.iloc[0]['role']} Login Successful!")
                    st.rerun()
                else:
                    r_df = pd.read_sql_query("SELECT id, store_name, password_hash, store_type FROM retailers WHERE username = ?;", conn, params=(username,))
                    if not r_df.empty and hash_password(password) == r_df.iloc[0]["password_hash"]:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.role = "RETAILER"
                        st.session_state.user_id = int(r_df.iloc[0]["id"])
                        st.session_state.terminal_type = "SERVER"
                        setup_local_environment(r_df.iloc[0]["store_name"])
                        conn.close()
                        st.success("Retailer Login Successful!")
                        st.rerun()
            conn.close()
            st.error("Invalid Credentials!")
    st.stop()

render_header()
st.sidebar.title(f"User: {st.session_state.username}")
st.sidebar.info(f"Role: {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.rerun()

# ================= SUPER ADMIN (OWNER) PANEL =================
if st.session_state.role == "SUPER_ADMIN":
    st.subheader("🛡 Owner Central Command (Global Enterprise)")
    conn = get_db_connection()
    tab1, tab2 = st.tabs(["🌍 All Hierarchy Nodes", "➕ Add Country Head"])
    with tab1:
        all_nodes = pd.read_sql_query("SELECT id, role, name, email, phone, username FROM hierarchy_users;", conn)
        if not all_nodes.empty:
            st.dataframe(all_nodes, use_container_width=True)
        else:
            st.info("No hierarchy nodes created yet.")
    with tab2:
        with st.form("add_country_head"):
            ch_name = st.text_input("Country Head Name")
            ch_email = st.text_input("Email")
            ch_phone = st.text_input("Phone")
            ch_user = st.text_input("Username")
            ch_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Create Country Head"):
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO hierarchy_users (parent_id, role, name, email, phone, username, password_hash) VALUES (NULL, 'COUNTRY_HEAD', ?, ?, ?, ?, ?);", (ch_name, ch_email, ch_phone, ch_user, hash_password(ch_pass)))
                    conn.commit()
                    st.success("Country Head created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    conn.close()

# ================= HIERARCHY MANAGEMENT PANELS =================
elif st.session_state.role in ["COUNTRY_HEAD", "STATE_HEAD", "DISTRICT_HEAD", "SSE"]:
    st.subheader(f"🏢 Hierarchy Portal: {st.session_state.role}")
    conn = get_db_connection()
    tab1, tab2 = st.tabs(["📂 My Downline Network", "➕ Add Sub-Node / Retailer"])
    with tab1:
        sub_users = pd.read_sql_query("SELECT id, role, name, email, phone, username FROM hierarchy_users WHERE parent_id = ?;", conn, params=(st.session_state.user_id,))
        st.dataframe(sub_users, use_container_width=True)
        ret_list = pd.read_sql_query("SELECT id, store_name, owner_name, phone, store_type FROM retailers;", conn)
        st.dataframe(ret_list, use_container_width=True)
    with tab2:
        with st.form("add_sub_node"):
            n_role = st.selectbox("Select Node Type", ["STATE_HEAD", "DISTRICT_HEAD", "SSE", "RETAILER"])
            n_name = st.text_input("Name / Store Name")
            n_email = st.text_input("Email")
            n_phone = st.text_input("Phone")
            n_user = st.text_input("Username")
            n_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Create Node"):
                c = conn.cursor()
                if n_role == "RETAILER":
                    c.execute("INSERT INTO retailers (assigned_sse_id, store_name, owner_name, email, phone, username, password_hash, store_type) VALUES (?, ?, ?, ?, ?, ?, ?, 'SINGLE');", (st.session_state.user_id, n_name, n_name, n_email, n_phone, n_user, hash_password(n_pass)))
                else:
                    c.execute("INSERT INTO hierarchy_users (parent_id, role, name, email, phone, username, password_hash) VALUES (?, ?, ?, ?, ?, ?, ?);", (st.session_state.user_id, n_role, n_name, n_email, n_phone, n_user, hash_password(n_pass)))
                conn.commit()
                st.success("Successfully created!")
                st.rerun()
    conn.close()

# ================= RETAILER PANEL =================
elif st.session_state.role == "RETAILER":
    conn = get_db_connection()
    r_info = pd.read_sql_query("SELECT store_name, store_type FROM retailers WHERE id = ?;", conn, params=(st.session_state.user_id,))
    r_store = r_info.iloc[0]["store_name"] if not r_info.empty else "Medical Store"
    r_type = r_info.iloc[0]["store_type"] if not r_info.empty else "SINGLE"
    conn.close()
    
    st.subheader(f"🏥 {r_store} - Retailer ERP")
    tab_bill, tab_inv, tab_term = st.tabs(["🛒 POS Billing", "📊 Inventory", "💻 Counter Terminals"])
    
    conn = get_db_connection()
    c = conn.cursor()
    with tab_bill:
        st.subheader("Billing Counter")
        df_active = pd.read_sql_query("SELECT name, batch, quantity, price FROM inventory WHERE retailer_id = ? AND quantity > 0;", conn, params=(st.session_state.user_id,))
        if not df_active.empty:
            sel_item = st.selectbox("Select Medicine", df_active['name'].unique())
            med_row = df_active[df_active['name'] == sel_item].iloc[0]
            qty = st.number_input("Quantity", min_value=1, max_value=int(med_row['quantity']), value=1)
            if st.button("Add to Cart"):
                st.session_state.cart.append({"name": sel_item, "batch": med_row['batch'], "price": med_row['price'], "qty": qty, "total": med_row['price']*qty})
                st.success("Added!")
                st.rerun()
            if st.session_state.cart:
                st.dataframe(pd.DataFrame(st.session_state.cart))
                if st.button("Complete Sale"):
                    g_tot = sum(i['total'] for i in st.session_state.cart)
                    inv_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    c.execute("INSERT INTO sales (retailer_id, invoice_number, total_amount) VALUES (?, ?, ?);", (st.session_state.user_id, inv_no, g_tot))
                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE retailer_id = ? AND batch = ?;", (item['qty'], st.session_state.user_id, item['batch']))
                    conn.commit()
                    st.session_state.cart = []
                    st.success(f"Invoice {inv_no} generated!")
                    st.rerun()

    with tab_inv:
        st.subheader("Inventory Stock")
        inv_df = pd.read_sql_query("SELECT name, batch, quantity, price FROM inventory WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
        st.dataframe(inv_df, use_container_width=True)

    with tab_term:
        if r_type == "ENTERPRISE":
            st.subheader("Manage Counter Client Terminals")
            with st.form("add_counter"):
                t_name = st.text_input("Counter Name")
                t_user = st.text_input("Counter Username")
                t_pass = st.text_input("Counter Password", type="password")
                if st.form_submit_button("Create Counter Client"):
                    c.execute("INSERT INTO store_terminals (retailer_id, terminal_name, terminal_type, username, password_hash) VALUES (?, ?, 'CLIENT', ?, ?);", (st.session_state.user_id, t_name, t_user, hash_password(t_pass)))
                    conn.commit()
                    st.success("Counter terminal created!")
                    st.rerun()
            terminals_df = pd.read_sql_query("SELECT terminal_name, username, terminal_type FROM store_terminals WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            st.dataframe(terminals_df, use_container_width=True)
        else:
            st.warning("Counter Terminals are available only in Enterprise Plan.")
    conn.close()
