"""PII redaction (for logs/audit) and prompt-injection screening (for ingested documents)."""
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+?213|0)[\s.-]?[5-7](?:[\s.-]?\d){8}(?!\d)")
_LONG_ID = re.compile(r"(?<!\d)\d{12,}(?!\d)")  # e.g. 18-digit Algerian national ID, card numbers

_INJECTION = [
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)",
    r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|system)\s+(instructions|prompts?|rules)",
    r"(reveal|print|show|repeat)\s+(your\s+|the\s+)?(system\s+)?(prompt|instructions)",
    r"you\s+are\s+now\s+(?!a\s+student)",
    r"ignore[zr]?\s+(toutes\s+)?les\s+(instructions|consignes)\s+(précédentes|ci-dessus)?",
    r"oublie[zr]?\s+(toutes\s+)?les\s+(instructions|consignes)",
    r"تجاهل\s+(كل\s+)?(التعليمات|الأوامر)",
    r"انس\s+(كل\s+)?(التعليمات|الأوامر)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION), re.IGNORECASE)


def redact(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    return _LONG_ID.sub("[id]", text)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))
