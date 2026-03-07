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

    def __init__(self, base_path: str = ".", template_path: str = "core/templates"):
        # On sécurise toujours le chemin de base en chemin absolu strict
        self.base_path = Path(base_path).resolve()
        # Chemin vers les templates de référence (Golden Templates) de la Factory
        self.template_path = Path(__file__).parent.parent / template_path

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

        if relative_path.endswith('/') or relative_path.endswith('\\'):
            logger.error(f"🛑 Tentative d'écriture sur un dossier comme si c'était un fichier : {relative_path}")
            return False


        try:
            # Sécurité supplémentaire : si un dossier existe avec ce nom de fichier, on bloque
            if file_path.exists() and file_path.is_dir():
                logger.error(f"❌ Collision détectée : {relative_path} est un dossier, pas un fichier.")
                return False

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.debug(f"✅ Fichier écrit avec succès : {relative_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'écriture de {relative_path} : {e}")
            return False

    def move_task_to_completed(self, task_filename: str, source_folder: str, target_folder: str) -> bool:
        """Déplace un fichier d'un dossier à un autre."""
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

    def extract_and_write(self, code: str) -> list:
        """Extrait les fichiers du code (format Spec-Kit) et les écrit sur le disque avec filtre Golden Template."""
        import re
        written_files = []
        if not code:
            return written_files

        # Regex robuste pour détecter les en-têtes de fichiers
        pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        file_blocks = re.split(pattern, code)
        
        if len(file_blocks) > 1:
            for i in range(1, len(file_blocks), 2):
                file_path_str = file_blocks[i].strip()
                ai_content = file_blocks[i+1].strip()
                
                # --- FILTRE PHYSIQUE : GOLDEN TEMPLATE OVERRIDE ---
                final_content = ai_content
                
                if "tsconfig.json" in file_path_str.lower():
                    is_backend = "backend" in file_path_str.lower()
                    template_key = "tsconfig.backend.json" if is_backend else "tsconfig.frontend.json"
                    
                    # 1. Priorité : Template local du projet (Stack-Specific)
                    project_template = self.base_path / ".speckit" / "templates" / template_key
                    # 2. Fallback : Template global de la Factory (Standard)
                    factory_template = self.template_path / template_key
                    # 3. Fallback Legacy
                    legacy_template = self.base_path / "tsconfig.json.example"

                    chosen_template = None
                    if project_template.exists(): chosen_template = project_template
                    elif factory_template.exists(): chosen_template = factory_template
                    elif legacy_template.exists(): chosen_template = legacy_template

                    if chosen_template:
                        try:
                            final_content = chosen_template.read_text(encoding="utf-8")
                            logger.info(f"🛡️ Golden Template appliqué pour : {file_path_str} (Source: {chosen_template.name})")
                        except Exception as e:
                            logger.error(f"❌ Erreur lecture template {chosen_template}: {e}")
                    else:
                        logger.warning(f"⚠️ Aucun Golden Template trouvé pour {file_path_str}, utilisation du contenu IA.")

                # Nettoyage profond (marqueurs FIN, backticks markdown)
                final_content = re.sub(r'(?m)^(?://|#)\s*\[FIN_FICHIER:.*?\].*$', '', final_content)
                final_content = re.sub(r'```(?:[a-zA-Z0-9]+)?\n?', '', final_content)
                final_content = final_content.replace('```', '')
                
                # Protection JSON spécifique
                if file_path_str.endswith('.json'):
                    final_content = re.sub(r'/\*\*[\s\S]*?\*/', '', final_content)
                    final_content = re.sub(r'/\*[\s\S]*?\*/', '', final_content)
                    final_content = re.sub(r'(?m)^\s*//.*$', '', final_content)
                
                if self.safe_write(file_path_str, final_content.strip()):
                    written_files.append(file_path_str)
        
        return written_files