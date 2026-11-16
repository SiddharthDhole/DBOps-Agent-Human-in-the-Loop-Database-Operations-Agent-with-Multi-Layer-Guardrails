import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from langchain_core.runnables import RunnableConfig

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ApprovalRequest,
    ApprovalResponse,
    HealthResponse,
)
from app.api.service import (
    run_agent_sync,
    resume_agent_sync,
    stream_agent_session,
    resume_agent_stream,
)
from app.db.connection import db
from app.graph import graph
from app.tools.schema import get_database_schema

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def healthcheck():
    """Healthcheck endpoint verifying DB and checkpointer status."""
    db_status = "connected"
    try:
        conn = db.get_connection()
        conn.close()
    except Exception as exc:
        db_status = f"unhealthy ({exc})"

    checkpointer_type = type(graph.checkpointer).__name__ if hasattr(graph, "checkpointer") else "None"

    return HealthResponse(
        status="ok",
        database=db_status,
        checkpointer=checkpointer_type,
    )


@router.get("/api/schema")
def get_schema():
    """Fetch current database schema, columns, and foreign keys."""
    try:
        config: RunnableConfig = {"configurable": {"db": db}}
        raw_schema = get_database_schema.invoke({}, config=config)
        return {"schema": raw_schema}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """Synchronous REST endpoint for invoking DBOps Agent."""
    thread_id = request.thread_id or str(uuid.uuid4())
    try:
        res = run_agent_sync(request.question, thread_id)
        return ChatResponse(
            thread_id=thread_id,
            answer=res["answer"],
            approval_required=res.get("approval_required", False),
            pending_sql=res.get("pending_sql"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/chat/resume", response_model=ApprovalResponse)
def resume_endpoint(request: ApprovalRequest):
    """Resume execution after human review of a database write."""
    try:
        res = resume_agent_sync(request.thread_id, request.decision)
        return ApprovalResponse(
            thread_id=request.thread_id,
            status=res["status"],
            answer=res["answer"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.websocket("/ws/chat/{thread_id}")
async def websocket_chat(websocket: WebSocket, thread_id: str):
    """
    Bidirectional WebSocket endpoint for live streaming:
    - Real-time LLM tokens
    - Tool execution logs (query start, AST policy, results)
    - Pipeline node transitions
    - Human-in-the-loop interactive approval
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()

    await websocket.send_json({
        "type": "connected",
        "thread_id": thread_id,
        "message": f"Connected to DBOps Agent session [{thread_id}]",
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                question = data.get("content") or data.get("question", "")
                if not question.strip():
                    await websocket.send_json({
                        "type": "error",
                        "error": "Question cannot be empty.",
                    })
                    continue

                event_queue: asyncio.Queue = asyncio.Queue()

                # Launch streaming worker
                worker_task = asyncio.create_task(
                    stream_agent_session(question, thread_id, event_queue, loop)
                )

                # Stream all events to client
                while True:
                    event = await event_queue.get()
                    await websocket.send_json(event)
                    if event.get("type") == "stream_end":
                        break

                await worker_task

            elif msg_type == "approval_response":
                decision = data.get("decision", "rejected")
                event_queue = asyncio.Queue()

                worker_task = asyncio.create_task(
                    resume_agent_stream(decision, thread_id, event_queue, loop)
                )

                while True:
                    event = await event_queue.get()
                    await websocket.send_json(event)
                    if event.get("type") == "stream_end":
                        break

                await worker_task

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(exc),
            })
        except Exception:
            pass
