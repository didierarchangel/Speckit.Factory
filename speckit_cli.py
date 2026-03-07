# Point d'entrée CLI (Commandes: init, run, validate)
# Ce script est le point d'entrée unique de votre écosystème Speckit.Factory.
# Il utilise la bibliothèque click pour créer une interface en ligne de commande professionnelle

import click
import os
import json
import shutil
from pathlib import Path
import logging
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
# On cherche le .env dans le dossier courant de l'utilisateur (là où il lance la commande)
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

if not os.environ.get("GOOGLE_API_KEY"):
    # Fallback sur le dossier racine du script si non trouvé dans le dossier courant
    script_env = Path(__file__).parent / ".env"
    if script_env.exists():
        load_dotenv(dotenv_path=script_env)

from core.validator import SpecValidator
from core.graph import SpecGraphManager
from core.etapes import EtapeManager
from core.constitution_manager import ConstitutionManager
from utils.file_manager import FileManager
import re

# Configuration des logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Désactiver les logs verbeux des bibliothèques externes (comme httpx et google_genai)
# pour ne pas polluer le terminal de l'utilisateur avec les retries 503
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("langchain_core").setLevel(logging.ERROR)

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
        "Constitution"
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
        "5": ("Gemini 2.5 Flash (Rapide)", "google-flash")
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

    # Sélection interactive de la Stack
    click.echo("\n🏗️ Configuration de la Stack Technique :")
    
    backend_choices = {
        "1": "Node.js (Express)",
        "2": "Node.js (NestJS)",
        "3": "Python (FastAPI)",
        "4": "Python (Flask)"
    }
    click.echo("--- Backend ---")
    for k, v in backend_choices.items(): click.echo(f" {k}) {v}")
    b_choice = click.prompt("Votre choix de Backend", default="1", type=click.Choice(list(backend_choices.keys())))
    selected_backend = backend_choices[b_choice]

    frontend_choices = {
        "1": "React (Vite)",
        "2": "Next.js (Vite)",
        "3": "Vue.js (Vite)",
        "4": "Python (Django Templates)",
        "5": "Aucun (API Pure)"
    }
    click.echo("\n--- Frontend ---")
    for k, v in frontend_choices.items(): click.echo(f" {k}) {v}")
    f_choice = click.prompt("Votre choix de Frontend", default="1", type=click.Choice(list(frontend_choices.keys())))
    selected_frontend = frontend_choices[f_choice]    # Création de l'arborescence de base
    if selected_backend != "Aucun":
        (target_path / "backend" / "src").mkdir(parents=True, exist_ok=True)
    if selected_frontend != "Aucun (API Pure)":
        (target_path / "frontend" / "src").mkdir(parents=True, exist_ok=True)

    # Préparation des templates locaux (.speckit/templates)
    templates_dir = target_path / ".speckit" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    # factory_root : on cherche templates/tsconfigs là où est le script
    factory_root = Path(__file__).parent
    
    # 1. Injection du Backend Template
    backend_ts_map = {
        "Node.js (Express)": "tsconfig.backend.node.json",
        "Node.js (NestJS)": "tsconfig.backend.node.json",
        "Python (FastAPI)": None,
        "Python (Flask)": None
    }
    
    selected_backend_name = selected_backend
    if selected_backend_name in backend_ts_map and backend_ts_map[selected_backend_name]:
        source = factory_root / "core" / "templates" / "tsconfigs" / backend_ts_map[selected_backend_name]
        if source.exists():
            # Copie pour le FileManager (vrai Golden Template)
            shutil.copy(str(source), str(templates_dir / "tsconfig.backend.json"))
            click.echo(f"✅ Template Backend ({selected_backend_name}) stocké localement.")
            
            # Injection immédiate pour tsc
            target_ts = target_path / "backend" / "tsconfig.json"
            shutil.copy(str(source), str(target_ts))
            click.echo("✅ `backend/tsconfig.json` initialisé.")

    # 2. Injection du Frontend Template
    frontend_ts_map = {
        "React (Vite)": "tsconfig.frontend.react.json",
        "Next.js (Vite)": "tsconfig.frontend.next.json",
        "Vue.js (Vite)": "tsconfig.frontend.react.json"
    }

    selected_frontend_name = selected_frontend
    if selected_frontend_name in frontend_ts_map:
        source = factory_root / "core" / "templates" / "tsconfigs" / frontend_ts_map[selected_frontend_name]
        if source.exists():
            # Copie pour le FileManager
            shutil.copy(str(source), str(templates_dir / "tsconfig.frontend.json"))
            click.echo(f"✅ Template Frontend ({selected_frontend_name}) stocké localement.")

            # Injection immédiate pour tsc
            target_ts = target_path / "frontend" / "tsconfig.json"
            shutil.copy(str(source), str(target_ts))
            click.echo("✅ `frontend/tsconfig.json` initialisé.")

    # Injection du tsconfig.json.example à la racine (pour visibilité utilisateur)
    # On prend le backend par défaut pour l'exemple racine
    rootsource = factory_root / "core" / "templates" / "tsconfigs" / "tsconfig.backend.node.json"
    if rootsource.exists():
        shutil.copy(str(rootsource), str(target_path / "tsconfig.json.example"))
        click.echo("✅ `tsconfig.json.example` généré à la racine.")

    # Initialisation du verrou .spec-lock.json
    lock_file = target_path / ".spec-lock.json"
    initial_lock = {
        "version": "1.1",
        "constitution_hash": "",
        "completed_tasks": [],
        "completed_specs": [],
        "active_tasks": {},
        "selected_ais": selected_providers,
        "stack_preferences": {
            "backend": selected_backend,
            "frontend": selected_frontend
        }
    }

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
4. Respecter strictement la traçabilité via `.spec-lock.json` et `etapes.md`.

**L'IA de l'IDE ne doit pas tenter de tout générer en un bloc.**
"""
    rules_path.write_text(rules_content, encoding="utf-8")

    # Création du fichier .env.example
    setup_env_logic(target_path)
    
    # Création du .gitignore par défaut pour le projet cible
    gitignore_path = target_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = """# 🛡️ Speckit.Factory - Project GitIgnore
.env
.env.*
node_modules/
dist/
build/
.spec-lock.json
*.log
"""
        gitignore_path.write_text(gitignore_content, encoding="utf-8")
        click.echo("✅ Fichier `.gitignore` par défaut créé.")


def setup_env_logic(target_path: Path):
    """Logique de création du fichier .env.example et .env (TEMPLATE)."""
    env_example_path = target_path / ".env.example"
    env_path = target_path / ".env"
    
    content = """# 🔑 Speckit.Factory - Clés API (Template)
# Ajoutez vos clés API ici pour activer les IA
# NE JAMAIS COMMITTER VOTRE VRAI FICHIER .env (il est dans le .gitignore)

# Google API Key for Gemini models (gemini-2.5-flash, gemini-2.5-flash-lite)
# Get one at https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=votre_cle_ici

# Anthropic (Claude)
ANTHROPIC_API_KEY=votre_cle_ici

# OpenAI (GPT / Copilot)
OPENAI_API_KEY=votre_cle_ici
"""
    env_example_path.write_text(content, encoding="utf-8")
    
    # Créer le .env s'il n'existe pas déjà pour faciliter la vie de l'utilisateur
    if not env_path.exists():
        env_path.write_text(content, encoding="utf-8")

@cli.command("setup-env")
@click.option('--path', default=".", help="Chemin où créer le fichier .env.example")
def setup_env(path):
    """Crée un fichier .env.example template dans le dossier spécifié."""
    target_path = Path(path)
    if not target_path.exists():
        click.echo(f"❌ Le dossier {target_path} n'existe pas.")
        return
    
    setup_env_logic(target_path)
    click.echo(f"✅ Fichier .env.example créé dans : {target_path.absolute()}")

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
    if provider in ["google", "google-flash"]:
        if not os.environ.get("GOOGLE_API_KEY"):
            click.echo("\n❌ ERREUR : La clé GOOGLE_API_KEY est manquante.")
            click.echo(f"📍 Dossier actuel : {os.getcwd()}")
            click.echo("💡 Assurez-vous d'avoir un fichier .env contenant 'GOOGLE_API_KEY=votre_cle'.")
            
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Utilisation de noms plus robustes/récents pour éviter les 404
        if not model_name:
            model = "gemini-2.5-flash" if provider == "google" else "gemini-2.5-flash-lite"
        else:
            model = model_name
            
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
@click.option('--instruction', help="Instruction supplémentaire guidant l'implémentation (ex: 'Ne touche pas au frontend')")
def run(task, provider, model, instruction):
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
        
        # Auto-détection du contexte pour protéger les dossiers (Frontend vs Backend)
        auto_instruction = instruction or ""
        if not auto_instruction:
            task_lower = task.lower()
            # Détection explicite
            if "backend" in task_lower:
                auto_instruction = "⚠️ CONTEXTE BACKEND UNIQUEMENT : Ne modifie, ne crée et n'analyse AUCUN fichier du dossier 'frontend'. Concentre-toi exclusivement sur le backend. TOUS les chemins de fichiers backend doivent commencer par 'backend/' (ex: backend/src/app.ts, backend/package.json)."
            elif "frontend" in task_lower:
                auto_instruction = "⚠️ CONTEXTE FRONTEND UNIQUEMENT : Ne modifie, ne crée et n'analyse AUCUN fichier du dossier 'backend'. Concentre-toi exclusivement sur le frontend. TOUS les chemins de fichiers frontend doivent commencer par 'frontend/' (ex: frontend/src/App.tsx, frontend/package.json)."
            # Détection implicite par mots-clés métier (backend par défaut si pas frontend)
            elif any(kw in task_lower for kw in ['jwt', 'auth', 'modele', 'model', 'route', 'service', 'crud', 'api', 'middleware', 'database', 'mongo', 'passport']):
                auto_instruction = "⚠️ CONTEXTE BACKEND UNIQUEMENT (détecté automatiquement) : Cette tâche concerne le backend. Ne modifie AUCUN fichier frontend. TOUS les chemins de fichiers DOIVENT commencer par 'backend/' (ex: backend/src/app.ts, backend/package.json). Ne génère JAMAIS un chemin comme 'src/app.ts' sans le préfixe 'backend/'."

        initial_state = {
            "constitution_hash": validator.calculate_hash(constitution_path),
            "constitution_content": constitution_content,
            "current_step": current_step,
            "completed_tasks_summary": "Historique chargé via .spec-lock.json",
            "pending_tasks": "Voir etapes.md",
            "target_task": task,
            "analysis_output": "",
            "code_to_verify": "",
            "validation_status": "",
            "feedback_correction": "",
            "terminal_diagnostics": "",
            "error_count": 0,
            "last_error": "",
            "user_instruction": auto_instruction
        }
        
        # Exécution du graphe
        final_state = initial_state
        for output in graph_manager.app.stream(initial_state):
            for node_name, result in output.items():
                click.echo(f"📍 Nœud [{node_name}] terminé.")
                final_state.update(result)
        
        # 5. Traitement du résultat final
        if final_state.get("validation_status") == "APPROUVÉ":
            click.echo("\n" + "="*50)
            click.echo("🛡️  RAPPORT D'AUDIT SPECKIT")
            click.echo("="*50)
            click.echo(f"⭐ Score : {final_state.get('score', 'N/A')}")
            click.echo(f"✅ Points forts : {final_state.get('points_forts', 'N/A')}")
            click.echo(f"⚠️  Alertes : {final_state.get('alertes', 'Aucune')}")
            click.echo("="*50 + "\n")

            # Sauvegarde des fichiers
            fm = FileManager()
            code = final_state.get("code_to_verify", "")
            
            if code:
                written_files = fm.extract_and_write(code)
                
                if written_files:
                    for file_path in written_files:
                        click.echo(f"💾 Fichier sauvegardé : {file_path}")
                else:
                    # Fallback intelligent sur l'ancien comportement
                    impacted = final_state.get("impact_fichiers", [])
                    # On cherche le premier qui n'est pas un dossier (ne finit pas par / ou \)
                    target_file = None
                    for imp in impacted:
                        clean_path = imp.split(":")[-1].strip()
                        if not (clean_path.endswith('/') or clean_path.endswith('\\')):
                            target_file = clean_path
                            break
                    
                    if target_file and fm.safe_write(target_file, code):
                        click.echo(f"💾 Code sauvegardé (fallback) dans : {target_file}")
                    else:
                        click.echo("⚠️ Impossible de déterminer un fichier de destination valide (échec parsing + pas de fichier cible trouvé).")
                
                # Mise à jour du statut avec synthèse pour l'historique
                synthesis = f"⭐⭐ Score : {final_state.get('score', 'N/A')}\n"
                synthesis += f"✅ Points forts : {final_state.get('points_forts', 'N/A')}\n"
                synthesis += f"⚠️ Alertes : {final_state.get('alertes', 'Aucune')}"
                
                manager_etapes.mark_step_as_completed(task, synthesis=synthesis)
                click.echo(f"✅ Tâche {task} marquée comme terminée dans etapes.md et archivée dans EtapesAdd.md")
                
                # Mise à jour du verrou .spec-lock.json
                lock_file = Path(".spec-lock.json")
                if lock_file.exists():
                    try:
                        with open(lock_file, "r") as f:
                            data = json.load(f)
                        if task not in data.get("completed_tasks", []):
                            data.setdefault("completed_tasks", []).append(task)
                        with open(lock_file, "w") as f:
                            json.dump(data, f, indent=4)
                    except Exception as e:
                        logger.error(f"Erreur lors de la mise à jour du lock : {e}")
            else:
                click.echo("⚠️ Aucun code généré trouvé.")
            
            click.echo(f"\n✨ Tâche {task} terminée avec succès.")
        else:
            click.echo("\n" + "!"*50)
            click.echo("❌ ÉCHEC DE L'AUDIT")
            click.echo("!"*50)
            click.echo(f"Raison : {final_state.get('alertes', 'Inconnue')}")
            click.echo(f"Action corrective : {final_state.get('feedback_correction', 'N/A')}")
            click.echo("!"*50 + "\n")
        
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
