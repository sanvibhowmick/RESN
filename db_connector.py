

import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv


load_dotenv()


def get_db_connection():
    """Establishes connection to the Docker PostgreSQL DB"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            port=os.getenv("DB_PORT", "5432") # Added port for safety
        )
        return conn
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        return None

def run_query(query, params=None):
    """
    Smart Helper: 
    - Returns DataFrame for SELECT queries.
    - Commits changes for INSERT/UPDATE queries.
    """
    conn = get_db_connection()
    if conn:
        try:
            # Check if this is a WRITE operation (INSERT, UPDATE, DELETE)
            query_clean = query.strip().upper()
            if query_clean.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP")):
                cur = conn.cursor()
                cur.execute(query, params)
                conn.commit()  # <--- CRITICAL: Saves your data!
                cur.close()
                conn.close()
                return pd.DataFrame() # Return empty DF to keep code consistent
            
            else:
                # It is a READ operation (SELECT)
                df = pd.read_sql(query, conn, params=params)
                conn.close()
                return df
                
        except Exception as e:
            print(f"❌ Query Failed: {e}")
            if conn: conn.close()
            return pd.DataFrame()
            
    return pd.DataFrame()
# Add this to the end of db_connector.py

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