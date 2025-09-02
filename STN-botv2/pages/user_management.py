# pages/user_management.py - VERSION CORRIGÉE
"""Gestion des utilisateurs pour STN-bot v2 - Version simplifiée"""

import streamlit as st
import json
from datetime import datetime
from typing import List, Dict, Any

# Imports locaux
from database.sqlite_manager import get_database_manager
from pages.auth import check_authentication, require_role

def show_user_management_page():
    """Page de gestion des utilisateurs (admin seulement)"""
    user = require_role(['admin'])
    if not user:
        return
    
    st.header("👤 Gestion des utilisateurs")
    st.info("🚧 Fonctionnalité en développement - Version simplifiée")
    
    db = get_database_manager()
    
    # Pour l'instant, affichage simple des informations
    st.subheader("ℹ️ Informations système")
    
    try:
        # Statistiques de base
        people = db.get_all_people()
        forms = db.get_all_forms()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("👥 Personnes", len(people))
        
        with col2:
            st.metric("📋 Formulaires", len(forms))
        
        with col3:
            # Calculer le nombre de rappels envoyés
            total_reminders = 0
            for form, _ in forms:
                responses = db.get_responses_for_form(form.id)
                total_reminders += len([r for r in responses if r.last_reminder])
            
            st.metric("🔔 Rappels envoyés", total_reminders)
        
        # Informations utilisateur actuel
        st.subheader("👤 Utilisateur connecté")
        st.write(f"**Nom:** {user['username']}")
        st.write(f"**Rôle:** {user['role']}")
        
        if user.get('last_login'):
            try:
                last_login = datetime.fromisoformat(user['last_login'])
                st.write(f"**Dernière connexion:** {last_login.strftime('%d/%m/%Y %H:%M')}")
            except:
                st.write("**Dernière connexion:** Information non disponible")
        
        # Actions de maintenance
        st.subheader("🔧 Actions de maintenance")
        
        col_clear_cache, col_info = st.columns(2)
        
        with col_clear_cache:
            if st.button("🧹 Vider le cache Streamlit"):
                try:
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.success("Cache vidé !")
                except Exception as e:
                    st.error(f"Erreur: {e}")
        
        with col_info:
            if st.button("📊 Afficher les statistiques détaillées"):
                show_detailed_stats(db)
    
    except Exception as e:
        st.error(f"Erreur lors de la récupération des informations: {e}")

def show_detailed_stats(db):
    """Affiche les statistiques détaillées"""
    st.subheader("📊 Statistiques détaillées")
    
    try:
        # Stats par formulaire
        forms = db.get_all_forms()
        
        if forms:
            st.write("**📋 Détails par formulaire:**")
            
            for form, expected_people_ids in forms:
                with st.expander(f"{form.name}"):
                    stats = db.get_form_stats(form.id)
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total", stats['total'])
                    
                    with col2:
                        st.metric("Répondu", stats['responded'])
                    
                    with col3:
                        st.metric("En attente", stats['pending'])
                    
                    # Taux de réponse
                    if stats['total'] > 0:
                        rate = (stats['responded'] / stats['total']) * 100
                        st.write(f"**Taux de réponse:** {rate:.1f}%")
                    
                    # Personnes attendues
                    st.write(f"**Personnes attendues:** {len(expected_people_ids)}")
        
        # Stats des personnes
        people = db.get_all_people()
        
        st.write("**👥 Analyse des personnes:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            with_email = len([p for p in people if p.email])
            st.metric("Avec email", with_email)
        
        with col2:
            with_psid = len([p for p in people if p.psid])
            st.metric("Avec PSID", with_psid)
        
        with col3:
            complete = len([p for p in people if p.email and p.psid])
            st.metric("Profil complet", complete)
        
        # Tableau des personnes
        if people:
            st.write("**📋 Liste des personnes:**")
            
            people_data = []
            for person in people:
                people_data.append({
                    'Nom': person.name,
                    'Email': person.email or 'Non défini',
                    'PSID': 'Oui' if person.psid else 'Non',
                    'Ajouté le': person.created_at.strftime('%d/%m/%Y')
                })
            
            import pandas as pd
            df = pd.DataFrame(people_data)
            st.dataframe(df, use_container_width=True)
    
    except Exception as e:
        st.error(f"Erreur calcul statistiques: {e}")