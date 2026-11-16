import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import langchain_openai.chat_models.base as base_mod

from app.tools import tools
from app.observability import llm_usage_callback

# Enable reasoning extraction for reasoning models (Sarvam, DeepSeek, vLLM)
_orig_convert = base_mod._convert_delta_to_message_chunk

def _reasoning_aware_convert(_dict, default_class):
    chunk = _orig_convert(_dict, default_class)
    reasoning = _dict.get("reasoning") or _dict.get("reasoning_content")
    if reasoning and hasattr(chunk, "additional_kwargs"):
        chunk.additional_kwargs["reasoning"] = reasoning
    return chunk

base_mod._convert_delta_to_message_chunk = _reasoning_aware_convert

load_dotenv()


SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if SARVAM_API_KEY:
    model = ChatOpenAI(
        model="sarvam-105b",
        api_key=SARVAM_API_KEY,
        base_url="https://api.sarvam.ai/v1",
        temperature=0,
        streaming=True,
        max_tokens=4096,
        max_retries=1,
        callbacks=[llm_usage_callback],
    )
elif OPENROUTER_API_KEY:
    model = ChatOpenAI(
        model="openrouter/free",
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        streaming=True,
        max_retries=1,
        callbacks=[llm_usage_callback],
    )
else:
    raise RuntimeError(
        "Neither SARVAM_API_KEY nor OPENROUTER_API_KEY is configured in the environment."
    )


model_with_tools = model.bind_tools(tools)
