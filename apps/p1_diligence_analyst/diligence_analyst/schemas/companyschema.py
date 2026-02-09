from diligence_core import APIModel, IdModel, TimeStampModel
from pydantic import Field, AnyUrl, ConfigDict
from typing import Optional

class CompanyCreate(APIModel):
    name:str=Field(...,title='company name', description='name of company')
    website:Optional[AnyUrl]=Field(title='company website', description='website of company',default=None)
    industry:str = Field(...,title='industry type', description='industry type of company')

class CompanyOut(IdModel,TimeStampModel):
    name: str
    website: Optional[AnyUrl] = None
    industry: Optional[str] =None

    model_config = ConfigDict(from_attributes=True)