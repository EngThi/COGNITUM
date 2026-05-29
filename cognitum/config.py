import os
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "cognitum"
    timezone: str = "America/Sao_Paulo"
    
    # Base directory of the project
    base_dir: Path = Path(__file__).resolve().parent.parent
    
    # Path configuration
    database_path: Optional[str] = None
    vault_dir: Optional[str] = None
    memory_dir: Optional[str] = None
    profiles_dir: Optional[str] = None
    policies_dir: Optional[str] = None
    
    # Global HTTP Timeout
    http_timeout: float = 30.0
    
    # Gemini SDK Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    
    # Telegram Bot Token
    telegram_bot_token: Optional[str] = None
    
    # Kimi Proxy configurations
    kimi_proxy_url: str = "http://localhost:3000"
    kimi_proxy_api_key: str = "cognitum-internal-key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def resolve_paths(self) -> "Settings":
        # Resolve paths dynamically relative to base_dir if not explicitly set
        if not self.database_path:
            # ensure data directory exists
            data_dir = self.base_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.database_path = str(data_dir / "cognitum.db")
        if not self.vault_dir:
            self.vault_dir = str(self.base_dir / "vault")
        if not self.memory_dir:
            self.memory_dir = str(self.base_dir / "memory")
        if not self.profiles_dir:
            self.profiles_dir = str(self.base_dir / "profiles")
        if not self.policies_dir:
            self.policies_dir = str(self.base_dir / "policies")
            
        # Ensure directories exist
        Path(self.vault_dir).mkdir(parents=True, exist_ok=True)
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)
        Path(self.profiles_dir).mkdir(parents=True, exist_ok=True)
        Path(self.policies_dir).mkdir(parents=True, exist_ok=True)
        
        return self

settings = Settings()
