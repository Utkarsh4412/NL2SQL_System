from vanna_setup import memory
import asyncio
import inspect
from vanna.core.tool import ToolContext
from vanna.core.user import User


SEEDS = [
    # Patient queries (5)
    (
        "How many patients do we have?",
        "SELECT COUNT(*) AS total_patients FROM patients",
    ),
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
    # Doctor queries (3)
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
    # Appointment queries (3)
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
    # Financial queries (3)
    (
        "What is the total revenue?",
        "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'",
    ),
    (
        "Show revenue by doctor",
        "SELECT d.name, SUM(i.total_amount) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC",
    ),
    (
        "Show unpaid invoices",
        "SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.status, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Pending','Overdue') ORDER BY i.invoice_date",
    ),
    # Time-based queries (3)
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


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _save(question: str, sql: str) -> None:
    if hasattr(memory, "save_question_sql"):
        await _maybe_await(memory.save_question_sql(question=question, sql=sql))
        return
    # Fallback for current Vanna 2.0 DemoAgentMemory API: store a successful `run_sql` tool usage.
    ctx = ToolContext(
        user=User(id="seed_user", name="Seeder"),
        conversation_id="seed_conversation",
        request_id=f"seed:{hash(question)}",
        agent_memory=memory,
        metadata={"source": "seed_memory.py"},
    )
    await _maybe_await(
        memory.save_tool_usage(
        question=question,
        tool_name="run_sql",
        args={"sql": sql},
        context=ctx,
        success=True,
        metadata={"seed": True},
        )
    )


async def main() -> None:
    count = 0
    for i, (q, s) in enumerate(SEEDS, start=1):
        await _save(q, s)
        count += 1
        print(f"[{i:02d}/{len(SEEDS)}] Seeded: {q}")
    print(f"Seeded {count} question-SQL pairs into memory.")


if __name__ == "__main__":
    asyncio.run(main())

