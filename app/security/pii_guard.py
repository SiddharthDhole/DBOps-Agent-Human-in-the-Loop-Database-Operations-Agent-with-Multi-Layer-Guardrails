from presidio_analyzer import AnalyzerEngine


analyzer = AnalyzerEngine()


BLOCKED_PII_TYPES = {
    "CREDIT_CARD",
    "US_SSN",
    "PHONE_NUMBER",
}


def detect_pii(text: str) -> list[str]:
    """
    Detect sensitive PII in user input.

    Returns a list of detected entity types.
    """

    results = analyzer.analyze(
        text=text,
        language="en",
    )

    return list({
        result.entity_type
        for result in results
        if result.entity_type in BLOCKED_PII_TYPES
    })


def validate_pii(text: str) -> tuple[bool, str]:

    detected = detect_pii(text)

    if detected:
        return (
            False,
            f"Sensitive information detected: {', '.join(detected)}"
        )

    return True, "No blocked PII detected."