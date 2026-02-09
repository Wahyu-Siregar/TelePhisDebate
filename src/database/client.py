"""
Supabase client initialization
"""

from supabase import create_client, Client
from src.config import config


_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create Supabase client singleton"""
    global _supabase_client
    
    if _supabase_client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        
        _supabase_client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_KEY
        )
    
    return _supabase_client


# Convenience alias
db = get_supabase_client
