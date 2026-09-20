import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

# Neon PostgreSQL Connection Engine
@st.cache_resource
def get_engine():
    db_url = st.secrets["postgres"]["url"]
    return create_engine(db_url, pool_pre_ping=True)

# Helper function: Select queries (Dataframe return karega)
def run_query(query, params=None):
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

# Helper function: Insert / Update / Delete queries
def execute_query(query, params=None):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(query), params or {})