import requests
from typing import Dict, List
from database import Database
from models import Form, Person

class GoogleFormsService:
    """Service Google Forms simplifié"""
    
    def __init__(self, script_url: str):
        self.script_url = script_url
    
    def get_responses(self, google_form_id: str) -> List[Dict[str, str]]:
        """Récupère les réponses d'un formulaire"""
        try:
            response = requests.get(
                f"{self.script_url}?formId={google_form_id}",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Normaliser les réponses
            emails = data.get('emails', [])
            return [{'email': email.lower().strip()} for email in emails if email]
        except Exception:
            return []

class MessengerService:
    """Service Messenger simplifié"""
    
    def __init__(self, page_token: str):
        self.page_token = page_token
        self.base_url = "https://graph.facebook.com/v17.0/me/messages"
    
    def send_message(self, psid: str, message: str) -> bool:
        """Envoie un message"""
        try:
            response = requests.post(
                f"{self.base_url}?access_token={self.page_token}",
                json={
                    "recipient": {"id": psid},
                    "message": {"text": message}
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

class ReminderService:
    """Service de rappels unifié"""
    
    def __init__(self, db: Database, google_service: GoogleFormsService, 
                 messenger_service: MessengerService):
        self.db = db
        self.google = google_service
        self.messenger = messenger_service
    
    def sync_form(self, form: Form) -> Dict[str, int]:
        """Synchronise un formulaire avec Google Forms"""
        google_responses = self.google.get_responses(form.google_id)
        responded_emails = {resp['email'] for resp in google_responses}
        
        stats = {"updated": 0, "total": 0}
        
        for person_id in form.people_ids:
            person = self.db.get_person(person_id)
            if not person or not person.email:
                continue
            
            stats["total"] += 1
            
            if person.email.lower().strip() in responded_emails:
                if self.db.mark_responded(form.id, person_id):
                    stats["updated"] += 1
        
        return stats
    
    def send_reminders(self, form: Form, custom_message: str = None) -> Dict[str, int]:
        """Envoie des rappels pour un formulaire"""
        non_responders = self.db.get_non_responders(form.id)
        
        message = custom_message or f"""Hello {{name}},

Rappel pour remplir le formulaire "{form.name}".

Lien: {form.url}

Merci !"""
        
        stats = {"sent": 0, "failed": 0}
        
        for person, response in non_responders:
            if not person.psid:
                stats["failed"] += 1
                continue
            
            personalized_message = message.replace("{name}", person.name)
            
            if self.messenger.send_message(person.psid, personalized_message):
                self.db.record_reminder(form.id, person.id)
                stats["sent"] += 1
            else:
                stats["failed"] += 1
        
        return stats
