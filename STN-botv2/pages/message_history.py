# pages/message_history.py - VERSION MINIMALE SANS ERREUR
"""Page d'historique des messages pour STN-bot v2 - Version simplifiée"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Imports locaux
from database.sqlite_manager import get_database_manager
from pages.auth import check_authentication

def show_message_history_page():
    """Page d'historique des messages"""
    st.header("📜 Historique des messages")
    
    user = check_authentication()
    if not user:
        return
    
    db = get_database_manager()
    
    # Version simplifiée avec un seul onglet pour commencer
    st.subheader("📋 Messages par formulaire")
    
    try:
        # Récupérer tous les formulaires
        all_forms = db.get_active_forms()
        
        if not all_forms:
            st.info("Aucun formulaire disponible")
            return
        
        # Sélection du formulaire
        selected_form = st.selectbox(
            "Choisir un formulaire",
            options=[form for form, _ in all_forms],
            format_func=lambda f: f.name
        )
        
        if not selected_form:
            return
        
        # Récupérer les rappels pour ce formulaire
        responses = db.get_responses_for_form(selected_form.id)
        
        # Afficher les statistiques de base
        total_responses = len(responses)
        sent_reminders = len([r for r in responses if r.last_reminder])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📨 Total réponses", total_responses)
        with col2:
            st.metric("🔔 Rappels envoyés", sent_reminders)
        with col3:
            st.metric("✅ Ont répondu", len([r for r in responses if r.has_responded]))
        
        # Afficher les rappels envoyés
        st.subheader("📝 Rappels envoyés")
        
        reminder_data = []
        for response in responses:
            if response.last_reminder:
                person = db.get_person_by_id(response.person_id)
                if person:
                    reminder_data.append({
                        'Personne': person.name,
                        'Email': person.email or 'Non défini',
                        'Dernier rappel': response.last_reminder.strftime('%d/%m/%Y %H:%M'),
                        'Nombre de rappels': response.reminder_count,
                        'A répondu': '✅' if response.has_responded else '❌'
                    })
        
        if reminder_data:
            df = pd.DataFrame(reminder_data)
            st.dataframe(df, use_container_width=True)
            
            # Option d'export
            if st.button("📥 Exporter en CSV"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Télécharger CSV",
                    data=csv,
                    file_name=f"historique_{selected_form.name}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("Aucun rappel envoyé pour ce formulaire")
    
    except Exception as e:
        st.error(f"Erreur: {e}")