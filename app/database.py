import sqlite3
import os
from app.config import settings

def get_db_connection() -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    Enforces read-only mode by using SQLite URI mode=ro.
    """
    db_path = os.path.abspath(settings.DB_PATH)
    # Ensure the DB file exists before connecting
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at: {db_path}")
    
    # Open SQLite connection in read-only mode using URI
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
