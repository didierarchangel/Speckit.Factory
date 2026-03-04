# Gestion des dossiers Task_App1/Task_App2
# Ce module est responsable de la création et de la gestion des dossiers Task_App1 et Task_App2.

import os
import json
import logging
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from core.guard import TaskAppOutput

logger = logging.getLogger(__name__)


class TaskAppManager:
    def __init__(self, model, project_root="."):
        self.model = model
        self.root = Path(project_root)
        self.task_app1_path = self.root / "Task_App1"
        self.task_app2_path = self.root / "Task_App2"
        self.parser = JsonOutputParser(pydantic_object=TaskAppOutput)

    def create_task_app_folders(self):
        """Crée les dossiers Task_App1 et Task_App2 s'ils n'existent pas."""
        self.task_app1_path.mkdir(parents=True, exist_ok=True)
        self.task_app2_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Dossiers {self.task_app1_path} et {self.task_app2_path} créés/vérifiés.")

    def generate_task_app_content(self, constitution_content: str) -> dict:
        """
        Génère le contenu des dossiers Task_App1 et Task_App2 à partir de la Constitution.
        Utilise JsonOutputParser pour garantir un format de sortie correct.

        Retourne un dictionnaire avec les clés 'task_app1' et 'task_app2'.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Tu es un Architecte Logiciel Senior. En te basant sur la Constitution fournie, "
             "tu dois initialiser l'état du projet.\n\n"
             "RÈGLES D'INITIALISATION :\n"
             "1. Task_App1 (Tâches non réalisées) : Liste toutes les tâches architecturales "
             "initiales nécessaires pour mettre en place le projet, sous forme de checklist "
             "Markdown (- [ ] Tâche).\n"
             "2. Task_App2 (Tâches réalisées) : Au début du projet, ce fichier est vide ou "
             "contient uniquement l'état initial 'Projet vierge'.\n\n"
             "{format_instructions}"),
            ("user", "Constitution:\n{constitution_content}")
        ])

        chain = prompt | self.model | self.parser
        
        try:
            content = chain.invoke({
                "constitution_content": constitution_content,
                "format_instructions": self.parser.get_format_instructions()
            })
            return content
        except Exception as e:
            logger.error(f"Erreur lors de la génération/parsing du contenu : {e}")
            return {
                "task_app1": "# Tâches Non Réalisées (Erreur de génération)",
                "task_app2": "# Tâches Réalisées\n\n*(Aucune)*"
            }

    def save_task_app_content(self, content: dict):
        """Sauvegarde le contenu généré dans les dossiers respectifs."""
        if "task_app1" in content:
            (self.task_app1_path / "task_app1.md").write_text(content["task_app1"], encoding="utf-8")
            logger.info("Contenu de Task_App1 sauvegardé.")
        
        if "task_app2" in content:
            (self.task_app2_path / "task_app2.md").write_text(content["task_app2"], encoding="utf-8")
            logger.info("Contenu de Task_App2 sauvegardé.")

    def create_and_save(self, constitution_content: str):
        """Méthode de commodité : crée les dossiers et sauvegarde le contenu."""
        self.create_task_app_folders()
        content = self.generate_task_app_content(constitution_content)
        self.save_task_app_content(content)
