# database/repositories.py - VERSION CORRIGÉE
"""Repository pattern for database operations"""

import sqlite3
import logging
from typing import List, Optional, Tuple, Dict, Any, Union, cast
from datetime import datetime, timedelta

from .models import Person, Form, Response
from .sqlite_manager import get_database_manager
from utils.errors import DatabaseError, handle_error

logger = logging.getLogger(__name__)

class BaseRepository:
    """Base repository with common functionality"""
    
    def __init__(self):
        self.db = get_database_manager()
    
    def _handle_db_error(self, error: Exception, operation: str, fallback=None):
        """Handle database errors consistently"""
        return handle_error(
            DatabaseError(f"{operation}: {error}"),
            f"Database {operation}",
            fallback,
            show_user=False
        )

class PersonRepository(BaseRepository):
    """Repository for Person operations"""
    
    def find_all(self) -> List[Person]:
        """Get all people"""
        try:
            return self.db.get_all_people()
        except Exception as e:
            return self._handle_db_error(e, "find_all_people", [])
    
    def find_by_email(self, email: str) -> Optional[Person]:
        """Find person by email"""
        try:
            return self.db.get_person_by_email(email)
        except Exception as e:
            return self._handle_db_error(e, "find_by_email", None)
    
    def find_by_psid(self, psid: str) -> Optional[Person]:
        """Find person by PSID"""
        try:
            return self.db.get_person_by_psid(psid)
        except Exception as e:
            return self._handle_db_error(e, "find_by_psid", None)
    
    def create(self, person: Person) -> bool:
        """Create a new person"""
        try:
            return self.db.add_person(person)
        except Exception as e:
            self._handle_db_error(e, "create_person", False)
            return False
    
    def delete(self, person_id: str) -> bool:
        """Delete person"""
        try:
            return self.db.delete_person(person_id)
        except Exception as e:
            self._handle_db_error(e, "delete_person", False)
            return False

class FormRepository(BaseRepository):
    """Repository for Form operations"""
    
    def find_all(self) -> List[Tuple[Form, List[str]]]:
        """Get all forms with expected people"""
        try:
            return self.db.get_all_forms()
        except Exception as e:
            return self._handle_db_error(e, "find_all_forms", [])
    
    def find_active(self) -> List[Tuple[Form, List[str]]]:
        """Get active forms"""
        try:
            return self.db.get_active_forms()
        except Exception as e:
            return self._handle_db_error(e, "find_active_forms", [])
    
    def find_by_id(self, form_id: str) -> Optional[Tuple[Form, List[str]]]:
        """Find form by ID"""
        try:
            return self.db.get_form_by_id(form_id)
        except Exception as e:
            return self._handle_db_error(e, "find_form_by_id", None)
    
    def create(self, form: Form, expected_people_ids: List[str]) -> bool:
        """Create new form"""
        try:
            return self.db.add_form(form, expected_people_ids)
        except Exception as e:
            self._handle_db_error(e, "create_form", False)
            return False
    
    def get_stats(self, form_id: str) -> Dict[str, int]:
        """Get form statistics"""
        try:
            return self.db.get_form_stats(form_id)
        except Exception as e:
            return self._handle_db_error(e, "get_form_stats", 
                                       {"total": 0, "responded": 0, "pending": 0})

class ResponseRepository(BaseRepository):
    """Repository for Response operations"""
    
    def find_non_responders(self, form_id: str) -> List[Tuple[Person, Response]]:
        """Find non-responders for a form"""
        try:
            return self.db.get_non_responders_for_form(form_id)
        except Exception as e:
            return self._handle_db_error(e, "find_non_responders", [])
    
    def find_needing_reminders(self, form_id: str, 
                              cooldown_hours: int = 24) -> List[Tuple[Person, Response]]:
        """Find people needing reminders"""
        try:
            return self.db.get_people_needing_reminders(form_id, cooldown_hours)
        except Exception as e:
            return self._handle_db_error(e, "find_needing_reminders", [])
    
    def mark_responded(self, form_id: str, person_id: str, 
                      response_date: Optional[datetime] = None) -> bool:
        """Mark person as responded"""
        try:
            return self.db.mark_as_responded(form_id, person_id, response_date)
        except Exception as e:
            self._handle_db_error(e, "mark_responded", False)
            return False
    
    def record_reminder(self, form_id: str, person_id: str) -> bool:
        """Record that reminder was sent"""
        try:
            return self.db.record_reminder_sent(form_id, person_id)
        except Exception as e:
            self._handle_db_error(e, "record_reminder", False)
            return False

# Repository factory - VERSION CORRIGÉE avec types explicites
class RepositoryFactory:
    """Factory for repository instances with correct typing"""
    
    _instances: Dict[str, Union[PersonRepository, FormRepository, ResponseRepository]] = {}
    
    @classmethod
    def get_person_repository(cls) -> PersonRepository:
        """Get PersonRepository instance with correct typing"""
        if "person" not in cls._instances:
            cls._instances["person"] = PersonRepository()
        
        # Cast explicite pour satisfaire le type checker
        repo = cls._instances["person"]
        if not isinstance(repo, PersonRepository):
            # Failsafe: recréer si le type n'est pas correct
            cls._instances["person"] = PersonRepository()
            repo = cls._instances["person"]
        
        return cast(PersonRepository, repo)
    
    @classmethod  
    def get_form_repository(cls) -> FormRepository:
        """Get FormRepository instance with correct typing"""
        if "form" not in cls._instances:
            cls._instances["form"] = FormRepository()
        
        # Cast explicite pour satisfaire le type checker
        repo = cls._instances["form"]
        if not isinstance(repo, FormRepository):
            # Failsafe: recréer si le type n'est pas correct
            cls._instances["form"] = FormRepository()
            repo = cls._instances["form"]
        
        return cast(FormRepository, repo)
    
    @classmethod
    def get_response_repository(cls) -> ResponseRepository:
        """Get ResponseRepository instance with correct typing"""
        if "response" not in cls._instances:
            cls._instances["response"] = ResponseRepository()
        
        # Cast explicite pour satisfaire le type checker
        repo = cls._instances["response"]
        if not isinstance(repo, ResponseRepository):
            # Failsafe: recréer si le type n'est pas correct
            cls._instances["response"] = ResponseRepository()
            repo = cls._instances["response"]
        
        return cast(ResponseRepository, repo)
    
    @classmethod
    def clear_instances(cls) -> None:
        """Clear all repository instances (useful for testing)"""
        cls._instances.clear()

# Fonctions helper pour utilisation directe
def get_person_repository() -> PersonRepository:
    """Get PersonRepository instance - fonction utilitaire"""
    return RepositoryFactory.get_person_repository()

def get_form_repository() -> FormRepository:
    """Get FormRepository instance - fonction utilitaire"""
    return RepositoryFactory.get_form_repository()

def get_response_repository() -> ResponseRepository:
    """Get ResponseRepository instance - fonction utilitaire"""
    return RepositoryFactory.get_response_repository()

# Version alternative avec génériques (plus avancée)
from typing import TypeVar, Type, Generic

T = TypeVar('T', bound=BaseRepository)

class TypedRepositoryFactory(Generic[T]):
    """Factory générique avec types forts (version avancée)"""
    
    _instances: Dict[Type[BaseRepository], BaseRepository] = {}
    
    @classmethod
    def get_repository(cls, repo_class: Type[T]) -> T:
        """Get repository instance with generic typing"""
        if repo_class not in cls._instances:
            cls._instances[repo_class] = repo_class()
        
        return cast(T, cls._instances[repo_class])

# Utilisation recommandée: fonctions spécialisées
__all__ = [
    'BaseRepository',
    'PersonRepository', 
    'FormRepository',
    'ResponseRepository',
    'RepositoryFactory',
    'get_person_repository',
    'get_form_repository', 
    'get_response_repository'
]