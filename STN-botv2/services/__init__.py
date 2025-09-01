# =============================================================================
# 4. services/__init__.py - HARMONISÉ
# =============================================================================
"""Services module for STN-bot v2 with factory pattern"""

import streamlit as st
from .factory import ServiceFactory
from utils.errors import handle_error

# Import service classes
def _import_service_classes():
    """Lazy import of service classes to avoid circular dependencies"""
    try:
        from .google_forms_service import GoogleFormsService
        from .messenger_service import MessengerService
        from .reminder_service import ReminderService
        return {
            "google_forms": GoogleFormsService,
            "messenger": MessengerService, 
            "reminder": ReminderService
        }
    except ImportError as e:
        handle_error(e, "Import des services", fallback={})
        return {}

# Service getters with factory pattern
@st.cache_resource
def get_google_forms_service():
    """Get Google Forms service instance"""
    service_classes = _import_service_classes()
    if "google_forms" not in service_classes:
        return None
    
    return ServiceFactory.get_service(
        "google_forms", 
        service_classes["google_forms"],
        required=False
    )

@st.cache_resource  
def get_messenger_service():
    """Get Messenger service instance"""
    service_classes = _import_service_classes()
    if "messenger" not in service_classes:
        return None
    
    return ServiceFactory.get_service(
        "messenger",
        service_classes["messenger"], 
        required=False
    )

@st.cache_resource
def get_reminder_service():
    """Get Reminder service instance"""  
    service_classes = _import_service_classes()
    if "reminder" not in service_classes:
        return None
    
    return ServiceFactory.get_service(
        "reminder",
        service_classes["reminder"],
        required=False
    )

# Health check function
def check_all_services():
    """Check health of all services"""
    return ServiceFactory.get_status()

__all__ = [
    'get_google_forms_service',
    'get_messenger_service', 
    'get_reminder_service',
    'check_all_services',
    'ServiceFactory'
]
