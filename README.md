# NL2SQL Clinic API

An AI-powered Natural Language to SQL system for a clinic dataset.

**LLM Provider: Ollama (Mistral)**

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
pip install -r requirements.txt && py -3.9 setup_database.py && py -3.9 seed_memory.py && py -3.9 -m uvicorn main:app --port 8000
```

If port `8000` is blocked, use `8002`:

```bash
py -3.9 -m uvicorn main:app --port 8002
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

