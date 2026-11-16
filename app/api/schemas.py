from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="Natural language question or database command")
    thread_id: Optional[str] = Field(None, description="Optional thread session ID. Generated if not provided.")


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    approval_required: bool = False
    pending_sql: Optional[str] = None
    messages: list[dict[str, Any]] = []


class ApprovalRequest(BaseModel):
    thread_id: str = Field(..., description="Thread session ID requiring approval")
    decision: str = Field(..., description="'approved' (yes) or 'rejected' (no)")


class ApprovalResponse(BaseModel):
    thread_id: str
    status: str
    answer: str


class HealthResponse(BaseModel):
    status: str
    database: str
    checkpointer: str
