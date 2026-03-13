# ============================================================================
# ESM Import Resolver
# Patch automatique pour ajouter les extensions .js aux imports TypeScript
# ============================================================================
# Ce module résout les erreurs d'imports ESM dans les projets Node.js modernes
# En ajoutant automatiquement les extensions .js aux imports locaux TypeScript
# ============================================================================

import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class ESMImportResolver:
    """
    Resolver automatique pour les imports ESM TypeScript.
    
    Problème : En Node.js ESM (type=module), les imports TypeScript compilés en JS
    doivent inclure l'extension .js. Sans ça : "ERR_MODULE_NOT_FOUND"
    
    Solution : Scanner et corriger tous les imports locaux pour ajouter .js
    """
    
    # Regex pour détecter les imports relatifs (TypeScript)
    # Capture : import X from "./file" ou import X from "../services/user.service"
    IMPORT_REGEX = r'(?:from\s+["\']|import\s+.*\s+from\s+["\'])([.]{1,2}/[^"\']*)["\']'
    
    # Fichiers à ignorer (extensions)
    IGNORE_EXTENSIONS = {'.json', '.svg', '.png', '.jpg', '.gif', '.css', '.html'}
    
    # Extensions TypeScript (à ajouter lors de la correction)
    TS_EXTENSIONS = {'.ts', '.tsx'}
    JS_EXTENSIONS = {'.js', '.jsx'}
    
    def __init__(self, package_json_path: Path = None):
        """
        Initialise le resolver.
        
        Args:
            package_json_path: Chemin vers package.json pour vérifier type=module
        """
        self.package_json_path = package_json_path or Path("package.json")
        self.is_esm = self._check_esm_mode()
        logger.info(f"ESMImportResolver initialized - ESM Mode: {self.is_esm}")
    
    def _check_esm_mode(self) -> bool:
        """Vérifie si le projet est en mode ESM (type=module dans package.json)"""
        try:
            import json
            if self.package_json_path.exists():
                with open(self.package_json_path) as f:
                    data = json.load(f)
                    return data.get("type") == "module"
        except Exception as e:
            logger.warning(f"Could not check ESM mode: {e}")
        return False
    
    def resolve_file(self, file_path: Path) -> str:
        """
        Résout les imports ESM dans un fichier TypeScript.
        Retourne le contenu corrigé.
        
        Args:
            file_path: Chemin du fichier à traiter
            
        Returns:
            Contenu corrigé du fichier
        """
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return ""
        
        if not self._is_supported_file(file_path):
            return file_path.read_text()
        
        try:
            content = file_path.read_text(encoding='utf-8')
            fixed_content = self.resolve_content(content, file_path)
            return fixed_content
        except Exception as e:
            logger.error(f"Error resolving file {file_path}: {e}")
            return content
    
    def resolve_content(self, content: str, file_path: Path = None) -> str:
        """
        Résout les imports ESM dans un contenu TypeScript/JavaScript.
        
        Args:
            content: Contenu du fichier
            file_path: Path du fichier (optionnel, pour les logs)
            
        Returns:
            Contenu avec imports résolus
        """
        if not self.is_esm:
            return content
        
        def replace_import(match):
            import_path = match.group(1)
            
            # Exemple : "./file" → "./file.js"
            # Exemple : "../services/user.service" → "../services/user.service.js"
            
            # 1. Ignorer si déjà une extension
            if self._has_valid_extension(import_path):
                return match.group(0)
            
            # 2. Ignorer les imports externes (sans ./ ou ../)
            if not import_path.startswith('.'):
                return match.group(0)
            
            # 3. Ajouter .js
            fixed_path = import_path + ".js"
            
            # Reconstruire l'import
            original = match.group(0)
            fixed = original.replace(import_path, fixed_path)
            
            if file_path:
                logger.debug(f"[{file_path.name}] Fixed import: {import_path} → {fixed_path}")
            
            return fixed
        
        # Pattern pour matcher les imports TypeScript
        # Exemples :
        #   import x from "./file"
        #   import y from '../services/user.service'
        #   from "./components/Button"
        
        pattern = r'(?:from\s+|import\s+[^;]+\s+from\s+)(["\'])([.]{1,2}/[^"\']*)\1'
        fixed_content = re.sub(
            pattern,
            lambda m: m.group(0).replace(m.group(2), m.group(2) + ".js"),
            content
        )
        
        return fixed_content
    
    def _has_valid_extension(self, import_path: str) -> bool:
        """Vérifie si l'import a déjà une extension valide"""
        for ext in self.TS_EXTENSIONS | self.JS_EXTENSIONS | self.IGNORE_EXTENSIONS:
            if import_path.endswith(ext):
                return True
        return False
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """Vérifie si le fichier doit être traité"""
        suffix = file_path.suffix.lower()
        supported = {'.ts', '.tsx', '.js', '.jsx', '.mts', '.cts'}
        return suffix in supported
    
    def resolve_directory(self, dir_path: Path, recursive: bool = True) -> Dict[str, int]:
        """
        Résout les imports ESM dans tous les fichiers d'un répertoire.
        
        Args:
            dir_path: Répertoire à scanner
            recursive: Si True, scanne récursivement
            
        Returns:
            Dict avec stats {filepath: nombre_corrections}
        """
        stats = {}
        
        if not dir_path.exists() or not dir_path.is_dir():
            logger.error(f"Directory not found: {dir_path}")
            return stats
        
        pattern = "**/*.ts" if recursive else "*.ts"
        pattern_jsx = "**/*.tsx" if recursive else "*.tsx"
        
        files_to_process = list(dir_path.glob(pattern)) + list(dir_path.glob(pattern_jsx))
        files_to_process += list(dir_path.glob("**/*.js" if recursive else "*.js"))
        
        for file_path in files_to_process:
            try:
                original = file_path.read_text(encoding='utf-8')
                fixed = self.resolve_content(original, file_path)
                
                if original != fixed:
                    file_path.write_text(fixed, encoding='utf-8')
                    # Compter le nombre de replacements
                    num_fixes = len(re.findall(r'\.js["\']', fixed)) - len(re.findall(r'\.js["\']', original))
                    stats[str(file_path)] = num_fixes
                    logger.info(f"✓ Fixed {file_path.relative_to(dir_path)} ({num_fixes} imports)")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats[str(file_path)] = -1  # Erreur
        
        return stats
    
    def get_report(self, stats: Dict[str, int]) -> str:
        """Génère un rapport des corrections effectuées"""
        if not stats:
            return "ℹ️ No ESM import fixes needed."
        
        successful = {k: v for k, v in stats.items() if v > 0}
        errors = {k: v for k, v in stats.items() if v < 0}
        
        report = []
        report.append(f"📋 ESM Import Resolver Report")
        report.append(f"━" * 50)
        
        if successful:
            total_fixes = sum(successful.values())
            report.append(f"✅ Successfully fixed: {len(successful)} files")
            report.append(f"   Total import extensions added: {total_fixes}")
        
        if errors:
            report.append(f"❌ Errors in: {len(errors)} files")
        
        return "\n".join(report)


def apply_esm_import_resolver(project_root: Path = None, target_dirs: List[str] = None) -> Dict[str, int]:
    """
    Fonction utilitaire pour appliquer le resolver ESM sur un projet.
    
    Usage dans le pipeline :
    ```python
    from utils.esm_import_resolver import apply_esm_import_resolver
    stats = apply_esm_import_resolver(project_root=Path("."), target_dirs=["backend/src", "frontend/src"])
    ```
    
    Args:
        project_root: Racine du projet (default: cwd)
        target_dirs: Répertoires à scanner (default: ["backend/src", "frontend/src"])
        
    Returns:
        Dict avec stats globales
    """
    if project_root is None:
        project_root = Path(".")
    
    if target_dirs is None:
        target_dirs = ["backend/src", "frontend/src"]
    
    resolver = ESMImportResolver(project_root / "package.json")
    
    if not resolver.is_esm:
        logger.info("Project is not in ESM mode. Skipping import resolver.")
        return {}
    
    all_stats = {}
    
    for target_dir in target_dirs:
        dir_path = project_root / target_dir
        if dir_path.exists():
            logger.info(f"Scanning {target_dir}...")
            stats = resolver.resolve_directory(dir_path)
            all_stats.update(stats)
            logger.info(resolver.get_report(stats))
    
    return all_stats


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # Test local :
    # python -m utils.esm_import_resolver
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    stats = apply_esm_import_resolver(project_root)
