# Système de Hash et Context Lock pour la vérification des fichiers
# Ce script calcule l'empreinte numérique (hash) de vos fichiers critiques
# pour s'assurer qu'aucune modification non autorisée n'a eu lieu
# entre deux étapes.
# Il protège la Constitution mais aussi le coeur du moteur (Protocoles).

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict

import time

logger = logging.getLogger(__name__)

class SpecValidator:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.lock_file = self.root / ".spec-lock.json"
        self.constitution_path = self.root / "Constitution" / "CONSTITUTION.md"
        
        # Fichiers vitaux du framework qui ne doivent jamais être altérés en douce
        self.core_files = [
            self.root / "protocols" / "constitution_rules.md",
            self.root / "protocols" / "task_protocol.md",
            self.root / "protocols" / "verification_rules.md",
            self.root / "templates" / "activation.md"
        ]

    def calculate_hash(self, file_path: Path) -> str:
        """Calcule le SHA-256 d'un fichier pour vérifier son intégrité."""
        if not file_path.exists():
            return ""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Erreur lors du calcul du hash pour {file_path.name} : {e}")
            return ""

    def check_integrity(self) -> bool:
        """Vérifie si la Constitution et les protocoles correspondent aux hash verrouillés."""
        if not self.lock_file.exists():
            logger.warning("Fichier .spec-lock.json introuvable. Impossible de vérifier l'intégrité.")
            return False
            
        try:
            with open(self.lock_file, "r", encoding="utf-8") as f:
                lock_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.error("Le fichier .spec-lock.json est corrompu ou inaccessible.")
            return False
            
        # 0. Vérification des verrous de tâches (Concurrency protection)
        active_tasks = lock_data.get("active_tasks", {})
        # On nettoie les verrous expirés (ex: plus de 30 min)
        now = time.time()
        expired_tasks = [tid for tid, timestamp in active_tasks.items() if now - timestamp > 1800]
        if expired_tasks:
            for tid in expired_tasks:
                del active_tasks[tid]
            self._save_lock_data(lock_data)
            
        # 1. Vérification de la Constitution
        stored_const_hash = lock_data.get("constitution_hash", "")
        current_const_hash = self.calculate_hash(self.constitution_path)
        
        if stored_const_hash and current_const_hash != stored_const_hash:
            logger.error("🚨 VIOLATION : La Constitution a été modifiée sans validation (Hash différent) !")
            return False

        # 2. Vérification des Protocoles Core
        stored_core_hashes = lock_data.get("core_hashes", {})
        for core_file in self.core_files:
            if core_file.exists():
                current_hash = self.calculate_hash(core_file)
                # On utilise le chemin relatif avec des slash '/' comme clé universelle
                rel_key = core_file.relative_to(self.root).as_posix()
                stored_hash = stored_core_hashes.get(rel_key, "")
                
                if stored_hash and current_hash != stored_hash:
                    logger.error(f"🚨 VIOLATION SYSTEME : Le fichier critique '{rel_key}' a été altéré !")
                    return False
            
            
        return True

    def is_task_locked(self, task_id: str) -> bool:
        """Vérifie si une tâche est actuellement verrouillée par un autre processus."""
        if not self.lock_file.exists():
            return False
        try:
            with open(self.lock_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            active_tasks = data.get("active_tasks", {})
            if task_id in active_tasks:
                # Vérification de l'expiration (30 min)
                if time.time() - active_tasks[task_id] < 1800:
                    return True
            return False
        except Exception:
            return False

    def acquire_task_lock(self, task_id: str) -> bool:
        """Tente de verrouiller une tâche pour exécution."""
        if not self.lock_file.exists():
            self.lock_version() # Initialise si absent
            
        try:
            with open(self.lock_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            active_tasks = data.setdefault("active_tasks", {})
            
            if task_id in active_tasks:
                # Vérifier si expiré
                if time.time() - active_tasks[task_id] < 1800:
                    logger.warning(f"🔒 Tâche {task_id} déjà en cours d'exécution.")
                    return False
            
            active_tasks[task_id] = time.time()
            self._save_lock_data(data)
            logger.info(f"🔒 Tâche {task_id} verrouillée pour exécution.")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du verrouillage de la tâche : {e}")
            return False

    def release_task_lock(self, task_id: str):
        """Libère le verrou sur une tâche."""
        if not self.lock_file.exists():
            return
            
        try:
            with open(self.lock_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            active_tasks = data.get("active_tasks", {})
            if task_id in active_tasks:
                del active_tasks[task_id]
                self._save_lock_data(data)
                logger.info(f"🔓 Tâche {task_id} déverrouillée.")
        except Exception as e:
            logger.error(f"Erreur lors du déverrouillage de la tâche : {e}")

    def _save_lock_data(self, data: dict):
        """Sauvegarde atomique du fichier lock."""
        try:
            with open(self.lock_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Erreur de sauvegarde lock : {e}")

    def lock_version(self):
        """Met à jour les empreintes dans .spec-lock.json après une validation globale."""
        
        # Initialisation de la structure avec la nouvelle version
        data = {
            "version": "1.1",
            "constitution_hash": self.calculate_hash(self.constitution_path),
            "core_hashes": {},
            "completed_tasks": [],
            "completed_specs": [],
            "active_tasks": {}
        }
        
        # Sauvegarde des historiques existants si le fichier est déjà là
        if self.lock_file.exists():
            try:
                with open(self.lock_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    data["completed_tasks"] = old_data.get("completed_tasks", [])
                    data["completed_specs"] = old_data.get("completed_specs", [])
                    data["active_tasks"] = old_data.get("active_tasks", {})
            except json.JSONDecodeError:
                logger.warning("Le fichier .spec-lock.json existant est corrompu. Il sera écrasé.")

        # Calcul des empreintes pour les "Core files"
        for core_file in self.core_files:
            if core_file.exists():
                rel_key = core_file.relative_to(self.root).as_posix()
                data["core_hashes"][rel_key] = self.calculate_hash(core_file)
        
        # Écriture finale
        try:
            with open(self.lock_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info("🔒 Système verrouillé : Constitution et Protocoles enregistrés.")
        except Exception as e:
            logger.error(f"❌ Impossible de verrouiller .spec-lock.json : {e}")