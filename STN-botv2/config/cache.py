# =============================================================================
# 5. config/cache.py - NOUVEAU
# =============================================================================
"""Centralized cache configuration"""

from typing import Dict, Any

# Cache settings for different data types
CACHE_SETTINGS = {
    "google_forms_responses": {
        "ttl": 60,  # 1 minute
        "show_spinner": False,
        "persist": "disk"
    },
    "google_forms_batch": {
        "ttl": 60,
        "show_spinner": True,
        "persist": "disk"
    },
    "database_stats": {
        "ttl": 300,  # 5 minutes  
        "show_spinner": False,
        "persist": "memory"
    },
    "service_instances": {
        "show_spinner": False,
        "persist": "session"
    },
    "health_checks": {
        "ttl": 120,  # 2 minutes
        "show_spinner": False,
        "persist": "memory"
    }
}

def get_cache_config(cache_type: str) -> Dict[str, Any]:
    """Get cache configuration for a specific type"""
    return CACHE_SETTINGS.get(cache_type, {"ttl": 300, "show_spinner": False})

def clear_all_caches():
    """Clear all Streamlit caches"""
    import streamlit as st
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
        return True
    except Exception:
        return False