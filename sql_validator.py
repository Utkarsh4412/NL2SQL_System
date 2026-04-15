import re
from typing import Tuple


_SELECT_ONLY_RE = re.compile(r"^\s*select\b", re.IGNORECASE)
_MODIFICATION_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|merge)\b", re.IGNORECASE
)
_BANNED_KEYWORDS_RE = re.compile(
    r"\b(exec|execute|grant|revoke|shutdown|call)\b|(?:\bxp_|\bsp_)",
    re.IGNORECASE,
)
_SYSTEM_TABLES_RE = re.compile(
    r"\b(sqlite_master|sqlite_sequence|information_schema|sqlite_stat\w*)\b",
    re.IGNORECASE,
)
_INJECTION_RE = re.compile(r"(--|/\*|\*/|;.*;)", re.DOTALL)


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Returns (is_valid, error_message). True means safe to execute.
    """
    if sql is None:
        return False, "Only SELECT queries are permitted. Modification statements are blocked."

    s = sql.strip()
    if not s:
        return False, "Only SELECT queries are permitted. Modification statements are blocked."

    if not _SELECT_ONLY_RE.match(s):
        return (
            False,
            "Only SELECT queries are permitted. Modification statements are blocked.",
        )

    # Layer 1b: explicit modification keywords anywhere
    m = _MODIFICATION_RE.search(s)
    if m:
        kw = m.group(1).upper()
        return False, f"Blocked keyword detected: '{kw}'. Query rejected for safety."

    # Layer 2: banned keywords
    m = _BANNED_KEYWORDS_RE.search(s)
    if m:
        kw = (m.group(1) or m.group(0)).strip().upper()
        return False, f"Blocked keyword detected: '{kw}'. Query rejected for safety."

    # Layer 3: system tables
    if _SYSTEM_TABLES_RE.search(s):
        return False, "Access to system tables is not permitted."

    # Layer 4: injection patterns
    if _INJECTION_RE.search(s):
        return False, "Potential SQL injection pattern detected. Query rejected."

    return True, ""

