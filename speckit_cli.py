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
from utils.scanner import SemanticScanner
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
    
    # Détection de projet existant (si le dossier n'est pas vide)
    existing_files = [f for f in target_path.glob('*') if f.name not in ['.git', '.speckit', '.gitignore', '.env', '.env.example']]
    if existing_files:
        click.echo(f"⚠️  ALERTE : Le dossier {target_path.absolute()} contient déjà des fichiers.")
        click.echo("💡 Si vous souhaitez ajouter une fonctionnalité à ce projet existant,")
        click.echo("💡 il est recommandé d'utiliser : speckit component \"votre demande\"")
        click.echo("---")
    
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

    # Injection de la CONSTITUTION par défaut
    factory_root = Path(__file__).parent
    source_constitution = factory_root / "core" / "templates" / "CONSTITUTION.template.md"
    if source_constitution.exists():
        shutil.copy(str(source_constitution), str(target_path / "Constitution" / "CONSTITUTION.md"))

    # Initialisation de l'intelligence graphique (design/)
    design_path = target_path / "design"
    (design_path / "dataset").mkdir(parents=True, exist_ok=True)
    
    source_design = factory_root / "core" / "templates" / "design"
    if source_design.exists():
        # Copie récursive des patterns et de la constitution design
        for item in source_design.iterdir():
            if item.is_dir():
                # On ne copie que dataset/ pour l'instant
                if item.name == "dataset":
                    for ds_file in item.iterdir():
                        # Mapper les anciens noms vers les nouveaux si nécessaire (bien que déjà renommés dans templates)
                        target_name = ds_file.name.replace("material", "standard").replace("pronanut", "premium")
                        shutil.copy(str(ds_file), str(design_path / "dataset" / target_name))
            else:
                shutil.copy(str(item), str(design_path / item.name))
        click.echo("✅ Intelligence Graphique (design/) initialisée.")
    
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
    
    design_choices = {
        "1": "Standard",
        "2": "premium"
    }
    click.echo("--- Style de Design ---")
    for k, v in design_choices.items(): click.echo(f" {k}) {v}")
    d_choice = click.prompt("Votre choix de Design", default="1", type=click.Choice(list(design_choices.keys())))
    selected_design = design_choices[d_choice]
    
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
            
            # --- Nouveau : Configuration .env du Backend ---
            setup_backend_env_logic(target_path, selected_backend)

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
            "frontend": selected_frontend,
            "design": selected_design
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

def setup_backend_env_logic(target_path: Path, backend_type: str):
    """Crée un fichier .env spécifique au backend sélectionné."""
    backend_env_path = target_path / "backend" / ".env"
    backend_env_example_path = target_path / "backend" / ".env.example"
    
    # Template par défaut (Node.js / MongoDB)
    content = """# 💻 Backend Configuration
PORT=5000
MONGODB_URI=mongodb://localhost:27017/mon_projet
JWT_SECRET=super_secret_key_à_changer_en_production
NODE_ENV=development
"""
    
    if "FastAPI" in backend_type or "Flask" in backend_type:
        content = """# 🐍 Python Backend Configuration
DATABASE_URL=sqlite:///./sql_app.db
SECRET_KEY=votre_cle_secrete_python
DEBUG=True
"""
    
    # Création des fichiers
    backend_env_path.parent.mkdir(parents=True, exist_ok=True)
    backend_env_example_path.write_text(content, encoding="utf-8")
    
    if not backend_env_path.exists():
        backend_env_path.write_text(content, encoding="utf-8")
    
    click.echo("✅ Environnement Backend (.env) initialisé.")

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
        
        # Configuration avec timeout pour éviter les blocages
        return ChatGoogleGenerativeAI(
            model=model,
            timeout=60,  # Timeout correct pour langchain-google-genai
            max_retries=2       # Retry automatique en cas d'échec
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model = model_name or "claude-3-5-sonnet-20240620"
        return ChatAnthropic(model=model, timeout=60, max_retries=2)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = model_name or "gpt-4o"
        return ChatOpenAI(model=model, request_timeout=60, max_retries=2)
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
            lock_file_path = Path(".spec-lock.json")
            if lock_file_path.exists():
                with open(lock_file_path, "r") as f:
                    data = json.load(f)
                    selected = data.get("selected_ais", [])
                    if selected:
                        provider_name = selected[0]

        # 1. Résolution du Design Style (Priorité : Lockfile > Prompt interactif)
        selected_design = None
        lock_file_path = Path(".spec-lock.json")
        
        if lock_file_path.exists():
            try:
                with open(lock_file_path, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                    selected_design = lock_data.get("stack_preferences", {}).get("design")
            except:
                pass

        if not selected_design:
            design_choices = {
                "1": "Standard",
                "2": "premium"
            }
            click.echo("\n🏗️  Style de Design pour ce projet :")
            for k, v in design_choices.items(): click.echo(f" {k}) {v}")
            d_choice = click.prompt("Votre choix de Design", default="1", type=click.Choice(list(design_choices.keys())))
            selected_design = design_choices[d_choice]
            
            # Sauvegarde immédiate dans le lock si on a dû demander
            if lock_file_path.exists():
                try:
                    with open(lock_file_path, "r", encoding="utf-8") as f:
                        lock_data = json.load(f)
                    if "stack_preferences" not in lock_data:
                        lock_data["stack_preferences"] = {}
                    lock_data["stack_preferences"]["design"] = selected_design
                    with open(lock_file_path, "w", encoding="utf-8") as f:
                        json.dump(lock_data, f, indent=4)
                except:
                    pass

        # 2. Vérification de la Constitution
        const_path = Path("Constitution/CONSTITUTION.md")
        if const_path.exists() and const_path.stat().st_size > 0:
            if not click.confirm("⚠️  Une CONSTITUTION existe déjà. Continuer écrasera vos règles actuelles. Voulez-vous continuer ?", default=False):
                click.echo("🛑 Opération annulée. Utilisez `speckit component` pour amender la Constitution.")
                return

        # 3. Synchronisation du Lock File (pour les futurs agents)
        lock_file_path = Path(".spec-lock.json")
        if lock_file_path.exists():
            try:
                with open(lock_file_path, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                if "stack_preferences" not in lock_data:
                    lock_data["stack_preferences"] = {}
                lock_data["stack_preferences"]["design"] = selected_design
                with open(lock_file_path, "w", encoding="utf-8") as f:
                    json.dump(lock_data, f, indent=4)
            except Exception as e:
                click.echo(f"⚠️ Impossible de mettre à jour le lock file : {e}")

        # 4. Génération de la Constitution
        click.echo(f"🧠 Analyse architecturale en cours avec l'IA ({provider_name})...")
        manager = ConstitutionManager(llm)
        manager.generate_constitution(prompt, design_style=selected_design)
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
@click.argument('prompt')
@click.option('--provider', help="Provider IA spécifique")
@click.option('--model', help="Nom du modèle spécifique")
def component(prompt, provider, model):
    """[DOCTRINE MAINT] Amende la Constitution et ajoute une nouvelle composante (Étape)."""
    try:
        llm = get_llm(provider, model)
        click.echo("🔍 Scan sémantique du projet en cours...")
        scanner = SemanticScanner()
        semantic_map = scanner.generate_map()
        
        click.echo("🧠 Analyse de l'évolution architecturale...")
        const_manager = ConstitutionManager(llm)
        const_manager.amend_constitution(prompt, semantic_map)
        
        click.echo("🗺️ Mise à jour de la feuille de route (etapes.md)...")
        etape_manager = EtapeManager(llm)
        new_step = etape_manager.append_steps_from_constitution(semantic_map=semantic_map)
        
        click.echo(f"\n✅ NOUVELLE COMPOSANTE AJOUTÉE :\n{new_step}")
        click.echo("\n👉 Prochaine étape : `speckit run --component ID` pour l'implémenter.")
    except Exception as e:
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
        click.echo("🔍 Scan sémantique du projet...")
        scanner = SemanticScanner()
        semantic_map = scanner.generate_map()

        etapes_path = Path("Constitution/etapes.md")
        if etapes_path.exists() and etapes_path.stat().st_size > 0:
            if not click.confirm("⚠️  Une feuille de route (etapes.md) existe déjà. L'écraser ?", default=False):
                click.echo("🛑 Opération annulée.")
                return

        click.echo(f"🗺️ Génération de la feuille de route intelligente avec l'IA ({provider_name})...")
        manager = EtapeManager(llm)
        manager.generate_steps_from_constitution(semantic_map=semantic_map)
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
@click.option('--task', help="ID de la tâche à exécuter (ex: 01_01)")
@click.option('--component', help="Alias pour --task, ID de la composante à exécuter")
@click.option('--provider', help="Provider IA (laisssez vide pour utiliser le premier choix du projet)")
@click.option('--model', help="Nom du modèle spécifique")
@click.option('--instruction', help="Instruction supplémentaire guidant l'implémentation (ex: 'Ne touche pas au frontend')")
def run(task, component, provider, model, instruction):
    """Exécute une tâche sous verrouillage de contexte et de concurrence."""
    target_id = task or component
    if not target_id:
        click.echo("❌ ERREUR : Vous devez spécifier --task ou --component.")
        return

    validator = SpecValidator()
    
    # 1. Vérification de l'intégrité globale
    if not validator.check_integrity():
        click.echo("🛑 ARRÊT : Intégrité compromise ! Vérifiez vos fichiers core ou votre Constitution.")
        return

    # 2. Verrouillage de la tâche (Multi-IA safety)
    if not validator.acquire_task_lock(target_id):
        click.echo(f"🔒 La tâche {target_id} est déjà en cours d'exécution par une autre IA.")
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
        
        # current_step = manager_etapes.get_next_pending_step() or "Inconnue"
        current_step = target_id # On utilise l'ID cible directement

        # Scan structure projet
        scanner = SemanticScanner()
        semantic_map = scanner.generate_map()
        file_tree = scanner.get_file_tree() 
        
        # 4. Orchestration via le graphe
        click.echo(f"🧠 Lancement du graphe d'orchestration pour : {target_id}")
        graph_manager = SpecGraphManager(llm) 
        
        # Extraction du checklist de sous-tâches
        subtasks = manager_etapes.get_subtasks_for_step(target_id)
        subtask_checklist = "\n".join([f"- [ ] {st}" for st in subtasks]) if subtasks else "Aucune sous-tâche définie."

        initial_state = {
            "constitution_hash": validator.calculate_hash(constitution_path),
            "constitution_content": constitution_content,
            "current_step": current_step,
            "completed_tasks_summary": "Historique chargé via .spec-lock.json",
            "pending_tasks": "Voir etapes.md",
            "target_task": target_id,
            "analysis_output": "",
            "code_to_verify": "",
            "validation_status": "",
            "feedback_correction": "",
            "terminal_diagnostics": "",
            "error_count": 0,
            "last_error": "",
            "user_instruction": instruction,
            "subtask_checklist": subtask_checklist,
            "code_map": semantic_map,
            "file_tree": file_tree,
            "existing_code_snapshot": ""
        }
        
        # Exécution du graphe
        final_state = initial_state
        for output in graph_manager.app.stream(initial_state):
            for node_name, result in output.items():
                final_state.update(result)
        
        # 5. Ground Truth : vérification réelle sur disque avant validation finale
        gt_result = manager_etapes.mark_step_as_completed(target_id, synthesis="", project_root=".")
        if isinstance(gt_result, tuple):
            _, checked_count, total_count = gt_result
        else:
            checked_count, total_count = 0, 0
        
        task_complete = (checked_count == total_count) if total_count > 0 else True
        audit_approved = final_state.get("validation_status") == "APPROUVÉ"
        
        if audit_approved and task_complete:
            click.echo("\n" + "="*50)
            click.echo("🛡️  RAPPORT D'AUDIT SPECKIT")
            click.echo("="*50)
            click.echo(f"⭐ Score : {final_state.get('score', 'N/A')}")
            click.echo(f"✅ Points forts : {final_state.get('points_forts', 'N/A')}")
            click.echo(f"⚠️  Alertes : {final_state.get('alertes', 'Aucune')}")
            click.echo(f"📊 Sous-tâches : {checked_count}/{total_count}")
            click.echo("="*50 + "\n")

            # Les fichiers sont déjà sur disque grâce à persist_node
            code = final_state.get("code_to_verify", "")
            if code:
                click.echo("💾 Fichiers déjà persistés par le pipeline.")
            else:
                click.echo("⚠️ Aucun code généré trouvé.")
            
            # Mise à jour du statut avec synthèse pour l'historique
            synthesis = f"⭐ Score : {final_state.get('score', 'N/A')}\n"
            synthesis += f"✅ Points forts : {final_state.get('points_forts', 'N/A')}\n"
            synthesis += f"⚠️ Alertes : {final_state.get('alertes', 'Aucune')}"
            
            manager_etapes.mark_step_as_completed(target_id, synthesis=synthesis)
            click.echo(f"✅ Tâche {target_id} marquée comme terminée dans etapes.md")
            
            # Mise à jour du verrou .spec-lock.json
            lock_file = Path(".spec-lock.json")
            if lock_file.exists():
                try:
                    with open(lock_file, "r") as f:
                        data = json.load(f)
                    if target_id not in data.get("completed_tasks", []):
                        data.setdefault("completed_tasks", []).append(target_id)
                    with open(lock_file, "w") as f:
                        json.dump(data, f, indent=4)
                except Exception as e:
                    logger.error(f"Erreur lors de la mise à jour du lock : {e}")
            
            click.echo(f"\n✨ Tâche {target_id} terminée avec succès.")
        else:
            click.echo("\n" + "!"*50)
            click.echo("❌ ÉCHEC DE L'AUDIT" if not audit_approved else "⚠️ SUCCÈS PARTIEL (Erreurs au Build)")
            click.echo("!"*50)
            if not audit_approved:
                click.echo(f"Raison Audit : {final_state.get('alertes', 'Aucune alerte')}")
                feedback = final_state.get('feedback_correction', '')
                if feedback:
                    click.echo(f"Action corrective : {feedback}")
            if not task_complete:
                click.echo(f"Raison Checklist : {checked_count}/{total_count} sous-tâches validées")
                
            # Loguer les erreurs TypeScript brutes pour que l'utilisateur puisse les voir
            terminal_errors = final_state.get('terminal_diagnostics', '')
            if terminal_errors and "❌ ÉCHEC" in terminal_errors:
                click.echo("\n🔍 DÉTAILS DES ERREURS TYPESCRIPT :")
                click.echo("-" * 40)
                click.echo(terminal_errors)
                click.echo("-" * 40)
                
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
        validator.release_task_lock(target_id)

if __name__ == "__main__":
    cli()
