from typing import List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.retrieval import upsert_chunks
from app.models.schemas import IngestRequest, IngestResponse, SourceChunk

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    allowed_domains = [d.strip().lower() for d in settings.allowed_ingest_domains.split(",") if d.strip()]
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _extract_clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("article") or soup.find("div", id="content")
    if not node:
        return ""
    return " ".join(node.get_text(separator=" ", strip=True).split())


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


@router.post("", response_model=IngestResponse)
def ingest(payload: IngestRequest):
    source_chunks: List[SourceChunk] = []
    for url in payload.urls:
        if not _is_allowed_url(url):
            raise HTTPException(status_code=400, detail=f"URL is not allowed: {url}")
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        clean_text = _extract_clean_text(response.text)
        for chunk in _chunk_text(clean_text):
            source_chunks.append(
                SourceChunk(
                    text=chunk,
                    source_url=url,
                    role_access=payload.role_access,
                )
            )

    count = upsert_chunks(source_chunks)
    return IngestResponse(ingested_urls=payload.urls, chunks_upserted=count)
