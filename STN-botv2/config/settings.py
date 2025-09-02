# config/settings.py
"""Configuration centralisée pour STN-bot v2 - Version Ultra-Propre CORRIGÉE"""

import os
import sys
import logging
from typing import Optional, Dict, Any, Literal

# Import et chargement des variables d'environnement
def setup_environment() -> bool:
    """Configure l'environnement et charge les variables"""
    try:
        from dotenv import load_dotenv
        result = load_dotenv()
        print("✅ python-dotenv chargé avec succès")
        return result
    except ImportError:
        print("⚠️ python-dotenv non disponible, chargement manuel du .env")
        return load_env_manually()

def load_env_manually() -> bool:
    """Charge le fichier .env manuellement"""
    env_path = ".env"
    if not os.path.exists(env_path):
        print("❌ Fichier .env non trouvé")
        return False
    
    line_num = 0  # Initialiser à 0 par défaut
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"\'')
        print("✅ Fichier .env chargé manuellement")
        return True
    except Exception as e:
        print(f"❌ Erreur lecture .env ligne {line_num}: {e}")
        return False

# Charger l'environnement au démarrage du module
setup_environment()

logger = logging.getLogger(__name__)

class Settings:
    """Configuration centralisée de l'application"""
    
    def __init__(self):
        print("🔧 Initialisation des settings STN-bot v2...")
        
        # App Configuration
        self.app_title = os.getenv("APP_TITLE", "STN-bot v2")
        self.app_icon = os.getenv("APP_ICON", "🔔")
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        
        # External APIs (gardés de v1)
        self.page_token = self._get_required_env("PAGE_TOKEN", "Facebook Messenger")
        self.google_app_script_url = self._get_required_env("GOOGLE_APP_SCRIPT_URL", "Google App Script")
        
        # Logging configuration
        self._setup_logging()
        
        print(f"✅ Configuration chargée:")
        print(f"   📱 App: {self.app_title}")
        print(f"   🔗 Google App Script: {self.google_app_script_url[:50]}...")
        print(f"   🔧 Debug mode: {self.debug_mode}")
        print(f"   📱 Page token: {'✅ Défini' if self.page_token else '❌ Manquant'}")
        
        logger.info("🚀 STN-bot v2 configuration loaded successfully")
    
    def _get_required_env(self, key: str, service_name: str) -> str:
        """Récupère une variable d'environnement requise"""
        value = os.getenv(key)
        if not value:
            error_msg = f"❌ Variable d'environnement manquante: {key} (pour {service_name})"
            print(error_msg)
            print(f"💡 Ajoutez dans votre .env: {key}=votre_valeur")
            logger.error(error_msg)
            raise ValueError(error_msg)
        return value
    
    def _get_optional_env(self, key: str, default: str = "") -> str:
        """Récupère une variable d'environnement optionnelle"""
        return os.getenv(key, default)
    
    def _setup_logging(self):
        """Configure le système de logging"""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        
        try:
            logging.basicConfig(
                level=level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('stn_bot_v2.log'),
                    logging.StreamHandler()
                ],
                force=True  # Force la reconfiguration
            )
            
            # Réduire le niveau de logging pour les libs externes
            logging.getLogger('requests').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            
        except Exception as e:
            print(f"⚠️ Erreur configuration logging: {e}")

# Instance globale avec gestion d'erreur propre
settings: Optional[Settings] = None

try:
    settings = Settings()
except Exception as e:
    print(f"💥 ERREUR CRITIQUE lors de l'initialisation des settings:")
    print(f"   {e}")
    print(f"\n🔧 VÉRIFICATIONS:")
    print(f"   1. Fichier .env existe: {os.path.exists('.env')}")
    print(f"   2. PAGE_TOKEN défini: {bool(os.getenv('PAGE_TOKEN'))}")
    print(f"   3. GOOGLE_APP_SCRIPT_URL défini: {bool(os.getenv('GOOGLE_APP_SCRIPT_URL'))}")
    print(f"\n💡 SOLUTION:")
    print(f"   Créez un fichier .env avec:")
    print(f"   PAGE_TOKEN=votre_token_facebook")
    print(f"   GOOGLE_APP_SCRIPT_URL=votre_url_app_script")
    raise

# Vérification que settings est bien initialisé
if settings is None:
    raise RuntimeError("Settings non initialisé")

# Constantes pour l'application
class AppConstants:
    """Constantes de l'application"""
    
    # URLs et templates
    GOOGLE_FORM_URL_TEMPLATE = "https://docs.google.com/forms/d/{form_id}/viewform"
    
    # Messages par défaut
    DEFAULT_REMINDER_TEMPLATE = """Hello {name},

Petit rappel pour remplir le formulaire *{form_name}*, diffusé le {date_envoi}.

Lien du formulaire 👉👉 {form_url}

Bien à toi,
La bise Santana"""
    
    # Configuration Streamlit CORRIGÉE avec types explicites
    @classmethod
    def get_streamlit_config(cls) -> Dict[str, Any]:
        """Configuration Streamlit avec types corrects"""
        if settings is None:
            return {
                "page_title": "STN-bot v2",
                "page_icon": "🔔",
                "layout": "wide",
                "initial_sidebar_state": "expanded"
            }
        return {
            "page_title": settings.app_title,
            "page_icon": settings.app_icon,
            "layout": "wide",  # Type Literal correct
            "initial_sidebar_state": "expanded"  # Type Literal correct
        }
    
    # Cache settings (en secondes)
    CACHE_GOOGLE_FORMS = 60  # 1 minute pour Google Forms
    CACHE_DATABASE = 300     # 5 minutes pour la base de données
    
    # Couleurs du thème
    COLORS = {
        "primary": "#FF6B6B",
        "success": "#4CAF50", 
        "warning": "#FF9800",
        "error": "#F44336",
        "info": "#2196F3"
    }
    
    # Emojis pour l'interface
    EMOJIS = {
        "forms": "📋",
        "people": "👥", 
        "responses": "📝",
        "reminders": "🔔",
        "sync": "🔄",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "settings": "⚙️",
        "dashboard": "📊"
    }

def validate_configuration() -> bool:
    """Valide que toute la configuration est correcte"""
    try:
        # Test basic settings
        assert settings is not None, "Settings not initialized"
        assert settings.page_token, "PAGE_TOKEN is required"
        assert settings.google_app_script_url, "GOOGLE_APP_SCRIPT_URL is required"
        
        logger.info("✅ Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False

if __name__ == "__main__":
    # Test de la configuration
    print("\n🧪 Testing STN-bot v2 configuration...")
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Répertoire: {os.getcwd()}")
    
    if validate_configuration():
        print("🎉 Configuration is valid!")
    else:
        print("💥 Configuration has errors!")
    
    print(f"\n📋 Variables d'environnement détectées:")
    for key in ['PAGE_TOKEN', 'GOOGLE_APP_SCRIPT_URL', 'APP_TITLE', 'DEBUG_MODE']:
        value = os.getenv(key)
        if value:
            display_value = value[:20] + "..." if len(value) > 20 else value
            print(f"   ✅ {key}: {display_value}")
        else:
            print(f"   ❌ {key}: Non défini")