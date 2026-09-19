"""
GreenGuard AI - Database layer (SQLite)

Tables:
  medicines          -> verified "ground truth" medicine records
  certifications      -> valid certifying bodies + license number regex
  reported_fakes      -> crowd-sourced / logged fake listings
  scan_history         -> every scan a user runs (for demo + audit trail)
"""

import sqlite3
import os
from contextlib import contextmanager
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist yet. Safe to call on every startup."""
    with db_session() as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            manufacturer TEXT NOT NULL,
            category TEXT,                    -- e.g. Ayurvedic, Herbal, Organic
            batch_format_regex TEXT,          -- expected batch number pattern
            license_number TEXT,              -- e.g. AYUSH license code
            certifying_body TEXT,             -- AYUSH / FSSAI / ISO etc.
            verified_logo_hash TEXT,          -- perceptual hash of real logo
            description TEXT,                 -- used for RAG context
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body_name TEXT NOT NULL UNIQUE,      -- e.g. AYUSH, FSSAI, ISO 9001
            license_regex TEXT NOT NULL,         -- regex to validate format
            official_lookup_url TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS reported_fakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            seller_info TEXT,
            reason TEXT,
            reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            extracted_text TEXT,
            matched_medicine_id INTEGER,
            trust_score INTEGER,
            verdict TEXT,
            mode_used TEXT,                   -- 'online' or 'offline'
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (matched_medicine_id) REFERENCES medicines (id)
        )
        """)

        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
