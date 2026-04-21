# NL2SQL Clinic API

An AI-powered Natural Language to SQL system for a clinic dataset.

**LLM Provider: Ollama (Mistral)**

## Architecture Overview

1. User asks a question in Streamlit UI
2. Frontend sends request to FastAPI `POST /chat`
3. Backend uses Vanna 2.0 agent with Ollama (Mistral) to generate SQL
4. SQL is validated for safety (SELECT-only, dangerous patterns blocked)
5. Valid SQL executes on `clinic.db` (SQLite)
6. API returns structured JSON (`message`, `sql_query`, `columns`, `rows`, `row_count`, optional chart)

## Reviewer Setup (Ollama Required)

If Ollama is not installed:

1. Download Ollama from [https://ollama.com](https://ollama.com)
2. Pull the model:

```bash
ollama pull mistral
```

3. Start Ollama (it runs in the background), either by opening the Ollama app or:

```bash
ollama serve
```

Create `.env` using this exact setup:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral
```

## Required One-Command Run

Assignment command:

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

Windows equivalent:

```bash
pip install -r requirements.txt; py -3.9 setup_database.py; py -3.9 seed_memory.py; py -3.9 -m uvicorn main:app --port 8000
```

Note: In Windows PowerShell 5.1, use `;` between commands (as shown above).

If port `8000` is blocked, use `8002`:

```bash
py -3.9 -m uvicorn main:app --port 8002 --reload
```

## Run Full System

### Terminal 1 — Start API backend

Make sure Ollama is running, then:

```bash
py -3.9 -m uvicorn main:app --port 8000 --reload
```

Expected output includes:

```text
INFO: Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2 — Start Streamlit frontend

In the same project folder:

```bash
streamlit run app.py
```

Browser opens at:

`http://localhost:8501`

## Test Frontend

1. Sidebar shows **Connected** in green
2. Click any example question button in sidebar
3. Question appears in chat input
4. Press Enter
5. Verify AI message, SQL expander, data table, optional chart
6. Try: `Show revenue by doctor` (should produce a chart)

## Test API Directly (Optional)

```bash
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"question\":\"How many patients do we have?\"}"
```

Example response:

```json
{
  "message": "Here are the results.",
  "sql_query": "SELECT COUNT(*) AS total_patients FROM patients",
  "columns": ["total_patients"],
  "rows": [[200]],
  "row_count": 1,
  "chart": null,
  "chart_type": null
}
```

Expected JSON keys:
`message`, `sql_query`, `columns`, `rows`, `row_count`

## Test Health

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok","database":"connected","agent_memory_items":123}
```

