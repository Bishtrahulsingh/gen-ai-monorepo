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
    GROQ_API_KEY:str = Field(title="Groq API Key",description="Groq API Key")
    QDRANT_API_KEY:str
    LANGFUSE_PUBLIC_KEY: str = Field(default="")
    LANGFUSE_SECRET_KEY: str = Field(default="")
    LANGFUSE_BASE_URL: str = Field(default="https://cloud.langfuse.com")
    GEMINI_API_KEY:str = Field(default="")
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_ADMIN_KEY: str

settings = Settings()