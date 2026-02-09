import datetime

from fastapi import APIRouter
import uuid
from ..schemas import DocumentCreate,DocumentOut

router = APIRouter(prefix='/api/v1',tags=['documents'])

@router.post("/document",response_model=DocumentOut)
async def create_document(payload:DocumentCreate):
    return DocumentOut(
        id=uuid.uuid4(),
        company_id=payload.company_id,
        title=payload.title,
        doc_type=payload.doc_type,
        source=payload.source,
        created_at = datetime.datetime.utcnow(),
        updated_at = datetime.datetime.utcnow()
    )