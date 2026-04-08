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
from typing import Optional, Any
from pydantic import SecretStr

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

# 🛡️ CIRCUIT BREAKER - Global LLM Failure Threshold
MAX_LLM_FAILURES = 2
MAX_GRAPH_FAILURES = 3

# ============================================================
# 🔧 ROUTEURS BACKEND & FRONTEND (GÉNÉRATEURS)
# ============================================================

# 🗄️ Configurations de Package.json par base de données
def get_express_package_json(db_type: str = "mongodb") -> dict:
    """Génère le package.json Express selon le type de BD."""
    base_config = {
        "name": "backend",
        "version": "1.0.0",
        "description": "Backend for Project Application",
        "main": "dist/app.js",
        "type": "module",
        "scripts": {
            "dev": "cross-env NODE_OPTIONS='--loader ts-node/esm' nodemon --exec ts-node --esm src/app.ts",
            "build": "tsc",
            "start": "node dist/index.js",
            "lint": "eslint . --ext .ts",
            "format": "prettier --write \"src/**/*.ts\"",
            "test": "cross-env NODE_OPTIONS=--experimental-vm-modules jest"
        },
        "keywords": [],
        "author": "",
        "license": "ISC",
        "dependencies": {
            "cors": "2.8.5",
            "dotenv": "16.4.5",
            "express": "4.18.2",
            "helmet": "7.1.0",
            "jsonwebtoken": "9.0.2",
            "morgan": "1.10.0",
            "zod": "3.22.4",
            "bcryptjs": "2.4.3"
        },
        "devDependencies": {
            "@types/cors": "2.8.17",
            "@types/express": "4.17.21",
            "@types/jest": "29.5.12",
            "@types/jsonwebtoken": "9.0.6",
            "@types/morgan": "1.9.9",
            "@types/node": "20.12.12",
            "@types/supertest": "6.0.2",
            "@typescript-eslint/eslint-plugin": "8.57.0",
            "@typescript-eslint/parser": "8.57.0",
            "cross-env": "7.0.3",
            "eslint": "8.57.0",
            "eslint-config-prettier": "9.1.0",
            "eslint-plugin-prettier": "5.1.3",
            "jest": "29.7.0",
            "nodemon": "3.1.0",
            "prettier": "3.2.5",
            "supertest": "6.3.4",
            "ts-jest": "29.1.2",
            "ts-node": "^10.9.0",
            "typescript": "5.4.5"
        }
    }
    
    # Ajouter les dépendances spécifiques à la BD
    if db_type in ["postgresql", "supabase"]:
        base_config["dependencies"]["@prisma/client"] = "5.13.0"
        base_config["devDependencies"]["prisma"] = "5.13.0"
        base_config["scripts"]["prisma:generate"] = "prisma generate"
        base_config["scripts"]["prisma:migrate"] = "prisma migrate dev"
        base_config["scripts"]["prisma:setup"] = "prisma generate && prisma migrate dev --name init"
        base_config["scripts"]["prisma:studio"] = "prisma studio"
    elif db_type == "mongodb":
        base_config["dependencies"]["mongoose"] = "^8.0.0"
        base_config["dependencies"]["mongodb"] = "^6.0.0"
    
    return base_config

def generate_express_project(target_path: Path, db_type: str = "mongodb"):
    """Génère la structure de base pour Express.js avec support BD."""
    backend_path = target_path / "backend"
    src_path = backend_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    
    package_json = get_express_package_json(db_type)
    
    (backend_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (src_path / "index.ts").write_text("import express from 'express';\nconst app = express();\napp.listen(5000);\n")
    click.echo(f"✅ Projet Express configuré (BD: {db_type})")

def generate_nestjs_project(target_path: Path):
    """Génère la structure de base pour NestJS (100% ESM)."""
    backend_path = target_path / "backend"
    src_path = backend_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    
    # ✅ CONFIGURATION ESM POUR NESTJS
    package_json = {
        "name": "backend-nestjs",
        "version": "1.0.0",
        "type": "module",  # ✅ ESM obligatoire
        "main": "dist/main.js",
        "scripts": {
            "dev": "cross-env NODE_OPTIONS='--loader ts-node/esm' nest start --watch",
            "build": "nest build",
            "start": "node dist/main.js",
            "lint": "eslint . --ext .ts"
        },
        "dependencies": {
            "@nestjs/common": "^10.0.0",
            "@nestjs/core": "^10.0.0",
            "@nestjs/platform-express": "^10.0.0",
            "reflect-metadata": "^0.1.0",
            "rxjs": "^7.8.0"
        },
        "devDependencies": {
            "@nestjs/cli": "^10.0.0",
            "@nestjs/schematics": "^10.0.0",
            "@type-fest/package": "^0.20.0",
            "typescript": "^5.0.0",
            "@types/node": "^20.0.0",
            "ts-node": "^10.9.0",
            "cross-env": "^7.0.0"
        }
    }
    
    (backend_path / "package.json").write_text(json.dumps(package_json, indent=2))
    
    # ✅ Fichier main.ts en ESM
    main_ts = """/**
 * NestJS Main Entry Point (ESM)
 * Import: utilise la syntaxe ESM avec extensions '.js'
 */

import { NestFactory } from '@nestjs/core'
import { AppModule } from './app.module.js'

async function bootstrap() {
    const app = await NestFactory.create(AppModule)
    const port = process.env.PORT || 3000
    await app.listen(port)
    console.log(`✅ NestJS app listening on port ${port}`)
}

bootstrap().catch(err => {
    console.error('❌ Erreur au démarrage:', err)
    process.exit(1)
})
"""
    (src_path / "main.ts").write_text(main_ts)
    click.echo("✅ Projet NestJS configuré (ESM + TypeScript)")

def generate_fastapi_project(target_path: Path):
    """Génère la structure pour FastAPI (Python)."""
    backend_path = target_path / "backend"
    src_path = backend_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    
    requirements = "fastapi==0.104.0\nuvicorn==0.24.0\npydantic==2.5.0\npython-dotenv==1.0.0\n"
    (backend_path / "requirements.txt").write_text(requirements)
    
    main_py = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FastAPI Backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
    (src_path / "main.py").write_text(main_py)
    click.echo("✅ Projet FastAPI configuré")

def generate_flask_project(target_path: Path):
    """Génère la structure pour Flask (Python)."""
    backend_path = target_path / "backend"
    src_path = backend_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    
    requirements = "flask==3.0.0\nflask-cors==4.0.0\npython-dotenv==1.0.0\n"
    (backend_path / "requirements.txt").write_text(requirements)
    
    main_py = """from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def hello():
    return {"message": "Flask Backend"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)
"""
    (src_path / "main.py").write_text(main_py)
    click.echo("✅ Projet Flask configuré")

def generate_react_vite_project(target_path: Path):
    """Génère la structure pour React + Vite."""
    frontend_path = target_path / "frontend"
    src_path = frontend_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    
    package_json = {
        "name": "frontend-react",
        "version": "1.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview"
        },
        "dependencies": {
            "react": "^18.0.0",
            "react-dom": "^18.0.0"
        },
        "devDependencies": {
            "vite": "^5.0.0",
            "@vitejs/plugin-react": "^4.0.0",
            "typescript": "^5.0.0"
        }
    }
    
    (frontend_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (src_path / "App.tsx").write_text("export default function App() {\n  return <h1>React + Vite</h1>;\n}\n")
    click.echo("✅ Projet React (Vite) configuré")

def generate_nextjs_project(target_path: Path):
    """Génère la structure pour Next.js."""
    frontend_path = target_path / "frontend"
    app_path = frontend_path / "app"
    app_path.mkdir(parents=True, exist_ok=True)
    
    package_json = {
        "name": "frontend-nextjs",
        "version": "1.0.0",
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start"
        },
        "dependencies": {
            "next": "^14.0.0",
            "react": "^18.0.0",
            "react-dom": "^18.0.0"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "@types/node": "^20.0.0"
        }
    }
    
    (frontend_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (app_path / "page.tsx").write_text("export default function Home() {\n  return <main>Next.js Frontend</main>;\n}\n")
    click.echo("✅ Projet Next.js configuré")

def generate_vue_vite_project(target_path: Path):
    """Génère la structure pour Vue.js + Vite."""
    frontend_path = target_path / "frontend"
    src_path = frontend_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    
    package_json = {
        "name": "frontend-vue",
        "version": "1.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build"
        },
        "dependencies": {
            "vue": "^3.0.0"
        },
        "devDependencies": {
            "vite": "^5.0.0",
            "@vitejs/plugin-vue": "^5.0.0",
            "typescript": "^5.0.0"
        }
    }
    
    (frontend_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (src_path / "App.vue").write_text("<template><h1>Vue + Vite</h1></template>\n")
    click.echo("✅ Projet Vue.js (Vite) configuré")

# 🗺️ Mappings des générateurs (mise à jour pour supporter BD parameter)
BACKEND_GENERATORS = {
    "express": lambda target_path, db: generate_express_project(target_path, db),
    "nestjs": generate_nestjs_project,
    "fastapi": generate_fastapi_project,
    "flask": generate_flask_project
}

FRONTEND_GENERATORS = {
    "react-vite": generate_react_vite_project,
    "nextjs": generate_nextjs_project,
    "vue-vite": generate_vue_vite_project
}

# 💡 Recommandations intelligentes de Backend selon Frontend
BACKEND_RECOMMENDATIONS = {
    "react-vite": "express",      # React classique → Express
    "nextjs": "nestjs",           # Next.js → NestJS (TypeScript, scalable)
    "vue-vite": "express",        # Vue → Express (léger)
    "django-templates": "fastapi" # Django → FastAPI (Python)
}

def get_recommended_backend(frontend_choice: str) -> str:
    """Retourne le backend recommandé pour le frontend sélectionné."""
    return BACKEND_RECOMMENDATIONS.get(frontend_choice, "express")

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
    factory_root = Path(__file__).parent.parent
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
    
    # Sélection interactive des IA
    click.echo("\n🤖 Configuration des IA que vous souhaitez utiliser pour vibe-coder (Sélectionnez une ou plusieurs) :")

    available_ais = {
        "1": ("Gemini 2.5 Flash (Rapide)", "google"),
        "2": ("OpenAI GPT", "openai"),
        "3": ("Anthropic Claude", "anthropic"),
        "4": ("DeepSeek", "deepseek"),
        "5": ("xAI Grok", "grok"),
        "6": ("OpenRouter (Accès multi-modèles)", "openrouter")
    }

    selected_providers = []

    while not selected_providers:

        for key, (name, _) in available_ais.items():
            click.echo(f" {key}) {name}")

        choices = click.prompt(
            "Entrez les numéros séparés par une virgule (ex: 1,3,6)",
            default="1",
            type=str
        )

        for c in choices.split(","):
            c = c.strip()

            ai_choice = available_ais.get(c)
            if ai_choice:
                selected_providers.append(ai_choice[1])
            else:
                click.echo(f"⚠️ Choix '{c}' invalide.")

        if not selected_providers:
            click.echo("🛑 Veuillez sélectionner au moins une IA.")

# Sélection des modèles spécifiques pour les provider OpenRouter (DeepSeek, Claude, Grok, etc.)
        openrouter_model = None

    if "openrouter" in selected_providers:

        click.echo("\n🌐 Sélection du modèle OpenRouter :")

        openrouter_models = {
        "1": ("Claude 3 Haiku", "anthropic/claude-3-haiku"),
        "2": ("Claude 3.5 Sonnet", "anthropic/claude-3.5-sonnet"),
        "3": ("Grok 2", "x-ai/grok-2"),
        "4": ("Mixtral 8x7B", "mistralai/mixtral-8x7b")
    }

        for key, (name, _) in openrouter_models.items():
            click.echo(f" {key}) {name}")

        choice = click.prompt(
            "Choisissez un modèle",
            default="1",
            type=click.Choice(list(openrouter_models.keys()))
        )

        openrouter_model = openrouter_models[choice][1]
    else:
        openrouter_model = None
    
    # Sélection interactive de la Stack
    click.echo("\n🏗️ Configuration de la Stack Technique :")
    
    # On impose le style Premium par défaut (Design Intelligence activé)
    selected_design = "premium"
    click.echo(f"🎨 Style de Design : {selected_design} (Constitutional Architecture)")
    
    # ============================================================
    # 📱 SÉLECTION FRONTEND EN PREMIER (pour recommandations)
    # ============================================================
    frontend_choices = {
        "1": ("react-vite", "React (Vite)"),
        "2": ("nextjs", "Next.js"),
        "3": ("vue-vite", "Vue.js (Vite)"),
        "4": ("django-templates", "Python (Django Templates)"),
        "5": ("none", "Aucun (API Pure)")
    }

    click.echo("\n--- Frontend (sélectionnez en premier pour recommandations) ---")
    for k, v in frontend_choices.items(): 
        click.echo(f" {k}) {v[1]}")
    f_choice = click.prompt("Votre choix de Frontend", default="1", type=click.Choice(list(frontend_choices.keys())))
    selected_frontend_id, selected_frontend_label = frontend_choices[f_choice]
    
    # ============================================================
    # 💻 SÉLECTION BACKEND (avec recommandation intelligente)
    # ============================================================
    backend_choices = {
        "1": ("express", "Node.js (Express) ⚡ Prioritaire"),
        "2": ("nestjs", "Node.js (NestJS)"),
        "3": ("fastapi", "Python (FastAPI)"),
        "4": ("flask", "Python (Flask)")
    }
    
    recommended_backend = get_recommended_backend(selected_frontend_id)
    recommended_idx = None
    for idx, (backend_id, _) in backend_choices.items():
        if backend_id == recommended_backend:
            recommended_idx = idx
            break
    
    click.echo(f"\n--- Backend ({selected_frontend_label} recommande: {recommended_backend}) ---")
    for k, v in backend_choices.items(): 
        is_recommended = " 💡" if k == recommended_idx else ""
        click.echo(f" {k}) {v[1]}{is_recommended}")
    
    default_backend_choice = recommended_idx or "1"
    b_choice = click.prompt("Votre choix de Backend", default=default_backend_choice, type=click.Choice(list(backend_choices.keys())))
    selected_backend_id, selected_backend_label = backend_choices[b_choice]
    
    # ============================================================
    # �️ SÉLECTION BASE DE DONNÉES
    # ============================================================
    database_choices = {
        "1": ("mongodb", "MongoDB (NoSQL - Flexible)"),
        "2": ("postgresql", "PostgreSQL Local (SQL Relational)"),
        "3": ("supabase", "Supabase (PostgreSQL Cloud)")
    }
    
    click.echo("\n--- Base de Données ---")
    for k, v in database_choices.items():
        click.echo(f" {k}) {v[1]}")
    db_choice = click.prompt("Votre choix de Base de Données", default="1", type=click.Choice(list(database_choices.keys())))
    selected_database_id, selected_database_label = database_choices[db_choice]
    
    # ============================================================
    # 🚀 APPELS AUX GÉNÉRATEURS (via MAPPINGS)
    # ============================================================
    click.echo("\n🔧 Initialisation des structures de projet...")
    
    # Création de l'arborescence de base
    if selected_backend_id != "none":
        (target_path / "backend" / "src").mkdir(parents=True, exist_ok=True)
        # Appel du générateur Backend via le mapping avec paramètre BD
        if selected_backend_id in BACKEND_GENERATORS:
            if selected_backend_id == "express":
                BACKEND_GENERATORS[selected_backend_id](target_path, selected_database_id)
            else:
                BACKEND_GENERATORS[selected_backend_id](target_path)

    if selected_frontend_id != "none":
        (target_path / "frontend" / "src").mkdir(parents=True, exist_ok=True)
        # Appel du générateur Frontend via le mapping
        if selected_frontend_id in FRONTEND_GENERATORS:
            FRONTEND_GENERATORS[selected_frontend_id](target_path)


    # Préparation des templates locaux (.speckit/templates)
    templates_dir = target_path / ".speckit" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    # factory_root : on cherche templates/tsconfigs là où est le script
    factory_root = Path(__file__).parent.parent
    
    # 1. Injection du Backend Template
    backend_ts_map = {
        "express": "tsconfig.backend.node.json",
        "nestjs": "tsconfig.backend.node.json",
        "fastapi": None,
        "flask": None
    }
    
    backend_ts_file = backend_ts_map.get(selected_backend_id)
    if backend_ts_file:
        source = factory_root / "core" / "templates" / "tsconfigs" / backend_ts_file
        if source.exists():
            # Copie pour le FileManager (vrai Golden Template)
            shutil.copy(str(source), str(templates_dir / "tsconfig.backend.json"))
            click.echo(f"✅ Template Backend ({selected_backend_label}) stocké localement.")
            
            # Injection immédiate pour tsc
            target_ts = target_path / "backend" / "tsconfig.json"
            shutil.copy(str(source), str(target_ts))
            click.echo("✅ `backend/tsconfig.json` initialisé.")
            
            # --- Nouveau : Configuration .env du Backend ---
            setup_backend_env_logic(target_path, selected_backend_id, selected_database_id)

    # 2. Injection du Frontend Template
    frontend_ts_map = {
        "react-vite": "tsconfig.frontend.react.json",
        "nextjs": "tsconfig.frontend.next.json",
        "vue-vite": "tsconfig.frontend.react.json"
    }

    if selected_frontend_id in frontend_ts_map:
        source = factory_root / "core" / "templates" / "tsconfigs" / frontend_ts_map[selected_frontend_id]
        if source.exists():
            # Copie pour le FileManager
            shutil.copy(str(source), str(templates_dir / "tsconfig.frontend.json"))
            click.echo(f"✅ Template Frontend ({selected_frontend_label}) stocké localement.")

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
        "openrouter_model": openrouter_model,  # Persistance du modèle OpenRouter sélectionné
        "stack_preferences": {
            "backend": selected_backend_id,
            "frontend": selected_frontend_id,
            "design": selected_design,
            "database": selected_database_id
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
        click.echo("\n✨ Projet initialisé avec succès!")
        click.echo("\n✨ Avant de passer à la prochaine étape, n'oubliez pas de configurer vos clés API dans le fichier `.env` à la racine du projet.")
        click.echo("👉 Prochaine étape : `speckit specify \"Voici mon projet pour une application ...\"`")


def setup_env_logic(target_path: Path):
    """Logique de création du fichier .env.example et .env (TEMPLATE)."""
    env_example_path = target_path / ".env.example"
    env_path = target_path / ".env"
    
    content = """# 🔑 Speckit.Factory - Clés API (Template)
# Ajoutez vos clés API ici pour activer les IA
# NE JAMAIS COMMITTER VOTRE VRAI FICHIER .env (il est dans le .gitignore)

# Anthropic (Claude)
ANTHROPIC_API_KEY=votre_cle_ici

# CODEX-CLI (GPT)
OPENAI_API_KEY=votre_cle_ici
# Get one at https://openai.com/fr-FR/index/openai-api/

# Google API Key for Gemini models (gemini-1.5-flash, gemini-1.5-flash-lite, gemini-1.5-pro)
# Get one at https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=votre_cle_ici

# OpenRouter (DeepSeek, etc.)
OPENROUTER_API_KEY=votre_cle_ici
# Get one at https://openrouter.ai/settings/keys

"""
    env_example_path.write_text(content, encoding="utf-8")
    
    # Créer le .env s'il n'existe pas déjà pour faciliter la vie de l'utilisateur
    if not env_path.exists():
        env_path.write_text(content, encoding="utf-8")

def setup_backend_env_logic(target_path: Path, backend_id: str, db_type: str = "mongodb"):
    """Crée un fichier .env spécifique au backend et à la BD sélectionnée."""
    backend_env_path = target_path / "backend" / ".env"
    backend_env_example_path = target_path / "backend" / ".env.example"
    
    # Template par défaut selon la BD
    if db_type == "mongodb":
        content = """# 💻 Backend Configuration - MongoDB
PORT=5000
MONGODB_URI=mongodb://localhost:27017/mon_projet
JWT_SECRET=super_secret_key_à_changer_en_production
NODE_ENV=development
"""
    elif db_type == "postgresql":
        content = """# 💻 Backend Configuration - PostgreSQL Local
PORT=5000
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/drugstoredb
JWT_SECRET=super_secret_key_à_changer_en_production
NODE_ENV=development
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=postgres
DB_PASSWORD=PASSWORD
DB_NAME=drugstoredb
"""
    elif db_type == "supabase":
        content = """# 💻 Backend Configuration - Supabase (PostgreSQL Cloud)
PORT=5000
DATABASE_URL=postgresql://postgres.PROJECT_ID:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres
JWT_SECRET=super_secret_key_à_changer_en_production
NODE_ENV=production
DATABASE_TYPE=postgres
DB_HOST=db.PROJECT_ID.supabase.co
DB_PORT=5432
DB_USERNAME=postgres
DB_PASSWORD=PASSWORD
DB_NAME=postgres
SUPABASE_PROJECT_ID=PROJECT_ID
SUPABASE_API_KEY=your_supabase_api_key
SUPABASE_URL=https://PROJECT_ID.supabase.co
"""
    else:
        # Fallback Node.js / MongoDB (Python pour FastAPI/Flask)
        if backend_id in ["fastapi", "flask"]:
            content = """# 🐍 Python Backend Configuration
DATABASE_URL=sqlite:///./sql_app.db
SECRET_KEY=votre_cle_secrete_python
DEBUG=True
"""
        else:
            content = """# 💻 Backend Configuration
PORT=5000
MONGODB_URI=mongodb://localhost:27017/mon_projet
JWT_SECRET=super_secret_key_à_changer_en_production
NODE_ENV=development
"""
    
    # Création des fichiers
    backend_env_path.parent.mkdir(parents=True, exist_ok=True)
    backend_env_example_path.write_text(content, encoding="utf-8")
    
    if not backend_env_path.exists():
        backend_env_path.write_text(content, encoding="utf-8")
    
    click.echo(f"✅ Environnement Backend (.env pour {db_type}) initialisé.")

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

def get_llm(provider: Optional[str] = None, model_name: Optional[str] = None, temperature: float = 0.0):
    """Factory LLM multi-provider Speckit."""

    # Auto-détection depuis .spec-lock.json
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

    provider = (provider or "google").lower()

    # ---------------- GOOGLE (Gemini) ----------------
    if provider in ["google", "google-flash"]:

        if not os.environ.get("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY manquant")

        from langchain_google_genai import ChatGoogleGenerativeAI

        model = model_name or (
            "gemini-2.5-flash"
            if provider == "google"
            else "gemini-2.5-flash-lite"
        )

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            timeout=60,
            max_retries=2
        )

    # ---------------- OPENAI ----------------
    elif provider == "openai":

        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY manquant")

        from langchain_openai import ChatOpenAI

        model = model_name or "gpt-4o"

        return ChatOpenAI(
            model=model,
            timeout=60,
            max_retries=2
        )

    # ---------------- ANTHROPIC ----------------
    elif provider == "anthropic":

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY manquant")

        from langchain_anthropic import ChatAnthropic

        model = model_name or "claude-3-5-sonnet-20240620"

        return ChatAnthropic(
                model_name=model,
                max_tokens_to_sample=1024,
                timeout=60,
                max_retries=2,
                stop=None
            )

    # ---------------- DEEPSEEK ----------------
    elif provider == "deepseek":

        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        if not deepseek_key:
            raise ValueError("DEEPSEEK_API_KEY manquant")

        from langchain_openai import ChatOpenAI

        model = model_name or "deepseek-chat"

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(deepseek_key),
            base_url="https://api.deepseek.com/v1",
            timeout=60,
            max_retries=2
        )

    # ---------------- GROK ----------------
    elif provider == "grok":

        grok_key = os.environ.get("GROK_API_KEY")
        if not grok_key:
            raise ValueError("GROK_API_KEY manquant")

        from langchain_openai import ChatOpenAI

        model = model_name or "grok-2-latest"

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(grok_key),
            base_url="https://api.x.ai/v1",
            timeout=60,
            max_retries=2
        )

    # ---------------- OPENROUTER ----------------
    elif provider == "openrouter":

        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY manquant")

        from langchain_openai import ChatOpenAI

        # Récupérer le modèle depuis lock file si pas de modèle spécifié
        if not model_name:
            lock_file = Path(".spec-lock.json")
            if lock_file.exists():
                try:
                    with open(lock_file, "r") as f:
                        data = json.load(f)
                        saved_model = data.get("openrouter_model")
                        if saved_model:
                            model_name = saved_model
                except:
                    pass
        
        model = model_name or "meta-llama/llama-3.3-70b-instruct:free"

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(openrouter_key),
            base_url="https://openrouter.ai/api/v1",
            timeout=60,
            max_retries=2
        )

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
        click.echo("👉 Veuillez la valider ou la modifier manuellement.")
        click.echo("👉 Prochaine étape : `speckit vibe-design` pour extraire l'identité visuelle.")
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
@click.argument('arg_prompt', required=False)
@click.option('--provider', help="Provider IA spécifique")
@click.option('--model', help="Nom du modèle spécifique")
@click.option('--prompt', help="Description additionnelle de l'ambiance (Vibe)")
def vibe_design(arg_prompt, provider, model, prompt):
    """[VIBE DESIGN MAKER] Extrait l'identité visuelle (tokens, patterns) du projet."""
    raw_prompt = arg_prompt or prompt or "Générer une identité visuelle premium et cohérente."
    full_prompt = f"speckit vibe-design : {raw_prompt}"
    try:
        from core.graph import AgentState
        # Temperature=0 pour une extraction de design précise
        llm = get_llm(provider, model, temperature=0)
        click.echo("🎨 Vibe Design Maker : Extraction de l'identité visuelle...")
        
        # Charger la constitution
        const_path = Path("Constitution/CONSTITUTION.md")
        if not const_path.exists():
            click.echo("❌ Erreur : La Constitution est manquante. Lancez `speckit specify` d'abord.")
            return
        constitution_content = const_path.read_text(encoding="utf-8")
        
        # Initialiser le manager de graphe
        graph_manager = SpecGraphManager(llm)
        
        # État initial pour le design
        state: AgentState = {
            "constitution_content": constitution_content,
            "user_instruction": full_prompt,
            "target_task": "Vibe Design Extraction",
            "pattern_vision": {},
            "component_manifest": {},
            "project_brief": {},
            "design_system": {},
            "ux_flow": {},
            "current_step": "design_extraction"
        }
        
        # Exécuter SEULEMENT les nœuds de design pour ne pas écraser la constitution métier
        # click.echo(" ↳ ✨ Enrichissement du brief projet...")
        # state.update(graph_manager.project_enhancer_node(state)) # type: ignore
        
        # click.echo(" ↳ 🧩 Segmentation des composants UI...")
        # state.update(graph_manager.component_improver_node(state)) # type: ignore
        
        click.echo(" ↳ 👁️  Détection des patterns visuels (Vibe)...")
        state.update(graph_manager.pattern_vision_node(state)) # type: ignore
        
        click.echo(" ↳ 🎨 Génération du Design System...")
        state.update(graph_manager.design_system_node(state)) # type: ignore
        
        # click.echo(" ↳ 🌊 Définition des flux UX...")
        # state.update(graph_manager.ux_flow_node(state)) # type: ignore
        
        # click.echo(" ↳ 📜 Mise à jour de la Constitution avec le design...")
        # state.update(graph_manager.constitution_generator_node(state)) # type: ignore
        
        # 🛡️ PERSISTENCE : Sauvegarder les tokens dans design/tokens.yaml
        tokens_path = Path("design/tokens.yaml")
        tokens_path.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        tokens = state.get("pattern_vision", {}).get("tokens", {})
        if tokens:
            with open(tokens_path, "w", encoding="utf-8") as f:
                yaml.dump(tokens, f, default_flow_style=False)
            click.echo(f" ↳ 💾 Tokens sauvegardés dans {tokens_path}")
        
        # 📜 Smart Update de la Constitution
        if constitution_content:
            import re
            ds_style = state.get("design_system", {}).get("style", "premium")
            ds_tokens = state.get("pattern_vision", {}).get("tokens", {}).get("colors", {}).keys()
            tokens_str = ", ".join(ds_tokens) if ds_tokens else "primary, secondary, accent"
            
            new_design_block = f"## 🎨 Design System Généré\n- Style: {ds_style}\n- Tokens clés: {tokens_str}\n"
            
            # Remplacement de la section Design existante
            pattern = re.compile(r"## 🎨 Design System Généré.*?(?=\n## |$)", re.DOTALL)
            if pattern.search(constitution_content):
                new_const = pattern.sub(new_design_block, constitution_content)
            else:
                new_const = constitution_content + "\n\n" + new_design_block
                
            const_path.write_text(new_const, encoding="utf-8")
            click.echo(" ↳ 📜 Constitution mise à jour intelligemment (sans effacer le métier).")
        click.echo("")
        click.secho("✨ [VIBE DESIGN MAKER] EXTRACTION RÉUSSIE !", fg="green", bold=True)
        click.echo(f"✅ Tokens visuels sauvegardés dans `{tokens_path}`.")
        click.echo("✅ Constitution enrichie avec l'identité du projet.")
        click.echo("")
        click.secho("👉 PROCHAINE ÉTAPE :", fg="cyan", bold=True)
        click.echo("   Exécutez `speckit plan` pour générer la feuille de route basée sur ce nouveau design.")
        click.echo("")
    except Exception as e:
        click.echo(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()

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
        
        # Vérification si le design est présent
        tokens_path = Path("design/tokens.yaml")
        if not tokens_path.exists():
            click.echo("\n⚠️  Note : `design/tokens.yaml` n'a pas été trouvé.")
            click.echo("💡 Il est recommandé de lancer `speckit vibe-design` pour une meilleure identité visuelle.")
        
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
            "existing_code_snapshot": "",
            "llm_failures": 0,
            "fatal_error": False,
            "fatal_error_reason": ""
        }
        
        # Exécution du graphe avec circuit breaker LLM
        final_state = initial_state
        graph_iteration = 0
        try:
            for output in graph_manager.app.stream(initial_state):  # type: ignore
                graph_iteration += 1
                
                # 🛡️ CIRCUIT BREAKER : Check LLM failure threshold
                llm_failures = final_state.get("llm_failures", 0)
                if llm_failures >= MAX_LLM_FAILURES:
                    click.echo(f"\n🛑 Circuit breaker activé : {llm_failures} défaillances LLM détectées.")
                    click.echo("⛔ Arrêt immédiat du graphe.")
                    final_state["fatal_error"] = True
                    final_state["fatal_error_reason"] = f"LLM failures exceeded ({llm_failures}/{MAX_LLM_FAILURES})"
                    break
                
                # Check fatal error flag from nodes
                if final_state.get("fatal_error", False):
                    click.echo(f"\n⛔ Erreur fatale détectée : {final_state.get('fatal_error_reason', 'Raison inconnue')}")
                    break
                
                for node_name, result in output.items():
                    if result is not None:  # Defensive: ensure node returns a dict
                        final_state.update(result)
                    else:
                        logger.warning(f"⚠️ Node {node_name} returned None instead of dict")
        except Exception as graph_error:
            # Capture errors from graph execution
            error_str = str(graph_error).upper()
            click.echo(f"\n💥 Erreur critique pendant l'exécution du graphe : {graph_error}")
            
            # Check if this is an LLM-related error
            if any(kw in error_str for kw in ["RESOURCE_EXHAUSTED", "QUOTA", "429", "RATE_LIMIT"]):
                click.echo("\n⛔ RESSOURCE ÉPUISÉE - LLM API Quota dépassé")
                click.echo("💡 Attendez quelques minutes avant de réessayer.")
                final_state["fatal_error"] = True
                final_state["fatal_error_reason"] = "LLM Quota exhausted (RESOURCE_EXHAUSTED)"
                final_state["llm_failures"] = MAX_LLM_FAILURES  # Mark as critical failure
            elif any(kw in error_str for kw in ["AUTHENTICATION", "API_KEY", "401", "UNAUTHORIZED"]):
                click.echo("\n⛔ AUTHENTIFICATION ÉCHOUÉE - Clé API invalide ou expirée")
                click.echo(f"💡 Vérifiez votre clé API pour le provider: {provider}")
                final_state["fatal_error"] = True
                final_state["fatal_error_reason"] = "LLM Authentication failed"
            else:
                # Generic error
                final_state["last_error"] = str(graph_error)
                final_state["llm_failures"] = final_state.get("llm_failures", 0) + 1
        
        # 5. Ground Truth : vérification réelle sur disque avant validation finale
        gt_result = manager_etapes.mark_step_as_completed(target_id, synthesis="", project_root=".")  # type: ignore
        if isinstance(gt_result, tuple):
            _, checked_count, total_count = gt_result  # type: ignore
        else:
            checked_count, total_count = 0, 0
        
        task_complete = (checked_count == total_count) if total_count > 0 else True
        audit_approved = final_state.get("validation_status") == "APPROUVÉ"
        fatal_error = final_state.get("fatal_error", False)
        
        # 🛑 Check if run was aborted due to fatal error
        if fatal_error:
            click.echo("\n" + "!"*50)
            click.echo("🛑 EXÉCUTION INTERROMPUE (ERREUR FATALE)")
            click.echo("!"*50)
            click.echo(f"Raison : {final_state.get('fatal_error_reason', 'Raison inconnue')}")
            click.echo("!"*50 + "\n")
            return
        
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
            terminal_errors = str(final_state.get('terminal_diagnostics', ''))
            if terminal_errors and "❌ ÉCHEC" in terminal_errors:
                click.echo("\n🔍 DÉTAILS DES ERREURS TYPESCRIPT :")
                click.echo("-" * 40)
                click.echo(terminal_errors)
                click.echo("-" * 40)
                
            click.echo("!"*50 + "\n")
        
    except Exception as e:
        error_msg = str(e).upper()
        
        # 🛡️ CRITICAL ERROR HANDLING - LLM Down Detection
        if "RESOURCE_EXHAUSTED" in error_msg or "QUOTA" in error_msg:
            click.echo("\n" + "⛔"*25)
            click.echo("⛔ LLM QUOTA DÉPASSÉ - ARRÊT IMMÉDIAT")
            click.echo("⛔"*25)
            click.echo(f"Provider : {provider}")
            click.echo("Opération : Suspendre pour 24h ou changer de provider")
            click.echo("Alternatives : --provider anthropic, --provider openai, --provider deepseek")
            click.echo("⛔"*25 + "\n")
            
        elif "AUTHENTICATION" in error_msg or "API_KEY" in error_msg or "401" in error_msg:
            click.echo("\n" + "⚠️ "*25)
            click.echo("⚠️  AUTHENTIFICATION ÉCHOUÉE")
            click.echo("⚠️ "*25)
            click.echo(f"Provider : {provider}")
            click.echo("Action : Vérifiez votre clé API dans .env")
            click.echo("⚠️ "*25 + "\n")
            
        else:
            click.echo(f"\n❌ ERREUR lors de l'exécution : {e}")
            logger.exception("Détails complets de l'erreur :")
            
    finally:
        # 5. Libération du verrou (toujours exécuté, même en cas d'erreur)
        validator.release_task_lock(target_id)

if __name__ == "__main__":
    cli()
