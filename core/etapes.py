# Ce module est le chef d'orchestre de votre workflow :
# il prend la Constitution validée et la transforme en une liste de tâches actionnables,
# tout en assurant le suivi de progression (Réalisé vs Non réalisé).

# Ce script utilise LangChain pour analyser la Constitution et
# générer le fichier etapes.md qui servira de feuille de route à tous les agents

import re
import logging
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class EtapeManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
        self.constitution_path = self.root / "Constitution" / "CONSTITUTION.md"
        self.etapes_path = self.root / "Constitution" / "etapes.md"
        self.history_path = self.root / "Constitution" / "EtapesAdd.md"

    def generate_steps_from_constitution(self, semantic_map: str = "") -> str:
        """Analyse la Constitution pour définir les étapes du projet avec des sous-tâches détaillées."""
        if not self.constitution_path.exists():
            raise FileNotFoundError(
                f"CONSTITUTION.md introuvable : {self.constitution_path}"
            )

        constitution_content = self.constitution_path.read_text(encoding="utf-8")
        existing_plan = ""
        if self.etapes_path.exists():
            existing_plan = self.etapes_path.read_text(encoding="utf-8")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es un chef de projet DevOps expert. Basé sur la CONSTITUTION fournie, l'état actuel du code (SEMANTIC MAP) et le PLAN EXISTANT,
            découpe le projet en étapes techniques majeures (ex: 01, 02, 03).
            
            Tu DOIS :
            1. Comparer la Constitution avec la SEMANTIC MAP et le PLAN EXISTANT.
            2. Générer la liste COMPLÈTE des étapes nécessaires pour tout le projet (historique inclus).
            3. PRÉSERVER le statut [x] pour toutes les étapes et sous-tâches déjà marquées comme terminées dans le PLAN EXISTANT.
            4. **RÈGLE RÉALITÉ & GOLDEN FILES** : Ne crée JAMAIS de tâche pour configurer un fichier déjà présent dans la SEMANTIC MAP s'il s'agit d'un fichier de structure géré par le framework (`tsconfig.json`, `.spec-lock.json`, `CONSTITUTION.md`). Ils sont marqués [x] dans l'Etape 01 et ne doivent plus apparaître dans les étapes suivantes.
            5. **INTERDICTION D'HALLUCINATION** : Si un fichier (ex: `package.json`, `.eslintrc.js`, `app.ts`) n'est PAS listé dans la SEMANTIC MAP, la tâche qui le concerne DOIT rester en [ ]. Ne suppose jamais qu'un standard est présent.
            6. Marquer [x] une sous-tâche UNIQUEMENT si tu vois la preuve directe de son accomplissement dans la SEMANTIC MAP (ex: le fichier mentionné est présent). 
            7. Découper le reste en étapes atomiques avec des sous-tâches actionnables (src/, routes/, models/).
            
            Format de sortie STRICT :
            ## [x] 01_nom_etape : Titre (Préservé car déjà fait)
            - [x] Sous-tâche déjà faite
            
            ## [ ] 02_nom_etape : Titre (Nouvelle étape à faire)
            - [ ] Sous-tâche à réaliser
            
            IMPORTANT : Les IDs d'étape (01_nom_etape) doivent être courts, sans espaces, et utiliser des underscores."""),
            ("user", "CONSTITUTION :\n{content}\n\nSEMANTIC MAP (État du code actuel) :\n{semantic_map}\n\nPLAN EXISTANT (etapes.md actuel) :\n{existing_plan}")
        ])

        chain = prompt | self.model | StrOutputParser()
        steps = chain.invoke({
            "content": constitution_content, 
            "semantic_map": semantic_map,
            "existing_plan": existing_plan
        })

        self.etapes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.etapes_path, "w", encoding="utf-8") as f:
            f.write("# ÉTAPES DU PROJET (etapes.md)\n\n")
            f.write("Ce fichier documente la progression détaillée du projet.\n\n")
            f.write(steps)

        logger.info("Fichier etapes.md généré avec succès avec un format granulaire.")
        return steps

    def append_steps_from_constitution(self, semantic_map: str = "") -> str:
        """Analyse la Constitution pour ajouter uniquement les nouvelles étapes (Composantes) à la feuille de route."""
        if not self.constitution_path.exists():
            raise FileNotFoundError(f"CONSTITUTION.md introuvable.")

        constitution_content = self.constitution_path.read_text(encoding="utf-8")
        existing_etapes = ""
        if self.etapes_path.exists():
            existing_etapes = self.etapes_path.read_text(encoding="utf-8")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es un chef de projet DevOps. Ta mission est d'extraire la NOUVELLE fonctionnalité
            ajoutée à la Constitution et de la transformer en une ou plusieurs ÉTAPES TECHNIQUES à la suite du plan existant.
            
            Tu reçois :
            1. La CONSTITUTION amendée.
            2. Le plan d'étapes actuel (etapes.md).
            3. La SEMANTIC MAP (état actuel des fichiers).
            
            Tu DOIS :
            - Identifier ce qui est nouveau dans la Constitution par rapport au plan actuel et au code existant.
            - Créer une ou plusieurs étapes (ex: ## [ ] 04_nouveau_module) si la fonctionnalité est complexe.
            - Ne pas répéter les étapes déjà présentes dans le plan actuel.
            - **RÈGLE RÉALITÉ** : Marquer [x] UNIQUEMENT si le fichier est dans la Semantic Map.
            - Si un fichier n'est pas vu sur le disque, laisse la tâche en [ ].
            - RÉPONDRE UNIQUEMENT AVEC LE BLOC DES NOUVELLES ÉTAPES (format Markdown ## [ ] id : titre)."""),
            ("user", "CONSTITUTION :\n{const}\n\nPLAN ACTUEL :\n{etapes}\n\nSEMANTIC MAP :\n{semantic_map}")
        ])

        chain = prompt | self.model | StrOutputParser()
        new_steps = chain.invoke({
            "const": constitution_content, 
            "etapes": existing_etapes,
            "semantic_map": semantic_map
        })

        # Append to etapes.md
        with open(self.etapes_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + new_steps)

        logger.info("Nouvelles étapes ajoutées à etapes.md")
        return new_steps

    def get_next_pending_step(self) -> str | None:
        """Récupère la première étape non cochée [ ] dans etapes.md."""
        if not self.etapes_path.exists():
            return None

        with open(self.etapes_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("## [ ]"):
                    match = re.search(r"## \[ \] (\w+)", line)
                    if match:
                        return match.group(1)
        return None

    def get_all_steps(self) -> list[dict]:
        """Retourne toutes les étapes avec leur statut (done/pending)."""
        if not self.etapes_path.exists():
            return []

        steps = []
        content = self.etapes_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            # Étape majeure : ## [x] 01_setup : Description
            match_done = re.search(r"## \[x\] (\w+)\s*:\s*(.*)", line)
            if match_done:
                steps.append({
                    "id": match_done.group(1),
                    "description": match_done.group(2).strip(),
                    "status": "done",
                })
                continue

            # Étape majeure : ## [ ] 02_api : Description
            match_pending = re.search(r"## \[ \] (\w+)\s*:\s*(.*)", line)
            if match_pending:
                steps.append({
                    "id": match_pending.group(1),
                    "description": match_pending.group(2).strip(),
                    "status": "pending",
                })
        return steps

    def get_progress(self) -> dict:
        """Retourne un résumé de la progression : total, done, pending, pourcentage."""
        steps = self.get_all_steps()
        total = len(steps)
        done = sum(1 for s in steps if s["status"] == "done")
        pending = total - done
        pct = round((done / total) * 100, 1) if total > 0 else 0.0

        return {
            "total": total,
            "done": done,
            "pending": pending,
            "progress_pct": pct,
        }

    def get_subtasks_for_step(self, step_id: str) -> list[str]:
        """Retourne la liste des sous-tâches (texte brut) pour une étape donnée."""
        if not self.etapes_path.exists():
            return []
        
        lines = self.etapes_path.read_text(encoding="utf-8").splitlines()
        subtasks = []
        inside_target = False
        
        # Regex plus stricte pour éviter les correspondances partielles
        step_header_pattern = rf"^## \[.\] {re.escape(step_id)}(?:\s*:|$)"
        
        for line in lines:
            if re.match(step_header_pattern, line):
                inside_target = True
                continue
            if line.startswith("## ") and inside_target:
                break
            if inside_target and line.strip().startswith("- ["):
                # Extraire le texte de la sous-tâche (sans le checkbox)
                text = re.sub(r'^-\s*\[.\]\s*', '', line.strip())
                if text and text not in subtasks: # Éviter les doublons de lecture
                    subtasks.append(text)
        
        return subtasks

    def _file_exists(self, check_root: Path, path_str: str) -> bool:
        """Vérifie l'existence d'un fichier ou d'un dossier sur le disque."""
        # 1. Chemin direct
        if (check_root / path_str).exists():
            return True
            
        # 2. Normalisation
        clean_path = path_str.lstrip('/').lstrip('\\').replace('\\', '/')
        
        # 3. Test des préfixes standards
        prefixes = ["backend", "backend/src", "frontend", "frontend/src"]
        for prefix in prefixes:
            if clean_path.startswith(prefix + "/"):
                if (check_root / clean_path).exists(): return True
            elif (check_root / prefix / clean_path).exists():
                return True
        
        # 4. Fuzzy match : normaliser le nom de fichier pour gérer les variantes
        #    healthcheck.controller.ts ↔ healthcheckController.ts ↔ health-check.controller.ts
        def normalize_name(name: str) -> str:
            """Normalise un nom de fichier en retirant dots/hyphens/underscores et en lowercase."""
            stem = name.rsplit('.', 1)[0] if '.' in name else name  # Retirer l'extension
            ext = name.rsplit('.', 1)[1] if '.' in name else ''
            normalized = stem.replace('.', '').replace('-', '').replace('_', '').lower()
            return f"{normalized}.{ext}" if ext else normalized
        
        # Trouver le dossier parent attendu et vérifier son contenu
        target = Path(clean_path)
        target_normalized = normalize_name(target.name)
        
        # Chercher dans les dossiers candidats
        candidate_dirs = [check_root / target.parent]
        for prefix in prefixes:
            candidate_dirs.append(check_root / prefix / target.parent)
        
        for candidate_dir in candidate_dirs:
            if candidate_dir.exists() and candidate_dir.is_dir():
                for existing_file in candidate_dir.iterdir():
                    if normalize_name(existing_file.name) == target_normalized:
                        return True
        
        return False

    def _dependency_installed(self, check_root: Path, dep_name: str) -> bool:
        """Vérifie si une dépendance NPM est installée (via package.json)."""
        import json
        pkg_paths = [
            check_root / "package.json",
            check_root / "backend" / "package.json",
            check_root / "frontend" / "package.json"
        ]
        
        for pkg_path in pkg_paths:
            if pkg_path.exists():
                try:
                    data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if dep_name in dependencies:
                        return True
                except Exception:
                    continue
        return False

    def _script_exists(self, check_root: Path, script_name: str) -> bool:
        """Vérifie si un script npm existe dans le package.json."""
        import json
        pkg_paths = [
            check_root / "package.json",
            check_root / "backend" / "package.json",
            check_root / "frontend" / "package.json"
        ]
        
        for pkg_path in pkg_paths:
            if pkg_path.exists():
                try:
                    data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    scripts = data.get("scripts", {})
                    if script_name in scripts:
                        return True
                except Exception:
                    continue
        return False

    def mark_step_as_completed(self, step_id: str, synthesis: str = None, project_root: str = None) -> bool:
        """Passe une étape majeure de [ ] à [x]. Les sous-tâches sont cochées intelligemment 
        en vérifiant l'existence des fichiers/dossiers mentionnés sur le disque."""
        if not self.etapes_path.exists():
            raise FileNotFoundError(f"etapes.md introuvable : {self.etapes_path}")

        # Déterminer la racine du projet pour la vérification des fichiers
        check_root = Path(project_root) if project_root else self.root

        lines = self.etapes_path.read_text(encoding="utf-8").splitlines()
        updated_lines = []
        inside_target_step = False
        found = False
        checked_count = 0
        total_subtasks = 0
        header_index = -1

        # Regex pour matcher l'étape cible
        step_pattern = rf"^## \[ \] {re.escape(step_id)}(?:\s*:|$)"

        for line in lines:
            # Si on trouve le header de l'étape cible
            if re.match(step_pattern, line):
                header_index = len(updated_lines)
                updated_lines.append(line)
                inside_target_step = True
                found = True
                continue
            
            # Si on rentre dans une AUTRE étape majeure, on arrête
            if line.startswith("## ") and inside_target_step:
                inside_target_step = False
            
            # Pour les sous-tâches : vérification intelligente sur DISQUE
            if inside_target_step and line.strip().startswith("- [ ]"):
                total_subtasks += 1
                subtask_text = line.strip()
                
                # Patterns : `backend/tsconfig.json` ou `express`
                items_to_check = re.findall(r'`([^`]+)`', subtask_text)
                
                if items_to_check:
                    all_ok = True
                    missing_items = []
                    
                    for item in items_to_check:
                        # Skip les glob patterns (src/**/* , *.ts, etc.)
                        if '*' in item:
                            continue
                        
                        # Skip les valeurs de config (CommonJS, ES2022, strict, etc.)
                        config_keywords = {'CommonJS', 'ES2022', 'ES2021', 'ES2020', 'ESNext', 
                                          'strict', 'true', 'false', 'node', 'commonjs',
                                          'dist', 'src', 'rootDir', 'outDir', 'target', 'module',
                                          'include', 'exclude', 'compilerOptions'}
                        if item in config_keywords:
                            continue
                        
                        # Skip les flags CLI (-y, --save, --dev, etc.)
                        if item.startswith('-'):
                            continue
                        
                        # Skip les commandes shell (contiennent des espaces ou commencent par npm/npx)
                        if ' ' in item or item.startswith(('npm ', 'npx ', 'node ', 'yarn ')):
                            # Mapping commande → artefact produit
                            if 'npm init' in item or 'yarn init' in item:
                                if self._file_exists(check_root, 'package.json') or self._file_exists(check_root, 'backend/package.json'):
                                    continue
                            continue
                        
                        # Skip les noms de scripts npm (dev, build, start, test)
                        if item in ('dev', 'build', 'start', 'test'):
                            # Vérifier dans les scripts du package.json
                            if self._script_exists(check_root, item):
                                continue
                            else:
                                all_ok = False
                                missing_items.append(item)
                                continue
                                
                        # Skip les extraits de code JS/TS fréquents (faux positifs pour des fichiers)
                        code_snippets = {
                            'express.json', 'express.urlencoded', 'cors()', 'helmet()', 'morgan()',
                            'NextFunction', 'Request', 'Response', 'app.use', 'connectDB()', 'errorHandler'
                        }
                        if item in code_snippets or item.endswith('()'):
                            continue
                        
                        # On vérifie si c'est un fichier OU une dépendance
                        exists_as_file = self._file_exists(check_root, item)
                        exists_as_dep = self._dependency_installed(check_root, item)
                        
                        if not (exists_as_file or exists_as_dep):
                            all_ok = False
                            missing_items.append(item)
                    
                    if all_ok:
                        updated_lines.append(line.replace("[ ]", "[x]"))
                        checked_count += 1
                        logger.info(f"  ✅ Sous-tâche validée (Disque/Deps) : {subtask_text[:60]}")
                    else:
                        updated_lines.append(line)
                        logger.warning(f"  ❌ Sous-tâche NON validée (Manquant: {missing_items}) : {subtask_text[:60]}")
                else:
                    # Pas d'item spécifique -> Auto-validation par propagation
                    updated_lines.append(line.replace("[ ]", "[x]"))
                    checked_count += 1
            else:
                updated_lines.append(line)

        if not found:
            # Vérifier si déjà complétée
            if f"## [x] {step_id}" in self.etapes_path.read_text(encoding="utf-8"):
                logger.info("Étape '%s' déjà marquée comme terminée.", step_id)
                if synthesis: self.add_step_to_history(step_id, synthesis)
                return True
            logger.warning("Étape '%s' non trouvée.", step_id)
            return False

        if header_index != -1 and checked_count == total_subtasks and total_subtasks > 0:
            updated_lines[header_index] = updated_lines[header_index].replace("[ ]", "[x]")
        elif header_index != -1 and total_subtasks == 0:
            updated_lines[header_index] = updated_lines[header_index].replace("[ ]", "[x]")

        self.etapes_path.write_text("\n".join(updated_lines), encoding="utf-8")
        logger.info(f"Étape '{step_id}' : {checked_count}/{total_subtasks} sous-tâches vérifiées et cochées.")

        if synthesis:
            self.add_step_to_history(step_id, synthesis)

        return True, checked_count, total_subtasks


    def add_step_to_history(self, step_id: str, synthesis: str):
        """Ajoute une étape réalisée avec sa synthèse dans EtapesAdd.md."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            
            header = ""
            if not self.history_path.exists():
                header = "# HISTORIQUE DES ÉTAPES RÉALISÉES (EtapesAdd.md)\n\n"
            
            with open(self.history_path, "a", encoding="utf-8") as f:
                if header:
                    f.write(header)
                f.write(f"### ✅ Étape : {step_id}\n")
                f.write(f"{synthesis}\n\n---\n\n")
            
            logger.info("Synthèse ajoutée à EtapesAdd.md pour l'étape %s.", step_id)
        except Exception as e:
            logger.error("Impossible d'écrire l'historique dans EtapesAdd.md : %s", e)