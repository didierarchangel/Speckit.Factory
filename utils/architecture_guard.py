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
        "backend/tsconfig.test.json",
        "backend/.eslintrc.json",
        "backend/.eslintrc.js",
        "backend/.prettierrc.json",
        "backend/.prettierrc.js",
        "backend/.env",
        "backend/.env.example",
        "backend/nodemon.json",
        "backend/jest.config.ts",
        "backend/jest.config.js",
        "backend/vitest.config.ts",
        "backend/vitest.config.js",
        "backend/jest.setup.ts",
        "backend/jest.setup.js"
    ]

    FRONTEND_ALLOWED = [
        "frontend/src",
        "frontend/public",
        "frontend/package.json",
        "frontend/tsconfig.json",
        "frontend/tsconfig.test.json",
        "frontend/vite.config.ts",
        "frontend/tailwind.config.js",
        "frontend/postcss.config.js",
        "frontend/index.html",
        "frontend/.eslintrc.json",
        "frontend/.eslintrc.js",
        "frontend/.prettierrc.json",
        "frontend/.prettierrc.js",
        "frontend/.env",
        "frontend/.env.example",
        "frontend/jest.config.ts",
        "frontend/jest.config.js",
        "frontend/vitest.config.ts",
        "frontend/vitest.config.js",
        "frontend/next.config.js",
        "frontend/next.config.ts",
        "frontend/jest.setup.ts",
        "frontend/jest.setup.js"
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
        # 🛡️ GLOBAL ALLOWLIST : Fichiers système autorisés partout (ex: GitHub Actions)
        if any(path.startswith(prefix) for prefix in [".github/", ".git/", ".vscode/"]):
            return
            
        # Autoriser explicitement la racine du backend pour les fichiers de config
        if path == "backend" or path == "backend/":
            return
            
        is_allowed = False
        # Autoriser si ça commence par un dossier permis, ou si c'est un fichier permis à la racine
        if any(path.startswith(p) for p in self.BACKEND_ALLOWED):
            is_allowed = True
            
        if not is_allowed:
            allowed_str = "\n".join([f"- {p}" for p in self.BACKEND_ALLOWED])
            raise ValueError(
                f"Architecture violation in 'backend' module.\n"
                f"Invalid path: {path}\n"
                f"Allowed paths:\n{allowed_str}\n"
                f"Suggested fix: If it's a source file, move it to backend/src/. If it's a config file, check if it's in the allowlist."
            )

        ext = Path(path).suffix
        if ext in {".tsx", ".jsx"}:
            raise ValueError(
                f"Architecture violation: UI file (.tsx/.jsx) detected in backend.\n"
                f"Invalid path: {path}\n"
                f"Reason: Frontend components are not allowed in the backend module."
            )

    def _validate_frontend(self, path: str):
        if any(path.startswith(prefix) for prefix in [".github/", ".git/", ".vscode/"]):
            return
            
        # Autoriser explicitement la racine du frontend pour les fichiers de config
        if path == "frontend" or path == "frontend/":
            return
            
        is_allowed = False
        if any(path.startswith(p) for p in self.FRONTEND_ALLOWED):
            is_allowed = True
            
        if not is_allowed:
            allowed_str = "\n".join([f"- {p}" for p in self.FRONTEND_ALLOWED])
            raise ValueError(
                f"Architecture violation in 'frontend' module.\n"
                f"Invalid path: {path}\n"
                f"Allowed paths:\n{allowed_str}\n"
                f"Suggested fix: Move the file to frontend/src/ or another allowed directory."
            )
