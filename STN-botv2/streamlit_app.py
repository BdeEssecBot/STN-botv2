# streamlit_app.py
"""
STN-bot v2 - Application Streamlit avec SQLite
Architecture persistante - Données sauvegardées automatiquement
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import os
from typing import Optional, Dict, Any, List

# Configuration de la page
st.set_page_config(
    page_title="STN-bot v2",
    page_icon="🔔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Imports après configuration
try:
    from config.settings import settings, AppConstants, validate_configuration
    from database.sqlite_manager import get_database_manager
    from database.models import Person, Form
    from services.reminder_service import get_reminder_service
    from services.google_forms_service import get_google_forms_service
    from services.messenger_service import get_messenger_service
except ImportError as e:
    st.error(f"Erreur d'import critique: {e}")
    st.markdown("Vérifiez que tous les modules sont installés : `pip install -r requirements.txt`")
    st.stop()

logger = logging.getLogger(__name__)

class STNBotV2:
    """Application STN-bot v2 avec persistance SQLite"""
    
    def __init__(self):
        self.db = get_database_manager()
        
        # Services optionnels
        self.reminder_service = None
        self.google_service = None
        self.messenger_service = None
        
        try:
            if settings:
                self.reminder_service = get_reminder_service()
                self.google_service = get_google_forms_service()
                self.messenger_service = get_messenger_service()
        except Exception as e:
            st.warning(f"Certains services non disponibles: {e}")
    
    def run(self):
        """Point d'entrée principal"""
        self._render_sidebar()
        self._render_main_content()
    
    def _render_sidebar(self):
        """Sidebar avec navigation et stats"""
        with st.sidebar:
            st.title("🔔 STN-bot v2")
            st.caption("Base SQLite persistante")
            
            # Navigation
            pages = [
                "📊 Dashboard",
                "👥 Personnes", 
                "📋 Formulaires",
                "🔔 Rappels",
                "🔄 Synchronisation",
                "⚙️ Administration"
            ]
            
            if 'current_page' not in st.session_state:
                st.session_state.current_page = pages[0]
            
            selected = st.selectbox("Navigation", pages, 
                                  index=pages.index(st.session_state.current_page))
            st.session_state.current_page = selected
            
            st.divider()
            
            # Stats rapides
            try:
                stats = self.db.get_statistics()
                st.metric("👥 Personnes", stats.total_people)
                st.metric("📝 Réponses", stats.total_responses)
                st.metric("🔔 En attente", stats.pending_reminders)
                
                if stats.last_sync:
                    time_diff = datetime.now() - stats.last_sync
                    sync_text = f"Il y a {time_diff.days}j" if time_diff.days > 0 else "Récente"
                    st.caption(f"🔄 Sync: {sync_text}")
            except Exception as e:
                st.error(f"Erreur stats: {e}")
    
    def _render_main_content(self):
        """Contenu principal selon la page"""
        page = st.session_state.current_page
        
        if page == "📊 Dashboard":
            self._render_dashboard()
        elif page == "👥 Personnes":
            self._render_people_page()
        elif page == "📋 Formulaires":
            self._render_forms_page()
        elif page == "🔔 Rappels":
            self._render_reminders_page()
        elif page == "🔄 Synchronisation":
            self._render_sync_page()
        elif page == "⚙️ Administration":
            self._render_admin_page()
    
    def _render_dashboard(self):
        """Dashboard principal"""
        st.header("📊 Dashboard STN-bot v2")
        
        try:
            # Statistiques globales
            stats = self.db.get_statistics()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Personnes", stats.total_people)
            with col2:
                st.metric("📝 Réponses totales", stats.total_responses)
            with col3:
                st.metric("🔔 En attente", stats.pending_reminders)
            with col4:
                st.metric("📈 Taux réussite", f"{stats.success_rate:.1f}%")
            
            # Tableau des formulaires avec stats
            st.subheader("📋 État des formulaires")
            
            forms_data = self.db.get_all_forms()
            if forms_data:
                chart_data = []
                table_data = []
                
                for form, expected_people_ids in forms_data:
                    if not form.is_active:
                        continue
                    
                    stats = self.db.get_form_stats(form.id)
                    
                    table_data.append({
                        "Formulaire": form.name,
                        "Statut": "🟢 Actif" if form.is_active else "🔴 Inactif",
                        "Réponses": f"{stats['responded']}/{stats['total']}",
                        "En attente": stats['pending'],
                        "Taux": f"{(stats['responded']/stats['total']*100) if stats['total'] > 0 else 0:.0f}%"
                    })
                    
                    chart_data.append({
                        "Formulaire": form.name,
                        "Ont répondu": stats['responded'],
                        "En attente": stats['pending']
                    })
                
                # Affichage tableau
                if table_data:
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Graphique
                    if chart_data:
                        chart_df = pd.DataFrame(chart_data)
                        fig = px.bar(chart_df, 
                                   x="Formulaire", 
                                   y=["Ont répondu", "En attente"],
                                   title="Réponses par formulaire",
                                   color_discrete_map={
                                       "Ont répondu": "#4CAF50",
                                       "En attente": "#FF9800"
                                   })
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucun formulaire créé")
            
            # Actions rapides
            st.subheader("⚡ Actions rapides")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Synchroniser", type="primary", disabled=not self.reminder_service):
                    if self.reminder_service:
                        self._handle_sync()
                    else:
                        st.error("Service de rappels non disponible")
            
            with col2:
                if st.button("📧 Aperçu rappels", disabled=not self.reminder_service):
                    if self.reminder_service:
                        self._handle_preview_reminders()
                    else:
                        st.error("Service de rappels non disponible")
            
            with col3:
                if st.button("🧪 Test connexions", disabled=not self.reminder_service):
                    if self.reminder_service:
                        self._handle_test_connections()
                    else:
                        st.error("Service de rappels non disponible")
        
        except Exception as e:
            st.error(f"Erreur dashboard: {e}")
    
    def _handle_sync(self):
        """Gère la synchronisation"""
        with st.spinner("Synchronisation..."):
            try:
                result = self.reminder_service.sync_all_forms()
                if result.get("status") == "success":
                    st.success(f"✅ Sync réussie: {result.get('updated', 0)} mises à jour")
                    st.rerun()
                else:
                    st.error(f"❌ Erreur: {result.get('error', 'Inconnu')}")
            except Exception as e:
                st.error(f"Erreur sync: {e}")
    
    def _handle_preview_reminders(self):
        """Aperçu des rappels"""
        try:
            # Compter les rappels nécessaires par formulaire
            total_reminders = 0
            form_details = []
            
            for form, _ in self.db.get_active_forms():
                non_responders = self.db.get_non_responders_for_form(form.id)
                ready_for_reminder = self.db.get_people_needing_reminders(form.id, 24)
                
                if ready_for_reminder:
                    total_reminders += len(ready_for_reminder)
                    form_details.append(f"📋 {form.name}: {len(ready_for_reminder)} rappels")
            
            if total_reminders > 0:
                st.success(f"📊 {total_reminders} rappels à envoyer")
                for detail in form_details:
                    st.info(detail)
            else:
                st.info("Aucun rappel nécessaire")
        except Exception as e:
            st.error(f"Erreur aperçu: {e}")
    
    def _handle_test_connections(self):
        """Test des connexions"""
        with st.spinner("Test connexions..."):
            try:
                results = self.reminder_service.test_all_connections()
                if results.get("overall_status") == "success":
                    st.success("✅ Toutes les connexions OK")
                else:
                    st.warning("⚠️ Certaines connexions ont des problèmes")
            except Exception as e:
                st.error(f"Erreur test: {e}")
    
    def _render_people_page(self):
        """Page gestion des personnes"""
        st.header("👥 Gestion des Personnes")
        
        tab1, tab2 = st.tabs(["📋 Liste", "➕ Ajouter"])
        
        with tab1:
            # Liste des personnes
            people = self.db.get_all_people()
            
            if people:
                # Filtres
                col1, col2 = st.columns([3, 1])
                with col1:
                    search = st.text_input("🔍 Rechercher", placeholder="Nom ou email...")
                with col2:
                    show_no_psid = st.checkbox("Sans PSID seulement")
                
                # Filtrage
                filtered_people = people
                if search:
                    search_lower = search.lower()
                    filtered_people = [p for p in people if 
                                     search_lower in p.name.lower() or 
                                     search_lower in (p.email or "").lower()]
                
                if show_no_psid:
                    filtered_people = [p for p in filtered_people if not p.psid]
                
                st.write(f"**{len(filtered_people)}** personne(s)")
                
                # Tableau
                if filtered_people:
                    data = []
                    for person in filtered_people:
                        # Compter ses réponses
                        total_forms = 0
                        responded_forms = 0
                        
                        for form, expected_people_ids in self.db.get_active_forms():
                            if person.id in expected_people_ids:
                                total_forms += 1
                                responses = self.db.get_responses_for_form(form.id)
                                for response in responses:
                                    if response.person_id == person.id and response.has_responded:
                                        responded_forms += 1
                                        break
                        
                        data.append({
                            "Nom": person.name,
                            "Email": person.email or "",
                            "PSID": "✅" if person.psid else "❌",
                            "Formulaires": f"{responded_forms}/{total_forms}",
                            "Créé": person.created_at.strftime("%d/%m/%Y")
                        })
                    
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Export
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        csv = df.to_csv(index=False)
                        st.download_button("📤 Export CSV", csv, "personnes.csv", "text/csv")
                    
                    # Statistiques
                    with col2:
                        with_psid = len([p for p in filtered_people if p.psid])
                        st.metric("Avec PSID", f"{with_psid}/{len(filtered_people)}")
            else:
                st.info("Aucune personne dans la base")
        
        with tab2:
            # Formulaire d'ajout
            st.subheader("Ajouter une personne")
            
            with st.form("add_person"):
                name = st.text_input("Nom complet*", placeholder="Jean Dupont")
                email = st.text_input("Email", placeholder="jean.dupont@example.com")
                psid = st.text_input("PSID Messenger", placeholder="123456789...")
                
                submitted = st.form_submit_button("➕ Ajouter", type="primary")
                
                if submitted:
                    if not name.strip():
                        st.error("Le nom est requis")
                    else:
                        person = Person(
                            name=name.strip(),
                            email=email.strip().lower() if email.strip() else None,
                            psid=psid.strip() if psid.strip() else None
                        )
                        
                        if self.db.add_person(person):
                            st.success(f"✅ {name} ajouté(e)")
                            st.rerun()
                        else:
                            st.error("❌ Erreur (doublon possible)")
    
    def _render_forms_page(self):
        """Page gestion des formulaires"""
        st.header("📋 Gestion des Formulaires")
        
        tab1, tab2 = st.tabs(["📋 Liste", "➕ Ajouter"])
        
        with tab1:
            # Liste des formulaires
            forms_data = self.db.get_all_forms()
            
            if forms_data:
                for form, expected_people_ids in forms_data:
                    with st.expander(f"📋 {form.name} ({'Actif' if form.is_active else 'Inactif'})"):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**Google Form ID:** {form.google_form_id}")
                            st.write(f"**Description:** {form.description}")
                            if form.date_envoi:
                                st.write(f"**Date envoi:** {form.date_envoi.strftime('%d/%m/%Y')}")
                            
                            # Personnes attendues
                            st.write(f"**Personnes attendues ({len(expected_people_ids)}):**")
                            if expected_people_ids:
                                expected_names = []
                                for person_id in expected_people_ids:
                                    person = self.db.get_person_by_id(person_id)
                                    if person:
                                        expected_names.append(person.name)
                                st.write(", ".join(expected_names))
                        
                        with col2:
                            stats = self.db.get_form_stats(form.id)
                            st.metric("Réponses", f"{stats['responded']}/{stats['total']}")
                            st.metric("En attente", stats['pending'])
                            
                            # Actions
                            if st.button(f"🔗 Ouvrir", key=f"open_{form.id}"):
                                st.markdown(f"[Ouvrir le formulaire]({form.url})")
                            
                            if st.button(f"📧 Rappels", key=f"remind_{form.id}", 
                                       disabled=not self.reminder_service):
                                if self.reminder_service:
                                    self._handle_send_reminders_for_form(form.id)
                                else:
                                    st.error("Service non disponible")
            else:
                st.info("Aucun formulaire créé")
        
        with tab2:
            # Formulaire d'ajout
            st.subheader("Créer un nouveau formulaire")
            
            # Récupérer les personnes disponibles
            all_people = self.db.get_all_people()
            
            if not all_people:
                st.warning("⚠️ Aucune personne dans la base. Ajoutez des personnes d'abord.")
                return
            
            with st.form("add_form"):
                name = st.text_input("Nom du formulaire*", placeholder="Enquête satisfaction Q1 2025")
                google_form_id = st.text_input("Google Form ID*", 
                                              placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
                description = st.text_area("Description", placeholder="Description optionnelle")
                
                col1, col2 = st.columns(2)
                with col1:
                    date_envoi = st.date_input("Date d'envoi")
                with col2:
                    is_active = st.checkbox("Formulaire actif", value=True)
                
                # NOUVELLE INTERFACE: Sélection des personnes attendues
                st.markdown("**👥 Personnes attendues pour ce formulaire:**")
                
                # Option pour sélectionner toutes les personnes
                select_all = st.checkbox("Sélectionner toutes les personnes", value=True)
                
                if select_all:
                    selected_people_ids = [p.id for p in all_people]
                    st.info(f"✅ Toutes les personnes sélectionnées ({len(all_people)})")
                else:
                    # Interface de sélection manuelle
                    people_options = {f"{p.name} ({p.email or 'sans email'})": p.id for p in all_people}
                    selected_people_names = st.multiselect(
                        "Choisir les personnes:",
                        options=list(people_options.keys()),
                        default=list(people_options.keys())  # Toutes sélectionnées par défaut
                    )
                    selected_people_ids = [people_options[name] for name in selected_people_names]
                
                st.write(f"**{len(selected_people_ids)}** personne(s) sélectionnée(s)")
                
                submitted = st.form_submit_button("➕ Créer le formulaire", type="primary")
                
                if submitted:
                    if not name.strip():
                        st.error("Le nom est requis")
                    elif not google_form_id.strip():
                        st.error("Le Google Form ID est requis")
                    elif not selected_people_ids:
                        st.error("Sélectionnez au moins une personne")
                    else:
                        form = Form(
                            name=name.strip(),
                            google_form_id=google_form_id.strip(),
                            description=description.strip(),
                            date_envoi=datetime.combine(date_envoi, datetime.min.time()) if date_envoi else None,
                            is_active=is_active
                        )
                        
                        if self.db.add_form(form, selected_people_ids):
                            st.success(f"✅ Formulaire '{name}' créé avec {len(selected_people_ids)} personnes attendues")
                            st.rerun()
                        else:
                            st.error("❌ Erreur lors de la création (doublon possible)")
    
    def _handle_send_reminders_for_form(self, form_id: str):
        """Envoie des rappels pour un formulaire"""
        with st.spinner("Envoi rappels..."):
            try:
                result = self.reminder_service.send_reminders_for_form(form_id)
                if result.get("status") == "success":
                    st.success(f"✅ {result.get('sent', 0)} rappels envoyés")
                else:
                    st.error(f"❌ {result.get('error', 'Erreur inconnue')}")
            except Exception as e:
                st.error(f"Erreur envoi: {e}")
    
    def _render_reminders_page(self):
        """Page des rappels"""
        st.header("🔔 Gestion des Rappels")
        
        if not self.reminder_service:
            st.error("Service de rappels non disponible")
            return
        
        tab1, tab2 = st.tabs(["📊 Aperçu", "📧 Envoi"])
        
        with tab1:
            st.subheader("Aperçu des rappels nécessaires")
            
            forms_data = self.db.get_active_forms()
            if not forms_data:
                st.info("Aucun formulaire actif")
                return
            
            total_reminders = 0
            
            for form, expected_people_ids in forms_data:
                non_responders = self.db.get_non_responders_for_form(form.id)
                ready_for_reminder = self.db.get_people_needing_reminders(form.id, 24)
                
                with st.expander(f"📋 {form.name} ({len(ready_for_reminder)} rappels possibles)"):
                    if ready_for_reminder:
                        total_reminders += len(ready_for_reminder)
                        
                        # Tableau des personnes
                        reminder_data = []
                        for person, response in ready_for_reminder:
                            reminder_data.append({
                                "Nom": person.name,
                                "Email": person.email or "",
                                "PSID": "✅" if person.psid else "❌",
                                "Dernière rappel": response.last_reminder.strftime("%d/%m %H:%M") if response.last_reminder else "Jamais",
                                "Nb rappels": response.reminder_count
                            })
                        
                        df = pd.DataFrame(reminder_data)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("Aucun rappel nécessaire pour ce formulaire")
            
            if total_reminders > 0:
                st.success(f"📊 **Total: {total_reminders} rappels à envoyer**")
            else:
                st.info("Aucun rappel nécessaire actuellement")
        
        with tab2:
            st.subheader("Envoi de rappels")
            
            with st.form("send_reminders"):
                # Sélection du mode
                send_all = st.radio(
                    "Mode d'envoi:",
                    ["Tous les formulaires", "Formulaire spécifique"]
                )
                
                selected_form_id = None
                if send_all == "Formulaire spécifique":
                    form_options = {}
                    for form, _ in self.db.get_active_forms():
                        form_options[form.name] = form.id
                    
                    if form_options:
                        selected_form_name = st.selectbox("Formulaire:", list(form_options.keys()))
                        selected_form_id = form_options[selected_form_name]
                    else:
                        st.warning("Aucun formulaire actif")
                
                # Options
                col1, col2 = st.columns(2)
                with col1:
                    sync_first = st.checkbox("Synchroniser avant envoi", value=True)
                with col2:
                    cooldown = st.number_input("Délai entre rappels (h)", min_value=1, value=24)
                
                # Template de message
                default_template = """Hello {name},

Petit rappel pour remplir le formulaire *{form_name}*.

Lien: {form_url}

Merci !"""
                
                custom_template = st.text_area(
                    "Template de message (optionnel):",
                    placeholder=default_template,
                    help="Variables: {name}, {form_name}, {form_url}, {date_envoi}"
                )
                
                submitted = st.form_submit_button("📧 Envoyer les rappels", type="primary")
                
                if submitted:
                    self._handle_send_reminders(send_all, selected_form_id, sync_first, 
                                              custom_template, cooldown)
    
    def _handle_send_reminders(self, send_all: str, selected_form_id: Optional[str], 
                              sync_first: bool, custom_template: str, cooldown: int):
        """Gère l'envoi des rappels"""
        with st.spinner("Envoi en cours..."):
            try:
                template = custom_template.strip() if custom_template.strip() else None
                
                if send_all == "Tous les formulaires":
                    result = self.reminder_service.send_reminders_for_all_forms(
                        sync_first=sync_first,
                        custom_message_template=template,
                        cooldown_hours=cooldown
                    )
                    if result.get("status") == "success":
                        st.success(f"✅ {result.get('total_sent', 0)} rappels envoyés au total")
                        for form_name, form_result in result.get("reminder_results", {}).items():
                            if form_result.get('sent', 0) > 0:
                                st.info(f"📋 {form_name}: {form_result['sent']} rappels")
                    else:
                        st.error(f"❌ {result.get('error', 'Erreur inconnue')}")
                
                else:  # Formulaire spécifique
                    if selected_form_id:
                        result = self.reminder_service.send_reminders_for_form(
                            selected_form_id,
                            sync_first=sync_first,
                            custom_message_template=template,
                            cooldown_hours=cooldown
                        )
                        if result.get("status") == "success":
                            st.success(f"✅ {result.get('sent', 0)} rappels envoyés")
                        else:
                            st.error(f"❌ {result.get('error', 'Erreur inconnue')}")
                    else:
                        st.error("Formulaire non sélectionné")
            except Exception as e:
                st.error(f"Erreur envoi: {e}")
    
    def _render_sync_page(self):
        """Page de synchronisation"""
        st.header("🔄 Synchronisation Google Forms")
        
        if not self.reminder_service or not self.google_service:
            st.error("Services de synchronisation non disponibles")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Synchronisation complète")
            st.caption("Synchronise tous les formulaires actifs")
            
            if st.button("🔄 Synchroniser tout", type="primary"):
                self._handle_sync()
        
        with col2:
            st.subheader("Tests de connexion")
            
            if st.button("🧪 Test Google Forms"):
                with st.spinner("Test Google Forms..."):
                    try:
                        result = self.google_service.test_connection()
                        if result.get("status") == "success":
                            st.success("✅ Google Forms OK")
                        else:
                            st.error(f"❌ Google Forms: {result.get('message', 'Erreur')}")
                    except Exception as e:
                        st.error(f"Erreur test Google: {e}")
            
            if st.button("🧪 Test Messenger"):
                with st.spinner("Test Messenger..."):
                    try:
                        result = self.messenger_service.test_connection()
                        if result.get("status") == "success":
                            st.success("✅ Messenger OK")
                        else:
                            st.error(f"❌ Messenger: {result.get('message', 'Erreur')}")
                    except Exception as e:
                        st.error(f"Erreur test Messenger: {e}")
        
        # Statut de synchronisation
        st.divider()
        st.subheader("📊 Statut")
        
        stats = self.db.get_statistics()
        if stats.last_sync:
            time_diff = datetime.now() - stats.last_sync
            sync_text = f"Il y a {time_diff.days} jour(s)" if time_diff.days > 0 else "Récente"
            st.info(f"🔄 Dernière synchronisation: {sync_text}")
        else:
            st.warning("🟡 Aucune synchronisation effectuée")
    
    def _render_admin_page(self):
        """Page d'administration"""
        st.header("⚙️ Administration")
        
        tab1, tab2 = st.tabs(["📊 Système", "🗄️ Données"])
        
        with tab1:
            # Informations système
            st.subheader("Informations système")
            
            health = self.db.get_health_check()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 Base de données**")
                if health["status"] == "healthy":
                    st.success("✅ Base SQLite saine")
                else:
                    st.warning("⚠️ Problèmes détectés")
                
                st.metric("Personnes", health["people_count"])
                st.metric("Formulaires", health["forms_count"])
                st.metric("Réponses", health["responses_count"])
            
            with col2:
                st.markdown("**⚙️ Configuration**")
                if settings:
                    st.info(f"App: {getattr(settings, 'app_title', 'N/A')}")
                    st.info(f"Debug: {'✅' if getattr(settings, 'debug_mode', False) else '❌'}")
                else:
                    st.error("Configuration non chargée")
                
                st.info(f"DB Version: {health.get('database_version', 'N/A')}")
        
        with tab2:
            # Gestion des données
            st.subheader("Gestion des données")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**⚠️ Actions dangereuses**")
                st.warning("Ces actions sont irréversibles!")
                
                if st.button("🗑️ Vider toute la base", type="secondary"):
                    if st.checkbox("Je confirme vouloir supprimer toutes les données"):
                        if self.db.clear_all_data():
                            st.success("🗑️ Base de données vidée")
                            st.rerun()
                        else:
                            st.error("❌ Erreur lors de la suppression")
            
            with col2:
                st.markdown("**📊 Statistiques détaillées**")
                
                # Afficher les stats détaillées
                try:
                    # Personnes avec/sans PSID
                    people = self.db.get_all_people()
                    with_psid = len([p for p in people if p.psid])
                    without_psid = len(people) - with_psid
                    
                    st.write(f"👥 Personnes avec PSID: {with_psid}")
                    st.write(f"👥 Personnes sans PSID: {without_psid}")
                    
                    # Formulaires actifs/inactifs
                    forms_data = self.db.get_all_forms()
                    active_forms = len([f for f, _ in forms_data if f.is_active])
                    inactive_forms = len(forms_data) - active_forms
                    
                    st.write(f"📋 Formulaires actifs: {active_forms}")
                    st.write(f"📋 Formulaires inactifs: {inactive_forms}")
                
                except Exception as e:
                    st.error(f"Erreur stats: {e}")


def main():
    """Point d'entrée principal de l'application"""
    try:
        # Vérifier la configuration de base
        if not settings:
            st.error("⚠️ Configuration manquante")
            st.markdown("""
            **Créez un fichier `.env` avec :**
            ```
            PAGE_TOKEN=votre_token_facebook
            GOOGLE_APP_SCRIPT_URL=votre_url_app_script
            APP_TITLE=STN-bot v2
            DEBUG_MODE=false
            ```
            """)
            return
        
        # Lancer l'application
        app = STNBotV2()
        app.run()
        
    except Exception as e:
        st.error(f"💥 Erreur critique: {e}")
        logger.error(f"Erreur critique main: {e}")
        
        # Mode debug
        if settings and getattr(settings, 'debug_mode', False):
            st.exception(e)


if __name__ == "__main__":
    main()