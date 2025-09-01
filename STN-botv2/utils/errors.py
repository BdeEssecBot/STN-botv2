# =============================================================================
# 2. utils/errors.py - NOUVEAU
# =============================================================================
"""Centralized error handling for STN-bot v2"""

import streamlit as st
import logging
from typing import Optional, Any
from config.settings import settings

logger = logging.getLogger(__name__)

class STNBotException(Exception):
    """Base exception for STN-bot"""
    pass

class ConfigurationError(STNBotException):
    """Configuration error"""
    pass

class ServiceUnavailableError(STNBotException):
    """Service unavailable error"""
    pass

class DatabaseError(STNBotException):
    """Database operation error"""
    pass

def handle_error(error: Exception, context: str, fallback: Any = None, 
                show_user: bool = True) -> Any:
    """
    Centralized error handler
    
    Args:
        error: The exception that occurred
        context: Context where the error happened
        fallback: Value to return on error
        show_user: Whether to show error to user via Streamlit
    
    Returns:
        Fallback value
    """
    error_msg = f"{context}: {str(error)}"
    logger.error(error_msg)
    
    if show_user:
        if settings and getattr(settings, 'debug_mode', False):
            st.error(error_msg)
            st.exception(error)
        else:
            st.error(f"Erreur dans {context}")
    
    return fallback

def safe_service_call(func, context: str, fallback: Any = None, 
                     show_spinner: bool = True):
    """
    Safe wrapper for service calls
    
    Args:
        func: Function to call
        context: Context for error reporting
        fallback: Value to return on error
        show_spinner: Show spinner during execution
    
    Returns:
        Function result or fallback
    """
    try:
        if show_spinner:
            with st.spinner(f"{context}..."):
                return func()
        else:
            return func()
    except Exception as e:
        return handle_error(e, context, fallback)