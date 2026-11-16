import os
from typing import Optional


class PricingConfig:
    """
    Configurable LLM token pricing calculator.
    Allows configuring price per 1 Million tokens via environment variables
    or per-model overrides.
    """

    def __init__(
        self,
        default_input_price_per_1m: Optional[float] = None,
        default_output_price_per_1m: Optional[float] = None,
    ):
        # Default pricing from env (e.g. LLM_INPUT_PRICE_PER_1M=0.75, LLM_OUTPUT_PRICE_PER_1M=3.75)
        self.default_input_price_per_1m = float(
            default_input_price_per_1m
            if default_input_price_per_1m is not None
            else os.getenv("LLM_INPUT_PRICE_PER_1M", "0.75")
        )
        self.default_output_price_per_1m = float(
            default_output_price_per_1m
            if default_output_price_per_1m is not None
            else os.getenv("LLM_OUTPUT_PRICE_PER_1M", "3.75")
        )

        # Provider/model-specific rate table (price per 1M tokens)
        self.model_pricing_table = {
            # Gemini models
            "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
            "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
            "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
            "gemini-3.8-flash": {"input": self.default_input_price_per_1m, "output": self.default_output_price_per_1m},
            "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
            # Sarvam models
            "sarvam-105b": {"input": self.default_input_price_per_1m, "output": self.default_output_price_per_1m},
            "sarvam": {"input": self.default_input_price_per_1m, "output": self.default_output_price_per_1m},
            # OpenAI / OpenRouter models
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "openrouter/free": {"input": 0.0, "output": 0.0},
        }

    def get_pricing(self, model_name: str) -> tuple[float, float]:
        """Return (input_price_per_1m, output_price_per_1m) for the model."""
        clean_name = (model_name or "").lower().strip()
        for key, rates in self.model_pricing_table.items():
            if key in clean_name:
                return rates["input"], rates["output"]

        return self.default_input_price_per_1m, self.default_output_price_per_1m

    def calculate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, float]:
        """
        Calculate costs based on input and output token counts.
        """
        input_price_per_1m, output_price_per_1m = self.get_pricing(model_name)

        input_cost = (input_tokens / 1_000_000.0) * input_price_per_1m
        output_cost = (output_tokens / 1_000_000.0) * output_price_per_1m
        total_cost = input_cost + output_cost

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_price_per_1m": input_price_per_1m,
            "output_price_per_1m": output_price_per_1m,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
        }


pricing_config = PricingConfig()
