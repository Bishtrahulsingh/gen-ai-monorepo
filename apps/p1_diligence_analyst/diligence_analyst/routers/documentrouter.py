import datetime

from fastapi import APIRouter
import uuid

from diligence_core.chunkingpipeline import read_pdf, create_chunks
from diligence_core.embeddings.fastembedembedding import embed_context
from ..schemas import DocumentCreate,DocumentOut

router = APIRouter(prefix='/api/v1',tags=['documents'])

@router.post("/document",response_model=DocumentOut)
async def create_document(payload:DocumentCreate):
    source = "sample.pdf"
    pages_list = read_pdf(source)
    chunks = create_chunks(pages_list = pages_list, user_id=uuid.uuid4(), doc_id=uuid.uuid4(), org_id=uuid.uuid4(), case_id=uuid.uuid4())
    context_embeddings = await embed_context(chunks)
    print(context_embeddings)

    return DocumentOut(
        id=uuid.uuid4(),
        company_id=payload.company_id,
        title=payload.title,
        doc_type=payload.doc_type,
        source=payload.source,
        created_at = datetime.datetime.utcnow(),
        updated_at = datetime.datetime.utcnow()
    )