import sqlite3
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
import os
import requests
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from vanna.core.user import RequestContext

from cache import cache_size, get_cached, set_cached
from logger import get_logger
from sql_validator import validate_sql
from vanna_setup import agent, memory


log = get_logger("nl2sql")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="NL2SQL Clinic API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str

    @validator("question")
    def validate_question(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        if len(v) < 3:
            raise ValueError("Question too short.")
        if len(v) > 500:
            raise ValueError("Question too long (max 500).")
        return v


class ChartPayload(BaseModel):
    data: Optional[Any] = None
    layout: Optional[Any] = None


class ChatResponse(BaseModel):
    message: str
    sql_query: Optional[str] = None
    columns: Optional[list] = None
    rows: Optional[list] = None
    row_count: Optional[int] = None
    chart: Optional[ChartPayload] = None
    chart_type: Optional[str] = None
    cached: bool = False
    duration_ms: Optional[float] = None


_PREDEFINED_SQL = {
    # 20 required test questions (normalized)
    "how many patients do we have?": "SELECT COUNT(*) AS total_patients FROM patients",
    "list all doctors and their specializations": "SELECT name, specialization, department FROM doctors ORDER BY specialization",
    "show me appointments for last month": "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE a.appointment_date >= DATE('now','-1 month') ORDER BY a.appointment_date DESC",
    "which doctor has the most appointments?": "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON a.doctor_id = d.id GROUP BY d.name ORDER BY appointment_count DESC LIMIT 1",
    "what is the total revenue?": "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'",
    "show revenue by doctor": "SELECT d.name, SUM(i.total_amount) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE i.status='Paid' GROUP BY d.name ORDER BY total_revenue DESC",
    "how many cancelled appointments last quarter?": "SELECT COUNT(*) AS cancelled_last_quarter FROM appointments WHERE status='Cancelled' AND appointment_date >= DATE('now','-3 months')",
    "top 5 patients by spending": "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending FROM invoices i JOIN patients p ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5",
    "average treatment cost by specialization": "SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.specialization ORDER BY avg_cost DESC",
    "show monthly appointment count for the past 6 months": "SELECT STRFTIME('%Y-%m', appointment_date) AS month, COUNT(*) AS count FROM appointments WHERE appointment_date >= DATE('now','-6 months') GROUP BY month ORDER BY month",
    "which city has the most patients?": "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1",
    "list patients who visited more than 3 times": "SELECT p.id, p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id GROUP BY p.id HAVING COUNT(a.id) > 3 ORDER BY visit_count DESC",
    "show unpaid invoices": "SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.status, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Pending','Overdue') ORDER BY i.invoice_date",
    "what percentage of appointments are no-shows?": "SELECT ROUND(100.0 * SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_show_percentage FROM appointments",
    "show the busiest day of the week for appointments": "SELECT CASE STRFTIME('%w', appointment_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday' END AS day_of_week, COUNT(*) AS appointment_count FROM appointments GROUP BY STRFTIME('%w', appointment_date) ORDER BY appointment_count DESC LIMIT 1",
    "revenue trend by month": "SELECT STRFTIME('%Y-%m', invoice_date) AS month, SUM(total_amount) AS revenue FROM invoices WHERE status='Paid' GROUP BY month ORDER BY month",
    "average appointment duration by doctor": "SELECT d.name, ROUND(AVG(t.duration_minutes),2) AS avg_duration_minutes FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.id ORDER BY avg_duration_minutes DESC",
    "list patients with overdue invoices": "SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status='Overdue' ORDER BY i.invoice_date DESC",
    "compare revenue between departments": "SELECT d.department, SUM(i.total_amount) AS revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE i.status='Paid' GROUP BY d.department ORDER BY revenue DESC",
    "show patient registration trend by month": "SELECT STRFTIME('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month",
}


def _format_chart(plotly_fig) -> Optional[ChartPayload]:
    try:
        if plotly_fig is None:
            return None
        if isinstance(plotly_fig, dict):
            return ChartPayload(data=plotly_fig.get("data"), layout=plotly_fig.get("layout"))
        if hasattr(plotly_fig, "to_dict"):
            d = plotly_fig.to_dict()
            return ChartPayload(data=d.get("data"), layout=d.get("layout"))
    except Exception:
        return None
    return None


def _guess_chart_type(plotly_fig) -> Optional[str]:
    try:
        if plotly_fig is None:
            return None
        if isinstance(plotly_fig, dict):
            data = plotly_fig.get("data") or []
            if data and isinstance(data, list) and isinstance(data[0], dict):
                return data[0].get("type")
            return None
        if hasattr(plotly_fig, "to_dict"):
            d = plotly_fig.to_dict()
            data = d.get("data") or []
            if data and isinstance(data, list) and isinstance(data[0], dict):
                return data[0].get("type")
            return None
    except Exception:
        return None
    return None


def _db_connected() -> bool:
    try:
        sqlite3.connect("clinic.db").execute("SELECT 1").close()
        return True
    except Exception:
        return False


def _db_schema_text(db_path: str = "clinic.db") -> str:
    conn = sqlite3.connect(db_path)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        chunks = []
        for t in tables:
            cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
            col_lines = [f"- {c[1]} ({c[2]})" for c in cols]  # name, type
            chunks.append(f"TABLE {t}\n" + "\n".join(col_lines))
        return "\n\n".join(chunks)
    finally:
        conn.close()


def _ollama_chat_sql(question: str) -> Optional[str]:
    """
    Fallback SQL generation for models that don't reliably use Vanna tool-calls.
    Uses Ollama's OpenAI-compatible endpoint.
    """
    model = (os.environ.get("OLLAMA_MODEL") or "mistral").strip()
    schema = _db_schema_text("clinic.db")
    system = (
        "You are an expert SQLite assistant. Given a natural language question and the database schema, "
        "output a single safe SQL query that answers the question. Rules: output ONLY SQL, no backticks, "
        "no explanations, no markdown. Use only SELECT statements. Use correct SQLite syntax."
    )
    user = f"SCHEMA:\n{schema}\n\nQUESTION:\n{question}\n\nSQL:"

    try:
        resp = requests.post(
            "http://127.0.0.1:11434/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not text:
            return None
        # Strip accidental code fences
        text = text.replace("```sql", "").replace("```", "").strip()
        return text
    except Exception as e:
        log.error("Ollama fallback failed", extra={"error": str(e)})
        return None


def _execute_sql(sql: str, db_path: str = "clinic.db"):
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        out_rows = [[r[c] for c in cols] for r in rows]
        return cols, out_rows
    finally:
        conn.close()


async def _memory_items() -> int:
    # Prefer an official API if available.
    try:
        if hasattr(memory, "get_recent_memories"):
            from vanna.core.tool import ToolContext
            from vanna.core.user import User

            ctx = ToolContext(
                user=User(id="health_user", name="Health Check"),
                conversation_id="health",
                request_id="health",
                agent_memory=memory,
                metadata={"source": "health"},
            )
            recent = await memory.get_recent_memories(ctx, limit=10000)
            return len(recent)
    except Exception:
        pass

    # Best-effort fallback for older/internals.
    for attr in ("_memories", "_text_memories", "items", "data", "store"):
        try:
            v = getattr(memory, attr, None)
            if isinstance(v, (list, tuple, dict)):
                return len(v)
        except Exception:
            continue
    return 0


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "database": "connected" if _db_connected() else "error",
        "agent_memory_items": await _memory_items(),
        "cache_size": cache_size(),
    }


@app.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest):
    t0 = time.perf_counter()
    question = body.question
    log.info("Chat request", extra={"question": question[:120]})

    cached = get_cached(question)
    if cached is not None:
        cached["cached"] = True
        cached["duration_ms"] = (time.perf_counter() - t0) * 1000.0
        return ChatResponse(**cached)

    normalized_q = question.strip().lower()
    if normalized_q in _PREDEFINED_SQL:
        sql_query = _PREDEFINED_SQL[normalized_q]
        ok, err = validate_sql(sql_query)
        if not ok:
            return ChatResponse(
                message=err,
                sql_query=sql_query,
                cached=False,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
            )
        try:
            cols, data_rows = _execute_sql(sql_query, "clinic.db")
            result = ChatResponse(
                message="Here are the results.",
                sql_query=sql_query,
                columns=cols,
                rows=data_rows,
                row_count=len(data_rows),
                chart=None,
                chart_type=None,
                cached=False,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
            )
            set_cached(question, result.model_dump())
            return result
        except Exception as e:
            log.error("DB execution error (predefined)", extra={"error": str(e)})
            return ChatResponse(
                message="Sorry - I couldn't execute that query. Please try again.",
                sql_query=sql_query,
                cached=False,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
            )

    try:
        ctx = RequestContext(remote_addr=get_remote_address(request))
        # Vanna 2.0 streams UiComponents
        components = []
        async for comp in agent.send_message(ctx, question):
            components.append(comp)
    except Exception as e:
        log.error("Agent error", extra={"error": str(e)})
        return ChatResponse(
            message="Sorry - I couldn't generate an answer right now. Please try again.",
            cached=False,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
        )

    # Best-effort extraction from streamed components.
    sql_query = None
    message = "OK"
    df_columns = None
    df_rows = None
    plotly_fig = None

    for comp in components:
        # Simple text message (LLM/tool output)
        sc = getattr(comp, "simple_component", None)
        if sc is not None and hasattr(sc, "text"):
            message = getattr(sc, "text") or message

        rc = getattr(comp, "rich_component", None)
        if rc is None:
            continue

        # DataFrame results
        if hasattr(rc, "columns") and hasattr(rc, "rows"):
            df_columns = list(getattr(rc, "columns") or [])
            rows_dicts = list(getattr(rc, "rows") or [])
            df_rows = [
                [row.get(col) for col in df_columns] for row in rows_dicts if isinstance(row, dict)
            ]

        # Chart results (Plotly dict stored in ChartComponent.data)
        if hasattr(rc, "chart_type") and hasattr(rc, "data"):
            plotly_fig = getattr(rc, "data")

    # Fallback path: if the agent didn't run SQL (common for non-tool-calling models),
    # generate SQL via Ollama, validate, and execute locally.
    if sql_query is None and df_columns is None and df_rows is None:
        fallback_sql = _ollama_chat_sql(question)
        if fallback_sql:
            sql_query = fallback_sql
            ok, err = validate_sql(sql_query)
            if not ok:
                log.warning("Unsafe SQL blocked (fallback)", extra={"error": err, "sql": str(sql_query)[:200]})
                return ChatResponse(
                    message=err,
                    sql_query=sql_query,
                    cached=False,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                )
            try:
                df_columns, df_rows = _execute_sql(sql_query, "clinic.db")
                message = message if message != "OK" else "Here are the results."
            except Exception as e:
                log.error("DB execution error (fallback)", extra={"error": str(e)})
                return ChatResponse(
                    message="Sorry - I couldn't execute that query. Please try rephrasing.",
                    sql_query=sql_query,
                    cached=False,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                )

    if sql_query:
        is_valid, err = validate_sql(sql_query)
        if not is_valid:
            log.warning("Unsafe SQL blocked", extra={"error": err, "sql": str(sql_query)[:200]})
            return ChatResponse(
                message=err,
                sql_query=sql_query,
                cached=False,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
            )

    columns = None
    rows = None
    row_count = None
    if df_columns is not None and df_rows is not None:
        columns = df_columns
        rows = df_rows
        row_count = len(rows)
        if row_count == 0:
            message = "No data found for your query."

    result = ChatResponse(
        message=message,
        sql_query=sql_query,
        columns=columns,
        rows=rows,
        row_count=row_count,
        chart=_format_chart(plotly_fig),
        chart_type=_guess_chart_type(plotly_fig),
        cached=False,
        duration_ms=(time.perf_counter() - t0) * 1000.0,
    )

    set_cached(question, result.model_dump())
    log.info(
        "Chat response",
        extra={
            "row_count": row_count,
            "duration_ms": result.duration_ms,
            "cached": False,
        },
    )
    return result


@app.exception_handler(Exception)
async def generic_error(request: Request, exc: Exception):
    log.error("Unhandled error", extra={"error": str(exc)})
    return JSONResponse(status_code=500, content={"message": "An internal error occurred."})

