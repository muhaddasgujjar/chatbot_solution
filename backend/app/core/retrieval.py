import re
from typing import List

import chromadb
from chromadb.api.models.Collection import Collection
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.models.schemas import SourceChunk

_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
_chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
_collection: Collection = _chroma_client.get_or_create_collection(name="ou_docs")


def _embed(texts: List[str]) -> List[List[float]]:
    return _embedding_model.encode(texts).tolist()


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(token) >= 3}


def _score_chunk(query: str, chunk: SourceChunk) -> float:
    query_tokens = _tokenize(query)
    chunk_tokens = _tokenize(chunk.text)
    source_tokens = _tokenize(chunk.source_url)
    if query_tokens:
        overlap = len(query_tokens.intersection(chunk_tokens)) / len(query_tokens)
        source_overlap = len(query_tokens.intersection(source_tokens)) / len(query_tokens)
    else:
        overlap = 0.0
        source_overlap = 0.0

    length = len(chunk.text)
    length_penalty = 0.0
    if length < 120:
        length_penalty = settings.rerank_short_chunk_penalty
    elif length > 2200:
        length_penalty = settings.rerank_long_chunk_penalty

    rerank_score = (
        (settings.rerank_semantic_weight * chunk.score)
        + (settings.rerank_keyword_weight * overlap)
        + (settings.rerank_source_url_weight * source_overlap)
        - length_penalty
    )
    return max(rerank_score, 0.0)


def rerank_chunks(query: str, chunks: List[SourceChunk], top_k: int) -> List[SourceChunk]:
    scored = [(chunk, _score_chunk(query, chunk)) for chunk in chunks]
    scored.sort(key=lambda item: item[1], reverse=True)
    reranked: List[SourceChunk] = []
    for chunk, score in scored[:top_k]:
        reranked.append(
            SourceChunk(
                text=chunk.text,
                source_url=chunk.source_url,
                role_access=chunk.role_access,
                score=score,
            )
        )
    return reranked


def upsert_chunks(chunks: List[SourceChunk]) -> int:
    if not chunks:
        return 0

    documents = [chunk.text for chunk in chunks]
    metadatas = [
        {"source_url": chunk.source_url, "role_access": chunk.role_access} for chunk in chunks
    ]
    ids = [f"chunk-{idx}-{abs(hash(doc))}" for idx, doc in enumerate(documents)]
    embeddings = _embed(documents)

    _collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(chunks)


def retrieve_context(query: str, role: str, top_k: int) -> List[SourceChunk]:
    try:
        count = _collection.count()
    except Exception:
        return []
    if count == 0:
        return []

    query_vector = _embed([query])[0]
    actual_k = min(top_k, count)

    try:
        results = _collection.query(
            query_embeddings=[query_vector],
            n_results=actual_k,
            where={"role_access": {"$in": [role, "all"]}},
        )
    except Exception:
        return []

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    response: List[SourceChunk] = []
    for idx, (doc, meta) in enumerate(zip(docs, metas)):
        distance = distances[idx] if idx < len(distances) else 1.0
        score = 1.0 / (1.0 + max(distance, 0.0))
        response.append(
            SourceChunk(
                text=doc,
                source_url=meta.get("source_url", ""),
                role_access=meta.get("role_access", "all"),
                score=score,
            )
        )
    return rerank_chunks(query, response, top_k)
