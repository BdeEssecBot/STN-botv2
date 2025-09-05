import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from models import Person, Form, Response, Pole, Group

class Database:
    """Base de données SQLite avec pôles et groupes - VERSION CORRIGÉE"""
    
    def __init__(self, db_path: str = "data/stn_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_tables()
    
    def _init_tables(self):
        """Initialise les tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS poles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    color TEXT DEFAULT '#FF6B6B',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    member_ids TEXT,
                    color TEXT DEFAULT '#4CAF50',
                    icon TEXT DEFAULT '👥',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS people (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT,
                    psid TEXT,
                    created_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS forms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    google_id TEXT UNIQUE,
                    pole_id TEXT,
                    people_ids TEXT,
                    created_at TEXT,
                    FOREIGN KEY (pole_id) REFERENCES poles (id)
                );
                
                CREATE TABLE IF NOT EXISTS responses (
                    id TEXT PRIMARY KEY,
                    form_id TEXT,
                    person_id TEXT,
                    has_responded BOOLEAN DEFAULT 0,
                    last_reminder TEXT,
                    FOREIGN KEY (form_id) REFERENCES forms (id),
                    FOREIGN KEY (person_id) REFERENCES people (id)
                );
            """)
            
            # Créer un pôle par défaut si aucun existe
            cursor = conn.execute("SELECT COUNT(*) FROM poles")
            if cursor.fetchone()[0] == 0:
                default_pole = Pole(name="Général", description="Pôle par défaut")
                conn.execute(
                    "INSERT INTO poles VALUES (?, ?, ?, ?, ?, ?)",
                    (default_pole.id, default_pole.name, default_pole.description,
                     default_pole.color, default_pole.is_active, default_pole.created_at.isoformat())
                )
                print("✅ Pôle par défaut 'Général' créé")
    
    # === PEOPLE ===
    def add_person(self, person: Person) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO people VALUES (?, ?, ?, ?, ?)",
                    (person.id, person.name, person.email, person.psid, 
                     person.created_at.isoformat())
                )
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_people(self) -> List[Person]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM people ORDER BY name").fetchall()
            return [
                Person(
                    id=row[0], name=row[1], email=row[2], psid=row[3],
                    created_at=datetime.fromisoformat(row[4])
                )
                for row in rows
            ]
    
    def get_person(self, person_id: str) -> Optional[Person]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
            if row:
                return Person(
                    id=row[0], name=row[1], email=row[2], psid=row[3],
                    created_at=datetime.fromisoformat(row[4])
                )
        return None
    
    def delete_person(self, person_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
            return cursor.rowcount > 0
    
    # === POLES ===
    def add_pole(self, pole: Pole) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO poles VALUES (?, ?, ?, ?, ?, ?)",
                    (pole.id, pole.name, pole.description, pole.color,
                     pole.is_active, pole.created_at.isoformat())
                )
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_poles(self) -> List[Pole]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM poles WHERE is_active = 1 ORDER BY name").fetchall()
            return [
                Pole(
                    id=row[0], name=row[1], description=row[2], color=row[3],
                    is_active=bool(row[4]), created_at=datetime.fromisoformat(row[5])
                )
                for row in rows
            ]
    
    def get_pole(self, pole_id: str) -> Optional[Pole]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM poles WHERE id = ?", (pole_id,)).fetchone()
            if row:
                return Pole(
                    id=row[0], name=row[1], description=row[2], color=row[3],
                    is_active=bool(row[4]), created_at=datetime.fromisoformat(row[5])
                )
        return None
    
    # === GROUPS ===
    def add_group(self, group: Group) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO groups VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (group.id, group.name, group.description, json.dumps(group.member_ids),
                     group.color, group.icon, group.is_active, group.created_at.isoformat())
                )
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_groups(self) -> List[Group]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM groups WHERE is_active = 1 ORDER BY name").fetchall()
            return [
                Group(
                    id=row[0], name=row[1], description=row[2],
                    member_ids=json.loads(row[3]) if row[3] else [],
                    color=row[4], icon=row[5], is_active=bool(row[6]),
                    created_at=datetime.fromisoformat(row[7])
                )
                for row in rows
            ]
    
    # === FORMS - CORRIGÉ ===
    def add_form(self, form: Form) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Insérer le formulaire
                print(f"🔧 Ajout formulaire: {form.name} (ID: {form.id})")
                conn.execute(
                    "INSERT INTO forms VALUES (?, ?, ?, ?, ?, ?)",
                    (form.id, form.name, form.google_id, form.pole_id,
                     json.dumps(form.people_ids), form.created_at.isoformat())
                )
                
                # Créer les réponses pour chaque personne
                print(f"📝 Création de {len(form.people_ids)} réponses...")
                for person_id in form.people_ids:
                    response = Response(form_id=form.id, person_id=person_id)
                    conn.execute(
                        "INSERT INTO responses VALUES (?, ?, ?, ?, ?)",
                        (response.id, response.form_id, response.person_id,
                         response.has_responded, None)
                    )
                
                conn.commit()
                print(f"✅ Formulaire '{form.name}' ajouté avec succès")
                return True
                
        except sqlite3.IntegrityError as e:
            print(f"❌ Erreur IntegrityError: {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            return False
    
    def get_forms(self) -> List[Form]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM forms ORDER BY created_at DESC").fetchall()
            return [
                Form(
                    id=row[0], name=row[1], google_id=row[2], pole_id=row[3],
                    people_ids=json.loads(row[4]) if row[4] else [],
                    created_at=datetime.fromisoformat(row[5])
                )
                for row in rows
            ]
    
    def get_forms_by_pole(self, pole_id: str) -> List[Form]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM forms WHERE pole_id = ? ORDER BY created_at DESC", (pole_id,)).fetchall()
            return [
                Form(
                    id=row[0], name=row[1], google_id=row[2], pole_id=row[3],
                    people_ids=json.loads(row[4]) if row[4] else [],
                    created_at=datetime.fromisoformat(row[5])
                )
                for row in rows
            ]
    
    # === RESPONSES - CORRIGÉ ===
    def mark_responded(self, form_id: str, person_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE responses SET has_responded = 1 WHERE form_id = ? AND person_id = ?",
                (form_id, person_id)
            )
            return cursor.rowcount > 0
    
    def get_non_responders(self, form_id: str) -> List[tuple[Person, Response]]:
        """CORRIGÉ: Gestion des index de colonnes"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT 
                    p.id as person_id, p.name as person_name, p.email as person_email, 
                    p.psid as person_psid, p.created_at as person_created_at,
                    r.id as response_id, r.form_id, r.person_id as resp_person_id, 
                    r.has_responded, r.last_reminder
                FROM people p
                JOIN responses r ON p.id = r.person_id
                WHERE r.form_id = ? AND r.has_responded = 0
                ORDER BY p.name
            """, (form_id,)).fetchall()
            
            result = []
            for row in rows:
                person = Person(
                    id=row['person_id'], 
                    name=row['person_name'], 
                    email=row['person_email'], 
                    psid=row['person_psid'],
                    created_at=datetime.fromisoformat(row['person_created_at'])
                )
                response = Response(
                    id=row['response_id'], 
                    form_id=row['form_id'], 
                    person_id=row['resp_person_id'],
                    has_responded=bool(row['has_responded']),
                    last_reminder=datetime.fromisoformat(row['last_reminder']) if row['last_reminder'] else None
                )
                result.append((person, response))
            return result
    
    def record_reminder(self, form_id: str, person_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE responses SET last_reminder = ? WHERE form_id = ? AND person_id = ?",
                (datetime.now().isoformat(), form_id, person_id)
            )
            conn.commit()
    
    # === DEBUG/TEST ===
    def debug_forms(self):
        """Debug: affiche tous les formulaires"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM forms").fetchall()
            print(f"🔍 DEBUG: {len(rows)} formulaires en base:")
            for row in rows:
                print(f"  - {row[1]} (ID: {row[0][:8]}...)")
    
    def debug_responses(self, form_id: str):
        """Debug: affiche les réponses d'un formulaire"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM responses WHERE form_id = ?", (form_id,)).fetchall()
            print(f"🔍 DEBUG: {len(rows)} réponses pour formulaire {form_id[:8]}...")
            for row in rows:
                print(f"  - Person {row[2][:8]}...: responded={row[3]}")