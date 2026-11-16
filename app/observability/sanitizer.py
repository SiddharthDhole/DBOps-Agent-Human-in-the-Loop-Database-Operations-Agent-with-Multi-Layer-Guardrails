import re
from typing import Any

# Regular expression patterns for sensitive data redaction
_SECRET_PATTERNS = [
    # Database connection URIs (e.g., postgresql://user:pass@host:port/dbname)
    (re.compile(r'(postgres(?:ql)?:\/\/[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1[REDACTED_PASSWORD]\3'),
    # Generic password patterns in query strings or JSON
    (re.compile(r'((?:password|passwd|pwd|secret|api_key|apikey|access_token|auth_token)\s*[:=]\s*["\']?)([^"\'\s&,]+)(["\']?)', re.IGNORECASE), r'\1[REDACTED]\3'),
    # Bearer tokens
    (re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]{15,}', re.IGNORECASE), r'\1[REDACTED_TOKEN]'),
    # OpenAI/OpenRouter-style API keys (sk-...)
    (re.compile(r'sk-[a-zA-Z0-9_\-]{20,}'), '[REDACTED_API_KEY]'),
    # Google API keys (AIza...)
    (re.compile(r'AIza[0-9A-Za-z-_]{35}'), '[REDACTED_API_KEY]'),
]


def sanitize_text(text: str) -> str:
    """
    Sanitize sensitive information (passwords, API keys, database credentials)
    from log text.
    """
    if not text:
        return ""
    
    sanitized = str(text)
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_data(data: Any) -> Any:
    """
    Recursively sanitize dictionaries, lists, or strings.
    """
    if isinstance(data, str):
        return sanitize_text(data)
    elif isinstance(data, dict):
        clean_dict = {}
        for k, v in data.items():
            if any(term in str(k).lower() for term in ["password", "secret", "token", "api_key", "apikey"]):
                clean_dict[k] = "[REDACTED]"
            else:
                clean_dict[k] = sanitize_data(v)
        return clean_dict
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data
