import os
import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONNECTION POOL INITIALIZATION ---
# This creates a pool of 1 to 10 connections that stay open
# and are reused across different app sessions.
try:
    db_host = os.getenv("DB_HOST", "localhost")
    is_localhost = db_host in ["localhost", "127.0.0.1", "0.0.0.0"]
    ssl_mode = "disable" if is_localhost else "require"

    db_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=db_host,
        database=os.getenv("DB_NAME", "resn_school"),
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASS", "password"),
        port=os.getenv("DB_PORT", "5432"),
        sslmode=ssl_mode
    )
    print("✅ Connection pool initialized")
except Exception as e:
    print(f"❌ Failed to initialize connection pool: {e}")
    db_pool = None

def run_query(query, params=None, is_write=False, return_dict=True):
    """
    Executes SQL queries using the connection pool for high performance.
    """
    if not db_pool:
        if is_write: return False
        return [] if return_dict else pd.DataFrame()

    conn = None
    try:
        # Request a warm connection from the pool
        conn = db_pool.getconn()
        
        if is_write:
            # For writes, we use a standard cursor to handle RETURNING clauses
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
                # For reads, use RealDictCursor for AI-friendly dictionary output
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(query, params)
                result = cur.fetchall()
                cur.close()
                return [dict(row) for row in result]
            else:
                # Returns a DataFrame for Streamlit charts
                return pd.read_sql(query, conn, params=params)

    except Exception as e:
        if conn:
            conn.rollback() # Ensure failed transactions are rolled back
        print(f"❌ Query Failed: {str(e)}")
        if is_write: return False
        return [] if return_dict else pd.DataFrame() 
    finally:
        if conn:
            # CRITICAL: Return the connection to the pool instead of closing it
            db_pool.putconn(conn)

def init_db():
    """Initializes tables using a single pooled connection."""
    try:
        schema_path = os.path.join('init_db', 'schema.sql')
        if not os.path.exists(schema_path):
             schema_path = 'schema.sql'
             
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # We can just use our existing run_query for simple execution
        # but for multiple statements in schema.sql, we do it directly:
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