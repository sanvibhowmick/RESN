import os
import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables for agents to access
load_dotenv()

def get_db_connection():
    """Establishes connection to the PostgreSQL DB."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "resn_school"),
            user=os.getenv("DB_USER", "admin"),
            password=os.getenv("DB_PASS", "password"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        return None

def run_query(query, params=None, is_write=False, return_dict=True):
    """
    Executes SQL queries optimized for AI Agents.
    - is_write=True: For INSERT/UPDATE. Returns the ID or True.
    - return_dict=True: Returns a list of dictionaries (LLM-friendly).
    - return_dict=False: Returns a Pandas DataFrame (Dashboard-friendly).
    """
    conn = get_db_connection()
    if not conn:
        
        if is_write: return None
        return [] if return_dict else pd.DataFrame()

    try:
        if is_write:
            # WRITE Operation (e.g., saving a new intervention)
            cur = conn.cursor()
            cur.execute(query, params)
            result = True
            if "RETURNING" in query.upper():
                result = cur.fetchone()[0]
            conn.commit()
            cur.close()
            return result
        else:
            # READ Operation (e.g., fetching student history for an agent)
            if return_dict:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(query, params)
                result = cur.fetchall()
                cur.close()
                return [dict(row) for row in result]
            else:
                return pd.read_sql(query, conn, params=params)
    except Exception as e:
        print(f"❌ Query Failed: {e}")
        if is_write:
            return False
        # FIX: Returns correct type on error to avoid 'list has no attribute empty'
        return [] if return_dict else pd.DataFrame()
    finally:
        if conn:
            conn.close()

def init_db():
    """Initializes tables. Run this when you update schema.sql with pgvector support."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        # Check for schema.sql in the standard project path
        schema_path = os.path.join('init_db', 'schema.sql')
        if not os.path.exists(schema_path):
             schema_path = 'schema.sql'
             
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        cur = conn.cursor()
        cur.execute(schema_sql)
        conn.commit()
        print("✅ Database tables and pgvector initialized!")
        cur.close()
    except Exception as e:
        print(f"❌ Error initializing DB: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()