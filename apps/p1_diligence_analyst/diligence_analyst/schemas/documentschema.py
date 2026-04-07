from diligence_core import APIModel, IdModel, TimeStampModel
from pydantic import Field, AnyUrl, ConfigDict, BaseModel
from typing import Optional
import uuid
import enum


class DocumentCreate(APIModel):
    company_id:uuid.UUID = Field(...,title='company_id',description='id of company')
    title:str=Field(...,title='document title',description='title of document')
    doc_type:str = Field(...,title='document type',description='type of document from pdf,sec_filling,web,image,audio')
    source:AnyUrl=Field(...,title='source url',description='enter source url of document')
    fiscal_year:int=Field(...,title='fiscal year',description='fiscal year of document')

class DocumentOut(IdModel,TimeStampModel):
    company_id:uuid.UUID
    title:str
    doc_type:str
    source:Optional[AnyUrl]=None
    model_config = ConfigDict(from_attributes=True)



class StoredDocument(BaseModel):
    fiscal_year:str
    ticker:str


class DocumentYearsRequest(BaseModel):
    ticker: str