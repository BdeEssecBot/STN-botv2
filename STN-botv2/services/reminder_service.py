# services/reminder_service.py
"""Service principal de rappels pour STN-bot v2 - Architecture Streamlit Native"""

import streamlit as st
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections.abc import Iterable

from database.managers import get_database_manager, StreamlitDatabase  # Changé vers managers.py
from database.models import Person, Form, Response, ReminderStats
from services.google_forms_service import get_google_forms_service, GoogleFormsService
from services.messenger_service import get_messenger_service, MessengerService
from config.settings import AppConstants

logger = logging.getLogger(__name__)

class ReminderService:
    """
    Service principal orchestrant la synchronisation et l'envoi de rappels
    RÉVOLUTION: Utilise uniquement la base Streamlit native + caches optimisés
    """
    
    def __init__(self):
        self.db: StreamlitDatabase = get_database_manager()
        self.google_forms: GoogleFormsService = get_google_forms_service()
        self.messenger: MessengerService = get_messenger_service()
        
        logger.info("🚀 Service de rappels v2 initialisé (Streamlit Native)")
    
    # ============ SYNCHRONISATION GOOGLE FORMS ============
    
    def sync_all_forms(self, show_progress: bool = True) -> Dict[str, Any]:
        """
        Synchronise tous les formulaires actifs avec Google Forms
        
        Args:
            show_progress: Afficher la progress bar
            
        Returns:
            Résultats de synchronisation
        """
        logger.info("🔄 Début synchronisation complète avec Google Forms")
        
        try:
            # Récupérer les formulaires actifs
            active_forms = self.db.get_active_forms()
            
            if not active_forms:
                logger.warning("⚠️ Aucun formulaire actif trouvé")
                return {
                    "status": "warning",
                    "message": "Aucun formulaire actif à synchroniser",
                    "forms_processed": 0
                }
            
            # Préparer les configurations pour l'API Google
            form_configs = []
            for form in active_forms:
                if form.google_form_id and form.is_active:
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
            
            # Appel groupé à Google Forms (avec cache)
            google_responses = self.google_forms.get_multiple_forms_responses(form_configs)
            
            # Synchroniser avec la base locale
            sync_stats = self.db.sync_google_forms_responses(google_responses)
            
            # Résumé de synchronisation
            summary = self.google_forms.get_sync_summary(google_responses)
            summary.update(sync_stats)
            summary["status"] = "success"
            summary["forms_processed"] = len(form_configs)
            
            logger.info(f"✅ Synchronisation terminée: {sync_stats['updated']} mises à jour, "
                       f"{sync_stats['created']} nouvelles personnes")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la synchronisation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "forms_processed": 0
            }
    
    def sync_specific_form(self, form_id: str) -> Dict[str, Any]:
        """
        Synchronise un formulaire spécifique
        
        Args:
            form_id: ID du formulaire (interne)
            
        Returns:
            Résultat de synchronisation
        """
        logger.info(f"🔄 Synchronisation formulaire spécifique: {form_id[:8]}...")
        
        try:
            form = self.db.get_form_by_id(form_id)
            if not form:
                return {
                    "status": "error",
                    "error": "Formulaire non trouvé",
                    "form_id": form_id
                }
            
            if not form.google_form_id:
                return {
                    "status": "error",
                    "error": "Google Form ID manquant",
                    "form_name": form.name
                }
            
            # Synchroniser ce formulaire seulement
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
            
            logger.info(f"✅ Formulaire '{form.name}' synchronisé: {sync_stats['updated']} mises à jour")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur sync formulaire {form_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "form_id": form_id
            }
    
    # ============ GESTION DES RAPPELS ============
    
    def send_reminders_for_all_forms(self, sync_first: bool = True,
                                   custom_message_template: Optional[str] = None,
                                   cooldown_hours: int = 24) -> Dict[str, Any]:
        """
        Envoie des rappels pour tous les formulaires actifs
        
        Args:
            sync_first: Synchroniser avant envoi
            custom_message_template: Template de message personnalisé
            cooldown_hours: Délai minimum entre rappels
            
        Returns:
            Statistiques d'envoi
        """
        logger.info("📧 Début envoi rappels pour tous les formulaires")
        
        results = {
            "sync_results": None,
            "reminder_results": {},
            "total_sent": 0,
            "total_failed": 0,
            "start_time": datetime.now()
        }
        
        try:
            # Étape 1: Synchronisation optionnelle
            if sync_first:
                logger.info("🔄 Synchronisation préalable activée")
                sync_results = self.sync_all_forms(show_progress=True)
                results["sync_results"] = sync_results
                
                if sync_results["status"] == "error":
                    logger.error("❌ Échec synchronisation, arrêt des rappels")
                    results["status"] = "sync_failed"
                    return results
            
            # Étape 2: Récupérer tous les non-répondants
            all_non_responders = self.db.get_all_non_responders()
            
            if not all_non_responders:
                logger.info("✅ Aucun rappel nécessaire")
                results["status"] = "no_reminders_needed"
                return results
            
            # Étape 3: Envoyer les rappels par formulaire
            for form_name, non_responders in all_non_responders.items():
                if not non_responders:
                    continue
                
                # Filtrer selon le cooldown
                eligible_for_reminder = []
                for person, response in non_responders:
                    if response.can_send_reminder(cooldown_hours):
                        eligible_for_reminder.append((person, response))
                
                if not eligible_for_reminder:
                    logger.info(f"📋 {form_name}: Tous en cooldown, aucun rappel envoyé")
                    results["reminder_results"][form_name] = {
                        "total_non_responders": len(non_responders),
                        "eligible_for_reminder": 0,
                        "sent": 0,
                        "failed": 0,
                        "reason": "Tous en période de cooldown"
                    }
                    continue
                
                # Envoyer les rappels pour ce formulaire
                form_results = self._send_reminders_for_form_list(
                    eligible_for_reminder, custom_message_template
                )
                
                results["reminder_results"][form_name] = form_results
                results["total_sent"] += form_results["sent"]
                results["total_failed"] += form_results["failed"]
                
                logger.info(f"📋 {form_name}: {form_results['sent']}/{len(eligible_for_reminder)} rappels envoyés")
            
            results["status"] = "success"
            results["end_time"] = datetime.now()
            results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()
            
            logger.info(f"✅ Rappels terminés: {results['total_sent']} envoyés, "
                       f"{results['total_failed']} échecs en {results['duration']:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi rappels globaux: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            return results
    
    def send_reminders_for_form(self, form_id: str, sync_first: bool = True,
                               custom_message_template: Optional[str] = None,
                               cooldown_hours: int = 24) -> Dict[str, Any]:
        """
        Envoie des rappels pour un formulaire spécifique
        
        Args:
            form_id: ID du formulaire
            sync_first: Synchroniser avant envoi
            custom_message_template: Template personnalisé
            cooldown_hours: Délai minimum entre rappels
            
        Returns:
            Résultats d'envoi
        """
        logger.info(f"📧 Envoi rappels pour formulaire {form_id[:8]}...")
        
        try:
            # Vérifier que le formulaire existe
            form = self.db.get_form_by_id(form_id)
            if not form:
                return {
                    "status": "error",
                    "error": "Formulaire non trouvé",
                    "form_id": form_id
                }
            
            # Synchronisation optionnelle
            sync_result = None
            if sync_first:
                sync_result = self.sync_specific_form(form_id)
                if sync_result["status"] == "error":
                    logger.warning(f"⚠️ Échec sync {form.name}, continuation avec données actuelles")
            
            # Récupérer les non-répondants
            non_responders = self.db.get_non_responders_for_form(form_id)
            
            if not non_responders:
                return {
                    "status": "success",
                    "form_name": form.name,
                    "message": "Aucun rappel nécessaire",
                    "sent": 0,
                    "sync_result": sync_result
                }
            
            # Filtrer selon le cooldown
            eligible_for_reminder = []
            for person, response in non_responders:
                if response.can_send_reminder(cooldown_hours):
                    eligible_for_reminder.append((person, response))
            
            if not eligible_for_reminder:
                return {
                    "status": "success",
                    "form_name": form.name,
                    "message": "Tous les non-répondants sont en période de cooldown",
                    "total_non_responders": len(non_responders),
                    "eligible": 0,
                    "sent": 0,
                    "sync_result": sync_result
                }
            
            # Envoyer les rappels
            reminder_results = self._send_reminders_for_form_list(
                eligible_for_reminder, custom_message_template
            )
            
            result = {
                "status": "success",
                "form_name": form.name,
                "form_id": form_id,
                "sync_result": sync_result,
                **reminder_results
            }
            
            logger.info(f"✅ Rappels '{form.name}': {reminder_results['sent']}/{len(eligible_for_reminder)} envoyés")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur rappels formulaire {form_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "form_id": form_id
            }
    
    def _send_reminders_for_form_list(self, reminders_list: List[Tuple[Person, Response]],
                                     custom_template: Optional[str] = None) -> Dict[str, Any]:
        """
        Envoie des rappels pour une liste de (personne, réponse)
        
        Args:
            reminders_list: Liste des rappels à envoyer
            custom_template: Template personnalisé
            
        Returns:
            Statistiques d'envoi
        """
        if not reminders_list:
            return {"sent": 0, "failed": 0, "details": []}
        
        # Préparer les messages
        messages_data = []
        for person, response in reminders_list:
            form = self.db.get_form_by_id(response.form_id)
            if not form or not person.psid:
                continue
            
            message = self.messenger.build_reminder_message(person, form, custom_template)
            messages_data.append({
                "psid": person.psid,
                "message": message,
                "person_name": person.name,
                "person_id": person.id,
                "form_id": form.id,
                "response_id": response.id
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
        
        # Mettre à jour la base de données pour les envois réussis
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
    
    # ============ RAPPORTS ET STATISTIQUES ============
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques pour le tableau de bord"""
        try:
            stats = self.db.get_statistics()
            messenger_stats = self.messenger.get_statistics(24)  # 24h
            
            # Statistiques par formulaire
            forms_stats = []
            for form in self.db.get_active_forms():
                responses = self.db.get_responses_for_form(form.id)
                non_responders = self.db.get_non_responders_for_form(form.id)

                # Normaliser la structure des réponses :
                # - peut être un itérable de `Response`
                # - ou un itérable de tuples `(Person, Response)`
                response_list: List[Any] = []
                if isinstance(responses, Iterable) and not isinstance(responses, (str, bytes)):
                    try:
                        response_list = list(responses)
                    except TypeError:
                        response_list = []
                
                if response_list and isinstance(response_list[0], tuple) and len(response_list[0]) == 2:
                    response_objs = [r for _, r in response_list]
                else:
                    response_objs = response_list

                responded_count = sum(1 for r in response_objs if getattr(r, "has_responded", False))
                total_responses = len(response_objs)

                forms_stats.append({
                    "form_name": form.name,
                    "form_id": form.id,
                    "total_responses": total_responses,
                    "responded": responded_count,
                    "pending": len(non_responders) if isinstance(non_responders, list) else 0,
                    "response_rate": (responded_count / total_responses * 100) if total_responses else 0
                })
            
            return {
                "global_stats": stats.to_dict(),
                "messenger_stats": messenger_stats,
                "forms_stats": forms_stats,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul statistiques dashboard: {e}")
            return {"error": str(e)}
    
    def generate_detailed_report(self) -> str:
        """Génère un rapport détaillé texte"""
        try:
            stats = self.get_dashboard_stats()
            
            report = "📊 RAPPORT STN-BOT V2 (STREAMLIT NATIVE)\n"
            report += "=" * 55 + "\n\n"
            
            # Statistiques globales
            global_stats = stats["global_stats"]
            report += "🌍 STATISTIQUES GLOBALES:\n"
            report += f"• Personnes totales: {global_stats['total_people']}\n"
            report += f"• Réponses totales: {global_stats['total_responses']}\n"
            report += f"• Rappels en attente: {global_stats['pending_reminders']}\n"
            report += f"• Taux de réussite: {global_stats['success_rate']:.1f}%\n"
            
            if global_stats.get("last_sync"):
                last_sync = datetime.fromisoformat(global_stats["last_sync"])
                report += f"• Dernière sync: {last_sync.strftime('%d/%m/%Y %H:%M')}\n"
            
            report += "\n"
            
            # Statistiques Messenger
            msg_stats = stats["messenger_stats"]
            if "error" not in msg_stats:
                report += "📱 MESSENGER (24h):\n"
                report += f"• Messages envoyés: {msg_stats['total_messages']}\n"
                report += f"• Succès: {msg_stats['successful']} ({msg_stats['success_rate']:.1f}%)\n"
                report += f"• Échecs: {msg_stats['failed']}\n"
                report += f"• Temps moyen: {msg_stats['avg_response_time']:.2f}s\n\n"
            
            # Détail par formulaire
            report += "📋 DÉTAIL PAR FORMULAIRE:\n"
            for form_stat in stats["forms_stats"]:
                report += f"\n📄 {form_stat['form_name']}:\n"
                report += f"   • Réponses: {form_stat['responded']}/{form_stat['total_responses']}\n"
                report += f"   • En attente: {form_stat['pending']}\n"
                report += f"   • Taux: {form_stat['response_rate']:.1f}%\n"
            
            report += f"\n🕐 Rapport généré: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            report += "🚀 STN-bot v2 - Architecture Streamlit Native"
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Erreur génération rapport: {e}")
            return f"❌ Erreur génération rapport: {e}"
    
    # ============ TESTS ET DIAGNOSTICS ============
    
    def test_all_connections(self) -> Dict[str, Any]:
        """Teste toutes les connexions externes"""
        logger.info("🧪 Test de toutes les connexions")
        
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
        
        logger.info(f"🧪 Tests terminés - Statut global: {results['overall_status']}")
        return results
    
    def test_form_accessibility(self) -> Dict[str, Any]:
        """Teste l'accessibilité de tous les formulaires Google"""
        logger.info("🧪 Test accessibilité formulaires Google")
        
        active_forms = self.db.get_active_forms()
        results = {}
        
        for form in active_forms:
            if not form.google_form_id:
                results[form.name] = {
                    "status": "error",
                    "error": "Google Form ID manquant"
                }
                continue
            
            try:
                responses = self.google_forms.get_form_responses(form.google_form_id)
                results[form.name] = {
                    "status": "success",
                    "google_form_id": form.google_form_id,
                    "responses_found": len(responses),
                    "unique_emails": len(set(r.get('email', '') for r in responses if r.get('email')))
                }
            except Exception as e:
                results[form.name] = {
                    "status": "error",
                    "google_form_id": form.google_form_id,
                    "error": str(e)
                }
        
        # Statistiques globales
        total_forms = len(results)
        accessible_forms = len([r for r in results.values() if r.get("status") == "success"])
        
        summary = {
            "total_forms": total_forms,
            "accessible_forms": accessible_forms,
            "success_rate": (accessible_forms / total_forms * 100) if total_forms > 0 else 0,
            "forms_details": results,
            "test_timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"🧪 Test formulaires: {accessible_forms}/{total_forms} accessibles")
        return summary
    
    # ============ UTILITAIRES ============
    
    def preview_reminders(self, form_id: Optional[str] = None, 
                         cooldown_hours: int = 24) -> Dict[str, Any]:
        """
        Prévisualise les rappels qui seraient envoyés (sans les envoyer)
        
        Args:
            form_id: ID formulaire spécifique (optionnel)
            cooldown_hours: Délai minimum entre rappels
            
        Returns:
            Aperçu des rappels
        """
        try:
            preview = {
                "total_reminders": 0,
                "forms_preview": {},
                "timestamp": datetime.now().isoformat()
            }
            
            if form_id:
                # Preview pour un formulaire spécifique
                form = self.db.get_form_by_id(form_id)
                if not form:
                    return {"error": "Formulaire non trouvé"}
                
                non_responders = self.db.get_non_responders_for_form(form_id)
                eligible = [
                    (person, response) for person, response in non_responders
                    if response.can_send_reminder(cooldown_hours) and person.psid
                ]
                
                preview["forms_preview"][form.name] = {
                    "form_id": form_id,
                    "total_non_responders": len(non_responders),
                    "eligible_for_reminder": len(eligible),
                    "people": [
                        {
                            "name": person.name,
                            "email": person.email,
                            "last_reminder": response.last_reminder.isoformat() if response.last_reminder else None,
                            "reminder_count": response.reminder_count
                        }
                        for person, response in eligible
                    ]
                }
                preview["total_reminders"] = len(eligible)
                
            else:
                # Preview pour tous les formulaires
                all_non_responders = self.db.get_all_non_responders()
                
                for form_name, non_responders in all_non_responders.items():
                    eligible = [
                        (person, response) for person, response in non_responders
                        if response.can_send_reminder(cooldown_hours) and person.psid
                    ]
                    
                    preview["forms_preview"][form_name] = {
                        "total_non_responders": len(non_responders),
                        "eligible_for_reminder": len(eligible),
                        "people": [
                            {
                                "name": person.name,
                                "email": person.email,
                                "last_reminder": response.last_reminder.isoformat() if response.last_reminder else None,
                                "reminder_count": response.reminder_count
                            }
                            for person, response in eligible
                        ]
                    }
                    preview["total_reminders"] += len(eligible)
            
            return preview
            
        except Exception as e:
            logger.error(f"❌ Erreur preview rappels: {e}")
            return {"error": str(e)}
    
    def get_person_status(self, person_email: str) -> Dict[str, Any]:
        """
        Récupère le statut complet d'une personne
        
        Args:
            person_email: Email de la personne
            
        Returns:
            Statut détaillé
        """
        try:
            person = self.db.get_person_by_email(person_email)
            if not person:
                return {"error": "Personne non trouvée"}
            
            responses = self.db.get_responses_for_person(person.id)
            
            status = {
                "person": {
                    "name": person.name,
                    "email": person.email,
                    "psid": person.psid,
                    "created_at": person.created_at.isoformat() if person.created_at else None
                },
                "forms_status": [],
                "summary": {
                    "total_forms": len(responses),
                    "responded": 0,
                    "pending": 0,
                    "total_reminders_sent": 0
                }
            }
            
            for response in responses:
                form = self.db.get_form_by_id(response.form_id)
                if form:
                    form_status = {
                        "form_name": form.name,
                        "has_responded": response.has_responded,
                        "response_date": response.response_date.isoformat() if response.response_date else None,
                        "last_reminder": response.last_reminder.isoformat() if response.last_reminder else None,
                        "reminder_count": response.reminder_count,
                        "can_send_reminder": response.can_send_reminder()
                    }
                    
                    status["forms_status"].append(form_status)
                    
                    if response.has_responded:
                        status["summary"]["responded"] += 1
                    else:
                        status["summary"]["pending"] += 1
                    
                    status["summary"]["total_reminders_sent"] += response.reminder_count
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Erreur statut personne {person_email}: {e}")
            return {"error": str(e)}
    
    def cleanup_orphaned_data(self) -> Dict[str, Any]:
        """Nettoie les données orphelines dans la base"""
        logger.info("🧹 Nettoyage des données orphelines")
        
        cleanup_stats: Dict[str, Any] = {  # Type explicite
            "orphaned_responses_removed": 0,
            "invalid_people_removed": 0,
            "inactive_forms_responses_cleaned": 0
        }
        
        try:
            # Nettoyer les réponses orphelines (sans personne ou formulaire valide)
            all_responses = self.db.get_all_responses()
            for response in all_responses:
                person = self.db.get_person_by_id(response.person_id)
                form = self.db.get_form_by_id(response.form_id)
                
                if not person or not form:
                    # Supprimer la réponse orpheline
                    st.session_state.responses = [
                        r for r in st.session_state.responses 
                        if r["id"] != response.id
                    ]
                    cleanup_stats["orphaned_responses_removed"] += 1
            
            # Nettoyer les personnes sans email ni PSID valide
            all_people = self.db.get_all_people()
            for person in all_people:
                if not person.is_valid():
                    self.db.delete_person(person.id)
                    cleanup_stats["invalid_people_removed"] += 1
            
            logger.info(f"🧹 Nettoyage terminé: {sum(v for v in cleanup_stats.values() if isinstance(v, int))} éléments supprimés")
            
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage: {e}")
            cleanup_stats["error"] = str(e)
        
        return cleanup_stats

# Factory function pour Streamlit
@st.cache_resource
def get_reminder_service() -> ReminderService:
    """Récupère l'instance singleton du service de rappels"""
    return ReminderService()