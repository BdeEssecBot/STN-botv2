
# 1. pages/auth.py
"""Module d'authentification pour STN-bot v2"""

import streamlit as st
from datetime import datetime
from typing import Optional, Dict, Any

# Imports locaux (à ajuster selon votre structure)
from database.enhanced_sqlite_manager import EnhancedSQLiteDatabase

def get_enhanced_database_manager() -> EnhancedSQLiteDatabase:
    """Récupère l'instance de la base de données étendue"""
    if "enhanced_db" not in st.session_state:
        st.session_state.enhanced_db = EnhancedSQLiteDatabase()
    return st.session_state.enhanced_db

def show_login_page() -> bool:
    """Page de connexion"""
    st.title("🔐 Connexion - STN-bot v2")
    
    if "user" in st.session_state:
        st.success(f"Déjà connecté en tant que {st.session_state.user['username']}")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🏠 Continuer vers l'app"):
                return True
        
        with col2:
            if st.button("🚪 Se déconnecter"):
                del st.session_state.user
                st.rerun()
        
        return True
    
    # Formulaire de connexion
    with st.form("login_form"):
        st.subheader("Identifiez-vous")
        
        username = st.text_input("Nom d'utilisateur", placeholder="admin")
        password = st.text_input("Mot de passe", type="password", placeholder="admin123")
        
        submitted = st.form_submit_button("Se connecter", type="primary")
        
        if submitted:
            if not username or not password:
                st.error("❌ Tous les champs sont requis")
            else:
                try:
                    db = get_enhanced_database_manager()
                    user = db.authenticate_user(username, password)
                    
                    if user:
                        st.session_state.user = user
                        st.success(f"✅ Bienvenue {user['username']} !")
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects")
                except Exception as e:
                    st.error(f"❌ Erreur de connexion: {e}")
    
    # Info pour l'admin par défaut
    with st.expander("ℹ️ Première connexion"):
        st.info("""
        **Compte administrateur par défaut:**
        - Utilisateur: `admin`
        - Mot de passe: `admin123`
        
        ⚠️ **Changez ce mot de passe immédiatement après la première connexion !**
        """)
    
    return False

def check_authentication() -> Optional[Dict[str, Any]]:
    """Vérifie si l'utilisateur est connecté"""
    if "user" not in st.session_state:
        if not show_login_page():
            st.stop()
        return None
    
    return st.session_state.user

def require_role(allowed_roles: list) -> Optional[Dict[str, Any]]:
    """Vérifie si l'utilisateur a le rôle requis"""
    user = check_authentication()
    if not user:
        return None
    
    if user['role'] not in allowed_roles:
        st.error("🔒 Accès refusé - Permissions insuffisantes")
        st.info(f"Rôles autorisés: {', '.join(allowed_roles)}")
        st.info(f"Votre rôle: {user['role']}")
        st.stop()
    
    return user

def logout_user():
    """Déconnecte l'utilisateur"""
    if "user" in st.session_state:
        del st.session_state.user
    if "enhanced_db" in st.session_state:
        del st.session_state.enhanced_db
    st.rerun()
