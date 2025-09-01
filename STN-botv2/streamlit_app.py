# database/sqlite_manager.py
"""Gestionnaire SQLite pour STN-bot v2 avec persistance complète - VERSION CORRIGÉE"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import uuid

from database.models import Person, Form, Response, ReminderStats

logger = logging.getLogger(__name__)

class SQLiteDatabase:
    """Gestionnaire de base de données SQLite avec persistance complète"""
    
    def __init__(self, db_path: str = "data/stn_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._create_tables()
        logger.info(f"Base SQLite initialisée: {self.db_path}")
    
    def _create_tables(self):
        """Crée les tables SQLite avec syntaxe compatible"""
        with sqlite3.connect(self.db_path) as conn:
            # Table people - SYNTAXE CORRIGÉE
            conn.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT,
                    psid TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Index uniques séparés pour email et psid - SOLUTION PROPRE
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_people_email 
                ON people(email) 
                WHERE email IS NOT NULL AND email != ''
            """)
            
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_people_psid 
                ON people(psid) 
                WHERE psid IS NOT NULL AND psid != ''
            """)
            
            # Table forms
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    google_form_id TEXT NOT NULL,
                    expected_people_ids TEXT,
                    description TEXT,
                    date_envoi TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Index unique pour google_form_id
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_forms_google_id 
                ON forms(google_form_id)
            """)
            
            # Table responses
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id TEXT PRIMARY KEY,
                    form_id TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    has_responded BOOLEAN DEFAULT 0,
                    response_date TEXT,
                    last_reminder TEXT,
                    reminder_count INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (form_id) REFERENCES forms (id) ON DELETE CASCADE,
                    FOREIGN KEY (person_id) REFERENCES people (id) ON DELETE CASCADE
                )
            """)
            
            # Index unique pour form_id + person_id
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_responses_form_person 
                ON responses(form_id, person_id)
            """)
            
            # Table app_metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            
            conn.commit()
            logger.info("Tables SQLite créées/vérifiées avec syntaxe corrigée")
    
    # ============ PEOPLE MANAGEMENT ============
    
    def add_person(self, person: Person) -> bool:
        """Ajoute une personne avec gestion des doublons améliorée"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Vérifier les doublons manuellement
                if person.email:
                    existing = conn.execute(
                        "SELECT id FROM people WHERE LOWER(email) = LOWER(?)", 
                        (person.email,)
                    ).fetchone()
                    if existing:
                        logger.warning(f"Email déjà existant: {person.email}")
                        return False
                
                if person.psid:
                    existing = conn.execute(
                        "SELECT id FROM people WHERE psid = ?", 
                        (person.psid,)
                    ).fetchone()
                    if existing:
                        logger.warning(f"PSID déjà existant: {person.psid}")
                        return False
                
                # Insérer la nouvelle personne
                conn.execute("""
                    INSERT INTO people (id, name, email, psid, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    person.id, person.name, person.email, person.psid,
                    person.created_at.isoformat(), person.updated_at.isoformat()
                ))
                conn.commit()
                logger.info(f"Personne ajoutée: {person.name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite ajout personne: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur ajout personne: {e}")
            return False
    
    def get_all_people(self) -> List[Person]:
        """Récupère toutes les personnes"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Pour accéder par nom de colonne
                cursor = conn.execute("SELECT * FROM people ORDER BY name")
                people = []
                for row in cursor:
                    person = Person(
                        id=row['id'], 
                        name=row['name'], 
                        email=row['email'], 
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    people.append(person)
                return people
        except Exception as e:
            logger.error(f"Erreur récupération personnes: {e}")
            return []
    
    def get_person_by_id(self, person_id: str) -> Optional[Person]:
        """Récupère une personne par ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,))
                row = cursor.fetchone()
                if row:
                    return Person(
                        id=row['id'],
                        name=row['name'], 
                        email=row['email'], 
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
            return None
        except Exception as e:
            logger.error(f"Erreur récupération personne {person_id}: {e}")
            return None
    
    def get_person_by_email(self, email: str) -> Optional[Person]:
        """Récupère une personne par email"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM people WHERE LOWER(email) = LOWER(?)", (email,))
                row = cursor.fetchone()
                if row:
                    return Person(
                        id=row['id'],
                        name=row['name'],
                        email=row['email'],
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
            return None
        except Exception as e:
            logger.error(f"Erreur récupération personne par email: {e}")
            return None
    
    def get_person_by_psid(self, psid: str) -> Optional[Person]:
        """Récupère une personne par PSID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM people WHERE psid = ?", (psid,))
                row = cursor.fetchone()
                if row:
                    return Person(
                        id=row['id'],
                        name=row['name'],
                        email=row['email'],
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
            return None
        except Exception as e:
            logger.error(f"Erreur récupération personne par PSID: {e}")
            return None
    
    def delete_person(self, person_id: str) -> bool:
        """Supprime une personne et ses réponses"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Les réponses sont supprimées automatiquement (CASCADE)
                cursor = conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
                if deleted:
                    logger.info(f"Personne {person_id} supprimée")
                return deleted
        except Exception as e:
            logger.error(f"Erreur suppression personne: {e}")
            return False
    
    # ============ FORMS MANAGEMENT ============
    
    def add_form(self, form: Form, expected_people_ids: List[str]) -> bool:
        """Ajoute un formulaire avec les personnes attendues"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Vérifier doublon Google Form ID
                existing = conn.execute(
                    "SELECT id FROM forms WHERE google_form_id = ?", 
                    (form.google_form_id,)
                ).fetchone()
                if existing:
                    logger.warning(f"Google Form ID déjà existant: {form.google_form_id}")
                    return False
                
                # Ajouter le formulaire
                conn.execute("""
                    INSERT INTO forms (id, name, google_form_id, expected_people_ids, description, 
                                     date_envoi, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    form.id, form.name, form.google_form_id, json.dumps(expected_people_ids),
                    form.description, form.date_envoi.isoformat() if form.date_envoi else None,
                    form.is_active, form.created_at.isoformat(), form.updated_at.isoformat()
                ))
                
                # Créer les réponses pour les personnes attendues
                for person_id in expected_people_ids:
                    response = Response(
                        form_id=form.id,
                        person_id=person_id,
                        has_responded=False
                    )
                    conn.execute("""
                        INSERT INTO responses (id, form_id, person_id, has_responded, 
                                             created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        response.id, response.form_id, response.person_id, response.has_responded,
                        response.created_at.isoformat(), response.updated_at.isoformat()
                    ))
                
                conn.commit()
                logger.info(f"Formulaire ajouté: {form.name} avec {len(expected_people_ids)} personnes attendues")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite ajout formulaire: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur ajout formulaire: {e}")
            return False
    
    def get_all_forms(self) -> List[Tuple[Form, List[str]]]:
        """Récupère tous les formulaires avec leurs personnes attendues"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM forms ORDER BY created_at DESC")
                forms = []
                for row in cursor:
                    form = Form(
                        id=row['id'], 
                        name=row['name'], 
                        google_form_id=row['google_form_id'],
                        description=row['description'] or "",
                        date_envoi=datetime.fromisoformat(row['date_envoi']) if row['date_envoi'] else None,
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    expected_people_ids = json.loads(row['expected_people_ids']) if row['expected_people_ids'] else []
                    forms.append((form, expected_people_ids))
                return forms
        except Exception as e:
            logger.error(f"Erreur récupération formulaires: {e}")
            return []
    
    def get_active_forms(self) -> List[Tuple[Form, List[str]]]:
        """Récupère les formulaires actifs"""
        return [(form, people_ids) for form, people_ids in self.get_all_forms() if form.is_active]
    
    def get_form_by_id(self, form_id: str) -> Optional[Tuple[Form, List[str]]]:
        """Récupère un formulaire par ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
                row = cursor.fetchone()
                if row:
                    form = Form(
                        id=row['id'],
                        name=row['name'],
                        google_form_id=row['google_form_id'],
                        description=row['description'] or "",
                        date_envoi=datetime.fromisoformat(row['date_envoi']) if row['date_envoi'] else None,
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    expected_people_ids = json.loads(row['expected_people_ids']) if row['expected_people_ids'] else []
                    return (form, expected_people_ids)
            return None
        except Exception as e:
            logger.error(f"Erreur récupération formulaire: {e}")
            return None
    
    def get_form_by_google_id(self, google_form_id: str) -> Optional[Tuple[Form, List[str]]]:
        """Récupère un formulaire par Google Form ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM forms WHERE google_form_id = ?", (google_form_id,))
                row = cursor.fetchone()
                if row:
                    form = Form(
                        id=row['id'],
                        name=row['name'],
                        google_form_id=row['google_form_id'],
                        description=row['description'] or "",
                        date_envoi=datetime.fromisoformat(row['date_envoi']) if row['date_envoi'] else None,
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    expected_people_ids = json.loads(row['expected_people_ids']) if row['expected_people_ids'] else []
                    return (form, expected_people_ids)
            return None
        except Exception as e:
            logger.error(f"Erreur récupération formulaire par Google ID: {e}")
            return None
    
    # ============ RESPONSES MANAGEMENT ============
    
    def get_responses_for_form(self, form_id: str) -> List[Response]:
        """Récupère les réponses d'un formulaire"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM responses WHERE form_id = ?", (form_id,))
                responses = []
                for row in cursor:
                    response = Response(
                        id=row['id'], 
                        form_id=row['form_id'], 
                        person_id=row['person_id'],
                        has_responded=bool(row['has_responded']),
                        response_date=datetime.fromisoformat(row['response_date']) if row['response_date'] else None,
                        last_reminder=datetime.fromisoformat(row['last_reminder']) if row['last_reminder'] else None,
                        reminder_count=row['reminder_count'], 
                        notes=row['notes'] or "",
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    responses.append(response)
                return responses
        except Exception as e:
            logger.error(f"Erreur récupération réponses: {e}")
            return []
    
    def get_form_stats(self, form_id: str) -> Dict[str, int]:
        """Récupère les statistiques d'un formulaire"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN has_responded = 1 THEN 1 END) as responded
                    FROM responses WHERE form_id = ?
                """, (form_id,))
                row = cursor.fetchone()
                if row:
                    total = row[0]
                    responded = row[1]
                    return {
                        "total": total,
                        "responded": responded,
                        "pending": total - responded
                    }
            return {"total": 0, "responded": 0, "pending": 0}
        except Exception as e:
            logger.error(f"Erreur stats formulaire: {e}")
            return {"total": 0, "responded": 0, "pending": 0}
    
    def mark_as_responded(self, form_id: str, person_id: str, response_date: Optional[datetime] = None) -> bool:
        """Marque une personne comme ayant répondu"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE responses 
                    SET has_responded = 1, response_date = ?, updated_at = ?
                    WHERE form_id = ? AND person_id = ?
                """, (
                    (response_date or datetime.now()).isoformat(),
                    datetime.now().isoformat(),
                    form_id, person_id
                ))
                updated = cursor.rowcount > 0
                conn.commit()
                return updated
        except Exception as e:
            logger.error(f"Erreur marquage réponse: {e}")
            return False
    
    def record_reminder_sent(self, form_id: str, person_id: str) -> bool:
        """Enregistre qu'un rappel a été envoyé"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE responses 
                    SET last_reminder = ?, reminder_count = reminder_count + 1, updated_at = ?
                    WHERE form_id = ? AND person_id = ?
                """, (
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    form_id, person_id
                ))
                updated = cursor.rowcount > 0
                conn.commit()
                return updated
        except Exception as e:
            logger.error(f"Erreur enregistrement rappel: {e}")
            return False
    
    def get_non_responders_for_form(self, form_id: str) -> List[Tuple[Person, Response]]:
        """Récupère les non-répondants d'un formulaire avec leurs infos"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT p.*, r.* FROM responses r
                    JOIN people p ON r.person_id = p.id
                    WHERE r.form_id = ? AND r.has_responded = 0
                    ORDER BY p.name
                """, (form_id,))
                
                non_responders = []
                for row in cursor:
                    # Person data
                    person = Person(
                        id=row['id'], 
                        name=row['name'], 
                        email=row['email'], 
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    # Response data - utiliser les colonnes avec préfixe si nécessaire
                    # SQLite JOIN peut créer des conflits de noms, on utilise les indices
                    response = Response(
                        id=row[6],  # r.id
                        form_id=row[7],  # r.form_id
                        person_id=row[8],  # r.person_id
                        has_responded=bool(row[9]),  # r.has_responded
                        response_date=datetime.fromisoformat(row[10]) if row[10] else None,  # r.response_date
                        last_reminder=datetime.fromisoformat(row[11]) if row[11] else None,  # r.last_reminder
                        reminder_count=row[12],  # r.reminder_count
                        notes=row[13] or "",  # r.notes
                        created_at=datetime.fromisoformat(row[14]),  # r.created_at
                        updated_at=datetime.fromisoformat(row[15])  # r.updated_at
                    )
                    non_responders.append((person, response))
                
                return non_responders
        except Exception as e:
            logger.error(f"Erreur récupération non-répondants: {e}")
            return []
    
    def get_people_needing_reminders(self, form_id: str, cooldown_hours: int = 24) -> List[Tuple[Person, Response]]:
        """Récupère les personnes pouvant recevoir un rappel"""
        try:
            cooldown_time = datetime.now() - timedelta(hours=cooldown_hours)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT p.*, r.* FROM responses r
                    JOIN people p ON r.person_id = p.id
                    WHERE r.form_id = ? AND r.has_responded = 0 
                    AND (r.last_reminder IS NULL OR r.last_reminder < ?)
                    AND p.psid IS NOT NULL AND p.psid != ''
                    ORDER BY p.name
                """, (form_id, cooldown_time.isoformat()))
                
                ready_for_reminder = []
                for row in cursor:
                    person = Person(
                        id=row['id'],
                        name=row['name'],
                        email=row['email'],
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    response = Response(
                        id=row[6],  # r.id
                        form_id=row[7],  # r.form_id
                        person_id=row[8],  # r.person_id
                        has_responded=bool(row[9]),
                        response_date=datetime.fromisoformat(row[10]) if row[10] else None,
                        last_reminder=datetime.fromisoformat(row[11]) if row[11] else None,
                        reminder_count=row[12],
                        notes=row[13] or "",
                        created_at=datetime.fromisoformat(row[14]),
                        updated_at=datetime.fromisoformat(row[15])
                    )
                    ready_for_reminder.append((person, response))
                
                return ready_for_reminder
        except Exception as e:
            logger.error(f"Erreur récupération rappels nécessaires: {e}")
            return []
    
    # ============ SYNC GOOGLE FORMS ============
    
    def sync_google_forms_responses(self, google_responses: Dict[str, List[Dict]]) -> Dict[str, int]:
        """Synchronise avec Google Forms"""
        sync_stats = {"updated": 0, "created": 0, "errors": 0}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                for google_form_id, responses_data in google_responses.items():
                    # Trouver le formulaire
                    form_data = self.get_form_by_google_id(google_form_id)
                    if not form_data:
                        continue
                    
                    form, _ = form_data
                    
                    for response_data in responses_data:
                        email = response_data.get('email', '').lower().strip()
                        if not email:
                            continue
                        
                        # Trouver ou créer la personne
                        person = self.get_person_by_email(email)
                        if not person:
                            full_name = f"{response_data.get('firstName', '')} {response_data.get('lastName', '')}".strip()
                            if not full_name:
                                full_name = email.split('@')[0]
                            
                            person = Person(name=full_name, email=email)
                            if self.add_person(person):
                                sync_stats["created"] += 1
                            else:
                                sync_stats["errors"] += 1
                                continue
                        
                        # Marquer comme répondu
                        response_date = None
                        if response_data.get('timestamp'):
                            try:
                                response_date = datetime.fromisoformat(response_data['timestamp'])
                            except:
                                response_date = datetime.now()
                        
                        if self.mark_as_responded(form.id, person.id, response_date):
                            sync_stats["updated"] += 1
                        else:
                            sync_stats["errors"] += 1
                
                # Mettre à jour timestamp de sync
                conn.execute("""
                    INSERT OR REPLACE INTO app_metadata (key, value, updated_at)
                    VALUES ('last_sync', ?, ?)
                """, (datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()
        
        except Exception as e:
            logger.error(f"Erreur synchronisation: {e}")
            sync_stats["errors"] += 1
        
        return sync_stats
    
    # ============ STATISTICS ============
    
    def get_statistics(self) -> ReminderStats:
        """Calcule les statistiques globales"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Compter les personnes
                cursor = conn.execute("SELECT COUNT(*) FROM people")
                total_people = cursor.fetchone()[0]
                
                # Compter les réponses
                cursor = conn.execute("SELECT COUNT(*) FROM responses")
                total_responses = cursor.fetchone()[0]
                
                # Compter les rappels en attente
                cursor = conn.execute("SELECT COUNT(*) FROM responses WHERE has_responded = 0")
                pending_reminders = cursor.fetchone()[0]
                
                # Rappels envoyés aujourd'hui
                today = datetime.now().date().isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM responses 
                    WHERE DATE(last_reminder) = ?
                """, (today,))
                sent_today = cursor.fetchone()[0]
                
                # Taux de réussite
                cursor = conn.execute("SELECT COUNT(*) FROM responses WHERE has_responded = 1")
                responded = cursor.fetchone()[0]
                success_rate = (responded / total_responses * 100) if total_responses > 0 else 0
                
                # Dernière sync
                cursor = conn.execute("SELECT value FROM app_metadata WHERE key = 'last_sync'")
                last_sync_row = cursor.fetchone()
                last_sync = datetime.fromisoformat(last_sync_row[0]) if last_sync_row else None
                
                return ReminderStats(
                    total_people=total_people,
                    total_responses=total_responses,
                    pending_reminders=pending_reminders,
                    sent_today=sent_today,
                    success_rate=success_rate,
                    last_sync=last_sync
                )
        except Exception as e:
            logger.error(f"Erreur calcul statistiques: {e}")
            return ReminderStats()
    
    # ============ UTILITIES ============
    
    def get_health_check(self) -> Dict[str, Any]:
        """Vérifie la santé de la base"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Compter les éléments
                people_count = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
                forms_count = conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
                responses_count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
                
                # Vérifier les orphelins
                orphaned = conn.execute("""
                    SELECT COUNT(*) FROM responses r
                    WHERE NOT EXISTS (SELECT 1 FROM people p WHERE p.id = r.person_id)
                    OR NOT EXISTS (SELECT 1 FROM forms f WHERE f.id = r.form_id)
                """).fetchone()[0]
                
                return {
                    "status": "healthy" if orphaned == 0 else "warning",
                    "people_count": people_count,
                    "forms_count": forms_count,
                    "responses_count": responses_count,
                    "orphaned_responses": orphaned,
                    "database_version": "2.0-sqlite-fixed"
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def clear_all_data(self) -> bool:
        """Supprime toutes les données"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM responses")
                conn.execute("DELETE FROM forms")
                conn.execute("DELETE FROM people")
                conn.execute("DELETE FROM app_metadata")
                conn.commit()
                logger.warning("Toutes les données supprimées")
                return True
        except Exception as e:
            logger.error(f"Erreur suppression données: {e}")
            return False


# Singleton avec gestion d'erreur améliorée
_db_instance = None

def get_database_manager() -> SQLiteDatabase:
    """Récupère l'instance singleton de la base SQLite avec gestion d'erreur"""
    global _db_instance
    if _db_instance is None:
        try:
            _db_instance = SQLiteDatabase()
            logger.info("✅ Instance SQLite créée avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur création instance SQLite: {e}")
            # Re-lever l'exception pour que l'application puisse la gérer
            raise
    return _db_instance