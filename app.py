import streamlit as st, pandas as pd
from datetime import datetime, timedelta; from db import run_query, init_db; from auth import hash_password, verify_password

st.set_page_config(
    page_title="PharmaFlow - Cloud Medical ERP",
    page_icon="💊",
    layout="wide"
)

try:
    init_db()
except Exception:
    pass

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

st.title("💊 PharmaFlow - Cloud Medical ERP")
st.caption("A Product of Neelam Technologies | Multi-Tenant Cloud Architecture")
st.markdown("---")

if not st.session_state.logged_in:
    auth_mode = st.radio(
        "Chunein:",
        ["Chemist / Admin Login", "Register New Pharmacy (7-Day Instant Trial)"],
        horizontal=True
    )

    if auth_mode == "Chemist / Admin Login":
        st.subheader("Login Portal")
        col1, col2 = st.columns([1, 1])
        with col1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Sign In", type="primary", use_container_width=True):
                if username == "admin" and password == "admin123":
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        "username": "admin",
                        "role": "WHOLESALER",
                        "store_name": "Neelam Technologies HQ",
                        "store_id": 0,
                        "subscription_status": "ACTIVE"
                    }
                    st.rerun()
                else:
                    user_df = run_query(
                        """
                        SELECT u.id, u.username, u.password_hash, u.role, u.store_id,
                               s.store_name, s.subscription_status, s.plan_expiry_date
                        FROM users u
                        LEFT JOIN stores s ON u.store_id = s.id
                        WHERE u.username = :username
                        """,
                        {"username": username}
                    )
                    if user_df is not None and not user_df.empty:
                        user = user_df.iloc[0]
                        if verify_password(password, user["password_hash"]):
                            if user["role"] != "WHOLESALER":
                                expiry = pd.to_datetime(user["plan_expiry_date"])
                                if datetime.now() > expiry:
                                    st.error("⚠️ Aapka 7-day trial/license expire ho gaya hai.")
                                    st.stop()
                            st.session_state.logged_in = True
                            st.session_state.user_info = {
                                "username": user["username"],
                                "role": user["role"],
                                "store_name": user["store_name"],
                                "store_id": user["store_id"],
                                "subscription_status": user["subscription_status"]
                            }
                            st.rerun()
                        else:
                            st.error("Galat password!")
                    else:
                        st.error("User nahi mila!")
    else:
        st.subheader("Register Pharmacy - 7-Day Free Trial")
        with st.form("register_store_form"):
            s_name = st.text_input("Store / Pharmacy Name *")
            o_name = st.text_input("Owner Full Name *")
            s_email = st.text_input("Official Email *")
            s_phone = st.text_input("Phone Number")
            dist_code = st.text_input("Distributor / Referral Code (Optional)")
            admin_user = st.text_input("Create Admin Username *")
            admin_pass = st.text_input("Create Password *", type="password")
            submitted = st.form_submit_button("Start 7-Day Instant Trial", type="primary")

            if submitted:
                if not s_name or not s_email or not admin_user or not admin_pass:
                    st.warning("Kripya sabhi mandatory (*) fields bharein.")
                else:
                    try:
                        expiry_date = datetime.now() + timedelta(days=7)
                        run_query(
                            """
                            INSERT INTO stores (store_name, owner_name, email, phone, distributor_code, subscription_status, plan_expiry_date)
                            VALUES (:s_name, :o_name, :email, :phone, :dist, 'TRIAL', :expiry)
                            """,
                            {
                                "s_name": s_name,
                                "o_name": o_name,
                                "email": s_email,
                                "phone": s_phone,
                                "dist": dist_code,
                                "expiry": expiry_date
                            }
                        )
                        s_df = run_query("SELECT id FROM stores WHERE email = :email", {"email": s_email})
                        store_id = int(s_df.iloc[0]["id"])
                        hashed = hash_password(admin_pass)
                        run_query(
                            """
                            INSERT INTO users (store_id, username, password_hash, role)
                            VALUES (:s_id, :uname, :pwd, 'CHEMIST')
                            """,
                            {
                                "s_id": store_id,
                                "uname": admin_user,
                                "pwd": hashed
                            }
                        )
                        st.success("✅ Store successfully registered! Aap Sign In kar sakte hain.")
                    except Exception as e:
                        st.error(f"Registration fail hua: {e}")
    st.stop()

with st.sidebar:
    st.success(f"User: **{st.session_state.user_info['username']}** ({st.session_state.user_info['role']})")
    st.info(f"Store: **{st.session_state.user_info['store_name']}**")
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.rerun()

user_role = st.session_state.user_info["role"]
store_id = st.session_state.user_info["store_id"]

if user_role == "WHOLESALER":
    st.header("🛡️ Neelam Technologies - Central Audit & Licensing")
    tab1, tab2 = st.tabs(["📋 All Onboarded Stores", "⚡ Instant Plan Renewal"])
    with tab1:
        stores_df = run_query("SELECT id, store_name, owner_name, email, phone, subscription_status, plan_expiry_date FROM stores ORDER BY id DESC")
        if stores_df is not None and not stores_df.empty:
            st.dataframe(stores_df, use_container_width=True)
        else:
            st.write("Abhi koi registered store nahi hai.")
    with tab2:
        with st.form("renew_form"):
            target_store_id = st.number_input("Store ID", min_value=1, step=1)
            additional_days = st.selectbox("Plan Extension", [30, 90, 180, 365], index=0)
            if st.form_submit_button("Renew License", type="primary"):
                new_expiry = datetime.now() + timedelta(days=additional_days)
                run_query("UPDATE stores SET subscription_status = 'ACTIVE', plan_expiry_date = :exp WHERE id = :s_id", {"exp": new_expiry, "s_id": target_store_id})
                st.success("Subscription renew ho gaya!")
else:
    st.header(f"🏪 {st.session_state.user_info['store_name']} - Dashboard")
    menu = st.selectbox("Navigation:", ["💊 Inventory & Medicine Stock", "🧾 Point of Sale (Billing)", "📊 Sales History"])
    if menu == "💊 Inventory & Medicine Stock":
        with st.expander("➕ Add New Medicine"):
            with st.form("add_med"):
                m_name = st.text_input("Medicine Name *")
                b_no = st.text_input("Batch Number *")
                exp_date = st.date_input("Expiry Date *")
                qty = st.number_input("Quantity *", min_value=1, value=10)
                mrp = st.number_input("MRP (₹) *", min_value=0.0, value=50.0)
                rate = st.number_input("Billing Rate (₹) *", min_value=0.0, value=40.0)
                if st.form_submit_button("Save Stock", type="primary"):
                    run_query("INSERT INTO inventory (store_id, medicine_name, batch_number, expiry_date, quantity, mrp, rate) VALUES (:s_id, :m_name, :b_no, :exp_date, :qty, :mrp, :rate)", {"s_id": store_id, "m_name": m_name, "b_no": b_no, "exp_date": exp_date, "qty": qty, "mrp": mrp, "rate": rate})
                    st.success("Stock jud gaya!")
        inv_df = run_query("SELECT medicine_name, batch_number, expiry_date, quantity, mrp, rate FROM inventory WHERE store_id = :s_id", {"s_id": store_id})
        if inv_df is not None and not inv_df.empty:
            st.dataframe(inv_df, use_container_width=True)
    elif menu == "🧾 Point of Sale (Billing)":
        st.subheader("Billing Portal")
        st.info("Inventory se medicines select karke invoice banayein.")
    elif menu == "📊 Sales History":
        st.subheader("Sales Register")
        sales_df = run_query("SELECT invoice_number, customer_name, total_amount, created_at FROM sales WHERE store_id = :s_id", {"s_id": store_id})
        if sales_df is not None and not sales_df.empty:
            st.dataframe(sales_df, use_container_width=True)
