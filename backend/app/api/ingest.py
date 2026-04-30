import shutil
import tempfile
from pathlib import Path
from typing import List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.retrieval import upsert_chunks
from app.models.schemas import IngestRequest, IngestResponse, SourceChunk

router = APIRouter(prefix="/ingest", tags=["ingest"])

_ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


# ── URL helpers ──────────────────────────────────────────────────────────────

def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("https",):
        return False
    host = (parsed.hostname or "").lower()
    allowed = [d.strip().lower() for d in settings.allowed_ingest_domains.split(",") if d.strip()]
    return any(host == d or host.endswith(f".{d}") for d in allowed)


def _extract_clean_text(html: str) -> str:
    """Extract main content text from HTML; strips nav/chrome elements."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "header", "footer", "aside", "script", "style", "noscript", "form"]):
        tag.decompose()
    node = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id="content")
        or soup.find(id="main-content")
        or soup.find(id="page-content")
        or soup.find(attrs={"role": "main"})
        or soup.find("div", class_=lambda c: c and any(k in c for k in ("content", "article", "post")))
        or soup.body
    )
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
    seen: set[str] = set()
    queue = [u for u in seed_urls if _is_allowed_url(u)]
    while queue and len(visited) < max_pages:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if not _is_allowed_url(current):
            continue
        try:
            response = requests.get(current, timeout=20, headers={"User-Agent": "OU-KB-Crawler/1.0"})
            response.raise_for_status()
        except requests.RequestException:
            continue
        visited.append(current)
        for discovered in _extract_links(current, response.text):
            if discovered not in seen and _is_allowed_url(discovered):
                queue.append(discovered)
    return visited


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


# ── Document extractors ───────────────────────────────────────────────────────

def _extract_docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise HTTPException(500, "DOCX support requires python-docx.") from exc
    doc = Document(str(path))
    return " ".join(" ".join(p.text.split()) for p in doc.paragraphs if p.text.strip())


def _extract_pdf_text(path: Path) -> str:
    try:
        import pypdf
    except ImportError as exc:
        raise HTTPException(500, "PDF support requires pypdf.") from exc
    reader = pypdf.PdfReader(str(path))
    parts: List[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            parts.append(text.strip())
    return " ".join(" ".join(p.split()) for p in parts)


def _extract_text_from_path(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(400, f"File not found: {file_path}")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    raise HTTPException(400, f"Unsupported file type '{suffix}'. Only .pdf and .docx are accepted.")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=IngestResponse)
def ingest(payload: IngestRequest):
    has_input = bool(payload.urls or payload.docx_paths or payload.pdf_paths)
    if not has_input:
        raise HTTPException(400, "Provide at least one URL, DOCX path, or PDF path.")
    if payload.max_pages > settings.ingest_max_crawl_pages:
        raise HTTPException(400, f"max_pages exceeds limit ({settings.ingest_max_crawl_pages}).")
    if len(payload.docx_paths) > settings.ingest_max_docx_files:
        raise HTTPException(400, f"DOCX batch exceeds limit ({settings.ingest_max_docx_files}).")

    source_chunks: List[SourceChunk] = []

    # ── URL / crawl ──
    urls_to_process = payload.urls
    if payload.crawl and payload.urls:
        urls_to_process = _crawl_allowed_urls(payload.urls, payload.max_pages)

    for url in urls_to_process:
        if not _is_allowed_url(url):
            raise HTTPException(400, f"URL not in allowed domains: {url}")
        response = requests.get(url, timeout=20, headers={"User-Agent": "OU-KB-Crawler/1.0"})
        response.raise_for_status()
        text = _extract_clean_text(response.text)
        for chunk in _chunk_text(text):
            source_chunks.append(SourceChunk(text=chunk, source_url=url, role_access=payload.role_access))

    # ── DOCX paths ──
    ingested_docx: List[str] = []
    for docx_path in payload.docx_paths:
        text = _extract_text_from_path(docx_path)
        resolved = str(Path(docx_path).resolve())
        for chunk in _chunk_text(text):
            source_chunks.append(SourceChunk(text=chunk, source_url=f"file://{resolved}", role_access=payload.role_access))
        ingested_docx.append(resolved)

    # ── PDF paths ──
    ingested_pdf: List[str] = []
    for pdf_path in payload.pdf_paths:
        text = _extract_text_from_path(pdf_path)
        resolved = str(Path(pdf_path).resolve())
        for chunk in _chunk_text(text):
            source_chunks.append(SourceChunk(text=chunk, source_url=f"file://{resolved}", role_access=payload.role_access))
        ingested_pdf.append(resolved)

    count = upsert_chunks(source_chunks)
    return IngestResponse(
        ingested_urls=urls_to_process,
        ingested_docx_paths=ingested_docx,
        ingested_pdf_paths=ingested_pdf,
        chunks_upserted=count,
    )


@router.post("/upload", response_model=IngestResponse)
async def ingest_upload(
    file: UploadFile,
    role_access: str = Form(default="all"),
):
    """Upload a PDF or DOCX file directly from the browser and ingest it into the KB."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(400, f"Only PDF and DOCX uploads are supported (got '{suffix}').")

    # Stream into a temp file to avoid loading all into memory
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir) / (file.filename or f"upload{suffix}")
    try:
        with tmp_path.open("wb") as f:
            total = 0
            while True:
                chunk = await file.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File exceeds 50 MB upload limit.")
                f.write(chunk)

        text = _extract_text_from_path(str(tmp_path))
        source_url = f"upload://{file.filename}"
        chunks = [
            SourceChunk(text=ch, source_url=source_url, role_access=role_access)
            for ch in _chunk_text(text)
        ]
        count = upsert_chunks(chunks)

        field = "ingested_pdf_paths" if suffix == ".pdf" else "ingested_docx_paths"
        return IngestResponse(
            **{field: [file.filename or "upload"]},
            chunks_upserted=count,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
