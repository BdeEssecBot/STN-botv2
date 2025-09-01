# services/reminder_service.py
"""Service de rappels adapté pour SQLite"""

import streamlit as st
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from database.sqlite_manager import get_database_manager
from database.models import Person, Form, Response
from services.google_forms_service import get_google_forms_service
from services.messenger_service import get_messenger_service
from config.settings import AppConstants

logger = logging.getLogger(__name__)

class ReminderService:
    """Service de rappels utilisant SQLite"""
    
    def __init__(self):
        self.db = get_database_manager()
        self.google_forms = get_google_forms_service()
        self.messenger = get_messenger_service()
        logger.info("Service de rappels SQLite initialisé")
    
    # ============ SYNCHRONISATION ============
    
    def sync_all_forms(self, show_progress: bool = True) -> Dict[str, Any]:
        """Synchronise tous les formulaires actifs avec Google Forms"""
        logger.info("Début synchronisation complète")
        
        try:
            # Récupérer les formulaires actifs
            active_forms = self.db.get_active_forms()
            
            if not active_forms:
                return {
                    "status": "warning",
                    "message": "Aucun formulaire actif",
                    "forms_processed": 0
                }
            
            # Préparer les configurations pour Google Forms
            form_configs = []
            for form, expected_people_ids in active_forms:
                if form.google_form_id:
                    form_configs.append({
                        "form_id": form.google_form_id,
                        "name": form.name,
                        "internal_id": form.id
                    })
            
            if not form_configs:
                return {
                    "status": "warning",
                    "message": "Aucun formulaire avec Google Form ID valide",
                    "forms_processed": 0
                }
            
            # Appel groupé à Google Forms
            google_responses = self.google_forms.get_multiple_forms_responses(form_configs)
            
            # Synchroniser avec la base SQLite
            sync_stats = self.db.sync_google_forms_responses(google_responses)
            
            result = {
                "status": "success",
                "forms_processed": len(form_configs),
                **sync_stats
            }
            
            logger.info(f"Synchronisation terminée: {sync_stats['updated']} mises à jour, "
                       f"{sync_stats['created']} créations")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur synchronisation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "forms_processed": 0
            }
    
    def sync_specific_form(self, form_id: str) -> Dict[str, Any]:
        """Synchronise un formulaire spécifique"""
        logger.info(f"Synchronisation formulaire: {form_id}")
        
        try:
            form_data = self.db.get_form_by_id(form_id)
            if not form_data:
                return {
                    "status": "error",
                    "error": "Formulaire non trouvé",
                    "form_id": form_id
                }
            
            form, _ = form_data
            
            if not form.google_form_id:
                return {
                    "status": "error",
                    "error": "Google Form ID manquant",
                    "form_name": form.name
                }
            
            # Synchroniser ce formulaire
            form_configs = [{
                "form_id": form.google_form_id,
                "name": form.name,
                "internal_id": form.id
            }]
            
            google_responses = self.google_forms.get_multiple_forms_responses(form_configs)
            sync_stats = self.db.sync_google_forms_responses(google_responses)
            
            result = {
                "status": "success",
                "form_name": form.name,
                "form_id": form_id,
                "google_form_id": form.google_form_id,
                **sync_stats
            }
            
            logger.info(f"Formulaire '{form.name}' synchronisé: {sync_stats['updated']} mises à jour")
            return result
            
        except Exception as e:
            logger.error(f"Erreur sync formulaire {form_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "form_id": form_id
            }
    
    # ============ ENVOI DE RAPPELS ============
    
    def send_reminders_for_all_forms(self, sync_first: bool = True,
                                   custom_message_template: Optional[str] = None,
                                   cooldown_hours: int = 24) -> Dict[str, Any]:
        """Envoie des rappels pour tous les formulaires actifs"""
        logger.info("Début envoi rappels pour tous les formulaires")
        
        results = {
            "sync_results": None,
            "reminder_results": {},
            "total_sent": 0,
            "total_failed": 0,
            "start_time": datetime.now()
        }
        
        try:
            # Synchronisation optionnelle
            if sync_first:
                logger.info("Synchronisation préalable")
                sync_results = self.sync_all_forms(show_progress=True)
                results["sync_results"] = sync_results
                
                if sync_results["status"] == "error":
                    logger.error("Échec synchronisation")
                    results["status"] = "sync_failed"
                    return results
            
            # Récupérer tous les formulaires actifs
            active_forms = self.db.get_active_forms()
            
            if not active_forms:
                results["status"] = "no_forms"
                return results
            
            # Traiter chaque formulaire
            for form, expected_people_ids in active_forms:
                # Récupérer les personnes pouvant recevoir un rappel
                people_needing_reminders = self.db.get_people_needing_reminders(form.id, cooldown_hours)
                
                if not people_needing_reminders:
                    results["reminder_results"][form.name] = {
                        "sent": 0,
                        "failed": 0,
                        "reason": "Aucun rappel nécessaire"
                    }
                    continue
                
                # Envoyer les rappels pour ce formulaire
                form_results = self._send_reminders_for_people_list(
                    form, people_needing_reminders, custom_message_template
                )
                
                results["reminder_results"][form.name] = form_results
                results["total_sent"] += form_results["sent"]
                results["total_failed"] += form_results["failed"]
                
                logger.info(f"{form.name}: {form_results['sent']} rappels envoyés")
            
            results["status"] = "success"
            results["end_time"] = datetime.now()
            results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()
            
            logger.info(f"Rappels terminés: {results['total_sent']} envoyés, "
                       f"{results['total_failed']} échecs")
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur envoi rappels globaux: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            return results
    
    def send_reminders_for_form(self, form_id: str, sync_first: bool = True,
                               custom_message_template: Optional[str] = None,
                               cooldown_hours: int = 24) -> Dict[str, Any]:
        """Envoie des rappels pour un formulaire spécifique"""
        logger.info(f"Envoi rappels pour formulaire: {form_id}")
        
        try:
            # Vérifier le formulaire
            form_data = self.db.get_form_by_id(form_id)
            if not form_data:
                return {
                    "status": "error",
                    "error": "Formulaire non trouvé",
                    "form_id": form_id
                }
            
            form, expected_people_ids = form_data
            
            # Synchronisation optionnelle
            sync_result = None
            if sync_first:
                sync_result = self.sync_specific_form(form_id)
                if sync_result["status"] == "error":
                    logger.warning(f"Échec sync {form.name}, continuation")
            
            # Récupérer les personnes nécessitant un rappel
            people_needing_reminders = self.db.get_people_needing_reminders(form_id, cooldown_hours)
            
            if not people_needing_reminders:
                return {
                    "status": "success",
                    "form_name": form.name,
                    "message": "Aucun rappel nécessaire",
                    "sent": 0,
                    "sync_result": sync_result
                }
            
            # Envoyer les rappels
            reminder_results = self._send_reminders_for_people_list(
                form, people_needing_reminders, custom_message_template
            )
            
            result = {
                "status": "success",
                "form_name": form.name,
                "form_id": form_id,
                "sync_result": sync_result,
                **reminder_results
            }
            
            logger.info(f"Rappels '{form.name}': {reminder_results['sent']} envoyés")
            return result
            
        except Exception as e:
            logger.error(f"Erreur rappels formulaire {form_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "form_id": form_id
            }
    
    def _send_reminders_for_people_list(self, form: Form, 
                                      people_and_responses: List[Tuple[Person, Response]],
                                      custom_template: Optional[str] = None) -> Dict[str, Any]:
        """Envoie des rappels pour une liste de personnes"""
        if not people_and_responses:
            return {"sent": 0, "failed": 0, "details": []}
        
        # Préparer les messages
        messages_data = []
        for person, response in people_and_responses:
            if not person.psid:
                continue
            
            message = self.messenger.build_reminder_message(person, form, custom_template)
            messages_data.append({
                "psid": person.psid,
                "message": message,
                "person_name": person.name,
                "person_id": person.id,
                "form_id": form.id
            })
        
        if not messages_data:
            return {
                "sent": 0,
                "failed": 0,
                "details": [],
                "error": "Aucun PSID valide trouvé"
            }
        
        # Envoi en lot
        send_results = self.messenger.send_bulk_messages(messages_data, show_progress=True)
        
        # Enregistrer les rappels envoyés avec succès
        for i, result in enumerate(send_results["results"]):
            if result["success"]:
                msg_data = messages_data[i]
                self.db.record_reminder_sent(msg_data["form_id"], msg_data["person_id"])
        
        return {
            "sent": send_results["successful"],
            "failed": send_results["failed"],
            "total_time": send_results["total_time"],
            "success_rate": send_results["success_rate"],
            "details": send_results["results"]
        }
    
    # ============ STATISTIQUES ET RAPPORTS ============
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques pour le dashboard"""
        try:
            stats = self.db.get_statistics()
            messenger_stats = self.messenger.get_statistics(24)  # 24h
            
            # Statistiques par formulaire
            forms_stats = []
            for form, expected_people_ids in self.db.get_active_forms():
                form_stats = self.db.get_form_stats(form.id)
                forms_stats.append({
                    "form_name": form.name,
                    "form_id": form.id,
                    "total_responses": form_stats["total"],
                    "responded": form_stats["responded"],
                    "pending": form_stats["pending"],
                    "response_rate": (form_stats["responded"] / form_stats["total"] * 100) 
                                   if form_stats["total"] > 0 else 0
                })
            
            return {
                "global_stats": stats.to_dict(),
                "messenger_stats": messenger_stats,
                "forms_stats": forms_stats,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur stats dashboard: {e}")
            return {"error": str(e)}
    
    def preview_reminders(self, form_id: Optional[str] = None, 
                         cooldown_hours: int = 24) -> Dict[str, Any]:
        """Prévisualise les rappels qui seraient envoyés"""
        try:
            preview = {
                "total_reminders": 0,
                "forms_preview": {},
                "timestamp": datetime.now().isoformat()
            }
            
            if form_id:
                # Preview pour un formulaire spécifique
                form_data = self.db.get_form_by_id(form_id)
                if not form_data:
                    return {"error": "Formulaire non trouvé"}
                
                form, _ = form_data
                people_needing_reminders = self.db.get_people_needing_reminders(form_id, cooldown_hours)
                
                preview["forms_preview"][form.name] = {
                    "form_id": form_id,
                    "eligible_for_reminder": len(people_needing_reminders),
                    "people": [
                        {
                            "name": person.name,
                            "email": person.email or "",
                            "last_reminder": response.last_reminder.isoformat() 
                                           if response.last_reminder else None,
                            "reminder_count": response.reminder_count
                        }
                        for person, response in people_needing_reminders
                    ]
                }
                preview["total_reminders"] = len(people_needing_reminders)
                
            else:
                # Preview pour tous les formulaires
                for form, _ in self.db.get_active_forms():
                    people_needing_reminders = self.db.get_people_needing_reminders(form.id, cooldown_hours)
                    
                    preview["forms_preview"][form.name] = {
                        "eligible_for_reminder": len(people_needing_reminders),
                        "people": [
                            {
                                "name": person.name,
                                "email": person.email or "",
                                "last_reminder": response.last_reminder.isoformat() 
                                               if response.last_reminder else None,
                                "reminder_count": response.reminder_count
                            }
                            for person, response in people_needing_reminders
                        ]
                    }
                    preview["total_reminders"] += len(people_needing_reminders)
            
            return preview
            
        except Exception as e:
            logger.error(f"Erreur preview rappels: {e}")
            return {"error": str(e)}
    
    # ============ TESTS ============
    
    def test_all_connections(self) -> Dict[str, Any]:
        """Teste toutes les connexions externes"""
        logger.info("Test de toutes les connexions")
        
        results = {
            "google_forms": {"status": "testing"},
            "messenger": {"status": "testing"},
            "database": {"status": "testing"},
            "overall_status": "testing"
        }
        
        # Test Google Forms
        try:
            google_test = self.google_forms.test_connection()
            results["google_forms"] = google_test
        except Exception as e:
            results["google_forms"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Test Messenger
        try:
            messenger_test = self.messenger.test_connection()
            results["messenger"] = messenger_test
        except Exception as e:
            results["messenger"] = {
                "status": "error", 
                "error": str(e)
            }
        
        # Test Database
        try:
            db_health = self.db.get_health_check()
            results["database"] = db_health
        except Exception as e:
            results["database"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Statut global
        all_success = all(
            result.get("status") in ["success", "healthy"] 
            for result in results.values() 
            if isinstance(result, dict)
        )
        
        results["overall_status"] = "success" if all_success else "warning"
        results["test_timestamp"] = datetime.now().isoformat()
        
        logger.info(f"Tests terminés - Statut: {results['overall_status']}")
        return results
    
    # ============ UTILITAIRES ============
    
    def cleanup_orphaned_data(self) -> Dict[str, Any]:
        """Nettoie les données orphelines"""
        # Avec SQLite et les contraintes de clés étrangères, 
        # les données orphelines sont automatiquement supprimées
        return {
            "orphaned_responses_removed": 0,
            "invalid_people_removed": 0,
            "message": "SQLite maintient automatiquement l'intégrité des données"
        }


# Singleton
@st.cache_resource
def get_reminder_service() -> ReminderService:
    """Récupère l'instance singleton du service de rappels"""
    return ReminderService()