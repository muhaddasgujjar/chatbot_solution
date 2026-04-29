from typing import List
from urllib.parse import urljoin, urlparse
from pathlib import Path

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


def _extract_links(base_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url, anchor["href"]).split("#")[0]
        links.append(absolute)
    return links


def _crawl_allowed_urls(seed_urls: List[str], max_pages: int) -> List[str]:
    visited: List[str] = []
    seen = set()
    queue = [url for url in seed_urls if _is_allowed_url(url)]

    while queue and len(visited) < max_pages:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if not _is_allowed_url(current):
            continue
        try:
            response = requests.get(current, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            # Skip crawl failures but continue processing remaining pages.
            continue
        visited.append(current)
        for discovered in _extract_links(current, response.text):
            if discovered not in seen and _is_allowed_url(discovered):
                queue.append(discovered)

    return visited


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


def _extract_docx_text_from_path(docx_path: str) -> str:
    try:
        from docx import Document
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="DOCX ingestion requires python-docx. Install backend requirements.",
        ) from exc

    path = Path(docx_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=400, detail=f"DOCX path does not exist: {docx_path}")
    if path.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail=f"Only .docx files are supported: {docx_path}")

    document = Document(str(path))
    text = " ".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())
    return " ".join(text.split())


@router.post("", response_model=IngestResponse)
def ingest(payload: IngestRequest):
    if not payload.urls and not payload.docx_paths:
        raise HTTPException(status_code=400, detail="Provide at least one URL or DOCX path to ingest.")
    if payload.max_pages > settings.ingest_max_crawl_pages:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Crawl page limit exceeds configured max ({payload.max_pages}). "
                f"Max allowed is {settings.ingest_max_crawl_pages}."
            ),
        )
    if len(payload.docx_paths) > settings.ingest_max_docx_files:
        raise HTTPException(
            status_code=400,
            detail=(
                f"DOCX batch exceeds limit ({len(payload.docx_paths)}). "
                f"Max allowed is {settings.ingest_max_docx_files}."
            ),
        )

    source_chunks: List[SourceChunk] = []
    urls_to_process = payload.urls
    if payload.crawl and payload.urls:
        urls_to_process = _crawl_allowed_urls(payload.urls, payload.max_pages)

    for url in urls_to_process:
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

    ingested_docx_paths: List[str] = []
    for docx_path in payload.docx_paths:
        clean_text = _extract_docx_text_from_path(docx_path)
        for chunk in _chunk_text(clean_text):
            source_chunks.append(
                SourceChunk(
                    text=chunk,
                    source_url=f"file://{Path(docx_path).resolve()}",
                    role_access=payload.role_access,
                )
            )
        ingested_docx_paths.append(str(Path(docx_path).resolve()))

    count = upsert_chunks(source_chunks)
    return IngestResponse(
        ingested_urls=urls_to_process,
        ingested_docx_paths=ingested_docx_paths,
        chunks_upserted=count,
    )
