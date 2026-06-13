# NF QueryGPT — Updated Architecture (Pinecone RAG + SQLite)

**Stack:** FastAPI · SQLite · Pinecone · LangChain · OpenAI · SSE Streaming

---

## Why Pinecone Here?

Plain schema injection works for 12 tables, but it hits limits fast:

| Problem | Raw Schema Approach | Pinecone RAG Approach |
|---------|--------------------|-----------------------|
| Token bloat | Full schema (12 tables + samples) eats ~3K tokens every call | Retrieve only the 3–5 relevant table descriptions per question |
| Few-shot accuracy | Static examples — can't scale past 10–15 | Store 100+ NL→SQL pairs, retrieve the 3 most similar to each question |
| Hinglish | LLM must figure it out cold | Embed Hinglish examples — retrieval handles the mapping |
| Domain knowledge | None — LLM guesses what "premium" or "match" means | Embed a glossary — "match" = mutual acceptance, "premium" = paid plan, etc. |
| Ambiguity handling | Hardcoded rules | Embed past clarification patterns, retrieve the relevant one |

**In short:** Pinecone turns the system prompt from a static wall of text into a dynamic, question-aware context window.

---

## Updated Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│   Chat UI — text input, SQL panel, table/chart/number output │
└───────────────────────┬──────────────────────────────────────┘
                        │ SSE stream
┌───────────────────────▼──────────────────────────────────────┐
│                     FastAPI Backend                           │
│                                                              │
│  POST /api/query ─────────────────────────────────────┐      │
│                                                       │      │
│  ┌────────────────────────────────────────────────────▼──┐   │
│  │              RAG Query Pipeline                       │   │
│  │                                                       │   │
│  │  1. History-Aware Reformulator (multi-turn support)    │   │
│  │     └─ LangChain create_history_aware_retriever       │   │
│  │                                                       │   │
│  │  2. Pinecone Retriever (dynamic namespace + filter)   │   │
│  │     └─ Fetch relevant: schema chunks, few-shot        │   │
│  │        examples, glossary terms, query patterns       │   │
│  │                                                       │   │
│  │  3. SQL Generator (LLM + retrieved context)           │   │
│  │     └─ LangChain create_stuff_documents_chain         │   │
│  │                                                       │   │
│  │  4. SQL Validator (read-only enforcement)              │   │
│  │                                                       │   │
│  │  5. Query Executor (SQLite read-only)                 │   │
│  │                                                       │   │
│  │  6. Response Formatter + NL Answer via LLM            │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │   Pinecone   │  │    SQLite    │  │  Embedding Model  │   │
│  │  (RAG index) │  │  (data, RO)  │  │  (llama-text or   │   │
│  │              │  │              │  │   text-embedding)  │   │
│  └──────────────┘  └──────────────┘  └───────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Updated Project Structure

```
nf-querygpt/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app + lifespan
│   ├── config.py                   # All env vars
│   ├── database.py                 # SQLite read-only connection
│   │
│   ├── vectorstore/
│   │   ├── __init__.py
│   │   ├── embeddings.py           # Pinecone embedding class (from your ref code)
│   │   ├── pinecone_client.py      # Pinecone init + vectorstore
│   │   ├── retriever.py            # Dynamic retriever with filters
│   │   └── indexer.py              # One-time script to index schema/examples
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── schema_loader.py        # Load DB schema (also used by indexer)
│   │   ├── sql_validator.py        # Block writes
│   │   ├── query_executor.py       # Execute against SQLite
│   │   ├── response_formatter.py   # Table / number / chart
│   │   └── pipeline.py             # Full RAG chain assembly
│   │
│   ├── prompts/
│   │   ├── system_prompt.py        # QA system prompt
│   │   ├── contextualise.py        # History-aware reformulation prompt
│   │   └── few_shot_bank.py        # All NL→SQL examples (for indexing)
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── query.py                # POST /api/query (streaming + non-streaming)
│   │   ├── schema.py               # GET  /api/schema
│   │   └── suggestions.py          # GET  /api/suggest
│   │
│   └── models/
│       └── schemas.py              # Pydantic models
│
├── scripts/
│   └── index_knowledge.py          # Run once: indexes schema + examples into Pinecone
│
├── data/
│   ├── nf_buildathon.db
│   ├── schema.sql
│   └── csv/
│
├── .env
├── requirements.txt
└── README.md
```

---

## 1. Config — `config.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SQLite
    DB_PATH: str = "data/nf_buildathon.db"

    # Pinecone
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "nf-querygpt"
    PINECONE_NAMESPACE: str = "nf-schema"        # single namespace for this project
    EMBEDDING_MODEL: str = "llama-text-embed-v2"  # or "multilingual-e5-large" for Hinglish

    # LLM
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"

    # App
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 2. Embeddings — `vectorstore/embeddings.py`

Directly adapted from your reference code. Keeping the `input_type` distinction which is critical for retrieval accuracy.

```python
from langchain_core.embeddings import Embeddings
from pinecone import Pinecone


class PineconeLlamaEmbeddings(Embeddings):
    """
    Custom embeddings using Pinecone's hosted llama-text-embed-v2.

    CRITICAL: input_type must differ between indexing and querying.
    - Indexing (embed_documents): input_type = "passage"
    - Querying (embed_query):     input_type = "query"
    Mismatching these is the #1 cause of low similarity scores.
    """

    def __init__(self, pc_client: Pinecone, model_name: str = "llama-text-embed-v2"):
        self.pc = pc_client
        self.model = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.pc.inference.embed(
            model=self.model,
            inputs=texts,
            parameters={"input_type": "passage", "truncate": "END"},
        )
        return [item.values for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        response = self.pc.inference.embed(
            model=self.model,
            inputs=[text],
            parameters={"input_type": "query", "truncate": "END"},
        )
        return response.data[0].values
```

---

## 3. Pinecone Client — `vectorstore/pinecone_client.py`

```python
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from app.config import settings
from app.vectorstore.embeddings import PineconeLlamaEmbeddings

# Singleton instances
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
embeddings = PineconeLlamaEmbeddings(pc, model_name=settings.EMBEDDING_MODEL)

vectorstore = PineconeVectorStore(
    index_name=settings.PINECONE_INDEX_NAME,
    embedding=embeddings,
)
```

---

## 4. Dynamic Retriever — `vectorstore/retriever.py`

Adapted from your reference code's `get_dynamic_retriever`. Here the filter is by `doc_type` (schema / few-shot / glossary) instead of `policy_id`.

```python
from app.vectorstore.pinecone_client import vectorstore
from app.config import settings


def get_retriever(doc_types: list[str] = None, top_k: int = 15):
    """
    Creates a Pinecone retriever scoped to the NF QueryGPT namespace.

    Args:
        doc_types: Filter by document type — ["schema", "few_shot", "glossary"].
                   None = retrieve from all types.
        top_k:     Number of chunks to retrieve. 15 is a good balance —
                   enough context without token bloat.

    Why no score threshold:
        Low-scoring but correct chunks get silently dropped with thresholds.
        Better to retrieve more and let the LLM ignore irrelevant ones.
    """
    search_kwargs: dict = {
        "k": top_k,
        "namespace": settings.PINECONE_NAMESPACE,
    }

    if doc_types:
        search_kwargs["filter"] = {
            "doc_type": {"$in": doc_types}
        }

    return vectorstore.as_retriever(
        search_type="similarity",  # no score threshold — don't drop weak hits
        search_kwargs=search_kwargs,
    )


def get_schema_retriever(top_k: int = 5):
    """Retrieve only schema descriptions for the relevant tables."""
    return get_retriever(doc_types=["schema"], top_k=top_k)


def get_few_shot_retriever(top_k: int = 5):
    """Retrieve the most similar NL→SQL examples."""
    return get_retriever(doc_types=["few_shot"], top_k=top_k)


def get_full_retriever(top_k: int = 15):
    """Retrieve schema + few-shot + glossary — the full context."""
    return get_retriever(doc_types=None, top_k=top_k)
```

---

## 5. Knowledge Indexer — `scripts/index_knowledge.py`

**Run once** to populate Pinecone with three types of documents.

```python
"""
One-time script: indexes schema descriptions, few-shot examples,
and domain glossary into Pinecone for RAG retrieval.

Usage:
    python -m scripts.index_knowledge
"""
import sqlite3
from langchain_core.documents import Document
from app.vectorstore.pinecone_client import vectorstore
from app.config import settings


def build_schema_documents(db_path: str) -> list[Document]:
    """One document per table — rich description with columns, types, FKs, samples."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    docs = []
    for (table_name,) in tables:
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
         "sql": "SELECT * FROM users WHERE is_active = 1 LIMIT 100",
         "tables": "users"},

        # --- Profiles ---
        {"nl": "Profiles missing a photo",
         "sql": "SELECT u.id, u.name FROM users u JOIN profiles p ON u.id = p.user_id WHERE p.photo_url IS NULL OR p.photo_url = ''",
         "tables": "users,profiles"},
        {"nl": "Average profile completion rate",
         "sql": "SELECT AVG(completion_percentage) AS avg_completion FROM profiles",
         "tables": "profiles"},

        # --- Matches ---
        {"nl": "How many matches happened this week?",
         "sql": "SELECT COUNT(*) AS weekly_matches FROM matches WHERE created_at >= date('now', '-7 days')",
         "tables": "matches"},
        {"nl": "Match acceptance rate",
         "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) / COUNT(*), 2) AS acceptance_rate FROM matches",
         "tables": "matches"},
        {"nl": "sabse zyada match kisko mila?",
         "sql": "SELECT user_id, COUNT(*) AS match_count FROM (SELECT user_1_id AS user_id FROM matches UNION ALL SELECT user_2_id FROM matches) GROUP BY user_id ORDER BY match_count DESC LIMIT 10",
         "tables": "matches"},

        # --- Messages ---
        {"nl": "Average messages per match",
         "sql": "SELECT ROUND(AVG(msg_count), 1) AS avg_messages FROM (SELECT match_id, COUNT(*) AS msg_count FROM messages GROUP BY match_id)",
         "tables": "messages"},

        # --- Payments & Plans ---
        {"nl": "Total revenue this quarter",
         "sql": "SELECT SUM(amount) AS total_revenue FROM payments WHERE created_at >= date('now', 'start of month', '-2 months')",
         "tables": "payments"},
        {"nl": "kitne logon ne premium liya?",
         "sql": "SELECT COUNT(DISTINCT s.user_id) AS premium_users FROM subscriptions s JOIN plans p ON s.plan_id = p.id WHERE LOWER(p.name) LIKE '%premium%'",
         "tables": "subscriptions,plans"},
        {"nl": "Which plan has the most subscribers?",
         "sql": "SELECT p.name, COUNT(*) AS subscriber_count FROM subscriptions s JOIN plans p ON s.plan_id = p.id GROUP BY p.id ORDER BY subscriber_count DESC LIMIT 1",
         "tables": "subscriptions,plans"},

        # --- Profile Views ---
        {"nl": "Top 10 most viewed profiles",
         "sql": "SELECT pv.viewed_user_id, u.name, COUNT(*) AS views FROM profile_views pv JOIN users u ON pv.viewed_user_id = u.id GROUP BY pv.viewed_user_id ORDER BY views DESC LIMIT 10",
         "tables": "profile_views,users"},

        # --- Subscriptions ---
        {"nl": "Active vs expired subscriptions",
         "sql": "SELECT status, COUNT(*) AS count FROM subscriptions GROUP BY status",
         "tables": "subscriptions"},

        # --- Reports ---
        {"nl": "Most reported users",
         "sql": "SELECT reported_user_id, COUNT(*) AS report_count FROM reports GROUP BY reported_user_id ORDER BY report_count DESC LIMIT 10",
         "tables": "reports"},

        # --- Support Tickets ---
        {"nl": "Open support tickets by category",
         "sql": "SELECT category, COUNT(*) AS open_count FROM support_tickets WHERE status = 'open' GROUP BY category ORDER BY open_count DESC",
         "tables": "support_tickets"},

        # --- Interests ---
        {"nl": "Top 10 most common interests",
         "sql": "SELECT interest, COUNT(*) AS count FROM interests GROUP BY interest ORDER BY count DESC LIMIT 10",
         "tables": "interests"},

        # --- Cross-table ---
        {"nl": "Premium users who never sent a message",
         "sql": "SELECT u.id, u.name FROM users u JOIN subscriptions s ON u.id = s.user_id JOIN plans p ON s.plan_id = p.id LEFT JOIN messages m ON u.id = m.sender_id WHERE LOWER(p.name) LIKE '%premium%' AND m.id IS NULL",
         "tables": "users,subscriptions,plans,messages"},

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
        docs.append(Document(
            page_content=content,
            metadata={
                "doc_type": "few_shot",
                "tables": ex["tables"],
                "language": "hinglish" if any(
                    w in ex["nl"].lower() for w in ["kitne", "sabse", "zyada", "logon", "kisko", "mila"]
                ) else "english",
            },
        ))

    return docs


def build_glossary_documents() -> list[Document]:
    """Domain terms that the LLM might misinterpret."""
    glossary = [
        {"term": "match", "definition": "A mutual connection between two users who have both expressed interest in each other. Stored in the matches table with status (pending/accepted/rejected)."},
        {"term": "premium / gold / platinum", "definition": "Paid subscription tiers in the plans table. Users subscribe via the subscriptions table and pay via the payments table."},
        {"term": "profile view", "definition": "When one user views another user's profile. Tracked in profile_views with viewer_id and viewed_user_id."},
        {"term": "report", "definition": "A user filing a complaint against another user. Stored in reports with reporter_user_id and reported_user_id."},
        {"term": "interest", "definition": "A hobby or trait listed by a user in their profile. Stored in the interests table linked to user_id."},
        {"term": "partner preference", "definition": "Criteria a user sets for their ideal match — age range, location, religion, etc. Stored in partner_preferences."},
        {"term": "active user", "definition": "A user with is_active = 1 in the users table. Does NOT mean recently logged in."},
        {"term": "revenue / paisa / payment", "definition": "Money collected from users. Stored in the payments table with amount, currency, and status fields."},
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
    print(f"  → {len(schema_docs)} table descriptions")

    print("Building few-shot documents...")
    few_shot_docs = build_few_shot_documents()
    print(f"  → {len(few_shot_docs)} NL→SQL examples")

    print("Building glossary documents...")
    glossary_docs = build_glossary_documents()
    print(f"  → {len(glossary_docs)} glossary terms")

    all_docs = schema_docs + few_shot_docs + glossary_docs
    print(f"\nIndexing {len(all_docs)} documents into Pinecone...")
    print(f"  Index: {settings.PINECONE_INDEX_NAME}")
    print(f"  Namespace: {settings.PINECONE_NAMESPACE}")

    vectorstore.add_documents(all_docs, namespace=settings.PINECONE_NAMESPACE)
    print("Done.")


if __name__ == "__main__":
    main()
```

---

## 6. Prompts — `prompts/system_prompt.py`

The system prompt now expects retrieved context (schema + examples + glossary) injected by LangChain's `{context}` variable.

```python
qa_system_prompt = """You are NF QueryGPT — a data assistant for NikahForever, a matrimonial platform.
You convert natural language questions (English or Hinglish) into SQLite-compatible SQL queries.

RETRIEVED CONTEXT (schema, examples, glossary):
{context}

RULES — follow these exactly:
1. ONLY generate SELECT queries. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.
2. Use table and column names EXACTLY as shown in the retrieved schema. Never invent columns.
3. Use explicit JOIN syntax with aliases (u for users, p for profiles, m for matches, etc.).
4. Add LIMIT 100 to queries that could return large result sets unless the user asks for all.
5. For aggregations, use meaningful aliases (e.g., AS total_revenue, AS match_count).
6. Handle dates with SQLite functions: date(), strftime(), datetime().
7. If the question is ambiguous or you cannot determine which columns to use, set needs_clarification = true.
8. Never guess. If a column might not exist, ask rather than hallucinate.
9. For Hinglish, understand the intent first, then generate SQL. Note the language in your explanation.
10. If the retrieved context includes a similar example, adapt its SQL pattern — don't start from scratch.

RESPONSE FORMAT — always respond with valid JSON, nothing else:
{{
  "sql": "SELECT ...",
  "explanation": "What this query does, in plain English",
  "result_type": "table | number | chart",
  "chart_config": {{"type": "bar|line|pie", "x": "column", "y": "column"}},
  "needs_clarification": false,
  "clarification": null
}}

If you need to ask for clarification:
{{
  "sql": null,
  "explanation": null,
  "result_type": null,
  "needs_clarification": true,
  "clarification": "Your specific follow-up question"
}}
"""
```

---

## 7. Contextualise Prompt — `prompts/contextualise.py`

```python
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, just "
    "reformulate it if needed and otherwise return it as is."
)
```

---

## 8. RAG Pipeline — `core/pipeline.py`

This is the heart of the system. Adapted from your reference code's pattern.

```python
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever

from app.config import settings
from app.vectorstore.retriever import get_full_retriever
from app.prompts.system_prompt import qa_system_prompt
from app.prompts.contextualise import contextualize_q_system_prompt
from app.core.sql_validator import validate_sql
from app.core.query_executor import execute_query
from app.core.response_formatter import format_response

# LLM instances
llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0)
streaming_llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0, streaming=True)

# Prompt templates
contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

qa_prompt = ChatPromptTemplate.from_messages([
    ("system", qa_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])


# ---------------------------------------------------------------------------
# Streaming entry-point (SSE)
# ---------------------------------------------------------------------------
async def stream_query(question: str, chat_history: list):
    """
    SSE streaming generator.

    Yields:
        data: {"type": "sql",     "content": "SELECT ..."}
        data: {"type": "token",   "content": "<token>"}
        data: {"type": "result",  "content": { ... }}
        data: [DONE]
    """
    retriever = get_full_retriever(top_k=15)

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    question_answer_chain = create_stuff_documents_chain(streaming_llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    full_answer = ""

    async for chunk in rag_chain.astream({
        "input": question,
        "chat_history": chat_history,
    }):
        if "answer" in chunk:
            full_answer += chunk["answer"]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk['answer']})}\n\n"

    # Once streaming is done, parse the full JSON response
    try:
        llm_data = json.loads(full_answer)
    except json.JSONDecodeError:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to parse LLM response'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Handle clarification
    if llm_data.get("needs_clarification"):
        yield f"data: {json.dumps({'type': 'clarification', 'content': llm_data['clarification']})}\n\n"
        yield "data: [DONE]\n\n"
        return

    sql = llm_data.get("sql", "")
    yield f"data: {json.dumps({'type': 'sql', 'content': sql})}\n\n"

    # Validate
    validation = validate_sql(sql)
    if not validation["valid"]:
        yield f"data: {json.dumps({'type': 'error', 'content': validation['error']})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Execute
    result = execute_query(validation["sanitised_sql"])
    if "error" in result:
        yield f"data: {json.dumps({'type': 'error', 'content': result['error']})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Format and send
    formatted = await format_response(result, llm_data)
    yield f"data: {json.dumps({'type': 'result', 'content': formatted})}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Non-streaming entry-point (for testing / API calls)
# ---------------------------------------------------------------------------
async def invoke_query(question: str, chat_history: list) -> dict:
    """
    Non-streaming version — returns the full structured response.
    """
    retriever = get_full_retriever(top_k=15)

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    result = await rag_chain.ainvoke({
        "input": question,
        "chat_history": chat_history,
    })

    answer = result.get("answer", "")

    try:
        llm_data = json.loads(answer)
    except json.JSONDecodeError:
        return {"success": False, "error": "Failed to parse LLM response", "raw": answer}

    if llm_data.get("needs_clarification"):
        return {
            "success": True,
            "needs_clarification": True,
            "clarification": llm_data["clarification"],
        }

    sql = llm_data.get("sql", "")
    validation = validate_sql(sql)
    if not validation["valid"]:
        return {"success": False, "error": validation["error"]}

    query_result = execute_query(validation["sanitised_sql"])
    if "error" in query_result:
        return {"success": False, "error": query_result["error"]}

    formatted = await format_response(query_result, llm_data)

    return {
        "success": True,
        "question": question,
        "sql": validation["sanitised_sql"],
        "explanation": llm_data.get("explanation"),
        "result": formatted,
        "execution_time_ms": query_result["execution_time_ms"],
    }
```

---

## 9. Routes — `routes/query.py`

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import QueryRequest, QueryResponse
from app.core.pipeline import stream_query, invoke_query

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query/stream")
async def handle_query_stream(request: QueryRequest):
    """SSE streaming endpoint — use for the chat UI."""
    return StreamingResponse(
        stream_query(request.question, request.chat_history or []),
        media_type="text/event-stream",
    )


@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """Non-streaming endpoint — returns full response at once."""
    result = await invoke_query(request.question, request.chat_history or [])
    return result
```

---

## 10. SQL Validator — `core/sql_validator.py`

*(Unchanged from the previous guide — same read-only enforcement)*

```python
import re
import sqlparse

BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "ATTACH",
    "DETACH", "PRAGMA",
]

BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(BLOCKED_KEYWORDS) + r")\b", re.IGNORECASE,
)


def validate_sql(sql: str) -> dict:
    if not sql or not sql.strip():
        return {"valid": False, "error": "Empty query", "sanitised_sql": None}

    parsed = sqlparse.format(sql, strip_comments=True).strip()

    if BLOCKED_PATTERN.search(parsed):
        matched = BLOCKED_PATTERN.findall(parsed)
        return {"valid": False, "error": f"Blocked: {', '.join(matched)}", "sanitised_sql": None}

    first_kw = parsed.split()[0].upper() if parsed else ""
    if first_kw not in ("SELECT", "WITH"):
        return {"valid": False, "error": f"Only SELECT allowed. Got: {first_kw}", "sanitised_sql": None}

    statements = [s for s in sqlparse.split(parsed) if s.strip()]
    if len(statements) > 1:
        return {"valid": False, "error": "Multiple statements not allowed", "sanitised_sql": None}

    if "LIMIT" not in parsed.upper():
        parsed = parsed.rstrip(";") + " LIMIT 500"

    return {"valid": True, "error": None, "sanitised_sql": parsed + ";"}
```

---

## 11. Pinecone Index Setup

Before running the indexer, create the index in the Pinecone console or via API:

```python
# One-time setup (run in a notebook or script)
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="YOUR_KEY")

pc.create_index(
    name="nf-querygpt",
    dimension=1024,              # llama-text-embed-v2 outputs 1024-dim vectors
    metric="cosine",
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1",      # match your Pinecone plan region
    ),
)
```

Then run the indexer:

```bash
python -m scripts.index_knowledge
```

---

## 12. Dependencies — `requirements.txt`

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
openai==1.82.*
sqlparse==0.5.*
pydantic-settings==2.*
python-dotenv==1.*

# Pinecone + LangChain
pinecone==5.*
langchain-pinecone==0.2.*
langchain-openai==0.3.*
langchain-core==0.3.*
langchain-classic==0.1.*

# If using Pinecone's hosted embedding
# (no extra package needed — uses pinecone.inference.embed)
```

---

## 13. Key Differences from Your Reference Code

| Aspect | Your Policy Chat (reference) | NF QueryGPT (this project) |
|--------|------------------------------|---------------------------|
| **Namespace** | Per-user (`user_id`) | Single shared (`nf-schema`) — everyone queries the same DB |
| **Filter** | By `policy_id` | By `doc_type` (schema / few_shot / glossary) |
| **Post-retrieval** | Direct LLM answer | LLM generates SQL → validate → execute → format |
| **Streaming output** | Raw text tokens | Structured SSE frames (sql, token, result, error) |
| **Embedding model** | `llama-text-embed-v2` | Same — reuse your Pinecone infra |
| **k value** | 20 | 15 (schema docs are fewer and more targeted) |

---

## 14. What Gets Indexed in Pinecone (Summary)

| doc_type | Count | What |
|----------|-------|------|
| `schema` | 12 | One rich description per table (columns, types, FKs, sample rows) |
| `few_shot` | 15–50+ | NL→SQL example pairs covering all tables, including Hinglish |
| `glossary` | 8–15 | Domain terms: "match", "premium", "report", "active user", etc. |

**Total:** ~35–75 documents. Tiny index, fast retrieval, low cost.

---

## 15. Execution Flow (Step by Step)

```
User: "kitne logon ne premium liya?"
         │
         ▼
1. History-Aware Reformulator
   (no history → passes through unchanged)
         │
         ▼
2. Pinecone Retriever (top 15)
   Retrieved:
   ├── [schema]   subscriptions table description
   ├── [schema]   plans table description
   ├── [schema]   users table description
   ├── [few_shot] "kitne logon ne premium liya?" → SQL example
   ├── [few_shot] "Which plan has the most subscribers?" → SQL example
   └── [glossary] "premium = paid subscription tier..."
         │
         ▼
3. LLM (GPT-4o, temp=0)
   System prompt + retrieved context + user question
   → Generates JSON with SQL
         │
         ▼
4. SQL Validator
   ✓ SELECT only, no blocked keywords, single statement
   → Sanitised SQL
         │
         ▼
5. SQLite Executor (read-only)
   → { columns, rows, row_count, execution_time_ms }
         │
         ▼
6. Response Formatter
   → { type: "number", value: 1247, label: "premium_users" }
         │
         ▼
7. SSE Stream to Frontend
   data: {"type":"sql","content":"SELECT COUNT(DISTINCT ...) ..."}
   data: {"type":"result","content":{"type":"number","value":1247}}
   data: [DONE]
```

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set env vars
cp .env.example .env
# Fill in PINECONE_API_KEY, OPENAI_API_KEY

# 3. Place nf_buildathon.db in data/

# 4. Create Pinecone index (one time)
# Via console or the script in Section 11

# 5. Index knowledge (one time)
python -m scripts.index_knowledge

# 6. Run
uvicorn app.main:app --reload --port 8000

# 7. Test
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "kitne logon ne premium liya?"}'
```
