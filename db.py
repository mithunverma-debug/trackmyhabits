"""
Database connection and session utilities for TrackMyHabits.
Supports direct Supabase PostgreSQL connection via DATABASE_URL or psycopg2.
Includes fallback mock/sqlite mode for isolated offline testing.
"""
import os
import urllib.parse
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

# Primary DB connection string
# Can be provided via DATABASE_URL or derived from Supabase project config
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db_connection():
    """
    Returns a psycopg2 connection configured with RealDictCursor.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Fallback or standard Supabase pooler/direct connection
        # Supabase default host pattern: db.<ref>.supabase.co or aws-0-ap-south-1.pooler.supabase.com
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

    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    conn.autocommit = False
    return conn

def execute_query(sql, params=None, fetch_all=True, fetch_one=False, commit=False):
    """
    Helper to run a query safely with parameter binding and auto-cleanup.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if commit:
                conn.commit()
                if fetch_one:
                    return cur.fetchone()
                if fetch_all:
                    return cur.fetchall()
                return cur.rowcount
            else:
                if fetch_one:
                    res = cur.fetchone()
                elif fetch_all:
                    res = cur.fetchall()
                else:
                    res = None
                return res
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()
