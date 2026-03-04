# Analyse des modifications de fichiers
# Ce module est fondamental pour le Constitutional DevOps : il permet de détecter précisément 
# ce qu'une IA a tenté de modifier.
# Il sert à l'agent VERIFY pour s'assurer que l'agent IMPL n'a pas touché à des lignes de code 
# sensibles ou n'a pas modifié des fichiers hors du périmètre de la tâche.

import difflib
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

class DiffChecker:
    """Analyse les différences entre les versions de fichiers pour valider l'intégrité."""

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()

    def _is_safe_path(self, target_path: Path) -> bool:
        """Vérifie que le chemin cible ne tente pas de sortir du répertoire de base (Directory Traversal)."""
        try:
            target_path.resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    def get_file_diff(self, relative_path: str, new_content: str) -> str:
        """Compare le contenu actuel d'un fichier avec une proposition de l'IA."""
        file_path = self.root / relative_path
        
        if not self._is_safe_path(file_path):
            logger.error(f"🛑 Tentative de Directory Traversal bloquée (get_diff) : {relative_path}")
            return f"ERREUR : Chemin d'accès interdit pour {relative_path}"

        if not file_path.exists():
            return f"--- Nouveau fichier : {relative_path} ---\n{new_content}"

        try:
            old_content = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            logger.error(f"❌ Erreur d'encodage (get_diff) : {relative_path} n'est pas de l'UTF-8.")
            return f"ERREUR : Encodage non supporté pour {relative_path}"

        new_content_list = new_content.splitlines()

        diff = difflib.unified_diff(
            old_content, 
            new_content_list, 
            fromfile=f"a/{relative_path}", 
            tofile=f"b/{relative_path}",
            lineterm=""
        )
        
        return "\n".join(list(diff))

    def analyze_impact(self, relative_path: str, new_content: str) -> Dict:
        """Analyse l'impact quantitatif des modifications."""
        file_path = self.root / relative_path
        
        if not self._is_safe_path(file_path):
            logger.error(f"🛑 Tentative de Directory Traversal bloquée (analyze_impact) : {relative_path}")
            return {"status": "error", "message": "Accès interdit"}

        if not file_path.exists():
            return {"status": "created", "added": len(new_content.splitlines()), "removed": 0}

        try:
            old_content = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return {"status": "error", "message": "Encodage non supporté (pas UTF-8)"}

        new_content_list = new_content.splitlines()

        added = 0
        removed = 0
        
        for line in difflib.ndiff(old_content, new_content_list):
            if line.startswith('+ '):
                added += 1
            elif line.startswith('- '):
                removed += 1

        return {
            "status": "modified",
            "added": added,
            "removed": removed,
            "total_lines_before": len(old_content),
            "total_lines_after": len(new_content_list)
        }

    def is_protected_area_touched(self, diff_text: str, protected_keywords: List[str]) -> bool:
        """Vérifie si des zones sensibles (ex: "Auth", "DB_URL", "ADMIN") ont été modifiées."""
        # Si le diff_text signale une erreur d'encodage ou de sécurité, on protège par défaut
        if diff_text.startswith("ERREUR"):
            return True
            
        for line in diff_text.splitlines():
            # Ne vérifier que les lignes créées (+) ou supprimées (-) (mais ignorer les en-têtes de diff +++ / ---)
            if (line.startswith('+') or line.startswith('-')) and not line.startswith('+++') and not line.startswith('---'):
                if any(kw.lower() in line.lower() for kw in protected_keywords):
                    logger.warning(f"🚨 Zone sensible modifiée détectée : le code touche un mot-clé protégé.")
                    return True
        return False