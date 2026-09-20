import streamlit as st
from datetime import date, timedelta
from db import run_query, execute_query
from auth import authenticate_user, hash_password

st.set_page_config(page_title="PharmaFlow ERP", page_icon="💊", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

st.title("💊 PharmaFlow - Cloud Medical ERP")
st.caption("A Product of Neelam Technologies | Multi-Tenant Cloud Architecture")
st.markdown("---")

# 1. LOGGED IN STATE
if st.session_state.user:
    u = st.session_state.user
    
    st.sidebar.success(f"User: **{u['username']}** ({u['role']})")
    if u.get("store_name"):
        st.sidebar.info(f"Store: **{u['store_name']}**")
    
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

    # --- A. MASTER ADMIN AUDIT PANEL ---
    if u["role"] == "WHOLESALER" and u["username"] == "admin":
        st.subheader("🛡️ Neelam Technologies - Central Audit & Licensing")
        st.info("Master Alert Inbox: contact.neelamtechnologies@gmail.com")
        
        tab_stores, tab_renew = st.tabs(["📋 All Onboarded Stores", "⚡ Instant Plan Renewal"])
        
        with tab_stores:
            st.write("Distributors dwara onboard kiye gaye sabhi retail accounts:")
            all_stores = run_query("""
                SELECT store_id, store_name, owner_name, phone, email, distributor_code, 
                       subscription_status, expiry_date, created_at
                FROM stores 
                ORDER BY created_at DESC;
            """)
            st.dataframe(all_stores, use_container_width=True)

        with tab_renew:
            st.write("Payment receive hone par store ki validity extend karein:")
            active_list = run_query("SELECT store_id, store_name, phone FROM stores;")
            if not active_list.empty:
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    store_choice = st.selectbox(
                        "Store Chunein:", 
                        active_list["store_id"], 
                        format_func=lambda x: f"ID {x} - {active_list.loc[active_list['store_id'] == x, 'store_name'].values[0]}"
                    )
                with c2:
                    add_months = st.selectbox("Validity Add Karein:", [1, 3, 6, 12], index=0)
                with c3:
                    st.write("")
                    st.write("")
                    if st.button("Extend License", use_container_width=True):
                        new_exp = date.today() + timedelta(days=add_months * 30)
                        execute_query(
                            "UPDATE stores SET subscription_status = 'ACTIVE', expiry_date = :exp WHERE store_id = :sid",
                            {"exp": new_exp, "sid": store_choice}
                        )
                        st.success(f"Store #{store_choice} ka subscription {add_months} mahine ke liye renew ho gaya!")
                        st.rerun()

    # --- B. CHEMIST VIEW (AUTO-TRIAL & EXPIRY LOCK) ---
    else:
        store_check = run_query(
            "SELECT subscription_status, expiry_date FROM stores WHERE store_id = :sid", 
            {"sid": u["store_id"]}
        ).iloc[0]
        
        today = date.today()
        expiry = store_check["expiry_date"]
        days_left = (expiry - today).days

        # HARD EXPIRY LOCKOUT
        if days_left < 0:
            st.error("⛔ AAPKA PHARMAFLOW LICENSE EXPIRE HO CHUKA HAI")
            st.warning("Aapka 7 din ka free trial ya subscription period poora ho gaya hai. Service continue rakhne ke liye apne distributor se renewal karwayein.")
            st.info("Technical Support: contact.neelamtechnologies@gmail.com | Powered by Neelam Technologies")
            st.stop()

        # TRIAL RUNNER BANNER
        if store_check["subscription_status"] == "TRIAL":
            st.warning(f"⏳ Free Trial Active: Aapke paas **{days_left} din** bache hain. Uske baad automated lock lag jayega.")
        else:
            st.success(f"✅ Subscription Active (Valid till: {expiry})")

        # Main Store Interface
        st.subheader(f"Store: {u['store_name']}")
        t1, t2, t3 = st.tabs(["🛒 Quick Billing", "📦 Inventory / Stock", "📊 Sales Summary"])
        
        with t1:
            st.write("⚡ Fast Chemist Billing POS (Ready)")
        with t2:
            inv_df = run_query(
                "SELECT medicine_name, batch_no, expiry_date, quantity, mrp FROM inventory WHERE store_id = :s;", 
                {"s": u["store_id"]}
            )
            st.dataframe(inv_df, use_container_width=True)
        with t3:
            st.write("Turnover aur GST details.")

# 2. LOGIN & ONBOARDING STATE
else:
    mode = st.radio("Chunein:", ["Chemist / Admin Login", "Register New Pharmacy (7-Day Instant Trial)"], horizontal=True)

    if mode == "Chemist / Admin Login":
        st.subheader("Login Portal")
        with st.form("login_form"):
            uname = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                if uname == "admin" and pwd == "admin123":
                    st.session_state.user = {
                        "user_id": 0, "store_id": None, "username": "admin", 
                        "role": "WHOLESALER", "store_name": "Neelam Technologies HQ"
                    }
                    st.rerun()

                user = authenticate_user(uname, pwd)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid Username ya Password.")

    else:
        st.subheader("Register New Pharmacy (Instant 7-Day Trial)")
        with st.form("reg_form"):
            c1, c2 = st.columns(2)
            with c1:
                s_name = st.text_input("Medical Store Name *")
                o_name = st.text_input("Owner Name *")
                phone = st.text_input("Phone Number (10 digits) *")
                email = st.text_input("Retailer Email ID *", placeholder="store@example.com")
                dl_no = st.text_input("Drug License No.")
            with c2:
                dist_code = st.text_input("Distributor Agency / Code *", placeholder="e.g. INDORE-MEDICO-01")
                username = st.text_input("Store Login Username *")
                password = st.text_input("Store Login Password *", type="password")

            if st.form_submit_button("Create Account & Start 7-Day Trial", use_container_width=True):
                if not (s_name and o_name and phone and email and username and password and dist_code):
                    st.warning("Sabhi zaroori details (email sahit) bharein.")
                else:
                    trial_exp = date.today() + timedelta(days=7)
                    
                    try:
                        ins_store = """
                            INSERT INTO stores (store_name, owner_name, phone, email, drug_license_no, subscription_status, expiry_date, distributor_code)
                            VALUES (:s_name, :o_name, :phone, :email, :dl, 'TRIAL', :exp, :dist);
                        """
                        execute_query(ins_store, {
                            "s_name": s_name, "o_name": o_name, "phone": phone, "email": email,
                            "dl": dl_no, "exp": trial_exp, "dist": dist_code
                        })
                        
                        store_res = run_query("SELECT store_id FROM stores WHERE phone = :p ORDER BY store_id DESC LIMIT 1;", {"p": phone})
                        new_store_id = int(store_res["store_id"].iloc[0])

                        execute_query("""
                            INSERT INTO users (store_id, username, password_hash, role)
                            VALUES (:s_id, :uname, :pwd, 'OWNER');
                        """, {"s_id": new_store_id, "uname": username, "pwd": hash_password(password)})

                        st.success(f"🎉 Store '{s_name}' register ho gaya! Chemist login details ready hain.")
                            
                    except Exception as err:
                        st.error(f"Registration failed: {err}")