import threading
from typing import Dict, Any


class LLMUsageTracker:
    """
    In-memory cumulative tracker for LLM calls across the application lifecycle.
    Thread-safe to support concurrent requests in FastAPI / LangGraph.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.total_calls: int = 0
        self.successful_calls: int = 0
        self.failed_calls: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_tokens: int = 0
        self.total_estimated_cost: float = 0.0
        self.total_latency: float = 0.0

    def record_call(
        self,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
        duration: float,
        is_error: bool = False,
    ) -> None:
        """
        Record a completed or failed LLM invocation.
        """
        with self._lock:
            self.total_calls += 1
            if is_error:
                self.failed_calls += 1
            else:
                self.successful_calls += 1

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_tokens += (input_tokens + output_tokens)
            self.total_estimated_cost += estimated_cost
            self.total_latency += duration

    def get_stats(self) -> Dict[str, Any]:
        """
        Retrieve cumulative metrics snapshot.
        """
        with self._lock:
            avg_latency = (
                (self.total_latency / self.total_calls)
                if self.total_calls > 0
                else 0.0
            )
            return {
                "total_calls": self.total_calls,
                "successful_calls": self.successful_calls,
                "failed_calls": self.failed_calls,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens": self.total_tokens,
                "total_estimated_cost": self.total_estimated_cost,
                "average_latency": avg_latency,
            }

    def reset(self) -> None:
        """
        Reset all cumulative metrics.
        """
        with self._lock:
            self.total_calls = 0
            self.successful_calls = 0
            self.failed_calls = 0
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.total_tokens = 0
            self.total_estimated_cost = 0.0
            self.total_latency = 0.0


# Global singleton instance
llm_usage_tracker = LLMUsageTracker()
