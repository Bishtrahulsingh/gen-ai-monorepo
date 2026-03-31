import uuid
from pydantic import BaseModel,Field,ConfigDict
from typing import Optional,List

class RetrivalSchema(BaseModel):
    query:str
    company_name:str = Field(title="Company Name",description="Company Name",default="")
    collection_name:str = Field(...,title='collection name',description='collection name')
    ticker:str = Field(...,title='ticker',description='ticker')
    fiscal_year:int = Field(...,title='fiscal year',description='fiscal year')
    model_config = ConfigDict(from_attributes=True)