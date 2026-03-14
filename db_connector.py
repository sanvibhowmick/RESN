import os
import streamlit as st
import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

# Load local environment variables for local development
load_dotenv()

# --- ROBUST SECRET RETRIEVAL ---
def get_db_secret(key, default_val):
    """
    Checks Streamlit secrets first (for Cloud), then environment variables (for Local).
    """
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key, default_val)

# --- CONNECTION POOL INITIALIZATION ---
try:
    db_host = get_db_secret("DB_HOST", "localhost")
    # Neon requires 'require' for remote connections; local dev usually 'disable'
    is_localhost = db_host in ["localhost", "127.0.0.1", "0.0.0.0"]
    ssl_mode = "disable" if is_localhost else "require"

    db_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=db_host,
        database=get_db_secret("DB_NAME", "resn_school"),
        user=get_db_secret("DB_USER", "admin"),
        password=get_db_secret("DB_PASS", "password"),
        port=get_db_secret("DB_PORT", "5432"),
        sslmode=ssl_mode
    )
    print(f"✅ Connection pool initialized (Host: {db_host}, SSL: {ssl_mode})")
except Exception as e:
    # On Streamlit Cloud, it's better to show the error so you can debug
    st.error(f"❌ Database Pool Error: {e}")
    db_pool = None

def run_query(query, params=None, is_write=False, return_dict=True):
    """
    Executes SQL queries using the connection pool.
    """
    if not db_pool:
        if is_write: return False
        return [] if return_dict else pd.DataFrame()

    conn = None
    try:
        conn = db_pool.getconn()
        
        if is_write:
            cur = conn.cursor()
            cur.execute(query, params)
            result = True
            if "RETURNING" in query.upper():
                row = cur.fetchone()
                if row:
                    result = row[0]
            conn.commit()
            cur.close()
            return result
        else:
            if return_dict:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(query, params)
                result = cur.fetchall()
                cur.close()
                return [dict(row) for row in result]
            else:
                return pd.read_sql(query, conn, params=params)

    except Exception as e:
        if conn:
            conn.rollback()
        # Printing to Streamlit to catch silent errors in the Cloud
        st.error(f"❌ Query Failed: {str(e)}")
        if is_write: return False
        return [] if return_dict else pd.DataFrame() 
    finally:
        if conn:
            db_pool.putconn(conn)

def init_db():
    """Initializes tables using a single pooled connection."""
    try:
        schema_path = os.path.join('init_db', 'schema.sql')
        if not os.path.exists(schema_path):
             schema_path = 'schema.sql'
             
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute(schema_sql)
        conn.commit()
        cur.close()
        db_pool.putconn(conn)
        print("✅ Database tables and pgvector initialized!")
    except Exception as e:
        print(f"❌ Error initializing DB: {e}")

if __name__ == "__main__":
    init_db()