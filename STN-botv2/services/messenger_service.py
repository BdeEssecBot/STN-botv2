# services/messenger_service.py
"""Service Messenger optimisé pour STN-bot v2"""

import streamlit as st
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time

from config.settings import settings, AppConstants
from database.models import Person, Form

logger = logging.getLogger(__name__)

class MessengerService:
    """
    Service Messenger pour l'envoi de rappels
    OPTIMISATION: Rate limiting + historique + retry logic
    """
    
    def __init__(self):
        if settings is None:
            raise RuntimeError("Settings non initialisé - vérifiez votre configuration")
        
        self.base_url = "https://graph.facebook.com/v17.0/me/messages"
        self.access_token = settings.page_token
        self.rate_limit_delay = 1.0  # 1 seconde entre les messages
        self.last_message_time = 0.0
        
        # Historique des envois (en session state)
        if 'messenger_history' not in st.session_state:
            st.session_state.messenger_history = []
        
        logger.info("📱 Service Messenger initialisé")
    
    def send_message(self, psid: str, message: str, person_name: str = "Utilisateur") -> Dict[str, Any]:
        """
        Envoie un message via Facebook Messenger avec rate limiting
        
        Args:
            psid: Page-Scoped ID de l'utilisateur
            message: Contenu du message
            person_name: Nom de la personne (pour les logs)
            
        Returns:
            Résultat de l'envoi
        """
        try:
            # Rate limiting
            self._apply_rate_limit()
            
            # Construire la requête
            url = f"{self.base_url}?access_token={self.access_token}"
            message_data = {
                "recipient": {"id": psid},
                "message": {"text": message}
            }
            
            logger.info(f"📤 Envoi message à {person_name} (PSID: {psid[:10]}...)")
            
            # Envoyer le message
            start_time = time.time()
            response = requests.post(url, json=message_data, timeout=30)
            response_time = time.time() - start_time
            
            result = {
                "success": False,
                "person_name": person_name,
                "psid": psid,
                "message_preview": message[:50] + "..." if len(message) > 50 else message,
                "timestamp": datetime.now(),
                "response_time": response_time
            }
            
            if response.status_code == 200:
                response_data = response.json()
                result.update({
                    "success": True,
                    "message_id": response_data.get("message_id"),
                    "recipient_id": response_data.get("recipient_id"),
                    "status": "sent"
                })
                logger.info(f"✅ Message envoyé à {person_name} en {response_time:.2f}s")
            else:
                result.update({
                    "error": f"HTTP {response.status_code}",
                    "error_details": response.text[:200],
                    "status": "failed"
                })
                logger.error(f"❌ Échec envoi à {person_name}: HTTP {response.status_code}")
            
            # Ajouter à l'historique
            self._add_to_history(result)
            
            return result
            
        except requests.exceptions.Timeout:
            result = {
                "success": False,
                "person_name": person_name,
                "psid": psid,
                "error": "Timeout (30s)",
                "status": "timeout",
                "timestamp": datetime.now()
            }
            logger.error(f"⏰ Timeout envoi message à {person_name}")
            self._add_to_history(result)
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "success": False,
                "person_name": person_name,
                "psid": psid,
                "error": f"Erreur réseau: {e}",
                "status": "network_error",
                "timestamp": datetime.now()
            }
            logger.error(f"🌐 Erreur réseau envoi à {person_name}: {e}")
            self._add_to_history(result)
            return result
            
        except Exception as e:
            result = {
                "success": False,
                "person_name": person_name,
                "psid": psid,
                "error": f"Erreur inattendue: {e}",
                "status": "unexpected_error",
                "timestamp": datetime.now()
            }
            logger.error(f"💥 Erreur inattendue envoi à {person_name}: {e}")
            self._add_to_history(result)
            return result
    
    def send_bulk_messages(self, messages_data: List[Dict[str, str]], 
                          show_progress: bool = True) -> Dict[str, Any]:
        """
        Envoie plusieurs messages en lot avec progress bar
        
        Args:
            messages_data: Liste de {"psid": str, "message": str, "person_name": str}
            show_progress: Afficher la progress bar Streamlit
            
        Returns:
            Statistiques d'envoi
        """
        logger.info(f"📧 Envoi en lot de {len(messages_data)} messages")
        
        results = []
        start_time = time.time()
        
        # Progress bar Streamlit - initialisation sécurisée
        progress_bar = None
        status_text = None
        
        if show_progress and len(messages_data) > 1:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        for i, msg_data in enumerate(messages_data):
            psid = msg_data["psid"]
            message = msg_data["message"]
            person_name = msg_data.get("person_name", f"Personne {i+1}")
            
            if show_progress and len(messages_data) > 1 and progress_bar is not None and status_text is not None:
                progress = (i + 1) / len(messages_data)
                progress_bar.progress(progress)
                status_text.text(f"Envoi: {person_name} ({i+1}/{len(messages_data)})")
            
            result = self.send_message(psid, message, person_name)
            results.append(result)
        
        if show_progress and len(messages_data) > 1 and progress_bar is not None and status_text is not None:
            progress_bar.empty()
            status_text.empty()
        
        # Calculer les statistiques
        total_time = time.time() - start_time
        successful = len([r for r in results if r["success"]])
        failed = len(results) - successful
        
        stats = {
            "total_messages": len(results),
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / len(results) * 100) if results else 0,
            "total_time": total_time,
            "avg_time_per_message": total_time / len(results) if results else 0,
            "results": results
        }
        
        logger.info(f"✅ Envoi en lot terminé: {successful}/{len(results)} réussites "
                   f"en {total_time:.2f}s")
        
        return stats
    
    def build_reminder_message(self, person: Person, form: Form, 
                             custom_template: Optional[str] = None) -> str:
        """
        Construit un message de rappel personnalisé
        
        Args:
            person: Personne destinataire
            form: Formulaire concerné
            custom_template: Template personnalisé (optionnel)
            
        Returns:
            Message personnalisé
        """
        if custom_template:
            template = custom_template
        else:
            template = AppConstants.DEFAULT_REMINDER_TEMPLATE
        
        # Variables disponibles pour le template
        variables = {
            "name": person.name or "Cher/Chère participant(e)",
            "form_name": form.name,
            "form_url": form.url,
            "date_envoi": form.date_envoi.strftime("%d/%m/%Y") if form.date_envoi else "récemment"
        }
        
        try:
            message = template.format(**variables)
            logger.debug(f"Message généré pour {person.name}: {len(message)} caractères")
            return message
        except KeyError as e:
            logger.error(f"❌ Variable manquante dans le template: {e}")
            # Fallback sur un message simple
            return f"Hello {person.name},\n\nRappel pour remplir le formulaire {form.name}.\n\nLien: {form.url}"
    
    def _apply_rate_limit(self):
        """Applique le rate limiting entre les messages"""
        current_time = time.time()
        time_since_last = current_time - self.last_message_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"⏳ Rate limiting: attente {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_message_time = time.time()
    
    def _add_to_history(self, result: Dict[str, Any]):
        """Ajoute un résultat à l'historique"""
        try:
            # Limiter l'historique à 1000 entrées
            if len(st.session_state.messenger_history) >= 1000:
                st.session_state.messenger_history = st.session_state.messenger_history[-900:]
            
            # Convertir datetime en string pour la sérialisation
            history_entry = result.copy()
            if isinstance(history_entry.get("timestamp"), datetime):
                history_entry["timestamp"] = history_entry["timestamp"].isoformat()
            
            st.session_state.messenger_history.append(history_entry)
            
        except Exception as e:
            logger.error(f"❌ Erreur ajout historique: {e}")
    
    def get_recent_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Récupère l'historique récent des envois"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_history = []
            
            for entry in st.session_state.messenger_history:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time >= cutoff_time:
                    recent_history.append(entry)
            
            return recent_history
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération historique: {e}")
            return []
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Calcule les statistiques d'envoi récentes"""
        try:
            recent_history = self.get_recent_history(hours)
            
            if not recent_history:
                return {
                    "period_hours": hours,
                    "total_messages": 0,
                    "successful": 0,
                    "failed": 0,
                    "success_rate": 0.0,
                    "avg_response_time": 0.0
                }
            
            successful = len([h for h in recent_history if h.get("success", False)])
            failed = len(recent_history) - successful
            
            # Temps de réponse moyen (seulement pour les succès)
            response_times = [h.get("response_time", 0) for h in recent_history 
                            if h.get("success", False) and h.get("response_time")]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            return {
                "period_hours": hours,
                "total_messages": len(recent_history),
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / len(recent_history) * 100),
                "avg_response_time": avg_response_time
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul statistiques: {e}")
            return {"error": str(e)}
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test la connexion Messenger (envoi d'un message de test à soi-même)
        
        Returns:
            Résultat du test
        """
        try:
            # Test basique de l'API (sans envoyer de message)
            url = f"https://graph.facebook.com/v17.0/me?access_token={self.access_token}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "message": f"Token valide - Page: {data.get('name', 'Unknown')}",
                    "page_name": data.get("name"),
                    "page_id": data.get("id")
                }
            else:
                return {
                    "status": "error",
                    "message": f"Token invalide - HTTP {response.status_code}",
                    "details": response.text[:200]
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Erreur de connexion: {e}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Erreur inattendue: {e}"
            }
    
    def clear_history(self):
        """Vide l'historique des messages"""
        try:
            st.session_state.messenger_history = []
            logger.info("🧹 Historique Messenger vidé")
        except Exception as e:
            logger.error(f"❌ Erreur vidage historique: {e}")
    
    def export_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Exporte l'historique récent pour analyse"""
        return self.get_recent_history(hours)
    
    def validate_psid(self, psid: str) -> bool:
        """
        Valide qu'un PSID a le bon format
        
        Args:
            psid: PSID à valider
            
        Returns:
            True si le PSID semble valide
        """
        if not psid or len(psid) < 10:
            return False
        
        # Les PSIDs sont généralement numériques
        return psid.isdigit()

# Factory function pour Streamlit
@st.cache_resource  
def get_messenger_service() -> MessengerService:
    """Récupère l'instance singleton du service Messenger"""
    return MessengerService()