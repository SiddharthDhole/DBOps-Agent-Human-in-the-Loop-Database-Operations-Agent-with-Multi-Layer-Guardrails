# DBOps Agent

An intelligent, safety-first database operations and analytics agent built with **LangGraph**, **LangChain**, and **PostgreSQL**.

---

## Overview

DBOps Agent allows users to query and operate on a relational database in natural language with automated multi-layer security guardrails and Human-in-the-Loop (HITL) approval for write operations.

### Core Features
- **Natural Language to SQL**: Converts analytical questions into valid PostgreSQL queries.
- **Safety & Guardrails**:
  - Input validation: Prompt injection defense & PII screening with Presidio Analyzer.
  - SQL policy enforcement: AST parsing with `sqlglot` to prevent stacked queries and unsafe DDL.
  - Output guardrails: Automatic filtering of secrets, connection URLs, and sensitive credentials.
- **Human-In-The-Loop (HITL)**: Requires explicit human review and approval for modifying queries (`INSERT`, `UPDATE`, `DELETE`).
- **Autonomous Recovery**: Automated query correction and retry loop upon database errors.
- **State Checkpointing**: Persistent conversation threads backed by PostgreSQL (`PostgresSaver`).

---

## Project Structure

```
dbops-agent/
├── app/
│   ├── context/          # Schema context metadata and selection
│   ├── db/               # Database connection and migration scripts
│   ├── eval/             # Evaluation suites (accuracy, guardrails, SQL safety)
│   ├── nodes/            # LangGraph execution nodes and router logic
│   ├── observability/    # Structured event logging and tracing
│   ├── security/         # Input, output, PII, and SQL safety guardrails
│   ├── tools/            # Database execution tools
│   ├── graph.py          # LangGraph state machine definition
│   ├── model.py          # LLM configuration (OpenRouter)
│   ├── prompts.py        # System prompt and operational guidelines
│   └── state.py          # TypedDict state schemas
├── docker-compose.yml    # PostgreSQL container service
├── main.py               # Interactive CLI agent application
├── pyproject.toml        # Project configuration
├── requirements.txt      # Dependency manifest
└── FUTURE_WORK.md        # Comprehensive technical analysis and roadmap
```

---

## Quickstart

### 1. Prerequisites
- Python 3.12+ (or 3.14)
- Docker & Docker Compose (for PostgreSQL)

### 2. Setup Environment
```bash
# Clone and navigate
cd dbops-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Start Database
```bash
docker compose up -d
python -m app.db.migration
```

### 4. Run the Agent

#### Option A: Interactive Web UI & Live WebSocket Server (Recommended)
```bash
python run_server.py
```
- Open **Web UI**: [http://localhost:8000](http://localhost:8000)
- Interactive **Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Live WebSocket**: `ws://localhost:8000/ws/chat/{thread_id}`

#### Option B: Terminal CLI
```bash
python main.py
```


---

## Detailed Technical Analysis & Future Work

For a comprehensive technical assessment, architectural diagrams, identified bugs, and prioritized roadmap, please refer to:
👉 **[FUTURE_WORK.md](FUTURE_WORK.md)**
