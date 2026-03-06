from typing import Optional
import datetime
from pydantic import BaseModel, Field, AnyUrl
import uuid

class MetadataSchema(BaseModel):
    text: str
    document_id: uuid.UUID
    company_id: uuid.UUID
    part:Optional[str] = Field(default='Unknown')
    item:Optional[str] = Field(default='Unknown')
    heading:Optional[str] = Field(default='Unknown')
    page_number:int
    chunk_number:int
    doc_type:str
    source_url:AnyUrl
    filed_at:Optional[datetime.datetime] = Field(default_factory=datetime.datetime.now)

