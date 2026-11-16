import asyncio
from typing import Any, Optional
from langchain_core.callbacks import BaseCallbackHandler


import re

_REASONING_REPLACEMENTS = [
    (re.compile(r'\bexecute_sql\b', re.IGNORECASE), '[database_query]'),
    (re.compile(r'\bget_database_schema\b', re.IGNORECASE), '[schema_inspection]'),
    (re.compile(r'\bexecute_write_sql\b', re.IGNORECASE), '[database_write]'),
]


def _sanitize_reasoning(text: str) -> str:
    for pattern, replacement in _REASONING_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


class StreamingCallbackHandler(BaseCallbackHandler):
    """
    Thread-safe streaming callback handler that pushes events into an asyncio.Queue
    for real-time WebSocket broadcasting.
    """

    def __init__(self, queue: asyncio.Queue, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.queue = queue
        self.loop = loop or asyncio.get_event_loop()
        self._is_thinking = False

    def _put_event(self, event_data: dict[str, Any]):
        try:
            if self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.queue.put(event_data), self.loop)
            else:
                self.queue.put_nowait(event_data)
        except Exception:
            pass

    def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
        self._is_thinking = False

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        chunk = kwargs.get("chunk")
        msg = getattr(chunk, "message", None) if chunk else None
        
        # Check for reasoning tokens from reasoning models (Sarvam, DeepSeek)
        reasoning = (
            msg.additional_kwargs.get("reasoning")
            or msg.additional_kwargs.get("reasoning_content")
            if msg and hasattr(msg, "additional_kwargs")
            else None
        )

        # Notify UI that model is thinking without leaking raw internal monologue
        if reasoning and not self._is_thinking:
            self._is_thinking = True
            self._put_event({
                "type": "llm_thinking",
                "status": "thinking",
                "message": "Thinking...",
            })

        if token:
            self._is_thinking = False
            self._put_event({
                "type": "llm_token",
                "token": token,
            })

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        display_map = {
            "execute_sql": "Querying Database",
            "get_database_schema": "Reading Database Schema",
            "execute_write_sql": "Executing Database Write",
        }
        display_title = display_map.get(tool_name, "Processing Database Operation")
        self._put_event({
            "type": "tool_start",
            "tool": display_title,
            "input": input_str,
            "message": f"{display_title}...",
        })


    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        output_str = str(output)
        self._put_event({
            "type": "tool_end",
            "output": output_str,
            "message": "Tool execution completed.",
        })

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._put_event({
            "type": "tool_error",
            "error": str(error),
            "message": f"Tool execution failed: {str(error)}",
        })
