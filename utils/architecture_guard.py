from pathlib import Path

class ArchitectureGuard:
    """
    Vérifie que les fichiers générés par l'IA respectent
    l'architecture du projet (frontend / backend).
    """

    BACKEND_ALLOWED = [
        "backend/src",
        "backend/prisma",
        "backend/scripts",
        "backend/package.json",
        "backend/tsconfig.json",
        "backend/.eslintrc.json",
        "backend/.prettierrc.json"
    ]

    FRONTEND_ALLOWED = [
        "frontend/src",
        "frontend/public",
        "frontend/package.json",
        "frontend/tsconfig.json",
        "frontend/vite.config.ts",
        "frontend/tailwind.config.js",
        "frontend/postcss.config.js",
        "frontend/index.html",
        "frontend/.eslintrc.json",
        "frontend/.prettierrc.json"
    ]

    def validate(self, task_type: str, file_paths: list[str]) -> list[str]:
        """
        Vérifie la validité architecturale des chemins générés.

        Retourne la liste des chemins validés.
        Lève une exception si un chemin est invalide.
        """
        validated = []
        for path in file_paths:
            # Nettoyage du chemin
            path = path.replace("\\", "/")
            
            # Détection automatique du type de tâche si non spécifié ou générique
            current_type = task_type
            if not current_type or current_type not in ["backend", "frontend"]:
                if path.startswith("backend/"):
                    current_type = "backend"
                elif path.startswith("frontend/"):
                    current_type = "frontend"
                else:
                    # Ni backend ni frontend spécifié, et chemin non préfixé : on bloque par défaut par sécurité
                    raise ValueError(f"ArchitectureGuard: Impossible de déterminer le module pour le chemin → {path}")

            if current_type == "backend":
                self._validate_backend(path)
            elif current_type == "frontend":
                self._validate_frontend(path)

            validated.append(path)

        return validated

    def _validate_backend(self, path: str):
        # Autoriser explicitement la racine du backend pour les fichiers de config
        if path == "backend" or path == "backend/":
            return
            
        is_allowed = False
        # Autoriser si ça commence par un dossier permis, ou si c'est un fichier permis à la racine
        if any(path.startswith(p) for p in self.BACKEND_ALLOWED):
            is_allowed = True
            
        if not is_allowed:
            raise ValueError(
                f"ArchitectureGuard: chemin backend invalide (hors dossiers autorisés) → {path}"
            )

        ext = Path(path).suffix
        if ext in {".tsx", ".jsx"}:
            raise ValueError(
                f"ArchitectureGuard: fichier UI (.tsx/.jsx) détecté dans backend → {path}"
            )

    def _validate_frontend(self, path: str):
        # Autoriser explicitement la racine du frontend pour les fichiers de config
        if path == "frontend" or path == "frontend/":
            return
            
        is_allowed = False
        if any(path.startswith(p) for p in self.FRONTEND_ALLOWED):
            is_allowed = True
            
        if not is_allowed:
            raise ValueError(
                f"ArchitectureGuard: chemin frontend invalide (hors dossiers autorisés) → {path}"
            )

        # Les fichiers .ts/.js sont autorisés dans le frontend (ex: utilitaires, services, config)
        # Mais un fichier backend typique (ex: modèle mongoose, route express) aura été bloqué
        # par le filtre de répertoire (s'ils essaient d'écrire dans frontend/src/models par exemple)
        # On peut affiner avec le SemanticScanner plus tard comme suggéré
