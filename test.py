import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

api_key = os.getenv("SARVAM_API_KEY")

if not api_key:
    raise ValueError("SARVAM_API_KEY is not set")

llm = ChatOpenAI(
    model="sarvam-105b",
    api_key=api_key,
    base_url="https://api.sarvam.ai/v1",
    max_retries=0,
)

response = llm.invoke(
    "Hello! Explain what an AI agent is in two simple sentences."
)

print("\n--- Sarvam Response ---")
print(response.content)

print("\n--- Usage Metadata ---")
print(response.usage_metadata)