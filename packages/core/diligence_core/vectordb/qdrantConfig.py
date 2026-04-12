import asyncio
import logging
import uuid
from typing import List

from fastembed import SparseTextEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    VectorParams, Distance, HnswConfigDiff, OptimizersConfigDiff,
    PayloadSchemaType, Filter, FieldCondition, MatchValue, PointStruct,
    SparseVectorParams, SparseIndexParams, SparseVector
)
from qdrant_client.models import Prefetch, FusionQuery, Fusion

from diligence_core.reranker.commonreranker import async_reranker
from diligence_core.utilities.settings import settings
from diligence_core.embeddings.embeddinggenerator import embed_query
from diligence_core.schemas.chunkschema import ChunkSchema

client = AsyncQdrantClient(
    url="https://4a59a5a1-9827-45a4-9df2-d7584fcbe28f.us-west-1-0.aws.cloud.qdrant.io:6333",
    api_key=settings.QDRANT_API_KEY,
    timeout=60
)

_sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

_known_collections: set = set()


def _encode_sparse(text: str) -> SparseVector:
    result = list(_sparse_model.embed([text]))[0]
    return SparseVector(
        indices=result.indices.tolist(),
        values=result.values.tolist()
    )


def _encode_sparse_batch(texts: List[str]) -> List[SparseVector]:
    results = list(_sparse_model.embed(texts))
    return [
        SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
        for r in results
    ]


async def get_or_create_collection(collection_name: str, dimension: int):
    if not await client.collection_exists(collection_name):
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams()
                )
            },
            hnsw_config=HnswConfigDiff(
                m=16,
                ef_construct=100,
                full_scan_threshold=10000
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,
                memmap_threshold=50000,
            )
        )

        await client.create_payload_index(
            collection_name=collection_name,
            field_name='company_id',
            field_schema=PayloadSchemaType.KEYWORD
        )
        await client.create_payload_index(
            collection_name=collection_name,
            field_name='ticker',
            field_schema=PayloadSchemaType.KEYWORD
        )
        await client.create_payload_index(
            collection_name=collection_name,
            field_name='fiscal_year',
            field_schema=PayloadSchemaType.INTEGER
        )
        logging.info(f"Collection {collection_name} created successfully with all payload indexes")

        _known_collections.add(collection_name)
    else:
        logging.info(f"Collection {collection_name} already exists")
        _known_collections.add(collection_name)

    return await client.get_collection(collection_name)


async def migrate_add_missing_indexes(collection_name: str):
    if not await client.collection_exists(collection_name):
        logging.warning(f"Collection {collection_name} does not exist, skipping migration")
        return

    try:
        await client.create_payload_index(
            collection_name=collection_name,
            field_name='ticker',
            field_schema=PayloadSchemaType.KEYWORD
        )
        logging.info(f"Created 'ticker' index on {collection_name}")
    except Exception as e:
        logging.warning(f"Could not create 'ticker' index (may already exist): {e}")

    try:
        await client.create_payload_index(
            collection_name=collection_name,
            field_name='fiscal_year',
            field_schema=PayloadSchemaType.INTEGER
        )
        logging.info(f"Created 'fiscal_year' index on {collection_name}")
    except Exception as e:
        logging.warning(f"Could not create 'fiscal_year' index (may already exist): {e}")

    logging.info(f"Migration complete for collection: {collection_name}")


async def create_collection(collection_name: str, dimension: int):
    collection = await get_or_create_collection(collection_name, dimension)
    return collection


async def filter_and_search_chunks(
    collection_name: str,
    query: str,
    ticker: str,
    fiscal_year: int
):
    if collection_name not in _known_collections:
        if not await client.collection_exists(collection_name):
            raise Exception(f"Collection {collection_name} does not exist")
        _known_collections.add(collection_name)

    dense_vector, sparse_vector = await asyncio.gather(
        embed_query(query),
        asyncio.to_thread(_encode_sparse, query)
    )

    search_filter = Filter(
        must=[
            FieldCondition(key="ticker", match=MatchValue(value=str(ticker))),
            FieldCondition(key="fiscal_year", match=MatchValue(value=fiscal_year)),
        ]
    )

    chunks = await client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using="dense",
                filter=search_filter,
                limit=25,
            ),
            Prefetch(
                query=sparse_vector,
                using="sparse",
                filter=search_filter,
                limit=25,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=12,
        with_payload=True,
    )

    return chunks


async def update_or_insert_chunk(
    collection_name: str,
    chunks: List[ChunkSchema],
    batch_size: int = 100
):
    for idx in range(0, len(chunks), batch_size):
        batch_chunk = chunks[idx: idx + batch_size]
        sparse_vectors: List[SparseVector] = await asyncio.to_thread(
            _encode_sparse_batch,
            [chunk['text'] for chunk in batch_chunk]
        )

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": chunk['vector'],
                    "sparse": sparse_vectors[i],
                },
                payload={key: chunk[key] for key in dict(chunk) if key != "vector"}
            )
            for i, chunk in enumerate(batch_chunk)
        ]

        await client.upsert(
            collection_name=collection_name,
            points=points
        )

    logging.info("Chunks stored successfully")