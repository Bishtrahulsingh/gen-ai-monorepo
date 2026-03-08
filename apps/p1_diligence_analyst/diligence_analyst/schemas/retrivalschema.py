import uuid
from pydantic import BaseModel,Field,ConfigDict
from typing import Optional,List

class RetrivalSchema(BaseModel):
    query:str
    company_name:Optional[str] = Field(default='UNKNOWN',title='company name', description='company name')
    collection_name:str = Field(title='collection name',description='collection name')
    company_id:uuid.UUID = Field(title='company id',description='company id')
    model_config = ConfigDict(from_attributes=True)