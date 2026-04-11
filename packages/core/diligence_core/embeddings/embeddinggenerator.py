from typing import List, Dict, Union
from fastembed import TextEmbedding
import numpy as np
import uuid
import asyncio

from diligence_core.eval_system.observability.tracer import Tracer

# _query_sem: allow up to 16 concurrent query embeddings (lightweight, single text)
# _context_sem: allow only 1 concurrent context embedding job at a time.
#   Previously set to 2, which allowed two full chunk batches in RAM simultaneously.
#   On Railway free tier (512 MB) this caused OOM crashes during document ingestion.
_query_sem = asyncio.Semaphore(16)
_context_sem = asyncio.Semaphore(1)

_embedding_model = TextEmbedding()

Value = Union[str, int, uuid.UUID, np.ndarray]
Chunk = Dict[str, Value]
Chunks = List[Chunk]

tracer = Tracer()


async def _embed_text(chunks: Chunks, batch_size: int = 16) -> Chunks:
    out = []
    texts = [chunk['text'] for chunk in chunks]

    for i in range(0, len(texts), batch_size):
        current_batch = texts[i: min(i + batch_size, len(texts))]
        out.extend(list(_embedding_model.embed(current_batch)))

    for i, vector in enumerate(out):
        chunks[i]['vector'] = np.array(vector, dtype=np.float32)

    return chunks


async def embed_query(query: str):
    if not query:
        return []

    async with _query_sem:
        qv = await _embed_text([{'text': query}], batch_size=1)
        return qv[0]['vector']


async def embed_context(chunks: Chunks) -> Chunks:
    with tracer.start_observation(name="embed_context", observation_type="embedding"):
        if not chunks:
            return []

        async with _context_sem:
            return await _embed_text(chunks, batch_size=16)