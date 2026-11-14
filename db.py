"""
Database connection and query execution utilities for TrackMyHabits.
Fully compatible with Supabase PostgreSQL (Direct & Transaction Pooler port 6543)
and serverless execution environments like Vercel.
"""
import os
import urllib.parse
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db_connection():
    """
    Returns a psycopg2 connection configured with RealDictCursor.
    Handles connection timeouts and clean disconnection for serverless functions.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_user = os.environ.get("DB_USER", "postgres")
        db_pass = os.environ.get("DB_PASSWORD", "")
        db_host = os.environ.get("DB_HOST", "db.qyexezkaasrvprbakhtw.supabase.co")
        db_port = os.environ.get("DB_PORT", "5432")
        db_name = os.environ.get("DB_NAME", "postgres")
        
        if db_pass:
            encoded_pass = urllib.parse.quote_plus(db_pass)
            db_url = f"postgresql://{db_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
        else:
            db_url = ""

    if not db_url:
        raise ValueError("DATABASE_URL or DB_PASSWORD environment variable is required to connect to Supabase.")

    # Connect with 10-second timeout, autocommit=False for transaction safety
    conn = psycopg2.connect(
        db_url,
        cursor_factory=RealDictCursor,
        connect_timeout=10
    )
    return conn

def execute_query(sql, params=None, fetch_all=False, fetch_one=False, commit=False):
    """
    Safely executes an SQL query and returns results appropriately:
    - If fetch_one is True: fetches a single row only if cursor.description is present (has results)
    - If fetch_all is True: fetches all rows only if cursor.description is present
    - If neither fetch flag is set (e.g. UPDATE, DELETE, or INSERT without returning): returns rowcount
    - Avoids 'ProgrammingError: no results to fetch' when executing non-SELECT/DML queries.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            
            # Check if this query returned a result set (e.g. SELECT, or INSERT/UPDATE with RETURNING)
            has_results = cur.description is not None
            
            if has_results:
                if fetch_one:
                    res = cur.fetchone()
                elif fetch_all:
                    res = cur.fetchall()
                else:
                    res = cur.fetchall()
            else:
                res = cur.rowcount

            if commit:
                conn.commit()

            return res
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()
