import os
import re
import json
from pathlib import Path

class SemanticScanner:
    """Scanne la structure d'un projet pour fournir un contexte sémantique à l'IA."""
    
    # 🔴 Constantes pour détection des dépendances
    NODE_BUILTINS = {"fs", "path", "http", "https", "os", "sys", "util", "events", "stream"}
    IMPORT_RE = re.compile(
        r"(?:import\s+.+\s+from\s+['\"]([^'\"]+)['\"])|(?:require\(['\"]([^'\"]+)['\"]\))"
    )
    
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path)
        self.ignored_dirs = {
            "node_modules", ".git", "dist", "build", ".venv", 
            "__pycache__", ".next", "out", "target", "vendor"
        }
        self.important_extensions = {".ts", ".tsx", ".js", ".jsx", ".py", ".md", ".json", ".sql"}

    def generate_map(self) -> str:
        """Génère une représentation textuelle de l'arborescence et des fichiers clés."""
        lines = ["# SEMANTIC CODE MAP"]
        lines.append(f"Project Root: {self.root.absolute()}")
        lines.append("\n## Structure des fichiers :")
        
        structure = self._scan_dir(self.root)
        lines.append(structure)
        
        lines.append("\n## Points d'entrée et fichiers de configuration détectés :")
        config_files = self._detect_configs()
        for cfg in config_files:
            lines.append(f"- `{cfg}`")
            
        return "\n".join(lines)

    def get_file_tree(self) -> str:
        """Retourne la liste plate de tous les fichiers du projet (pour l'Auditeur)."""
        file_list = []
        for root, dirs, files in os.walk(str(self.root)):
            # Filtrage des dossiers ignorés
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), str(self.root)).replace('\\', '/')
                file_list.append(rel_path)
        return "\n".join(file_list)

    def _scan_dir(self, directory: Path, indent: str = "") -> str:
        """Récursivement scanne les dossiers en ignorant les dossiers bruyants."""
        output = []
        try:
            items = sorted(list(directory.iterdir()), key=lambda x: (not x.is_dir(), x.name))
            for item in items:
                if item.is_dir():
                    if item.name in self.ignored_dirs:
                        continue
                    output.append(f"{indent}📁 {item.name}/")
                    # On limite la profondeur pour ne pas saturer le contexte LLM ?
                    # Pour l'instant on scanne tout sauf ignored
                    res = self._scan_dir(item, indent + "  ")
                    if res: output.append(res)
                else:
                    if item.suffix in self.important_extensions:
                        output.append(f"{indent}📄 {item.name}")
        except Exception as e:
            output.append(f"{indent}⚠️ Erreur d'accès à {directory.name} : {e}")
            
        return "\n".join(output)

    def _detect_configs(self) -> list[str]:
        """Détecte les fichiers de configuration importants."""
        configs = []
        target_files = [
            "package.json", "tsconfig.json", "requirements.txt", 
            "pyproject.toml", "docker-compose.yml", ".env.example",
            "Constitution/CONSTITUTION.md"
        ]
        for f in target_files:
            if (self.root / f).exists():
                configs.append(f)
        return configs

    def _extract_imports(self, file_path: Path) -> set:
        """
        🔴 Extrait les imports d'un fichier TypeScript/JavaScript.
        
        Gère:
        - import X from 'module'
        - import { X } from 'module'
        - require('module')
        - Scoped packages (@namespace/package)
        - Ignore les imports locaux (./module, ../module)
        """
        imports = set()
        
        try:
            text = file_path.read_text(encoding="utf-8")
            
            for match in self.IMPORT_RE.findall(text):
                # match est un tuple: (import_match, require_match)
                # un seul sera non-vide
                module = match[0] or match[1]
                
                if not module:
                    continue
                
                # Ignorer les imports locaux (./module, ../module)
                if module.startswith("."):
                    continue
                
                # Extraire le package root (avant le premier /)
                # Pour @namespace/package, on garde les deux parties
                if module.startswith("@"):
                    parts = module.split("/")
                    if len(parts) >= 2:
                        pkg_name = f"{parts[0]}/{parts[1]}"
                    else:
                        pkg_name = parts[0]
                else:
                    pkg_name = module.split("/")[0]
                
                imports.add(pkg_name)
        
        except Exception as e:
            pass  # Silencieusement ignorer les erreurs de lecture
        
        return imports

    def detect_dependencies(self) -> set:
        """
        🔴 Analyse les imports du projet pour détecter les dépendances npm.
        
        Scope:
        - Scanne tous les fichiers .ts, .tsx, .js, .jsx
        - Ignore node_modules et autres dossiers bruyants
        - Retourne un set des modules utilisés
        
        Exemple:
        - Trouve: '@testing-library/react', 'react', 'express'
        - Retourne: {'react', '@testing-library/react', 'express'}
        """
        modules = set()
        
        for root, dirs, files in os.walk(str(self.root)):
            # Filtrer les répertoires ignorés
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            for file in files:
                path = Path(root) / file
                
                # Analyser SEULEMENT les fichiers TypeScript/JavaScript
                if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
                    continue
                
                # Extraire et fusionner les imports
                modules |= self._extract_imports(path)
        
        return modules

    def detect_missing_dependencies(self) -> list[str]:
        """
        🔴 Compare les imports utilisés avec package.json.
        
        Logique:
        1. Charge package.json (dependencies + devDependencies)
        2. Analyse les imports du projet
        3. Retourne les modules utilisés MAIS non déclarés
        
        Résultat:
        - Liste les dépendances manquantes
        - Ignore les modules intégrés Node.js (fs, path, http)
        - Ignore react, react-dom (souvent pré-installés)
        
        Return:
        - list[str]: dépendances vraiment manquantes
        """
        pkg_path = self.root / "package.json"
        
        if not pkg_path.exists():
            return []
        
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        
        # Fusion des dépendances déclarées
        declared = set(pkg.get("dependencies", {}))
        declared |= set(pkg.get("devDependencies", {}))
        
        # Détection des imports utilisés
        used = self.detect_dependencies()
        
        # Trouver ce qui manque (utilisé mais non déclaré)
        missing_declaration = [m for m in used if m not in declared]
        
        # Trouver ce qui est déclaré mais non installé physiquement
        missing_physical = []
        for pkg in declared:
            if pkg in self.NODE_BUILTINS:
                continue
            pkg_path = self.root / "node_modules" / pkg
            if not pkg_path.exists():
                missing_physical.append(pkg)
        
        return sorted(list(set(missing_declaration + missing_physical)))

