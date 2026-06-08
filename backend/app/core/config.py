from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "AI Auto-ETL Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    LITELLM_API_BASE: str = "http://localhost:4000"
    LITELLM_MASTER_KEY: str = "sk-litellm-local-test"
    
    EMBEDDING_SERVICE_URL: str = "http://localhost:8001"
    
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8033
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    
    DATAWORKS_REGION: str = "cn-hangzhou"
    DATAWORKS_ACCESS_KEY_ID: Optional[str] = None
    DATAWORKS_ACCESS_KEY_SECRET: Optional[str] = None
    
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_DATABASE: str = "default"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
