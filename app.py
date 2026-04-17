import json
import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

DEFAULT_API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000").strip() or "http://127.0.0.1:8000"
FALLBACK_API_URL = "http://127.0.0.1:8002"

st.set_page_config(
    page_title="Clinic Analytics — NL2SQL",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "prefill" not in st.session_state:
    st.session_state["prefill"] = None
if "api_url" not in st.session_state:
    st.session_state["api_url"] = DEFAULT_API_URL
if "health" not in st.session_state:
    st.session_state["health"] = None
if "last_health_url" not in st.session_state:
    st.session_state["last_health_url"] = None


def fetch_health(base_url: str) -> dict:
    try:
        r = requests.get(f"{base_url}/health", timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"status": "error"}


def refresh_health(force: bool = False) -> None:
    current_url = st.session_state["api_url"]
    if not force and st.session_state["last_health_url"] == current_url and st.session_state["health"] is not None:
        return

    primary = fetch_health(current_url)
    if primary.get("status") == "ok":
        st.session_state["health"] = primary
        st.session_state["last_health_url"] = current_url
        return

    # Reviewer-friendly fallback if backend is running on the alternate common port.
    if current_url != FALLBACK_API_URL:
        fallback = fetch_health(FALLBACK_API_URL)
        if fallback.get("status") == "ok":
            st.session_state["api_url"] = FALLBACK_API_URL
            st.session_state["health"] = fallback
            st.session_state["last_health_url"] = FALLBACK_API_URL
            return

    st.session_state["health"] = primary
    st.session_state["last_health_url"] = current_url

st.sidebar.header("API Settings")
api_url = st.sidebar.text_input("API URL", value=st.session_state["api_url"])
normalized_api_url = api_url.strip() or DEFAULT_API_URL
api_url_changed = normalized_api_url != st.session_state["api_url"]
st.session_state["api_url"] = normalized_api_url

refresh_health(force=api_url_changed)

if st.sidebar.button("Check connection"):
    refresh_health(force=True)

health = st.session_state.get("health")
if health and health.get("status") == "ok":
    st.sidebar.success("Connected")
    st.sidebar.caption(f"agent_memory_items: {health.get('agent_memory_items', 0)}")
    st.sidebar.caption(f"cache_size: {health.get('cache_size', 0)}")
else:
    st.sidebar.error("Disconnected")

with st.sidebar.expander("Example Questions", expanded=False):
    examples = [
        "How many patients do we have?",
        "Which doctor has the most appointments?",
        "Show revenue by doctor",
        "Top 5 patients by spending",
        "Show monthly appointment count for the past 6 months",
        "What percentage of appointments are no-shows?",
        "Which city has the most patients?",
        "Average treatment cost by specialization",
        "List patients who visited more than 3 times",
        "Compare revenue between departments",
    ]
    for q in examples:
        if st.button(q, key=f"example_{q}"):
            st.session_state["prefill"] = q

if st.sidebar.button("Clear conversation"):
    st.session_state["messages"] = []
    st.session_state["prefill"] = None
    st.rerun()

st.sidebar.info(
    "Ask questions about the clinic database in plain English.\n"
    "The AI generates SQL, validates it, and returns results.\n\n"
    "Stack: FastAPI · Vanna 2.0 · Ollama/Mistral · SQLite · Streamlit"
)

st.markdown(
    """
<style>
.stChatMessage { border-radius: 12px; margin-bottom: 8px; }
.stChatMessage[data-testid="stChatMessageUser"] { background: #EDE9FE; }
.stChatMessage[data-testid="stChatMessageAssistant"] { background: #F8FAFC; }
.metric-box { background: #F1F5F9; border-radius: 8px; padding: 12px; text-align: center; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🏥 Clinic Analytics")
st.caption("Ask anything about your clinic data")


def render_assistant_payload(payload: dict) -> None:
    st.write(payload.get("message", ""))

    sql_query = payload.get("sql_query")
    if sql_query:
        with st.expander("View generated SQL", expanded=False):
            st.code(sql_query, language="sql")

    columns = payload.get("columns")
    rows = payload.get("rows")
    row_count = payload.get("row_count")
    if columns and rows and (row_count or 0) > 0:
        st.write(f"Found {row_count} result(s)")
        df = pd.DataFrame(rows, columns=columns)
        st.dataframe(df, use_container_width=True)
        st.download_button(
            label="Download CSV",
            data=df.to_csv(index=False),
            file_name=f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key=f"download_{datetime.now().timestamp()}",
        )

    chart = payload.get("chart")
    if chart and chart.get("data") is not None:
        try:
            fig = go.Figure(data=chart.get("data"), layout=chart.get("layout"))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    st.caption(
        f"Cached: {'Yes' if payload.get('cached') else 'No'} | "
        f"Time: {payload.get('duration_ms', 0):.0f}ms"
    )

    if payload.get("row_count") == 0 or not payload.get("rows"):
        st.info("No data found for this query.")


for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        if m["role"] == "assistant" and m.get("data"):
            render_assistant_payload(m["data"])
        else:
            st.write(m["content"])

prefill = st.session_state.get("prefill")
if prefill:
    st.info(f"Selected example: {prefill}")

chat_text = st.chat_input("Ask a question about your clinic data...")
question = None
if prefill:
    question = prefill
    st.session_state["prefill"] = None
elif chat_text:
    question = chat_text

if question:
    st.session_state["messages"].append({"role": "user", "content": question, "data": None})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    f"{st.session_state['api_url']}/chat",
                    json={"question": question},
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    render_assistant_payload(data)
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": data.get("message", ""), "data": data}
                    )
                else:
                    err_text = f"API error {resp.status_code}: {resp.text[:200]}"
                    st.error(err_text)
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": err_text, "data": None}
                    )
            except requests.exceptions.ConnectionError:
                msg = "Cannot connect to API. Make sure the server is running."
                st.error(msg)
                st.session_state["messages"].append(
                    {"role": "assistant", "content": msg, "data": None}
                )
            except requests.exceptions.Timeout:
                msg = "Request timed out after 60 seconds."
                st.error(msg)
                st.session_state["messages"].append(
                    {"role": "assistant", "content": msg, "data": None}
                )
            except Exception as e:
                msg = str(e)
                st.error(msg)
                st.session_state["messages"].append(
                    {"role": "assistant", "content": msg, "data": None}
                )

