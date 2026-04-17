import os
from functools import lru_cache


class Settings:
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "timewise")
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200
    
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 314572800


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
