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

    def normalize_path(self, file_path_str: str, target_module: str = None) -> str:
        """Normalise les chemins de fichiers générés par l'IA pour garantir le préfixe du module.
        
        Stratégie de correction (en cascade):
        1. Si le chemin est déjà complet (ex: backend/src/..., frontend/src/...) → retourner tel quel
        2. Si le chemin commence par "src/" ou "components/" → ajouter le préfixe du module
        3. Si c'est un fichier seul sans répertoire → chercher dans les répertoires standards
        
        Args:
            file_path_str: Chemin du fichier (peut être relatif)
            target_module: Module cible ('backend' ou 'frontend') - détecté automatiquement sinon
            
        Returns:
            Chemin normalisé (ex: frontend/src/components/RegisterForm.tsx)
        """
        import re
        
        # Nettoyer le chemin
        path = file_path_str.strip().replace('\\', '/')
        
        # Niveau 1 : Déjà un chemin complet avec module ?
        if path.startswith('backend/') or path.startswith('frontend/') or path.startswith('mobile/'):
            return path
        
        # Déterminer le module cible si non fourni
        if not target_module:
            # Heuristique : Chercher des indices dans le nom de fichier
            if 'component' in path.lower() or 'page' in path.lower() or 'hook' in path.lower():
                target_module = 'frontend'
            elif 'middleware' in path.lower() or 'controller' in path.lower() or 'model' in path.lower() or 'route' in path.lower():
                target_module = 'backend'
            else:
                target_module = 'frontend'  # Défaut
        
        # Niveau 2 : Commence par "src/" ou un dossier standard ?
        if path.startswith('src/'):
            return f"{target_module}/{path}"
        
        # Niveau 3 : Commence par un dossier standard (components/, services/, etc.) ?
        standard_dirs = ['components', 'hooks', 'pages', 'services', 'routes', 'controllers', 'models', 'middlewares']
        for dir_name in standard_dirs:
            if path.startswith(f"{dir_name}/"):
                return f"{target_module}/src/{path}"
        
        # Niveau 4 : C'est juste un nom de fichier ?
        # Chercher le meilleur endroit pour le mettre
        filename = path.split('/')[-1]
        
        if 'component' in filename.lower():
            return f"{target_module}/src/components/{path}"
        elif 'page' in filename.lower():
            return f"{target_module}/src/pages/{path}"
        elif 'hook' in filename.lower():
            return f"{target_module}/src/hooks/{path}"
        elif 'service' in filename.lower() or 'api' in filename.lower():
            return f"{target_module}/src/services/{path}"
        elif 'controller' in filename.lower():
            return f"backend/src/controllers/{path}"
        elif 'model' in filename.lower():
            return f"backend/src/models/{path}"
        elif 'middleware' in filename.lower():
            return f"backend/src/middlewares/{path}"
        elif 'route' in filename.lower():
            return f"backend/src/routes/{path}"
        else:
            # Défaut : mettre dans src directement
            return f"{target_module}/src/{path}"

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

    def _normalize_package_json(self, content: str) -> str:
        """Déplace les dépendances de développement (types, outils) dans devDependencies."""
        import json
        try:
            pkg = json.loads(content)
            modified = False
            
            if "dependencies" not in pkg: pkg["dependencies"] = {}
            if "devDependencies" not in pkg: pkg["devDependencies"] = {}
            
            dev_patterns = ["eslint", "prettier", "typescript", "ts-node", "nodemon", "jest", "vitest", "supertest"]
            
            for dep in list(pkg["dependencies"].keys()):
                is_dev = dep.startswith("@types/") or any(p in dep for p in dev_patterns)
                
                if is_dev:
                    pkg["devDependencies"][dep] = pkg["dependencies"].pop(dep)
                    modified = True
            
            if modified:
                logger.info("🧙‍♂️ package.json normalisé : dépendances de dev déplacées vers devDependencies.")
                return json.dumps(pkg, indent=2)
            return content
        except Exception as e:
            logger.warning(f"⚠️ Échec de la normalisation de package.json : {e}")
            return content

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
                
                # --- NORMALISATION DES CHEMINS (FIX MISSING MODULE PREFIX) ---
                original_path = file_path_str
                file_path_str = self.normalize_path(file_path_str)
                if file_path_str != original_path:
                    logger.info(f"🔧 Chemin normalisé : '{original_path}' → '{file_path_str}'")
                
                # --- FILTRE PHYSIQUE : GOLDEN TEMPLATE OVERRIDE ---
                final_content = ai_content
                is_golden = False
                
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
                            is_golden = True
                            logger.info(f"🛡️ Golden Template appliqué pour : {file_path_str} (Source: {chosen_template.name})")
                        except Exception as e:
                            logger.error(f"❌ Erreur lecture template {chosen_template}: {e}")
                    else:
                        logger.warning(f"⚠️ Aucun Golden Template trouvé pour {file_path_str}, utilisation du contenu IA.")

                # --- NORMALISATION DES DÉPENDANCES ---
                if not is_golden and "package.json" in file_path_str.lower():
                    final_content = self._normalize_package_json(final_content)

                # Nettoyage profond (marqueurs FIN, backticks markdown)
                final_content = re.sub(r'(?m)^(?://|#)\s*\[FIN_FICHIER:.*?\].*$', '', final_content)
                final_content = re.sub(r'```(?:[a-zA-Z0-9]+)?\n?', '', final_content)
                final_content = final_content.replace('```', '')
                
                # Protection JSON spécifique (uniquement sur le code IA)
                if not is_golden and file_path_str.endswith('.json'):
                    def strip_comments(text):
                        result = []
                        i = 0
                        in_string = False
                        while i < len(text):
                            if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
                                in_string = not in_string
                                result.append(text[i])
                                i += 1
                            elif not in_string:
                                if text[i:i+2] == '//':
                                    # Skip until end of line
                                    i = text.find('\n', i)
                                    if i == -1: i = len(text)
                                elif text[i:i+2] == '/*':
                                    # Skip until end of comment block
                                    i = text.find('*/', i)
                                    if i == -1: i = len(text)
                                    else: i += 2
                                else:
                                    result.append(text[i])
                                    i += 1
                            else:
                                result.append(text[i])
                                i += 1
                        return "".join(result)
                    
                    final_content = strip_comments(final_content)
                
                if self.safe_write(file_path_str, final_content.strip()):
                    # On retourne le contenu FINAL (sanitisé/golden) pour synchronisation
                    written_files.append({"path": file_path_str, "content": final_content.strip()})
        
        return written_files
