# services/google_forms_service.py
"""Service Google Forms optimisé pour STN-bot v2 - VERSION CORRIGÉE"""

import streamlit as st
import requests
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from config.settings import settings, AppConstants

logger = logging.getLogger(__name__)

class GoogleFormsService:
    """
    Service Google Forms utilisant App Script
    OPTIMISATION: Cache Streamlit natif + appels minimisés
    """
    
    def __init__(self):
        if settings is None:
            raise RuntimeError("Settings non initialisé - vérifiez votre configuration")
        
        self.app_script_url = settings.google_app_script_url
        logger.info("🔗 Service Google Forms initialisé avec App Script")
    
    @st.cache_data(ttl=AppConstants.CACHE_GOOGLE_FORMS, show_spinner=False)
    def get_form_responses(_self, form_id: str) -> List[Dict[str, Any]]:
        """
        Récupère les réponses d'un formulaire Google via App Script
        CACHE: 1 minute pour éviter les appels répétés
        
        Args:
            form_id: ID du formulaire Google
            
        Returns:
            Liste des réponses avec emails et noms
        """
        try:
            logger.info(f"📞 Appel App Script pour formulaire {form_id[:10]}...")
            
            # Appel à votre App Script existant
            url = f"{_self.app_script_url}?formId={form_id}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Vérifier les erreurs de l'App Script - CORRECTION ICI
            if 'error' in data:
                error_msg = data['error']
                # Si c'est juste "missing formId", c'est qu'on teste sans paramètre
                if 'missing formId' not in error_msg.lower():
                    logger.error(f"❌ Erreur App Script: {error_msg}")
                    return []
            
            # Extraire les réponses
            emails = data.get('emails', [])
            people = data.get('people', [])
            
            logger.info(f"📊 Récupéré {len(emails)} emails uniques, {len(people)} personnes détaillées")
            
            # Convertir au format unifié
            unified_responses = []
            
            # Priorité aux données détaillées des personnes
            for person in people:
                if person.get('email'):
                    unified_responses.append({
                        'email': person['email'].lower().strip(),
                        'firstName': person.get('firstName', '').strip(),
                        'lastName': person.get('lastName', '').strip(),
                        'fullName': f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
                        'timestamp': person.get('timestamp'),  # Inclure le timestamp si disponible
                        'source': 'detailed'
                    })
            
            # Ajouter les emails supplémentaires qui ne sont pas dans les personnes détaillées
            detailed_emails = {resp['email'] for resp in unified_responses}
            for email in emails:
                email_normalized = email.lower().strip()
                if email_normalized not in detailed_emails:
                    unified_responses.append({
                        'email': email_normalized,
                        'firstName': '',
                        'lastName': '',
                        'fullName': '',
                        'timestamp': None,
                        'source': 'email_only'
                    })
            
            logger.info(f"✅ {len(unified_responses)} réponses traitées pour {form_id[:10]}...")
            return unified_responses
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur réseau App Script pour {form_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erreur inattendue pour {form_id}: {e}")
            return []
    
    @st.cache_data(ttl=AppConstants.CACHE_GOOGLE_FORMS, show_spinner=False)
    def get_multiple_forms_responses(_self, form_configs: List[Dict[str, str]]) -> Dict[str, List[Dict]]:
        """
        Récupère les réponses de plusieurs formulaires
        OPTIMISATION: Cache global + traitement en lot
        
        Args:
            form_configs: Liste de {"form_id": "google_form_id", "name": "form_name"}
            
        Returns:
            Dict[google_form_id -> List[responses]]
        """
        all_responses = {}
        
        logger.info(f"🔄 Synchronisation de {len(form_configs)} formulaires via App Script")
        
        # Progress bar pour Streamlit
        progress_bar = None
        status_text = None
        
        if len(form_configs) > 1:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        for i, config in enumerate(form_configs):
            google_form_id = config["form_id"]
            form_name = config.get("name", f"Form {i+1}")
            
            if len(form_configs) > 1 and progress_bar is not None and status_text is not None:
                progress = (i + 1) / len(form_configs)
                progress_bar.progress(progress)
                status_text.text(f"Synchronisation: {form_name} ({i+1}/{len(form_configs)})")
            
            logger.info(f"📋 Traitement formulaire: {form_name}")
            responses = _self.get_form_responses(google_form_id)
            all_responses[google_form_id] = responses
        
        if len(form_configs) > 1 and progress_bar is not None and status_text is not None:
            progress_bar.empty()
            status_text.empty()
        
        total_responses = sum(len(responses) for responses in all_responses.values())
        logger.info(f"✅ Synchronisation terminée: {total_responses} réponses totales")
        
        return all_responses
    
    def test_connection(self, test_form_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Test la connexion App Script - VERSION CORRIGÉE
        
        Args:
            test_form_id: ID de formulaire pour test (optionnel)
            
        Returns:
            Résultat du test
        """
        try:
            if test_form_id:
                # Test avec un formulaire spécifique
                responses = self.get_form_responses(test_form_id)
                return {
                    "status": "success",
                    "message": f"Connexion réussie - {len(responses)} réponses trouvées",
                    "responses_count": len(responses),
                    "form_id": test_form_id
                }
            else:
                # Test basique de connexion (sans formId) - CORRECTION ICI
                response = requests.get(self.app_script_url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Vérifier si c'est la réponse attendue "missing formId"
                if 'error' in data and 'missing formId' in str(data['error']).lower():
                    return {
                        "status": "success",
                        "message": "App Script accessible et fonctionnel",
                        "app_script_url": self.app_script_url[:50] + "...",
                        "note": "Erreur 'missing formId' normale lors du test sans paramètre"
                    }
                elif 'emails' in data or 'people' in data:
                    return {
                        "status": "success",
                        "message": "App Script fonctionnel avec données",
                        "data_preview": f"Emails: {len(data.get('emails', []))}, Personnes: {len(data.get('people', []))}"
                    }
                else:
                    return {
                        "status": "warning",
                        "message": f"Réponse inattendue de l'App Script",
                        "data": data
                    }
                    
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Erreur de connexion App Script: {e}",
                "app_script_url": self.app_script_url[:50] + "..."
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Erreur inattendue: {e}"
            }
    
    def validate_form_id(self, google_form_id: str) -> bool:
        """
        Valide qu'un Google Form ID a le bon format
        
        Args:
            google_form_id: ID à valider
            
        Returns:
            True si l'ID semble valide
        """
        if not google_form_id or len(google_form_id) < 10:
            return False
        
        # Google Form IDs sont généralement alphanumériques avec des tirets/underscores
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
        return all(c in allowed_chars for c in google_form_id)
    
    def get_form_url(self, google_form_id: str) -> str:
        """
        Génère l'URL publique d'un formulaire Google
        
        Args:
            google_form_id: ID du formulaire
            
        Returns:
            URL complète du formulaire
        """
        if self.validate_form_id(google_form_id):
            return AppConstants.GOOGLE_FORM_URL_TEMPLATE.format(form_id=google_form_id)
        return ""
    
    def clear_cache(self):
        """Vide le cache des réponses Google Forms"""
        try:
            # Vider les caches spécifiques à cette classe
            self.get_form_responses.clear()
            self.get_multiple_forms_responses.clear()
            logger.info("🧹 Cache Google Forms vidé")
        except Exception as e:
            logger.error(f"❌ Erreur lors du vidage du cache: {e}")
    
    def get_sync_summary(self, responses_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Génère un résumé de synchronisation
        
        Args:
            responses_data: Données de réponses obtenues
            
        Returns:
            Résumé avec statistiques
        """
        total_forms = len(responses_data)
        total_responses = sum(len(responses) for responses in responses_data.values())
        total_emails = len(set(
            resp['email'] for responses in responses_data.values() 
            for resp in responses if resp.get('email')
        ))
        
        forms_with_responses = len([
            form_id for form_id, responses in responses_data.items() 
            if len(responses) > 0
        ])
        
        return {
            "total_forms": total_forms,
            "forms_with_responses": forms_with_responses,
            "total_responses": total_responses,
            "unique_emails": total_emails,
            "sync_timestamp": datetime.now().isoformat(),
            "success_rate": (forms_with_responses / total_forms * 100) if total_forms > 0 else 0
        }

# Factory function pour Streamlit
@st.cache_resource
def get_google_forms_service() -> GoogleFormsService:
    """Récupère l'instance singleton du service Google Forms"""
    return GoogleFormsService()