import streamlit as st
import pandas as pd
from datetime import datetime
from db import get_db_connection, hash_password, init_db, setup_local_environment

init_db()
setup_local_environment()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None
    st.session_state.terminal_type = "SERVER"

if "cart" not in st.session_state:
    st.session_state.cart = []

ROLE_RANKS = {
    "SUPER_ADMIN": 5,
    "COUNTRY_HEAD": 4,
    "STATE_HEAD": 3,
    "ZONAL_MANAGER": 2,
    "SSE": 1,
    "RETAILER": 0
}

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
                        conn.close()
                        st.success("Retailer Login Successful!")
                        st.rerun()
            conn.close()
            st.error("Invalid Credentials!")
    st.stop()

render_header()
st.sidebar.title(f"User: {st.session_state.username}")
st.sidebar.info(f"Role: {st.session_state.role}")

st.sidebar.markdown("---")
st.sidebar.subheader("🖥 Quick Actions")

shortcut_content = f"""[InternetShortcut]
URL=https://techpharma-solutions.streamlit.app
"""

st.sidebar.download_button(
    label="📥 Download Desktop Icon",
    data=shortcut_content,
    file_name="TechPharma Solutions.url",
    mime="text/plain",
    help="Click to download shortcut directly to your Desktop!"
)

if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.rerun()

if st.session_state.role == "SUPER_ADMIN":
    st.subheader("🛡 Owner Central Command (Global Enterprise)")
    conn = get_db_connection()
    tab1, tab2, tab3, tab4 = st.tabs(["🌍 All Nodes", "➕ Add Country Head", "✏️ Edit / Delete Nodes", "🔄 Transfer Retailer"])
    
    with tab1:
        all_nodes = pd.read_sql_query("SELECT id, role, name, email, phone, username FROM hierarchy_users;", conn)
        st.markdown("### Hierarchy Members")
        if not all_nodes.empty:
            st.dataframe(all_nodes, use_container_width=True)
        else:
            st.info("No hierarchy nodes created yet.")
        
        all_rets = pd.read_sql_query("SELECT id, assigned_sse_id, store_name, owner_name, gstin, subscription_status, payment_status FROM retailers;", conn)
        st.markdown("### All Retailers (with GSTIN)")
        if not all_rets.empty:
            st.dataframe(all_rets, use_container_width=True)
        else:
            st.info("No retailers registered yet.")
            
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
                    
    with tab3:
        st.subheader("Manage / Delete Hierarchy Nodes")
        nodes_df = pd.read_sql_query("SELECT id, role, name, username FROM hierarchy_users;", conn)
        if not nodes_df.empty:
            sel_node_id = st.selectbox("Select Node to Manage", nodes_df['id'], format_func=lambda x: f"{nodes_df[nodes_df['id']==x]['name'].values[0]} ({nodes_df[nodes_df['id']==x]['role'].values[0]})")
            node_row = nodes_df[nodes_df['id'] == sel_node_id].iloc[0]
            
            with st.form("edit_node_form"):
                e_name = st.text_input("Name", value=node_row['name'])
                e_pass = st.text_input("New Password (leave blank to keep unchanged)", type="password")
                col1, col2 = st.columns(2)
                update_btn = col1.form_submit_button("Update Node")
                delete_btn = col2.form_submit_button("Delete Node", type="primary")
                
                c = conn.cursor()
                if update_btn:
                    if e_pass:
                        c.execute("UPDATE hierarchy_users SET name = ?, password_hash = ? WHERE id = ?;", (e_name, hash_password(e_pass), int(sel_node_id)))
                    else:
                        c.execute("UPDATE hierarchy_users SET name = ? WHERE id = ?;", (e_name, int(sel_node_id)))
                    conn.commit()
                    st.success("Node updated successfully!")
                    st.rerun()
                elif delete_btn:
                    c.execute("DELETE FROM hierarchy_users WHERE id = ?;", (int(sel_node_id),))
                    conn.commit()
                    st.success("Node deleted successfully!")
                    st.rerun()
        else:
            st.info("No nodes available to manage.")
            
    with tab4:
        st.subheader("Transfer Retailer to Another SSE")
        rets_all = pd.read_sql_query("SELECT id, store_name, assigned_sse_id FROM retailers;", conn)
        sses_all = pd.read_sql_query("SELECT id, name FROM hierarchy_users WHERE role = 'SSE';", conn)
        
        if not rets_all.empty and not sses_all.empty:
            with st.form("transfer_ret_admin"):
                r_sel = st.selectbox("Select Retailer", rets_all['id'], format_func=lambda x: rets_all[rets_all['id']==x]['store_name'].values[0])
                s_sel = st.selectbox("Select New SSE", sses_all['id'], format_func=lambda x: sses_all[sses_all['id']==x]['name'].values[0])
                if st.form_submit_button("Transfer Retailer"):
                    c = conn.cursor()
                    c.execute("UPDATE retailers SET assigned_sse_id = ? WHERE id = ?;", (int(s_sel), int(r_sel)))
                    conn.commit()
                    st.success("Retailer successfully transferred to new SSE!")
                    st.rerun()
        else:
            st.warning("Retailers or SSEs are missing in the system.")
    conn.close()

elif st.session_state.role in ["COUNTRY_HEAD", "STATE_HEAD", "ZONAL_MANAGER", "SSE"]:
    st.subheader(f"🏢 Hierarchy Portal: {st.session_state.role}")
    conn = get_db_connection()
    tab1, tab2, tab3, tab4 = st.tabs(["📂 My Downline", "➕ Add Sub-Node / Retailer", "✏️ Edit / Delete Downline", "🔄 Transfer Retailer"])
    
    with tab1:
        sub_users = pd.read_sql_query("SELECT id, role, name, email, phone, username FROM hierarchy_users WHERE parent_id = ?;", conn, params=(st.session_state.user_id,))
        st.markdown("### Sub-Hierarchy Nodes")
        st.dataframe(sub_users, use_container_width=True)
        
        ret_list = pd.read_sql_query("SELECT id, store_name, owner_name, gstin, subscription_status, payment_status, store_type FROM retailers WHERE assigned_sse_id = ?;", conn, params=(st.session_state.user_id,))
        st.markdown("### Assigned Retailers")
        st.dataframe(ret_list, use_container_width=True)
        
    with tab2:
        with st.form("add_sub_node"):
            current_rank = ROLE_RANKS.get(st.session_state.role, 0)
            available_roles = [r for r, rank in ROLE_RANKS.items() if rank < current_rank]
            
            n_role = st.selectbox("Select Node Type", available_roles)
            n_name = st.text_input("Name / Store Name")
            n_email = st.text_input("Email")
            n_phone = st.text_input("Phone")
            n_user = st.text_input("Username")
            n_pass = st.text_input("Password", type="password")
            n_gstin = st.text_input("GSTIN Number (if Retailer)", value="27AAAAA0000A1Z5")
            if st.form_submit_button("Create Node"):
                c = conn.cursor()
                try:
                    if n_role == "RETAILER":
                        c.execute("INSERT INTO retailers (assigned_sse_id, store_name, owner_name, email, phone, username, password_hash, store_type, subscription_status, payment_status, gstin) VALUES (?, ?, ?, ?, ?, ?, ?, 'SINGLE', 'TRIAL', 'ACTIVE', ?);", (st.session_state.user_id, n_name, n_name, n_email, n_phone, n_user, hash_password(n_pass), n_gstin))
                    else:
                        c.execute("INSERT INTO hierarchy_users (parent_id, role, name, email, phone, username, password_hash) VALUES (?, ?, ?, ?, ?, ?, ?);", (st.session_state.user_id, n_role, n_name, n_email, n_phone, n_user, hash_password(n_pass)))
                    conn.commit()
                    st.success("Successfully created!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
                    
    with tab3:
        st.subheader("Edit or Delete Downline Users / Retailers")
        downline_nodes = pd.read_sql_query("SELECT id, role, name, username FROM hierarchy_users WHERE parent_id = ?;", conn, params=(st.session_state.user_id,))
        downline_rets = pd.read_sql_query("SELECT id, store_name as name, 'RETAILER' as role, username, subscription_status, payment_status, gstin FROM retailers WHERE assigned_sse_id = ?;", conn, params=(st.session_state.user_id,))
        
        combined_downline = pd.concat([downline_nodes, downline_rets], ignore_index=True)
        
        if not combined_downline.empty:
            sel_id = st.selectbox("Select Downline Member", combined_downline['id'], format_func=lambda x: f"{combined_downline[combined_downline['id']==x]['name'].values[0]} ({combined_downline[combined_downline['id']==x]['role'].values[0]})")
            selected_member = combined_downline[combined_downline['id'] == sel_id].iloc[0]
            m_role = selected_member['role']
            
            with st.form("edit_downline_form"):
                e_name = st.text_input("Name / Store Name", value=selected_member['name'])
                e_gstin = st.text_input("GSTIN", value=selected_member.get('gstin', '') if m_role == 'RETAILER' else '')
                e_pass = st.text_input("New Password (leave blank to keep unchanged)", type="password")
                col1, col2 = st.columns(2)
                up_btn = col1.form_submit_button("Update Member")
                del_btn = col2.form_submit_button("Delete Member", type="primary")
                
                c = conn.cursor()
                if up_btn:
                    if m_role == "RETAILER":
                        if e_pass:
                            c.execute("UPDATE retailers SET store_name = ?, gstin = ?, password_hash = ? WHERE id = ?;", (e_name, e_gstin, hash_password(e_pass), int(sel_id)))
                        else:
                            c.execute("UPDATE retailers SET store_name = ?, gstin = ? WHERE id = ?;", (e_name, e_gstin, int(sel_id)))
                    else:
                        if e_pass:
                            c.execute("UPDATE hierarchy_users SET name = ?, password_hash = ? WHERE id = ?;", (e_name, hash_password(e_pass), int(sel_id)))
                        else:
                            c.execute("UPDATE hierarchy_users SET name = ? WHERE id = ?;", (e_name, int(sel_id)))
                    conn.commit()
                    st.success("Member updated successfully!")
                    st.rerun()
                elif del_btn:
                    if m_role == "RETAILER":
                        sub_stat = selected_member.get('subscription_status', 'ACTIVE')
                        pay_stat = selected_member.get('payment_status', 'ACTIVE')
                        if sub_stat == 'TRIAL' or pay_stat == 'EXPIRED':
                            c.execute("DELETE FROM retailers WHERE id = ?;", (int(sel_id),))
                            conn.commit()
                            st.success("Retailer deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Cannot delete! Retailer is currently in active paid subscription period.")
                    else:
                        c.execute("DELETE FROM hierarchy_users WHERE id = ?;", (int(sel_id),))
                        conn.commit()
                        st.success("Node deleted successfully!")
                        st.rerun()
        else:
            st.info("No downline members found under your account.")

    with tab4:
        st.subheader("Transfer Retailer to Another SSE")
        rets_mgr = pd.read_sql_query("SELECT id, store_name FROM retailers;", conn)
        sses_mgr = pd.read_sql_query("SELECT id, name FROM hierarchy_users WHERE role = 'SSE';", conn)
        
        if not rets_mgr.empty and not sses_mgr.empty:
            with st.form("transfer_ret_mgr"):
                r_sel = st.selectbox("Select Retailer", rets_mgr['id'], format_func=lambda x: rets_mgr[rets_mgr['id']==x]['store_name'].values[0])
                s_sel = st.selectbox("Select Target SSE", sses_mgr['id'], format_func=lambda x: sses_mgr[sses_mgr['id']==x]['name'].values[0])
                if st.form_submit_button("Transfer Retailer"):
                    c = conn.cursor()
                    c.execute("UPDATE retailers SET assigned_sse_id = ? WHERE id = ?;", (int(s_sel), int(r_sel)))
                    conn.commit()
                    st.success("Retailer transferred successfully!")
                    st.rerun()
        else:
            st.warning("No retailers or SSEs available for transfer.")
    conn.close()

elif st.session_state.role == "RETAILER":
    conn = get_db_connection()
    r_info = pd.read_sql_query("SELECT store_name, store_type, gstin FROM retailers WHERE id = ?;", conn, params=(st.session_state.user_id,))
    r_store = r_info.iloc[0]["store_name"] if not r_info.empty else "Medical Store"
    r_type = r_info.iloc[0]["store_type"] if not r_info.empty else "SINGLE"
    r_gstin = r_info.iloc[0]["gstin"] if not r_info.empty else "Unregistered"
    conn.close()
    
    st.subheader(f"🏥 {r_store} - Retailer ERP (GSTIN: {r_gstin})")
    tab_bill, tab_inv, tab_supp, tab_term = st.tabs(["🛒 POS Billing & GST", "📊 Inventory & GST", "📦 Supplier Ledger & PO", "💻 Counter Terminals"])
    
    conn = get_db_connection()
    c = conn.cursor()
    with tab_bill:
        st.subheader("POS Billing with GST Invoice & Thermal Print / WhatsApp Support")
        
        scan_barcode = st.text_input("🔍 Optional Barcode Scan / Enter Barcode", "", placeholder="Scan barcode or leave blank to select manually...")
        
        df_active = pd.read_sql_query("SELECT name, batch, quantity, price, barcode, gst_rate FROM inventory WHERE retailer_id = ? AND quantity > 0;", conn, params=(st.session_state.user_id,))
        
        if not df_active.empty:
            matched_row = None
            if scan_barcode.strip():
                match_df = df_active[df_active['barcode'] == scan_barcode.strip()]
                if not match_df.empty:
                    matched_row = match_df.iloc[0]
                    st.success(f"Scanned Item Matched: {matched_row['name']} (Batch: {matched_row['batch']})")
                else:
                    st.warning("No medicine found with this barcode. Please select manually below.")
            
            if matched_row is not None:
                sel_item = matched_row['name']
                med_row = matched_row
            else:
                sel_item = st.selectbox("Select Medicine Manually", df_active['name'].unique())
                med_row = df_active[df_active['name'] == sel_item].iloc[0]
                
            qty = st.number_input("Quantity", min_value=1, max_value=int(med_row['quantity']), value=1)
            
            if st.button("Add to Cart"):
                item_price = float(med_row['price'])
                gst_pct = float(med_row['gst_rate'])
                line_total = item_price * qty
                
                st.session_state.cart.append({
                    "name": sel_item, 
                    "batch": med_row['batch'], 
                    "price": item_price, 
                    "qty": qty, 
                    "gst_rate": gst_pct,
                    "total": line_total
                })
                st.success("Added to cart with GST calculation!")
                st.rerun()
                
            if st.session_state.cart:
                st.markdown("### Current GST Bill Cart")
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df, use_container_width=True)
                
                subtotal = sum(i['total'] for i in st.session_state.cart)
                total_gst_amount = sum((i['total'] * i['gst_rate'] / 100.0) for i in st.session_state.cart)
                cgst_amt = total_gst_amount / 2.0
                sgst_amt = total_gst_amount / 2.0
                grand_total = subtotal + total_gst_amount
                
                st.markdown(f"**Taxable Amount:** ₹{subtotal:.2f}")
                st.markdown(f"**CGST / SGST:** ₹{cgst_amt:.2f} each | **Grand Total:** **₹{grand_total:.2f}**")
                
                if st.button("Complete Sale & Generate Invoice"):
                    inv_no = f"GST-INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    c.execute("INSERT INTO sales (retailer_id, invoice_number, total_amount, cgst, sgst) VALUES (?, ?, ?, ?, ?);", (st.session_state.user_id, inv_no, grand_total, cgst_amt, sgst_amt))
                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE retailer_id = ? AND batch = ?;", (item['qty'], st.session_state.user_id, item['batch']))
                    conn.commit()
                    
                    st.success(f"GST Tax Invoice {inv_no} Generated Successfully!")
                    st.info(f"🧾 Ready for Thermal Printer Hard Copy & WhatsApp Digital Share.")
                    
                    st.session_state.cart = []
                    st.rerun()
        else:
            st.info("No active stock available in inventory for billing.")

    with tab_inv:
        st.subheader("Inventory Stock & GST Management")
        
        with st.form("add_inv_form"):
            st.markdown("### Add New Stock with GST Rate")
            i_name = st.text_input("Medicine Name")
            i_batch = st.text_input("Batch Number")
            i_qty = st.number_input("Quantity", min_value=1, value=10)
            i_price = st.number_input("Price per Unit (₹)", min_value=0.0, value=10.0)
            i_gst = st.selectbox("GST Rate (%)", [0.0, 5.0, 12.0, 18.0, 28.0], index=2)
            i_barcode = st.text_input("Optional Barcode", placeholder="e.g. 890123456789")
            
            if st.form_submit_button("Add Stock with GST"):
                c.execute("INSERT INTO inventory (retailer_id, name, batch, quantity, price, barcode, gst_rate) VALUES (?, ?, ?, ?, ?, ?, ?);", (st.session_state.user_id, i_name, i_batch, i_qty, i_price, i_barcode, i_gst))
                conn.commit()
                st.success("Stock added with GST configuration successfully!")
                st.rerun()
                
        inv_df = pd.read_sql_query("SELECT name, batch, quantity, price, gst_rate, barcode FROM inventory WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
        st.markdown("### Current Inventory List")
        st.dataframe(inv_df, use_container_width=True)

    with tab_supp:
        st.subheader("📦 Supplier Ledger & Purchase Order Automation")
        
        supp_tab1, supp_tab2, supp_tab3 = st.tabs(["📋 Suppliers Directory", "➕ Add Supplier / Khata", "🛒 Generate Purchase Order (PO)"])
        
        with supp_tab1:
            supp_df = pd.read_sql_query("SELECT id, supplier_name, contact_person, phone, gstin, outstanding_balance FROM suppliers WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            if not supp_df.empty:
                st.dataframe(supp_df, use_container_width=True)
            else:
                st.info("No suppliers added yet.")
                
            st.markdown("### Recent Purchase Orders")
            po_df = pd.read_sql_query("SELECT po_number, items_summary, total_amount, status, created_at FROM purchase_orders WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            if not po_df.empty:
                st.dataframe(po_df, use_container_width=True)
            else:
                st.info("No purchase orders generated yet.")
                
        with supp_tab2:
            with st.form("add_supplier_form"):
                st.markdown("### Add New Distributor / Supplier")
                s_name = st.text_input("Supplier / Agency Name")
                s_contact = st.text_input("Contact Person Name")
                s_phone = st.text_input("Phone Number")
                s_gstin = st.text_input("Supplier GSTIN", value="27SUPPLIER0001Z5")
                s_bal = st.number_input("Initial Outstanding Balance (₹)", min_value=0.0, value=0.0)
                
                if st.form_submit_button("Save Supplier"):
                    c.execute("INSERT INTO suppliers (retailer_id, supplier_name, contact_person, phone, gstin, outstanding_balance) VALUES (?, ?, ?, ?, ?, ?);", (st.session_state.user_id, s_name, s_contact, s_phone, s_gstin, s_bal))
                    conn.commit()
                    st.success("Supplier added successfully to Ledger!")
                    st.rerun()
                    
        with supp_tab3:
            supp_list = pd.read_sql_query("SELECT id, supplier_name FROM suppliers WHERE retailer_id = ?;", conn, params=(st.session_state.user_id,))
            if not supp_list.empty:
                with st.form("po_form"):
                    st.markdown("### Create Automated Purchase Order")
                    po_supp = st.selectbox("Select Supplier", supp_list['id'], format_func=lambda x: supp_list[supp_list['id']==x]['supplier_name'].values[0])
                    po_items = st.text_area("Items Required (e.g. Paracetamol 500tabs, Pantoprazole 200tabs)")
                    po_amt = st.number_input("Estimated PO Amount (₹)", min_value=0.0, value=1000.0)
                    
                    if st.form_submit_button("Generate Purchase Order"):
                        po_no = f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        c.execute("INSERT INTO purchase_orders (retailer_id, supplier_id, po_number, items_summary, total_amount, status) VALUES (?, ?, ?, ?, ?, 'PENDING');", (st.session_state.user_id, int(po_supp), po_no, po_items, po_amt))
                        conn.commit()
                        st.success(f"Purchase Order {po_no} Generated Successfully for Supplier!")
                        st.rerun()
            else:
                st.warning("Please add at least one supplier first to generate a Purchase Order.")

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
