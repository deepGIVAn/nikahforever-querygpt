import time
import sqlite3
from app.database import get_db_connection

def execute_query(sql: str) -> dict:
    """
    Executes the validated SQL query against the read-only SQLite database.
    
    Returns:
        A dict with query results (columns, rows, row_count, execution_time_ms)
        or an error message.
    """
    start_time = time.perf_counter()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Fetch all rows
        rows = cursor.fetchall()
        
        # Convert rows (sqlite3.Row) to dicts for JSON serialization
        serialized_rows = [dict(row) for row in rows]
        
        end_time = time.perf_counter()
        execution_time_ms = round((end_time - start_time) * 1000, 2)
        
        return {
            "columns": columns,
            "rows": serialized_rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time_ms
        }
        
    except sqlite3.Error as e:
        end_time = time.perf_counter()
        execution_time_ms = round((end_time - start_time) * 1000, 2)
        return {
            "error": f"Database execution error: {str(e)}",
            "execution_time_ms": execution_time_ms
        }
    except Exception as e:
        end_time = time.perf_counter()
        execution_time_ms = round((end_time - start_time) * 1000, 2)
        return {
            "error": f"Unexpected execution error: {str(e)}",
            "execution_time_ms": execution_time_ms
        }
    finally:
        if conn:
            conn.close()
