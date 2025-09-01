# =============================================================================
# 1. database/__init__.py - CORRIGÉ
# =============================================================================
"""Database module for STN-bot v2 - SQLite Architecture"""

from .models import Person, Form, Response, ReminderStats, DatabaseQuery
from .sqlite_manager import SQLiteDatabase, get_database_manager

__all__ = [
    'Person', 'Form', 'Response', 'ReminderStats', 'DatabaseQuery',
    'SQLiteDatabase', 'get_database_manager'
]
