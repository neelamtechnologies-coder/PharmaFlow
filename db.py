import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import pandas as pd
import hashlib

def get_engine():
    try:
        if "postgres" in st.secrets and "url" in st.secrets["postgres"]:
            db_url = st.secrets["postgres"]["url"]
        else:
            db_url = st.secrets["url"]
    except Exception:
        db_url = "postgresql://neondb_owner:npg_a6hbH8qqLtIX@ep-quiet-wind-az98j8pn.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

    return create_engine(
        db_url,
        connect_args={"sslmode": "require", "connect_timeout": 5},
        poolclass=NullPool
    )

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Drop old tables to apply clean multi-tier schema
            conn.execute(text("DROP TABLE IF EXISTS sales CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS inventory CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS retailers CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS wholesalers CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS system_config CASCADE;"))

            # 1. System Config (Super Admin - Neelam Technologies)
            conn.execute(text("""
                CREATE TABLE system_config (
                    id SERIAL PRIMARY KEY,
                    company_name VARCHAR(255) DEFAULT 'Neelam Technologies',
                    super_admin_username VARCHAR(100) DEFAULT 'admin',
                    super_admin_password_hash VARCHAR(255) DEFAULT '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',
                    upi_id VARCHAR(100) DEFAULT 'neelamtech@upi',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            conn.execute(text("""
                INSERT INTO system_config (company_name, super_admin_username, super_admin_password_hash, upi_id)
                VALUES ('Neelam Technologies', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'neelamtech@upi');
            """))

            # 2. Wholesalers / Distributors Table (Middle Tier)
            conn.execute(text("""
                CREATE TABLE wholesalers (
                    id SERIAL PRIMARY KEY,
                    company_name VARCHAR(255) NOT NULL,
                    owner_name VARCHAR(255),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    phone VARCHAR(50),
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    upi_id VARCHAR(100),
                    subscription_status VARCHAR(50) DEFAULT 'ACTIVE',
                    plan_expiry_date TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 year'),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # 3. Retailers / Medical Stores Table (Child Tier under Wholesaler)
            conn.execute(text("""
                CREATE TABLE retailers (
                    id SERIAL PRIMARY KEY,
                    wholesaler_id INT REFERENCES wholesalers(id) ON DELETE CASCADE,
                    store_name VARCHAR(255) NOT NULL,
                    owner_name VARCHAR(255),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    phone VARCHAR(50),
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # 4. Inventory Table (Linked to Retailer)
            conn.execute(text("""
                CREATE TABLE inventory (
                    id SERIAL PRIMARY KEY,
                    retailer_id INT REFERENCES retailers(id) ON DELETE CASCADE,
                    medicine_name VARCHAR(255) NOT NULL,
                    batch_number VARCHAR(100) NOT NULL,
                    expiry_date DATE NOT NULL,
                    quantity INT NOT NULL DEFAULT 0,
                    mrp NUMERIC(10, 2) NOT NULL,
                    rate NUMERIC(10, 2) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # 5. Sales Table
            conn.execute(text("""
                CREATE TABLE sales (
                    id SERIAL PRIMARY KEY,
                    retailer_id INT REFERENCES retailers(id) ON DELETE CASCADE,
                    invoice_number VARCHAR(100) NOT NULL,
                    customer_name VARCHAR(255),
                    customer_phone VARCHAR(50),
                    total_amount NUMERIC(10, 2) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
    except Exception as e:
        st.error(f"Database Initialization Failed: {e}")
        st.stop()

def run_query(query: str, params: dict = None):
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        conn.commit()
        return None
