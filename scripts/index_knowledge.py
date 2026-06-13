"""
One-time script: indexes schema descriptions, few-shot examples,
and domain glossary into Pinecone for RAG retrieval.

Usage:
    python -m scripts.index_knowledge
"""
import os
import sys
import sqlite3
from langchain_core.documents import Document

# Add project root to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.vectorstore.pinecone_client import vectorstore

def build_schema_documents(db_path: str) -> list[Document]:
    """One document per table — rich description with columns, types, FKs, samples."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    docs = []
    for table_row in tables:
        table_name = table_row[0]
        # Skip sqlite internal tables
        if table_name.startswith("sqlite_"):
            continue
            
        columns = cursor.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        fks = cursor.execute(f"PRAGMA foreign_key_list('{table_name}')").fetchall()
        count = cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'").fetchone()[0]
        samples = cursor.execute(f"SELECT * FROM '{table_name}' LIMIT 3").fetchall()

        col_lines = [
            f"  - {c['name']} ({c['type']}, {'PK' if c['pk'] else 'nullable' if not c['notnull'] else 'NOT NULL'})"
            for c in columns
        ]
        fk_lines = [f"  FK: {fk['from']} → {fk['table']}.{fk['to']}" for fk in fks]

        sample_str = ""
        if samples:
            headers = [desc[0] for desc in cursor.description]
            for row in samples:
                sample_str += f"  {dict(row)}\n"

        content = (
            f"TABLE: {table_name} ({count} rows)\n"
            f"Columns:\n" + "\n".join(col_lines) + "\n"
            + (f"Foreign Keys:\n" + "\n".join(fk_lines) + "\n" if fk_lines else "")
            + (f"Sample rows:\n{sample_str}" if sample_str else "")
        )

        docs.append(Document(
            page_content=content,
            metadata={
                "doc_type": "schema",
                "table_name": table_name,
                "row_count": count,
            },
        ))

    conn.close()
    return docs

def build_few_shot_documents() -> list[Document]:
    """NL→SQL examples. The more you add, the better retrieval accuracy."""
    examples = [
        # --- Users ---
        {"nl": "How many users signed up last month?",
         "sql": "SELECT COUNT(*) AS new_users FROM users WHERE created_at >= date('now', '-1 month')",
         "tables": "users"},
        {"nl": "Show all active users",
         "sql": "SELECT * FROM users WHERE account_status = 'active' LIMIT 100",
         "tables": "users"},
        {"nl": "How many users are verified vs unverified?",
         "sql": "SELECT is_verified, COUNT(*) AS count FROM users GROUP BY is_verified",
         "tables": "users"},

        # --- Profiles ---
        {"nl": "Profiles missing a bio",
         "sql": "SELECT u.user_id, u.full_name FROM users u JOIN profiles p ON u.user_id = p.user_id WHERE p.bio IS NULL OR p.bio = ''",
         "tables": "users,profiles"},
        {"nl": "Average profile completeness percentage",
         "sql": "SELECT AVG(profile_completeness_pct) AS avg_completeness FROM profiles",
         "tables": "profiles"},

        # --- Matches ---
        {"nl": "How many matches happened this week?",
         "sql": "SELECT COUNT(*) AS weekly_matches FROM matches WHERE matched_at >= date('now', '-7 days')",
         "tables": "matches"},
        {"nl": "sabse zyada match kisko mila?",
         "sql": "SELECT user_id, COUNT(*) AS match_count FROM (SELECT user_a_id AS user_id FROM matches UNION ALL SELECT user_b_id FROM matches) GROUP BY user_id ORDER BY match_count DESC LIMIT 10",
         "tables": "matches"},

        # --- Messages ---
        {"nl": "Average messages per match",
         "sql": "SELECT ROUND(AVG(msg_count), 1) AS avg_messages FROM (SELECT match_id, COUNT(*) AS msg_count FROM messages GROUP BY match_id)",
         "tables": "messages"},

        # --- Payments & Plans ---
        {"nl": "Total revenue this quarter",
         "sql": "SELECT SUM(amount_inr) AS total_revenue FROM payments WHERE status = 'success' AND created_at >= date('now', 'start of month', '-2 months')",
         "tables": "payments"},
        {"nl": "kitne logon ne premium liya?",
         "sql": "SELECT COUNT(DISTINCT s.user_id) AS premium_users FROM subscriptions s JOIN plans p ON s.plan_id = p.plan_id WHERE LOWER(p.plan_name) LIKE '%premium%' OR LOWER(p.plan_name) LIKE '%gold%' OR LOWER(p.plan_name) LIKE '%platinum%'",
         "tables": "subscriptions,plans"},
        {"nl": "Which plan has the most subscribers?",
         "sql": "SELECT p.plan_name, COUNT(*) AS subscriber_count FROM subscriptions s JOIN plans p ON s.plan_id = p.plan_id GROUP BY p.plan_id ORDER BY subscriber_count DESC LIMIT 1",
         "tables": "subscriptions,plans"},

        # --- Profile Views ---
        {"nl": "Top 10 most viewed profiles",
         "sql": "SELECT pv.viewed_id, u.full_name, COUNT(*) AS views FROM profile_views pv JOIN users u ON pv.viewed_id = u.user_id GROUP BY pv.viewed_id ORDER BY views DESC LIMIT 10",
         "tables": "profile_views,users"},

        # --- Subscriptions ---
        {"nl": "Active vs expired subscriptions",
         "sql": "SELECT status, COUNT(*) AS count FROM subscriptions GROUP BY status",
         "tables": "subscriptions"},

        # --- Reports ---
        {"nl": "Most reported users",
         "sql": "SELECT reported_id, COUNT(*) AS report_count FROM reports GROUP BY reported_id ORDER BY report_count DESC LIMIT 10",
         "tables": "reports"},

        # --- Support Tickets ---
        {"nl": "Open support tickets by category",
         "sql": "SELECT category, COUNT(*) AS open_count FROM support_tickets WHERE status = 'open' GROUP BY category ORDER BY open_count DESC",
         "tables": "support_tickets"},

        # --- Interests ---
        {"nl": "Top 10 most common interests",
         "sql": "SELECT receiver_id, COUNT(*) AS count FROM interests GROUP BY receiver_id ORDER BY count DESC LIMIT 10",
         "tables": "interests"},

        # --- Cross-table ---
        {"nl": "Premium users who never sent a message",
         "sql": "SELECT u.user_id, u.full_name FROM users u JOIN subscriptions s ON u.user_id = s.user_id JOIN plans p ON s.plan_id = p.plan_id LEFT JOIN matches m ON (u.user_id = m.user_a_id OR u.user_id = m.user_b_id) LEFT JOIN messages msg ON m.match_id = msg.match_id AND msg.sender_id = u.user_id WHERE (LOWER(p.plan_name) LIKE '%premium%' OR LOWER(p.plan_name) LIKE '%gold%') AND msg.message_id IS NULL AND s.status = 'active'",
         "tables": "users,subscriptions,plans,matches,messages"},

        # --- Partner Preferences ---
        {"nl": "Users whose age preference range is narrower than 5 years",
         "sql": "SELECT user_id, min_age, max_age FROM partner_preferences WHERE (max_age - min_age) < 5",
         "tables": "partner_preferences"},
    ]

    docs = []
    for ex in examples:
        content = (
            f"Question: {ex['nl']}\n"
            f"SQL: {ex['sql']}\n"
            f"Tables used: {ex['tables']}"
        )
        # Check if the query has Hinglish keywords
        hinglish_words = ["kitne", "sabse", "zyada", "logon", "kisko", "mila", "liya"]
        is_hinglish = any(w in ex["nl"].lower() for w in hinglish_words)
        docs.append(Document(
            page_content=content,
            metadata={
                "doc_type": "few_shot",
                "tables": ex["tables"],
                "language": "hinglish" if is_hinglish else "english",
            },
        ))

    return docs

def build_glossary_documents() -> list[Document]:
    """Domain terms that the LLM might misinterpret."""
    glossary = [
        {"term": "match", "definition": "A mutual connection between two users who have both expressed interest in each other. Stored in the matches table with match_id, user_a_id, user_b_id, matched_at."},
        {"term": "silver / gold / platinum / premium / subscription plans", "definition": "The only paid subscription plans available on the platform are 'Silver', 'Gold', and 'Platinum' (stored in the plans table). There is NO 'Basic' or 'Standard' plan. Users subscribe via the subscriptions table and pay via the payments table."},
        {"term": "profile view", "definition": "When one user views another user's profile. Tracked in profile_views with viewer_id and viewed_id."},
        {"term": "report", "definition": "A user filing a complaint against another user. Stored in reports with reporter_id and reported_id, and status (open/actioned/dismissed)."},
        {"term": "interest", "definition": "Expressing desire to connect. Stored in interests with sender_id and receiver_id, and status (pending/accepted/declined)."},
        {"term": "partner preference", "definition": "Criteria a user sets for their ideal match — age range, location, religion, sect, etc. Stored in partner_preferences."},
        {"term": "active user", "definition": "A user with account_status = 'active' in the users table. Alternatively, users whose last_active_at is recent."},
        {"term": "revenue / paisa / payment", "definition": "Money collected from users. Stored in the payments table with amount_inr, method, status ('success'), and created_at fields."},
        {"term": "csat score", "definition": "Customer satisfaction rating on support tickets, stored in csat_score field of support_tickets table ranging from 1 to 5."},
    ]

    return [
        Document(
            page_content=f"Term: {g['term']}\nDefinition: {g['definition']}",
            metadata={"doc_type": "glossary", "term": g["term"]},
        )
        for g in glossary
    ]

def main():
    print("Building schema documents...")
    schema_docs = build_schema_documents(settings.DB_PATH)
    print(f"  -> {len(schema_docs)} table descriptions")

    print("Building few-shot documents...")
    few_shot_docs = build_few_shot_documents()
    print(f"  -> {len(few_shot_docs)} NL->SQL examples")

    print("Building glossary documents...")
    glossary_docs = build_glossary_documents()
    print(f"  -> {len(glossary_docs)} glossary terms")

    all_docs = schema_docs + few_shot_docs + glossary_docs
    print(f"\nIndexing {len(all_docs)} documents into Pinecone...")
    print(f"  Index: {settings.PINECONE_INDEX_NAME}")
    print(f"  Namespace: {settings.PINECONE_NAMESPACE}")

    # Upsert to Pinecone
    vectorstore.add_documents(all_docs, namespace=settings.PINECONE_NAMESPACE)
    print("Indexing completed successfully!")

if __name__ == "__main__":
    main()
