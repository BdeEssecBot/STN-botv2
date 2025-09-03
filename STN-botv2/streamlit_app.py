# streamlit_app.py
"""STN-bot v2 - Application Streamlit principale CORRIGÉE"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from modules.groups_management import show_groups_management_page

# Configuration Streamlit
from config.settings import settings, AppConstants, validate_configuration
from config.cache import clear_all_caches

# Services
from services import (
    get_google_forms_service, 
    get_messenger_service, 
    get_reminder_service,
    check_all_services
)

# Database
from database import get_database_manager
from database.models import Person, Form, Pole

# Utils
from utils.errors import handle_error, safe_service_call

# Modules (au lieu de pages pour éviter l'affichage automatique)
from modules.auth import check_authentication, show_login_page, logout_user
from modules.message_history import show_message_history_page
from modules.validation import show_validation_page
from modules.user_management import show_user_management_page

# Logger
logger = logging.getLogger(__name__)

def main():
    """Point d'entrée principal avec gestion des modes"""
    
    # Configuration de la page
    st.set_page_config(
        page_title=settings.app_title if settings else "STN-bot v2",
        page_icon=settings.app_icon if settings else "🔔",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Vérifier si on veut le mode enhanced ou classique
    if st.session_state.get("enhanced_mode", False):
        main_enhanced()
    else:
        main_classic()

def main_classic():
    """Version classique sans authentification (comme avant)"""
    
    st.title(f"{settings.app_icon if settings else '🔔'} {settings.app_title if settings else 'STN-bot v2'}")
    
    # Sidebar navigation classique
    with st.sidebar:
        st.header("Navigation")
        
        # Bouton pour activer le mode enhanced
        if st.button("🔐 Mode avancé (avec auth)"):
            st.session_state.enhanced_mode = True
            st.rerun()
        
        st.divider()
        
        # Navigation classique avec TOUTES les pages
        page = st.selectbox(
            "Choisir une page",
            [
                "🏠 Dashboard",
                "📋 Formulaires",
                "👥 Personnes",
                "🔔 Rappels",
                "🔄 Synchronisation",
                "⚙️ Paramètres"
            ]
        )
        
        # Statut des services
        show_service_status()
    
    # Routing classique
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "📋 Formulaires":
        show_forms_page()
    elif page == "👥 Personnes":
        show_people_page()
    elif page == "🔔 Rappels":
        show_reminders_page()
    elif page == "🔄 Synchronisation":
        show_sync_page()
    elif page == "⚙️ Paramètres":
        show_settings_page()

def main_enhanced():
    """Version enhanced avec authentification et fonctionnalités avancées"""
    
    # Vérification authentification
    if not check_authentication():
        return
    
    user = st.session_state.user
    
    # Interface adaptée au rôle
    st.title(f"🔔 STN-bot v2 - {user['username']} ({user['role']})")
    
    # Sidebar avec pages selon les permissions
    with st.sidebar:
        st.header("Navigation")
        
        # Bouton pour revenir au mode classique
        if st.button("🔓 Mode classique (sans auth)"):
            if "user" in st.session_state:
                del st.session_state.user
            st.session_state.enhanced_mode = False
            st.rerun()
        
        st.divider()
        
        available_pages = get_available_pages_for_role(user['role'])
        
        page = st.selectbox("Choisir une page", available_pages)
        
        # Info utilisateur
        st.divider()
        st.write(f"👤 **{user['username']}**")
        st.write(f"🏷️ Rôle: {user['role']}")
        
        if user['role'] != 'admin':
            accessible_poles = get_user_accessible_poles_names(user['id'])
            if accessible_poles:
                st.write(f"🏢 Pôles: {', '.join(accessible_poles)}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔑 Changer MDP"):
                st.session_state.show_change_password = True
        
        with col2:
            if st.button("🚪 Déconnexion"):
                logout_user()
        
        # Statut des services
        show_service_status()
    
    # Modal changement de mot de passe
    if st.session_state.get("show_change_password"):
        show_change_password_modal()
        return
    
    # Routing avec contrôle d'accès
    route_page_with_permissions(page, user)

def get_available_pages_for_role(role: str) -> List[str]:
    """Retourne TOUTES les pages disponibles selon le rôle"""
    base_pages = [
        "🏠 Dashboard",
        "📋 Formulaires",
        "👥 Personnes",
        "👥 Groupes de personnes",
        "🔔 Rappels"
    ]
    
    if role in ['admin', 'pole_manager']:
        base_pages.extend([
            "📜 Historique des messages",
            "⏳ Validation des contacts",
            "🔄 Synchronisation"
        ])
    
    if role == 'admin':
        base_pages.extend([
            "👤 Gestion des utilisateurs",
            "⚙️ Paramètres système"
        ])
    
    return base_pages

def route_page_with_permissions(page: str, user: Dict[str, Any]):
    """Route vers les pages avec contrôle des permissions"""
    
    # Pages classiques (toujours disponibles)
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "📋 Formulaires":
        show_forms_page()
    elif page == "👥 Personnes":
        show_people_page()
    elif page == "🔔 Rappels":
        show_reminders_page()
    elif page == "🔄 Synchronisation":
        show_sync_page()
    elif page == "⚙️ Paramètres système":
        show_settings_page()
    elif page == "👥 Groupes de personnes":
        show_groups_management_page()
    
    # Pages enhanced (nouvelles)
    elif page == "📜 Historique des messages":
        show_message_history_page()
    elif page == "⏳ Validation des contacts":
        show_validation_page()
    elif page == "👤 Gestion des utilisateurs":
        show_user_management_page()

# Correction pour le changement de mot de passe dans streamlit_app.py

def show_change_password_modal():
    """Modal pour changer le mot de passe - VERSION CORRIGÉE"""
    st.header("🔑 Changer le mot de passe")
    
    user = st.session_state.user
    
    with st.form("change_password"):
        current_password = st.text_input("Mot de passe actuel", type="password")
        new_password = st.text_input("Nouveau mot de passe", type="password")
        confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password")
        
        col1, col2 = st.columns(2)
        
        with col1:
            submitted = st.form_submit_button("💾 Changer", type="primary")
        
        with col2:
            cancelled = st.form_submit_button("❌ Annuler")
        
        if cancelled:
            del st.session_state.show_change_password
            st.rerun()
        
        if submitted:
            if not all([current_password, new_password, confirm_password]):
                st.error("Tous les champs sont requis")
            elif new_password != confirm_password:
                st.error("Les nouveaux mots de passe ne correspondent pas")
            elif len(new_password) < 8:
                st.error("Le mot de passe doit faire au moins 8 caractères")
            else:
                # Utiliser la base enhanced pour changer le mot de passe
                from database.enhanced_sqlite_manager import EnhancedSQLiteDatabase
                
                enhanced_db = EnhancedSQLiteDatabase()
                
                # Vérifier l'ancien mot de passe
                auth_result = enhanced_db.authenticate_user(user['username'], current_password)
                if not auth_result:
                    st.error("Mot de passe actuel incorrect")
                    return
                
                # Changer le mot de passe
                new_hash = enhanced_db._hash_password(new_password)
                
                try:
                    import sqlite3
                    with sqlite3.connect(enhanced_db.db_path) as conn:
                        # Vérifier d'abord si la colonne updated_at existe
                        cursor = conn.execute("PRAGMA table_info(users)")
                        columns = [row[1] for row in cursor.fetchall()]
                        
                        if 'updated_at' in columns:
                            # Si la colonne existe, l'utiliser
                            conn.execute("""
                                UPDATE users 
                                SET password_hash = ?, updated_at = ?
                                WHERE username = ?
                            """, (new_hash, datetime.now().isoformat(), user['username']))
                        else:
                            # Sinon, ne pas l'utiliser
                            conn.execute("""
                                UPDATE users 
                                SET password_hash = ?
                                WHERE username = ?
                            """, (new_hash, user['username']))
                        
                        conn.commit()
                    
                    st.success("✅ Mot de passe changé avec succès!")
                    del st.session_state.show_change_password
                    
                    # Forcer la reconnexion
                    st.info("Veuillez vous reconnecter avec votre nouveau mot de passe")
                    logout_user()
                    
                except Exception as e:
                    st.error(f"Erreur lors du changement: {e}")

def get_user_accessible_poles_names(user_id: str) -> List[str]:
    """Récupère les noms des pôles accessibles pour un utilisateur"""
    try:
        db = get_database_manager()
        poles = db.get_active_poles()
        return [pole.name for pole in poles]
    except Exception:
        return []

def show_service_status():
    """Affiche le statut des services dans la sidebar"""
    st.subheader("🔧 Statut des services")
    
    status = safe_service_call(
        check_all_services,
        "Vérification des services",
        fallback={},
        show_spinner=False
    )
    
    if not status:
        st.warning("Services non disponibles")
        return
    
    for service_name, service_status in status.items():
        if service_status == "available":
            st.success(f"✅ {service_name.title()}")
        elif "error" in service_status:
            st.error(f"❌ {service_name.title()}")
        else:
            st.warning(f"⚠️ {service_name.title()}")

# === TOUTES LES PAGES EXISTANTES CI-DESSOUS ===

def show_dashboard():
    """Page d'accueil avec statistiques"""
    st.header("📊 Dashboard")
    
    # Récupérer les statistiques
    reminder_service = get_reminder_service()
    if not reminder_service:
        st.error("Service de rappels non disponible")
        return
    
    stats = safe_service_call(
        reminder_service.get_dashboard_stats,
        "Chargement des statistiques",
        fallback={"error": "Données non disponibles"}
    )
    
    if "error" in stats:
        st.error(f"Erreur : {stats['error']}")
        return
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    global_stats = stats.get("global_stats", {})
    
    with col1:
        st.metric(
            "👥 Personnes totales",
            global_stats.get("total_people", 0)
        )
    
    with col2:
        st.metric(
            "📋 Réponses totales", 
            global_stats.get("total_responses", 0)
        )
    
    with col3:
        st.metric(
            "🔔 Rappels en attente",
            global_stats.get("pending_reminders", 0)
        )
    
    with col4:
        success_rate = global_stats.get("success_rate", 0)
        st.metric(
            "✅ Taux de réussite",
            f"{success_rate:.1f}%"
        )
    
    # Graphiques
    col_left, col_right = st.columns(2)
    
    with col_left:
        show_forms_chart(stats.get("forms_stats", []))
    
    with col_right:
        show_messenger_stats(stats.get("messenger_stats", {}))
    
    # Actions rapides
    st.subheader("🚀 Actions rapides")
    col_sync, col_remind, col_clear = st.columns(3)
    
    with col_sync:
        if st.button("🔄 Synchroniser tout", type="primary"):
            sync_all_forms()
    
    with col_remind:
        if st.button("📧 Envoyer rappels"):
            send_all_reminders()
    
    with col_clear:
        if st.button("🧹 Vider cache"):
            clear_all_caches()
            st.success("Cache vidé !")
            st.rerun()

def show_forms_chart(forms_stats: List[Dict]):
    """Graphique des formulaires"""
    st.subheader("📊 Statut des formulaires")
    
    if not forms_stats:
        st.info("Aucun formulaire à afficher")
        return
    
    df = pd.DataFrame(forms_stats)
    
    fig = px.bar(
        df,
        x="form_name",
        y=["responded", "pending"],
        title="Réponses par formulaire",
        color_discrete_map={
            "responded": AppConstants.COLORS["success"],
            "pending": AppConstants.COLORS["warning"]
        }
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def show_messenger_stats(messenger_stats: Dict):
    """Statistiques Messenger"""
    st.subheader("📱 Statistiques Messenger (24h)")
    
    if not messenger_stats or "error" in messenger_stats:
        st.info("Aucune donnée Messenger")
        return
    
    total = messenger_stats.get("total_messages", 0)
    successful = messenger_stats.get("successful", 0)
    failed = messenger_stats.get("failed", 0)
    
    if total == 0:
        st.info("Aucun message envoyé récemment")
        return
    
    # Graphique en camembert
    fig = go.Figure(data=[
        go.Pie(
            labels=["Réussis", "Échecs"],
            values=[successful, failed],
            hole=0.5,
            marker_colors=[AppConstants.COLORS["success"], AppConstants.COLORS["error"]]
        )
    ])
    
    fig.update_layout(
        title=f"Messages: {total} total",
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)

def show_forms_page():
    """Gestion des formulaires avec organisation par pôles"""
    st.header("📋 Gestion des formulaires par pôles")
    
    db = get_database_manager()
    
    # Récupérer les pôles
    poles = db.get_active_poles()
    
    if not poles:
        st.warning("⚠️ Aucun pôle configuré")
        if st.button("➕ Créer le premier pôle"):
            st.session_state.show_create_pole = True
            st.rerun()
        return
    
    # Sélection du pôle
    col_select, col_manage = st.columns([3, 1])
    
    with col_select:
        selected_pole = st.selectbox(
            "🏢 Choisir un pôle",
            options=poles,
            format_func=lambda p: f"{p.display_name} ({len(db.get_forms_by_pole(p.id))} formulaire(s))",
            key="selected_pole"
        )
    
    with col_manage:
        if st.button("⚙️ Gérer les pôles"):
            st.session_state.show_poles_management = True
            st.rerun()
    
    # Gestion des pôles (modal)
    if st.session_state.get("show_poles_management"):
        show_poles_management(db)
        return
    
    if not selected_pole:
        return
    
    # Afficher les formulaires du pôle sélectionné
    st.subheader(f"📋 Formulaires - {selected_pole.name}")
    
    # Onglets pour ce pôle
    tab_list, tab_create = st.tabs(["📄 Liste des formulaires", "➕ Nouveau formulaire"])
    
    with tab_list:
        show_forms_list_by_pole(db, selected_pole.id)
    
    with tab_create:
        show_create_form_with_pole(db, selected_pole.id)

def show_poles_management(db):
    """Interface de gestion des pôles"""
    st.header("⚙️ Gestion des pôles")
    
    # Bouton de retour
    if st.button("← Retour aux formulaires"):
        del st.session_state.show_poles_management
        st.rerun()
    
    # Onglets gestion
    tab_list, tab_create = st.tabs(["📄 Liste des pôles", "➕ Nouveau pôle"])
    
    with tab_list:
        show_poles_list(db)
    
    with tab_create:
        show_create_pole(db)

def show_poles_list(db):
    """Liste des pôles avec actions d'édition"""
    poles = db.get_all_poles()
    
    if not poles:
        st.info("Aucun pôle créé")
        return
    
    for pole in poles:
        with st.expander(f"{pole.display_name} - {len(db.get_forms_by_pole(pole.id))} formulaire(s)"):
            col_info, col_actions = st.columns([2, 1])
            
            with col_info:
                st.write(f"**Description:** {pole.description or 'Aucune'}")
                st.write(f"**Statut:** {'🟢 Actif' if pole.is_active else '🔴 Inactif'}")
                st.write(f"**Formulaires:** {len(db.get_forms_by_pole(pole.id))}")
                st.write(f"**Créé le:** {pole.created_at.strftime('%d/%m/%Y')}")
                
                # Aperçu couleur
                st.markdown(f"**Couleur:** <span style='background-color: {pole.color}; padding: 2px 8px; border-radius: 3px; color: white;'>{pole.color}</span>", unsafe_allow_html=True)
            
            with col_actions:
                col_edit, col_delete = st.columns(2)
                
                with col_edit:
                    if st.button(f"✏️ Modifier", key=f"edit_pole_{pole.id}"):
                        st.session_state[f"editing_pole_{pole.id}"] = True
                        st.rerun()
                
                with col_delete:
                    if st.button(f"🗑️ Supprimer", key=f"delete_pole_{pole.id}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_pole_{pole.id}"):
                            # Vérifier s'il y a des formulaires
                            forms_count = len(db.get_forms_by_pole(pole.id))
                            if forms_count > 0:
                                st.error(f"Impossible de supprimer: {forms_count} formulaire(s) associé(s)")
                            else:
                                success = db.delete_pole(pole.id)
                                if success:
                                    st.success(f"Pôle '{pole.name}' supprimé")
                                    cleanup_pole_session_state(pole.id)
                                    st.rerun()
                                else:
                                    st.error("Erreur lors de la suppression")
                        else:
                            st.session_state[f"confirm_delete_pole_{pole.id}"] = True
                            st.warning("Cliquez à nouveau pour confirmer")
            
            # Modal d'édition
            if st.session_state.get(f"editing_pole_{pole.id}"):
                show_edit_pole_modal(db, pole)

def show_create_pole(db):
    """Création d'un nouveau pôle"""
    st.subheader("➕ Créer un nouveau pôle")
    
    with st.form("create_pole"):
        name = st.text_input("Nom du pôle*", placeholder="ex: Marketing, RH, IT...")
        description = st.text_area("Description", placeholder="Description du pôle...")
        
        # Sélection de couleur
        col_color, col_preview = st.columns([2, 1])
        with col_color:
            color = st.color_picker("Couleur", value="#FF6B6B")
        with col_preview:
            st.markdown(f"**Aperçu:** <span style='background-color: {color}; padding: 4px 12px; border-radius: 4px; color: white;'>{name or 'Nom du pôle'}</span>", unsafe_allow_html=True)
        
        is_active = st.checkbox("Pôle actif", value=True)
        
        submitted = st.form_submit_button("Créer le pôle", type="primary")
        
        if submitted:
            if not name:
                st.error("Le nom du pôle est requis")
            else:
                pole = Pole(
                    name=name,
                    description=description,
                    color=color,
                    is_active=is_active
                )
                
                success = db.add_pole(pole)
                
                if success:
                    st.success(f"✅ Pôle '{name}' créé avec succès!")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la création (nom déjà existant?)")

def show_edit_pole_modal(db, pole):
    """Modal d'édition d'un pôle"""
    st.subheader(f"✏️ Modifier {pole.name}")
    
    with st.form(f"edit_pole_{pole.id}"):
        new_name = st.text_input("Nom du pôle", value=pole.name)
        new_description = st.text_area("Description", value=pole.description)
        
        col_color, col_preview = st.columns([2, 1])
        with col_color:
            new_color = st.color_picker("Couleur", value=pole.color)
        with col_preview:
            st.markdown(f"**Aperçu:** <span style='background-color: {new_color}; padding: 4px 12px; border-radius: 4px; color: white;'>{new_name}</span>", unsafe_allow_html=True)
        
        new_is_active = st.checkbox("Pôle actif", value=pole.is_active)
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button("💾 Sauvegarder", type="primary")
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ Annuler")
        
        if cancelled:
            del st.session_state[f"editing_pole_{pole.id}"]
            st.rerun()
        
        if submitted:
            if not new_name:
                st.error("Le nom est requis")
            else:
                success = db.update_pole(pole.id, new_name, new_description, new_color, new_is_active)
                if success:
                    st.success(f"✅ Pôle '{new_name}' mis à jour!")
                    del st.session_state[f"editing_pole_{pole.id}"]
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la mise à jour")


def show_create_form_with_pole(db, pole_id: str = None): # type: ignore
    """Création d'un nouveau formulaire avec sélection du pôle et support des groupes"""
    st.subheader("➕ Créer un nouveau formulaire")
    
    with st.form("create_form_with_pole"):
        name = st.text_input("Nom du formulaire*", placeholder="ex: Enquête satisfaction Q4")
        google_form_id = st.text_input("Google Form ID*", placeholder="1FAIpQLSe...")
        description = st.text_area("Description", placeholder="Description du formulaire...")
        date_envoi = st.date_input("Date d'envoi", value=datetime.now().date())
        
        # Sélection du pôle
        st.subheader("🏢 Pôle associé")
        poles = db.get_active_poles()
        
        if poles:
            # Si pole_id fourni, trouver son index
            default_index = 0
            if pole_id:
                for i, pole in enumerate(poles):
                    if pole.id == pole_id:
                        default_index = i
                        break
            
            selected_pole = st.selectbox(
                "Choisir le pôle*",
                options=poles,
                index=default_index,
                format_func=lambda p: p.display_name,
                help="Le formulaire sera associé à ce pôle"
            )
            pole_id_final = selected_pole.id if selected_pole else None
        else:
            st.error("⚠️ Aucun pôle disponible. Créez d'abord un pôle!")
            pole_id_final = None
            return
        
        # Section de sélection avec groupes
        st.subheader("📋 Sélection des destinataires")
        
        # Onglets pour différents modes de sélection
        tab_groups, tab_individual = st.tabs(["👥 Par groupes", "👤 Individuel"])
        
        selected_people_ids = set()
        
        with tab_groups:
            groups = db.get_all_groups()
            if groups:
                st.write("**Sélectionner des groupes:**")
                
                for group in groups:
                    if st.checkbox(
                        f"{group.display_name} ({group.member_count} membres)",
                        key=f"group_{group.id}",
                        help=group.description
                    ):
                        selected_people_ids.update(group.member_ids)
                
                if selected_people_ids:
                    st.success(f"✅ {len(selected_people_ids)} personnes sélectionnées via les groupes")
            else:
                st.info("Aucun groupe disponible. Créez des groupes pour faciliter la sélection!")
        
        with tab_individual:
            people = db.get_all_people()
            if people:
                st.write("**Ajuster la sélection individuellement:**")
                if selected_people_ids:
                    st.info("Les personnes déjà sélectionnées via les groupes sont pré-cochées")
                
                # Afficher les personnes avec leur statut
                cols = st.columns(2)
                for i, person in enumerate(people):
                    with cols[i % 2]:
                        # Pré-cocher si déjà dans un groupe sélectionné
                        default_checked = person.id in selected_people_ids
                        
                        if st.checkbox(
                            f"{person.name} ({person.email or 'pas d\'email'})",
                            key=f"person_{person.id}",
                            value=default_checked
                        ):
                            selected_people_ids.add(person.id)
                        elif person.id in selected_people_ids:
                            selected_people_ids.remove(person.id)
            else:
                st.warning("Aucune personne dans la base. Ajoutez des personnes d'abord.")
        
        # Résumé de la sélection
        st.divider()
        if selected_people_ids:
            st.success(f"📊 Total: {len(selected_people_ids)} personne(s) sélectionnée(s)")
        else:
            st.warning("⚠️ Aucune personne sélectionnée")
        
        submitted = st.form_submit_button("Créer le formulaire", type="primary")
        
        if submitted:
            if not name or not google_form_id:
                st.error("Nom et Google Form ID sont requis")
            elif not pole_id_final:
                st.error("Veuillez sélectionner un pôle")
            elif not selected_people_ids:
                st.error("Sélectionnez au moins une personne")
            else:
                form = Form(
                    name=name,
                    google_form_id=google_form_id,
                    pole_id=pole_id_final,  # Utiliser le pôle sélectionné
                    description=description,
                    date_envoi=datetime.combine(date_envoi, datetime.min.time())
                )
                
                # Convertir le set en list pour l'envoi
                success = db.add_form(form, list(selected_people_ids))
                
                if success:
                    st.success(f"✅ Formulaire '{name}' créé dans le pôle '{selected_pole.name}' avec {len(selected_people_ids)} destinataires!")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la création du formulaire")

def show_people_page():
    """Gestion des personnes"""
    st.header("👥 Gestion des personnes")
    
    db = get_database_manager()
    
    # Onglets
    tab_list, tab_add = st.tabs(["📄 Liste des personnes", "➕ Nouvelle personne"])
    
    with tab_list:
        show_people_list(db)
    
    with tab_add:
        show_add_person(db)

def show_people_list(db):
    """Liste des personnes avec actions d'édition"""
    people = safe_service_call(
        db.get_all_people,
        "Chargement des personnes",
        fallback=[]
    )
    
    if not people:
        st.info("Aucune personne enregistrée")
        return
    
    st.subheader("👥 Liste des personnes")
    
    for i, person in enumerate(people):
        with st.expander(f"{person.name} - {person.email or 'Pas d\'email'}"):
            col_info, col_actions = st.columns([2, 1])
            
            with col_info:
                st.write(f"**Nom:** {person.name}")
                st.write(f"**Email:** {person.email or 'Non défini'}")
                st.write(f"**PSID:** {person.psid[:15] + '...' if person.psid and len(person.psid) > 15 else person.psid or 'Non défini'}")
                st.write(f"**Ajouté le:** {person.created_at.strftime('%d/%m/%Y à %H:%M')}")
            
            with col_actions:
                col_edit, col_delete = st.columns(2)
                
                with col_edit:
                    if st.button(f"✏️ Modifier", key=f"edit_person_{person.id}"):
                        st.session_state[f"editing_person_{person.id}"] = True
                        st.rerun()
                
                with col_delete:
                    if st.button(f"🗑️ Supprimer", key=f"delete_person_{person.id}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_person_{person.id}"):
                            success = db.delete_person(person.id)
                            if success:
                                st.success(f"Personne '{person.name}' supprimée")
                                cleanup_person_session_state(person.id)
                                st.rerun()
                            else:
                                st.error("Erreur lors de la suppression")
                        else:
                            st.session_state[f"confirm_delete_person_{person.id}"] = True
                            st.warning("Cliquez à nouveau pour confirmer")
            
            # Modal d'édition
            if st.session_state.get(f"editing_person_{person.id}"):
                show_edit_person_modal(db, person)

def show_add_person(db):
    """Ajout d'une nouvelle personne"""
    st.subheader("➕ Ajouter une nouvelle personne")
    
    with st.form("add_person"):
        name = st.text_input("Nom complet*", placeholder="Jean Dupont")
        email = st.text_input("Email", placeholder="jean.dupont@example.com")
        psid = st.text_input("PSID Messenger", placeholder="1234567890")
        
        submitted = st.form_submit_button("Ajouter la personne", type="primary")
        
        if submitted:
            if not name:
                st.error("Le nom est requis")
            elif not email and not psid:
                st.error("Email ou PSID est requis")
            else:
                person = Person(
                    name=name,
                    email=email,
                    psid=psid
                )
                
                success = db.add_person(person)
                
                if success:
                    st.success(f"✅ Personne '{name}' ajoutée avec succès!")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de l'ajout (doublon possible)")

# Amélioration 1 : Page des rappels avec synchronisation obligatoire

def show_reminders_page():
    """Page de gestion des rappels avec synchronisation obligatoire"""
    st.header("🔔 Gestion des rappels")
    
    reminder_service = get_reminder_service()
    if not reminder_service:
        st.error("Service de rappels non disponible")
        return
    
    # État de synchronisation
    if 'last_sync_time' not in st.session_state:
        st.session_state.last_sync_time = None
    
    if 'sync_results' not in st.session_state:
        st.session_state.sync_results = None
    
    # Afficher l'état de la dernière synchronisation
    if st.session_state.last_sync_time:
        time_since_sync = datetime.now() - st.session_state.last_sync_time
        minutes_since = int(time_since_sync.total_seconds() / 60)
        
        if minutes_since < 5:
            st.success(f"✅ Synchronisé il y a {minutes_since} minute(s)")
        elif minutes_since < 60:
            st.warning(f"⚠️ Dernière synchronisation il y a {minutes_since} minutes")
        else:
            st.error(f"❌ Dernière synchronisation il y a plus d'une heure")
    else:
        st.warning("⚠️ Aucune synchronisation effectuée dans cette session")
    
    # Section Synchronisation (obligatoire avant prévisualisation)
    st.subheader("🔄 Synchronisation des réponses Google Forms")
    
    col_sync_all, col_sync_info = st.columns([1, 2])
    
    with col_sync_all:
        if st.button("🔄 Synchroniser maintenant", type="primary"):
            with st.spinner("Synchronisation en cours..."):
                sync_results = reminder_service.sync_all_forms(show_progress=True)
                st.session_state.last_sync_time = datetime.now()
                st.session_state.sync_results = sync_results
                
                if sync_results["status"] == "success":
                    st.success(f"✅ Synchronisation réussie: {sync_results['updated']} mises à jour, {sync_results['created']} créations")
                else:
                    st.error(f"❌ Erreur de synchronisation: {sync_results.get('error', 'Erreur inconnue')}")
    
    with col_sync_info:
        st.info("💡 La synchronisation récupère les dernières réponses depuis Google Forms pour éviter d'envoyer des rappels aux personnes qui ont déjà répondu.")
    
    st.divider()
    
    # Section Prévisualisation (nécessite synchronisation)
    st.subheader("👀 Prévisualisation des rappels")
    
    # Vérifier si synchronisé récemment
    can_preview = st.session_state.last_sync_time and (datetime.now() - st.session_state.last_sync_time).total_seconds() < 3600
    
    if not can_preview:
        st.warning("⚠️ Veuillez synchroniser avant de prévisualiser les rappels")
    
    cooldown_hours = st.slider("Délai minimum entre rappels (heures)", 1, 72, 24, 
                               help="Ne pas renvoyer de rappel si un a déjà été envoyé dans ce délai")
    
    col_preview, col_info = st.columns([1, 2])
    
    with col_preview:
        if st.button("🔍 Prévisualiser", disabled=not can_preview):
            preview = safe_service_call(
                lambda: reminder_service.preview_reminders(cooldown_hours=cooldown_hours),
                "Prévisualisation des rappels",
                fallback={"error": "Erreur de prévisualisation"}
            )
            
            if "error" in preview:
                st.error(preview["error"])
            else:
                st.session_state.preview_results = preview
                st.success(f"📧 {preview['total_reminders']} rappels seraient envoyés")
    
    with col_info:
        st.info("La prévisualisation montre qui recevrait un rappel en fonction des dernières données synchronisées")
    
    # Afficher les résultats de prévisualisation
    if 'preview_results' in st.session_state and st.session_state.preview_results:
        preview = st.session_state.preview_results
        
        for form_name, form_preview in preview["forms_preview"].items():
            if form_preview['eligible_for_reminder'] > 0:
                with st.expander(f"{form_name} - {form_preview['eligible_for_reminder']} rappel(s)"):
                    for person in form_preview["people"]:
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.write(f"👤 {person['name']}")
                        with col2:
                            st.write(f"📧 {person.get('email', 'Pas d\'email')}")
                        with col3:
                            if person.get('last_reminder'):
                                st.write(f"Dernier: {person['reminder_count']}x")
                            else:
                                st.write("Premier rappel")
    
    st.divider()
    
    # Section Envoi des rappels (nécessite synchronisation ET prévisualisation)
    st.subheader("📤 Envoi des rappels")
    
    can_send = (can_preview and 
                'preview_results' in st.session_state and 
                st.session_state.preview_results and 
                st.session_state.preview_results.get('total_reminders', 0) > 0)
    
    if not can_send:
        if not can_preview:
            st.warning("⚠️ Synchronisez d'abord les données")
        elif 'preview_results' not in st.session_state:
            st.warning("⚠️ Prévisualisez d'abord les rappels")
        elif st.session_state.preview_results.get('total_reminders', 0) == 0:
            st.info("✅ Aucun rappel à envoyer - Tout le monde a répondu ou a été rappelé récemment!")
        else:
            st.warning("⚠️ Prévisualisation requise avant envoi")
    
    # Options d'envoi
    st.subheader("⚙️ Options d'envoi")
    
    # Synchronisation automatique avant envoi
    auto_sync = st.checkbox(
        "🔄 Re-synchroniser juste avant l'envoi", 
        value=True,
        help="Recommandé : vérifie une dernière fois les réponses avant d'envoyer"
    )
    
    # Template personnalisé
    with st.expander("✏️ Message personnalisé"):
        custom_template = st.text_area(
            "Template de message (optionnel)",
            value=AppConstants.DEFAULT_REMINDER_TEMPLATE,
            help="Variables disponibles: {name}, {form_name}, {form_url}, {date_envoi}"
        )
    
    # Boutons d'envoi
    col_all, col_form = st.columns(2)
    
    with col_all:
        if st.button("📧 Envoyer tous les rappels", type="primary", disabled=not can_send):
            # Confirmation
            st.warning(f"⚠️ Vous allez envoyer {st.session_state.preview_results['total_reminders']} rappel(s)")
            
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Confirmer l'envoi", type="primary"):
                    with st.spinner("Envoi des rappels..."):
                        # Re-synchroniser si demandé
                        if auto_sync:
                            st.info("🔄 Re-synchronisation avant envoi...")
                            sync_results = reminder_service.sync_all_forms(show_progress=False)
                            if sync_results["status"] != "success":
                                st.error("❌ Échec de la re-synchronisation")
                                st.stop()
                        
                        # Envoyer les rappels
                        results = reminder_service.send_reminders_for_all_forms(
                            sync_first=False,  # On a déjà synchronisé
                            custom_message_template=custom_template if custom_template != AppConstants.DEFAULT_REMINDER_TEMPLATE else None,
                            cooldown_hours=cooldown_hours
                        )
                        
                        if results["status"] == "success":
                            st.success(f"✅ {results['total_sent']} rappels envoyés, {results['total_failed']} échecs")
                            
                            # Réinitialiser la prévisualisation
                            del st.session_state.preview_results
                            
                            # Détails par formulaire
                            with st.expander("Détails par formulaire"):
                                for form_name, form_results in results["reminder_results"].items():
                                    st.write(f"**{form_name}:** {form_results['sent']} envoyés, {form_results['failed']} échecs")
                        else:
                            st.error(f"❌ Erreur d'envoi: {results.get('error', 'Erreur inconnue')}")
            
            with col_cancel:
                if st.button("❌ Annuler"):
                    st.info("Envoi annulé")
    
    with col_form:
        # Sélection d'un formulaire spécifique
        db = get_database_manager()
        forms_data = db.get_active_forms()
        
        if forms_data:
            selected_form = st.selectbox(
                "Ou choisir un formulaire spécifique",
                options=[form for form, _ in forms_data],
                format_func=lambda f: f.name
            )
            
            if st.button("📧 Rappels pour ce formulaire", disabled=not can_preview):
                # Même logique de confirmation
                form_preview = st.session_state.preview_results['forms_preview'].get(selected_form.name, {})
                count = form_preview.get('eligible_for_reminder', 0)
                
                if count > 0:
                    st.warning(f"⚠️ {count} rappel(s) seront envoyés pour {selected_form.name}")
                    
                    if st.button("✅ Confirmer", key="confirm_single"):
                        with st.spinner("Envoi..."):
                            if auto_sync:
                                reminder_service.sync_specific_form(selected_form.id)
                            
                            result = reminder_service.send_reminders_for_form(
                                selected_form.id,
                                sync_first=False,
                                custom_message_template=custom_template if custom_template != AppConstants.DEFAULT_REMINDER_TEMPLATE else None,
                                cooldown_hours=cooldown_hours
                            )
                            
                            if result["status"] == "success":
                                st.success(f"✅ {result['sent']} rappels envoyés")
                            else:
                                st.error(f"❌ Erreur: {result.get('error', 'Erreur inconnue')}")
                else:
                    st.info("Aucun rappel à envoyer pour ce formulaire")

def show_sync_page():
    """Page de synchronisation"""
    st.header("🔄 Synchronisation Google Forms")
    
    reminder_service = get_reminder_service()
    google_service = get_google_forms_service()
    
    if not reminder_service or not google_service:
        st.error("Services non disponibles")
        return
    
    # Test de connexion
    st.subheader("🔧 Test des connexions")
    
    if st.button("🧪 Tester toutes les connexions"):
        test_all_connections_ui()
    
    # Synchronisation
    st.subheader("📥 Synchronisation des données")
    
    col_sync_all, col_sync_specific = st.columns(2)
    
    with col_sync_all:
        if st.button("🔄 Synchroniser tous les formulaires", type="primary"):
            sync_all_forms()
    
    with col_sync_specific:
        # Formulaire spécifique
        db = get_database_manager()
        forms_data = db.get_all_forms()
        
        if forms_data:
            selected_form = st.selectbox(
                "Synchroniser un formulaire",
                options=[form for form, _ in forms_data],
                format_func=lambda f: f.name
            )
            
            if st.button("🔄 Synchroniser ce formulaire"):
                sync_specific_form(selected_form.id)

def show_settings_page():
    """Page des paramètres"""
    st.header("⚙️ Paramètres et maintenance")
    
    db = get_database_manager()
    
    # Informations système
    st.subheader("ℹ️ Informations système")
    
    col_config, col_health = st.columns(2)
    
    with col_config:
        st.write("**Configuration:**")
        app_title = settings.app_title if settings else "STN-bot v2"
        debug_mode = settings.debug_mode if settings else False
        st.write(f"- App: {app_title}")
        st.write(f"- Debug: {debug_mode}")
        st.write(f"- Google App Script: ✅ Configuré")
        st.write(f"- Page Token: ✅ Configuré")
    
    with col_health:
        st.write("**Santé de la base:**")
        health = db.get_health_check()
        
        if health["status"] == "healthy":
            st.success("✅ Base de données saine")
        else:
            st.warning("⚠️ Problèmes détectés")
        
        st.write(f"- Personnes: {health.get('people_count', 0)}")
        st.write(f"- Pôles: {health.get('poles_count', 0)}")
        st.write(f"- Formulaires: {health.get('forms_count', 0)}")
        st.write(f"- Réponses: {health.get('responses_count', 0)}")
    
    # Cache
    st.subheader("🧹 Gestion du cache")
    
    col_clear_cache, col_clear_data = st.columns(2)
    
    with col_clear_cache:
        if st.button("🧹 Vider le cache"):
            clear_all_caches()
            st.success("Cache vidé!")
    
    with col_clear_data:
        if st.button("🗑️ DANGER: Effacer toutes les données", type="secondary"):
            if st.session_state.get("confirm_clear_all"):
                success = db.clear_all_data()
                if success:
                    st.success("Toutes les données effacées")
                    clear_all_caches()
                    st.rerun()
                else:
                    st.error("Erreur lors de l'effacement")
            else:
                st.session_state.confirm_clear_all = True
                st.error("⚠️ ATTENTION: Cela supprimera TOUTES les données! Cliquez à nouveau pour confirmer.")

# === FONCTIONS UTILITAIRES ===

def sync_all_forms():
    """Synchronise tous les formulaires"""
    reminder_service = get_reminder_service()
    
    if not reminder_service:
        st.error("Service non disponible")
        return
    
    with st.spinner("Synchronisation en cours..."):
        results = reminder_service.sync_all_forms(show_progress=True)
    
    if results["status"] == "success":
        st.success(f"✅ Synchronisation réussie: {results['updated']} mises à jour, {results['created']} créations")
    else:
        st.error(f"❌ Erreur de synchronisation: {results.get('error', 'Erreur inconnue')}")

def sync_specific_form(form_id: str):
    """Synchronise un formulaire spécifique"""
    reminder_service = get_reminder_service()
    
    if not reminder_service:
        st.error("Service non disponible")
        return
    
    with st.spinner("Synchronisation en cours..."):
        result = reminder_service.sync_specific_form(form_id)
    
    if result["status"] == "success":
        st.success(f"✅ Synchronisation réussie")
    else:
        st.error(f"❌ Erreur: {result.get('error', 'Erreur inconnue')}")

def send_all_reminders(custom_template: Optional[str] = None):
    """Envoie tous les rappels"""
    reminder_service = get_reminder_service()
    
    if not reminder_service:
        st.error("Service non disponible")
        return
    
    with st.spinner("Envoi des rappels..."):
        results = reminder_service.send_reminders_for_all_forms(
            sync_first=True,
            custom_message_template=custom_template
        )
    
    if results["status"] == "success":
        st.success(f"✅ {results['total_sent']} rappels envoyés, {results['total_failed']} échecs")
    else:
        st.error(f"❌ Erreur d'envoi: {results.get('error', 'Erreur inconnue')}")

def send_form_reminders(form_id: str, custom_template: Optional[str] = None):
    """Envoie des rappels pour un formulaire"""
    reminder_service = get_reminder_service()
    
    if not reminder_service:
        st.error("Service non disponible")
        return
    
    with st.spinner("Envoi des rappels..."):
        result = reminder_service.send_reminders_for_form(
            form_id,
            sync_first=True,
            custom_message_template=custom_template
        )
    
    if result["status"] == "success":
        st.success(f"✅ {result['form_name']}: {result['sent']} rappels envoyés")
    else:
        st.error(f"❌ Erreur: {result.get('error', 'Erreur inconnue')}")

def show_edit_form_modal(db, form, expected_people_ids):
    """Modal d'édition complète d'un formulaire"""
    st.subheader(f"✏️ Modifier {form.name}")
    
    with st.form(f"edit_form_{form.id}"):
        new_name = st.text_input("Nom du formulaire", value=form.name)
        new_google_form_id = st.text_input("Google Form ID", value=form.google_form_id)
        new_description = st.text_area("Description", value=form.description or "")
        new_date_envoi = st.date_input(
            "Date d'envoi", 
            value=form.date_envoi.date() if form.date_envoi else datetime.now().date()
        )
        
        # Sélection du pôle
        st.subheader("🏢 Pôle associé")
        poles = db.get_active_poles()
        
        if poles:
            current_pole_index = 0
            for i, pole in enumerate(poles):
                if pole.id == form.pole_id:
                    current_pole_index = i
                    break
            
            new_pole = st.selectbox(
                "Pôle",
                options=poles,
                index=current_pole_index,
                format_func=lambda p: p.display_name
            )
            new_pole_id = new_pole.id if new_pole else form.pole_id
        else:
            new_pole_id = form.pole_id
            st.warning("Aucun pôle disponible")
        
        new_is_active = st.checkbox("Formulaire actif", value=form.is_active)
        
        # Sélection des personnes avec groupes
        st.subheader("📋 Destinataires")
        
        tab_groups, tab_individual = st.tabs(["👥 Par groupes", "👤 Individuel"])
        
        # Initialiser avec les personnes actuelles
        selected_people_ids = set(expected_people_ids)
        
        with tab_groups:
            groups = db.get_all_groups()
            if groups:
                st.write("**Modifier via les groupes:**")
                
                for group in groups:
                    # Vérifier si ce groupe contient des personnes déjà sélectionnées
                    group_selected = any(pid in selected_people_ids for pid in group.member_ids)
                    
                    if st.checkbox(
                        f"{group.display_name} ({group.member_count} membres)",
                        key=f"edit_group_{group.id}",
                        value=group_selected,
                        help=group.description
                    ):
                        selected_people_ids.update(group.member_ids)
                    else:
                        # Retirer les membres du groupe
                        selected_people_ids -= set(group.member_ids)
        
        with tab_individual:
            people = db.get_all_people()
            if people:
                st.write("**Ajuster individuellement:**")
                
                cols = st.columns(2)
                for i, person in enumerate(people):
                    with cols[i % 2]:
                        default_checked = person.id in selected_people_ids
                        
                        if st.checkbox(
                            f"{person.name} ({person.email or 'pas d\'email'})",
                            key=f"edit_person_{person.id}",
                            value=default_checked
                        ):
                            selected_people_ids.add(person.id)
                        else:
                            selected_people_ids.discard(person.id)
        
        st.divider()
        st.info(f"📊 {len(selected_people_ids)} personne(s) sélectionnée(s)")
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button("💾 Sauvegarder", type="primary")
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ Annuler")
        
        if cancelled:
            del st.session_state[f"editing_form_{form.id}"]
            st.rerun()
        
        if submitted:
            if not new_name or not new_google_form_id:
                st.error("Nom et Google Form ID sont requis")
            elif not selected_people_ids:
                st.error("Sélectionnez au moins une personne")
            else:
                success = update_form_complete(
                    db, form.id, new_name, new_google_form_id, new_description,
                    datetime.combine(new_date_envoi, datetime.min.time()),
                    new_pole_id, new_is_active, list(selected_people_ids)
                )
                if success:
                    st.success(f"✅ Formulaire '{new_name}' mis à jour!")
                    del st.session_state[f"editing_form_{form.id}"]
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la mise à jour")

def update_form_complete(db, form_id: str, name: str, google_form_id: str, description: str, 
                         date_envoi: datetime, pole_id: str, is_active: bool, 
                         expected_people_ids: List[str]) -> bool:
    """Met à jour complètement un formulaire"""
    try:
        import sqlite3
        import json
        
        with sqlite3.connect(db.db_path) as conn:
            # Mettre à jour le formulaire
            cursor = conn.execute("""
                UPDATE forms 
                SET name = ?, google_form_id = ?, description = ?, date_envoi = ?, 
                    pole_id = ?, is_active = ?, expected_people_ids = ?, updated_at = ?
                WHERE id = ?
            """, (
                name, google_form_id, description, date_envoi.isoformat() if date_envoi else None,
                pole_id, is_active, json.dumps(expected_people_ids), 
                datetime.now().isoformat(), form_id
            ))
            
            if cursor.rowcount == 0:
                return False
            
            # Mettre à jour les réponses
            # D'abord, récupérer les réponses existantes
            existing_responses = conn.execute("""
                SELECT person_id, has_responded, response_date, last_reminder, reminder_count, notes
                FROM responses WHERE form_id = ?
            """, (form_id,)).fetchall()
            
            # Créer un dictionnaire des réponses existantes
            existing_data = {
                row[0]: {
                    'has_responded': row[1],
                    'response_date': row[2],
                    'last_reminder': row[3],
                    'reminder_count': row[4],
                    'notes': row[5]
                }
                for row in existing_responses
            }
            
            # Supprimer toutes les réponses actuelles
            conn.execute("DELETE FROM responses WHERE form_id = ?", (form_id,))
            
            # Recréer les réponses avec les nouvelles personnes
            from database.models import Response
            for person_id in expected_people_ids:
                response = Response(
                    form_id=form_id,
                    person_id=person_id,
                    has_responded=False
                )
                
                # Si cette personne avait déjà une réponse, conserver ses données
                if person_id in existing_data:
                    old_data = existing_data[person_id]
                    response.has_responded = old_data['has_responded']
                    response.response_date = datetime.fromisoformat(old_data['response_date']) if old_data['response_date'] else None
                    response.last_reminder = datetime.fromisoformat(old_data['last_reminder']) if old_data['last_reminder'] else None
                    response.reminder_count = old_data['reminder_count'] or 0
                    response.notes = old_data['notes'] or ""
                
                conn.execute("""
                    INSERT INTO responses 
                    (id, form_id, person_id, has_responded, response_date, last_reminder, 
                     reminder_count, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    response.id, response.form_id, response.person_id, response.has_responded,
                    response.response_date.isoformat() if response.response_date else None,
                    response.last_reminder.isoformat() if response.last_reminder else None,
                    response.reminder_count, response.notes,
                    response.created_at.isoformat(), response.updated_at.isoformat()
                ))
            
            conn.commit()
            return True
            
    except Exception as e:
        logger.error(f"Erreur mise à jour formulaire: {e}")
        return False


def delete_form_complete(db, form_id: str) -> bool:
    """Supprime complètement un formulaire et ses réponses"""
    try:
        import sqlite3
        
        with sqlite3.connect(db.db_path) as conn:
            # Les réponses sont supprimées automatiquement grâce à ON DELETE CASCADE
            cursor = conn.execute("DELETE FROM forms WHERE id = ?", (form_id,))
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Formulaire {form_id} supprimé avec toutes ses réponses")
            
            return success
            
    except Exception as e:
        logger.error(f"Erreur suppression formulaire: {e}")
        return False

def show_forms_list_by_pole(db, pole_id: str):
    """Liste des formulaires avec actions complètes"""
    forms_data = db.get_forms_by_pole(pole_id)
    
    if not forms_data:
        st.info("Aucun formulaire dans ce pôle")
        return
    
    for form, expected_people_ids in forms_data:
        with st.expander(f"{form.display_name} - {form.google_form_id[:15]}..."):
            col_info, col_actions = st.columns([2, 1])
            
            with col_info:
                st.write(f"**Description:** {form.description or 'Aucune'}")
                st.write(f"**Date d'envoi:** {form.date_envoi.strftime('%d/%m/%Y') if form.date_envoi else 'Non définie'}")
                st.write(f"**Statut:** {'🟢 Actif' if form.is_active else '🔴 Inactif'}")
                
                # Afficher le pôle
                pole = db.get_pole_by_id(form.pole_id)
                if pole:
                    st.write(f"**Pôle:** {pole.display_name}")
                
                st.write(f"**Personnes attendues:** {len(expected_people_ids)}")
                
                # Statistiques
                stats = db.get_form_stats(form.id)
                response_rate = (stats['responded']/stats['total']*100) if stats['total'] > 0 else 0
                st.write(f"**Réponses:** {stats['responded']}/{stats['total']} ({response_rate:.1f}%)")
            
            with col_actions:
                # Ligne 1 : Sync et Rappels
                col_sync, col_remind = st.columns(2)
                
                with col_sync:
                    if st.button(f"🔄 Sync", key=f"sync_{form.id}"):
                        sync_specific_form(form.id)
                
                with col_remind:
                    if st.button(f"🔔 Rappels", key=f"remind_{form.id}"):
                        send_form_reminders(form.id)
                
                # Ligne 2 : Liens
                st.link_button(f"🔗 Voir formulaire", form.url)
                st.link_button(f"📊 Voir réponses", form.edit_url)
                
                # Ligne 3 : Édition et Suppression
                col_edit, col_delete = st.columns(2)
                
                with col_edit:
                    if st.button(f"✏️ Modifier", key=f"edit_{form.id}"):
                        st.session_state[f"editing_form_{form.id}"] = True
                        st.rerun()
                
                with col_delete:
                    if st.button(f"🗑️ Supprimer", key=f"delete_{form.id}", type="secondary"):
                        # Demander confirmation
                        if st.session_state.get(f"confirm_delete_{form.id}"):
                            # Supprimer vraiment
                            success = delete_form_complete(db, form.id)
                            if success:
                                st.success(f"Formulaire '{form.name}' supprimé")
                                del st.session_state[f"confirm_delete_{form.id}"]
                                st.rerun()
                            else:
                                st.error("Erreur lors de la suppression")
                        else:
                            st.session_state[f"confirm_delete_{form.id}"] = True
                            st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")
            
            # Modal d'édition si nécessaire
            if st.session_state.get(f"editing_form_{form.id}"):
                show_edit_form_modal(db, form, expected_people_ids)

def show_edit_person_modal(db, person):
    """Modal d'édition d'une personne"""
    st.subheader(f"✏️ Modifier {person.name}")
    
    with st.form(f"edit_person_{person.id}"):
        new_name = st.text_input("Nom complet", value=person.name)
        new_email = st.text_input("Email", value=person.email or "")
        new_psid = st.text_input("PSID Messenger", value=person.psid or "")
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button("💾 Sauvegarder", type="primary")
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ Annuler")
        
        if cancelled:
            del st.session_state[f"editing_person_{person.id}"]
            st.rerun()
        
        if submitted:
            if not new_name:
                st.error("Le nom est requis")
            elif not new_email and not new_psid:
                st.error("Email ou PSID est requis")
            else:
                success = update_person(db, person.id, new_name, new_email, new_psid)
                if success:
                    st.success(f"✅ Personne '{new_name}' mise à jour!")
                    del st.session_state[f"editing_person_{person.id}"]
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la mise à jour")

def update_person(db, person_id: str, name: str, email: str, psid: str) -> bool:
    """Met à jour une personne dans la base"""
    try:
        import sqlite3
        from datetime import datetime
        
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute("""
                UPDATE people 
                SET name = ?, email = ?, psid = ?, updated_at = ?
                WHERE id = ?
            """, (name, email, psid, datetime.now().isoformat(), person_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
    except Exception as e:
        st.error(f"Erreur mise à jour personne: {e}")
        return False

def test_all_connections_ui():
    """Interface de test de toutes les connexions"""
    reminder_service = get_reminder_service()
    
    if not reminder_service:
        st.error("❌ Service de rappels non disponible")
        return
    
    results = safe_service_call(
        reminder_service.test_all_connections,
        "Test des connexions",
        fallback={"overall_status": "error"}
    )
    
    if results["overall_status"] == "success":
        st.success("✅ Toutes les connexions fonctionnent")
    else:
        st.warning("⚠️ Certaines connexions ont des problèmes")
    
    # Détails
    for service, result in results.items():
        if service == "overall_status":
            continue
        
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            if status == "success" or status == "healthy":
                st.success(f"✅ {service.title()}: {result.get('message', 'OK')}")
            else:
                st.error(f"❌ {service.title()}: {result.get('error', 'Erreur inconnue')}")
        else:
            st.warning(f"⚠️ {service.title()}: {str(result)}")

def cleanup_person_session_state(person_id: str):
    """Nettoie les états de session pour une personne"""
    keys_to_remove = []
    for key in st.session_state.keys():
        if isinstance(key, str) and person_id in key:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]

def cleanup_pole_session_state(pole_id: str):
    """Nettoie les états de session pour un pôle"""
    keys_to_remove = []
    for key in st.session_state.keys():
        if isinstance(key, str) and pole_id in key:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]

# === IMPORTATIONS UUID SI NÉCESSAIRE ===
import uuid

if __name__ == "__main__":
    main()