# Ce module est la couche de sécurité qui sépare la logique métier du système de fichiers physique.
# Il garantit que l'IA ne peut pas écrire n'importe où et que chaque fichier respecte l'encodage utf-8
# pour éviter les corruptions de données, particulièrement sous Windows.

import shutil
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

class FileManager:
    """Gestionnaire de fichiers sécurisé pour Speckit.Factory"""

    def __init__(self, base_path: str = "."):
        # On sécurise toujours le chemin de base en chemin absolu strict
        self.base_path = Path(base_path).resolve()

    def _is_safe_path(self, target_path: Path) -> bool:
        """Vérifie que le chemin cible ne tente pas de sortir du répertoire de base (Directory Traversal)."""
        try:
            target_path.resolve().relative_to(self.base_path)
            return True
        except ValueError:
            return False

    def safe_read(self, relative_path: str) -> Optional[str]:
        """Lit un fichier de manière sécurisée en vérifiant son existence et l'encodage utf-8."""
        file_path = self.base_path / relative_path
        
        if not self._is_safe_path(file_path):
            logger.error(f"🛑 Tentative de Directory Traversal bloquée : {relative_path}")
            return None

        if not file_path.exists():
            logger.warning(f"⚠️ Fichier introuvable : {relative_path}")
            return None
        
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.error(f"❌ Erreur d'encodage : {relative_path} n'est pas un fichier UTF-8 valide.")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur inattendue lors de la lecture de {relative_path} : {e}")
            return None

    def safe_write(self, relative_path: str, content: str, overwrite: bool = True) -> bool:
        """Écrit du contenu dans un fichier, avec création automatique des dossiers parents."""
        file_path = self.base_path / relative_path
        
        if not self._is_safe_path(file_path):
            logger.error(f"🛑 Tentative de Directory Traversal bloquée : {relative_path}")
            return False

        if file_path.exists() and not overwrite:
            logger.info(f"🛑 Écriture annulée : {relative_path} existe déjà et overwrite=False.")
            return False

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.debug(f"✅ Fichier écrit avec succès : {relative_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'écriture de {relative_path} : {e}")
            return False

    def move_task_to_completed(self, task_filename: str, source_folder: str, target_folder: str) -> bool:
        """Déplace un fichier (généralement de Task_App1 vers Task_App2)."""
        source = self.base_path / source_folder / task_filename
        target = self.base_path / target_folder / task_filename

        if not self._is_safe_path(source) or not self._is_safe_path(target):
            logger.error(f"🛑 Tentative de Directory Traversal bloquée lors du déplacement : {task_filename}")
            return False

        if not source.exists():
            logger.warning(f"⚠️ Déplacement annulé, source introuvable : {source}")
            return False

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            logger.info(f"🚚 Fichier déplacé avec succès vers : {target}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors du déplacement de {task_filename} : {e}")
            return False

    def list_files_in_dir(self, directory: str, extension: str = ".md") -> List[str]:
        """Liste les fichiers d'un dossier avec une extension donnée (ex: tâches en attente)."""
        dir_path = self.base_path / directory
        
        if not self._is_safe_path(dir_path):
            logger.error(f"🛑 Tentative de Directory Traversal bloquée lors du scan : {directory}")
            return []

        if not dir_path.exists() or not dir_path.is_dir():
            return []
            
        return [f.name for f in dir_path.glob(f"*{extension}")]