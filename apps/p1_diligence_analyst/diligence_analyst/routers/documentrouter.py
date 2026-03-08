import datetime

from fastapi import APIRouter
import uuid

from diligence_core.chunkingpipeline import read_pdf, create_chunks
from diligence_core.embeddings.embeddinggenerator import embed_context
from diligence_core.vectordb.qdrantConfig import update_or_insert_chunk
from ..schemas import DocumentCreate,DocumentOut

router = APIRouter(prefix='/api/v1',tags=['documents'])

@router.post("/store/document",response_model=DocumentOut)
async def create_document(payload:DocumentCreate):
    source = str(payload.source)
    chunks = await create_chunks(file_path=source, user_id=uuid.uuid4(), document_id=uuid.uuid4(), company_id=payload.company_id)
    context_embeddings = await embed_context(chunks)
    await update_or_insert_chunk('sec_filings',chunks=context_embeddings)

    return DocumentOut(
        id=uuid.uuid4(),
        company_id=payload.company_id,
        title=payload.title,
        doc_type=payload.doc_type,
        source=payload.source,
        created_at = datetime.datetime.utcnow(),
        updated_at = datetime.datetime.utcnow()
    )