# streamlit_app.py
"""STN-bot v2 - Application Streamlit principale avec support des pôles"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Literal

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

# Logger
logger = logging.getLogger(__name__)

def main():
    """Point d'entrée principal de l'application"""
    
    # Configuration de la page avec valeurs explicites et types corrects
    config = AppConstants.get_streamlit_config()
    
    # Types explicites pour satisfaire Pylance
    layout: Literal["centered", "wide"] = "wide"
    initial_sidebar_state: Literal["auto", "expanded", "collapsed"] = "expanded"
    
    st.set_page_config(
        page_title=config["page_title"],
        page_icon=config["page_icon"],
        layout=layout,
        initial_sidebar_state=initial_sidebar_state
    )
    
    # Vérification de la configuration
    if not validate_configuration():
        st.error("❌ Configuration invalide - vérifiez votre fichier .env")
        st.stop()
    
    # Titre principal avec vérification
    app_icon = settings.app_icon if settings else "🔔"
    app_title = settings.app_title if settings else "STN-bot v2"
    st.title(f"{app_icon} {app_title}")
    
    # Sidebar pour la navigation
    with st.sidebar:
        st.header("Navigation")
        
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
        st.divider()
        show_service_status()
    
    # Routing vers les pages
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

def show_forms_list_by_pole(db, pole_id: str):
    """Liste des formulaires filtrés par pôle"""
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
                st.write(f"**Personnes attendues:** {len(expected_people_ids)}")
                
                # Statistiques avec détails des répondants
                stats = db.get_form_stats(form.id)
                response_rate = (stats['responded']/stats['total']*100) if stats['total'] > 0 else 0
                st.write(f"**Réponses:** {stats['responded']}/{stats['total']} ({response_rate:.1f}%)")
                
                # Afficher qui a répondu
                if stats['responded'] > 0:
                    responders = get_form_responders(db, form.id)
                    if responders:
                        st.write("**Ont répondu:**")
                        for person, response in responders:
                            response_date = response.response_date.strftime('%d/%m/%Y à %H:%M') if response.response_date else 'Date inconnue'
                            st.write(f"  ✅ {person.name} - {response_date}")
                
                # Afficher qui n'a pas répondu
                if stats['pending'] > 0:
                    non_responders = get_form_non_responders(db, form.id)
                    if non_responders:
                        with st.expander(f"❌ {stats['pending']} personne(s) n'ont pas répondu"):
                            for person, response in non_responders:
                                last_reminder = response.last_reminder.strftime('%d/%m/%Y') if response.last_reminder else 'Jamais'
                                st.write(f"  - {person.name} - Dernier rappel: {last_reminder}")
            
            with col_actions:
                col_sync, col_remind = st.columns(2)
                
                with col_sync:
                    if st.button(f"🔄 Sync", key=f"sync_{form.id}"):
                        sync_specific_form(form.id)
                
                with col_remind:
                    if st.button(f"🔔 Rappels", key=f"remind_{form.id}"):
                        send_form_reminders(form.id)
                
                st.link_button(f"🔗 Voir le formulaire", form.url)
                st.link_button(f"✏️ Éditer/Voir réponses", form.edit_url)
                
                # Actions d'édition
                col_edit, col_delete = st.columns(2)
                
                with col_edit:
                    if st.button(f"✏️ Modifier", key=f"edit_{form.id}"):
                        st.session_state[f"editing_form_{form.id}"] = True
                        st.rerun()
                
                with col_delete:
                    if st.button(f"🗑️ Supprimer", key=f"delete_{form.id}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_form_{form.id}"):
                            success = delete_form(db, form.id)
                            if success:
                                st.success(f"Formulaire '{form.name}' supprimé")
                                st.rerun()
                            else:
                                st.error("Erreur lors de la suppression")
                        else:
                            st.session_state[f"confirm_delete_form_{form.id}"] = True
                            st.warning("Cliquez à nouveau pour confirmer")
            
            # Modal d'édition
            if st.session_state.get(f"editing_form_{form.id}"):
                show_edit_form_modal_with_pole(db, form, expected_people_ids)

def show_create_form_with_pole(db, pole_id: str):
    """Création d'un nouveau formulaire dans un pôle"""
    st.subheader("➕ Créer un nouveau formulaire")
    
    with st.form("create_form_with_pole"):
        name = st.text_input("Nom du formulaire*", placeholder="ex: Enquête satisfaction Q4")
        google_form_id = st.text_input("Google Form ID*", placeholder="1FAIpQLSe...")
        description = st.text_area("Description", placeholder="Description du formulaire...")
        date_envoi = st.date_input("Date d'envoi", value=datetime.now().date())
        
        # Sélection des personnes attendues
        people = db.get_all_people()
        if people:
            st.subheader("Personnes attendues")
            selected_people = st.multiselect(
                "Sélectionner les personnes qui doivent répondre",
                options=[p.id for p in people],
                format_func=lambda pid: next((p.name + f" ({p.email})" for p in people if p.id == pid), pid)
            )
        else:
            st.warning("Aucune personne dans la base. Ajoutez des personnes d'abord.")
            selected_people = []
        
        submitted = st.form_submit_button("Créer le formulaire", type="primary")
        
        if submitted:
            if not name or not google_form_id:
                st.error("Nom et Google Form ID sont requis")
            elif not selected_people:
                st.error("Sélectionnez au moins une personne")
            else:
                form = Form(
                    name=name,
                    google_form_id=google_form_id,
                    pole_id=pole_id,  # Associer au pôle
                    description=description,
                    date_envoi=datetime.combine(date_envoi, datetime.min.time())
                )
                
                success = db.add_form(form, selected_people)
                
                if success:
                    st.success(f"✅ Formulaire '{name}' créé avec succès!")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la création du formulaire")

def show_edit_form_modal_with_pole(db, form, expected_people_ids):
    """Modal d'édition d'un formulaire avec sélection du pôle"""
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
        
        new_is_active = st.checkbox("Formulaire actif", value=form.is_active)
        
        # Sélection des personnes
        all_people = db.get_all_people()
        if all_people:
            st.subheader("Personnes attendues")
            new_selected_people = st.multiselect(
                "Sélectionner les personnes qui doivent répondre",
                options=[p.id for p in all_people],
                default=expected_people_ids,
                format_func=lambda pid: next((p.name + f" ({p.email})" for p in all_people if p.id == pid), pid)
            )
        else:
            new_selected_people = expected_people_ids
        
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
            elif not new_selected_people:
                st.error("Sélectionnez au moins une personne")
            else:
                success = update_form_with_pole(
                    db, form.id, new_name, new_google_form_id, new_description,
                    datetime.combine(new_date_envoi, datetime.min.time()),
                    new_pole_id, new_is_active, new_selected_people
                )
                if success:
                    st.success(f"✅ Formulaire '{new_name}' mis à jour!")
                    del st.session_state[f"editing_form_{form.id}"]
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la mise à jour")

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
    
    # Tableau des personnes avec sélection
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
                # Actions d'édition
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
                                # Nettoyer les états de session
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

def show_reminders_page():
    """Page de gestion des rappels"""
    st.header("🔔 Gestion des rappels")
    
    reminder_service = get_reminder_service()
    if not reminder_service:
        st.error("Service de rappels non disponible")
        return
    
    # Prévisualisation
    st.subheader("👀 Prévisualisation des rappels")
    
    cooldown_hours = st.slider("Délai entre rappels (heures)", 1, 72, 24)
    
    if st.button("🔍 Prévisualiser"):
        preview = safe_service_call(
            lambda: reminder_service.preview_reminders(cooldown_hours=cooldown_hours),
            "Prévisualisation des rappels",
            fallback={"error": "Erreur de prévisualisation"}
        )
        
        if "error" in preview:
            st.error(preview["error"])
        else:
            st.info(f"📧 {preview['total_reminders']} rappels seraient envoyés")
            
            for form_name, form_preview in preview["forms_preview"].items():
                with st.expander(f"{form_name} - {form_preview['eligible_for_reminder']} rappels"):
                    for person in form_preview["people"]:
                        st.write(f"• {person['name']} ({person.get('email', 'Pas d\'email')})")
    
    # Envoi des rappels
    st.subheader("📤 Envoi des rappels")
    
    # Template personnalisé
    with st.expander("✏️ Message personnalisé"):
        custom_template = st.text_area(
            "Template de message (optionnel)",
            value=AppConstants.DEFAULT_REMINDER_TEMPLATE,
            help="Variables disponibles: {name}, {form_name}, {form_url}, {date_envoi}"
        )
    
    col_all, col_form = st.columns(2)
    
    with col_all:
        if st.button("📧 Envoyer tous les rappels", type="primary"):
            send_all_reminders(custom_template if custom_template != AppConstants.DEFAULT_REMINDER_TEMPLATE else None)
    
    with col_form:
        # Sélection d'un formulaire spécifique
        db = get_database_manager()
        forms_data = db.get_active_forms()
        
        if forms_data:
            selected_form = st.selectbox(
                "Formulaire spécifique",
                options=[form for form, _ in forms_data],
                format_func=lambda f: f.name
            )
            
            if st.button("📧 Rappels pour ce formulaire"):
                send_form_reminders(selected_form.id, custom_template if custom_template != AppConstants.DEFAULT_REMINDER_TEMPLATE else None)

def show_sync_page():
    """Page de synchronisation"""
    st.header("🔄 Synchronisation Google Forms")
    
    reminder_service = get_reminder_service()
    google_service = get_google_forms_service()
    
    if not reminder_service or not google_service:
        st.error("Services non disponibles")
        return
    
    # Test de connexion avec diagnostic approfondi
    st.subheader("🔧 Test des connexions")
    
    col_test_all, col_test_google = st.columns(2)
    
    with col_test_all:
        if st.button("🧪 Tester toutes les connexions"):
            test_all_connections_ui()
    
    with col_test_google:
        if st.button("🔍 Diagnostic Google Forms"):
            diagnose_google_forms_detailed()
    
    # Test avec un formulaire spécifique
    st.subheader("🧪 Test spécifique")
    test_form_id = st.text_input(
        "Tester avec un Google Form ID spécifique",
        placeholder="1FAIpQLSe...",
        help="Entrez un Google Form ID pour tester la récupération des réponses"
    )
    
    if st.button("🔎 Tester ce formulaire") and test_form_id:
        test_specific_google_form(test_form_id)
    
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

# Fonctions utilitaires pour les actions

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
    """Synchronise un formulaire spécifique - interface simplifiée"""
    reminder_service = get_reminder_service()
    
    if not reminder_service:
        st.error("Service non disponible")
        return
    
    # Synchronisation avec spinner simple
    with st.spinner("Synchronisation en cours..."):
        result = reminder_service.sync_specific_form(form_id)
    
    # Affichage du résultat uniquement
    if result["status"] == "success":
        st.success(f"✅ Synchronisation réussie")
        
        # Statistiques finales
        db = get_database_manager()
        stats = db.get_form_stats(form_id)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mises à jour", result.get('updated', 0))
        with col2:
            st.metric("Créations", result.get('created', 0))  
        with col3:
            st.metric("Taux de réponse", f"{(stats['responded']/stats['total']*100) if stats['total'] > 0 else 0:.1f}%")
            
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
        
        # Détails par formulaire
        with st.expander("Détails par formulaire"):
            for form_name, form_results in results["reminder_results"].items():
                st.write(f"**{form_name}:** {form_results['sent']} envoyés, {form_results['failed']} échecs")
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

# Fonctions d'édition et suppression

def show_edit_person_modal(db, person: Person):
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
                    st.error("❌ Erreur lors de la mise à jour (doublon possible)")

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

def update_form_with_pole(db, form_id: str, name: str, google_form_id: str, description: str, 
                         date_envoi: datetime, pole_id: str, is_active: bool, expected_people_ids: List[str]) -> bool:
    """Met à jour un formulaire avec pôle dans la base"""
    try:
        import sqlite3
        import json
        from datetime import datetime
        
        with sqlite3.connect(db.db_path) as conn:
            # Mettre à jour le formulaire avec pole_id
            cursor = conn.execute("""
                UPDATE forms 
                SET name = ?, google_form_id = ?, description = ?, date_envoi = ?, 
                    pole_id = ?, is_active = ?, expected_people_ids = ?, updated_at = ?
                WHERE id = ?
            """, (
                name, google_form_id, description, date_envoi.isoformat(),
                pole_id, is_active, json.dumps(expected_people_ids), datetime.now().isoformat(),
                form_id
            ))
            
            # Mettre à jour les réponses (supprimer les anciennes, créer les nouvelles)
            conn.execute("DELETE FROM responses WHERE form_id = ?", (form_id,))
            
            # Créer les nouvelles réponses
            from database.models import Response
            for person_id in expected_people_ids:
                response = Response(
                    form_id=form_id,
                    person_id=person_id,
                    has_responded=False
                )
                conn.execute("""
                    INSERT INTO responses (id, form_id, person_id, has_responded, 
                                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    response.id, response.form_id, response.person_id, response.has_responded,
                    response.created_at.isoformat(), response.updated_at.isoformat()
                ))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
    except Exception as e:
        logger.error(f"Erreur mise à jour formulaire: {e}")
        return False

def delete_form(db, form_id: str) -> bool:
    """Supprime un formulaire"""
    try:
        import sqlite3
        
        with sqlite3.connect(db.db_path) as conn:
            # Les réponses sont supprimées automatiquement (CASCADE)
            cursor = conn.execute("DELETE FROM forms WHERE id = ?", (form_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
    except Exception as e:
        st.error(f"Erreur suppression formulaire: {e}")
        return False

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

# Fonctions de diagnostic Google Forms

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
        
        # Vérification du type de result pour éviter l'erreur
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            if status == "success" or status == "healthy":
                st.success(f"✅ {service.title()}: {result.get('message', 'OK')}")
            else:
                st.error(f"❌ {service.title()}: {result.get('error', 'Erreur inconnue')}")
        else:
            # Si result n'est pas un dict, l'afficher tel quel
            st.warning(f"⚠️ {service.title()}: {str(result)}")

def diagnose_google_forms_detailed():
    """Diagnostic approfondi de Google Forms"""
    st.subheader("🔍 Diagnostic Google Forms détaillé")
    
    google_service = get_google_forms_service()
    if not google_service:
        st.error("❌ Service Google Forms non disponible")
        return
    
    with st.spinner("Diagnostic en cours..."):
        # Test de base
        basic_test = google_service.test_connection()
        
        st.write("**Test de base:**")
        if basic_test["status"] == "success":
            st.success(f"✅ {basic_test['message']}")
        else:
            st.error(f"❌ {basic_test['message']}")
        
        # Afficher l'URL utilisée
        st.write(f"**URL App Script:** `{google_service.app_script_url[:100]}...`")
        
        # Test avec les formulaires existants
        st.write("**Test avec formulaires existants:**")
        db = get_database_manager()
        forms_data = db.get_all_forms()
        
        if forms_data:
            for form, _ in forms_data[:3]:  # Tester les 3 premiers seulement
                with st.expander(f"Test: {form.name}"):
                    try:
                        responses = google_service.get_form_responses(form.google_form_id)
                        st.success(f"✅ {len(responses)} réponses trouvées")
                        
                        if responses:
                            st.write("**Exemple de réponse:**")
                            st.json(responses[0])
                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
        else:
            st.info("Aucun formulaire à tester")

def test_specific_google_form(form_id: str):
    """Test d'un formulaire Google spécifique avec diagnostic détaillé"""
    google_service = get_google_forms_service()
    if not google_service:
        st.error("Service non disponible")
        return
    
    with st.spinner(f"Test du formulaire {form_id[:15]}..."):
        try:
            # Validation du format
            if not google_service.validate_form_id(form_id):
                st.error("❌ Format de Google Form ID invalide")
                return
            
            # Test direct de l'App Script - NOUVEAU
            st.subheader("🔍 Réponse brute de l'App Script")
            try:
                import requests
                url = f"{google_service.app_script_url}?formId={form_id}"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                raw_data = response.json()
                
                st.write("**Réponse JSON brute:**")
                st.json(raw_data)
                
                # Analyser la structure
                st.write("**Analyse de la structure:**")
                if 'error' in raw_data:
                    st.error(f"❌ Erreur App Script: {raw_data['error']}")
                    return
                
                st.write(f"- **Emails trouvés:** {len(raw_data.get('emails', []))}")
                st.write(f"- **People trouvés:** {len(raw_data.get('people', []))}")
                
                if raw_data.get('people'):
                    first_person = raw_data['people'][0]
                    st.write(f"- **Structure d'une personne:** {list(first_person.keys())}")
                    st.json(first_person)
                
            except Exception as e:
                st.error(f"❌ Erreur appel direct App Script: {e}")
                return
            
            # Test via le service Python
            st.subheader("🔄 Test via le service Python")
            responses = google_service.get_form_responses(form_id)
            
            st.success(f"✅ Service Python: {len(responses)} réponses traitées")
            
            if responses:
                st.write("**Première réponse traitée:**")
                st.json(responses[0])
                
                # Statistiques
                emails = [r.get('email') for r in responses if r.get('email')]
                st.write(f"**Emails uniques:** {len(set(emails))}")
                
                detailed_responses = [r for r in responses if r.get('firstName') or r.get('lastName')]
                st.write(f"**Réponses détaillées:** {len(detailed_responses)}")
                
                with_timestamps = [r for r in responses if r.get('timestamp')]
                st.write(f"**Avec timestamps:** {len(with_timestamps)}")
            else:
                st.warning("⚠️ Aucune réponse traitée par le service Python")
                
        except Exception as e:
            st.error(f"❌ Erreur lors du test: {e}")
            import traceback
            st.code(traceback.format_exc())

# Fonctions helper pour les répondants

def get_form_responders(db, form_id: str):
    """Récupère les personnes qui ont répondu à un formulaire"""
    try:
        responses = db.get_responses_for_form(form_id)
        responders = []
        
        for response in responses:
            if response.has_responded:
                person = db.get_person_by_id(response.person_id)
                if person:
                    responders.append((person, response))
        
        return responders
    except Exception as e:
        logger.error(f"Erreur récupération répondants: {e}")
        return []

def get_form_non_responders(db, form_id: str):
    """Récupère les personnes qui n'ont pas répondu à un formulaire"""
    try:
        return db.get_non_responders_for_form(form_id)
    except Exception as e:
        logger.error(f"Erreur récupération non-répondants: {e}")
        return []

if __name__ == "__main__":
    main()