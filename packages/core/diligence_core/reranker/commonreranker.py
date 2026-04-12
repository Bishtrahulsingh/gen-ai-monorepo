import asyncio
from typing import List

from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client.fastembed_common import QueryResponse

_reranker_model: TextCrossEncoder | None = None


def _get_reranker() -> TextCrossEncoder:
    global _reranker_model
    if _reranker_model is None:
        _reranker_model = TextCrossEncoder(
            'Xenova/ms-marco-MiniLM-L-6-v2',
            threads=2,
            batch_size=32,
        )
    return _reranker_model


def _sandwich(items: list) -> list:
    result = [None] * len(items)
    left, right = 0, len(items) - 1
    for i, item in enumerate(items):
        if i % 2 == 0:
            result[left] = item
            left += 1
        else:
            result[right] = item
            right -= 1
    return result


def reranker(chunks: QueryResponse, query: str, top_k: int = 5) -> List[dict]:
    points = chunks.points

    if not points:
        return []

    points = points[:12]

    texts: List[str] = [p.payload['text'] for p in points]
    scores = list(_get_reranker().rerank(query, texts, batch_size=32))

    ranked = sorted(zip(points, scores), key=lambda x: x[1], reverse=True)
    top = [point.payload for point, score in ranked][:top_k]

    return _sandwich(top)


async def async_reranker(chunks: QueryResponse, query: str, top_k: int = 5) -> List[dict]:
    return await asyncio.to_thread(reranker, chunks, query, top_k)