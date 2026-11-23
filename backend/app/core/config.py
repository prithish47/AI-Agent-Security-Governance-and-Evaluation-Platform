# =============================================================================
# AgentGuard — Application Configuration
# =============================================================================
# Uses Pydantic Settings to load configuration from environment variables.
#
# WHY PYDANTIC SETTINGS?
# - Automatic type validation (a string "30" becomes int 30)
# - Default values for development
# - Clear documentation of what configuration exists
# - Fails fast if required config is missing
# - Works with .env files for local development
#
# HOW IT WORKS:
# 1. Pydantic reads environment variables automatically
# 2. Variable names are case-insensitive (SECRET_KEY or secret_key)
# 3. The .env file in the project root is loaded if it exists
# 4. Environment variables override .env file values
# =============================================================================

import json
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    
    Every field here corresponds to an environment variable.
    Fields with defaults are optional; fields without defaults are required.
    """
    
    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "AgentGuard"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    # The async connection string for PostgreSQL
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    database_url: str = "postgresql+asyncpg://agentguard:agentguard_dev_password@localhost:5432/agentguard"
    
    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    # JWT signing key — MUST be changed in production
    secret_key: str = "dev-secret-key-CHANGE-IN-PRODUCTION"
    
    # Token lifetimes
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"
    
    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    # Origins allowed to make cross-origin requests
    # In production, this should be only your frontend domain
    cors_origins: List[str] = ["http://localhost:3000"]
    
    # -------------------------------------------------------------------------
    # Agent Runtime
    # -------------------------------------------------------------------------
    # Maximum number of iterations any agent execution can perform
    # This is a hard ceiling — individual agents can set lower limits
    global_iteration_ceiling: int = 20
    
    # -------------------------------------------------------------------------
    # AI Providers (all optional — mock provider works without these)
    # -------------------------------------------------------------------------
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-pro"
    
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    
    # -------------------------------------------------------------------------
    # Pydantic Settings Configuration
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        # Load from .env file in the backend directory
        env_file=".env",
        # Environment variables are case-insensitive
        case_sensitive=False,
        # Allow extra fields (e.g., POSTGRES_USER used only by Docker)
        extra="ignore",
    )


# Create a singleton settings instance
# This is imported throughout the application as:
#   from app.core.config import settings
settings = Settings()
