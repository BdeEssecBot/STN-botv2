# database/models.py
"""Modèles de données pour STN-bot v2 - Architecture Streamlit Native"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
from config.settings import AppConstants

@dataclass
class Person:
    """Modèle pour une personne"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    psid: str = ""  # Pour Messenger
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def normalize_email(self) -> str:
        """Email normalisé pour les comparaisons"""
        return self.email.lower().strip() if self.email else ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Conversion en dictionnaire pour Streamlit"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "psid": self.psid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Person':
        """Création depuis un dictionnaire"""
        person = cls()
        person.id = data.get("id", str(uuid.uuid4()))
        person.name = data.get("name", "")
        person.email = data.get("email", "")
        person.psid = data.get("psid", "")
        
        # Parse dates
        if data.get("created_at"):
            person.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            person.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return person
    
    def is_valid(self) -> bool:
        """Validation des données"""
        return bool(self.name.strip() and (self.email.strip() or self.psid.strip()))

@dataclass
class Form:
    """Modèle pour un formulaire"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    google_form_id: str = ""
    date_envoi: Optional[datetime] = None
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def url(self) -> str:
        """URL du formulaire Google"""
        if self.google_form_id:
            return AppConstants.GOOGLE_FORM_URL_TEMPLATE.format(form_id=self.google_form_id)
        return ""
    
    @property
    def display_name(self) -> str:
        """Nom d'affichage avec émoji"""
        return f"{AppConstants.EMOJIS['forms']} {self.name}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Conversion en dictionnaire pour Streamlit"""
        return {
            "id": self.id,
            "name": self.name,
            "google_form_id": self.google_form_id,
            "date_envoi": self.date_envoi.isoformat() if self.date_envoi else None,
            "description": self.description,
            "is_active": self.is_active,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Form':
        """Création depuis un dictionnaire"""
        form = cls()
        form.id = data.get("id", str(uuid.uuid4()))
        form.name = data.get("name", "")
        form.google_form_id = data.get("google_form_id", "")
        form.description = data.get("description", "")
        form.is_active = data.get("is_active", True)
        
        # Parse dates
        if data.get("date_envoi"):
            form.date_envoi = datetime.fromisoformat(data["date_envoi"])
        if data.get("created_at"):
            form.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            form.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return form
    
    def is_valid(self) -> bool:
        """Validation des données"""
        return bool(self.name.strip() and self.google_form_id.strip())

@dataclass
class Response:
    """Modèle pour une réponse à un formulaire"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    form_id: str = ""
    person_id: str = ""
    has_responded: bool = False
    response_date: Optional[datetime] = None
    last_reminder: Optional[datetime] = None
    reminder_count: int = 0
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def needs_reminder(self) -> bool:
        """Détermine si cette personne a besoin d'un rappel"""
        return not self.has_responded
    
    def can_send_reminder(self, cooldown_hours: int = 24) -> bool:
        """Vérifie si on peut envoyer un rappel (cooldown)"""
        if not self.needs_reminder():
            return False
        
        if not self.last_reminder:
            return True
        
        time_since_last = datetime.now() - self.last_reminder
        return time_since_last.total_seconds() > (cooldown_hours * 3600)
    
    def mark_as_responded(self, response_date: Optional[datetime] = None):
        """Marque comme ayant répondu"""
        self.has_responded = True
        self.response_date = response_date or datetime.now()
        self.updated_at = datetime.now()
    
    def record_reminder_sent(self):
        """Enregistre qu'un rappel a été envoyé"""
        self.last_reminder = datetime.now()
        self.reminder_count += 1
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Conversion en dictionnaire pour Streamlit"""
        return {
            "id": self.id,
            "form_id": self.form_id,
            "person_id": self.person_id,
            "has_responded": self.has_responded,
            "response_date": self.response_date.isoformat() if self.response_date else None,
            "last_reminder": self.last_reminder.isoformat() if self.last_reminder else None,
            "reminder_count": self.reminder_count,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Response':
        """Création depuis un dictionnaire"""
        response = cls()
        response.id = data.get("id", str(uuid.uuid4()))
        response.form_id = data.get("form_id", "")
        response.person_id = data.get("person_id", "")
        response.has_responded = data.get("has_responded", False)
        response.reminder_count = data.get("reminder_count", 0)
        response.notes = data.get("notes", "")
        
        # Parse dates
        if data.get("response_date"):
            response.response_date = datetime.fromisoformat(data["response_date"])
        if data.get("last_reminder"):
            response.last_reminder = datetime.fromisoformat(data["last_reminder"])
        if data.get("created_at"):
            response.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            response.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return response
    
    def is_valid(self) -> bool:
        """Validation des données"""
        return bool(self.form_id and self.person_id)

@dataclass
class ReminderStats:
    """Statistiques des rappels"""
    total_people: int = 0
    total_responses: int = 0
    pending_reminders: int = 0
    sent_today: int = 0
    success_rate: float = 0.0
    last_sync: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_people": self.total_people,
            "total_responses": self.total_responses,
            "pending_reminders": self.pending_reminders,
            "sent_today": self.sent_today,
            "success_rate": self.success_rate,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None
        }

# Classes utilitaires pour les queries complexes

class DatabaseQuery:
    """Classe helper pour construire des requêtes sur les données"""
    
    @staticmethod
    def filter_responses_by_form(responses: List[Response], form_id: str) -> List[Response]:
        """Filtre les réponses par formulaire"""
        return [r for r in responses if r.form_id == form_id]
    
    @staticmethod
    def get_non_responders(responses: List[Response]) -> List[Response]:
        """Récupère tous les non-répondants"""
        return [r for r in responses if r.needs_reminder()]
    
    @staticmethod
    def get_people_needing_reminders(responses: List[Response], cooldown_hours: int = 24) -> List[Response]:
        """Récupère les personnes qui peuvent recevoir un rappel"""
        return [r for r in responses if r.can_send_reminder(cooldown_hours)]
    
    @staticmethod
    def calculate_stats(responses: List[Response], people: List[Person]) -> ReminderStats:
        """Calcule les statistiques globales"""
        stats = ReminderStats()
        stats.total_people = len(people)
        stats.total_responses = len(responses)
        stats.pending_reminders = len([r for r in responses if r.needs_reminder()])
        
        # Rappels envoyés aujourd'hui
        today = datetime.now().date()
        stats.sent_today = len([
            r for r in responses 
            if r.last_reminder and r.last_reminder.date() == today
        ])
        
        # Taux de réussite
        responded_count = len([r for r in responses if r.has_responded])
        stats.success_rate = (responded_count / len(responses) * 100) if responses else 0.0
        
        return stats