import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Ensure .env variables are loaded
from dotenv import load_dotenv
load_dotenv(dotenv_path="c:\\Workspace\\hackathon\\.env")

class Settings(BaseSettings):
    DB_PATH: str = "data/nf_buildathon.db"
    
    # Pinecone
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "nikahforever"
    PINECONE_NAMESPACE: str = "nf-schema"
    EMBEDDING_MODEL: str = "llama-text-embed-v2"
    
    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODELS: str = "gemini-3.5-flash"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:8501"

    model_config = SettingsConfigDict(
        env_file="c:\\Workspace\\hackathon\\.env", 
        extra="ignore"
    )

    @property
    def selected_model(self) -> str:
        """
        Returns the active model name.
        Bypasses any deprecated models (like gemini-2.0-flash or gemini-1.5-flash) 
        and prioritizes gemini-3.5-flash.
        """
        # Return gemini-3.5-flash directly as it is verified as active and working
        return "gemini-3.5-flash"

settings = Settings()
