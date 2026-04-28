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
    query_vector = _embed([query])[0]

    results = _collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        where={"role_access": {"$in": [role, "all"]}},
    )

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
    return response
