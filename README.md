# NF QueryGPT

NF QueryGPT is an AI-powered data assistant for NikahForever. It lets users ask business questions in plain English or Hinglish, converts them into safe read-only SQL, queries the local SQLite database, and shows the results in a Streamlit app backed by a FastAPI API.

## Setup

### Prerequisites

- Python `3.13+`
- `uv` installed
- A local database file at `data/nf_buildathon.db`
- Pinecone API key
- Gemini API key

### 1. Create and activate the virtual environment

```powershell
uv venv
.venv\Scripts\activate
```

### 2. Install dependencies

```powershell
uv sync
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your keys.

```powershell
Copy-Item .env.example .env
```

Required values in `.env`:

```env
DB_PATH=data/nf_buildathon.db
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=nikahforever
EMBEDDING_MODEL=llama-text-embed-v2
GEMINI_API_KEY=your_gemini_key
GEMINI_MODELS=gemini-3.5-flash
CORS_ORIGINS=http://localhost:8501
```

### 4. Index the knowledge base

Create a Pinecone index named `nikahforever`, then run:

```powershell
uv run python -m scripts.index_knowledge
```

## Run

Start both the backend and frontend together:

```powershell
uv run python main.py
```

App URLs:

- Frontend: `http://localhost:8501`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Run Services Separately

Backend:

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
uv run streamlit run app/frontend.py
```

## What This Project Does

- Accepts natural language analytics questions
- Retrieves schema and example knowledge from Pinecone
- Generates safe SQL for the NikahForever dataset
- Queries the SQLite database in read-only mode
- Streams answers and results in a simple chat UI
