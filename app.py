import streamlit as st
from db import init_db, run_query, hash_password

# Initialize Database
init_db()

# Session state for authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""

# Fetch System Config (White-Label Branding)
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
    st.markdown("### Secure Multi-Tenant Access Portal")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username == ADMIN_USER and hash_password(password) == ADMIN_PASS_HASH:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "SUPER_ADMIN"
                st.success("Login Successful!")
                st.rerun()
            else:
                st.error("Invalid Username or Password!")
    st.stop()

# --- MAIN DASHBOARD (AFTER LOGIN) ---
st.sidebar.title(f"User: {st.session_state.username}")
st.sidebar.info(f"Role: {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.rerun()

st.title(f"💊 PharmaFlow - Cloud Medical ERP")
st.subheader(f"🛡️ {COMPANY_NAME} - Central Administration & Licensing")

tab1, tab2, tab3, tab4 = st.tabs([
    "📂 Onboarded Stores", 
    "➕ Onboard Store", 
    "🔄 Plan Renewal", 
    "⚙️ White-Label Settings"
])

with tab1:
    st.markdown("### Registered Medical Stores List")
    stores_df = run_query("SELECT id, store_name, owner_name, email, phone, subscription_status, payment_status, plan_expiry_date FROM stores ORDER BY id DESC")
    if stores_df is not None and not stores_df.empty:
        st.dataframe(stores_df, use_container_width=True)
    else:
        st.info("Abhi koi registered store nahi hai.")

with tab2:
    st.markdown("### Register New Medical Store")
    with st.form("onboard_form"):
        store_name = st.text_input("Store Name")
        owner_name = st.text_input("Owner Name")
        email = st.text_input("Store Email (Unique)")
        phone = st.text_input("Phone Number")
        
        st.markdown("---")
        st.markdown("#### 💳 Payment & UPI Configuration")
        store_upi = st.text_input("Store UPI ID (Leave blank to use default)", value=DEFAULT_UPI)
        bank_details = st.text_area("Bank Details / IFSC")
        
        submitted = st.form_submit_button("Onboard Store")
        
        if submitted:
            if store_name and email:
                try:
                    query = """
                        INSERT INTO stores (store_name, owner_name, email, phone, upi_id, bank_details, payment_status)
                        VALUES (:store_name, :owner_name, :email, :phone, :upi_id, :bank_details, 'PENDING')
                    """
                    run_query(query, {
                        "store_name": store_name,
                        "owner_name": owner_name,
                        "email": email,
                        "phone": phone,
                        "upi_id": store_upi,
                        "bank_details": bank_details
                    })
                    st.success(f"Store '{store_name}' successfully onboarded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error registering store: {e}")
            else:
                st.warning("Store Name aur Email bharna anivarya hai.")

with tab3:
    st.markdown("### Instant Plan Renewal (Exact 1 Month / 1 Year Extension)")
    stores_list = run_query("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    
    if stores_list is not None and not stores_list.empty:
        store_options = {row["store_name"]: row["id"] for _, row in stores_list.iterrows()}
        selected_store = st.selectbox("Select Store for Renewal", list(store_options.keys()))
        store_id = store_options[selected_store]
        
        st.info(f"Official Payment UPI QR Handle: **{DEFAULT_UPI}**")
        
        renewal_type = st.radio("Select Extension Duration", ["1 Month", "1 Year"])
        
        if st.button("Confirm & Renew Plan"):
            if renewal_type == "1 Month":
                query = "UPDATE stores SET plan_expiry_date = plan_expiry_date + INTERVAL '1 month', payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = :store_id;"
            else:
                query = "UPDATE stores SET plan_expiry_date = plan_expiry_date + INTERVAL '1 year', payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = :store_id;"
            
            run_query(query, {"store_id": store_id})
            st.success(f"Store '{selected_store}' subscription successfully extended by {renewal_type}!")
            st.rerun()
    else:
        st.info("Renewal ke liye pehle koi store onboard karein.")

with tab4:
    st.markdown("### ⚙️ White-Label & Owner Profile Settings")
    st.markdown("Yahan naya owner apni company ka naam, admin username/password, aur official payment UPI ID change kar sakta hai.")
    
    with st.form("settings_form"):
        new_company = st.text_input("Company / Brand Name", value=COMPANY_NAME)
        new_admin_user = st.text_input("Admin Username", value=ADMIN_USER)
        new_password = st.text_input("New Admin Password (leave blank to keep current)", type="password")
        new_upi = st.text_input("Official Business UPI ID", value=DEFAULT_UPI)
        
        save_settings = st.form_submit_button("Update White-Label Settings")
        
        if save_settings:
            try:
                if new_password:
                    pass_hash = hash_password(new_password)
                    q = "UPDATE system_config SET company_name = :c, super_admin_username = :u, super_admin_password_hash = :p, upi_id = :upi WHERE id = 1;"
                    run_query(q, {"c": new_company, "u": new_admin_user, "p": pass_hash, "upi": new_upi})
                else:
                    q = "UPDATE system_config SET company_name = :c, super_admin_username = :u, upi_id = :upi WHERE id = 1;"
                    run_query(q, {"c": new_company, "u": new_admin_user, "upi": new_upi})
                
                st.success("White-Label Settings successfully updated! App reboot ho rahi hai...")
                st.rerun()
            except Exception as e:
                st.error(f"Error updating settings: {e}")
