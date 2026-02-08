import datetime
import uuid

from fastapi import APIRouter

from ..schemas import CompanyOut,CompanyCreate
router = APIRouter(prefix="/api/v1", tags=['company'])

@router.post('/company',response_model=CompanyOut)
def create_company(payload:CompanyCreate):

    return CompanyOut(
        id=uuid.uuid4(),
        name=payload.name,
        website=payload.website,
        industry=payload.industry,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now()
    )