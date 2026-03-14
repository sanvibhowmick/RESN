import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

# Load environment variables for local development
load_dotenv()

# Safely import Streamlit to prevent local script crashes if Streamlit isn't used
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

# --- CLOUD & LOCAL CREDENTIAL HANDLER ---
def get_credential(key, default_val=None):
    """
    Safely fetches credentials. 
    Prioritizes Streamlit Secrets (Cloud), then falls back to os.getenv (Local).
    """
    if HAS_STREAMLIT:
        try:
            # Check if we are running inside a Streamlit app and the secret exists
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            # Fallback if st.secrets is inaccessible (e.g., running python locally)
            pass 
            
    return os.getenv(key, default_val)

# --- INITIALIZE CONNECTION POOL ---
db_pool = None
try:
    db_host = get_credential("DB_HOST", "localhost")
    db_name = get_credential("DB_NAME", "neondb")
    db_user = get_credential("DB_USER", "neondb_owner")
    db_pass = get_credential("DB_PASS", "password")
    db_port = get_credential("DB_PORT", "5432")

    # Neon requires SSL for remote connections. Localhost does not.
    ssl_mode = "disable" if db_host in ["localhost", "127.0.0.1", "0.0.0.0"] else "require"

    db_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_pass,
        port=db_port,
        sslmode=ssl_mode
    )
    print(f"✅ Connection pool initialized (Host: {db_host[:15]}..., DB: {db_name}, SSL: {ssl_mode})")
except Exception as e:
    error_msg = f"❌ Connection Pool Failed: {e}"
    print(error_msg)
    if HAS_STREAMLIT:
        try:
            st.error(error_msg)
        except Exception:
            pass

# --- QUERY EXECUTION ---
def run_query(query, params=None, is_write=False, return_dict=True):
    """
    Executes SQL queries safely using the connection pool.
    """
    if not db_pool:
        error_msg = "Database connection pool is not initialized. Check your credentials."
        print(error_msg)
        if HAS_STREAMLIT:
            try:
                st.error(error_msg)
            except Exception:
                pass
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
        error_msg = f"❌ Query Failed: {str(e)}"
        print(error_msg)
        if HAS_STREAMLIT:
            try:
                st.error(error_msg) # Shows the exact DB error in the cloud UI
            except Exception:
                pass
        if is_write: return False
        return [] if return_dict else pd.DataFrame() 
    finally:
        if conn:
            db_pool.putconn(conn)

# --- DATABASE INITIALIZATION ---
def init_db():
    """Initializes tables using a single pooled connection."""
    if not db_pool:
        print("❌ Cannot initialize DB: No connection pool.")
        return

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
        print("✅ Database tables initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing DB: {e}")

if __name__ == "__main__":
    init_db()