"""Core module for authentication, configuration, and database."""

from core.config import settings
from core.database import get_db

__all__ = ["settings", "get_db"]
