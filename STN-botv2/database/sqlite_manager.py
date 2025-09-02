# database/sqlite_manager.py
"""Gestionnaire SQLite pour STN-bot v2 avec persistance complète et support des pôles"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import uuid

from database.models import Person, Form, Response, ReminderStats, Pole

logger = logging.getLogger(__name__)

class SQLiteDatabase:
    """Gestionnaire de base de données SQLite avec persistance complète et pôles"""
    
    def __init__(self, db_path: str = "data/stn_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._create_tables()
        logger.info(f"Base SQLite initialisée: {self.db_path}")
    
    def _create_tables(self):
        """Crée les tables SQLite avec syntaxe compatible et support des pôles"""
        with sqlite3.connect(self.db_path) as conn:
            # Table poles - NOUVELLE
            conn.execute("""
                CREATE TABLE IF NOT EXISTS poles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    color TEXT DEFAULT '#FF6B6B',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Index pour recherche par nom
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_poles_name 
                ON poles(name)
            """)
            
            # Table people
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
            
            # Index uniques séparés pour email et psid
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
            
            # Table forms - MODIFIÉE avec pole_id
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    google_form_id TEXT NOT NULL,
                    pole_id TEXT,
                    expected_people_ids TEXT,
                    description TEXT,
                    date_envoi TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (pole_id) REFERENCES poles (id) ON DELETE SET NULL
                )
            """)
            
            # Vérifier si la colonne pole_id existe déjà (migration)
            cursor = conn.execute("PRAGMA table_info(forms)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'pole_id' not in columns:
                conn.execute("ALTER TABLE forms ADD COLUMN pole_id TEXT")
                logger.info("Migration: colonne pole_id ajoutée à la table forms")
            
            # Index unique pour google_form_id
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_forms_google_id 
                ON forms(google_form_id)
            """)
            
            # Index pour pole_id
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_forms_pole_id 
                ON forms(pole_id)
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
            
            # Créer un pôle par défaut si aucun existe
            cursor = conn.execute("SELECT COUNT(*) FROM poles")
            pole_count = cursor.fetchone()[0]
            
            if pole_count == 0:
                default_pole_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO poles (id, name, description, color, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    default_pole_id, "Général", "Pôle par défaut", "#2196F3",
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                # Assigner tous les formulaires existants au pôle par défaut
                conn.execute("""
                    UPDATE forms SET pole_id = ? WHERE pole_id IS NULL OR pole_id = ''
                """, (default_pole_id,))
                
                logger.info("Pôle par défaut 'Général' créé et assigné aux formulaires existants")
            
            conn.commit()
            logger.info("Tables SQLite créées/mises à jour avec support des pôles")
    
    # ============ POLES MANAGEMENT ============
    
    def add_pole(self, pole: Pole) -> bool:
        """Ajoute un pôle"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Vérifier les doublons de nom
                existing = conn.execute(
                    "SELECT id FROM poles WHERE LOWER(name) = LOWER(?)", 
                    (pole.name,)
                ).fetchone()
                if existing:
                    logger.warning(f"Nom de pôle déjà existant: {pole.name}")
                    return False
                
                conn.execute("""
                    INSERT INTO poles (id, name, description, color, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    pole.id, pole.name, pole.description, pole.color, pole.is_active,
                    pole.created_at.isoformat(), pole.updated_at.isoformat()
                ))
                conn.commit()
                logger.info(f"Pôle ajouté: {pole.name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite ajout pôle: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur ajout pôle: {e}")
            return False
    
    def get_all_poles(self) -> List[Pole]:
        """Récupère tous les pôles"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM poles ORDER BY name")
                poles = []
                for row in cursor:
                    pole = Pole(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'] or "",
                        color=row['color'] or "#FF6B6B",
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    poles.append(pole)
                return poles
        except Exception as e:
            logger.error(f"Erreur récupération pôles: {e}")
            return []
    
    def get_active_poles(self) -> List[Pole]:
        """Récupère les pôles actifs"""
        return [pole for pole in self.get_all_poles() if pole.is_active]
    
    def get_pole_by_id(self, pole_id: str) -> Optional[Pole]:
        """Récupère un pôle par ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM poles WHERE id = ?", (pole_id,))
                row = cursor.fetchone()
                if row:
                    return Pole(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'] or "",
                        color=row['color'] or "#FF6B6B",
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
            return None
        except Exception as e:
            logger.error(f"Erreur récupération pôle {pole_id}: {e}")
            return None
    
    def update_pole(self, pole_id: str, name: str, description: str, color: str, is_active: bool) -> bool:
        """Met à jour un pôle"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE poles 
                    SET name = ?, description = ?, color = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                """, (name, description, color, is_active, datetime.now().isoformat(), pole_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                if success:
                    logger.info(f"Pôle {pole_id} mis à jour")
                return success
        except Exception as e:
            logger.error(f"Erreur mise à jour pôle: {e}")
            return False
    
    def delete_pole(self, pole_id: str, move_forms_to: Optional[str] = None) -> bool:
        """Supprime un pôle (avec option de déplacement des formulaires)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Déplacer les formulaires vers un autre pôle si spécifié
                if move_forms_to:
                    conn.execute("""
                        UPDATE forms SET pole_id = ?, updated_at = ? WHERE pole_id = ?
                    """, (move_forms_to, datetime.now().isoformat(), pole_id))
                    logger.info(f"Formulaires déplacés du pôle {pole_id} vers {move_forms_to}")
                
                # Supprimer le pôle
                cursor = conn.execute("DELETE FROM poles WHERE id = ?", (pole_id,))
                success = cursor.rowcount > 0
                conn.commit()
                if success:
                    logger.info(f"Pôle {pole_id} supprimé")
                return success
        except Exception as e:
            logger.error(f"Erreur suppression pôle: {e}")
            return False
    
    def get_forms_by_pole(self, pole_id: str) -> List[Tuple[Form, List[str]]]:
        """Récupère les formulaires d'un pôle"""
        try:
            all_forms = self.get_all_forms()
            return [(form, people_ids) for form, people_ids in all_forms if form.pole_id == pole_id]
        except Exception as e:
            logger.error(f"Erreur récupération formulaires pôle {pole_id}: {e}")
            return []
    
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
                conn.row_factory = sqlite3.Row
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
                cursor = conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
                if deleted:
                    logger.info(f"Personne {person_id} supprimée")
                return deleted
        except Exception as e:
            logger.error(f"Erreur suppression personne: {e}")
            return False
    
    # ============ FORMS MANAGEMENT - MODIFIÉ AVEC PÔLES ============
    
    def add_form(self, form: Form, expected_people_ids: List[str]) -> bool:
        """Ajoute un formulaire avec les personnes attendues et pôle"""
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
                
                # Ajouter le formulaire avec pole_id
                conn.execute("""
                    INSERT INTO forms (id, name, google_form_id, pole_id, expected_people_ids, description, 
                                     date_envoi, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    form.id, form.name, form.google_form_id, form.pole_id, json.dumps(expected_people_ids),
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
                logger.info(f"Formulaire ajouté: {form.name} (pôle: {form.pole_id}) avec {len(expected_people_ids)} personnes attendues")
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
                        pole_id=row['pole_id'] or "",
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
                        pole_id=row['pole_id'] or "",
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
                        pole_id=row['pole_id'] or "",
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
            logger.info(f"🎯 Tentative marquage réponse: form_id={form_id}, person_id={person_id}")
            
            with sqlite3.connect(self.db_path) as conn:
                check_cursor = conn.execute("""
                    SELECT id, has_responded FROM responses 
                    WHERE form_id = ? AND person_id = ?
                """, (form_id, person_id))
                existing_response = check_cursor.fetchone()
                
                if existing_response:
                    logger.info(f"✅ Réponse trouvée: ID={existing_response[0]}, has_responded={existing_response[1]}")
                else:
                    logger.error(f"❌ Aucune réponse trouvée pour form_id={form_id}, person_id={person_id}")
                    return False
                
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
                
                if updated:
                    logger.info(f"✅ Réponse mise à jour avec succès")
                else:
                    logger.error(f"❌ Aucune ligne mise à jour")
                
                return updated
                
        except Exception as e:
            logger.error(f"💥 Erreur marquage réponse: {e}")
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
                    person = Person(
                        id=row['id'], 
                        name=row['name'], 
                        email=row['email'], 
                        psid=row['psid'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    response = Response(
                        id=row[6],
                        form_id=row[7],
                        person_id=row[8],
                        has_responded=bool(row[9]),
                        response_date=datetime.fromisoformat(row[10]) if row[10] else None,
                        last_reminder=datetime.fromisoformat(row[11]) if row[11] else None,
                        reminder_count=row[12],
                        notes=row[13] or "",
                        created_at=datetime.fromisoformat(row[14]),
                        updated_at=datetime.fromisoformat(row[15])
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
                        id=row[6],
                        form_id=row[7],
                        person_id=row[8],
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
            logger.info(f"🔄 Début synchronisation avec {len(google_responses)} formulaires")
            
            with sqlite3.connect(self.db_path) as conn:
                for google_form_id, responses_data in google_responses.items():
                    logger.info(f"📋 Traitement formulaire Google: {google_form_id}")
                    
                    form_data = self.get_form_by_google_id(google_form_id)
                    if not form_data:
                        logger.warning(f"❌ Formulaire non trouvé pour Google ID: {google_form_id}")
                        sync_stats["errors"] += 1
                        continue
                    
                    form, expected_people_ids = form_data
                    logger.info(f"📝 Formulaire trouvé: {form.name} avec {len(expected_people_ids)} personnes attendues")
                    
                    for response_data in responses_data:
                        email = response_data.get('email', '').lower().strip()
                        if not email:
                            logger.warning("❌ Réponse sans email, ignorée")
                            continue
                        
                        logger.info(f"📧 Traitement réponse: {email}")
                        
                        person = None
                        for person_id in expected_people_ids:
                            candidate_person = self.get_person_by_id(person_id)
                            if candidate_person and candidate_person.email:
                                if candidate_person.email.lower().strip() == email:
                                    person = candidate_person
                                    logger.info(f"✅ Personne trouvée parmi les attendues: {person.name}")
                                    break
                        
                        if not person:
                            person = self.get_person_by_email(email)
                            if person:
                                logger.info(f"✅ Personne trouvée dans la base: {person.name}")
                        
                        if not person:
                            full_name = response_data.get('fullName', '').strip()
                            first_name = response_data.get('firstName', '').strip()
                            last_name = response_data.get('lastName', '').strip()
                            
                            if full_name:
                                name = full_name
                            elif first_name or last_name:
                                name = f"{first_name} {last_name}".strip()
                            else:
                                name = email.split('@')[0]
                            
                            logger.info(f"➕ Création nouvelle personne: {name} ({email})")
                            
                            person = Person(name=name, email=email)
                            if self.add_person(person):
                                sync_stats["created"] += 1
                                logger.info(f"✅ Personne créée: {person.name}")
                                
                                expected_people_ids.append(person.id)
                                
                                conn.execute("""
                                    UPDATE forms 
                                    SET expected_people_ids = ?, updated_at = ?
                                    WHERE id = ?
                                """, (
                                    json.dumps(expected_people_ids),
                                    datetime.now().isoformat(),
                                    form.id
                                ))
                                
                                response = Response(
                                    form_id=form.id,
                                    person_id=person.id,
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
                                logger.info(f"✅ Réponse créée pour {person.name}")
                            else:
                                sync_stats["errors"] += 1
                                logger.error(f"❌ Échec création personne: {name}")
                                continue
                        
                        response_date = None
                        if response_data.get('timestamp'):
                            try:
                                response_date = datetime.fromisoformat(response_data['timestamp'].replace('Z', '+00:00'))
                            except:
                                response_date = datetime.now()
                                logger.warning(f"⚠️ Timestamp invalide, utilisation de maintenant")
                        else:
                            response_date = datetime.now()
                        
                        success = self.mark_as_responded(form.id, person.id, response_date)
                        if success:
                            sync_stats["updated"] += 1
                            logger.info(f"✅ {person.name} marqué comme ayant répondu")
                        else:
                            sync_stats["errors"] += 1
                            logger.error(f"❌ Échec marquage réponse pour {person.name}")
                
                conn.execute("""
                    INSERT OR REPLACE INTO app_metadata (key, value, updated_at)
                    VALUES ('last_sync', ?, ?)
                """, (datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()
                
                logger.info(f"🎉 Synchronisation terminée: {sync_stats['updated']} mises à jour, "
                           f"{sync_stats['created']} créations, {sync_stats['errors']} erreurs")
        
        except Exception as e:
            logger.error(f"💥 Erreur critique synchronisation: {e}")
            sync_stats["errors"] += 1
        
        return sync_stats
    
    # ============ STATISTICS ============
    
    def get_statistics(self) -> ReminderStats:
        """Calcule les statistiques globales"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM people")
                total_people = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM responses")
                total_responses = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM responses WHERE has_responded = 0")
                pending_reminders = cursor.fetchone()[0]
                
                today = datetime.now().date().isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM responses 
                    WHERE DATE(last_reminder) = ?
                """, (today,))
                sent_today = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM responses WHERE has_responded = 1")
                responded = cursor.fetchone()[0]
                success_rate = (responded / total_responses * 100) if total_responses > 0 else 0
                
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
                people_count = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
                poles_count = conn.execute("SELECT COUNT(*) FROM poles").fetchone()[0]
                forms_count = conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
                responses_count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
                
                orphaned = conn.execute("""
                    SELECT COUNT(*) FROM responses r
                    WHERE NOT EXISTS (SELECT 1 FROM people p WHERE p.id = r.person_id)
                    OR NOT EXISTS (SELECT 1 FROM forms f WHERE f.id = r.form_id)
                """).fetchone()[0]
                
                forms_without_pole = conn.execute("""
                    SELECT COUNT(*) FROM forms WHERE pole_id IS NULL OR pole_id = ''
                """).fetchone()[0]
                
                return {
                    "status": "healthy" if orphaned == 0 and forms_without_pole == 0 else "warning",
                    "people_count": people_count,
                    "poles_count": poles_count,
                    "forms_count": forms_count,
                    "responses_count": responses_count,
                    "orphaned_responses": orphaned,
                    "forms_without_pole": forms_without_pole,
                    "database_version": "2.0-sqlite-poles"
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
                conn.execute("DELETE FROM poles")
                conn.execute("DELETE FROM app_metadata")
                conn.commit()
                logger.warning("Toutes les données supprimées")
                return True
        except Exception as e:
            logger.error(f"Erreur suppression données: {e}")
            return False


# Singleton
_db_instance = None

def get_database_manager() -> SQLiteDatabase:
    """Récupère l'instance singleton de la base SQLite avec gestion d'erreur"""
    global _db_instance
    if _db_instance is None:
        try:
            _db_instance = SQLiteDatabase()
            logger.info("✅ Instance SQLite avec pôles créée avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur création instance SQLite: {e}")
            raise
    return _db_instance