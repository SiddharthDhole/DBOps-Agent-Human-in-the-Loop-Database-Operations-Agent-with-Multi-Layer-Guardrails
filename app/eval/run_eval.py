import uuid

from langchain_core.messages import HumanMessage

from app.graph import graph
from app.security.sql_guard import validate_sql
from app.security.input_guard import validate_input
from app.security.output_guard import validate_output
from .test_cases import (
    TEST_CASES,
    SAFETY_TEST_CASES,
    INPUT_GUARDRAIL_TEST_CASES,
    OUTPUT_GUARDRAIL_TEST_CASES,
)
from .evaluator import evaluate_test_case


def run_evaluation():

    results = []

    for test_case in TEST_CASES:

        thread_id = f"eval-{uuid.uuid4()}"

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        try:

            result = graph.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content=test_case["question"]
                        )
                    ],
                    "retry_count": 0,
                },
                config=config,
            )

            evaluation = evaluate_test_case(
                test_case,
                result,
            )

        except Exception as exc:

            evaluation = {
                "id": test_case["id"],
                "question": test_case["question"],
                "answer": "",
                "answer_passed": False,
                "passed": False,
                "error": str(exc),
            }

        results.append(evaluation)

    return results


def run_safety_evaluation():

    passed = 0

    for test in SAFETY_TEST_CASES:

        allowed, _ = validate_sql(test["query"])

        success = allowed == test["should_allow"]

        if success:
            passed += 1

        status = "PASS" if success else "FAIL"

        print(
            f"[{status}] "
            f"{test['query']}"
        )

    print(
        f"\nSafety: "
        f"{passed}/{len(SAFETY_TEST_CASES)}"
    )

    return passed, len(SAFETY_TEST_CASES)


def run_input_guardrail_evaluation():

    passed = 0

    for test in INPUT_GUARDRAIL_TEST_CASES:

        allowed, message = validate_input(test["input"])

        success = allowed == test["should_allow"]

        if success:
            passed += 1

        status = "PASS" if success else "FAIL"

        preview = test["input"] if len(test["input"]) <= 50 else test["input"][:47] + "..."
        preview = preview.replace("\n", " ")

        print(
            f"[{status}] [{test['category']}] "
            f"{preview} -> {message}"
        )

    print(
        f"\nInput Guardrail: "
        f"{passed}/{len(INPUT_GUARDRAIL_TEST_CASES)}"
    )

    return passed, len(INPUT_GUARDRAIL_TEST_CASES)


def run_output_guardrail_evaluation():

    passed = 0

    for test in OUTPUT_GUARDRAIL_TEST_CASES:

        allowed, message = validate_output(test["output"])

        success = allowed == test["should_allow"]

        if success:
            passed += 1

        status = "PASS" if success else "FAIL"

        preview = test["output"] if len(test["output"]) <= 50 else test["output"][:47] + "..."
        preview = preview.replace("\n", " ")

        print(
            f"[{status}] [{test['category']}] "
            f"{preview} -> {message}"
        )

    print(
        f"\nOutput Guardrail: "
        f"{passed}/{len(OUTPUT_GUARDRAIL_TEST_CASES)}"
    )

    return passed, len(OUTPUT_GUARDRAIL_TEST_CASES)


if __name__ == "__main__":

    print("\n========== Input Guardrail Evaluation ==========\n")
    run_input_guardrail_evaluation()

    print("\n========== Output Guardrail Evaluation ==========\n")
    run_output_guardrail_evaluation()

    print("\n========== Safety (SQL Guard) Evaluation ==========\n")
    run_safety_evaluation()

    # print("\n========== DBOps Agent End-to-End Evaluation ==========\n")
    # results = run_evaluation()

    # passed = 0

    # for result in results:

    #     status = "PASS" if result["passed"] else "FAIL"

    #     if result["passed"]:
    #         passed += 1

    #     print(f"[{status}] {result['id']}")
    #     print(f"Question: {result['question']}")
    #     print(f"Answer:   {result['answer']}")

    #     if result.get("error"):
    #         print(f"Error:    {result['error']}")

    #     print()

    # total = len(results)

    # print("--------------------------------------------")
    # print(f"Passed: {passed}/{total}")
    # print(f"Score:  {(passed / total) * 100:.1f}%")