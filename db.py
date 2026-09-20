import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

def get_engine():
    db_url = st.secrets["postgres"]["url"]
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10
    )

def init_db():
    engine = get_engine()
    with engine.connect() as conn:
        # Stores table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stores (
                id SERIAL PRIMARY KEY,
                store_name VARCHAR(255) NOT NULL,
                owner_name VARCHAR(255),
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                distributor_code VARCHAR(50),
                subscription_status VARCHAR(50) DEFAULT 'TRIAL',
                plan_expiry_date TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 days'),
                activation_key VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Users table (RBAC)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                store_id INT REFERENCES stores(id) ON DELETE CASCADE,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Inventory table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                store_id INT REFERENCES stores(id) ON DELETE CASCADE,
                medicine_name VARCHAR(255) NOT NULL,
                batch_number VARCHAR(100) NOT NULL,
                expiry_date DATE NOT NULL,
                quantity INT NOT NULL DEFAULT 0,
                mrp NUMERIC(10, 2) NOT NULL,
                rate NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Sales table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                store_id INT REFERENCES stores(id) ON DELETE CASCADE,
                invoice_number VARCHAR(100) NOT NULL,
                customer_name VARCHAR(255),
                customer_phone VARCHAR(50),
                total_amount NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Payment logs table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS payment_logs (
                id SERIAL PRIMARY KEY,
                store_id INT REFERENCES stores(id) ON DELETE CASCADE,
                amount NUMERIC(10, 2) NOT NULL,
                payment_status VARCHAR(50) DEFAULT 'PENDING',
                transaction_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()

# Helper function
def run_query(query: str, params: dict = None):
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        conn.commit()
        return None