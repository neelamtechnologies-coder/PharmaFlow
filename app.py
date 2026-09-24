import streamlit as st
from db import init_db, run_query, hash_password
import pandas as pd

# Initialize Database
init_db()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None

# Fetch System Config (Owner Branding & Official UPI)
config_df = run_query("SELECT company_name, super_admin_username, super_admin_password_hash, upi_id FROM system_config LIMIT 1;")
if config_df is not None and not config_df.empty:
    COMPANY_NAME = config_df.iloc[0]["company_name"]
    ADMIN_USER = config_df.iloc[0]["super_admin_username"]
    ADMIN_PASS_HASH = config_df.iloc[0]["super_admin_password_hash"]
    OWNER_UPI = config_df.iloc[0]["upi_id"]
else:
    COMPANY_NAME = "Neelam Technologies"
    ADMIN_USER = "admin"
    ADMIN_PASS_HASH = hash_password("admin")
    OWNER_UPI = "neelamtech@upi"

# --- LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.title(f"💊 {COMPANY_NAME} - ERP Login")
    st.markdown("### Secure Multi-Tier Franchise Access Portal")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            # 1. Super Admin Login
            if username == ADMIN_USER and hash_password(password) == ADMIN_PASS_HASH:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "SUPER_ADMIN"
                st.success("Admin Login Successful!")
                st.rerun()
            else:
                # 2. Wholesaler / Distributor Login
                w_df = run_query("SELECT id, company_name, password_hash FROM wholesalers WHERE username = :u;", {"u": username})
                if w_df is not None and not w_df.empty:
                    if hash_password(password) == w_df.iloc[0]["password_hash"]:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.role = "WHOLESALER"
                        st.session_state.user_id = int(w_df.iloc[0]["id"])
                        st.success("Distributor Login Successful!")
                        st.rerun()
                else:
                    # 3. Retailer / Medical Store Login
                    r_df = run_query("SELECT id, store_name, password_hash FROM retailers WHERE username = :u;", {"u": username})
                    if r_df is not None and not r_df.empty:
                        if hash_password(password) == r_df.iloc[0]["password_hash"]:
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.role = "RETAILER"
                            st.session_state.user_id = int(r_df.iloc[0]["id"])
                            st.success("Retailer Login Successful!")
                            st.rerun()
                
                st.error("Invalid Username or Password!")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title(f"User: {st.session_state.username}")
st.sidebar.info(f"Role: {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.rerun()

# ==========================================
# SUPER ADMIN (OWNER) DASHBOARD
# ==========================================
if st.session_state.role == "SUPER_ADMIN":
    st.title(f"💊 PharmaFlow - Owner Administration Panel")
    st.subheader(f"🛡️ {COMPANY_NAME} | Central Control & Franchise Management")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📂 All Distributors", 
        "➕ Add Distributor", 
        "🏥 All Retailers", 
        "🔄 Renewals & Payments",
        "⚙️ White-Label Settings"
    ])

    with tab1:
        st.markdown("### Registered Distributors (Support Partners)")
        w_df = run_query("SELECT id, company_name, owner_name, email, phone, username, commission_rate, created_at FROM wholesalers ORDER BY id DESC;")
        if w_df is not None and not w_df.empty:
            st.dataframe(w_df, use_container_width=True)
        else:
            st.info("Abhi koi Distributor registered nahi hai.")

    with tab2:
        st.markdown("### Register New Distributor")
        with st.form("add_distributor_form_unique"):
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
                        run_query("""
                            INSERT INTO wholesalers (company_name, owner_name, email, phone, username, password_hash, commission_rate)
                            VALUES (:c, :o, :e, :p, :u, :pw, :cr)
                        """, {
                            "c": c_name, "o": o_name, "e": email, "p": phone,
                            "u": w_user, "pw": hash_password(w_pass), "cr": comm
                        })
                        st.success(f"Distributor '{c_name}' successfully added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Sabhi fields bharein.")

    with tab3:
        st.markdown("### All Medical Stores (Retailers in Network)")
        r_df = run_query("""
            SELECT r.id, r.store_name, r.owner_name, r.email, r.phone, r.subscription_status, r.payment_status, r.plan_expiry_date, w.company_name as assigned_distributor
            FROM retailers r
            LEFT JOIN wholesalers w ON r.wholesaler_id = w.id
            ORDER BY r.id DESC;
        """)
        if r_df is not None and not r_df.empty:
            st.dataframe(r_df, use_container_width=True)
        else:
            st.info("Abhi koi Retailer registered nahi hai.")

    with tab4:
        st.markdown("### Instant Subscription Renewal (Direct Owner Payment)")
        st.info(f"Official Central Payment UPI ID: **{OWNER_UPI}** (Paisa seedha owner ke paas aayega)")
        
        retailers_list = run_query("SELECT id, store_name FROM retailers ORDER BY store_name ASC;")
        if retailers_list is not None and not retailers_list.empty:
            r_opts = {row["store_name"]: row["id"] for _, row in retailers_list.iterrows()}
            sel_r = st.selectbox("Select Retailer for Plan Renewal", list(r_opts.keys()))
            r_id = r_opts[sel_r]
            
            period = st.radio("Renewal Duration", ["1 Month", "1 Year"])
            
            if st.button("Confirm Payment & Extend Plan"):
                if period == "1 Month":
                    q = "UPDATE retailers SET plan_expiry_date = plan_expiry_date + INTERVAL '1 month', payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = :rid;"
                else:
                    q = "UPDATE retailers SET plan_expiry_date = plan_expiry_date + INTERVAL '1 year', payment_status = 'ACTIVE', subscription_status = 'ACTIVE' WHERE id = :rid;"
                
                run_query(q, {"rid": r_id})
                st.success(f"Retailer '{sel_r}' plan successfully extended by {period}!")
                st.rerun()
        else:
            st.info("Renewal ke liye pehle retailer add karein.")

    with tab5:
        st.markdown("### ⚙️ White-Label Settings & Owner UPI")
        with st.form("settings_form"):
            new_comp = st.text_input("Company / Brand Name", value=COMPANY_NAME)
            new_user = st.text_input("Admin Username", value=ADMIN_USER)
            new_pwd = st.text_input("New Admin Password (leave blank to keep current)", type="password")
            new_upi = st.text_input("Official Business UPI ID (for direct payments)", value=OWNER_UPI)
            
            if st.form_submit_button("Update Settings"):
                try:
                    if new_pwd:
                        run_query("UPDATE system_config SET company_name = :c, super_admin_username = :u, super_admin_password_hash = :p, upi_id = :upi WHERE id = 1;",
                                  {"c": new_comp, "u": new_user, "p": hash_password(new_pwd), "upi": new_upi})
                    else:
                        run_query("UPDATE system_config SET company_name = :c, super_admin_username = :u, upi_id = :upi WHERE id = 1;",
                                  {"c": new_comp, "u": new_user, "upi": new_upi})
                    st.success("Settings updated successfully! App reboot ho rahi hai...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# WHOLESALER / DISTRIBUTOR DASHBOARD (SUPPORT)
# ==========================================
elif st.session_state.role == "WHOLESALER":
    w_info = run_query("SELECT company_name, commission_rate FROM wholesalers WHERE id = :id;", {"id": st.session_state.user_id})
    w_name = w_info.iloc[0]["company_name"]
    w_comm = w_info.iloc[0]["commission_rate"]
    
    st.title(f"📦 Distributor Support Portal: {w_name}")
    st.info(f"Your Commission Share: **{w_comm}%** | Role: Ground Support & Retailer Management")

    tab1, tab2 = st.tabs(["📂 My Network Retailers", "➕ Register New Retailer"])

    with tab1:
        st.markdown("### Retailers assigned under your support network")
        my_ret = run_query("""
            SELECT id, store_name, owner_name, email, phone, subscription_status, payment_status, plan_expiry_date, created_at 
            FROM retailers WHERE wholesaler_id = :wid ORDER BY id DESC;
        """, {"wid": st.session_state.user_id})
        
        if my_ret is not None and not my_ret.empty:
            st.dataframe(my_ret, use_container_width=True)
        else:
            st.info("Abhi aapke under koi retailer registered nahi hai.")

    with tab2:
        st.markdown("### Register New Medical Store (Retailer)")
        with st.form("add_retailer_form_unique"):
            s_name = st.text_input("Medical Store Name")
            o_name = st.text_input("Retailer Owner Name")
            email = st.text_input("Retailer Email (Unique)")
            phone = st.text_input("Phone Number")
            r_user = st.text_input("Retailer Login Username")
            r_pass = st.text_input("Retailer Login Password", type="password")
            
            if st.form_submit_button("Register Store"):
                if s_name and email and r_user and r_pass:
                    try:
                        run_query("""
                            INSERT INTO retailers (wholesaler_id, store_name, owner_name, email, phone, username, password_hash)
                            VALUES (:wid, :s, :o, :e, :p, :u, :pw)
                        """, {
                            "wid": st.session_state.user_id, "s": s_name, "o": o_name,
                            "e": email, "p": phone, "u": r_user, "pw": hash_password(r_pass)
                        })
                        st.success(f"Retailer '{s_name}' successfully added to your support network!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Sabhi fields bharein.")

# ==========================================
# RETAILER / MEDICAL STORE DASHBOARD
# ==========================================
elif st.session_state.role == "RETAILER":
    r_info = run_query("""
        SELECT r.store_name, r.subscription_status, r.plan_expiry_date, r.payment_status, w.company_name as support_partner, w.phone as support_phone
        FROM retailers r
        LEFT JOIN wholesalers w ON r.wholesaler_id = w.id
        WHERE r.id = :id;
    """, {"id": st.session_state.user_id})
    
    r_store = r_info.iloc[0]["store_name"]
    r_status = r_info.iloc[0]["subscription_status"]
    r_expiry = r_info.iloc[0]["plan_expiry_date"]
    support_partner = r_info.iloc[0]["support_partner"] or "Direct Neelam Technologies"
    support_phone = r_info.iloc[0]["support_phone"] or "N/A"
    
    st.title(f"🏥 {r_store} - Medical Store ERP")
    st.success(f"Subscription Status: **{r_status}** | Valid Till: **{r_expiry}**")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"🛠️ **Ground Support Partner:**\n{support_partner}\n📞 Contact: {support_phone}")
    
    tab1, tab2 = st.tabs(["💳 Subscription & Renewal Payment", "📦 Inventory & Billing"])
    
    with tab1:
        st.markdown("### Plan Renewal & Secure Payment")
        st.markdown(f"Apne plan ko renew karne ke liye niche diye gaye official owner UPI ID par payment karein.")
        st.info(f"🛡️ **Official Owner UPI ID:** `{OWNER_UPI}`\n(Direct payment to Owner)")
        
        st.warning("Note: Day-to-day assistance aur technical help ke liye apne assigned support partner (Distributor) se sampark karein.")

    with tab2:
        st.markdown("### Store Inventory & Billing Module")
        st.info("Yahan aapki medical store ki items, batch expiry, aur bill generation manage hogi.")
