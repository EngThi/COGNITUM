from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "automation-runtime"
    timezone: str = "America/Sao_Paulo"
    database_path: str = "/opt/automation/runtime/state/automation.db"
    
    # Global HTTP Timeout
    http_timeout: float = 30.0

    model_config = SettingsConfigDict(env_file="/opt/automation/.env", extra="ignore")

settings = Settings()
