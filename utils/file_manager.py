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
    
    # 🛡️ CHEMINS PROTÉGÉS - Ne jamais rediriger ou dupliquer
    PROTECTED_PATHS = frozenset([
        "Constitution/",
        "Speckit/",
        ".git/",
        ".github/",
        ".env",
        "LICENSE",
        "README",
        "package.json",
        "pyproject.toml"
    ])
    
    # Central Framework Mapping Table - Only 3 frameworks: React, Next.js, Vue
    # Organized with consistent directory naming and build configurations
    FRAMEWORK_MAP = {
        "react": {
            "name": "React + Vite",
            "module": "frontend",
            "src": "frontend/src",
            "pages_dir": "pages",
            "components_dir": "components",
            "structure": "frontend/src/{components,pages,services,hooks,utils}",
            "extensions": [".tsx", ".ts", ".jsx", ".js", ".css"],
            "config_files": ["vite.config.ts", "tsconfig.json"],
            "build_command": "npm run build",
            "validation_command": "npx tsc --noEmit",
            "features": ["components", "pages", "hooks", "services"]
        },
        "next": {
            "name": "Next.js",
            "module": "frontend",
            "src": "frontend",
            "pages_dir": "app",
            "components_dir": "components",
            "structure": "frontend/{app,components,lib,utils}",
            "extensions": [".tsx", ".ts", ".jsx", ".js", ".css"],
            "config_files": ["next.config.ts", "next.config.js", "tsconfig.json"],
            "build_command": "npm run build",
            "validation_command": "npx tsc --noEmit",
            "features": ["app-router", "api-routes", "server-components"]
        },
        "vue": {
            "name": "Vue + Vite",
            "module": "frontend",
            "src": "frontend/src",
            "pages_dir": "views",
            "components_dir": "components",
            "structure": "frontend/src/{components,views,services,composables,utils}",
            "extensions": [".vue", ".ts", ".js", ".css"],
            "config_files": ["vite.config.ts", "tsconfig.json"],
            "build_command": "npm run build",
            "validation_command": "npx vue-tsc --noEmit",
            "features": ["components", "views", "composables", "services"]
        }
    }

    def __init__(self, base_path: str = ".", template_path: str = "core/templates"):
        # On sécurise toujours le chemin de base en chemin absolu strict
        self.base_path = Path(base_path).resolve()
        # Chemin vers les templates de référence (Golden Templates) de la Factory
        self.template_path = Path(__file__).parent.parent / template_path
        # Snapshots pour diff tracking
        self._file_snapshots = {}  # {filepath: hash}
        self._files_before = None  # Snapshot avant persistence
        self._files_after = None   # Snapshot après persistence
        # Detected framework (initialized on first use)
        self._detected_framework = None
    
    def detect_framework(self) -> str:
        """Détecte automatiquement le framework du projet.
        
        Returns: "react", "next", or "vue"
        """
        if self._detected_framework:
            return self._detected_framework
        
        # Step 1: Check for Next.js
        if (self.base_path / "next.config.ts").exists() or (self.base_path / "next.config.js").exists():
            self._detected_framework = "next"
            logger.info("🔍 Framework detected: Next.js")
            return self._detected_framework
        
        # Step 2: Check for Vite (React or Vue)
        vite_config = (self.base_path / "vite.config.ts").exists() or (self.base_path / "frontend" / "vite.config.ts").exists()
        if vite_config:
            # Differentiate React vs Vue by checking package.json
            pkg_path = self.base_path / "package.json"
            if not pkg_path.exists():
                pkg_path = self.base_path / "frontend" / "package.json"
            
            if pkg_path.exists():
                try:
                    import json
                    data = json.loads(pkg_path.read_text())
                    
                    if "vue" in str(data):
                        self._detected_framework = "vue"
                        logger.info("🔍 Framework detected: Vue + Vite")
                        return self._detected_framework
                    
                    if "react" in str(data):
                        self._detected_framework = "react"
                        logger.info("🔍 Framework detected: React + Vite")
                        return self._detected_framework
                except Exception as e:
                    logger.debug(f"Could not parse package.json: {e}")
            
            # Fallback: check for Vue component file
            if (self.base_path / "frontend" / "src" / "App.vue").exists():
                self._detected_framework = "vue"
                logger.info("🔍 Framework detected: Vue + Vite (App.vue)")
                return self._detected_framework
        
        # Default: React + Vite
        self._detected_framework = "react"
        logger.debug("🔍 Framework not detected, defaulting to React + Vite")
        return self._detected_framework
    
    def get_framework_config(self, framework: str = None) -> dict:
        """Retourne la configuration du framework spécifié (detecté si non fourni)."""
        if not framework:
            framework = self.detect_framework()
        
        if framework in self.FRAMEWORK_MAP:
            return self.FRAMEWORK_MAP[framework]
        else:
            logger.warning(f"⚠️ Unknown framework: {framework}, returning React default")
            return self.FRAMEWORK_MAP["react"]
    
    def normalize_path_for_framework(self, file_path_str: str, framework: str = None) -> str:
        """Normalise le chemin en respectant les conventions du framework détecté."""
        framework = framework or self.detect_framework()
        return self.normalize_path(file_path_str, framework)

    def _compute_file_hash(self, file_path: Path) -> str:
        """Calcule le hash SHA256 d'un fichier pour le diff tracking."""
        import hashlib
        if not file_path.exists():
            return "FILE_NOT_EXISTS"
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:12]  # 12 chars pour lisibilité
        except Exception as e:
            logger.warning(f"⚠️ Cannot compute hash for {file_path}: {e}")
            return "ERROR"
    
    def snapshot_project_state(self, label: str = None) -> dict:
        """Crée un snapshot de l'état du projet (fichiers, tailles, hashes).
        
        Returns:
            dict: {"label": "...", "timestamp": "...", "files": {...}, "total_size": ...}
        """
        import time
        from datetime import datetime
        
        snapshot = {
            "label": label or f"snapshot_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "files": {},
            "total_size": 0,
            "file_count": 0
        }
        
        # Scanner récursif des fichiers du projet
        for root_dir in [self.base_path / "frontend", self.base_path / "backend"]:
            if not root_dir.exists():
                continue
            
            for file_path in root_dir.rglob("*"):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    try:
                        rel_path = str(file_path.relative_to(self.base_path)).replace("\\", "/")
                        file_size = file_path.stat().st_size
                        file_hash = self._compute_file_hash(file_path)
                        
                        snapshot["files"][rel_path] = {
                            "size": file_size,
                            "hash": file_hash
                        }
                        snapshot["total_size"] += file_size
                        snapshot["file_count"] += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Snapshot: Cannot access {file_path}: {e}")
        
        return snapshot
    
    def diff_snapshots(self, before_snapshot: dict, after_snapshot: dict) -> dict:
        """Compare deux snapshots et retourne les changements.
        
        Returns:
            dict: {
                "created": [...],
                "modified": [...],
                "deleted": [...],
                "size_delta": int,
                "summary": "..."
            }
        """
        before_files = before_snapshot.get("files", {})
        after_files = after_snapshot.get("files", {})
        
        created = []
        modified = []
        deleted = []
        
        # Fichiers créés ou modifiés
        for path, after_info in after_files.items():
            if path not in before_files:
                created.append(path)
                logger.info(f"  ✅ CREATED: {path} ({after_info['size']} bytes)")
            elif before_files[path]["hash"] != after_info["hash"]:
                modified.append({
                    "path": path,
                    "before_size": before_files[path]["size"],
                    "after_size": after_info["size"],
                    "size_change": after_info["size"] - before_files[path]["size"]
                })
                logger.info(f"  📝 MODIFIED: {path} ({before_files[path]['size']} → {after_info['size']} bytes)")
        
        # Fichiers supprimés
        for path in before_files:
            if path not in after_files:
                deleted.append(path)
                logger.warning(f"  🗑️ DELETED: {path}")
        
        size_delta = after_snapshot.get("total_size", 0) - before_snapshot.get("total_size", 0)
        
        summary = f"Created: {len(created)}, Modified: {len(modified)}, Deleted: {len(deleted)}, Size: {size_delta:+d} bytes"
        
        return {
            "created": created,
            "modified": modified,
            "deleted": deleted,
            "size_delta": size_delta,
            "summary": summary
        }

    def _is_safe_path(self, target_path: Path) -> bool:
        """Vérifie que le chemin cible ne tente pas de sortir du répertoire de base (Directory Traversal)."""
        try:
            target_path.resolve().relative_to(self.base_path)
            return True
        except ValueError:
            return False

    def normalize_path(self, path: str, framework: str = None) -> str:
        """Normalise les chemins selon le framework (react, next, vue).
        
        🛡️ PROTECTIONS:
        1. Constitution/, Speckit/, .git/ → retourner tel quel (chemins obligatoires)
        2. Si déjà complet (frontend/..., backend/...) → retourner tel quel
        3. Detecter les chemins "loose" et les ajouter aux bons dossiers
        
        Stratégie:
        1. Si déjà complet (frontend/..., backend/...) → retourner tel quel
        2. Ajouter src/ si nécessaire (React, Vue)
        3. Utiliser pages/ pour React, views/ pour Vue, app/ pour Next
        4. Ajouter module prefix (frontend/)
        
        Args:
            path: Chemin du fichier (ex: "components/Button.tsx")
            framework: Framework cible. Si None, détecte automatiquement.
        
        Returns:
            Chemin normalisé (ex: "frontend/src/components/Button.tsx")
        """
        import re
        
        # Nettoyer le chemin
        path = path.strip().replace('\\', '/')
        
        # 🛡️ SÉCURITÉ : Rejeter les chemins non sûrs
        if ".." in path or path.startswith('/') or ':' in path:
            raise ValueError(f"🛑 UNSAFE PATH DETECTED: {path} (contains .. or absolute path)")
        
        # 🛡️ NIVEAU 0 : CHEMINS PROTÉGÉS - Retourner immédiatement sans modification
        for protected in self.PROTECTED_PATHS:
            if path.startswith(protected):
                logger.info(f"🛡️ Protected path passthrough (no redirection): {path}")
                return path

        # Normalisation stricte des fichiers rc sans extension (évite `.prettierrc` / `.eslintrc`)
        rc_aliases = {
            "frontend/.prettierrc": "frontend/.prettierrc.json",
            "backend/.prettierrc": "backend/.prettierrc.json",
            "frontend/.eslintrc": "frontend/.eslintrc.json",
            "backend/.eslintrc": "backend/.eslintrc.json",
        }
        if path in rc_aliases:
            normalized = rc_aliases[path]
            logger.info(f"🛡️ Normalized rc config path: {path} -> {normalized}")
            return normalized
        
        # Si déjà complet, retourner
        if path.startswith(('frontend/', 'backend/')):
            logger.debug(f"✅ Path already complete: {path}")
            return path
        
        # Détecter framework si nécessaire
        framework = framework or self.detect_framework()
        config = self.get_framework_config(framework)
        
        # Niveau 1: Commence par "src/" (React, Vue)
        if framework in ("react", "vue"):
            if path.startswith('src/'):
                result = f"frontend/{path}"
                logger.debug(f"📁 Matched src/: {path} → {result}")
                return result
        
        # Niveau 2: Commence par un répertoire standard
        # Pour React/Vue: components, services, hooks, utils (tous vont dans src/)
        # Pour Next: components, lib, utils (pas de src/)
        
        if framework in ("react", "vue"):
            src_base = "frontend/src"
            standard_dirs = ["components", "services", "hooks", "utils", "composables"]  # composables for Vue
        else:  # next
            src_base = "frontend"
            standard_dirs = ["components", "lib", "utils", "api", "app"]
        
        for dir_name in standard_dirs:
            if path.startswith(f"{dir_name}/"):
                result = f"{src_base}/{path}"
                logger.debug(f"📁 Matched {dir_name}/: {path} → {result}")
                return result
        
        # Niveau 3: Filename sans répertoire → classifier
        filename = path.split('/')[-1]
        has_path = '/' in path
        
        # Pour React et Vue: pages → pages ou views
        if "page" in filename.lower() or "view" in filename.lower():
            if framework == "vue":
                result = f"frontend/src/views/{path}"
            elif framework == "next":
                result = f"frontend/app/{path}"
            else:  # react
                result = f"frontend/src/pages/{path}"
            logger.debug(f"📝 Matched page/view: {path} → {result}")
            return result
        
        # Default pour React/Vue:  components
        if framework in ("react", "vue"):
            result = f"frontend/src/components/{path}"
        else:  # next
            result = f"frontend/components/{path}"
        
        logger.debug(f"📝 Default: {path} → {result}")
        return result

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
        """Écrit du contenu dans un fichier, avec création automatique des dossiers parents.
        
        Sécurité:
        - Rejette les chemins avec ".." (directory traversal)
        - Valide que tous les chemins restent sous base_path
        - Empêche les écritures sur des dossiers
        - Enregistre toutes les tentatives suspectes
        """
        import os
        
        file_path = self.base_path / relative_path
        
        # SÉCURITÉ #1 : Rejeter les ".." explicitement
        if ".." in relative_path:
            logger.error(f"🛑 SECURITY: Directory traversal attempt blocked: {relative_path} (contains ..)")
            return False
        
        # SÉCURITÉ #2 : Vérifier que le chemin normalisé reste sous base_path
        if not self._is_safe_path(file_path):
            logger.error(f"🛑 SECURITY: Path escape attempt blocked: {relative_path}")
            return False

        # SÉCURITÉ #3 : Gérer les dossiers (se termine par /)
        if relative_path.endswith('/') or relative_path.endswith('\\'):
            try:
                file_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"📁 Directory created: {relative_path}")
                return True
            except Exception as e:
                logger.error(f"❌ Error creating directory {relative_path}: {e}")
                return False
        
        # SÉCURITÉ #4 : Rejeter les chemins qui ne contiennent pas d'extension fileou chemin invalide
        if not '.' in relative_path.split('/')[-1]:  # Le dernier composant doit avoir une extension
            logger.warning(f"⚠️ File has no extension (suspicious): {relative_path}")
        
        # Vérifier si le fichier existe déjà
        if file_path.exists() and not overwrite:
            logger.info(f"🛑 Write skipped: {relative_path} already exists and overwrite=False")
            return False

        try:
            # SÉCURITÉ #5 : Si un dossier existe avec ce nom, rejeter
            if file_path.exists() and file_path.is_dir():
                logger.error(f"❌ COLLISION: {relative_path} is a directory, not a file")
                return False

            # Créer les dossiers parents
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Écrire le fichier
            file_path.write_text(content, encoding="utf-8")
            file_size = len(content.encode('utf-8'))
            logger.info(f"✅ File written: {relative_path} ({file_size} bytes)")
            return True
            
        except PermissionError as e:
            logger.error(f"❌ PERMISSION DENIED: Cannot write to {relative_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ ERROR writing {relative_path}: {type(e).__name__}: {e}")
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

    def _normalize_tsconfig_json(self, content: str, file_path: str = "") -> str:
        """Met à niveau les options TypeScript dépréciées dans tsconfig*.json."""
        import json
        try:
            data = json.loads(content)
            compiler_options = data.setdefault("compilerOptions", {})
            changed = False

            module_resolution = str(compiler_options.get("moduleResolution", "")).strip().lower()
            if module_resolution in {"node", "node10", "classic"}:
                compiler_options["moduleResolution"] = "NodeNext"
                # Avec NodeNext, TypeScript attend aussi module=NodeNext.
                compiler_options["module"] = "NodeNext"
                changed = True

            # Réduit le bruit TS6 si un ancien template passe encore.
            if "ignoreDeprecations" not in compiler_options:
                compiler_options["ignoreDeprecations"] = "6.0"
                changed = True

            if changed:
                logger.info(f"🧙‍♂️ tsconfig normalisé ({file_path or 'tsconfig'}): moduleResolution moderne + ignoreDeprecations.")
                return json.dumps(data, indent=2)
            return content
        except Exception as e:
            logger.warning(f"⚠️ Échec de la normalisation de tsconfig ({file_path or 'unknown'}): {e}")
            return content

    def extract_and_write(self, code: str) -> list:
        """Extrait les fichiers du code (format Spec-Kit) et les écrit sur le disque avec filtre Golden Template.
        
        Retourne:
            list: [{"path": "...", "content": "..."}] pour chaque fichier écrit
        """
        import re
        written_files = []
        failed_files = []
        
        if not code:
            logger.warning("⚠️ extract_and_write() called with empty code")
            return written_files

        logger.info("=" * 70)
        logger.info("📦 Starting file extraction and persistence...")
        logger.info("=" * 70)

        # Regex robuste pour détecter les en-têtes de fichiers (inclut maintenant les dossiers finissant par /)
        pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+(?:\.[a-zA-Z0-9]+|/))\]?.*$'
        file_blocks = re.split(pattern, code)
        
        total_files_detected = (len(file_blocks) - 1) // 2
        logger.info(f"🔍 Detected {total_files_detected} file blocks in code")
        
        if len(file_blocks) > 1:
            for idx, i in enumerate(range(1, len(file_blocks), 2), 1):
                file_path_str = file_blocks[i].strip()
                ai_content = file_blocks[i+1].strip()
                
                logger.info(f"\n[{idx}/{total_files_detected}] Processing: {file_path_str}")
                
                try:
                    # --- NORMALISATION DES CHEMINS (FIX MISSING MODULE PREFIX) ---
                    original_path = file_path_str
                    file_path_str = self.normalize_path(file_path_str)
                    
                    if file_path_str != original_path:
                        logger.info(f"  🔧 Path normalized: '{original_path}' → '{file_path_str}'")
                    else:
                        logger.debug(f"  ✓ Path already valid: {file_path_str}")
                    
                    # 🛡️ SECONDE COUCHE : BLOQUER LES CHEMINS PROTÉGÉS
                    for protected in self.PROTECTED_PATHS:
                        if file_path_str.startswith(protected) and file_path_str != original_path:
                            # Si le chemin a été redirigé vers un chemin protégé, rejeter
                            logger.error(f"  🛑 BLOCKED: Attempt to write to protected path '{file_path_str}' (originally: '{original_path}')")
                            logger.error(f"        Protected paths cannot be auto-redirected: {', '.join(self.PROTECTED_PATHS)}")
                            failed_files.append({"path": original_path, "error": f"Protected path: {protected}"})
                            continue
                        elif file_path_str.startswith(protected) and file_path_str == original_path:
                            # Si c'est intentionnel (même chemin en entrée), log mais accepter
                            logger.info(f"  ✅ Explicit protected path write allowed: {file_path_str}")
                    
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
                                logger.info(f"  🛡️ Applied Golden Template (source: {chosen_template.name})")
                            except Exception as e:
                                logger.error(f"  ❌ Error reading template {chosen_template}: {e}")
                                failed_files.append({"path": file_path_str, "error": f"Template read error: {e}"})
                                continue
                        else:
                            logger.debug(f"  ℹ️ No Golden Template found, using AI-generated content")

                    # --- NORMALISATION DES DÉPENDANCES ---
                    if not is_golden and "package.json" in file_path_str.lower():
                        final_content = self._normalize_package_json(final_content)

                    # --- NORMALISATION TSCONFIG (migration node/node10 -> NodeNext) ---
                    if file_path_str.lower().endswith(".json") and "tsconfig" in file_path_str.lower():
                        final_content = self._normalize_tsconfig_json(final_content, file_path_str)

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
                    
                    # --- ÉCRITURE DU FICHIER ---
                    if self.safe_write(file_path_str, final_content.strip()):
                        # On retourne le contenu FINAL (sanitisé/golden) pour synchronisation
                        written_files.append({"path": file_path_str, "content": final_content.strip()})
                        logger.info(f"  ✅ WRITTEN: {file_path_str} ({len(final_content)} bytes)")
                    else:
                        logger.error(f"  ❌ WRITE FAILED: {file_path_str}")
                        failed_files.append({"path": file_path_str, "error": "Write operation returned False"})
                        
                except ValueError as e:
                    logger.error(f"  🛑 SECURITY ERROR: {e}")
                    failed_files.append({"path": file_path_str, "error": f"Security validation: {e}"})
                    
                except Exception as e:
                    logger.error(f"  ❌ UNEXPECTED ERROR processing {file_path_str}: {type(e).__name__}: {e}")
                    failed_files.append({"path": file_path_str, "error": f"Processing error: {e}"})
        
        # --- SUMMARY REPORT ---
        logger.info("\n" + "=" * 70)
        logger.info(f"📊 FILE PERSISTENCE SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Successfully written: {len(written_files)}/{total_files_detected}")
        
        if written_files:
            for i, file_info in enumerate(written_files, 1):
                logger.info(f"   {i}. {file_info['path']}")
        
        if failed_files:
            logger.warning(f"❌ Failed to write: {len(failed_files)}/{total_files_detected}")
            for i, file_info in enumerate(failed_files, 1):
                logger.warning(f"   {i}. {file_info['path']} - {file_info['error']}")
        
        logger.info("=" * 70 + "\n")
        
        return written_files
