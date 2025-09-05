import streamlit as st
from config import config
from database import Database
from services import GoogleFormsService, MessengerService, ReminderService
from models import Person, Form, Pole, Group

class STNBot:
    """Application principale complète avec CRUD complet"""
    
    def __init__(self):
        self.db = Database(config.db_path)
        
        if config.is_valid():
            self.google = GoogleFormsService(config.google_script_url)
            self.messenger = MessengerService(config.page_token)
            self.reminder = ReminderService(self.db, self.google, self.messenger)
        else:
            st.error("Configuration invalide - vérifiez votre fichier .env")
            st.stop()
    
    def run(self):
        """Lance l'application"""
        st.set_page_config(
            page_title=config.app_title,
            page_icon="🔔",
            layout="wide"
        )
        
        st.title(f"🔔 {config.app_title}")
        
        # Navigation étendue
        page = st.sidebar.selectbox(
            "Navigation",
            [
                "📊 Dashboard", 
                "👥 Personnes", 
                "👥 Groupes", 
                "🏢 Pôles",
                "📋 Formulaires", 
                "🔔 Rappels"
            ]
        )
        
        # DEBUG Global dans sidebar
        self.show_debug_sidebar()
        
        if page == "📊 Dashboard":
            self.show_dashboard()
        elif page == "👥 Personnes":
            self.show_people()
        elif page == "👥 Groupes":
            self.show_groups()
        elif page == "🏢 Pôles":
            self.show_poles()
        elif page == "📋 Formulaires":
            self.show_forms()
        elif page == "🔔 Rappels":
            self.show_reminders()
    
    def show_debug_sidebar(self):
        """Debug global dans la sidebar"""
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Debug")
        
        all_forms = self.db.get_forms()
        poles = self.db.get_poles()
        
        st.sidebar.write(f"📋 {len(all_forms)} formulaires total")
        st.sidebar.write(f"🏢 {len(poles)} pôles")
        
        # Afficher chaque formulaire avec son pôle
        for form in all_forms:
            pole = self.db.get_pole(form.pole_id) if form.pole_id else None
            pole_name = pole.name if pole else "❌ ORPHELIN"
            st.sidebar.write(f"• {form.name} → {pole_name}")
        
        if st.sidebar.button("🔧 Réparer orphelins"):
            self.repair_orphaned_forms()
            st.rerun()
    
    def repair_orphaned_forms(self):
        """Répare les formulaires orphelins - VERSION CORRIGÉE"""
        poles = self.db.get_poles()
        if not poles:
            st.sidebar.error("Aucun pôle disponible")
            return
        
        default_pole = poles[0]
        all_forms = self.db.get_forms()
        repaired = 0
        
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            for form in all_forms:
                # Vérifier si le pole_id existe vraiment
                pole_exists = any(p.id == form.pole_id for p in poles)
                
                if not form.pole_id or not pole_exists:
                    conn.execute(
                        "UPDATE forms SET pole_id = ? WHERE id = ?",
                        (default_pole.id, form.id)
                    )
                    repaired += 1
                    st.sidebar.success(f"✅ {form.name} → {default_pole.name}")
            
            conn.commit()
        
        st.sidebar.success(f"🔧 {repaired} formulaire(s) réparé(s)")
    
    def show_dashboard(self):
        """Dashboard avec stats complètes"""
        st.header("📊 Dashboard")
        
        people = self.db.get_people()
        forms = self.db.get_forms()
        poles = self.db.get_poles()
        groups = self.db.get_groups()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Personnes", len(people))
        with col2:
            st.metric("🏢 Pôles", len(poles))
        with col3:
            st.metric("👥 Groupes", len(groups))
        with col4:
            st.metric("📋 Formulaires", len(forms))
        
        # Répartition par pôle
        if poles and forms:
            st.subheader("📊 Répartition des formulaires par pôle")
            for pole in poles:
                pole_forms = [f for f in forms if f.pole_id == pole.id]
                st.write(f"🏢 **{pole.name}**: {len(pole_forms)} formulaire(s)")
    
    def show_people(self):
        """Gestion des personnes avec CRUD complet"""
        st.header("👥 Gestion des personnes")
        
        tab_list, tab_add = st.tabs(["📄 Liste des personnes", "➕ Ajouter"])
        
        with tab_list:
            people = self.db.get_people()
            if people:
                for person in people:
                    with st.expander(f"👤 {person.name}"):
                        col_info, col_actions = st.columns([2, 1])
                        
                        with col_info:
                            email_display = person.email or "Non défini"
                            psid_display = person.psid or "Non défini"
                            st.write(f"**Email:** {email_display}")
                            st.write(f"**PSID:** {psid_display}")
                            st.write(f"**Ajouté le:** {person.created_at.strftime('%d/%m/%Y')}")
                        
                        with col_actions:
                            col_edit, col_del = st.columns(2)
                            
                            with col_edit:
                                if st.button("✏️", key=f"edit_person_{person.id}", help="Modifier"):
                                    st.session_state[f"editing_person_{person.id}"] = True
                                    st.rerun()
                            
                            with col_del:
                                if st.button("🗑️", key=f"del_person_{person.id}", help="Supprimer"):
                                    if self.delete_person_safe(person.id, person.name):
                                        st.rerun()
                        
                        # Modal d'édition
                        if st.session_state.get(f"editing_person_{person.id}"):
                            self.show_edit_person_modal(person)
            else:
                st.info("Aucune personne enregistrée")
        
        with tab_add:
            with st.form("add_person_form", clear_on_submit=True):
                st.subheader("➕ Nouvelle personne")
                
                name = st.text_input("Nom complet*", placeholder="Jean Dupont")
                email = st.text_input("Email", placeholder="jean@example.com")
                psid = st.text_input("PSID Messenger", placeholder="1234567890")
                
                submitted = st.form_submit_button("Ajouter la personne", type="primary")
                
                if submitted:
                    if not name:
                        st.error("Le nom est requis")
                    elif not email and not psid:
                        st.error("Email ou PSID est requis")
                    else:
                        person = Person(name=name, email=email, psid=psid)
                        if self.db.add_person(person):
                            st.success(f"✅ Personne '{name}' ajoutée avec succès!")
                        else:
                            st.error("❌ Erreur lors de l'ajout (doublon possible)")
    
    def show_edit_person_modal(self, person):
        """Modal d'édition d'une personne"""
        with st.form(f"edit_person_{person.id}"):
            st.subheader(f"✏️ Modifier {person.name}")
            
            new_name = st.text_input("Nom", value=person.name)
            new_email = st.text_input("Email", value=person.email or "")
            new_psid = st.text_input("PSID", value=person.psid or "")
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                saved = st.form_submit_button("💾 Sauvegarder", type="primary")
            with col_cancel:
                cancelled = st.form_submit_button("❌ Annuler")
            
            if cancelled:
                del st.session_state[f"editing_person_{person.id}"]
                st.rerun()
            
            if saved:
                if self.update_person(person.id, new_name, new_email, new_psid):
                    st.success("Personne mise à jour!")
                    del st.session_state[f"editing_person_{person.id}"]
                    st.rerun()
                else:
                    st.error("Erreur lors de la mise à jour")
    
    def delete_person_safe(self, person_id: str, person_name: str) -> bool:
        """Suppression sécurisée d'une personne"""
        if st.session_state.get(f"confirm_delete_person_{person_id}"):
            if self.db.delete_person(person_id):
                st.success(f"Personne '{person_name}' supprimée")
                del st.session_state[f"confirm_delete_person_{person_id}"]
                return True
            else:
                st.error("Erreur lors de la suppression")
                return False
        else:
            st.session_state[f"confirm_delete_person_{person_id}"] = True
            st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")
            return False
    
    def update_person(self, person_id: str, name: str, email: str, psid: str) -> bool:
        """Met à jour une personne"""
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE people SET name = ?, email = ?, psid = ? WHERE id = ?",
                    (name, email, psid, person_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def show_groups(self):
        """Gestion des groupes avec CRUD complet"""
        st.header("👥 Gestion des groupes")
        
        tab_list, tab_create = st.tabs(["📄 Liste des groupes", "➕ Créer un groupe"])
        
        with tab_list:
            groups = self.db.get_groups()
            if groups:
                for group in groups:
                    with st.expander(f"{group.display_name} ({group.member_count} membres)"):
                        col_info, col_actions = st.columns([2, 1])
                        
                        with col_info:
                            description_display = group.description or "Aucune"
                            st.write(f"**Description:** {description_display}")
                            
                            if group.member_ids:
                                st.write("**Membres:**")
                                people = self.db.get_people()
                                for person_id in group.member_ids[:5]:
                                    person = next((p for p in people if p.id == person_id), None)
                                    if person:
                                        st.write(f"• {person.name}")
                                if len(group.member_ids) > 5:
                                    st.write(f"... et {len(group.member_ids) - 5} autres")
                        
                        with col_actions:
                            col_edit, col_del = st.columns(2)
                            
                            with col_edit:
                                if st.button("✏️", key=f"edit_group_{group.id}", help="Modifier"):
                                    st.session_state[f"editing_group_{group.id}"] = True
                                    st.rerun()
                            
                            with col_del:
                                if st.button("🗑️", key=f"del_group_{group.id}", help="Supprimer"):
                                    if self.delete_group_safe(group.id, group.name):
                                        st.rerun()
                        
                        # Modal d'édition
                        if st.session_state.get(f"editing_group_{group.id}"):
                            self.show_edit_group_modal(group)
            else:
                st.info("Aucun groupe créé")
        
        with tab_create:
            with st.form("create_group_form", clear_on_submit=True):
                st.subheader("➕ Nouveau groupe")
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    name = st.text_input("Nom du groupe*", placeholder="BDE Santana")
                with col2:
                    icon = st.selectbox("Icône", ["👥", "🎓", "💼", "🏆", "🌟"])
                
                description = st.text_area("Description", placeholder="Description du groupe...")
                
                people = self.db.get_people()
                if people:
                    def format_person_for_group(p):
                        email_part = p.email or "pas d'email"
                        return f"{p.name} ({email_part})"
                    
                    selected_members = st.multiselect(
                        "Sélectionner les membres",
                        options=people,
                        format_func=format_person_for_group
                    )
                else:
                    selected_members = []
                    st.warning("Aucune personne disponible. Ajoutez des personnes d'abord.")
                
                submitted = st.form_submit_button("Créer le groupe", type="primary")
                
                if submitted:
                    if not name:
                        st.error("Le nom du groupe est requis")
                    elif not selected_members:
                        st.error("Sélectionnez au moins un membre")
                    else:
                        group = Group(
                            name=name,
                            description=description,
                            member_ids=[p.id for p in selected_members],
                            icon=icon
                        )
                        if self.db.add_group(group):
                            st.success(f"✅ Groupe '{name}' créé avec {len(selected_members)} membres!")
                        else:
                            st.error("❌ Erreur lors de la création")
    
    def show_edit_group_modal(self, group):
        """Modal d'édition d'un groupe"""
        with st.form(f"edit_group_{group.id}"):
            st.subheader(f"✏️ Modifier {group.name}")
            
            new_name = st.text_input("Nom", value=group.name)
            new_description = st.text_area("Description", value=group.description or "")
            new_icon = st.selectbox("Icône", ["👥", "🎓", "💼", "🏆", "🌟"], 
                                   index=["👥", "🎓", "💼", "🏆", "🌟"].index(group.icon) if group.icon in ["👥", "🎓", "💼", "🏆", "🌟"] else 0)
            
            people = self.db.get_people()
            current_members = [p for p in people if p.id in group.member_ids]
            
            def format_person_edit(p):
                email_part = p.email or "pas d'email"
                return f"{p.name} ({email_part})"
            
            new_members = st.multiselect(
                "Membres",
                options=people,
                default=current_members,
                format_func=format_person_edit
            )
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                saved = st.form_submit_button("💾 Sauvegarder", type="primary")
            with col_cancel:
                cancelled = st.form_submit_button("❌ Annuler")
            
            if cancelled:
                del st.session_state[f"editing_group_{group.id}"]
                st.rerun()
            
            if saved:
                if self.update_group(group.id, new_name, new_description, [p.id for p in new_members], new_icon):
                    st.success("Groupe mis à jour!")
                    del st.session_state[f"editing_group_{group.id}"]
                    st.rerun()
                else:
                    st.error("Erreur lors de la mise à jour")
    
    def delete_group_safe(self, group_id: str, group_name: str) -> bool:
        """Suppression sécurisée d'un groupe"""
        if st.session_state.get(f"confirm_delete_group_{group_id}"):
            if self.delete_group(group_id):
                st.success(f"Groupe '{group_name}' supprimé")
                del st.session_state[f"confirm_delete_group_{group_id}"]
                return True
            else:
                st.error("Erreur lors de la suppression")
                return False
        else:
            st.session_state[f"confirm_delete_group_{group_id}"] = True
            st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")
            return False
    
    def update_group(self, group_id: str, name: str, description: str, member_ids: list, icon: str) -> bool:
        """Met à jour un groupe"""
        try:
            import sqlite3
            import json
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE groups SET name = ?, description = ?, member_ids = ?, icon = ? WHERE id = ?",
                    (name, description, json.dumps(member_ids), icon, group_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def delete_group(self, group_id: str) -> bool:
        """Supprime un groupe"""
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def show_poles(self):
        """Gestion des pôles avec CRUD complet"""
        st.header("🏢 Gestion des pôles")
        
        tab_list, tab_create = st.tabs(["📄 Liste des pôles", "➕ Créer un pôle"])
        
        with tab_list:
            poles = self.db.get_poles()
            for pole in poles:
                forms_count = len(self.db.get_forms_by_pole(pole.id))
                with st.expander(f"{pole.display_name} ({forms_count} formulaire(s))"):
                    col_info, col_actions = st.columns([2, 1])
                    
                    with col_info:
                        description_display = pole.description or "Aucune"
                        st.write(f"**Description:** {description_display}")
                        st.markdown(f"**Couleur:** <span style='background-color: {pole.color}; padding: 2px 8px; border-radius: 3px; color: white;'>{pole.color}</span>", unsafe_allow_html=True)
                        st.write(f"**Formulaires:** {forms_count}")
                    
                    with col_actions:
                        col_edit, col_del = st.columns(2)
                        
                        with col_edit:
                            if st.button("✏️", key=f"edit_pole_{pole.id}", help="Modifier"):
                                st.session_state[f"editing_pole_{pole.id}"] = True
                                st.rerun()
                        
                        with col_del:
                            if st.button("🗑️", key=f"del_pole_{pole.id}", help="Supprimer"):
                                if forms_count > 0:
                                    st.error(f"Impossible: {forms_count} formulaire(s) associé(s)")
                                else:
                                    if self.delete_pole_safe(pole.id, pole.name):
                                        st.rerun()
                    
                    # Modal d'édition
                    if st.session_state.get(f"editing_pole_{pole.id}"):
                        self.show_edit_pole_modal(pole)
        
        with tab_create:
            with st.form("create_pole_form", clear_on_submit=True):
                st.subheader("➕ Nouveau pôle")
                
                name = st.text_input("Nom du pôle*", placeholder="Marketing, RH, IT...")
                description = st.text_area("Description", placeholder="Description du pôle...")
                color = st.color_picker("Couleur", value="#FF6B6B")
                
                submitted = st.form_submit_button("Créer le pôle", type="primary")
                
                if submitted:
                    if not name:
                        st.error("Le nom du pôle est requis")
                    else:
                        pole = Pole(name=name, description=description, color=color)
                        if self.db.add_pole(pole):
                            st.success(f"✅ Pôle '{name}' créé avec succès!")
                        else:
                            st.error("❌ Erreur lors de la création (nom déjà existant?)")
    
    def show_edit_pole_modal(self, pole):
        """Modal d'édition d'un pôle"""
        with st.form(f"edit_pole_{pole.id}"):
            st.subheader(f"✏️ Modifier {pole.name}")
            
            new_name = st.text_input("Nom", value=pole.name)
            new_description = st.text_area("Description", value=pole.description or "")
            new_color = st.color_picker("Couleur", value=pole.color)
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                saved = st.form_submit_button("💾 Sauvegarder", type="primary")
            with col_cancel:
                cancelled = st.form_submit_button("❌ Annuler")
            
            if cancelled:
                del st.session_state[f"editing_pole_{pole.id}"]
                st.rerun()
            
            if saved:
                if self.update_pole(pole.id, new_name, new_description, new_color):
                    st.success("Pôle mis à jour!")
                    del st.session_state[f"editing_pole_{pole.id}"]
                    st.rerun()
                else:
                    st.error("Erreur lors de la mise à jour")
    
    def delete_pole_safe(self, pole_id: str, pole_name: str) -> bool:
        """Suppression sécurisée d'un pôle"""
        if st.session_state.get(f"confirm_delete_pole_{pole_id}"):
            if self.delete_pole(pole_id):
                st.success(f"Pôle '{pole_name}' supprimé")
                del st.session_state[f"confirm_delete_pole_{pole_id}"]
                return True
            else:
                st.error("Erreur lors de la suppression")
                return False
        else:
            st.session_state[f"confirm_delete_pole_{pole_id}"] = True
            st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")
            return False
    
    def update_pole(self, pole_id: str, name: str, description: str, color: str) -> bool:
        """Met à jour un pôle"""
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE poles SET name = ?, description = ?, color = ? WHERE id = ?",
                    (name, description, color, pole_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def delete_pole(self, pole_id: str) -> bool:
        """Supprime un pôle"""
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute("DELETE FROM poles WHERE id = ?", (pole_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def show_forms(self):
        """Gestion des formulaires avec CRUD complet - VERSION SIMPLIFIÉE"""
        st.header("📋 Gestion des formulaires")
        
        tab_all, tab_by_pole, tab_create = st.tabs(["📄 Tous les formulaires", "🏢 Par pôle", "➕ Nouveau"])
        
        with tab_all:
            # SOLUTION: Afficher TOUS les formulaires sans filtre
            st.subheader("📋 Tous les formulaires")
            all_forms = self.db.get_forms()
            poles = self.db.get_poles()
            
            if all_forms:
                for form in all_forms:
                    # Trouver le pôle associé
                    pole = next((p for p in poles if p.id == form.pole_id), None)
                    pole_name = pole.name if pole else "❌ Pôle introuvable"
                    
                    with st.expander(f"📋 {form.name} ({pole_name})"):
                        col_info, col_actions = st.columns([2, 1])
                        
                        with col_info:
                            st.write(f"**Google ID:** {form.google_id}")
                            st.write(f"**Pôle:** {pole_name}")
                            st.write(f"**Personnes:** {len(form.people_ids)}")
                            st.write(f"**Créé le:** {form.created_at.strftime('%d/%m/%Y')}")
                        
                        with col_actions:
                            col_edit, col_del = st.columns(2)
                            
                            with col_edit:
                                if st.button("✏️", key=f"edit_form_{form.id}", help="Modifier"):
                                    st.session_state[f"editing_form_{form.id}"] = True
                                    st.rerun()
                            
                            with col_del:
                                if st.button("🗑️", key=f"del_form_{form.id}", help="Supprimer"):
                                    if self.delete_form_safe(form.id, form.name):
                                        st.rerun()
                            
                            st.link_button("🔗 Voir", form.url)
                        
                        # Modal d'édition
                        if st.session_state.get(f"editing_form_{form.id}"):
                            self.show_edit_form_modal(form)
            else:
                st.info("Aucun formulaire créé")
        
        with tab_by_pole:
            # Vue par pôle (gardée pour l'organisation)
            poles = self.db.get_poles()
            if poles:
                selected_pole = st.selectbox(
                    "🏢 Choisir un pôle",
                    options=poles,
                    format_func=lambda p: f"{p.display_name} ({len(self.db.get_forms_by_pole(p.id))} formulaire(s))"
                )
                
                if selected_pole:
                    forms = self.db.get_forms_by_pole(selected_pole.id)
                    if forms:
                        for form in forms:
                            st.write(f"📋 **{form.name}** - {len(form.people_ids)} personne(s)")
                    else:
                        st.info(f"Aucun formulaire dans '{selected_pole.name}'")
            else:
                st.warning("Créez d'abord des pôles")
        
        with tab_create:
            self.show_create_form_tab()
    
    def show_create_form_tab(self):
        """Onglet de création de formulaire"""
        poles = self.db.get_poles()
        if not poles:
            st.warning("⚠️ Créez d'abord un pôle")
            return
        
        with st.form("create_form_form", clear_on_submit=True):
            st.subheader("➕ Nouveau formulaire")
            
            name = st.text_input("Nom du formulaire*", placeholder="Enquête satisfaction Q4")
            google_id = st.text_input("Google Form ID*", placeholder="1FAIpQLSe...")
            
            # Sélection du pôle
            selected_pole = st.selectbox(
                "🏢 Pôle*",
                options=poles,
                format_func=lambda p: p.display_name
            )
            
            # Sélection des personnes
            people = self.db.get_people()
            if people:
                def format_person_simple(p):
                    email_part = p.email or "pas d'email"
                    return f"{p.name} ({email_part})"
                
                selected_people = st.multiselect(
                    "👥 Destinataires*",
                    options=people,
                    format_func=format_person_simple
                )
            else:
                selected_people = []
                st.warning("Aucune personne disponible")
            
            submitted = st.form_submit_button("Créer le formulaire", type="primary")
            
            if submitted:
                if not name or not google_id:
                    st.error("Nom et Google Form ID requis")
                elif not selected_people:
                    st.error("Sélectionnez au moins une personne")
                else:
                    form = Form(
                        name=name,
                        google_id=google_id,
                        pole_id=selected_pole.id,
                        people_ids=[p.id for p in selected_people]
                    )
                    
                    if self.db.add_form(form):
                        st.success(f"✅ Formulaire '{name}' créé!")
                        st.rerun()
                    else:
                        st.error("❌ Erreur (Google ID déjà utilisé?)")
    
    def show_edit_form_modal(self, form):
        """Modal d'édition d'un formulaire"""
        with st.form(f"edit_form_{form.id}"):
            st.subheader(f"✏️ Modifier {form.name}")
            
            new_name = st.text_input("Nom", value=form.name)
            new_google_id = st.text_input("Google ID", value=form.google_id)
            
            poles = self.db.get_poles()
            current_pole_idx = next((i for i, p in enumerate(poles) if p.id == form.pole_id), 0)
            new_pole = st.selectbox(
                "Pôle",
                options=poles,
                index=current_pole_idx,
                format_func=lambda p: p.display_name
            )
            
            people = self.db.get_people()
            current_people = [p for p in people if p.id in form.people_ids]
            
            def format_person_edit_form(p):
                email_part = p.email or "pas d'email"
                return f"{p.name} ({email_part})"
            
            new_people = st.multiselect(
                "Destinataires",
                options=people,
                default=current_people,
                format_func=format_person_edit_form
            )
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                saved = st.form_submit_button("💾 Sauvegarder", type="primary")
            with col_cancel:
                cancelled = st.form_submit_button("❌ Annuler")
            
            if cancelled:
                del st.session_state[f"editing_form_{form.id}"]
                st.rerun()
            
            if saved:
                # Validation et nettoyage des données
                clean_name = new_name.strip() if new_name else ""
                clean_google_id = new_google_id.strip() if new_google_id else ""
                safe_pole_id = new_pole.id if new_pole else ""
                safe_people_ids = [p.id for p in new_people] if new_people else []
                
                if not clean_name or not clean_google_id:
                    st.error("Nom et Google ID sont requis")
                elif not safe_people_ids:
                    st.error("Sélectionnez au moins une personne")
                else:
                    if self.update_form(form.id, clean_name, clean_google_id, safe_pole_id, safe_people_ids):
                        st.success("Formulaire mis à jour!")
                        del st.session_state[f"editing_form_{form.id}"]
                        st.rerun()
                    else:
                        st.error("Erreur lors de la mise à jour")
    
    def delete_form_safe(self, form_id: str, form_name: str) -> bool:
        """Suppression sécurisée d'un formulaire"""
        if st.session_state.get(f"confirm_delete_form_{form_id}"):
            if self.delete_form(form_id):
                st.success(f"Formulaire '{form_name}' supprimé")
                del st.session_state[f"confirm_delete_form_{form_id}"]
                return True
            else:
                st.error("Erreur lors de la suppression")
                return False
        else:
            st.session_state[f"confirm_delete_form_{form_id}"] = True
            st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")
            return False
    
    def update_form(self, form_id: str, name: str, google_id: str, pole_id: str, people_ids: list) -> bool:
        """Met à jour un formulaire"""
        try:
            import sqlite3
            import json
            with sqlite3.connect(self.db.db_path) as conn:
                # Mettre à jour le formulaire
                cursor = conn.execute(
                    "UPDATE forms SET name = ?, google_id = ?, pole_id = ?, people_ids = ? WHERE id = ?",
                    (name, google_id, pole_id, json.dumps(people_ids), form_id)
                )
                
                # Recréer les réponses
                conn.execute("DELETE FROM responses WHERE form_id = ?", (form_id,))
                for person_id in people_ids:
                    from models import Response
                    response = Response(form_id=form_id, person_id=person_id)
                    conn.execute(
                        "INSERT INTO responses VALUES (?, ?, ?, ?, ?)",
                        (response.id, response.form_id, response.person_id, response.has_responded, None)
                    )
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def delete_form(self, form_id: str) -> bool:
        """Supprime un formulaire et ses réponses"""
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                # Les réponses sont supprimées automatiquement par FK CASCADE
                cursor = conn.execute("DELETE FROM forms WHERE id = ?", (form_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def show_reminders(self):
        """Gestion des rappels - INCHANGÉE"""
        st.header("🔔 Gestion des rappels")
        
        forms = self.db.get_forms()
        if not forms:
            st.info("Aucun formulaire disponible")
            return
        
        # Affichage par pôle
        poles = self.db.get_poles()
        for pole in poles:
            pole_forms = [f for f in forms if f.pole_id == pole.id]
            if pole_forms:
                st.subheader(f"🏢 {pole.name}")
                
                for form in pole_forms:
                    with st.expander(f"📋 {form.name}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("🔄 Synchroniser", key=f"sync_{form.id}"):
                                with st.spinner("Synchronisation..."):
                                    stats = self.reminder.sync_form(form)
                                    st.success(f"✅ {stats['updated']}/{stats['total']} mises à jour")
                        
                        with col2:
                            if st.button("📧 Envoyer rappels", key=f"remind_{form.id}"):
                                with st.spinner("Envoi..."):
                                    stats = self.reminder.send_reminders(form)
                                    st.success(f"✅ {stats['sent']} envoyés, {stats['failed']} échecs")
                        
                        # Aperçu des non-répondants
                        non_responders = self.db.get_non_responders(form.id)
                        if non_responders:
                            st.write("**👥 Non-répondants:**")
                            for person, response in non_responders[:5]:
                                psid_status = "✅" if person.psid else "❌"
                                email_display = person.email or "Pas d'email"
                                st.write(f"{psid_status} {person.name} - {email_display}")
                            if len(non_responders) > 5:
                                st.write(f"... et {len(non_responders) - 5} autres")
                        else:
                            st.success("✅ Tout le monde a répondu!")

# Point d'entrée pour Streamlit
if __name__ == "__main__":
    # Charger les variables d'environnement
    from dotenv import load_dotenv
    load_dotenv()
    
    # Lancer l'application
    app = STNBot()
    app.run()