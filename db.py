import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

def get_engine():
    # Fallback support for both flat and nested secret formats
    try:
        if "postgres" in st.secrets and "url" in st.secrets["postgres"]:
            db_url = st.secrets["postgres"]["url"]
        elif "url" in st.secrets:
            db_url = st.secrets["url"]
        else:
            # Direct fallback string if secrets aren't picked up
            db_url = "postgresql://neondb_owner:npg_a6hbH8qqLtIX@ep-quiet-wind-az98j8pn-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
    except Exception:
        db_url = "postgresql://neondb_owner:npg_a6hbH8qqLtIX@ep-quiet-wind-az98j8pn-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300
    )

def init_db():
    engine = get_engine()
    with engine.connect() as conn:
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
        conn.commit()

def run_query(query: str, params: dict = None):
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        conn.commit()
        return None
