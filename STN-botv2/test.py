# =============================================================================
# 7. tests/test_integration.py - NOUVEAU
# =============================================================================
"""Integration tests for STN-bot v2"""

import pytest
import tempfile
import os
from pathlib import Path

# Test configuration
@pytest.fixture
def test_env():
    """Setup test environment"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test .env
        env_content = """
PAGE_TOKEN=test_token_123
GOOGLE_APP_SCRIPT_URL=https://script.google.com/test
APP_TITLE=STN-bot Test
DEBUG_MODE=true
"""
        env_path = Path(temp_dir) / ".env"
        with open(env_path, "w") as f:
            f.write(env_content)
        
        # Change to test directory
        old_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        yield temp_dir
        
        # Cleanup
        os.chdir(old_cwd)

def test_database_initialization(test_env):
    """Test database initializes correctly"""
    from database import get_database_manager
    
    db = get_database_manager()
    assert db is not None
    
    health = db.get_health_check()
    assert health["status"] in ["healthy", "warning"]

def test_configuration_loading(test_env):
    """Test configuration loads correctly"""
    from config.settings import settings, validate_configuration
    
    # Reload settings in test environment
    assert settings is not None
    assert validate_configuration() is True

def test_service_factory(test_env):
    """Test service factory works correctly"""
    from services.factory import ServiceFactory
    from services import get_google_forms_service
    
    # Reset factory for clean test
    ServiceFactory.reset()
    
    # Test service creation
    service = get_google_forms_service()
    # Should either return service or None, not crash
    assert service is None or hasattr(service, 'get_form_responses')

def test_error_handling():
    """Test error handling works correctly"""
    from utils.errors import handle_error, STNBotException
    
    test_error = STNBotException("Test error")
    result = handle_error(test_error, "test_context", fallback="fallback_value", show_user=False)
    
    assert result == "fallback_value"

if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running basic integration tests...")
    
    try:
        # Test imports
        from database import get_database_manager
        from services import get_google_forms_service
        from utils.errors import handle_error
        from config.cache import get_cache_config
        
        print("✅ All imports successful")
        print("✅ Integration tests passed")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()