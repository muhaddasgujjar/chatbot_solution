from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    role: str = Field(default="all")


class SourceChunk(BaseModel):
    text: str
    source_url: str
    role_access: str
    score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    helpful_prompt: str = "[Was this helpful? Y/N]"
    sources: List[str]


class IngestRequest(BaseModel):
    urls: List[str] = Field(default_factory=list)
    docx_paths: List[str] = Field(default_factory=list)
    pdf_paths: List[str] = Field(default_factory=list)
    crawl: bool = False
    max_pages: int = Field(default=1, ge=1, le=2000)
    role_access: str = "all"


class IngestResponse(BaseModel):
    ingested_urls: List[str] = Field(default_factory=list)
    ingested_docx_paths: List[str] = Field(default_factory=list)
    ingested_pdf_paths: List[str] = Field(default_factory=list)
    chunks_upserted: int


class KbStatsResponse(BaseModel):
    total_chunks: int
    by_role: Dict[str, int]
    status: str


class FeedbackRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    helpful: bool


class SessionInitRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(default="all")
    department: str = ""
    job_title: str = ""


class TdxArticleSearchRequest(BaseModel):
    query: str = Field(min_length=1)


class TdxTicketCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    requester_email: str = Field(min_length=3, max_length=320)
    priority: str = Field(default="normal")
    category: str = Field(default="it-support")


class PureChatHandoffRequest(BaseModel):
    user_id: str = Field(min_length=1)
    transcript: List[str] = Field(default_factory=list)


class EntraClaimsRequest(BaseModel):
    user_id: str = Field(min_length=1)
    department: str = ""
    job_title: str = ""
    groups: List[str] = Field(default_factory=list)
