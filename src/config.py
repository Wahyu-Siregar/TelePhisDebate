"""
Configuration module - Load environment variables and settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """Application configuration from environment variables"""

    # LLM provider
    # Supported: deepseek (default), openrouter
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")

    # DeepSeek API
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # OpenRouter (for GPT-OSS free comparison)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
    # Optional attribution headers
    OPENROUTER_SITE_URL: str = os.getenv("OPENROUTER_SITE_URL", "")
    OPENROUTER_APP_NAME: str = os.getenv("OPENROUTER_APP_NAME", "")
    # OpenRouter throttling / runtime tuning (helps avoid 429 for free tier)
    try:
        OPENROUTER_MAX_RPM: int = int(os.getenv("OPENROUTER_MAX_RPM", "12"))
    except ValueError:
        OPENROUTER_MAX_RPM = 12
    OPENROUTER_PARALLEL: bool = os.getenv("OPENROUTER_PARALLEL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # External Security APIs
    VIRUSTOTAL_API_KEY: str = os.getenv("VIRUSTOTAL_API_KEY", "")
    GOOGLE_SAFE_BROWSING_KEY: str = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "")
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    DEEPSEEK_MONTHLY_BUDGET_USD: float = float(os.getenv("DEEPSEEK_MONTHLY_BUDGET_USD", "5.0"))
    
    # Debug
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of missing configs."""
        missing = []

        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        provider = (cls.LLM_PROVIDER or "deepseek").strip().lower()
        if provider == "deepseek":
            if not cls.DEEPSEEK_API_KEY:
                missing.append("DEEPSEEK_API_KEY")
        elif provider == "openrouter":
            if not cls.OPENROUTER_API_KEY:
                missing.append("OPENROUTER_API_KEY")
        else:
            missing.append(f"LLM_PROVIDER (unsupported: {cls.LLM_PROVIDER})")

        if not cls.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not cls.SUPABASE_KEY:
            missing.append("SUPABASE_KEY")

        return missing


# Singleton instance
config = Config()
