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

    def generate_steps_from_constitution(self) -> str:
        """Analyse la Constitution pour définir les étapes du projet avec des sous-tâches détaillées."""
        if not self.constitution_path.exists():
            raise FileNotFoundError(
                f"CONSTITUTION.md introuvable : {self.constitution_path}"
            )

        constitution_content = self.constitution_path.read_text(encoding="utf-8")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es un chef de projet DevOps expert. Basé sur la CONSTITUTION fournie,
            découpe le projet en étapes techniques majeures (ex: 01, 02, 03).
            Chaque étape doit contenir une liste de sous-tâches atomiques et actionnables.
            
            Format de sortie STRICT :
            ## [ ] 01_nom_etape : Titre de l'étape
            - [ ] Sous-tâche 1 (ex: Créer le dossier src)
            - [ ] Sous-tâche 2 (ex: Configurer tsconfig.json)
            
            ## [ ] 02_nom_etape : Titre de l'étape
            - [ ] Sous-tâche 1
            
            IMPORTANT : Les IDs d'étape (01_nom_etape) doivent être courts, sans espaces, et utiliser des underscores."""),
            ("user", "{content}")
        ])

        chain = prompt | self.model | StrOutputParser()
        steps = chain.invoke({"content": constitution_content})

        self.etapes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.etapes_path, "w", encoding="utf-8") as f:
            f.write("# ÉTAPES DU PROJET (etapes.md)\n\n")
            f.write("Ce fichier documente la progression détaillée du projet.\n\n")
            f.write(steps)

        logger.info("Fichier etapes.md généré avec succès avec un format granulaire.")
        return steps

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
        
        for line in lines:
            if f"## [ ] {step_id}" in line or f"## [x] {step_id}" in line:
                inside_target = True
                continue
            if line.startswith("## ") and inside_target:
                break
            if inside_target and line.strip().startswith("- ["):
                # Extraire le texte de la sous-tâche (sans le checkbox)
                text = re.sub(r'^-\s*\[.\]\s*', '', line.strip())
                subtasks.append(text)
        
        return subtasks

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

        for line in lines:
            # Si on trouve le header de l'étape cible
            if f"## [ ] {step_id}" in line:
                updated_lines.append(line.replace(f"## [ ] {step_id}", f"## [x] {step_id}"))
                inside_target_step = True
                found = True
                continue
            
            # Si on rentre dans une AUTRE étape majeure, on arrête
            if line.startswith("## ") and inside_target_step:
                inside_target_step = False
            
            # Pour les sous-tâches : vérification intelligente
            if inside_target_step and line.strip().startswith("- [ ]"):
                total_subtasks += 1
                subtask_text = line.strip()
                
                # Extraire les chemins de fichiers/dossiers mentionnés dans la sous-tâche
                # Patterns : `backend/tsconfig.json`, `backend/src`, `backend/.env`, etc.
                file_patterns = re.findall(r'`([a-zA-Z0-9._\-/\\]+(?:\.[a-zA-Z0-9]+)?)`', subtask_text)
                
                if file_patterns:
                    # Il y a des fichiers/dossiers mentionnés : vérifier leur existence
                    all_exist = all(
                        (check_root / fp).exists() for fp in file_patterns
                    )
                    if all_exist:
                        updated_lines.append(line.replace("- [ ]", "- [x]"))
                        checked_count += 1
                        logger.info(f"  ✅ Sous-tâche vérifiée : {subtask_text[:60]}")
                    else:
                        missing = [fp for fp in file_patterns if not (check_root / fp).exists()]
                        updated_lines.append(line)  # On ne coche PAS
                        logger.warning(f"  ❌ Sous-tâche NON vérifiée (fichiers manquants: {missing}): {subtask_text[:60]}")
                else:
                    # Pas de fichier mentionné (ex: "Installer les dépendances") 
                    # → On coche si l'étape parente est approuvée (comportement legacy)
                    updated_lines.append(line.replace("- [ ]", "- [x]"))
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

        self.etapes_path.write_text("\n".join(updated_lines), encoding="utf-8")
        logger.info(f"Étape '{step_id}' : {checked_count}/{total_subtasks} sous-tâches vérifiées et cochées.")

        if synthesis:
            self.add_step_to_history(step_id, synthesis)

        return True


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