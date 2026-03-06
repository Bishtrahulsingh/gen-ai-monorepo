import datetime

from fastapi import APIRouter
import uuid

from diligence_core.chunkingpipeline import read_pdf, create_chunks
from diligence_core.embeddings.fastembedembedding import embed_context
from ..schemas import DocumentCreate,DocumentOut

router = APIRouter(prefix='/api/v1',tags=['documents'])

@router.post("/document",response_model=DocumentOut)
async def create_document(payload:DocumentCreate):
    source = "https://zgeadpognspjixavxdbd.supabase.co/storage/v1/object/public/docs/Accenture-2024-10-K.pdf"
    chunks = await create_chunks(file_path=source, user_id=uuid.uuid4(), document_id=uuid.uuid4(), company_id=uuid.uuid4())
    for chunk in chunks :
        print(chunk, end="\n\n")
    # context_embeddings = await embed_context(chunks)
    # print(context_embeddings)

    return DocumentOut(
        id=uuid.uuid4(),
        company_id=payload.company_id,
        title=payload.title,
        doc_type=payload.doc_type,
        source=payload.source,
        created_at = datetime.datetime.utcnow(),
        updated_at = datetime.datetime.utcnow()
    )