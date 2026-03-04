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

    def generate_steps_from_constitution(self) -> str:
        """Analyse la Constitution pour définir les étapes du projet."""
        if not self.constitution_path.exists():
            raise FileNotFoundError(
                f"CONSTITUTION.md introuvable : {self.constitution_path}"
            )

        constitution_content = self.constitution_path.read_text(encoding="utf-8")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es un chef de projet DevOps. Basé sur la CONSTITUTION fournie,
            découpe le projet en étapes techniques numérotées (ex: 01, 02, 03).
            Format de sortie :
            ## [ ] 01_nom_etape : Description courte
            ## [ ] 02_nom_etape : Description courte"""),
            ("user", "{content}")
        ])

        chain = prompt | self.model | StrOutputParser()
        steps = chain.invoke({"content": constitution_content})

        self.etapes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.etapes_path, "w", encoding="utf-8") as f:
            f.write("# FEUILLE DE ROUTE DU PROJET (etapes.md)\n\n")
            f.write(steps)

        logger.info("Fichier etapes.md généré avec succès.")
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
        for line in content.splitlines():
            # Étape complétée : ## [x] 01_setup : Description
            match_done = re.search(r"## \[x\] (\w+)\s*:\s*(.*)", line)
            if match_done:
                steps.append({
                    "id": match_done.group(1),
                    "description": match_done.group(2).strip(),
                    "status": "done",
                })
                continue

            # Étape en attente : ## [ ] 02_api : Description
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

    def mark_step_as_completed(self, step_id: str) -> bool:
        """Passe une étape de [ ] à [x] une fois validée.

        Retourne True si l'étape a été trouvée et marquée, False sinon.
        """
        if not self.etapes_path.exists():
            raise FileNotFoundError(
                f"etapes.md introuvable : {self.etapes_path}"
            )

        content = self.etapes_path.read_text(encoding="utf-8")
        target = f"## [ ] {step_id}"

        if target not in content:
            logger.warning("Étape '%s' non trouvée ou déjà complétée.", step_id)
            return False

        updated_content = content.replace(target, f"## [x] {step_id}")
        self.etapes_path.write_text(updated_content, encoding="utf-8")

        logger.info("Étape '%s' marquée comme terminée.", step_id)
        return True