# app/core/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    
    # OpenAI
    OPENAI_API_KEY: str
    
    #FAISS
    FAISS : str
    
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 추가: 정의되지 않은 env 변수 무시



config = Settings()
