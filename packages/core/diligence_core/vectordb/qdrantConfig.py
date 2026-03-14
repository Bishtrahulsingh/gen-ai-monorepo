import logging
import uuid
from typing import List

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, HnswConfigDiff, OptimizersConfigDiff, PayloadSchemaType, \
    Filter, FieldCondition, MatchValue, PointStruct

from diligence_core.reranker.commonreranker import async_reranker
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

        # a single chunk looks like this
        '''
        points=[ScoredPoint(id='95b13768-d2fc-4212-b73c-e360ac40f597', version=18, score=0.814077, payload={'text': 'Consolidated Income Statements\nFor the Years Ended August 31, 2024, 2023 and 2022 \n2024 2023 2022\nREVENUES:\nRevenues $ 64,896,464 $ 64,111,745 $ 61,594,305 \nOPERATING EXPENSES:\nCost of services  43,734,147  43,380,138  41,892,766 \nSales and marketing  6,846,714  6,582,629  6,108,401 \nGeneral and administrative costs  4,281,316  4,275,943  4,225,957 \nBusiness optimization costs  438,440  1,063,146  — \nTotal operating expenses  55,300,617  55,301,856  52,227,124 \nOPERATING INCOME  9,595,847  8,809', 
        'document_id': 'd2b8cea3-5e9d-4502-831d-42fedc197dc7', 'company_id': '3fa85f64-5717-4562-b3fc-2c963f66afa6', 'part': 'Unknown', 'item': 'Unknown', 'heading': 'Unknown', 'page_number': 67, 'chunk_number': 0, 'doc_type': 'pdf', 'source_url': 'https://zgeadpognspjixavxdbd.supabase.co/storage/v1/object/public/docs/Accenture-2024-10-K.pdf#page=67', 'filed_at': '2026-03-08T16:16:10.978433'}, vector=None, shard_key=None, order_value=None)
        '''

        # #perform reranking here to get top n relevant chunks
        top_k_chunks = await  async_reranker(chunks,query,top_k=5)
        print(top_k_chunks)

        return top_k_chunks
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