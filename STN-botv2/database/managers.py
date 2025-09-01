# database/manager.py
"""Gestionnaire de base de données Streamlit native pour STN-bot v2"""

import streamlit as st
import pandas as pd
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

from database.models import Person, Form, Response, ReminderStats, DatabaseQuery

logger = logging.getLogger(__name__)

class StreamlitDatabase:
    """
    Gestionnaire de base de données utilisant le cache Streamlit
    RÉVOLUTION: Plus besoin de Notion ! Tout en mémoire optimisé.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialise la base de données dans session_state"""
        if 'db_initialized' not in st.session_state:
            st.session_state.db_initialized = True
            st.session_state.people = []
            st.session_state.forms = []
            st.session_state.responses = []
            st.session_state.last_sync = None
            st.session_state.database_version = "2.0"
            
            logger.info("🚀 Base de données Streamlit initialisée")
    
    # ============ PEOPLE MANAGEMENT ============
    
    def add_person(self, person: Person) -> bool:
        """Ajoute une personne à la base"""
        try:
            # Vérifier les doublons par email
            if person.email and self.get_person_by_email(person.email):
                logger.warning(f"Personne avec email {person.email} existe déjà")
                return False
            
            # Vérifier les doublons par PSID
            if person.psid and self.get_person_by_psid(person.psid):
                logger.warning(f"Personne avec PSID {person.psid} existe déjà")
                return False
            
            person.updated_at = datetime.now()
            st.session_state.people.append(person.to_dict())
            logger.info(f"✅ Personne ajoutée: {person.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur ajout personne: {e}")
            return False
    
    def get_all_people(self) -> List[Person]:
        """Récupère toutes les personnes"""
        try:
            return [Person.from_dict(p) for p in st.session_state.people]
        except Exception as e:
            logger.error(f"❌ Erreur récupération personnes: {e}")
            return []
    
    def get_person_by_id(self, person_id: str) -> Optional[Person]:
        """Récupère une personne par ID"""
        for person_dict in st.session_state.people:
            if person_dict["id"] == person_id:
                return Person.from_dict(person_dict)
        return None
    
    def get_person_by_email(self, email: str) -> Optional[Person]:
        """Récupère une personne par email (normalisé)"""
        normalized_email = email.lower().strip()
        for person_dict in st.session_state.people:
            person = Person.from_dict(person_dict)
            if person.normalize_email() == normalized_email:
                return person
        return None
    
    def get_person_by_psid(self, psid: str) -> Optional[Person]:
        """Récupère une personne par PSID"""
        for person_dict in st.session_state.people:
            if person_dict["psid"] == psid:
                return Person.from_dict(person_dict)
        return None
    
    def update_person(self, person: Person) -> bool:
        """Met à jour une personne"""
        try:
            for i, person_dict in enumerate(st.session_state.people):
                if person_dict["id"] == person.id:
                    person.updated_at = datetime.now()
                    st.session_state.people[i] = person.to_dict()
                    logger.info(f"✅ Personne mise à jour: {person.name}")
                    return True
            
            logger.warning(f"⚠️ Personne {person.id} non trouvée pour mise à jour")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour personne: {e}")
            return False
    
    def delete_person(self, person_id: str) -> bool:
        """Supprime une personne et ses réponses associées"""
        try:
            # Supprimer les réponses associées
            st.session_state.responses = [
                r for r in st.session_state.responses 
                if r["person_id"] != person_id
            ]
            
            # Supprimer la personne
            initial_count = len(st.session_state.people)
            st.session_state.people = [
                p for p in st.session_state.people 
                if p["id"] != person_id
            ]
            
            deleted = len(st.session_state.people) < initial_count
            if deleted:
                logger.info(f"✅ Personne {person_id} supprimée avec ses réponses")
            
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression personne: {e}")
            return False
    
    # ============ FORMS MANAGEMENT ============
    
    def add_form(self, form: Form) -> bool:
        """Ajoute un formulaire à la base"""
        try:
            # Vérifier les doublons par Google Form ID
            if self.get_form_by_google_id(form.google_form_id):
                logger.warning(f"Formulaire avec Google ID {form.google_form_id} existe déjà")
                return False
            
            form.updated_at = datetime.now()
            st.session_state.forms.append(form.to_dict())
            logger.info(f"✅ Formulaire ajouté: {form.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur ajout formulaire: {e}")
            return False
    
    def get_all_forms(self) -> List[Form]:
        """Récupère tous les formulaires"""
        try:
            return [Form.from_dict(f) for f in st.session_state.forms]
        except Exception as e:
            logger.error(f"❌ Erreur récupération formulaires: {e}")
            return []
    
    def get_active_forms(self) -> List[Form]:
        """Récupère les formulaires actifs seulement"""
        return [f for f in self.get_all_forms() if f.is_active]
    
    def get_form_by_id(self, form_id: str) -> Optional[Form]:
        """Récupère un formulaire par ID"""
        for form_dict in st.session_state.forms:
            if form_dict["id"] == form_id:
                return Form.from_dict(form_dict)
        return None
    
    def get_form_by_google_id(self, google_form_id: str) -> Optional[Form]:
        """Récupère un formulaire par Google Form ID"""
        for form_dict in st.session_state.forms:
            if form_dict["google_form_id"] == google_form_id:
                return Form.from_dict(form_dict)
        return None
    
    def update_form(self, form: Form) -> bool:
        """Met à jour un formulaire"""
        try:
            for i, form_dict in enumerate(st.session_state.forms):
                if form_dict["id"] == form.id:
                    form.updated_at = datetime.now()
                    st.session_state.forms[i] = form.to_dict()
                    logger.info(f"✅ Formulaire mis à jour: {form.name}")
                    return True
            
            logger.warning(f"⚠️ Formulaire {form.id} non trouvé pour mise à jour")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour formulaire: {e}")
            return False
    
    def delete_form(self, form_id: str) -> bool:
        """Supprime un formulaire et ses réponses associées"""
        try:
            # Supprimer les réponses associées
            st.session_state.responses = [
                r for r in st.session_state.responses 
                if r["form_id"] != form_id
            ]
            
            # Supprimer le formulaire
            initial_count = len(st.session_state.forms)
            st.session_state.forms = [
                f for f in st.session_state.forms 
                if f["id"] != form_id
            ]
            
            deleted = len(st.session_state.forms) < initial_count
            if deleted:
                logger.info(f"✅ Formulaire {form_id} supprimé avec ses réponses")
            
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression formulaire: {e}")
            return False
    
    # ============ RESPONSES MANAGEMENT ============
    
    def add_or_update_response(self, response: Response) -> bool:
        """Ajoute ou met à jour une réponse"""
        try:
            # Chercher si la réponse existe déjà (même form + person)
            existing_response = self.get_response_by_form_and_person(
                response.form_id, response.person_id
            )
            
            if existing_response:
                # Mettre à jour la réponse existante
                response.id = existing_response.id  # Garder le même ID
                response.created_at = existing_response.created_at  # Garder la date de création
                return self.update_response(response)
            else:
                # Créer nouvelle réponse
                response.updated_at = datetime.now()
                st.session_state.responses.append(response.to_dict())
                logger.info(f"✅ Réponse ajoutée: Form {response.form_id[:8]}... - Person {response.person_id[:8]}...")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur ajout/mise à jour réponse: {e}")
            return False
    
    def get_all_responses(self) -> List[Response]:
        """Récupère toutes les réponses"""
        try:
            return [Response.from_dict(r) for r in st.session_state.responses]
        except Exception as e:
            logger.error(f"❌ Erreur récupération réponses: {e}")
            return []
    
    def get_responses_for_form(self, form_id: str) -> List[Response]:
        """Récupère toutes les réponses pour un formulaire - RETOURNE List[Response]"""
        all_responses = self.get_all_responses()
        return DatabaseQuery.filter_responses_by_form(all_responses, form_id)
    
    def get_responses_with_people_for_form(self, form_id: str) -> List[Tuple[Person, Response]]:
        """Récupère les réponses avec les personnes pour un formulaire - RETOURNE List[Tuple[Person, Response]]"""
        responses = self.get_responses_for_form(form_id)
        result = []
        for response in responses:
            person = self.get_person_by_id(response.person_id)
            if person:
                result.append((person, response))
        return result
    
    def get_responses_for_person(self, person_id: str) -> List[Response]:
        """Récupère toutes les réponses d'une personne"""
        return [r for r in self.get_all_responses() if r.person_id == person_id]
    
    def get_response_by_form_and_person(self, form_id: str, person_id: str) -> Optional[Response]:
        """Récupère une réponse spécifique (form + person)"""
        for response_dict in st.session_state.responses:
            if (response_dict["form_id"] == form_id and 
                response_dict["person_id"] == person_id):
                return Response.from_dict(response_dict)
        return None
    
    def update_response(self, response: Response) -> bool:
        """Met à jour une réponse"""
        try:
            for i, response_dict in enumerate(st.session_state.responses):
                if response_dict["id"] == response.id:
                    response.updated_at = datetime.now()
                    st.session_state.responses[i] = response.to_dict()
                    logger.info(f"✅ Réponse mise à jour: {response.id[:8]}...")
                    return True
            
            logger.warning(f"⚠️ Réponse {response.id} non trouvée pour mise à jour")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour réponse: {e}")
            return False
    
    def mark_as_responded(self, form_id: str, person_id: str, 
                         response_date: Optional[datetime] = None) -> bool:
        """Marque une personne comme ayant répondu à un formulaire"""
        try:
            response = self.get_response_by_form_and_person(form_id, person_id)
            if response:
                response.mark_as_responded(response_date)
                return self.update_response(response)
            else:
                # Créer nouvelle réponse marquée comme répondue
                new_response = Response(
                    form_id=form_id,
                    person_id=person_id,
                    has_responded=True,
                    response_date=response_date or datetime.now()
                )
                return self.add_or_update_response(new_response)
                
        except Exception as e:
            logger.error(f"❌ Erreur marquage réponse: {e}")
            return False
    
    def record_reminder_sent(self, form_id: str, person_id: str) -> bool:
        """Enregistre qu'un rappel a été envoyé"""
        try:
            response = self.get_response_by_form_and_person(form_id, person_id)
            if response:
                response.record_reminder_sent()
                return self.update_response(response)
            else:
                # Créer nouvelle réponse avec rappel
                new_response = Response(
                    form_id=form_id,
                    person_id=person_id,
                    last_reminder=datetime.now(),
                    reminder_count=1
                )
                return self.add_or_update_response(new_response)
                
        except Exception as e:
            logger.error(f"❌ Erreur enregistrement rappel: {e}")
            return False
    
    # ============ QUERIES COMPLEXES ============
    
    def get_non_responders_for_form(self, form_id: str) -> List[Tuple[Person, Response]]:
        """
        MÉTHODE CENTRALE: Récupère les non-répondants pour un formulaire avec leurs infos
        RETOURNE: List[Tuple[Person, Response]] pour compatibilité avec reminder_service
        """
        responses = self.get_responses_for_form(form_id)  # List[Response]
        non_responders = DatabaseQuery.get_non_responders(responses)  # List[Response] aussi
        
        result = []
        for response in non_responders:
            person = self.get_person_by_id(response.person_id)
            if person:
                result.append((person, response))
        
        return result
    
    def get_all_non_responders(self) -> Dict[str, List[Tuple[Person, Response]]]:
        """Récupère tous les non-répondants groupés par formulaire"""
        result = {}
        
        for form in self.get_active_forms():
            non_responders = self.get_non_responders_for_form(form.id)
            result[form.name] = non_responders
        
        return result
    
    def get_people_needing_reminders(self, form_id: str, cooldown_hours: int = 24) -> List[Tuple[Person, Response]]:
        """Récupère les personnes qui peuvent recevoir un rappel pour un formulaire"""
        responses = self.get_responses_for_form(form_id)  # List[Response]
        ready_for_reminder = DatabaseQuery.get_people_needing_reminders(responses, cooldown_hours)
        
        result = []
        for response in ready_for_reminder:
            person = self.get_person_by_id(response.person_id)
            if person:
                result.append((person, response))
        
        return result
    
    def get_statistics(self) -> ReminderStats:
        """Calcule les statistiques globales"""
        people = self.get_all_people()
        responses = self.get_all_responses()
        stats = DatabaseQuery.calculate_stats(responses, people)
        stats.last_sync = st.session_state.get('last_sync')
        return stats
    
    # ============ SYNCHRONISATION GOOGLE FORMS ============
    
    def sync_google_forms_responses(self, google_responses: Dict[str, List[Dict]]) -> Dict[str, int]:
        """
        Synchronise les réponses Google Forms avec la base locale
        
        Args:
            google_responses: Dict[google_form_id -> List[responses]]
        
        Returns:
            Dict avec les statistiques de sync
        """
        sync_stats = {"updated": 0, "created": 0, "errors": 0}
        
        try:
            for google_form_id, responses_data in google_responses.items():
                # Trouver le formulaire local
                form = self.get_form_by_google_id(google_form_id)
                if not form:
                    logger.warning(f"⚠️ Formulaire Google {google_form_id} non trouvé dans la base locale")
                    continue
                
                # Traiter chaque réponse Google
                for response_data in responses_data:
                    email = response_data.get('email', '').lower().strip()
                    if not email:
                        continue
                    
                    # Trouver la personne correspondante
                    person = self.get_person_by_email(email)
                    if not person:
                        # Créer automatiquement la personne si elle n'existe pas
                        full_name = f"{response_data.get('firstName', '')} {response_data.get('lastName', '')}".strip()
                        if not full_name:
                            full_name = email.split('@')[0]  # Fallback sur username
                        
                        person = Person(
                            name=full_name,
                            email=email
                        )
                        if self.add_person(person):
                            sync_stats["created"] += 1
                        else:
                            sync_stats["errors"] += 1
                            continue
                    
                    # Marquer comme ayant répondu
                    response_date = None
                    if response_data.get('timestamp'):
                        try:
                            # Essayer de parser la date si fournie
                            response_date = datetime.fromisoformat(response_data['timestamp'])
                        except:
                            response_date = datetime.now()
                    
                    if self.mark_as_responded(form.id, person.id, response_date):
                        sync_stats["updated"] += 1
                    else:
                        sync_stats["errors"] += 1
            
            # Mettre à jour la date de dernière sync
            st.session_state.last_sync = datetime.now()
            
            logger.info(f"✅ Sync terminée: {sync_stats['updated']} mises à jour, "
                       f"{sync_stats['created']} créations, {sync_stats['errors']} erreurs")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la synchronisation: {e}")
            sync_stats["errors"] += 1
        
        return sync_stats
    
    # ============ IMPORT/EXPORT & UTILITIES ============
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Exporte toute la base de données vers un dictionnaire"""
        last_sync = st.session_state.get('last_sync')
        return {
            "people": st.session_state.people,
            "forms": st.session_state.forms,
            "responses": st.session_state.responses,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "database_version": st.session_state.get('database_version', '2.0'),
            "export_date": datetime.now().isoformat()
        }
    
    def import_from_dict(self, data: Dict[str, Any]) -> bool:
        """Importe des données depuis un dictionnaire"""
        try:
            st.session_state.people = data.get("people", [])
            st.session_state.forms = data.get("forms", [])
            st.session_state.responses = data.get("responses", [])
            
            if data.get("last_sync"):
                st.session_state.last_sync = datetime.fromisoformat(data["last_sync"])
            
            logger.info(f"✅ Import réussi: {len(st.session_state.people)} personnes, "
                       f"{len(st.session_state.forms)} formulaires, "
                       f"{len(st.session_state.responses)} réponses")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'import: {e}")
            return False
    
    def get_dataframes(self) -> Dict[str, pd.DataFrame]:
        """Retourne les données sous forme de DataFrames pour l'affichage"""
        try:
            return {
                "people": pd.DataFrame([p for p in st.session_state.people]),
                "forms": pd.DataFrame([f for f in st.session_state.forms]),
                "responses": pd.DataFrame([r for r in st.session_state.responses])
            }
        except Exception as e:
            logger.error(f"❌ Erreur création DataFrames: {e}")
            return {
                "people": pd.DataFrame(),
                "forms": pd.DataFrame(),
                "responses": pd.DataFrame()
            }
    
    def clear_all_data(self) -> bool:
        """ATTENTION: Supprime toutes les données"""
        try:
            st.session_state.people = []
            st.session_state.forms = []
            st.session_state.responses = []
            st.session_state.last_sync = None
            
            logger.warning("⚠️ TOUTES LES DONNÉES ONT ÉTÉ SUPPRIMÉES")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression données: {e}")
            return False
    
    def get_health_check(self) -> Dict[str, Any]:
        """Vérifie la santé de la base de données"""
        try:
            people_count = len(st.session_state.people)
            forms_count = len(st.session_state.forms)
            responses_count = len(st.session_state.responses)
            
            # Vérifications d'intégrité
            orphaned_responses = 0
            for response_dict in st.session_state.responses:
                response = Response.from_dict(response_dict)
                if (not self.get_person_by_id(response.person_id) or 
                    not self.get_form_by_id(response.form_id)):
                    orphaned_responses += 1
            
            return {
                "status": "healthy" if orphaned_responses == 0 else "warning",
                "people_count": people_count,
                "forms_count": forms_count,
                "responses_count": responses_count,
                "orphaned_responses": orphaned_responses,
                "last_sync": st.session_state.get('last_sync'),
                "database_version": st.session_state.get('database_version', '2.0')
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur health check: {e}")
            return {"status": "error", "error": str(e)}

# Instance globale du gestionnaire
@st.cache_resource
def get_database_manager() -> StreamlitDatabase:
    """Récupère l'instance singleton du gestionnaire de BDD"""
    return StreamlitDatabase()