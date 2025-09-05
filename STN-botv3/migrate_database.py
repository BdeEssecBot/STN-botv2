#!/usr/bin/env python3
"""
Script de migration de base de données STN-bot v2 → v3
Usage: python migrate_database.py
"""

import sqlite3
import os
from pathlib import Path
import uuid
from datetime import datetime

def migrate_database():
    """Migre la base de données vers la v3"""
    
    db_path = Path("data/stn_bot.db")
    
    print("🔄 Migration de la base de données v2 → v3")
    print("=" * 50)
    
    if not db_path.exists():
        print("❌ Base de données non trouvée. Création d'une nouvelle base...")
        create_fresh_database(db_path)
        return
    
    # Créer une sauvegarde
    backup_path = db_path.with_suffix('.backup.db')
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"💾 Sauvegarde créée: {backup_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            print("🔍 Analyse de la structure actuelle...")
            
            # Vérifier les colonnes existantes
            cursor = conn.execute("PRAGMA table_info(forms)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            print(f"📋 Colonnes forms existantes: {existing_columns}")
            
            # === ÉTAPE 1: Créer les nouvelles tables ===
            print("\n📁 Création des nouvelles tables...")
            
            # Table poles
            conn.execute("""
                CREATE TABLE IF NOT EXISTS poles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    color TEXT DEFAULT '#FF6B6B',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT
                )
            """)
            print("✅ Table poles créée")
            
            # Table groups
            conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    member_ids TEXT,
                    color TEXT DEFAULT '#4CAF50',
                    icon TEXT DEFAULT '👥',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT
                )
            """)
            print("✅ Table groups créée")
            
            # === ÉTAPE 2: Ajouter pole_id à forms ===
            if 'pole_id' not in existing_columns:
                print("\n🔧 Ajout de la colonne pole_id à forms...")
                conn.execute("ALTER TABLE forms ADD COLUMN pole_id TEXT")
                print("✅ Colonne pole_id ajoutée")
            else:
                print("✅ Colonne pole_id déjà présente")
            
            # === ÉTAPE 3: Créer un pôle par défaut ===
            print("\n🏢 Gestion du pôle par défaut...")
            
            cursor = conn.execute("SELECT COUNT(*) FROM poles")
            pole_count = cursor.fetchone()[0]
            
            if pole_count == 0:
                # Créer le pôle par défaut
                default_pole_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO poles (id, name, description, color, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    default_pole_id, "Général", "Pôle par défaut créé lors de la migration",
                    "#2196F3", True, datetime.now().isoformat()
                ))
                print("✅ Pôle par défaut 'Général' créé")
                
                # Assigner tous les formulaires existants au pôle par défaut
                cursor = conn.execute("""
                    UPDATE forms SET pole_id = ? WHERE pole_id IS NULL OR pole_id = ''
                """)
                updated_forms = cursor.rowcount
                print(f"✅ {updated_forms} formulaires assignés au pôle par défaut")
            else:
                print("✅ Pôles déjà présents")
            
            # === ÉTAPE 4: Vérifications finales ===
            print("\n🔍 Vérifications finales...")
            
            # Compter les données
            people_count = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            forms_count = conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
            poles_count = conn.execute("SELECT COUNT(*) FROM poles").fetchone()[0]
            groups_count = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            responses_count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
            
            print(f"📊 Statistiques après migration:")
            print(f"   👥 Personnes: {people_count}")
            print(f"   🏢 Pôles: {poles_count}")
            print(f"   👥 Groupes: {groups_count}")
            print(f"   📋 Formulaires: {forms_count}")
            print(f"   📝 Réponses: {responses_count}")
            
            # Vérifier les formulaires sans pôle
            orphaned_forms = conn.execute("""
                SELECT COUNT(*) FROM forms WHERE pole_id IS NULL OR pole_id = ''
            """).fetchone()[0]
            
            if orphaned_forms > 0:
                print(f"⚠️  {orphaned_forms} formulaires sans pôle détectés")
                # Les assigner au pôle par défaut
                default_pole = conn.execute("SELECT id FROM poles LIMIT 1").fetchone()
                if default_pole:
                    conn.execute("""
                        UPDATE forms SET pole_id = ? WHERE pole_id IS NULL OR pole_id = ''
                    """, (default_pole[0],))
                    print(f"✅ Formulaires orphelins assignés au pôle par défaut")
            
            conn.commit()
            
            print("\n🎉 MIGRATION RÉUSSIE!")
            print("=" * 50)
            print("✅ Votre base de données est maintenant compatible v3")
            print("✅ Toutes vos données ont été préservées")
            print("✅ Un pôle par défaut a été créé")
            print(f"💾 Sauvegarde disponible: {backup_path}")
            
    except Exception as e:
        print(f"\n💥 ERREUR DURANTE LA MIGRATION: {e}")
        print(f"🔄 Restauration de la sauvegarde...")
        
        # Restaurer la sauvegarde
        shutil.copy2(backup_path, db_path)
        print("✅ Sauvegarde restaurée")
        raise

def create_fresh_database(db_path):
    """Crée une nouvelle base de données v3"""
    print("🆕 Création d'une nouvelle base de données v3...")
    
    db_path.parent.mkdir(exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE poles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT DEFAULT '#FF6B6B',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT
            );
            
            CREATE TABLE groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                member_ids TEXT,
                color TEXT DEFAULT '#4CAF50',
                icon TEXT DEFAULT '👥',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT
            );
            
            CREATE TABLE people (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                psid TEXT,
                created_at TEXT
            );
            
            CREATE TABLE forms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                google_id TEXT UNIQUE,
                pole_id TEXT,
                people_ids TEXT,
                created_at TEXT,
                FOREIGN KEY (pole_id) REFERENCES poles (id)
            );
            
            CREATE TABLE responses (
                id TEXT PRIMARY KEY,
                form_id TEXT,
                person_id TEXT,
                has_responded BOOLEAN DEFAULT 0,
                last_reminder TEXT,
                FOREIGN KEY (form_id) REFERENCES forms (id),
                FOREIGN KEY (person_id) REFERENCES people (id)
            );
        """)
        
        # Créer le pôle par défaut
        default_pole_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO poles (id, name, description, color, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            default_pole_id, "Général", "Pôle par défaut",
            "#2196F3", True, datetime.now().isoformat()
        ))
        
        conn.commit()
    
    print("✅ Nouvelle base de données v3 créée avec pôle par défaut")

def test_database():
    """Teste la base après migration"""
    print("\n🧪 Test de la base de données...")
    
    try:
        from database import Database
        db = Database()
        
        # Test basique
        poles = db.get_poles()
        people = db.get_people()
        forms = db.get_forms()
        
        print(f"✅ Test réussi: {len(poles)} pôles, {len(people)} personnes, {len(forms)} formulaires")
        
        return True
        
    except Exception as e:
        print(f"❌ Test échoué: {e}")
        return False

if __name__ == "__main__":
    try:
        migrate_database()
        
        if test_database():
            print("\n🚀 Vous pouvez maintenant lancer l'application:")
            print("   streamlit run app.py")
        else:
            print("\n⚠️  Des problèmes ont été détectés. Vérifiez les logs.")
            
    except Exception as e:
        print(f"\n💥 Migration échouée: {e}")
        print("🔄 Vérifiez que la base de données n'est pas utilisée par une autre application")
        