# =============================================================================
# 3. services/factory.py - NOUVEAU
# =============================================================================
"""Service factory with proper dependency injection"""

import streamlit as st
import logging
from typing import Dict, Any, Optional, TypeVar, Generic
from config.settings import settings
from utils.errors import ServiceUnavailableError, handle_error

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceFactory:
    """Factory for managing service instances with proper error handling"""
    
    _instances: Dict[str, Any] = {}
    _initialization_errors: Dict[str, str] = {}
    
    @classmethod
    def get_service(cls, service_name: str, service_class: type, 
                   required: bool = True) -> Optional[Any]:
        """
        Get service instance with proper error handling
        
        Args:
            service_name: Name of the service
            service_class: Class to instantiate
            required: Whether service is required for app functionality
        
        Returns:
            Service instance or None if not available
        """
        if service_name in cls._instances:
            return cls._instances[service_name]
        
        if service_name in cls._initialization_errors:
            if required:
                error_msg = cls._initialization_errors[service_name]
                logger.error(f"Required service {service_name} unavailable: {error_msg}")
                raise ServiceUnavailableError(f"{service_name}: {error_msg}")
            return None
        
        try:
            # Check configuration requirements
            if not cls._check_service_requirements(service_name):
                error_msg = f"Configuration manquante pour {service_name}"
                cls._initialization_errors[service_name] = error_msg
                
                if required:
                    raise ServiceUnavailableError(error_msg)
                else:
                    logger.warning(error_msg)
                    return None
            
            # Initialize service
            instance = service_class()
            cls._instances[service_name] = instance
            logger.info(f"✅ Service {service_name} initialisé")
            
            return instance
            
        except Exception as e:
            error_msg = f"Échec initialisation {service_name}: {e}"
            cls._initialization_errors[service_name] = error_msg
            logger.error(error_msg)
            
            if required:
                raise ServiceUnavailableError(error_msg)
            return None
    
    @classmethod
    def _check_service_requirements(cls, service_name: str) -> bool:
        """Check if service configuration requirements are met"""
        if not settings:
            return False
        
        requirements = {
            "google_forms": ["google_app_script_url"],
            "messenger": ["page_token"],
            "reminder": ["page_token", "google_app_script_url"]
        }
        
        if service_name not in requirements:
            return True  # No specific requirements
        
        for req in requirements[service_name]:
            if not hasattr(settings, req) or not getattr(settings, req):
                logger.warning(f"Service {service_name} manque: {req}")
                return False
        
        return True
    
    @classmethod
    def reset(cls):
        """Reset all services (for testing)"""
        cls._instances.clear()
        cls._initialization_errors.clear()
    
    @classmethod
    def get_status(cls) -> Dict[str, str]:
        """Get status of all services"""
        status = {}
        for service_name, instance in cls._instances.items():
            status[service_name] = "available"
        
        for service_name, error in cls._initialization_errors.items():
            status[service_name] = f"error: {error}"
        
        return status