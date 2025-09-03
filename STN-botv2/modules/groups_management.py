import streamlit as st
from datetime import datetime
from database import get_database_manager
from database.models import PeopleGroup

def show_groups_management_page():
    """Page de gestion des groupes"""
    st.header("👥 Gestion des groupes de personnes")
    
    db = get_database_manager()
    
    tab_list, tab_create = st.tabs(["📄 Liste des groupes", "➕ Créer un groupe"])
    
    with tab_list:
        show_groups_list(db)
    
    with tab_create:
        show_create_group(db)

def show_groups_list(db):
    """Liste des groupes"""
    groups = db.get_all_groups()
    
    if not groups:
        st.info("Aucun groupe créé")
        return
    
    for group in groups:
        with st.expander(f"{group.display_name} ({group.member_count} membres)"):
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                st.write(f"**Description:** {group.description or 'Aucune'}")
                st.write(f"**Membres:** {group.member_count}")
                
                if group.member_ids:
                    people = db.get_all_people()
                    members = [p.name for p in people if p.id in group.member_ids[:5]]
                    for name in members:
                        st.write(f"• {name}")
                    if len(group.member_ids) > 5:
                        st.write(f"... et {len(group.member_ids) - 5} autres")
            
            with col_actions:
                if st.button(f"🗑️", key=f"del_{group.id}"):
                    if db.delete_group(group.id):
                        st.success("Groupe supprimé")
                        st.rerun()

def show_create_group(db):
    """Création d'un groupe"""
    with st.form("create_group"):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            name = st.text_input("Nom du groupe*", placeholder="ex: BDE_Santana")
        with col2:
            icon = st.selectbox("Icône", ["👥", "🎓", "💼", "🏆", "🌟"])
        
        description = st.text_area("Description")
        
        st.subheader("Sélectionner les membres")
        people = db.get_all_people()
        
        if people:
            selected_members = st.multiselect(
                "Membres",
                options=[p.id for p in people],
                format_func=lambda pid: next((p.name for p in people if p.id == pid), pid)
            )
        else:
            selected_members = []
        
        submitted = st.form_submit_button("Créer le groupe")
        
        if submitted and name and selected_members:
            group = PeopleGroup(
                name=name,
                description=description,
                member_ids=selected_members,
                icon=icon
            )
            
            if db.add_group(group):
                st.success(f"Groupe créé avec {len(selected_members)} membres!")
                st.rerun()