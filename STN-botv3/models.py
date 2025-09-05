from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid

@dataclass
class Person:
    """Modèle personne"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    psid: str = ""
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Pole:
    """Modèle pôle/département"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    color: str = "#FF6B6B"
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def display_name(self) -> str:
        return f"📁 {self.name}"

@dataclass
class Group:
    """Modèle groupe de personnes"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    member_ids: List[str] = field(default_factory=list)
    color: str = "#4CAF50"
    icon: str = "👥"
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def display_name(self) -> str:
        return f"{self.icon} {self.name}"
    
    @property
    def member_count(self) -> int:
        return len(self.member_ids)

@dataclass
class Form:
    """Modèle formulaire avec pôle"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    google_id: str = ""
    pole_id: str = ""
    people_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def url(self) -> str:
        return f"https://docs.google.com/forms/d/{self.google_id}/viewform"

@dataclass
class Response:
    """Modèle réponse"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    form_id: str = ""
    person_id: str = ""
    has_responded: bool = False
    last_reminder: Optional[datetime] = None