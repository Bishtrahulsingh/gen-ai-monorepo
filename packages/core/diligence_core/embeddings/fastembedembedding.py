from typing import List,Dict, Union
import asyncio
from fastembed import TextEmbedding
import numpy as np
import uuid

_query_sem = asyncio.Semaphore(16)
_context_sem = asyncio.Semaphore(2)
_embedding_model = TextEmbedding()

Value = Union[str,int, uuid.UUID,np.ndarray]
Chunk = Dict[str, Value]
Chunks = List[Chunk]

def _embed_text(chunks:Chunks,batch_size:int = 32)->Chunks:
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

async def embed_query(query:str)->Chunks:
    if not query:
        return []

    async with _query_sem:
        return await asyncio.to_thread(_embed_text,[{'text':query}])

async def embed_context(chunks:Chunks)->Chunks:
    if not chunks:
        return []

    async with _context_sem:
        return asyncio.to_thread(_embed_text, chunks)
