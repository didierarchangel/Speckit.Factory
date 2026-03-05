# Point d'entrée CLI (Commandes: init, run, validate)
# Ce script est le point d'entrée unique de votre écosystème Speckit.Factory.
# Il utilise la bibliothèque click pour créer une interface en ligne de commande professionnelle

import click
import os
import json
from pathlib import Path
import logging

from core.validator import SpecValidator
from core.graph import SpecGraphManager
from core.etapes import EtapeManager

# Configuration des logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Speckit")

# Configuration des chemins par défaut
DEFAULT_PROJECT_NAME = "SpecKit-App"

@click.group()
def cli():
    """🛡️ Speckit.Factory - Constitutional DevOps AI Framework"""
    pass

@cli.command()
@click.argument('path', default=DEFAULT_PROJECT_NAME)
@click.option('--here', is_flag=True, help="Initialise dans le dossier courant")
def init(path, here):
    """Initialise l'arborescence complète du projet."""
    target_path = Path(".") if here else Path(path)
    
    # Liste des dossiers à créer selon le protocole
    structure = [
        "Constitution",
        "Task_App1",      # Tâches non réalisées (Architecture)
        "Task_App2",      # Tâches réalisées (Architecture)
        "Task_Function1", # Spécifications non réalisées
        "Task_Function2", # Spécifications réalisées
        "Task1",          # Tâches techniques non réalisées
        "Task2"           # Tâches techniques réalisées
    ]

    click.echo(f"🏗️  Création de l'arborescence dans : {target_path.absolute()}")

    for folder in structure:
        (target_path / folder).mkdir(parents=True, exist_ok=True)
    
    # Création des fichiers de base
    (target_path / "Constitution" / "CONSTITUTION.md").touch()
    (target_path / "Constitution" / "etapes.md").touch()
    
    # Initialisation du verrou .spec-lock.json
    lock_file = target_path / ".spec-lock.json"
    if not lock_file.exists():
        initial_lock = {
            "constitution_hash": "",
            "completed_tasks": [],
            "completed_specs": []
        }
        with open(lock_file, "w") as f:
            json.dump(initial_lock, f, indent=4)
    
    click.echo("✅ Projet initialisé avec succès. La Constitution est prête.")

def get_llm(provider: str, model_name: str = None):
    """Factory pour obtenir le modèle LLM selon le provider."""
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = model_name or "gemini-1.5-pro"
        return ChatGoogleGenerativeAI(model=model)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model = model_name or "claude-3-5-sonnet-20240620"
        return ChatAnthropic(model=model)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = model_name or "gpt-4o"
        return ChatOpenAI(model=model)
    else:
        raise ValueError(f"Provider {provider} non supporté.")

@cli.command()
@click.option('--task', required=True, help="ID de la tâche à exécuter (ex: 01_01)")
@click.option('--provider', default="google", help="Provider IA (google, anthropic, openai)")
@click.option('--model', help="Nom du modèle spécifique")
def run(task, provider, model):
    """Exécute une tâche sous verrouillage de contexte et de concurrence."""
    validator = SpecValidator()
    
    # 1. Vérification de l'intégrité globale
    if not validator.check_integrity():
        click.echo("🛑 ARRÊT : Intégrité compromise ! Vérifiez vos fichiers core ou votre Constitution.")
        return

    # 2. Verrouillage de la tâche (Multi-IA safety)
    if not validator.acquire_task_lock(task):
        click.echo(f"🔒 La tâche {task} est déjà en cours d'exécution par une autre IA.")
        return

    try:
        click.echo(f"🚀 Initialisation de l'IA ({provider})...")
        llm = get_llm(provider, model)
        
        # 3. Chargement du contexte
        manager_etapes = EtapeManager(llm)
        constitution_path = Path("Constitution/CONSTITUTION.md")
        constitution_content = constitution_path.read_text(encoding="utf-8") if constitution_path.exists() else ""
        
        current_step = manager_etapes.get_next_pending_step() or "Inconnue"
        
        # 4. Orchestration via le graphe
        click.echo(f"🧠 Lancement du graphe d'orchestration pour : {task}")
        graph_manager = SpecGraphManager(llm)
        
        initial_state = {
            "constitution_content": constitution_content,
            "current_step": current_step,
            "completed_tasks_summary": "Historique chargé via .spec-lock.json",
            "pending_tasks": "Voir etapes.md",
            "target_task": task,
            "analysis_output": "",
            "code_to_verify": "",
            "validation_status": "",
            "feedback_correction": ""
        }
        
        # Exécution du graphe
        for output in graph_manager.app.stream(initial_state):
            for node_name, result in output.items():
                click.echo(f"📍 Nœud [{node_name}] terminé.")
        
        click.echo(f"✨ Tâche {task} terminée avec succès.")
        
    except Exception as e:
        click.echo(f"❌ ERREUR lors de l'exécution : {e}")
        logger.exception("Détails de l'erreur :")
    finally:
        # 5. Libération du verrou
        validator.release_task_lock(task)

if __name__ == "__main__":
    cli()
