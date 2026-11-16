import re

from app.security.pii_guard import validate_pii


MAX_INPUT_LENGTH = 1000


BLOCKED_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"forget\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(your|the)\s+prompt",
    r"show\s+(me\s+)?your\s+instructions",
    r"(what|list|show|reveal|identify)\s+(are\s+)?(all\s+)?(your\s+)?(internal\s+)?tools?",
    r"(what|list|show|reveal|identify)\s+(are\s+)?(all\s+)?(your\s+)?functions?",
    r"(what|show|reveal)\s+is\s+your\s+system\s+prompt",
    r"(tell|show|explain)\s+(me\s+)?(your\s+)?internal\s+(implementation|architecture|config)",
    r"(security\s+evaluation|penetration\s+test|audit|red\s+team).*(tools?|functions?|capabilities)",
    r"(tools?|functions?)\s+available\s+to\s+(you|me)",
    r"information-disclosure\s+test",
    r"(identify|list|name)\s+(every|each|all)\s+tool",
]



def validate_input(user_input: str) -> tuple[bool, str]:

    if not user_input:
        return False, "Input cannot be empty."

    user_input = user_input.strip()

    if not user_input:
        return False, "Input cannot be empty."

    if len(user_input) > MAX_INPUT_LENGTH:
        return False, (
            f"Input is too long. "
            f"Maximum length is {MAX_INPUT_LENGTH} characters."
        )

    normalized_input = user_input.lower()

    # Basic prompt-injection checks
    for pattern in BLOCKED_PATTERNS:

        if re.search(pattern, normalized_input):
            return (
                False,
                "Input blocked because it contains "
                "a potentially unsafe instruction."
            )

    # PII checks
    pii_valid, pii_message = validate_pii(user_input)

    if not pii_valid:
        return False, pii_message

    return True, "Input allowed."