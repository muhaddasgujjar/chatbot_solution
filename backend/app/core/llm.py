import re
from typing import List

import httpx

from app.core.config import settings
from app.models.schemas import SourceChunk

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),  # simple card pattern
]


def scrub_pii(text: str) -> str:
    scrubbed = text
    for pattern in PII_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed


def _build_prompt(query: str, context_chunks: List[SourceChunk]) -> str:
    context_text = "\n\n".join(
        f"Source: {chunk.source_url}\nRole: {chunk.role_access}\nContent: {chunk.text}"
        for chunk in context_chunks
    )
    return (
        "You are the Oakland University UTS Chatbot. Professional and helpful.\n"
        "Rules:\n"
        "- Answer using only the provided context.\n"
        "- Never invent URLs.\n"
        "- If context is insufficient, ask user to escalate to a human live agent.\n\n"
        f"Context:\n{context_text}\n\n"
        f"User Query:\n{query}"
    )


async def generate_answer(query: str, context_chunks: List[SourceChunk]) -> str:
    if settings.llm_provider.lower() != "groq":
        return "Unsupported provider in Phase 1. Set LLM_PROVIDER=groq."

    if not settings.groq_api_key:
        return "Groq API key is missing. Set GROQ_API_KEY in your .env file."

    prompt = _build_prompt(scrub_pii(query), context_chunks)
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return "Groq authentication failed. Please update GROQ_API_KEY in backend/.env."
            return f"Groq API request failed with status {exc.response.status_code}."
        except httpx.HTTPError:
            return "Could not reach Groq API. Please verify network connectivity and try again."
