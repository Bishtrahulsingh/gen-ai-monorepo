from pydantic import BaseModel, ConfigDict,Field
import uuid
import datetime

class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

class IdModel(APIModel):
    id: uuid.UUID = Field(..., title='id',description='unique identifier for table items')

class TimeStampModel(APIModel):
    created_at : datetime.datetime
    updated_at: datetime.datetime