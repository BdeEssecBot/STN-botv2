# pages/validation.py - VERSION CORRIGÉE
"""Page de validation des nouveaux contacts pour STN-bot v2"""

import streamlit as st
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Imports locaux
from database.sqlite_manager import get_database_manager
from modules.auth import check_authentication, require_role

def show_validation_page():
    """Page de validation des nouveaux contacts"""
    user = require_role(['admin', 'pole_manager'])
    if not user:
        return
    
    st.header("⏳ Validation des nouveaux contacts")
    
    db = get_database_manager()
    
    # Version simplifiée : afficher les personnes sans PSID ou email
    try:
        pending_people = get_pending_validations_simple(db)
        
        if not pending_people:
            st.success("✅ Aucun contact en attente de validation")
            
            # Afficher les contacts récemment ajoutés
            show_recently_added_contacts(db)
            return
        
        st.info(f"👥 {len(pending_people)} contact(s) nécessitent une attention")
        
        # Statistiques rapides
        show_validation_statistics(pending_people)
        
        # Traitement en lot
        show_bulk_validation_options(db, pending_people, user)
        
        # Validation individuelle
        st.subheader("👤 Validation individuelle")
        
        for person_data in pending_people:
            show_person_validation_card(db, person_data, user)
    
    except Exception as e:
        st.error(f"❌ Erreur récupération contacts: {e}")

def get_pending_validations_simple(db) -> List[Dict[str, Any]]:
    """Récupère les contacts qui nécessitent validation (version simplifiée)"""
    try:
        # Récupérer les personnes qui ont un PSID mais pas d'email, ou inversement
        people = db.get_all_people()
        pending = []
        
        for person in people:
            # Considérer comme "en attente" si PSID mais pas d'email
            if person.psid and not person.email:
                pending.append({
                    'id': person.id,
                    'name': person.name,
                    'email': person.email or '',
                    'psid': person.psid,
                    'created_at': person.created_at.isoformat(),
                    'auto_captured': bool(person.psid and not person.email),  # Simulation
                    'status': 'pending_validation'
                })
        
        return pending
    
    except Exception as e:
        st.error(f"Erreur récupération validations: {e}")
        return []

def show_validation_statistics(pending_people: List[Dict[str, Any]]):
    """Affiche les statistiques des contacts en attente"""
    if not pending_people:
        return
    
    # Calculer les stats
    total = len(pending_people)
    auto_captured = len([p for p in pending_people if p.get('auto_captured')])
    with_psid = len([p for p in pending_people if p.get('psid')])
    
    # Répartition par jour
    today_count = 0
    week_count = 0
    now = datetime.now()
    
    for person in pending_people:
        try:
            created_date = datetime.fromisoformat(person['created_at'])
            days_ago = (now - created_date).days
            
            if days_ago == 0:
                today_count += 1
            if days_ago <= 7:
                week_count += 1
        except:
            pass
    
    # Affichage
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📥 Total en attente", total)
    
    with col2:
        st.metric("🤖 Auto-capturés", auto_captured)
    
    with col3:
        st.metric("📅 Aujourd'hui", today_count)
    
    with col4:
        st.metric("📊 Cette semaine", week_count)

def show_bulk_validation_options(db, pending_people: List[Dict[str, Any]], user: Dict[str, Any]):
    """Options de validation en lot"""
    if not pending_people:
        return
    
    with st.expander("⚡ Actions en lot", expanded=False):
        st.write("**Actions rapides pour plusieurs contacts:**")
        
        # Sélection des contacts
        selected_contacts = st.multiselect(
            "Sélectionner les contacts à traiter",
            options=pending_people,
            format_func=lambda p: f"{p['name']} ({datetime.fromisoformat(p['created_at']).strftime('%d/%m %H:%M')})"
        )
        
        if selected_contacts:
            col_validate, col_reject = st.columns(2)
            
            with col_validate:
                if st.button("✅ Valider la sélection", type="primary"):
                    results = bulk_validate_contacts(db, selected_contacts, user['id'])
                    show_bulk_results(results)
            
            with col_reject:
                if st.button("❌ Marquer comme inactifs"):
                    results = bulk_reject_contacts(db, selected_contacts)
                    show_bulk_results(results)

def show_person_validation_card(db, person_data: Dict[str, Any], user: Dict[str, Any]):
    """Carte de validation pour une personne"""
    try:
        created_date = datetime.fromisoformat(person_data['created_at'])
        date_str = created_date.strftime('%d/%m/%Y à %H:%M')
    except:
        date_str = "Date inconnue"
    
    with st.expander(
        f"👤 {person_data['name']} - Ajouté le: {date_str}",
        expanded=True
    ):
        col_info, col_actions = st.columns([2, 1])
        
        with col_info:
            show_person_details(person_data)
        
        with col_actions:
            show_validation_actions(db, person_data, user)

def show_person_details(person_data: Dict[str, Any]):
    """Affiche les détails d'une personne"""
    st.write(f"**Nom complet:** {person_data['name']}")
    st.write(f"**Email actuel:** {person_data['email'] or 'Non défini'}")
    st.write(f"**PSID:** `{person_data['psid'][:15]}...`" if person_data.get('psid') else "Non défini")
    
    # Informations auto-capturées
    if person_data.get('auto_captured'):
        st.write("🤖 **Contact probablement auto-capturé depuis Facebook**")
        st.info("💡 Ce contact a un PSID mais pas d'email - probablement capturé automatiquement")
    
    # Simulation d'un profil Facebook
    if person_data.get('psid'):
        with st.expander("📱 Informations Facebook simulées"):
            st.write("**Prénom estimé:** " + person_data['name'].split()[0] if person_data['name'] else "N/A")
            if len(person_data['name'].split()) > 1:
                st.write("**Nom de famille estimé:** " + " ".join(person_data['name'].split()[1:]))
            st.write("**PSID complet:** " + person_data['psid'])

def show_validation_actions(db, person_data: Dict[str, Any], user: Dict[str, Any]):
    """Actions de validation pour une personne"""
    with st.form(f"validate_{person_data['id']}"):
        st.subheader("✅ Actions")
        
        # Champs de validation
        email = st.text_input(
            "📧 Email à attribuer",
            placeholder="exemple@domain.com",
            key=f"email_{person_data['id']}",
            value=person_data.get('email', '')
        )
        
        new_name = st.text_input(
            "👤 Nom (optionnel)",
            value=person_data['name'],
            key=f"name_{person_data['id']}"
        )
        
        notes = st.text_area(
            "📝 Notes",
            placeholder="Informations supplémentaires...",
            height=60,
            key=f"notes_{person_data['id']}"
        )
        
        # Actions
        col_accept, col_reject = st.columns(2)
        
        with col_accept:
            validated = st.form_submit_button("✅ Valider", type="primary")
        
        with col_reject:
            rejected = st.form_submit_button("❌ Marquer inactif")
        
        # Traitement des actions
        if validated:
            success = validate_single_person(
                db, 
                person_data, 
                user, 
                email.strip() if email else None, 
                new_name.strip() if new_name else '', 
                notes.strip() if notes else None
            )
            if success:
                st.success("✅ Contact validé !")
                st.rerun()
            else:
                st.error("❌ Erreur lors de la validation")
        
        if rejected:
            success = reject_single_person(db, person_data)
            if success:
                st.success("❌ Contact marqué comme inactif")
                st.rerun()
            else:
                st.error("❌ Erreur lors du marquage")

def show_recently_added_contacts(db):
    """Affiche les contacts récemment ajoutés"""
    try:
        # Récupérer les contacts ajoutés dans les dernières 24h
        people = db.get_all_people()
        now = datetime.now()
        recent_people = []
        
        for person in people:
            try:
                time_diff = now - person.created_at
                if time_diff.total_seconds() < 24 * 3600:  # 24 heures
                    recent_people.append(person)
            except:
                continue
        
        if recent_people:
            st.subheader("👥 Contacts récemment ajoutés (24h)")
            
            for person in recent_people[:5]:  # Limiter à 5
                try:
                    added_date = person.created_at.strftime('%d/%m %H:%M')
                except:
                    added_date = "Date inconnue"
                
                status_icon = "✅" if person.email else "⏳"
                st.write(f"{status_icon} **{person.name}** - ajouté le {added_date}")
    
    except Exception as e:
        st.error(f"Erreur récupération contacts récents: {e}")

def validate_single_person(db, person_data: Dict[str, Any], user: Dict[str, Any], email: Optional[str], new_name: str, notes: Optional[str]) -> bool:
    """Valide une seule personne"""
    try:
        with sqlite3.connect(db.db_path) as conn:
            # Construire la requête de mise à jour
            update_fields = ["updated_at = ?"]
            values = [datetime.now().isoformat()]
            
            if email:
                update_fields.append("email = ?")
                values.append(email)
            
            if new_name and new_name != person_data['name']:
                update_fields.append("name = ?")
                values.append(new_name)
            
            # Ajouter l'ID pour le WHERE
            values.append(person_data['id'])
            
            cursor = conn.execute(f"""
                UPDATE people 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, values)
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                # Log de l'action (version simplifiée)
                st.session_state[f"validation_log_{person_data['id']}"] = {
                    'validated_by': user['username'],
                    'validated_at': datetime.now().isoformat(),
                    'notes': notes
                }
            
            return success
    except Exception as e:
        st.error(f"Erreur validation: {e}")
        return False

def reject_single_person(db, person_data: Dict[str, Any]) -> bool:
    """Rejette une seule personne (version simplifiée - on ne supprime pas, on marque juste)"""
    try:
        with sqlite3.connect(db.db_path) as conn:
            # Ajouter une note dans le nom pour marquer comme inactif
            new_name = f"[INACTIF] {person_data['name']}"
            
            cursor = conn.execute("""
                UPDATE people 
                SET name = ?, updated_at = ?
                WHERE id = ?
            """, (new_name, datetime.now().isoformat(), person_data['id']))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
    except Exception as e:
        st.error(f"Erreur rejet: {e}")
        return False

def bulk_validate_contacts(db, contacts: List[Dict[str, Any]], validator_id: str) -> Dict[str, Any]:
    """Validation en lot de contacts"""
    results = {"success": 0, "failed": 0, "errors": []}
    
    for contact in contacts:
        try:
            # Validation simple : juste marquer comme traité
            success = validate_single_person(db, contact, {'username': 'bulk_validator'}, None, contact['name'], "Validation en lot")
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"Échec validation {contact['name']}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Erreur {contact['name']}: {e}")
    
    return results

def bulk_reject_contacts(db, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rejet en lot de contacts"""
    results = {"success": 0, "failed": 0, "errors": []}
    
    for contact in contacts:
        try:
            success = reject_single_person(db, contact)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"Échec rejet {contact['name']}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Erreur {contact['name']}: {e}")
    
    return results

def show_bulk_results(results: Dict[str, Any]):
    """Affiche les résultats d'une action en lot"""
    if results["success"] > 0:
        st.success(f"✅ {results['success']} contact(s) traité(s) avec succès")
    
    if results["failed"] > 0:
        st.error(f"❌ {results['failed']} échec(s)")
        
        for error in results["errors"]:
            st.write(f"• {error}")
    
    if results["success"] > 0:
        st.rerun()