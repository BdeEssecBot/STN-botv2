# database/enhanced_models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid

class UserRole(Enum):
    """Rôles utilisateurs"""
    ADMIN = "admin"
    POLE_MANAGER = "pole_manager"
    VIEWER = "viewer"

class PersonStatus(Enum):
    """Statuts des personnes"""
    ACTIVE = "active"
    PENDING_VALIDATION = "pending_validation"
    INACTIVE = "inactive"

class MessageStatus(Enum):
    """Statuts des messages"""
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"

@dataclass
class User:
    """Modèle utilisateur pour l'authentification"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    password_hash: str = ""
    role: UserRole = UserRole.VIEWER
    assigned_poles: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    
    def can_access_pole(self, pole_id: str) -> bool:
        """Vérifie si l'utilisateur peut accéder à un pôle"""
        if self.role == UserRole.ADMIN:
            return True
        return pole_id in self.assigned_poles
    
    def can_manage_pole(self, pole_id: str) -> bool:
        """Vérifie si l'utilisateur peut gérer un pôle"""
        if self.role == UserRole.ADMIN:
            return True
        return self.role == UserRole.POLE_MANAGER and pole_id in self.assigned_poles

@dataclass
class EnhancedPerson:
    """Modèle personne étendu avec statut et validation"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    psid: str = ""
    status: PersonStatus = PersonStatus.ACTIVE
    facebook_profile: Optional[Dict[str, Any]] = None
    auto_captured: bool = False  # Capturé automatiquement
    validation_notes: str = ""
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.name
    
    @property
    def display_status(self) -> str:
        """Statut affiché avec emoji"""
        status_map = {
            PersonStatus.ACTIVE: "✅ Actif",
            PersonStatus.PENDING_VALIDATION: "⏳ En attente de validation",
            PersonStatus.INACTIVE: "❌ Inactif"
        }
        return status_map.get(self.status, "❓ Inconnu")

@dataclass
class MessageHistory:
    """Historique complet des messages envoyés"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    form_id: str = ""
    person_id: str = ""
    sent_by_user_id: str = ""
    message_content: str = ""
    status: MessageStatus = MessageStatus.SENT
    facebook_message_id: Optional[str] = None
    delivery_timestamp: Optional[datetime] = None
    read_timestamp: Optional[datetime] = None
    error_details: Optional[str] = None
    response_time: Optional[float] = None
    reminder_number: int = 1  # Numéro du rappel (1er, 2e, etc.)
    template_used: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def status_emoji(self) -> str:
        """Emoji selon le statut"""
        status_map = {
            MessageStatus.SENT: "✅",
            MessageStatus.DELIVERED: "📨",
            MessageStatus.FAILED: "❌"
        }
        return status_map.get(self.status, "❓")

@dataclass
class WebhookEvent:
    """Événements reçus via webhook Facebook"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""  # message, postback, etc.
    sender_psid: str = ""
    message_text: Optional[str] = None
    sender_profile: Optional[Dict[str, Any]] = None
    processed: bool = False
    person_created: bool = False
    created_person_id: Optional[str] = None
    response_sent: bool = False
    error_details: Optional[str] = None
    raw_webhook_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)