# DeepEval Test Suite for DBOps Agent

This directory contains the production-ready evaluation suite for the DBOps Agent using the [DeepEval](https://github.com/confident-ai/deepeval) framework.

---

## 📁 Directory Structure

```text
tests/
├── eval_dataset.json      # Curated Golden Dataset (read, write, schema, security attacks)
├── eval_runner.py         # Test execution harness that captures LangGraph trajectory & ToolCalls
├── test_agent_eval.py     # DeepEval test cases & metrics
└── README.md              # Setup and execution guide
```

---

## 🎯 Evaluated Agent Dimensions

1. **SQL Quality (`GEval`):** Evaluates PostgreSQL correctness, schema accuracy, and non-destructive syntax.
2. **Tool Selection (`ToolCallMetric`):** Validates that the agent calls the correct tool (`execute_sql` vs `get_database_schema`).
3. **Security Defense (`GEval`):** Ensures malicious DDL (`DROP TABLE`) and prompt injection attacks are strictly refused.
4. **Human-in-the-Loop Routing:** Verifies that write operations (`INSERT`, `UPDATE`, `DELETE`) trigger the approval interrupt.
5. **Answer Grounding:** Checks that the final user response is faithful to the database rows returned.

---

## ⚙️ How to Plug In Your Judge LLM

DeepEval evaluates test metrics using an LLM-as-a-Judge. You can configure your preferred judge model:

### Option A: Standard OpenAI Judge
Set your API key in `.env` or terminal:
```bash
export OPENAI_API_KEY="your-openai-key"
```

### Option B: Custom LLM Judge
You can pass your own judge model to any DeepEval metric by passing `model="your-model-name"` or a custom `DeepEvalBaseLLM` instance:
```python
from deepeval.models.base_model import DeepEvalBaseLLM

class MyCustomJudge(DeepEvalBaseLLM):
    def __init__(self, model):
        self.model = model

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        return self.model.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        res = await self.model.ainvoke(prompt)
        return res.content

    def get_model_name(self):
        return "my-judge-model"

# Pass to metric:
# sql_quality_metric = GEval(..., model=MyCustomJudge(...))
```

---

## 🚀 Running the Evaluations

### 1. Run with DeepEval CLI (Interactive tabular report)
```bash
uv run deepeval test run tests/test_agent_eval.py
```

### 2. Run with Pytest
```bash
uv run pytest tests/test_agent_eval.py -v
```

### 3. (Optional) Sync with Confident AI Web Dashboard
To view live charts and test histories in your browser:
```bash
uv run deepeval login
```
