# Point d'entrée CLI (Commandes: init, run, validate)
# Ce script est le point d'entrée unique de votre écosystème Speckit.Factory.
# Il utilise la bibliothèque click pour créer une interface en ligne de commande professionnelle

import click
import os
import json
from pathlib import Path
import logging
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()

from core.validator import SpecValidator
from core.graph import SpecGraphManager
from core.etapes import EtapeManager
from core.constitution_manager import ConstitutionManager

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
    
    # Sélection interactive des IA (Style GitHub Spec-Kit)
    click.echo("\n🤖 Configuration des IA partenaires (Sélectionnez une ou plusieurs) :")
    available_ais = {
        "1": ("Gemini-Cli", "google"),
        "2": ("Claude", "anthropic"),
        "3": ("GitHub Copilot", "copilot"),
        "4": ("Codex-Cli", "openai"),
        "5": ("Gemini 1.5 Flash (Rapide)", "google-flash")
    }
    
    selected_providers = []
    while not selected_providers:
        for key, (name, _) in available_ais.items():
            click.echo(f" {key}) {name}")
        
        choices = click.prompt(
            "Entrez les numéros séparés par une virgule (ex: 1,2,4)",
            default="1",
            type=str
        )
        
        for c in choices.split(","):
            c = c.strip()
            if c in available_ais:
                selected_providers.append(available_ais[c][1])
            else:
                click.echo(f"⚠️ Choix '{c}' invalide.")
        
        if not selected_providers:
            click.echo("🛑 Veuillez sélectionner au moins une IA.")

    # Initialisation du verrou .spec-lock.json avec les IA choisies
    lock_file = target_path / ".spec-lock.json"
    initial_lock = {
        "version": "1.1",
        "constitution_hash": "",
        "completed_tasks": [],
        "completed_specs": [],
        "active_tasks": {},
        "selected_ais": selected_providers
    }
    
    # Si on est dans un projet existant, on fusionne ou on écrase
    if lock_file.exists():
        try:
            with open(lock_file, "r") as f:
                existing = json.load(f)
                initial_lock["completed_tasks"] = existing.get("completed_tasks", [])
                initial_lock["completed_specs"] = existing.get("completed_specs", [])
        except:
            pass

    with open(lock_file, "w") as f:
        json.dump(initial_lock, f, indent=4)
    
    # Création du fichier de Gouvernance (pour forcer l'IA de l'IDE à obéir)
    rules_path = target_path / ".speckit-rules"
    rules_content = """# 🛡️ SPECKIT.FACTORY - LOI DE GOUVERNANCE
Ce projet est régi par la Doctrine Speckit.Factory. 
Toute IA (Gemini, Claude, Copilot) opérant dans ce dossier DOIT :
1. Consulter `Constitution/CONSTITUTION.md` avant toute action.
2. Ne jamais modifier le code sans passer par le cycle : Analyse -> Implémentation -> Audit.
3. Utiliser les commandes CLI `speckit` pour les phases de planification.
4. Respecter strictement la segmentation des dossiers Task1/Task2 pour la traçabilité.

**L'IA de l'IDE ne doit pas tenter de tout générer en un bloc.**
"""
    rules_path.write_text(rules_content, encoding="utf-8")

    click.echo(f"✅ IA configurées : {', '.join(selected_providers)}")
    click.echo("✅ PROJET INITIALISÉ. Fichier de gouvernance `.speckit-rules` créé.")
    click.echo("👉 Prochaine étape : `speckit specify 'votre demande ici'`")

def get_llm(provider: str = None, model_name: str = None):
    """Factory pour obtenir le modèle LLM selon le provider (auto-sélection si vide)."""
    if not provider:
        lock_file = Path(".spec-lock.json")
        if lock_file.exists():
            try:
                with open(lock_file, "r") as f:
                    data = json.load(f)
                    selected = data.get("selected_ais", [])
                    if selected:
                        provider = selected[0]
            except:
                pass
    
    provider = (provider or "google").lower() # Fallback ultime et case-insensibilité
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = model_name or "gemini-1.5-pro"
        return ChatGoogleGenerativeAI(model=model)
    elif provider == "google-flash":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = model_name or "gemini-1.5-flash"
        return ChatGoogleGenerativeAI(model=model)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model = model_name or "claude-3-5-sonnet-20240620"
        return ChatAnthropic(model=model)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = model_name or "gpt-4o"
        return ChatOpenAI(model=model)
    elif provider == "copilot":
        # Simulation via OpenAI ou spécifique Github si implémenté
        from langchain_openai import ChatOpenAI
        click.echo("💡 GitHub Copilot utilisé via l'API OpenAI (Codex compatible).")
        model = model_name or "gpt-4-turbo"
        return ChatOpenAI(model=model)
    elif provider == "minimax":
        # Deprecated: Minimax is no longer supported directly. 
        # Redirection vers Gemini Flash pour assurer la continuité
        click.echo("⚠️ Provider 'minimax' obsolète. Basculement sur Gemini 1.5 Flash...")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    else:
        raise ValueError(f"Provider {provider} non supporté.")

@cli.command()
@click.argument('prompt')
@click.option('--provider', help="Provider IA spécifique")
@click.option('--model', help="Nom du modèle spécifique")
def specify(prompt, provider, model):
    """[DOCTRINE 2] Analyse une demande et produit la CONSTITUTION.md."""
    try:
        llm = get_llm(provider, model)
        # Résolution du nom du provider pour l'affichage
        provider_name = provider
        if not provider_name:
            lock_file = Path(".spec-lock.json")
            if lock_file.exists():
                with open(lock_file, "r") as f:
                    data = json.load(f)
                    selected = data.get("selected_ais", [])
                    if selected:
                        provider_name = selected[0]
        
        provider_name = provider_name or "inconnu"
        click.echo(f"🧠 Analyse architecturale en cours avec l'IA ({provider_name})...")
        manager = ConstitutionManager(llm)
        manager.generate_constitution(prompt)
        click.echo("\n✅ CONSTITUTION GÉNÉRÉE dans `Constitution/CONSTITUTION.md`.")
        click.echo("👉 Veuillez la valider ou la modifier manuellement avant l'étape suivante.")
        click.echo("👉 Prochaine étape : `speckit plan` pour générer la feuille de route.")
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ["authentication", "auth", "api_key", "quota", "rate_limit", "resource_exhausted", "401", "429"]):
            click.echo("\n⚠️  [Modal Quota Reached]")
            click.echo("💡 Veuillez activer votre clé API ou changer de modèle.\n")
        else:
            click.echo(f"❌ Erreur : {e}")

@cli.command()
@click.option('--provider', help="Provider IA spécifique")
@click.option('--model', help="Nom du modèle spécifique")
def plan(provider, model):
    """[DOCTRINE 4] Analyse la Constitution et produit la feuille de route (etapes.md)."""
    try:
        llm = get_llm(provider, model)
        provider_name = provider
        if not provider_name:
            lock_file = Path(".spec-lock.json")
            if lock_file.exists():
                with open(lock_file, "r") as f:
                    data = json.load(f)
                    selected = data.get("selected_ais", [])
                    if selected:
                        provider_name = selected[0]

        provider_name = provider_name or "inconnu"
        click.echo(f"🗺️ Génération de la feuille de route avec l'IA ({provider_name})...")
        manager = EtapeManager(llm)
        manager.generate_steps_from_constitution()
        click.echo("✅ FEUILLE DE ROUTE GÉNÉRÉE dans `Constitution/etapes.md`.")
        click.echo("👉 Prochaine étape : `speckit run --task ID` pour commencer l'implémentation.")
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ["authentication", "auth", "api_key", "quota", "rate_limit", "resource_exhausted", "401", "429"]):
            click.echo("\n⚠️  [Modal Quota Reached]")
            click.echo("💡 Veuillez activer votre clé API ou changer de modèle.\n")
        else:
            click.echo(f"❌ Erreur : {e}")

@cli.command()
def status():
    """Affiche l'état d'avancement du projet selon la Doctrine."""
    click.echo("📊 STATUT SPECKIT.FACTORY :")
    
    const_path = Path("Constitution/CONSTITUTION.md")
    etapes_path = Path("Constitution/etapes.md")
    lock_file = Path(".spec-lock.json")

    click.echo(f" - Constitution : {'✅' if const_path.exists() and const_path.stat().st_size > 0 else '❌'}")
    click.echo(f" - Feuille de route : {'✅' if etapes_path.exists() else '❌'}")
    
    if etapes_path.exists():
        llm = get_llm()
        manager = EtapeManager(llm)
        progress = manager.get_progress()
        click.echo(f" - Progression : {progress['done']}/{progress['total']} tâches ({progress['progress_pct']}%)")
        next_task = manager.get_next_pending_step()
        if next_task:
            click.echo(f" 🔜 Prochaine tâche : {next_task}")

    if lock_file.exists():
        with open(lock_file, "r") as f:
            data = json.load(f)
            ais = data.get("selected_ais", [])
            click.echo(f" - IA actives : {', '.join(ais)}")

@cli.command()
@click.option('--task', required=True, help="ID de la tâche à exécuter (ex: 01_01)")
@click.option('--provider', help="Provider IA (laisssez vide pour utiliser le premier choix du projet)")
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
        # Sélection du provider par défaut si non spécifié
        if not provider:
            lock_file = Path(".spec-lock.json")
            if lock_file.exists():
                with open(lock_file, "r") as f:
                    data = json.load(f)
                    selected = data.get("selected_ais", [])
                    if selected:
                        provider = selected[0]
            
        if not provider:
            provider = "google" # Fallback ultime
            
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
        error_msg = str(e).lower()
        # Détection des erreurs de Quota / Auth (LangChain / Provider specific)
        if any(keyword in error_msg for keyword in ["authentication", "auth", "api_key", "quota", "rate_limit", "resource_exhausted", "401", "429"]):
            click.echo("\n⚠️  [Modal Quota Reached]")
            click.echo("💡 Veuillez activer votre clé API ou changer de modèle.\n")
        else:
            click.echo(f"❌ ERREUR lors de l'exécution : {e}")
            logger.exception("Détails de l'erreur :")
    finally:
        # 5. Libération du verrou
        validator.release_task_lock(task)

if __name__ == "__main__":
    cli()
