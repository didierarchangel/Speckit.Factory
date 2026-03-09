import os
from pathlib import Path

class SemanticScanner:
    """Scanne la structure d'un projet pour fournir un contexte sémantique à l'IA."""
    
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
