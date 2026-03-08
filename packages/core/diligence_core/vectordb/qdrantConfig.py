import logging
import uuid
from typing import List

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, HnswConfigDiff, OptimizersConfigDiff, PayloadSchemaType, \
    Filter, FieldCondition, MatchValue, PointStruct

from diligence_core.utilities.settings import settings
from diligence_core.embeddings.embeddinggenerator import embed_query
from diligence_core.schemas.chunkschema import ChunkSchema
from diligence_core.schemas.vectordbmetadataschema import MetadataSchema

client = AsyncQdrantClient(
    url="https://4a59a5a1-9827-45a4-9df2-d7584fcbe28f.us-west-1-0.aws.cloud.qdrant.io:6333",
    api_key=settings.QDRANT_API_KEY,
    timeout=60
)

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

async def filter_and_search_chunks(collection_name:str, query:str, company_id):
    if await client.collection_exists(collection_name):
        query_vector = await embed_query(query)
        chunks = await client.query_points(
            collection_name=collection_name,
            query = query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=str(company_id)),
                    )
                ]
            ),
            limit=20
        )

        print("chunks are: ", chunks)
        return chunks
    else:
        print(f"collection not found, {collection_name}")
        raise Exception(f"collection {collection_name} does not exist")

async def update_or_insert_chunk(collection_name:str, chunks:List[ChunkSchema],batch_size:int = 100):
    for idx in range(0,len(chunks),batch_size):
        batch_chunk = chunks[idx:min(len(chunks),idx+batch_size)]
        points = [
            PointStruct(
                id = str(uuid.uuid4()),
                vector=chunk['vector'],
                payload=MetadataSchema(
                    text=chunk['text'],
                    document_id= chunk['document_id'],
                    company_id= chunk['company_id'],
                    part= chunk['part'],
                    item=chunk['item'],
                    heading = chunk['heading'],
                    page_number=chunk['page_number'],
                    chunk_number=chunk['chunk_number'],
                    doc_type=chunk['doc_type'],
                    source_url=chunk['source_url'],
                    filed_at=chunk['filed_at']
                    ).model_dump()
            )
            for chunk in batch_chunk
        ]
        await client.upsert(
            collection_name=collection_name,
            points=points
        )
    logging.info('chunks stored successfully')