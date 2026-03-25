from typing import List,Dict, Union
from fastembed import TextEmbedding
import numpy as np
import uuid
import asyncio
from google import genai

from diligence_core.eval_system.observability.tracer import Tracer

_query_sem = asyncio.Semaphore(16)
_context_sem = asyncio.Semaphore(2)
_embedding_model = TextEmbedding()

Value = Union[str,int, uuid.UUID,np.ndarray]
Chunk = Dict[str, Value]
Chunks = List[Chunk]

tracer = Tracer()

async def _embed_text(chunks:Chunks,batch_size:int = 100)->Chunks:
    out = []
    texts = []
    for chunk in chunks:
        texts.append(chunk['text'])

    for i in range(0,len(texts),batch_size):
        current_chunk = texts[i:min(i+batch_size,len(texts))]
        out.extend(list(_embedding_model.embed(current_chunk)))

    for i,vector in enumerate(out):
        chunks[i]['vector'] = np.array(vector,dtype=np.float32)
    return chunks

async def embed_query(query:str):
    if not query:
        return []

    async with _query_sem:
        qv = await _embed_text([{'text':query}])
        return qv[0]['vector']

async def embed_context(chunks:Chunks)->Chunks:
    with tracer.start_observation(name="embed_context",observation_type="embedding"):
        if not chunks:
            return []

        async with _context_sem:
            return await _embed_text(chunks)
