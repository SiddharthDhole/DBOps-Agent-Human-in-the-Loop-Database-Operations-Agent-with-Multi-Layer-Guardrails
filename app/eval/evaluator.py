from typing import Any


def extract_final_answer(result: dict[str, Any]) -> str:
    """
    Extract the final assistant response from LangGraph result.
    """

    messages = result.get("messages", [])

    if not messages:
        return ""

    return str(messages[-1].content)


def evaluate_answer(
    answer: str,
    expected_contains: list[str],
) -> bool:
    """
    Check whether expected values appear in the final answer,
    accounting for punctuation and number formatting (e.g. 136,000 vs 136000).
    """

    normalized_answer = answer.lower()
    cleaned_answer = normalized_answer.replace(",", "")

    return all(
        str(expected).lower() in normalized_answer
        or str(expected).lower().replace(",", "") in cleaned_answer
        for expected in expected_contains
    )


def evaluate_test_case(
    test_case: dict,
    result: dict,
) -> dict:

    answer = extract_final_answer(result)

    answer_passed = evaluate_answer(
        answer,
        test_case["expected_contains"],
    )

    return {
        "id": test_case["id"],
        "question": test_case["question"],
        "answer": answer,
        "answer_passed": answer_passed,
        "passed": answer_passed,
    }