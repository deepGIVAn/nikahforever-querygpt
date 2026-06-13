import re
import sqlparse

BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "ATTACH",
    "DETACH", "PRAGMA", "REINDEX", "VACUUM"
]

# Case-insensitive word boundary matching for blocked words
BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(BLOCKED_KEYWORDS) + r")\b", re.IGNORECASE,
)

def validate_sql(sql: str) -> dict:
    """
    Validates a SQL query for safety.
    Enforces SELECT statements only, bans mutation keywords, restricts to single-statement execution,
    and appends a LIMIT 500 clause if none exists.
    """
    if not sql or not sql.strip():
        return {"valid": False, "error": "Empty query", "sanitised_sql": None}

    # Format and clean SQL
    parsed_sql = sqlparse.format(sql, strip_comments=True).strip()

    # Blocked keyword check
    if BLOCKED_PATTERN.search(parsed_sql):
        matched = BLOCKED_PATTERN.findall(parsed_sql)
        return {"valid": False, "error": f"Blocked keywords detected: {', '.join(set(matched))}", "sanitised_sql": None}

    # Split SQL into distinct statements
    statements = [s for s in sqlparse.split(parsed_sql) if s.strip()]
    if len(statements) > 1:
        return {"valid": False, "error": "Multiple statements not allowed", "sanitised_sql": None}
    
    if not statements:
        return {"valid": False, "error": "No statement parsed", "sanitised_sql": None}

    # Verify first keyword is SELECT or WITH (for CTEs)
    first_statement = statements[0]
    tokens = first_statement.split()
    if not tokens:
        return {"valid": False, "error": "Empty statement parsed", "sanitised_sql": None}
        
    first_kw = tokens[0].upper()
    if first_kw not in ("SELECT", "WITH"):
        return {"valid": False, "error": f"Only SELECT/WITH statements allowed. Got: {first_kw}", "sanitised_sql": None}

    # Ensure LIMIT exists
    upper_sql = first_statement.upper()
    if "LIMIT" not in upper_sql:
        # Strip trailing semicolon if present before appending limit
        cleaned = first_statement.rstrip(";")
        sanitised_sql = f"{cleaned} LIMIT 500;"
    else:
        sanitised_sql = first_statement
        if not sanitised_sql.endswith(";"):
            sanitised_sql += ";"

    return {"valid": True, "error": None, "sanitised_sql": sanitised_sql}
