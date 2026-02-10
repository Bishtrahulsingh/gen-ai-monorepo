from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME:str = 'Due Diligence Analyst'
    DEBUG: bool = True
    GROQ_API_KEY:str = Field(..., title="Groq API Key",description="Groq API Key")

settings = Settings()