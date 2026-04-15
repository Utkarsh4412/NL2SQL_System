import os
import asyncio

from dotenv import load_dotenv

# Vanna 2.0 imports (per docs / assignment)
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import RequestContext, User, UserResolver
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.sqlite import SqliteRunner
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)
from vanna.core.tool import ToolContext

from logger import get_logger
from sql_validator import validate_sql


load_dotenv()
log = get_logger("nl2sql")

DB_PATH = os.environ.get("CLINIC_DB_PATH", "clinic.db")
LLM_PROVIDER = (os.environ.get("LLM_PROVIDER") or "gemini").strip().lower()
_ALLOW_FALLBACK = (os.environ.get("ALLOW_NO_KEY_FALLBACK") or "1").strip().lower() in (
    "1",
    "true",
    "yes",
)


class DefaultUserResolver(UserResolver):
    # Some Vanna 2.0 releases name this method `resolve_user` (abstract).
    async def resolve_user(self, request: RequestContext) -> User:  # type: ignore[override]
        return User(id="default_user", name="Clinic Staff")

    # Back-compat alias (older docs/examples)
    async def resolve(self, request: RequestContext) -> User:  # type: ignore[override]
        return await self.resolve_user(request)


def _build_ollama_llm():
    from vanna.integrations.openai import OpenAILlmService

    model = os.environ.get("OLLAMA_MODEL") or "llama3"
    return OpenAILlmService(
        api_key="ollama",
        base_url="http://localhost:11434/v1",
        model=model,
    )


def _build_llm_service():
    if LLM_PROVIDER == "gemini":
        from vanna.integrations.google import GeminiLlmService

        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
        model = os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash"
        if not api_key:
            if _ALLOW_FALLBACK:
                log.warning("Missing GOOGLE_API_KEY/GEMINI_API_KEY; falling back to Ollama.")
                return _build_ollama_llm()
            log.warning("Missing GOOGLE_API_KEY/GEMINI_API_KEY; Gemini calls will fail.")
        return GeminiLlmService(api_key=api_key, model=model)

    if LLM_PROVIDER == "groq":
        from vanna.integrations.openai import OpenAILlmService

        api_key = os.environ.get("GROQ_API_KEY") or ""
        model = os.environ.get("GROQ_MODEL") or "llama-3.1-70b-versatile"
        if not api_key:
            if _ALLOW_FALLBACK:
                log.warning("Missing GROQ_API_KEY; falling back to Ollama.")
                return _build_ollama_llm()
            log.warning("Missing GROQ_API_KEY; Groq calls will fail.")
        return OpenAILlmService(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            model=model,
        )

    if LLM_PROVIDER == "ollama":
        return _build_ollama_llm()

    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. Use gemini|groq|ollama.")


def _register_tool(registry: ToolRegistry, tool, access_groups=None) -> None:
    """
    Vanna 2.0 uses ToolRegistry.register_local_tool(...) in current docs, but we keep a
    small compatibility wrapper because some releases exposed .register(...).
    """
    if access_groups is None:
        access_groups = ["admin", "user"]
    if hasattr(registry, "register_local_tool"):
        registry.register_local_tool(tool, access_groups=access_groups)
    else:
        registry.register(tool)


def build_agent() -> Agent:
    llm = _build_llm_service()

    # Sql runner for the clinic DB
    base_runner = SqliteRunner(database_path=DB_PATH)

    class SafeSqliteRunner:
        def __init__(self, inner):
            self._inner = inner

        async def run_sql(self, args, context):  # Vanna expects this method
            sql = getattr(args, "sql", None) if args is not None else None
            ok, err = validate_sql(sql or "")
            if not ok:
                raise ValueError(err)
            return await self._inner.run_sql(args, context)

    db_runner = SafeSqliteRunner(base_runner)

    # In-memory demo memory (ephemeral)
    agent_memory = DemoAgentMemory(max_items=int(os.environ.get("MEMORY_MAX_ITEMS", "2000")))

    tools = ToolRegistry()
    _register_tool(tools, RunSqlTool(sql_runner=db_runner), access_groups=["admin", "user"])
    _register_tool(tools, VisualizeDataTool(), access_groups=["admin", "user"])
    _register_tool(tools, SaveQuestionToolArgsTool(), access_groups=["admin"])
    _register_tool(tools, SearchSavedCorrectToolUsesTool(), access_groups=["admin", "user"])

    cfg = AgentConfig(stream_responses=False)

    return Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        config=cfg,
        agent_memory=agent_memory,
    )


agent = build_agent()
memory = agent.agent_memory


_SEED_PAIRS = [
    ("How many patients do we have?", "SELECT COUNT(*) AS total_patients FROM patients"),
    (
        "List all patients with their city and gender",
        "SELECT first_name, last_name, city, gender FROM patients ORDER BY last_name",
    ),
    (
        "How many patients are from each city?",
        "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC",
    ),
    (
        "Which city has the most patients?",
        "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1",
    ),
    (
        "How many male and female patients do we have?",
        "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender",
    ),
    (
        "List all doctors and their specializations",
        "SELECT name, specialization, department FROM doctors ORDER BY specialization",
    ),
    (
        "Which doctor has the most appointments?",
        "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON a.doctor_id = d.id GROUP BY d.name ORDER BY appointment_count DESC LIMIT 1",
    ),
    (
        "Show appointment count per doctor",
        "SELECT d.name, d.specialization, COUNT(a.id) AS total FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id GROUP BY d.id ORDER BY total DESC",
    ),
    (
        "How many appointments are there by status?",
        "SELECT status, COUNT(*) AS count FROM appointments GROUP BY status",
    ),
    (
        "Show appointments for the last 30 days",
        "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE a.appointment_date >= DATE('now','-30 days') ORDER BY a.appointment_date DESC",
    ),
    (
        "Show monthly appointment count for the past 6 months",
        "SELECT STRFTIME('%Y-%m', appointment_date) AS month, COUNT(*) AS count FROM appointments WHERE appointment_date >= DATE('now','-6 months') GROUP BY month ORDER BY month",
    ),
    ("What is the total revenue?", "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'"),
    (
        "Show revenue by doctor",
        "SELECT d.name, SUM(i.total_amount) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC",
    ),
    (
        "Show unpaid invoices",
        "SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.status, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Pending','Overdue') ORDER BY i.invoice_date",
    ),
    (
        "Show patient registration trend by month",
        "SELECT STRFTIME('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month",
    ),
    (
        "Top 5 patients by total spending",
        "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending FROM invoices i JOIN patients p ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5",
    ),
    (
        "Average treatment cost by specialization",
        "SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.specialization ORDER BY avg_cost DESC",
    ),
]


async def _seed_memory() -> None:
    try:
        existing = getattr(memory, "_memories", None)
        if isinstance(existing, list) and len(existing) > 0:
            return
    except Exception:
        pass

    ctx = ToolContext(
        user=User(id="seed_user", name="Seeder"),
        conversation_id="seed_conversation",
        request_id="seed:init",
        agent_memory=memory,
        metadata={"source": "vanna_setup.py"},
    )

    for q, sql in _SEED_PAIRS:
        await memory.save_tool_usage(
            question=q,
            tool_name="run_sql",
            args={"sql": sql},
            context=ctx,
            success=True,
            metadata={"seed": True},
        )


if (os.environ.get("AUTO_SEED_MEMORY") or "1").strip().lower() in ("1", "true", "yes"):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Avoid creating an un-awaited coroutine during import in environments with a running loop.
            pass
        else:
            asyncio.run(_seed_memory())
    except RuntimeError:
        asyncio.run(_seed_memory())

