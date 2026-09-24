import streamlit as st
from db import init_db, run_query, hash_password

# Initialize Database
init_db()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.wholesaler_id = None

# Fetch System Config
config_df = run_query("SELECT company_name, super_admin_username, super_admin_password_hash, upi_id FROM system_config LIMIT 1;")
if config_df is not None and not config_df.empty:
    COMPANY_NAME = config_df.iloc[0]["company_name"]
    ADMIN_USER = config_df.iloc[0]["super_admin_username"]
    ADMIN_PASS_HASH = config_df.iloc[0]["super_admin_password_hash"]
    DEFAULT_UPI = config_df.iloc[0]["upi_id"]
else:
    COMPANY_NAME = "Neelam Technologies"
    ADMIN_USER = "admin"
    ADMIN_PASS_HASH = hash_password("admin")
    DEFAULT_UPI = "neelamtech@upi"

# --- LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.title(f"💊 {COMPANY_NAME} - ERP Login")
    st.markdown("### Multi-Tier Reseller Portal (Super Admin & Wholesaler)")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            # 1. Check Super Admin Login
            if username == ADMIN_USER and hash_password(password) == ADMIN_PASS_HASH:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "SUPER_ADMIN"
                st.success("Super Admin Login Successful!")
                st.rerun()
            else:
                # 2. Check Wholesaler Login
                wholesaler_df = run_query("SELECT id, company_name, password_hash, upi_id FROM wholesalers WHERE username = :u;", {"u": username})
                if wholesaler_df is not None and not wholesaler_df.empty:
                    stored_hash = wholesaler_df.iloc[0]["password_hash"]
                    if hash_password(password) == stored_hash:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.role = "WHOLESALER"
                        st.session_state.wholesaler_id = int(wholesaler_df.iloc[0]["id"])
                        st.success("Wholesaler Login Successful!")
                        st.rerun()
                
                st.error("Invalid Username or Password!")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title(f"User: {st.session_state.username}")
st.sidebar.info(f"Role: {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.wholesaler_id = None
    st.rerun()

# ==========================================
# SUPER ADMIN DASHBOARD
# ==========================================
if st.session_state.role == "SUPER_ADMIN":
    st.title(f"💊 PharmaFlow - Super Admin Panel")
    st.subheader(f"🛡️ {COMPANY_NAME} - Central Management")

    tab1, tab2, tab3 = st.tabs([
        "📂 All Distributors (Wholesalers)", 
        "➕ Add Distributor", 
        "⚙️ White-Label Settings"
    ])

    with tab1:
        st.markdown("### Registered Distributors List")
        w_df = run_query("SELECT id, company_name, owner_name, email, phone, username, upi_id, plan_expiry_date FROM wholesalers ORDER BY id DESC")
        if w_df is not None and not w_df.empty:
            st.dataframe(w_df, use_container_width=True)
        else:
            st.info("Abhi koi Distributor registered nahi hai.")

    with tab2:
        st.markdown("### Register New Distributor (Wholesaler)")
        with st.form("add_distributor_form"):
            c_name = st.text_input("Distributor Company Name")
            o_name = st.text_input("Owner Name")
            email = st.text_input("Email (Unique)")
            phone = st.text_input("Phone Number")
            w_username = st.text_input("Distributor Login Username")
            w_password = st.text_input("Distributor Login Password", type="password")
            w_upi = st.text_input("Distributor UPI ID (for their retailers)")
            
            submitted = st.form_submit_button("Create Distributor")
            
            if submitted:
                if c_name and email and w_username and w_password:
                    try:
                        pass_hash = hash_password(w_password)
                        query = """
                            INSERT INTO wholesalers (company_name, owner_name, email, phone, username, password_hash, upi_id)
                            VALUES (:c_name, :o_name, :email, :phone, :w_username, :pass_hash, :w_upi)
                        """
                        run_query(query, {
                            "c_name": c_name, "o_name": o_name, "email": email, "phone": phone,
                            "w_username": w_username, "pass_hash": pass_hash, "w_upi": w_upi
                        })
                        st.success(f"Distributor '{c_name}' successfully created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating distributor: {e}")
                else:
                    st.warning("Sabhi zaroori fields bharein.")

    with tab3:
        st.markdown("### ⚙️ White-Label & Owner Profile Settings")
        with st.form("settings_form"):
            new_company = st.text_input("Company / Brand Name", value=COMPANY_NAME)
            new_admin_user = st.text_input("Admin Username", value=ADMIN_USER)
            new_password = st.text_input("New Admin Password (leave blank to keep current)", type="password")
            new_upi = st.text_input("Official Business UPI ID", value=DEFAULT_UPI)
            
            save_settings = st.form_submit_button("Update Settings")
            
            if save_settings:
                try:
                    if new_password:
                        pass_hash = hash_password(new_password)
                        q = "UPDATE system_config SET company_name = :c, super_admin_username = :u, super_admin_password_hash = :p, upi_id = :upi WHERE id = 1;"
                        run_query(q, {"c": new_company, "u": new_admin_user, "p": pass_hash, "upi": new_upi})
                    else:
                        q = "UPDATE system_config SET company_name = :c, super_admin_username = :u, upi_id = :upi WHERE id = 1;"
                        run_query(q, {"c": new_company, "u": new_admin_user, "upi": new_upi})
                    
                    st.success("Settings updated successfully! App reboot ho rahi hai...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# WHOLESALER / DISTRIBUTOR DASHBOARD
# ==========================================
elif st.session_state.role == "WHOLESALER":
    st.title(f"📦 Distributor Dashboard")
    
    # Fetch Wholesaler Details
    w_info = run_query("SELECT company_name, upi_id FROM wholesalers WHERE id = :id;", {"id": st.session_state.wholesaler_id})
    w_company = w_info.iloc[0]["company_name"]
    w_upi = w_info.iloc[0]["upi_id"]
    
    st.subheader(f"🏢 {w_company} | Payment UPI: `{w_upi}`")

    tab1, tab2 = st.tabs(["📂 My Retailers (Medical Stores)", "➕ Add New Retailer"])

    with tab1:
        st.markdown("### Retailers under your distribution")
        ret_df = run_query("SELECT id, store_name, owner_name, email, phone, username, created_at FROM retailers WHERE wholesaler_id = :wid ORDER BY id DESC", {"wid": st.session_state.wholesaler_id})
        if ret_df is not None and not ret_df.empty:
            st.dataframe(ret_df, use_container_width=True)
        else:
            st.info("Abhi aapke under koi retailer add nahi hai.")

    with tab2:
        st.markdown("### Add New Medical Store (Retailer)")
        with st.form("add_retailer_form"):
            store_name = st.text_input("Medical Store Name")
            owner_name = st.text_input("Retailer Owner Name")
            email = st.text_input("Retailer Email (Unique)")
            phone = st.text_input("Phone Number")
            r_username = st.text_input("Retailer Login Username")
            r_password = st.text_input("Retailer Login Password", type="password")
            
            sub_retailer = st.form_submit_button("Register Retailer")
            
            if sub_retailer:
                if store_name and email and r_username and r_password:
                    try:
                        r_pass_hash = hash_password(r_password)
                        q = """
                            INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, username, password_hash)
                            VALUES (:wid, :s_name, :o_name, :email, :phone, :r_user, :r_pass)
                        """
                        run_query(q, {
                            "wid": st.session_state.wholesaler_id,
                            "s_name": store_name,
                            "o_name": owner_name,
                            "email": email,
                            "phone": phone,
                            "r_user": r_username,
                            "r_pass": r_pass_hash
                        })
                        st.success(f"Retailer '{store_name}' successfully added under your network!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding retailer: {e}")
                else:
                    st.warning("Sabhi fields bharna anivarya hai.")
