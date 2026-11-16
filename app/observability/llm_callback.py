import datetime
import json
import logging
import sys
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import LLMResult

from app.observability.pricing import PricingConfig, pricing_config
from app.observability.sanitizer import sanitize_data, sanitize_text
from app.observability.usage_tracker import LLMUsageTracker, llm_usage_tracker

logger = logging.getLogger("dbops-agent.llm")


def _safe_print(text: str) -> None:
    """Print text safely across different OS terminal encodings (e.g. Windows cp1252)."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        clean_text = text.encode(encoding, errors="replace").decode(encoding)
        print(clean_text)


class LLMUsageCallback(BaseCallbackHandler):
    """
    Reusable LangChain Callback Handler to log complete usage information
    for every LLM invocation across LangGraph nodes and standalone calls.

    Captures:
    - Model name, latency, timestamps
    - System prompt, user message, conversation history, tool definitions
    - Full input context sent to provider (sanitized)
    - Output content and tool calls
    - Token counts from provider metadata (Gemini, OpenAI, Sarvam, Groq, Ollama)
    - Configurable cost estimation
    - Cumulative application statistics
    - Correlated run_id and llm_call_id
    """

    def __init__(
        self,
        pricing: Optional[PricingConfig] = None,
        tracker: Optional[LLMUsageTracker] = None,
        print_to_console: bool = True,
        log_to_logger: bool = False,
    ):
        super().__init__()
        self.pricing = pricing or pricing_config
        self.tracker = tracker or llm_usage_tracker
        self.print_to_console = print_to_console
        self.log_to_logger = log_to_logger
        self._active_calls: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _extract_model_name(
        self,
        serialized: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Extract the model name from callback arguments."""
        metadata = metadata or {}
        kwargs = kwargs or {}
        invocation_params = kwargs.get("invocation_params") or {}

        # 1. From invocation params
        if "model" in invocation_params:
            return str(invocation_params["model"])
        if "model_name" in invocation_params:
            return str(invocation_params["model_name"])

        # 2. From metadata
        if "ls_model_name" in metadata:
            return str(metadata["ls_model_name"])
        if "model_name" in metadata:
            return str(metadata["model_name"])
        if "model" in metadata:
            return str(metadata["model"])

        # 3. From serialized kwargs or id
        if "kwargs" in serialized and "model" in serialized["kwargs"]:
            return str(serialized["kwargs"]["model"])
        if "id" in serialized and isinstance(serialized["id"], list):
            return str(serialized["id"][-1])

        return serialized.get("name", "unknown-model")

    def _format_tools(self, tools: Any) -> List[str]:
        """Format tool definitions into clean readable summary lines."""
        formatted = []
        if not tools:
            return formatted

        for t in tools:
            if isinstance(t, dict):
                # Standard OpenAI/OpenRouter function schema
                fn = t.get("function", t)
                name = fn.get("name", "tool")
                desc = fn.get("description", "").strip()
                params = fn.get("parameters", {}).get("properties", {})
                param_names = list(params.keys()) if isinstance(params, dict) else []
                formatted.append(f"{name}({', '.join(param_names)}): {desc}")
            elif hasattr(t, "name"):
                desc = getattr(t, "description", "")
                formatted.append(f"{t.name}: {desc}")
            else:
                formatted.append(str(t))

        return formatted

    def _format_message(self, msg: BaseMessage) -> Dict[str, Any]:
        """Convert a BaseMessage into a structured dictionary."""
        role = "unknown"
        if isinstance(msg, SystemMessage):
            role = "system"
        elif isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, ToolMessage):
            role = "tool"
        elif isinstance(msg, FunctionMessage):
            role = "function"
        elif isinstance(msg, ChatMessage):
            role = msg.role
        elif hasattr(msg, "type"):
            role = msg.type

        msg_dict: Dict[str, Any] = {
            "role": role,
            "content": sanitize_text(str(msg.content or "")),
        }

        # Include tool calls if present in AI message
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            msg_dict["tool_calls"] = sanitize_data(msg.tool_calls)

        # Include tool response identifier if ToolMessage
        if isinstance(msg, ToolMessage) and getattr(msg, "tool_call_id", None):
            msg_dict["tool_call_id"] = msg.tool_call_id

        return msg_dict

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Executed before a Chat Model invocation."""
        start_time = time.perf_counter()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        call_id = f"call_{uuid.uuid4().hex[:8]}"

        # Correlate run ID: parent_run_id if in LangGraph node, else metadata or run_id
        agent_run_id = (
            str(parent_run_id)
            if parent_run_id
            else (metadata.get("run_id") if metadata and "run_id" in metadata else str(run_id))
        )

        model_name = self._extract_model_name(serialized, metadata, kwargs)

        # Extract available tools
        invocation_params = kwargs.get("invocation_params") or {}
        raw_tools = invocation_params.get("tools") or kwargs.get("tools") or []
        available_tools = self._format_tools(raw_tools)

        # Process messages
        call_messages = messages[0] if messages and len(messages) > 0 else []
        structured_messages = [self._format_message(m) for m in call_messages]

        system_prompts = [
            m["content"] for m in structured_messages if m["role"] == "system"
        ]
        system_prompt = "\n---\n".join(system_prompts) if system_prompts else None

        user_messages = [
            m["content"] for m in structured_messages if m["role"] == "user"
        ]
        latest_user_message = user_messages[-1] if user_messages else None

        # Previous conversation messages included in request
        conversation_history = []
        if len(structured_messages) > 1:
            conversation_history = structured_messages[:-1]

        with self._lock:
            self._active_calls[str(run_id)] = {
                "llm_call_id": call_id,
                "run_id": agent_run_id,
                "start_time": start_time,
                "timestamp": timestamp,
                "model_name": model_name,
                "available_tools": available_tools,
                "system_prompt": system_prompt,
                "user_message": latest_user_message,
                "messages": structured_messages,
                "conversation_history": conversation_history,
            }

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Executed before a standard LLM completion invocation."""
        start_time = time.perf_counter()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        call_id = f"call_{uuid.uuid4().hex[:8]}"

        agent_run_id = (
            str(parent_run_id)
            if parent_run_id
            else (metadata.get("run_id") if metadata and "run_id" in metadata else str(run_id))
        )
        model_name = self._extract_model_name(serialized, metadata, kwargs)
        sanitized_prompts = [sanitize_text(p) for p in prompts]

        with self._lock:
            self._active_calls[str(run_id)] = {
                "llm_call_id": call_id,
                "run_id": agent_run_id,
                "start_time": start_time,
                "timestamp": timestamp,
                "model_name": model_name,
                "available_tools": [],
                "system_prompt": None,
                "user_message": sanitized_prompts[0] if sanitized_prompts else None,
                "messages": [{"role": "user", "content": p} for p in sanitized_prompts],
                "conversation_history": [],
            }

    def _extract_tokens_and_output(
        self, response: LLMResult
    ) -> tuple[int, int, int, str, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extract token counts (input, output, total), output text, tool calls,
        and reasoning details.
        """
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        output_text = ""
        tool_calls: List[Dict[str, Any]] = []
        token_details: Dict[str, Any] = {}

        if response.generations and len(response.generations) > 0:
            first_gen_batch = response.generations[0]
            if first_gen_batch and len(first_gen_batch) > 0:
                gen = first_gen_batch[0]
                output_text = gen.text or ""

                if hasattr(gen, "message"):
                    msg = gen.message
                    if hasattr(msg, "content") and msg.content:
                        output_text = str(msg.content)

                    # Extract tool calls
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        tool_calls = sanitize_data(msg.tool_calls)

                    # Standard LangChain usage_metadata (AIMessage.usage_metadata)
                    usage_meta = getattr(msg, "usage_metadata", None)
                    if usage_meta and isinstance(usage_meta, dict):
                        input_tokens = usage_meta.get("input_tokens", 0)
                        output_tokens = usage_meta.get("output_tokens", 0)
                        total_tokens = usage_meta.get(
                            "total_tokens", input_tokens + output_tokens
                        )
                        token_details = {
                            "output_details": usage_meta.get("output_token_details", {}),
                            "input_details": usage_meta.get("input_token_details", {}),
                        }

                    # Provider response_metadata (Gemini, Anthropic, vLLM)
                    if (input_tokens == 0 and output_tokens == 0) and hasattr(
                        msg, "response_metadata"
                    ):
                        rm = msg.response_metadata or {}
                        # Gemini style
                        if "usage_metadata" in rm and isinstance(rm["usage_metadata"], dict):
                            um = rm["usage_metadata"]
                            input_tokens = um.get(
                                "prompt_token_count", um.get("input_tokens", 0)
                            )
                            output_tokens = um.get(
                                "candidates_token_count", um.get("output_tokens", 0)
                            )
                            total_tokens = um.get(
                                "total_token_count",
                                um.get("total_tokens", input_tokens + output_tokens),
                            )
                        elif "token_usage" in rm and isinstance(rm["token_usage"], dict):
                            tu = rm["token_usage"]
                            input_tokens = tu.get("prompt_tokens", tu.get("input_tokens", 0))
                            output_tokens = tu.get(
                                "completion_tokens", tu.get("output_tokens", 0)
                            )
                            total_tokens = tu.get(
                                "total_tokens", input_tokens + output_tokens
                            )

        # Fallback: response.llm_output (OpenAI / OpenRouter standard)
        if (input_tokens == 0 and output_tokens == 0) and response.llm_output:
            llm_out = response.llm_output or {}
            token_usage = llm_out.get("token_usage") or llm_out.get("usage") or {}
            if isinstance(token_usage, dict):
                input_tokens = token_usage.get(
                    "prompt_tokens", token_usage.get("input_tokens", 0)
                )
                output_tokens = token_usage.get(
                    "completion_tokens", token_usage.get("output_tokens", 0)
                )
                total_tokens = token_usage.get(
                    "total_tokens", input_tokens + output_tokens
                )

        if total_tokens == 0 and (input_tokens > 0 or output_tokens > 0):
            total_tokens = input_tokens + output_tokens

        return (
            input_tokens,
            output_tokens,
            total_tokens,
            sanitize_text(output_text),
            tool_calls,
            token_details,
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Executed upon successful completion of the LLM invocation."""
        duration = 0.0
        call_info: Dict[str, Any] = {}

        with self._lock:
            call_info = self._active_calls.pop(str(run_id), {})

        start_time = call_info.get("start_time")
        if start_time:
            duration = max(0.001, time.perf_counter() - start_time)

        model_name = call_info.get("model_name", "unknown")
        llm_call_id = call_info.get("llm_call_id", f"call_{uuid.uuid4().hex[:8]}")
        agent_run_id = call_info.get("run_id", str(parent_run_id or run_id))
        timestamp = call_info.get(
            "timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        (
            input_tokens,
            output_tokens,
            total_tokens,
            output_text,
            tool_calls,
            token_details,
        ) = self._extract_tokens_and_output(response)

        # Cost calculation
        cost_info = self.pricing.calculate_cost(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Update cumulative tracker
        self.tracker.record_call(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost_info["total_cost"],
            duration=duration,
            is_error=False,
        )

        cumulative = self.tracker.get_stats()

        # Format and log the readable summary
        self._log_call_summary(
            llm_call_id=llm_call_id,
            run_id=agent_run_id,
            timestamp=timestamp,
            model_name=model_name,
            duration=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_info=cost_info,
            cumulative=cumulative,
            call_info=call_info,
            output_text=output_text,
            tool_calls=tool_calls,
            token_details=token_details,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Executed when an LLM provider returns an error."""
        duration = 0.0
        call_info: Dict[str, Any] = {}

        with self._lock:
            call_info = self._active_calls.pop(str(run_id), {})

        start_time = call_info.get("start_time")
        if start_time:
            duration = max(0.001, time.perf_counter() - start_time)

        model_name = call_info.get("model_name", "unknown")
        llm_call_id = call_info.get("llm_call_id", f"call_{uuid.uuid4().hex[:8]}")
        agent_run_id = call_info.get("run_id", str(parent_run_id or run_id))
        timestamp = call_info.get(
            "timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        self.tracker.record_call(
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            duration=duration,
            is_error=True,
        )

        error_message = sanitize_text(str(error))

        border = "=" * 80
        lines = [
            f"\n{border}",
            f"## LLM CALL FAILED [call_id: {llm_call_id} | run_id: {agent_run_id}]",
            f"Timestamp: {timestamp}",
            f"Model    : {model_name}",
            f"Duration : {duration:.2f}s",
            f"ERROR    : {error_message}",
            f"{border}\n",
        ]
        summary_text = "\n".join(lines)
        if self.print_to_console:
            print(summary_text)
        if self.log_to_logger:
            logger.error(summary_text)

    def _log_call_summary(
        self,
        llm_call_id: str,
        run_id: str,
        timestamp: str,
        model_name: str,
        duration: float,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_info: Dict[str, float],
        cumulative: Dict[str, Any],
        call_info: Dict[str, Any],
        output_text: str,
        tool_calls: List[Dict[str, Any]],
        token_details: Dict[str, Any],
    ) -> None:
        """Generate and display the readable LLM call log."""
        border = "=" * 80

        lines = [
            f"\n{border}",
            f"## LLM CALL [call_id: {llm_call_id} | run_id: {run_id}]",
            f"Timestamp: {timestamp}",
            f"Model    : {model_name}",
            f"Duration : {duration:.2f}s",
            "",
            "INPUT TOKENS : {:,}".format(input_tokens),
            "OUTPUT TOKENS: {:,}".format(output_tokens),
            "TOTAL TOKENS : {:,}".format(total_tokens),
        ]

        # Reasoning details if available
        out_details = token_details.get("output_details", {})
        if out_details and "reasoning" in out_details:
            lines.append(f"  (Reasoning Tokens: {out_details['reasoning']:,})")

        lines.extend([
            "",
            "CUMULATIVE STATS (Current Application Run):",
            f"  Total LLM Calls     : {cumulative['total_calls']}",
            f"  Total Input Tokens  : {cumulative['total_input_tokens']:,}",
            f"  Total Output Tokens : {cumulative['total_output_tokens']:,}",
            f"  Total Tokens        : {cumulative['total_tokens']:,}",
            f"  Total Estimated Cost: ${cumulative['total_estimated_cost']:.6f}",
            f"  Average Latency     : {cumulative['average_latency']:.2f}s",
            border,
            "",
        ])

        output_str = "\n".join(lines)

        if self.print_to_console:
            _safe_print(output_str)

        if self.log_to_logger:
            logger.info(output_str)


# Global default callback instance
llm_usage_callback = LLMUsageCallback()
