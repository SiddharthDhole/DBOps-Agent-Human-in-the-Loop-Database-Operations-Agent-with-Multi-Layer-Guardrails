import re

from app.security.pii_guard import detect_pii


MAX_OUTPUT_LENGTH = 5000


SECRET_PATTERNS = [
    r"(?i)api[_-]?key\s*[:=]\s*\S+",
    r"(?i)secret[_-]?key\s*[:=]\s*\S+",
    r"(?i)access[_-]?token\s*[:=]\s*\S+",
    r"(?i)password\s*[:=]\s*\S+",
    r"(?i)authorization\s*[:=]\s*bearer\s+\S+",
]


DATABASE_URL_PATTERNS = [
    r"postgresql://[^\s]+",
    r"postgres://[^\s]+",
    r"mysql://[^\s]+",
    r"mongodb(?:\+srv)?://[^\s]+",
]


DANGEROUS_SQL_PATTERNS = [
    r"(?i)\bdrop\s+table\b",
    r"(?i)\bdrop\s+database\b",
    r"(?i)\btruncate\s+table\b",
    r"(?i)\bdelete\s+from\b",
    r"(?i)\bupdate\s+\w+\s+set\b",
]


INTERNAL_TOOL_PATTERNS = [
    r"(?i)\bexecute_sql\b",
    r"(?i)\bget_database_schema\b",
    r"(?i)\bexecute_write_sql\b",
]


def contains_internal_tool_leak(text: str) -> bool:
    return any(
        re.search(pattern, text)
        for pattern in INTERNAL_TOOL_PATTERNS
    )


def contains_secret(text: str) -> bool:


    return any(
        re.search(pattern, text)
        for pattern in SECRET_PATTERNS
    )


def contains_database_url(text: str) -> bool:

    return any(
        re.search(pattern, text)
        for pattern in DATABASE_URL_PATTERNS
    )


def contains_dangerous_sql(text: str) -> bool:

    return any(
        re.search(pattern, text)
        for pattern in DANGEROUS_SQL_PATTERNS
    )


def validate_output(text: str) -> tuple[bool, str]:

    if not text:
        return False, "Agent returned an empty response."

    text = text.strip()

    if not text:
        return False, "Agent returned an empty response."

    if len(text) > MAX_OUTPUT_LENGTH:
        return False, (
            f"Agent response is too long. "
            f"Maximum length is {MAX_OUTPUT_LENGTH} characters."
        )

    if contains_secret(text):
        return False, (
            "Output blocked because it contains "
            "potentially sensitive credentials."
        )

    if contains_database_url(text):
        return False, (
            "Output blocked because it contains "
            "a database connection string."
        )

    if contains_dangerous_sql(text):
        return False, (
            "Output blocked because it contains "
            "potentially dangerous SQL."
        )

    if contains_internal_tool_leak(text):
        return False, (
            "Output blocked because it references "
            "internal tool names or system implementation details."
        )

    pii_entities = detect_pii(text)

    if pii_entities:
        return False, (
            "Output blocked because it contains "
            f"sensitive information: {', '.join(pii_entities)}"
        )

    return True, "Output allowed."