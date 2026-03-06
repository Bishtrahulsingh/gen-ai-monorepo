import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, HnswConfigDiff, OptimizersConfigDiff, PayloadSchemaType, \
    Filter, FieldCondition, MatchValue, PointStruct

from diligence_core.schemas.vectordbmetadataschema import MetadataSchema

client = AsyncQdrantClient(":memory:")

async def get_or_create_collection(collection_name:str, dimension:int):
    if not await client.collection_exists(collection_name):
        await client.create_collection(
            collection_name = collection_name,
            vectors_config= VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
            hnsw_config=HnswConfigDiff(
                m=16,
                ef_construct=200,
                full_scan_threshold=10000
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,
                memmap_threshold=50000,
            )
        )

        await client.create_payload_index(
            collection_name = collection_name,
            field_name='company_id',
            field_schema=PayloadSchemaType.KEYWORD
        )
        logging.info(f"collection {collection_name} created successfully")
    else:
        logging.info(f"collection {collection_name} already exists")

    return await client.get_collection(collection_name)

async def create_collection(collection_name: str, dimension:int):
    collection = await get_or_create_collection(collection_name, dimension)
    return collection

async def filter_and_search_chunks(collection_name:str, query_vector:list[float], company_id):
    chunks = await client.query_points(
        collection_name=collection_name,
        query = query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=company_id),
                )
            ]
        )
    )

    print(chunks)
    return chunks

async def update_or_insert_chunk(collection_name, chunks):
    points = [
        PointStruct(
            id = 1,
            vector=chunk,
            payload=MetadataSchema(
                text="",
                document_id= uuid.uuid4(),
                company_id= uuid.uuid4(),
                part= 'unknown',
                item='unknown',
                heading = 'ads',
                page_number=20,
                chunk_number=2,
                doc_type='pdf',
                source_url="https://abc.com"
                ).model_dump()
        )
        for chunk in chunks
    ]
    await client.upsert(
        collection_name=collection_name,
        points=points
    )