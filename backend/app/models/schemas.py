from typing import List

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
    urls: List[str]
    role_access: str = "all"


class IngestResponse(BaseModel):
    ingested_urls: List[str]
    chunks_upserted: int


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


class PureChatHandoffRequest(BaseModel):
    user_id: str = Field(min_length=1)
    transcript: List[str] = Field(default_factory=list)


class EntraClaimsRequest(BaseModel):
    user_id: str = Field(min_length=1)
    department: str = ""
    job_title: str = ""
    groups: List[str] = Field(default_factory=list)
