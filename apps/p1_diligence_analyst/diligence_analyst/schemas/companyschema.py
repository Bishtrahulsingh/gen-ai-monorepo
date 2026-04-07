from diligence_core import APIModel, IdModel, TimeStampModel
from pydantic import Field, AnyUrl, ConfigDict, BaseModel
from typing import Optional, List


class CompanyCreate(APIModel):
    name:str=Field(...,title='company name', description='name of company')
    ticker:str=Field(title='company ticker', description='company ticker',default='')
    sector:str = Field(title='industry type', description='industry type of company',default='')
    model_config = ConfigDict(from_attributes=True)

class CompanyOut(IdModel,TimeStampModel):
    name: str
    model_config = ConfigDict(from_attributes=True)


class SearchAndStore(APIModel):
    name:str=Field(...,title='company name', description='name of company')
    ticker:str=Field(...,title='company ticker', description='company ticker')
    year:List[int] = Field(...,description='list of year of company sec filings')
    model_config = ConfigDict(from_attributes=True)

