# database/enhanced_sqlite_manager.py - VERSION CORRIGÉE
"""Extension du gestionnaire SQLite avec nouvelles fonctionnalités"""

import sqlite3
import json
import hashlib
import secrets
import uuid  # Import manquant
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

class EnhancedSQLiteDatabase:
    """Extension du gestionnaire SQLite avec nouvelles fonctionnalités"""
    
    def __init__(self, db_path: str = "data/stn_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._create_enhanced_tables()
        print(f"✅ Base SQLite étendue initialisée: {self.db_path}")
    
    def _create_enhanced_tables(self):
        """Crée les nouvelles tables pour les fonctionnalités avancées"""
        with sqlite3.connect(self.db_path) as conn:
            # Table users pour l'authentification
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    assigned_poles TEXT,  -- JSON array
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login TEXT
                )
            """)
            
            # Index unique pour username et email
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username 
                ON users(username)
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email 
                ON users(email)
            """)
            
            # Étendre la table people avec nouveaux champs
            self._migrate_people_table(conn)
            
            # Table message_history pour l'historique complet
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id TEXT PRIMARY KEY,
                    form_id TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    sent_by_user_id TEXT,
                    message_content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'sent',
                    facebook_message_id TEXT,
                    delivery_timestamp TEXT,
                    read_timestamp TEXT,
                    error_details TEXT,
                    response_time REAL,
                    reminder_number INTEGER DEFAULT 1,
                    template_used TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (form_id) REFERENCES forms (id) ON DELETE CASCADE,
                    FOREIGN KEY (person_id) REFERENCES people (id) ON DELETE CASCADE,
                    FOREIGN KEY (sent_by_user_id) REFERENCES users (id) ON DELETE SET NULL
                )
            """)
            
            # Index pour l'historique
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_history_form_id 
                ON message_history(form_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_history_person_id 
                ON message_history(person_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_history_created_at 
                ON message_history(created_at)
            """)
            
            # Table webhook_events pour les événements Facebook
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    sender_psid TEXT NOT NULL,
                    message_text TEXT,
                    sender_profile TEXT,  -- JSON
                    processed BOOLEAN DEFAULT 0,
                    person_created BOOLEAN DEFAULT 0,
                    created_person_id TEXT,
                    response_sent BOOLEAN DEFAULT 0,
                    error_details TEXT,
                    raw_webhook_data TEXT,  -- JSON
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (created_person_id) REFERENCES people (id) ON DELETE SET NULL
                )
            """)
            
            # Index pour les webhooks
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_events_psid 
                ON webhook_events(sender_psid)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_events_processed 
                ON webhook_events(processed)
            """)
            
            # Créer un utilisateur admin par défaut
            self._create_default_admin(conn)
            
            conn.commit()
            print("✅ Tables étendues créées/mises à jour")
    
    def _migrate_people_table(self, conn):
        """Migration de la table people avec nouveaux champs"""
        # Vérifier quelles colonnes existent déjà
        cursor = conn.execute("PRAGMA table_info(people)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # Ajouter les nouvelles colonnes si elles n'existent pas
        new_columns = [
            ("first_name", "TEXT DEFAULT ''"),
            ("last_name", "TEXT DEFAULT ''"),
            ("status", "TEXT DEFAULT 'active'"),
            ("facebook_profile", "TEXT"),  # JSON
            ("auto_captured", "BOOLEAN DEFAULT 0"),
            ("validation_notes", "TEXT DEFAULT ''"),
            ("validated_by", "TEXT"),
            ("validated_at", "TEXT")
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in existing_columns:
                conn.execute(f"ALTER TABLE people ADD COLUMN {column_name} {column_def}")
                print(f"✅ Colonne {column_name} ajoutée à people")
    
    def _create_default_admin(self, conn):
        """Crée un utilisateur admin par défaut"""
        # Vérifier s'il y a déjà des utilisateurs
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            # Créer admin par défaut
            admin_id = str(uuid.uuid4())
            default_password = "admin123"  # À changer !
            password_hash = self._hash_password(default_password)
            
            conn.execute("""
                INSERT INTO users (id, username, email, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                admin_id, "admin", "admin@stnbot.local", password_hash, "admin", 
                True, datetime.now().isoformat()
            ))
            
            print("🔑 Utilisateur admin créé - Identifiants: admin / admin123")
            print("⚠️  CHANGEZ LE MOT DE PASSE lors de la première connexion!")
    
    def _hash_password(self, password: str) -> str:
        """Hash sécurisé du mot de passe"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Vérifie un mot de passe"""
        try:
            salt, hash_hex = password_hash.split(':')
            password_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return secrets.compare_digest(password_check.hex(), hash_hex)
        except:
            return False
    
    # ============ GESTION DES UTILISATEURS ============
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authentifie un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM users 
                    WHERE username = ? AND is_active = 1
                """, (username,))
                
                user_row = cursor.fetchone()
                if not user_row:
                    return None
                
                if self._verify_password(password, user_row['password_hash']):
                    # Mettre à jour last_login
                    conn.execute("""
                        UPDATE users SET last_login = ? WHERE id = ?
                    """, (datetime.now().isoformat(), user_row['id']))
                    conn.commit()
                    
                    # Retourner les données utilisateur
                    assigned_poles = json.loads(user_row['assigned_poles']) if user_row['assigned_poles'] else []
                    
                    return {
                        "id": user_row['id'],
                        "username": user_row['username'],
                        "email": user_row['email'],
                        "role": user_row['role'],
                        "assigned_poles": assigned_poles,
                        "last_login": user_row['last_login']
                    }
                return None
        except Exception as e:
            print(f"❌ Erreur authentification: {e}")
            return None
    
    def create_user(self, username: str, email: str, password: str, role: str, assigned_poles: Optional[List[str]] = None) -> bool:
        """Crée un nouvel utilisateur - CORRIGÉ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                user_id = str(uuid.uuid4())
                password_hash = self._hash_password(password)
                assigned_poles = assigned_poles or []  # Utiliser liste vide si None
                
                conn.execute("""
                    INSERT INTO users (id, username, email, password_hash, role, assigned_poles, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, username, email, password_hash, role,
                    json.dumps(assigned_poles), datetime.now().isoformat()
                ))
                conn.commit()
                print(f"✅ Utilisateur '{username}' créé")
                return True
        except sqlite3.IntegrityError as e:
            print(f"❌ Utilisateur/email déjà existant: {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur création utilisateur: {e}")
            return False
    
    def get_user_accessible_poles(self, user_id: str) -> List[str]:
        """Récupère les pôles accessibles pour un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT role, assigned_poles FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return []
                
                # Admin peut tout voir
                if user['role'] == 'admin':
                    cursor = conn.execute("SELECT id FROM poles WHERE is_active = 1")
                    return [row[0] for row in cursor.fetchall()]
                
                # Autres utilisateurs selon leurs assignations
                return json.loads(user['assigned_poles']) if user['assigned_poles'] else []
        except Exception as e:
            print(f"❌ Erreur récupération pôles utilisateur: {e}")
            return []
    
    # ============ HISTORIQUE DES MESSAGES ============
    
    def add_message_to_history(self, form_id: str, person_id: str, sent_by_user_id: str,
                             message_content: str, status: str = "sent",
                             reminder_number: int = 1, template_used: Optional[str] = None) -> str:
        """Ajoute un message à l'historique - CORRIGÉ"""
        try:
            message_id = str(uuid.uuid4())
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO message_history 
                    (id, form_id, person_id, sent_by_user_id, message_content, status, 
                     reminder_number, template_used, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_id, form_id, person_id, sent_by_user_id, message_content,
                    status, reminder_number, template_used or '',  # Utiliser chaîne vide si None
                    datetime.now().isoformat()
                ))
                conn.commit()
            return message_id
        except Exception as e:
            print(f"❌ Erreur ajout historique message: {e}")
            return ""
    
    def get_form_message_history(self, form_id: str) -> List[Dict[str, Any]]:
        """Récupère l'historique des messages pour un formulaire"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT mh.*, p.name as person_name, p.email as person_email,
                           u.username as sent_by_username
                    FROM message_history mh
                    LEFT JOIN people p ON mh.person_id = p.id
                    LEFT JOIN users u ON mh.sent_by_user_id = u.id
                    WHERE mh.form_id = ?
                    ORDER BY mh.created_at DESC
                """, (form_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Erreur historique formulaire: {e}")
            return []
    
    def get_person_message_history(self, person_id: str) -> List[Dict[str, Any]]:
        """Récupère l'historique des messages pour une personne"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT mh.*, f.name as form_name,
                           u.username as sent_by_username
                    FROM message_history mh
                    LEFT JOIN forms f ON mh.form_id = f.id
                    LEFT JOIN users u ON mh.sent_by_user_id = u.id
                    WHERE mh.person_id = ?
                    ORDER BY mh.created_at DESC
                """, (person_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Erreur historique personne: {e}")
            return []
    
    def update_message_status(self, message_id: str, status: str, 
                            facebook_message_id: Optional[str] = None, error_details: Optional[str] = None) -> bool:
        """Met à jour le statut d'un message - CORRIGÉ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                update_fields = ["status = ?"]
                values = [status]
                
                if facebook_message_id:
                    update_fields.append("facebook_message_id = ?")
                    values.append(facebook_message_id)
                
                if error_details:
                    update_fields.append("error_details = ?")
                    values.append(error_details)
                
                if status == "delivered":
                    update_fields.append("delivery_timestamp = ?")
                    values.append(datetime.now().isoformat())
                
                values.append(message_id)
                
                conn.execute(f"""
                    UPDATE message_history 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, values)
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Erreur mise à jour statut message: {e}")
            return False
    
    # ============ WEBHOOK ET AUTO-CAPTURE ============
    
    def log_webhook_event(self, event_type: str, sender_psid: str, message_text: Optional[str] = None,
                         sender_profile: Optional[Dict[str, Any]] = None, raw_data: Optional[Dict[str, Any]] = None) -> str:
        """Enregistre un événement webhook - CORRIGÉ"""
        try:
            event_id = str(uuid.uuid4())
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO webhook_events 
                    (id, event_type, sender_psid, message_text, sender_profile, 
                     raw_webhook_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, event_type, sender_psid, message_text or '',  # Chaîne vide si None
                    json.dumps(sender_profile) if sender_profile else None,
                    json.dumps(raw_data) if raw_data else None,
                    datetime.now().isoformat()
                ))
                conn.commit()
            return event_id
        except Exception as e:
            print(f"❌ Erreur log webhook: {e}")
            return ""
    
    def get_person_by_psid(self, psid: str) -> Optional[Dict[str, Any]]:
        """Récupère une personne par PSID - MÉTHODE MANQUANTE"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM people WHERE psid = ?
                """, (psid,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'name': row['name'],
                        'email': row['email'],
                        'psid': row['psid'],
                        'status': row['status'] if 'status' in row.keys() else 'active',
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                return None
        except Exception as e:
            print(f"❌ Erreur récupération personne par PSID: {e}")
            return None
    
    def auto_create_person_from_webhook(self, sender_psid: str, sender_profile: Dict[str, Any],
                                      webhook_event_id: str) -> Optional[str]:
        """Crée automatiquement une personne depuis un webhook"""
        try:
            # Vérifier si la personne existe déjà
            existing_person = self.get_person_by_psid(sender_psid)
            if existing_person:
                return existing_person['id']  # Changé de .id à ['id']
            
            # Extraire les informations du profil
            first_name = sender_profile.get('first_name', '')
            last_name = sender_profile.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip() or f"Utilisateur {sender_psid[:8]}"
            
            # Créer la nouvelle personne
            person_id = str(uuid.uuid4())
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO people 
                    (id, name, first_name, last_name, psid, status, facebook_profile, 
                     auto_captured, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    person_id, full_name, first_name, last_name, sender_psid,
                    'pending_validation', json.dumps(sender_profile), True,
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                # Mettre à jour l'événement webhook
                conn.execute("""
                    UPDATE webhook_events 
                    SET person_created = 1, created_person_id = ?, processed = 1
                    WHERE id = ?
                """, (person_id, webhook_event_id))
                
                conn.commit()
            
            print(f"✅ Personne auto-créée: {full_name} (PSID: {sender_psid[:10]}...)")
            return person_id
            
        except Exception as e:
            print(f"❌ Erreur auto-création personne: {e}")
            return None
    
    def get_pending_validations(self) -> List[Dict[str, Any]]:
        """Récupère les personnes en attente de validation"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT p.*, we.message_text, we.created_at as first_contact_at
                    FROM people p
                    LEFT JOIN webhook_events we ON p.id = we.created_person_id
                    WHERE p.status = 'pending_validation'
                    ORDER BY p.created_at DESC
                """)
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Erreur récupération validations: {e}")
            return []
    
    def validate_person(self, person_id: str, validator_user_id: str, email: Optional[str] = None,
                       validation_notes: Optional[str] = None) -> bool:
        """Valide une personne en attente - CORRIGÉ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                update_fields = [
                    "status = 'active'",
                    "validated_by = ?",
                    "validated_at = ?",
                    "updated_at = ?"
                ]
                values = [validator_user_id, datetime.now().isoformat(), datetime.now().isoformat()]
                
                if email:
                    update_fields.append("email = ?")
                    values.append(email)
                
                if validation_notes:
                    update_fields.append("validation_notes = ?")
                    values.append(validation_notes)
                
                values.append(person_id)
                
                cursor = conn.execute(f"""
                    UPDATE people 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, values)
                
                success = cursor.rowcount > 0
                conn.commit()
                return success
        except Exception as e:
            print(f"❌ Erreur validation personne: {e}")
            return False