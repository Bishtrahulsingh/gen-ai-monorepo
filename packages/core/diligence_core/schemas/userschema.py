from pydantic import BaseModel,Field


class UserAuth(BaseModel):
    email:str = Field(
        ...,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        examples=['abc@example.com']
    )
    password:str