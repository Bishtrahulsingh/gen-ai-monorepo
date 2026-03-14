import asyncio
from typing import List

from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client.fastembed_common import QueryResponse

rerankerfunc = None

def reranker(chunks:QueryResponse, query:str, top_k:int=5):
    extracted_chunks = chunks.model_dump()['points']
    texts: List[str] = []
    for chunk in extracted_chunks:
        texts.append(chunk['payload']['text'])

    global rerankerfunc
    if not rerankerfunc:
        rerankerfunc=TextCrossEncoder('jinaai/jina-reranker-v1-turbo-en')

    ranks = list(rerankerfunc.rerank(query,texts))
    top_K_res = [chunk for chunk,rank in sorted(zip(extracted_chunks, ranks),key=lambda x:x[1],reverse=True)][:top_k]

    return top_K_res

async def async_reranker(chunks:QueryResponse, query:str, top_k:int=5):
    return await asyncio.to_thread(reranker,chunks,query,top_k)