# 3. SERVICE WEBHOOK POUR FACEBOOK MESSENGER
# services/webhook_service.py

import requests
from typing import Dict, Any, Optional
from datetime import datetime

class FacebookWebhookService:
    """Service pour gérer les webhooks Facebook Messenger"""
    
    def __init__(self, page_token: str, verify_token: str = "STN_WEBHOOK_2024"):
        self.page_token = page_token
        self.verify_token = verify_token
        self.db = None  # Sera injecté
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """Vérifie le webhook Facebook"""
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None
    
    def process_webhook_message(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Traite un message reçu via webhook"""
        results = []
        
        try:
            for entry in webhook_data.get('entry', []):
                for messaging in entry.get('messaging', []):
                    result = self._process_single_message(messaging)
                    results.append(result)
            
            return {
                "status": "success",
                "processed": len(results),
                "results": results
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "results": results
            }
    
    def _process_single_message(self, messaging: Dict[str, Any]) -> Dict[str, Any]:
        """Traite un message individuel"""
        sender_psid = messaging.get('sender', {}).get('id')
        message_text = messaging.get('message', {}).get('text')
        
        if not sender_psid:
            return {"status": "error", "error": "No sender PSID"}
        
        # Récupérer le profil de l'utilisateur
        profile = self._get_user_profile(sender_psid)
        
        # Enregistrer l'événement webhook
        if self.db:
            event_id = self.db.log_webhook_event(
                event_type="message",
                sender_psid=sender_psid,
                message_text=message_text,
                sender_profile=profile,
                raw_data=messaging
            )
            
            # Auto-créer la personne si elle n'existe pas
            person_id = self.db.auto_create_person_from_webhook(
                sender_psid, profile, event_id
            )
            
            # Envoyer une réponse automatique
            response_sent = self._send_auto_response(sender_psid, profile.get('first_name', 'Utilisateur'))
            
            if response_sent and self.db:
                self.db.execute("""
                    UPDATE webhook_events SET response_sent = 1 WHERE id = ?
                """, (event_id,))
            
            return {
                "status": "success",
                "sender_psid": sender_psid,
                "person_id": person_id,
                "profile": profile,
                "auto_response_sent": response_sent,
                "event_id": event_id
            }
        
        return {"status": "error", "error": "Database not available"}
    
    def _get_user_profile(self, psid: str) -> Dict[str, Any]:
        """Récupère le profil utilisateur Facebook"""
        try:
            url = f"https://graph.facebook.com/v17.0/{psid}"
            params = {
                "fields": "first_name,last_name,profile_pic",
                "access_token": self.page_token
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            print(f"❌ Erreur récupération profil {psid}: {e}")
            return {"first_name": "Utilisateur", "last_name": "", "error": str(e)}
    
    def _send_auto_response(self, psid: str, first_name: str) -> bool:
        """Envoie une réponse automatique"""
        try:
            message = f"Salut {first_name} ! 👋\n\nConnexion avec le bot STN établie ! ✅\n\nTu recevras désormais les rappels de formulaires directement ici.\n\nÀ bientôt ! 🚀"
            
            url = f"https://graph.facebook.com/v17.0/me/messages?access_token={self.page_token}"
            
            data = {
                "recipient": {"id": psid},
                "message": {"text": message}
            }
            
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            
            print(f"✅ Réponse automatique envoyée à {first_name} ({psid[:10]}...)")
            return True
        except Exception as e:
            print(f"❌ Erreur réponse automatique {psid}: {e}")
            return False
