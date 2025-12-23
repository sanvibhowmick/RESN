import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Establishes connection to the PostgreSQL DB"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "school_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS", "password"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        return None

def run_query(query, params=None, is_write=False):
    """
    Executes SQL queries.
    - is_write=False (Default): Returns DataFrame (for SELECT).
    - is_write=True: Executes INSERT/UPDATE and returns the ID (if RETURNING used) or True.
    """
    conn = get_db_connection()
    if not conn:
        return None if is_write else pd.DataFrame()

    try:
        if is_write:
            # WRITE Operation
            cur = conn.cursor()
            cur.execute(query, params)
            
            # --- THE FIX STARTS HERE ---
            # If the query includes 'RETURNING', fetch that value (e.g., student_id)
            if "RETURNING" in query.upper():
                result = cur.fetchone()[0] # Returns the ID (int)
            else:
                result = True # Returns Success (bool)
            # --- THE FIX ENDS HERE ---

            conn.commit()
            cur.close()
            conn.close()
            return result
            
        else:
            # READ Operation
            df = pd.read_sql(query, conn, params=params)
            conn.close()
            return df
            
    except Exception as e:
        print(f"❌ Query Failed: {e}")
        if conn: conn.close()
        return False if is_write else pd.DataFrame()

def init_db():
    """Reads schema.sql and creates tables if they don't exist"""
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to DB to initialize tables.")
        return

    try:
        with open('schema.sql', 'r') as f:
            schema_sql = f.read()
        
        cur = conn.cursor()
        cur.execute(schema_sql)
        conn.commit()
        print("✅ Database tables initialized successfully!")
        cur.close()
        conn.close()
    except FileNotFoundError:
        print("❌ Error: schema.sql file not found.")
    except Exception as e:
        print(f"❌ Error initializing DB: {e}")

if __name__ == "__main__":
    init_db()