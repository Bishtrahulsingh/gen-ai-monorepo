from diligence_core import APIModel, IdModel, TimeStampModel
from pydantic import Field, AnyUrl, ConfigDict
from typing import Optional
import uuid
import enum

class DocumentType(str, enum.Enum):
    pdf ='pdf'
    sec_filing ='sec_filing'
    web ='web'
    image ='image'
    audio = 'audio'

class DocumentCreate(APIModel):
    company_id:uuid.UUID = Field(...,title='company_id',description='id of company')
    title:str=Field(...,title='document title',description='title of document')
    doc_type:DocumentType = Field(...,title='document type',description='type of document from pdf,sec_filling,web,image,audio')
    source:Optional[AnyUrl]=Field(default=None,title='source url',description='enter source url of document')


class DocumentOut(IdModel,TimeStampModel):
    company_id:uuid.UUID
    title:str
    doc_type:DocumentType
    source:Optional[AnyUrl]=None
    model_config = ConfigDict(from_attributes=True)