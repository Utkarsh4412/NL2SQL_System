# NL2SQL Clinic API

An AI-powered Natural Language to SQL system for a small clinic dataset. Ask a question in plain English, the system generates SQL, validates it for safety, executes it against SQLite, and returns structured JSON with optional Plotly chart payload.

Built with Python 3.11, FastAPI, Vanna 2.0, SQLite, Plotly, and a small set of production-oriented bonuses (validation, caching, rate limiting, structured logging).

## Architecture overview

```
Client question
  -> FastAPI POST /chat (Pydantic validation, rate limit, cache)
  -> Vanna Agent.send_message(question)
  -> Extract SQL + validate_sql() (SELECT-only + safety filters)
  -> (Vanna tools) RunSqlTool executes on clinic.db
  -> (Optional) VisualizeDataTool returns Plotly figure
  -> JSON response (message + sql + rows/cols + chart)
```

## Prerequisites

- Python 3.11+
- pip
- (Optional) Ollama if using local LLMs

## Setup instructions

1. Create and activate a virtual environment (recommended).

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create the database:

```bash
python setup_database.py
```

4. Seed agent memory (17 known-good Q→SQL pairs):

```bash
python seed_memory.py
```

## LLM provider configuration

Create a `.env` file (or export env vars) based on `.env.example`.

- **Gemini (recommended)**: set `LLM_PROVIDER=gemini` and `GOOGLE_API_KEY=...`
  - Key: `https://aistudio.google.com/apikey`
- **Groq**: set `LLM_PROVIDER=groq` and `GROQ_API_KEY=...`
  - Console: `https://console.groq.com`
- **Ollama (local)**: set `LLM_PROVIDER=ollama` and optionally `OLLAMA_MODEL=mistral`
  - Install: `https://ollama.com`
  - Example: `ollama pull mistral`

Optional model overrides:
- `GEMINI_MODEL` (default: `gemini-2.0-flash`)
- `GROQ_MODEL` (default: `llama-3.1-70b-versatile`)
- `OLLAMA_MODEL` (default: `llama3`)

## Running the server

```bash
uvicorn main:app --port 8000 --reload
```

Open API docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Frontend (Streamlit)

Start the API server first:

```bash
py -3.9 -m uvicorn main:app --port 8000
```

Then in a second terminal, start the Streamlit frontend:

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`

Features:
- Chat interface — type questions in plain English
- View generated SQL for every query
- Interactive data tables with CSV download
- Plotly charts for visualization queries
- Sidebar with example questions to click
- API health status indicator
- Conversation history

## API documentation (example)

### Request

`POST /chat`

```json
{ "question": "How many patients do we have?" }
```

### Response (example shape)

```json
{
  "message": "There are 200 patients.",
  "sql_query": "SELECT COUNT(*) AS total_patients FROM patients",
  "columns": ["total_patients"],
  "rows": [[200]],
  "row_count": 1,
  "chart": null,
  "chart_type": null,
  "cached": false,
  "duration_ms": 312.4
}
```

## Testing with curl examples

Health:

```bash
curl http://localhost:8000/health
```

Chat:

```bash
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"question\":\"How many patients do we have?\"}"
```

## Running the 20 test questions

After the server is running, send the 20 questions listed in the assignment to `POST /chat` and record:
- generated SQL
- whether it was correct/safe
- short result summary

Fill them into `RESULTS.md`.

## Docker deployment

This repository includes a `Dockerfile` (build/run is optional for this assignment run-through).

```bash
docker build -t nl2sql-clinic .
docker run -p 8000:8000 --env-file .env nl2sql-clinic
```

## Required one-command run

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

