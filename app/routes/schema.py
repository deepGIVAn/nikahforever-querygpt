from fastapi import APIRouter
from app.database import get_db_connection

router = APIRouter(prefix="/api", tags=["schema"])

@router.get("/schema")
async def get_schema():
    """
    Returns database schema information including table names, column names,
    column types, and primary key indicators.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        
        schema_info = {}
        for row in tables:
            table_name = row[0]
            if table_name.startswith("sqlite_"):
                continue
                
            columns = cursor.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            schema_info[table_name] = [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "pk": bool(col["pk"]),
                    "notnull": bool(col["notnull"])
                }
                for col in columns
            ]
        return schema_info
    except Exception as e:
        return {"error": f"Failed to retrieve database schema: {str(e)}"}
    finally:
        if conn:
            conn.close()
