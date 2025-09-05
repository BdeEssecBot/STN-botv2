import os
import sys
from dataclasses import dataclass
from typing import Optional

# Import et chargement des variables d'environnement - COMME DANS V2
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
    
    line_num = 0  # Initialiser la variable
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

# Charger l'environnement au démarrage du module - COMME DANS V2
setup_environment()

class Config:
    """Configuration centralisée"""
    
    def __init__(self):
        self.page_token = os.getenv("PAGE_TOKEN", "")
        self.google_script_url = os.getenv("GOOGLE_SCRIPT_URL", "")
        self.app_title = os.getenv("APP_TITLE", "STN-bot v3")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.db_path = os.getenv("DB_PATH", "data/stn_bot.db")
    
    def is_valid(self) -> bool:
        """Vérifie la configuration"""
        return bool(self.page_token and self.google_script_url)

# Instance globale - COMME DANS V2
config = Config()

print(f"✅ Configuration chargée:")
print(f"   📱 Page token: {'✅ Défini' if config.page_token else '❌ Manquant'}")
print(f"   🔗 Google Script: {'✅ Défini' if config.google_script_url else '❌ Manquant'}")
print(f"   📋 App: {config.app_title}")
print(f"   🔧 Debug: {config.debug}")

if not config.is_valid():
    print("💥 ERREUR CRITIQUE: Configuration invalide")
    print("🔧 VÉRIFICATIONS:")
    print(f"   1. Fichier .env existe: {os.path.exists('.env')}")
    print(f"   2. PAGE_TOKEN défini: {bool(os.getenv('PAGE_TOKEN'))}")
    print(f"   3. GOOGLE_SCRIPT_URL défini: {bool(os.getenv('GOOGLE_SCRIPT_URL'))}")