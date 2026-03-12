# Le "Cerveau" du Spec-Kit (LE WORKFLOW DE CHAINAGE, LE PIPELINE, LE ROADMAP)
# Implémentation du graphe de routage LangGraph
# Ce module orchestre l'interaction entre les sous-agents (Analyse, Implémentation, Vérification)

import logging
from pathlib import Path
from typing import TypedDict, List
from itertools import chain
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.guard import SubagentAnalysisOutput, SubagentImplOutput, SubagentVerifyOutput, SubagentBuildFixOutput, SubagentTaskEnforcerOutput
from langchain_core.output_parsers import JsonOutputParser
from core.GraphicDesign import GraphicDesign

import shutil

# ─── Logger configuration (avant tout usage) ───
logger = logging.getLogger(__name__)

npm_path = shutil.which("npm") or shutil.which("npm.cmd")
logger.info(f"🔧 npm_path détecté : {npm_path}")

# ─── 0. Configuration des Limites ──────────────────────────────────────────────────
MAX_RETRIES = 3
MAX_DEP_INSTALL_ATTEMPTS = 3  # Limit dependency install loops
MAX_GRAPH_STEPS = 10  # 🛡️ Maximum number of graph routing decisions (prevents infinite cycles)
MAX_DEPENDENCY_CYCLES = 2  # 🛡️ Max cycles in Diagnostics → TaskEnforcer → InstallDeps loop

# ─── Packages dépréciés que le LLM hallucine souvent ───
DEPRECATED_PACKAGES = {
    "@testing-library/react-hooks": "@testing-library/react",  # Déprécié depuis 2020
    "react-test-utils": "@testing-library/react",              # Ancien pattern
    "react-dom/test-utils": "@testing-library/react"           # Ancien pattern
}

# ─── 1. État du graphe (ou StateGraph/Mémoire partagée) ─────────────────────────────

class AgentState(TypedDict):
    # Variables de contexte partagées (générées une seule fois)
    constitution_hash: str
    constitution_content: str

    current_step: str
    completed_tasks_summary: str
    pending_tasks: str
    
    # Spécifications de design (Générées par GraphicDesign)
    design_spec: dict
    
    # Cible actuelle
    target_task: str
    target_module: str  # Module cible extrait du task ID (backend/frontend/mobile/None)
    
    # Résultats des nœuds
    analysis_output: str
    code_to_verify: str
    impact_fichiers: List[str] # Liste des fichiers impactés
    validation_status: str # "APPROUVÉ" ou "REJETÉ"
    score: str # Score de l'auditeur
    points_forts: str # Points forts relevés
    alertes: str # Alertes détectées
    feedback_correction: str # Instructions si rejeté
    terminal_diagnostics: str # Erreurs réelles du terminal (build, lint, etc.)
    existing_code_snapshot: str # Fichiers réels lus depuis le disque (pour le mode PATCH)
    
    # Gestion des erreurs et boucle
    error_count: int 
    last_error: str
    audit_errors_history: List[str]  # 🛡️ Historique des erreurs d'audit pour détecter les répétitions
    
    # Instructions utilisateur additionnelles (Ex: speckit run --instruction "Fais ceci")
    user_instruction: str
    
    # Carte sémantique du code (Semantic Code Map)
    code_map: str
    file_tree: str
    
    # Checklist des sous-tâches
    subtask_checklist: str
    
    # Modules manquants détectés par les diagnostics (Auto-installation)
    missing_modules: List[str]
    deps_attempts: int
    
    # Erreurs détectées dans les modules non-cibles (pour éviter boucles)
    non_target_errors: dict  # {module_name: error_type}
    
    # Statistiques de complétion (via TaskEnforcer)
    total_subtasks: int
    missing_subtasks: int


class SpecGraphManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root).resolve()
        # Les prompts sont internes au package
        self.prompts_dir = Path(__file__).parent.parent / "agents"
        
        # Initialisation du graphe
        self.graph_builder = StateGraph(AgentState)
        self._build_graph()

    def _ensure_directory_structure(self):
        """Garantit l'existence de l'arborescence standard du projet."""
        folders = [
            "backend/src/routes",
            "backend/src/controllers",
            "backend/src/models",
            "backend/src/middlewares",
            "backend/src/services",
            "frontend/src/components",
            "frontend/src/hooks",
            "frontend/src/services",
            "frontend/src/views"
        ]
        count = 0
        for folder in folders:
            p = self.root / folder
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                count += 1
        if count > 0:
            logger.info(f"📁 Structure de dossiers garantie ({count} dossiers créés).")

    def _extract_target_module(self, task_id: str) -> str:
        """Extrait le module cible (backend/frontend/mobile) du task ID.
        
        Exemples:
        - "02_setup_backend" → "backend"
        - "03_setup_frontend" → "frontend"
        - "04_setup_mobile" → "mobile"
        - "05_feature_dashboard" → None (utilise tous les modules)
        """
        import re
        # Pattern: 02_setup_backend, 03_setup_frontend, etc.
        match = re.search(r"_(backend|frontend|mobile|api|infra|docs)", task_id, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        
        # Fallback: stratégie heuristique basée sur le numéro
        # 01-02 = backend, 03-04 = frontend, etc.
        match = re.match(r"(\d+)", task_id)
        if match:
            step_num = int(match.group(1))
            if step_num <= 2:
                return "backend"
            elif step_num <= 4:
                return "frontend"
        
        # Default: None (tous les modules)
        return None

    def _get_build_tool(self, target_module: str) -> str:
        """Détecte le bon outil de build selon le module et framework.
        
        Returns: "next", "vite", or "tsc"
        """
        if target_module == "frontend":
            # Check for Next.js first
            if ((self.root / "frontend" / "next.config.ts").exists() or 
                (self.root / "frontend" / "next.config.js").exists()):
                return "next"
            
            # Check for Vite (React or Vue)
            if (self.root / "frontend" / "vite.config.ts").exists():
                return "vite"
            
            # Fallback
            return "tsc"
        
        # Default: TypeScript
        return "tsc"
    
    def _detect_frontend_framework(self) -> str:
        """Détecte le framework frontend: 'react', 'vue', ou 'next'.
        
        Utilise la FileManager pour cohérence.
        """
        from utils.file_manager import FileManager
        fm = FileManager(str(self.root))
        return fm.detect_framework()
        return "tsc"

    def _get_nextjs_router_type(self) -> str:
        """Détecte le type de router Next.js: 'app' (App Router) ou 'pages' (Pages Router).
        
        Returns: 'app', 'pages', ou 'unknown'
        """
        frontend_dir = self.root / "frontend"
        
        # Next.js 13+ App Router utilise app/ directory
        if (frontend_dir / "app").exists():
            return "app"
        
        # Pages Router utilise pages/ directory
        if (frontend_dir / "pages").exists():
            return "pages"
        
        return "unknown"

    def _detect_cross_module_deps(self, target_module: str, pkg_path: Path) -> dict:
        """Détecte les dépendances cross-module (ex: frontend dépend du backend).
        
        Retourne: {"missing_module": "backend", "reason": "imports de services/auth"}
        """
        import json
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        except Exception:
            return {}
        
        # Pattern des libs de cross-module
        # Frontend qui importe des services backend
        if target_module == "frontend":
            # Chercher des indicateurs d'import backend
            if any(lib in all_deps for lib in ["@backend/shared", "@backend/models", "@backend/services", "backend-api"]):
                return {"missing_module": "backend", "reason": "Frontend dépend de services/modèles Backend"}
        
        # Backend qui importe du frontend (moins courant mais possible)
        if target_module == "backend":
            if any(lib in all_deps for lib in ["@frontend/shared", "@frontend/types", "frontend-types"]):
                return {"missing_module": "frontend", "reason": "Backend dépend de types Frontend"}
        
        return {}

    def _add_cross_module_task(self, target_module: str, missing_module: str, reason: str) -> None:
        """Ajoute une tâche manquante à l'étape concernée dans etapes.md.
        
        Stratégie:
        - Si on est en frontend et il manque du backend:
          Décocher la subtâche backend et ajouter une tâche à l'étape backend
        """
        from core.etapes import EtapeManager
        
        etape_mgr = EtapeManager(self.root)
        
        # Déterminer l'étape concernée
        step_map = {"backend": "02", "frontend": "03", "mobile": "04"}
        step_num = step_map.get(missing_module, "02")
        
        try:
            # Ajouter une nouvelle tâche non-cochée à l'étape concernée
            msg = f"[Cross-Module] {reason} (détecté depuis {target_module})"
            logger.warning(f"⚠️ Dépendance cross-module détectée: {msg}")
            logger.info(f"💡 Ajoute une tâche à l'étape {step_num} : Installer {missing_module}")
            
            # Lire etapes.md
            etapes_file = self.root / "Constitution" / "etapes.md"
            if etapes_file.exists():
                content = etapes_file.read_text(encoding="utf-8")
                
                # Injecter la tâche manquante dans l'étape concernée
                import re
                pattern = f"(## Étape {step_num}.*?)(?=## Étape|$)"
                
                def inject_task(match):
                    section = match.group(1)
                    # Ajouter la tâche avant la fin de la section
                    task_line = f"\n- [ ] [Cross-Module] {reason}"
                    return section + task_line
                
                new_content = re.sub(pattern, inject_task, content, flags=re.DOTALL)
                etapes_file.write_text(new_content, encoding="utf-8")
                logger.info(f"✅ Tâche ajoutée à etapes.md (Étape {step_num})")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'ajouter la tâche cross-module : {e}")

    def _invoke_with_retry(self, chain, invoke_dict: dict, max_attempts: int = 3):
        """🛡️ Appelle la chaîne LLM avec retry + exponential backoff pour éviter les erreurs réseau.
        
        Args:
            chain: La chaîne LangChain à invoquer
            invoke_dict: Variables à passer à la chaîne
            max_attempts: Nombre maximum de tentatives (default: 3)
            
        Returns:
            La sortie brute de chain.invoke()
            
        Raises:
            Exception: Si toutes les tentatives échouent
        """
        import time
        for attempt in range(max_attempts):
            try:
                logger.info(f"🔄 Invocation LLM (tentative {attempt + 1}/{max_attempts})...")
                result = chain.invoke(invoke_dict)
                logger.info(f"✅ Invocation réussie à la tentative {attempt + 1}")
                return result
            except Exception as e:
                if attempt < max_attempts - 1:
                    # Backoff exponentiel : 1s, 2s, 4s, etc.
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ Tentative {attempt + 1} échouée : {str(e)[:100]}. Attente {wait_time}s avant retry...")
                    time.sleep(wait_time)
                else:
                    # Dernière tentative échouée
                    logger.error(f"❌ Toutes les {max_attempts} tentatives ont échoué.")
                    raise

    def _load_prompt(self, filename: str) -> str:
        """Charge le contenu d'un fichier prompt."""
        path = self.prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Prompt introuvable : {path}")
        return path.read_text(encoding="utf-8")

    def _safe_parse_json(self, content: str, pydantic_object) -> dict:
        """Nettoie et parse le JSON avec des fallbacks robustes pour les grands volumes de code."""
        cleaned = content.strip()
        result = {}
        
        # --- EXTRACTION DU CODE MARKDOWN (MULTI-FORMAT) ---
        import re
        
        # 1. Priorité : bloc ```code (format demandé dans le prompt)
        # Fix Regex: eviter catastropic backtracking en retirant \s* avant .*?
        code_blocks = re.findall(r"```code\n?(.*?)\n?```", cleaned, re.DOTALL)
        
        # 2. Fallback : TOUS les blocs fenced sauf ```json (car c'est le JSON d'analyse)
        if not code_blocks:
            # On capture tous les blocs ``` qui ne sont PAS du JSON d'analyse
            all_blocks = re.findall(r"```(?!json\b)(\w*)\n?(.*?)\n?```", cleaned, re.DOTALL)
            code_blocks = []
            for lang, content in all_blocks:
                content = content.strip()
                # On ne garde que les blocs qui contiennent des marqueurs de fichiers
                if any(marker in content for marker in ['// Fichier', '// [DEBUT_FICHIER', '# Fichier', 'import ', 'export ', 'const ', 'function ', '"name":', '"dependencies":']):
                    code_blocks.append(content)
        
        if not code_blocks:
            result["code"] = ""
        else:
            result["code"] = "\n\n".join(code_blocks)
                
        # --- EXTRACTION DU JSON ---
        # 1. Priorité : Balises <JSON_OUTPUT> (Format standardisé)
        json_match = re.search(r"<JSON_OUTPUT>\n?(.*?)\n?</JSON_OUTPUT>", cleaned, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
        else:
            # 2. Nettoyage des backticks Markdown (```json ... ```)
            json_content = cleaned
            if "```json" in json_content:
                match = re.search(r"```json\n?(.*?)\n?```", json_content, re.DOTALL)
                if match:
                    json_content = match.group(1).strip()
                else:
                    json_content = re.sub(r"^```json\s*", "", json_content)
            elif "```" in json_content:
                 # S'il y a un bloc ``` générique au début, on assume que c'est le json
                 match = re.search(r"^```\n?(\{.*?\})\n?```", json_content, re.DOTALL)
                 if match:
                     json_content = match.group(1).strip()
            
            # On essaie d'isoler uniquement la partie dictionnaire { ... } si d'autres choses trainent
            match_dict = re.search(r"(\{.*\})", json_content, re.DOTALL)
            if match_dict:
                json_content = match_dict.group(1)
        
        # 2. Parsing via LangChain JsonOutputParser
        parser = JsonOutputParser(pydantic_object=pydantic_object)
        try:
            parsed_json = parser.parse(json_content)
            result.update(parsed_json)
            # Si le code était dans le JSON malencontreusement (ancien format), on le prend
            if not result.get("code") and parsed_json.get("code"):
                 result["code"] = parsed_json.get("code")
            
            # Nettoyage final des backticks résiduels dans le code extrait
            if result.get("code"):
                result["code"] = re.sub(r'```[a-zA-Z0-9-]*\n?', '', result["code"])
                result["code"] = result["code"].replace('```', '').strip()
                
            return result
        except Exception as e:
            logger.error(f"❌ Échec critique du parsing JSON : {str(e)}")
            # On renvoie une erreur explicite pour que le noeud appelant puisse réagir
            raise ValueError(f"Format JSON invalide ou absent dans la réponse de l'IA : {str(e)}")

    # ─── 2. Nœuds (fonctions de traitement) ───────────────────────────────

    def GraphicDesign_node(self, state: AgentState) -> dict:
        """Nœud de Design : Transforme l'intention UI en AST + Specs Tailwind."""
        logger.info(f"🎨 Début du Design pour la tâche : {state['target_task']}")
        
        # Initialisation du moteur Design
        design_engine = GraphicDesign(
            dataset_dir=str(self.root / "design" / "dataset"),
            constitution_path=str(self.root / "design" / "constitution_design.yaml")
        )
        
        # On utilise le prompt utilisateur ou la tâche cible pour le design
        prompt = state.get("user_instruction") or state["target_task"]
        
        # 🛡️ MANDATORY CHECK: Only run for frontend/UI related tasks
        target_module = state.get("target_module")
        is_ui_task = target_module == "frontend"
        
        if not is_ui_task:
            logger.info("ℹ️ GraphicDesign skipped: Not a UI/Frontend task.")
            return {"design_spec": {"error": "Skipped (non-UI)", "tailwind": {}}}

        try:
            design_result = design_engine.generate(prompt)
            # Ensure tailwind rules are always present even if empty
            if "tailwind" not in design_result:
                design_result["tailwind"] = {}
            
            # 🖼️ NEW: Generate a framework-specific Skeleton "mould"
            skeleton = design_engine.generate_skeleton(design_result)
            design_result["skeleton"] = skeleton
                
            logger.info(f"✅ Design generated: {design_result.get('pattern', 'default')} with Skeleton.")
            return {"design_spec": design_result}
        except Exception as e:
            logger.error(f"❌ Échec du moteur GraphicDesign : {str(e)}")
            # Fallback minimaliste
            return {"design_spec": {"error": str(e), "tailwind": {}}}

    def analysis_node(self, state: AgentState) -> dict:
        """Nœud 1 : Analyse de conformité et segmentation."""
        logger.info(f"🔍 Début de l'Analyse pour la tâche : {state['target_task']}")
        
        # ─── EXTRACTION DU MODULE CIBLE ───
        target_module = self._extract_target_module(state["target_task"])
        if target_module:
            logger.info(f"📍 Module cible identifié : {target_module}")
        
        prompt_text = self._load_prompt("subagent_analysis.prompt")
        
        # On utilise JsonOutputParser avec le modèle Pydantic de guard.py
        parser = JsonOutputParser(pydantic_object=SubagentAnalysisOutput)
        
        # Injection des instructions Pydantic dans le prompt
        prompt_text += "\n\n{format_instructions}"
        prompt = ChatPromptTemplate.from_template(prompt_text)
        
        chain = prompt | self.model | StrOutputParser()
        
        try:
            import concurrent.futures
            
            def run_chain():
                return self._invoke_with_retry(chain, {
                    "constitution_content": state["constitution_content"],
                    "current_step": state["current_step"],
                    "completed_tasks_summary": state["completed_tasks_summary"],
                    "pending_tasks": state["pending_tasks"],
                    "target_task": state["target_task"],
                    "user_instruction": state.get("user_instruction", ""),
                    "format_instructions": parser.get_format_instructions()
                })

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_chain)
                # Hard timeout de 90 secondes sur l'appel LLM
                raw_output = future.result(timeout=90)

            result = self._safe_parse_json(raw_output, SubagentAnalysisOutput)
            # On convertit le dict JSON en string formatée pour l'injecter au noeud suivant
            analysis_str = (
                f"Impact: {result['impact']}\n"
                f"Conflits: {result['conflits']}\n"
                f"Segmentation: {', '.join(result['segmentation'])}\n"
                f"Intégrité: {result['alerte_integrite']}"
            )
            logger.info("✅ Analyse terminée.")
            return {
                "analysis_output": analysis_str,
                "feedback_correction": "",
                "error_count": 0,
                "audit_errors_history": [],  # 🛡️ Initialize error tracking
                "target_module": target_module  # Passer le module cible au graphe
            }
        except ValueError as e:
            error_msg = f"Réponse IA corrompue (Analysis JSON) : {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "validation_status": "REJETÉ",
                "feedback_correction": f"CRITICAL: Analysis response was invalid JSON. {str(e)}. Please retry with valid JSON.",
                "last_error": error_msg
            }
        except Exception as e:
            error_msg = f"Erreur d'analyse : {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "analysis_output": "ERREUR D'ANALYSE", 
                "feedback_correction": error_msg,
                "last_error": error_msg
            }

    def _read_existing_code(self) -> str:
        """Lit les fichiers réels du projet sur disque pour le mode PATCH."""
        import os
        blocks = []
        extensions = ('.ts', '.tsx', '.js', '.jsx', '.json')
        ignore_dirs = {'node_modules', 'dist', '.git', '__pycache__', '.speckit'}
        
        for root_dir, dirs, files in os.walk(str(self.root)):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for f in files:
                if f.endswith(extensions):
                    abs_path = os.path.join(root_dir, f)
                    rel_path = os.path.relpath(abs_path, str(self.root)).replace('\\', '/')
                    try:
                        content = open(abs_path, 'r', encoding='utf-8').read()
                        blocks.append(f"// Fichier : {rel_path}\n{content}")
                    except Exception:
                        pass
        
        snapshot = "\n\n".join(blocks)
        logger.info(f"📸 Snapshot disque : {len(blocks)} fichiers lus.")
        return snapshot

    def _get_filtered_context(self, state: AgentState) -> dict:
        """Filtre le code_map et file_tree pour réduire le contexte LLM.
        
        Stratégie de réduction:
        - Extraire SEULEMENT les fichiers pertinents pour la tâche cible
        - Inclure les dépendances détectées  
        - Limiter à ~30-40 fichiers max
        - Idéal pour réduire du contexte 50-70% sans perdre de sémantique
        
        Le contexte réduit reste suffisant pour la génération avec la semantic map.
        """
        import json, re
        
        # Extraire les fichiers et contextes pertinents
        analysis = state.get("analysis_output", "")
        code_map_str = state.get("code_map", "{}")
        file_tree_str = state.get("file_tree", "")
        target_task = state.get("target_task", "")
        
        relevant_files = set()
        
        # 1️⃣ EXTRACTION AGRESSIVE des fichiers mentionnés dans analysis
        # Patterns: "fichier: X", "create X", import statements, etc.
        file_patterns = [
            r'(?:files?|fichiers?|path|chemin|import|from)\s*:?\s+["\']?([a-zA-Z0-9._\-/\\]+\.[a-zA-Z0-9]+)["\']?',
            r'(?:create|créer|modify|modifier|update)\s+([a-zA-Z0-9._\-/\\]+\.[a-zA-Z0-9]+)',
            r'(?:api|route|endpoint|endpoint_|controller|Controller|service|Service)\s*:\s*([a-zA-Z0-9._\-/\\]+\.[a-zA-Z0-9]+)',
        ]
        for pattern in file_patterns:
            matches = re.findall(pattern, analysis, re.IGNORECASE)
            relevant_files.update(m.strip() for m in matches if m)
        
        # 2️⃣ EXTRACTION des keywords de la tâche
        task_words = re.findall(r'\b([a-z]{3,}(?:_[a-z]+)*)\b', target_task.lower())
        task_words = list(set(task_words))  # Dédupliquer
        
        # 3️⃣ MATCHING des fichiers basés sur tâche
        # Ex: si tâche ="create_user_form", chercher user, form, User, Form
        for keyword in task_words:
            for line in file_tree_str.split('\n'):
                file_line = line.strip().lower()
                if file_line and (keyword in file_line or file_line.startswith(keyword)):
                    relevant_files.add(line.strip())
        
        # 4️⃣ FICHIERS DE CONFIG obligatoires
        config_patterns = [
            'package.json', 'tsconfig', 'index.ts', 'index.tsx', 'index.js', 
            'env', 'types.ts', 'interfaces', '.ts'  # Fichier de types général
        ]
        for line in file_tree_str.split('\n'):
            if line.strip():
                for config in config_patterns:
                    if config.lower() in line.lower():
                        relevant_files.add(line.strip())
                        break
        
        # 5️⃣ PARSER code_map et FILTRER
        try:
            code_map_dict = json.loads(code_map_str) if code_map_str and code_map_str != "{}" else {}
        except:
            code_map_dict = {}
        
        filtered_code_map = {}
        
        # Inclure fichiers qui match any relevant criterion
        for file_path in code_map_dict.keys():
            # Critère 1: Explicitement mentionné dans analysis
            if file_path in relevant_files or any(rp in file_path for rp in relevant_files):
                filtered_code_map[file_path] = code_map_dict[file_path]
                continue
            
            # Critère 2: Contient un keyword de tâche
            if any(kw in file_path.lower() for kw in task_words):
                filtered_code_map[file_path] = code_map_dict[file_path]
                continue
            
            # Critère 3: Est un fichier de config/index important
            if any(config.lower() in file_path.lower() for config in config_patterns):
                filtered_code_map[file_path] = code_map_dict[file_path]
                continue
        
        # Fallback: si RIEN n'est trouvé relevé, inclure les premiers fichiers pertinents
        if not filtered_code_map and code_map_dict:
            # Prioriser les fichiers mentionnés dans analysis ou contenant keywords
            priority_files = [f for f in code_map_dict.keys() 
                            if any(kw in f.lower() for kw in task_words)]
            if not priority_files:
                # Aucune priorité trouvée, prendre les premiers
                priority_files = list(code_map_dict.keys())[:15]
            
            for f in priority_files[:25]:  # Max 25 fichiers en fallback
                filtered_code_map[f] = code_map_dict[f]
        
        # 6️⃣ LIMITER STRICTEMENT la taille: max 35 fichiers
        if len(filtered_code_map) > 35:
            # Garder les plus pertinents (avec keywords de tâche en priorité)
            priority = sorted(filtered_code_map.keys(), 
                            key=lambda f: sum(1 for kw in task_words if kw in f.lower()),
                            reverse=True)
            filtered_code_map = {f: code_map_dict[f] for f in priority[:35]}
        
        # 7️⃣ FILTRER file_tree pour correspondre
        filtered_file_tree = []
        for line in file_tree_str.split('\n'):
            if not line.strip():
                continue
            # Inclure si: dans filtered_code_map ou dans relevant_files
            if any(fp in line for fp in filtered_code_map.keys()) or \
               any(rf in line for rf in relevant_files) or \
               any(kw.lower() in line.lower() for kw in task_words) or \
               any(cfg.lower() in line.lower() for cfg in config_patterns):
                filtered_file_tree.append(line.strip())
        
        # Limite stricte sur file_tree aussi
        if len(filtered_file_tree) > 40:
            filtered_file_tree = filtered_file_tree[:40]
        
        logger.info(f"📊 Context Filtering: {len(code_map_dict)} → {len(filtered_code_map)} files in code_map, " +
                   f"file_tree: ~{len(file_tree_str.split(chr(10)))} → {len(filtered_file_tree)} lines | " +
                   f"Task keywords: {task_words[:3]}")  # Log first 3 keywords
        
        return {
            "code_map_filtered": json.dumps(filtered_code_map),
            "file_tree_filtered": "\n".join(filtered_file_tree)
        }

    def _format_design_spec_for_prompt(self, design_spec: dict) -> str:
        """Formate le design_spec en instructions lisibles pour le LLM.
        
        Transforme un design_spec JSON complexe en directives claires et actionnables.
        """
        if not design_spec or "error" in design_spec:
            return "NO DESIGN SPECIFICATION PROVIDED. Use standard Tailwind defaults."
        
        pattern = design_spec.get("pattern", "N/A")
        tailwind = design_spec.get("tailwind", {})
        ui_ast = design_spec.get("ui_ast", {})
        
        tailwind_rules = ""
        if isinstance(tailwind, dict):
            for k, v in tailwind.items():
                tailwind_rules += f"- **{k}**: `{v}`\n"
        
        skeleton = design_spec.get("skeleton", "")
        
        # Build readability-first instructions for the LLM
        instructions = f"""
# 🎨 MANDATORY UI DESIGN SYSTEM (TAILWIND)

Use the following Tailwind classes for the UI. DO NOT USE ANY OTHER CLASSES.

## Pattern: {pattern}

{tailwind_rules}

## Structural Constraints:
- Layout: {ui_ast.get('name', 'Page') if isinstance(ui_ast, dict) else 'Page'}
- Component hierarchy: {str(ui_ast)[:300]}

## 🧱 THE SKELETON (CRITICAL):
YOU MUST START FROM THIS SKELETON. Do not generate a new layout structure.
FILL the placeholders but DO NOT REMOVE the styling classes. Total fidelity is required.

```tsx
{skeleton}
```

## CRITICAL RULES:
1. Every HTML element MUST use the classes defined above.
2. For buttons, use `{tailwind.get('primary', 'bg-blue-600 text-white') if isinstance(tailwind, dict) else 'bg-blue-600 text-white'}`.
3. For cards/containers, use `{tailwind.get('container', 'p-6 bg-white shadow-md') if isinstance(tailwind, dict) else 'p-6 bg-white shadow-md'}`.
4. Total fidelity to this design system is required.
"""
        return instructions


    def impl_node(self, state: AgentState) -> dict:
        """Nœud 2 : Génération de code pur (Exécutant)."""
        logger.info(f"💻 Début de la Génération de code pour la tâche : {state['target_task']}")
        
        # Garantie structurelle avant génération
        self._ensure_directory_structure()
        
        prompt_text = self._load_prompt("subagent_impl.prompt")
        
        # ─── MODE PATCH : Sur les retries, injecter le code réel du disque ───
        is_patch_mode = bool(state.get("feedback_correction"))
        existing_snapshot = ""
        
        if is_patch_mode:
            logger.warning("🔧 MODE PATCH : Lecture du code réel depuis le disque.")
            existing_snapshot = self._read_existing_code()
            prompt_text += "\n\n# ⚠️ INSTRUCTIONS DE CORRECTION (RETOUR AUDITEUR) :\n{feedback_correction}"
            prompt_text += "\n\n# 📂 CODE EXISTANT SUR DISQUE (NE PAS TOUT RÉGÉNÉRER) :\n{existing_code_snapshot}"
            prompt_text += "\n\n# MODE: PATCH — Modifie UNIQUEMENT les fichiers concernés par les erreurs ci-dessus. Ne régénère PAS les fichiers qui fonctionnent."
        
        parser = JsonOutputParser(pydantic_object=SubagentImplOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            # 🛡️ FILRAGE DE CONTEXTE : Réduire la taille avant d'envoyer au LLM
            filtered = self._get_filtered_context(state)
            code_map_to_use = filtered.get("code_map_filtered", state.get("code_map", ""))
            file_tree_to_use = filtered.get("file_tree_filtered", state.get("file_tree", ""))
            
            # 🛡️ CONSTITUTION: JAMAIS TRONQUER - C'est la source de vérité !
            constitution_content = state["constitution_content"]  # ← ALWAYS COMPLETE AND FULL
            
            # 🛡️ TRUNCATION DE existing_code_snapshot si > 10KB (PATCH mode SEULEMENT)
            if len(existing_snapshot) > 10000:
                existing_snapshot = existing_snapshot[:9800] + "\n// [... CODE TRUNCATED FOR CONTEXT LIMIT ...]"
                logger.warning(f"⚠️ Existing snapshot truncated from {len(state.get('existing_code_snapshot', ''))} to 9800 chars")
            
            # 🛡️ TRUNCATION DE analysis_output si > 5KB (can summarize, not critical)
            analysis_output = state.get("analysis_output", "")
            if len(analysis_output) > 5000:
                analysis_output = analysis_output[:4800] + "\n[... ANALYSIS TRUNCATED FOR CONTEXT LIMIT ...]"
                logger.warning(f"⚠️ Analysis output truncated to 4800 chars")
            
            # 🛡️ TRUNCATION DE terminal_diagnostics si > 3KB (can summarize)
            terminal_diagnostics = state.get("terminal_diagnostics", "")
            if len(terminal_diagnostics) > 3000:
                terminal_diagnostics = terminal_diagnostics[:2800] + "\n[... DIAGNOSTICS TRUNCATED ...]"
                logger.info(f"ℹ️ Terminal diagnostics truncated to 2800 chars")
            
            # 🎨 FORMAT DESIGN SPEC : Rendre lisible et actionnabel pour le LLM
            raw_design_spec = state.get("design_spec", {"error": "Non générée"})
            design_spec_formatted = self._format_design_spec_for_prompt(raw_design_spec)
            if raw_design_spec.get("pattern"):
                logger.info(f"🎨 Design pattern ready: {raw_design_spec['pattern']} (with Tailwind + AST)")
            else:
                logger.warning(f"⚠️ No design pattern found - using defaults")

            # 🛡️ RETRY avec backoff pour éviter les erreurs réseau
            invoke_dict = {
                "constitution_hash": state.get("constitution_hash", "INCONNU"),
                "constitution_content": constitution_content,  # ← ALWAYS COMPLETE (never truncated)
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "target_task": state["target_task"],
                "analysis_output": analysis_output,  # ← May be truncated (non-critical)
                "feedback_correction": state.get("feedback_correction", ""),
                "terminal_diagnostics": terminal_diagnostics,  # ← May be truncated (diagnostic only)
                "code_map": code_map_to_use,  # ← Filtered by _get_filtered_context()
                "file_tree": file_tree_to_use,  # ← Filtered by _get_filtered_context()
                "design_spec": design_spec_formatted,  # 🎨 ← NOW formatted and readable for LLM
                "subtask_checklist": state.get("subtask_checklist", "Non disponible"),
                "user_instruction": state.get("user_instruction", ""),
                "existing_code_snapshot": existing_snapshot,  # ← May be truncated (PATCH mode only)
                "format_instructions": parser.get_format_instructions()
            }
            
            raw_output = self._invoke_with_retry(chain, invoke_dict, max_attempts=3)

            result = self._safe_parse_json(raw_output, SubagentImplOutput)
            new_code = result.get("code", "")
            
            # En PATCH mode, merger avec le code existant au lieu de remplacer
            if is_patch_mode and state.get("code_to_verify"):
                new_code = self._merge_code(state["code_to_verify"], new_code)
                logger.info("✅ PATCH appliqué (merge avec le code existant).")
            else:
                logger.info("✅ Génération de code terminée.")
            
            return {
                "code_to_verify": new_code,
                "impact_fichiers": result.get("impact_fichiers", []),
                "existing_code_snapshot": existing_snapshot,
                "last_error": "",
                "validation_status": "GENERATED"
            }
        except Exception as e:
            error_msg = f"Erreur de génération : {str(e)}"
            logger.error(f"❌ {error_msg}")
            new_error_count = state.get("error_count", 0) + 1
            return {
                "validation_status": "REJETÉ",
                "feedback_correction": f"Technical error during generation: {str(e)}. Please retry.",
                "error_count": new_error_count,
                "last_error": error_msg
            }

    def path_guard_node(self, state: AgentState) -> dict:
        """Nœud : Garde protectrice pour la normalisation et validation des chemins.
        
        Objectifs:
        - Normaliser tous les chemins AVANT la persistance
        - Bloquer les chemins non sûrs (traversal, caractères invalides)
        - Signaler les anomalies détectées
        - Defense-in-depth: Double vérification avant write
        
        Ce nœud insert une couche de défense entre generation et persist.
        """
        import re
        from utils.file_manager import FileManager
        
        logger.info("🛡️ PathGuard: Validating and normalizing all paths...")
        
        code = state.get("code_to_verify", "")
        if not code:
            logger.debug("✓ No code to validate (empty)")
            return {"path_guard_status": "EMPTY"}
        
        # Instancier FileManager pour accéder aux méthodes de validation
        fm = FileManager(self.root)
        
        # Extraire tous les chemins du code
        file_pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        file_blocks = re.split(file_pattern, code)
        
        path_issues = []
        normalized_code = code
        
        if len(file_blocks) > 1:
            for i in range(1, len(file_blocks), 2):
                original_path = file_blocks[i].strip()
                
                logger.info(f"🔍 Validating path: {original_path}")
                
                try:
                    # SÉCURITÉ 1 : Détecter les chemins non sûrs
                    if ".." in original_path:
                        logger.error(f"🛑 Directory traversal detected: {original_path}")
                        path_issues.append({
                            "path": original_path,
                            "issue": "Directory traversal (..) detected",
                            "severity": "CRITICAL"
                        })
                        continue
                    
                    if original_path.startswith('/') or ':' in original_path:
                        logger.error(f"🛑 Absolute path detected: {original_path}")
                        path_issues.append({
                            "path": original_path,
                            "issue": "Absolute path (not allowed)",
                            "severity": "CRITICAL"
                        })
                        continue
                    
                    # SÉCURITÉ 2 : Normaliser le chemin
                    try:
                        normalized_path = fm.normalize_path(original_path)
                        logger.info(f"  ✅ Path normalized: {original_path} → {normalized_path}")
                        
                        # SÉCURITÉ 3 : Valider le chemin normalisé
                        if ".." in normalized_path or not normalized_path.startswith(('frontend/', 'backend/', 'mobile/')):
                            logger.error(f"🛑 Normalized path fails validation: {normalized_path}")
                            path_issues.append({
                                "path": original_path,
                                "normalized": normalized_path,
                                "issue": "Normalized path failed validation",
                                "severity": "CRITICAL"
                            })
                        else:
                            logger.debug(f"  ✓ Path validation passed")
                        
                        # Mettre à jour le code avec le chemin normalisé
                        if normalized_path != original_path:
                            # Note: In real scenario, we would update the code
                            # For now, we just track it
                            pass
                            
                    except ValueError as e:
                        logger.warning(f"⚠️ Path normalization failed: {e}")
                        path_issues.append({
                            "path": original_path,
                            "issue": str(e),
                            "severity": "WARNING"
                        })
                
                except Exception as e:
                    logger.error(f"❌ Unexpected error validating path {original_path}: {e}")
                    path_issues.append({
                        "path": original_path,
                        "issue": f"Validation error: {e}",
                        "severity": "ERROR"
                    })
        
        # RÉSUMÉ
        critical_issues = [p for p in path_issues if p.get("severity") == "CRITICAL"]
        warning_issues = [p for p in path_issues if p.get("severity") in ["WARNING", "ERROR"]]
        
        if critical_issues:
            logger.error(f"🛑 PathGuard: {len(critical_issues)} critical issue(s) detected")
            status = "BLOCKED"
        elif warning_issues:
            logger.warning(f"⚠️ PathGuard: {len(warning_issues)} warning(s) detected")
            status = "WARNED"
        else:
            logger.info(f"✅ PathGuard: All paths validated successfully")
            status = "PASSED"
        
        return {
            "path_guard_status": status,
            "path_guard_issues": path_issues,
            "validation_status": "PATH_BLOCKED" if status == "BLOCKED" else "PATH_VALIDATED"
        }

    def persist_node(self, state: AgentState) -> dict:
        """Nœud : Persistance du code sur le disque + Assurance des artefacts obligatoires.
        
        Inclut le diff tracking pour visibilité des changements.
        """
        from utils.file_manager import FileManager
        
        logger.info("💾 Persistance des fichiers sur le disque...")
        code = state.get("code_to_verify", "")
        if not code:
            state["validation_status"] = "EMPTY_CODE"
            return state
        
        # Snapshot AVANT
        fm = FileManager(self.root)
        snapshot_before = fm.snapshot_project_state("before_persist")
        logger.info(f"📸 Project snapshot before: {snapshot_before['file_count']} files, {snapshot_before['total_size']} bytes")
        
        # Persistence
        sanitized_code, written_paths = self._persist_code_to_disk(code)
        logger.info(f"✅ {len(written_paths)} fichiers écrits.")
        
        # ─── ASSURER LES ARTEFACTS OBLIGATOIRES ───
        # Extraire et créer tout fichier manquant listés dans la checklist
        required_files = self._extract_required_files(state.get("subtask_checklist", ""))
        missing_files = self._ensure_required_artifacts(required_files, written_paths)
        
        if missing_files:
            logger.warning(f"⚠️ Fichiers obligatoires manquants créés : {missing_files}")
            written_paths.extend(missing_files)
        
        # Snapshot APRÈS
        snapshot_after = fm.snapshot_project_state("after_persist")
        logger.info(f"📸 Project snapshot after: {snapshot_after['file_count']} files, {snapshot_after['total_size']} bytes")
        
        # Diff des snapshots
        file_diff = fm.diff_snapshots(snapshot_before, snapshot_after)
        logger.info(f"📊 File persistence diff: {file_diff['summary']}")
        
        return {
            "code_to_verify": sanitized_code,
            "impact_fichiers": list(set(state.get("impact_fichiers", []) + written_paths)),
            "validation_status": "PERSISTED",
            "snapshot_before": snapshot_before,
            "snapshot_after": snapshot_after,
            "file_diff": file_diff
        }

    def typescript_validate_node(self, state: AgentState) -> dict:
        """Nœud : Validation TypeScript des fichiers générés (phase post-persist).
        
        Objectifs:
        - Déterminer si le code TypeScript/JavaScript est syntaxiquement valide
        - Capturer les erreurs de compilation avant le pipeline de correction
        - Signaler les dépendances manquantes détectées
        """
        import subprocess
        import re
        
        logger.info("📝 TypeScript Validation (post-persist)...")
        
        written_paths = state.get("impact_fichiers", [])
        if not written_paths:
            logger.debug("✓ No files written, skipping TypeScript validation")
            return {"typescript_errors": [], "typescript_validation_status": "SKIPPED"}
        
        # Déterminer les modules cibles à valider
        modules_to_check = set()
        for path in written_paths:
            if path.startswith('frontend/'):
                modules_to_check.add('frontend')
            elif path.startswith('backend/'):
                modules_to_check.add('backend')
        
        if not modules_to_check:
            logger.debug("✓ No frontend/backend modules detected in written files")
            return {"typescript_errors": [], "typescript_validation_status": "NO_MODULES"}
        
        typescript_errors = []
        
        for module in modules_to_check:
            module_path = self.root / module
            tsconfig_path = module_path / "tsconfig.json"
            
            if not tsconfig_path.exists():
                logger.debug(f"⚠️ No tsconfig.json found in {module}, skipping validation")
                continue
            
            logger.info(f"🔍 Checking TypeScript in {module}/ module...")
            
            try:
                # Exécuter tsc --noEmit pour valider sans émettre
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    cwd=str(module_path),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=True
                )
                
                if result.returncode != 0:
                    # Parsing errors
                    error_lines = result.stderr.split('\n') if result.stderr else []
                    
                    for line in error_lines:
                        if line.strip() and ('error' in line.lower() or 'ts(' in line):
                            # Extract file path and error message
                            match = re.search(r'([^:\n]+):(\d+):(\d+)\s*-\s*(.+)', line)
                            if match:
                                file_path, line_num, col_num, error_msg = match.groups()
                                typescript_errors.append({
                                    "file": file_path,
                                    "line": int(line_num),
                                    "column": int(col_num),
                                    "message": error_msg.strip(),
                                    "module": module
                                })
                                logger.warning(f"  ❌ {file_path}:{line_num} - {error_msg.strip()}")
                            else:
                                # Generic error line
                                typescript_errors.append({
                                    "module": module,
                                    "raw_error": line.strip()
                                })
                    
                    logger.warning(f"⚠️ TypeScript found {len(typescript_errors)} error(s) in {module}")
                else:
                    logger.info(f"✅ No TypeScript errors in {module}")
                    
            except FileNotFoundError:
                logger.warning(f"⚠️ TypeScript compiler not found in {module} (npm_path install first?)")
            except subprocess.TimeoutExpired:
                logger.error(f"❌ TypeScript validation timeout in {module}")
                typescript_errors.append({
                    "module": module,
                    "error": "Compilation timeout (>30s)"
                })
            except Exception as e:
                logger.error(f"❌ Unexpected error during TypeScript validation in {module}: {e}")
                typescript_errors.append({
                    "module": module,
                    "error": f"Validation failed: {e}"
                })
        
        # Résumé
        if typescript_errors:
            logger.warning(f"📊 TypeScript validation: {len(typescript_errors)} issue(s) found")
            status = "FAILED"
        else:
            logger.info(f"✅ TypeScript validation: All modules pass")
            status = "PASSED"
        
        return {
            "typescript_errors": typescript_errors,
            "typescript_validation_status": status,
            "validation_status": "VALIDATED" if status == "PASSED" else "VALIDATION_FAILED"
        }

    def validate_dependency_node(self, state: AgentState) -> dict:
        """
        Valide et répare les dépendances AVANT npm install.
        
        🔴 Architecture:
        1. Utilise SemanticScanner pour détecter les VRAIES dépendances utilisées
        2. Compare avec package.json
        3. Ajoute les dépendances manquantes à package.json (pas les hallucinations LLM)
        
        Résultat: Zéro hallucinations de dépendances, seulement des imports réels.
        """
        logger.info("🔍 Validation des dépendances (avant npm install)...")
        
        try:
            from utils.scanner import SemanticScanner
            import json
            from pathlib import Path
            
            fixed_issues = []
            target_module = state.get("target_module")
            search_dirs = [self.root / target_module] if target_module else [self.root, self.root / "backend", self.root / "frontend"]
            
            for target_dir in search_dirs:
                try:
                    pkg_path = target_dir / "package.json"
                    if not pkg_path.exists():
                        continue
                    
                    # 🔴 UTILISER LE SCANNER pour détecter les vraies dépendances
                    scanner = SemanticScanner(str(target_dir))
                    missing_dependencies = scanner.detect_missing_dependencies()
                    
                    if not missing_dependencies:
                        logger.info(f"✅ {target_dir.name}: Toutes les dépendances sont déclarées.")
                        continue
                    
                    # Ajouter les dépendances manquantes à package.json
                    pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    
                    for pkg in missing_dependencies:
                        # Déterminer si c'est une dev dependency
                        is_dev = any(pkg.startswith(prefix) for prefix in ["@types/", "ts-", "jest", "vitest", "supertest", "@testing-library"])
                        section = "devDependencies" if is_dev else "dependencies"
                        
                        if section not in pkg_data:
                            pkg_data[section] = {}
                        
                        pkg_data[section][pkg] = "latest"
                        fixed_issues.append(f"Added {pkg} to {section}")
                        logger.info(f"➕ Ajouté {pkg} aux {section}")
                    
                    # Sauvegarder si modifications
                    if fixed_issues:
                        pkg_path.write_text(json.dumps(pkg_data, indent=2) + "\n", encoding="utf-8")
                        # Invalider le hash pour forcer un nouveau build
                        hash_file = target_dir / ".speckit_hash"
                        if hash_file.exists():
                            hash_file.unlink()
                        logger.info(f"✅ package.json mis à jour: {len(fixed_issues)} dépendances ajoutées")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erreur validation {target_dir}: {e}")
            
            # 🛡️ Filtrer les modules halluciner du LLM (si présents dans state)
            IGNORE_MODULES = [
                "@testing-library/react-hooks",
                "@testing-library/react",
                "jest",
                "vitest"
            ]
            state["missing_modules"] = [m for m in state.get("missing_modules", []) if m not in IGNORE_MODULES]
            
            logger.info(f"✅ Validation terminée. Dépendances du scanner définies dans package.json")
            
        except Exception as e:
            logger.error(f"❌ validate_dependency_node error: {e}")
            state["missing_modules"] = []
        
        # 🛡️ TOUJOURS retourner state
        return state

    def install_deps_node(self, state: AgentState) -> dict:
        """Nœud : Installation des dépendances npm — détection statique (scanner) SEULE source de vérité."""
        import subprocess
        from pathlib import Path
        from utils.scanner import SemanticScanner
        
        logger.info("📦 Installation des dépendances (npm install)...")
        
        # ─── 🛡️ ANTI-BOUCLE NIVEAU 1: Vérifier dep_install_attempts ───
        attempts = state.get("dep_install_attempts", 0)
        if attempts >= 1:
            logger.warning("⚠️ Dependency install already attempted. Skipping to prevent loops.")
            state["missing_modules"] = []
            return state

        state["dep_install_attempts"] = attempts + 1
        
        # ─── Déterminer le répertoire cible ───
        target_module = state.get("target_module")
        if target_module:
            target_dir = self.root / target_module
        else:
            # Chercher le premier répertoire avec package.json
            for search_dir in [self.root, self.root / "backend", self.root / "frontend"]:
                if (search_dir / "package.json").exists():
                    target_dir = search_dir
                    break
            else:
                logger.warning("⚠️ Aucun package.json trouvé")
                state["missing_modules"] = []
                return state
        
        pkg_path = target_dir / "package.json"
        if not pkg_path.exists():
            logger.warning(f"⚠️ package.json non trouvé dans {target_dir}")
            state["missing_modules"] = []
            return state
        
        # 🔴 DÉTECTION STATIQUE: Scanner = SOURCE DE VÉRITÉ
        # Le scanner analyse les imports RÉELLEMENT utilisés dans le code
        # C'est la seule vérité fiable. Le LLM peut halluciner, pas le code source.
        scanner = SemanticScanner(str(target_dir))
        missing_from_scanner = scanner.detect_missing_dependencies()
        
        logger.info(f"🔍 Scanner détecté {len(missing_from_scanner)} modules vraiment manquants: {missing_from_scanner}")
        
        # 🛡️ FILTRE DEPRECATED_PACKAGES: Remplacer les packages halluciner/dépréciés
        if missing_from_scanner:
            replaced = []
            for m in missing_from_scanner:
                if m in DEPRECATED_PACKAGES:
                    replacement = DEPRECATED_PACKAGES[m]
                    logger.info(f"🔄 Package déprécié {m} → remplacé par {replacement}")
                    replaced.append(replacement)
                else:
                    replaced.append(m)
            missing_from_scanner = list(set(replaced))  # Deduplicate si plusieurs pointent au même replacement
        
        # 🛡️ STOCKER LE RÉSULTAT DU SCANNER COMME SOURCE DE VÉRITÉ
        state["scanner_missing_modules"] = missing_from_scanner
        
        # ═══ RÈGLE ARCHITECTURALE ═══
        # Si le scanner dit 0 → c'est 0
        # Pas de fallback au LLM (qui peut halluciner)
        if not missing_from_scanner:
            logger.info("✅ Scanner confirme : aucune dépendance manquante.")
            state["missing_modules"] = []
            return state
        
        # ─── 🛡️ ANTI-BOUCLE NIVEAU 2: Filtrer les modules déjà tentés ───
        attempted = state.get("attempted_installs", [])
        filtered_missing = [m for m in missing_from_scanner if m not in attempted]
        
        if not filtered_missing:
            logger.info(f"⚠️ Tous les modules ont déjà été tentés: {missing_from_scanner}")
            logger.warning("🛑 Arrêt des tentatives d'installation pour éviter la boucle infinie.")
            state["missing_modules"] = []
            return state
        
        if len(filtered_missing) < len(missing_from_scanner):
            skipped = set(missing_from_scanner) - set(filtered_missing)
            logger.info(f"⏭️  Modules déjà tentés (ignorés): {list(skipped)}")
        
        # ─── Installer les modules manquants ───
        logger.warning(f"🚀 Installation de {len(filtered_missing)} modules: {filtered_missing}...")
        
        # 🛡️ Tracker les tentatives avant d'essayer
        state["attempted_installs"] = attempted + filtered_missing
        
        try:
            import shutil
            npm_path = shutil.which("npm") or shutil.which("npm.cmd")
            if not npm_path:
                logger.error("❌ npm not found in PATH")
                state["missing_modules"] = []
                return state
            
            subprocess.run(
                [npm_path, "install"] + filtered_missing,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=180
            )
            logger.info(f"✅ Modules {filtered_missing} installés avec succès.")
            
            # ─── 🛡️ Effacer missing_modules APRÈS installation ───
            state["missing_modules"] = []
            
            # ─── Tracker les modules installés ───
            installed = state.get("installed_modules", [])
            installed.extend(filtered_missing)
            state["installed_modules"] = installed
        except Exception as e:
            logger.error(f"⚠️ Échec installation modules {filtered_missing}: {e}")
            # Même en cas d'erreur, effacer pour éviter les boucles
            state["missing_modules"] = []

        return state


    def verify_node(self, state: AgentState) -> dict:
        """Nœud 3 : Audit de sécurité et conformité finale."""
        if state.get("error_count", 0) >= MAX_RETRIES:
            logger.error("🛑 Limite de tentatives atteinte (MAX_RETRIES).")
            # Tolérance structurelle : si on a atteint la limite d'essais TypeScript (buildfix) 
            # MAIS que l'Agent a réussi à structurer les fichiers et les deps (STRUCTURE_OK)
            # alors on le marque comme APPROUVÉ avec alerte pour ne pas bloquer tout le projet.
            if state.get("validation_status") == "STRUCTURE_OK" or state.get("validation_status") == "DEPS_INSTALLED":
                state["validation_status"] = "APPROUVÉ"
                state["alertes"] = "Limite de tentatives atteinte. Des erreurs TypeScript mineures peuvent subsister, mais la structure (fichiers/dossiers/routes) a été correctement générée."
            else:
                state["validation_status"] = "REJETÉ"
                state["alertes"] = "Limite de tentatives atteinte et la structure demandée n'est pas conforme."
            return state

        # Rafraîchir le file_tree depuis le disque pour un audit précis
        import os
        fresh_tree = []
        ignore = {'node_modules', 'dist', '.git', '__pycache__'}
        for root_dir, dirs, files in os.walk(str(self.root)):
            dirs[:] = [d for d in dirs if d not in ignore]
            for f in files:
                fresh_tree.append(os.path.relpath(os.path.join(root_dir, f), str(self.root)).replace('\\', '/'))
        state = {**state, "file_tree": "\n".join(fresh_tree)}

        logger.info(f"🛡️ Début de l'Audit pour le code généré.")
        
        prompt_text = self._load_prompt("subagent_verify.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentVerifyOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            # 🛡️ IMPROVED: Capturer l'état de génération AVANT l'audit
            generation_failed = state.get("validation_status") == "REJETÉ" or state.get("last_error", "")
            structure_valid = state.get("validation_status") in ["STRUCTURE_OK", "DEPS_INSTALLED", "GENERATED"]
            
            logger.info(f"📊 État pré-audit : generation_failed={generation_failed}, structure_valid={structure_valid}")
            
            # 🛡️ RETRY avec backoff pour l'audit lui-même
            invoke_dict = {
                "constitution_hash": state.get("constitution_hash", "INCONNU"),
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "analysis_output": state["analysis_output"],
                "code_to_verify": state["code_to_verify"],
                "terminal_diagnostics": state.get("terminal_diagnostics", "N/A"),
                "user_instruction": state.get("user_instruction", ""),
                "subtask_checklist": state["subtask_checklist"],
                "file_tree": state["file_tree"],
                "code_map": state["code_map"],
                "format_instructions": parser.get_format_instructions()
            }
            
            raw_output = self._invoke_with_retry(chain, invoke_dict, max_attempts=3)
            result = self._safe_parse_json(raw_output, SubagentVerifyOutput)
            
            verdict = result["verdict_final"].upper()
            verifier_status = "APPROUVÉ" if "APPROUVÉ" in verdict else "REJETÉ"
            final_score = int(result.get("score_conformite", 0))
            
            # 🛡️ IMPROVED AUDIT LOGIC:
            # - Si génération échouée ET structure invalide → REJETÉ
            # - Sinon, on accepte le verdict du verifier
            if generation_failed and not structure_valid:
                logger.warning(f"⚠️ Génération échouée ET structure invalide → REJET")
                status = "REJETÉ"
                feedback_msg = f"Generation erro detected and structure is invalid. {result.get('action_corrective', '')}"
            else:
                status = verifier_status
                feedback_msg = result.get('action_corrective', '') if verifier_status == "REJETÉ" else ""
                if generation_failed and structure_valid:
                    logger.warning(f"⚠️ Génération échouée MAIS structure valide → APPROUVÉ avec alerte")
                    logger.info(f"✅ Au moins la structure demandée a été générée correctement.")
            
            if status == "APPROUVÉ":
                logger.info(f"✅ Code APPROUVÉ. Score: {final_score}")
                return {
                    "validation_status": "APPROUVÉ", 
                    "score": str(final_score),
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', 'Aucune.' if not generation_failed else 'Génération partiellement échouée Mais structure valide.'),
                    "feedback_correction": "",
                    "audit_errors_history": state.get("audit_errors_history", [])
                }
            else:
                new_error_count = state.get("error_count", 0) + 1
                
                # 🛡️ TRACK audit errors to detect recurring issues
                audit_errors = state.get("audit_errors_history", [])
                error_summary = f"{result.get('alertes', '')[:100]}..."  # First 100 chars
                audit_errors.append(error_summary)
                
                # 🔍 DETECT RECURRING ERRORS (same error twice = can't fix it automatically)
                is_recurring_error = len(audit_errors) >= 2 and audit_errors[-1] == audit_errors[-2]
                if is_recurring_error:
                    logger.error(f"🔄 RECURRING ERROR DETECTED: {audit_errors[-1]}")
                    logger.error(f"🛑 Same error appeared {len([e for e in audit_errors if e == audit_errors[-1]])} times. Stopping retries.")
                    new_error_count = MAX_RETRIES  # Force END by marking max retries reached
                
                return {
                    "validation_status": "REJETÉ", 
                    "score": str(final_score),
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', ''),
                    "feedback_correction": feedback_msg,
                    "error_count": new_error_count,
                    "audit_errors_history": audit_errors
                }
        except Exception as e:
            logger.error(f"❌ Erreur audit : {e}")
            state["validation_status"] = "REJETÉ"
            state["feedback_correction"] = str(e)
            state["error_count"] = state.get("error_count", 0) + 1
            return state

    def task_enforcer_node(self, state: AgentState) -> dict:
        """Nœud de vérification structurelle."""
        logger.info("🛡️ Vérification structurelle (TaskEnforcer)...")
        prompt_text = self._load_prompt("subagent_Speckit-TaskEnforcer.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentTaskEnforcerOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            invoke_dict = {
                "subtask_checklist": state.get("subtask_checklist", ""),
                "file_tree": state.get("file_tree", ""),
                "format_instructions": parser.get_format_instructions()
            }
            raw_output = self._invoke_with_retry(chain, invoke_dict, max_attempts=3)
            result = self._safe_parse_json(raw_output, SubagentTaskEnforcerOutput)
            
            # ──────── POST-PROCESSING: Vérifier les fichiers manquants en Python ────────
            # Parfois l'IA retourne juste le nom du fichier ("HomePage.tsx")
            # au lieu du chemin complet ("frontend/src/pages/HomePage.tsx").
            # On fait une vérification robuste en Python avant de marquer comme manquant.
            
            file_tree_str = state.get("file_tree", "")
            file_tree_list = file_tree_str.split('\n') if file_tree_str else []
            
            verified_missing = []
            for missing_file in result.get("missing_files", []):
                # Essayer 3 niveaux de correspondance
                if self._file_exists_in_tree(missing_file, file_tree_list):
                    logger.info(f"✅ Fichier trouvé après post-processing: {missing_file}")
                    # Le fichier existe vraiment, ne pas le marquer comme manquant
                else:
                    logger.warning(f"❌ Fichier manquant confirmé: {missing_file}")
                    verified_missing.append(missing_file)
            
            # Mettre à jour le résultat avec les vraiment manquants
            result["missing_files"] = verified_missing
            result["missing_tasks"] = len(verified_missing)
            
            if len(verified_missing) == 0:
                state["validation_status"] = "STRUCTURE_OK"
                return state
            else:
                return {
                    "validation_status": "STRUCTURE_KO",
                    "feedback_correction": f"MANQUANT: {', '.join(verified_missing)}",
                    "error_count": state.get("error_count", 0) + 1
                }
        except Exception as e:
            state["validation_status"] = "STRUCTURE_KO"
            state["feedback_correction"] = str(e)
            return state

    def code_map_node(self, state: AgentState) -> dict:
        """Nœud de génération de la Semantic Code Map."""
        logger.info("🗺️ Génération de la Semantic Code Map...")
        import os, re, json
        
        code_map = {"file_tree": [], "semantics": {}}
        ignore_dirs = {'node_modules', 'dist', '.git', '__pycache__'}
        
        for root, dirs, files in os.walk(str(self.root)):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), str(self.root)).replace('\\', '/')
                code_map["file_tree"].append(rel_path)
                if file.endswith(('.ts', '.js', '.tsx', '.jsx')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            content = f.read()
                            imports = re.findall(r"import.*from\s+['\"]([^'\"]+)['\"]", content)
                            exports = re.findall(r"export.*?(?:const|let|var|function|class|interface|type)\s+([\w$]+)", content)
                            code_map["semantics"][rel_path] = {"imports": list(set(imports)), "exports": list(set(exports))}
                    except: pass
        
        return {"code_map": json.dumps(code_map["semantics"]), "file_tree": "\n".join(code_map["file_tree"])}

    def buildfix_node(self, state: AgentState) -> dict:
        """Nœud de réparation automatique du build."""
        logger.info("🛠️ Tentative de réparation du build...")
        
        try:
            prompt_text = self._load_prompt("subagent_buildfix.prompt")
            from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, HumanMessagePromptTemplate
            parser = JsonOutputParser(pydantic_object=SubagentBuildFixOutput)
            format_instructions = parser.get_format_instructions()
            inject_dict = {
                "code_to_verify": state.get("code_to_verify", ""),
                "terminal_diagnostics": state.get("terminal_diagnostics", ""),
                "file_tree": state.get("file_tree", ""),
                "code_map": state.get("code_map", ""),
                "feedback_correction": state.get("feedback_correction", ""),
                "format_instructions": format_instructions
            }
            # Replace placeholders safely without template parsing
            for key, value in inject_dict.items():
                placeholder = "{" + key + "}"
                prompt_text = prompt_text.replace(placeholder, str(value))
            prompt = ChatPromptTemplate.from_template("You are a helpful assistant.\n\n" + prompt_text)
            chain = prompt | self.model | StrOutputParser()
            # 🛡️ RETRY with backoff
            raw_output = self._invoke_with_retry(chain, {}, max_attempts=3)
            result = self._safe_parse_json(raw_output, SubagentBuildFixOutput)
            sanitized_fix, written = self._persist_code_to_disk(result.get("code", ""))
            merged = self._merge_code(state.get("code_to_verify", ""), sanitized_fix)
            return {
                "code_to_verify": merged,
                "error_count": state.get("error_count", 0) + 1,
                "impact_fichiers": list(set(state.get("impact_fichiers", []) + written)),
                "feedback_correction": f"BUILD FIX: {result.get('resume', '')}"
            }
        except Exception as e:
            logger.error(f"🛑 buildfix_node error: {e}")
            return {"feedback_correction": f"BUILD FIX FAILED: {str(e)}"}

    def _persist_code_to_disk(self, code: str) -> tuple[str, list[str]]:
        from utils.file_manager import FileManager
        fm = FileManager(base_path=str(self.root))
        results = fm.extract_and_write(code)
        written_paths = [item["path"] for item in results]
        sanitized_blocks = []
        for item in results:
            sanitized_blocks.append(f"// Fichier : {item['path']}\n{item['content']}")
        return "\n\n".join(sanitized_blocks), written_paths

    def _validate_typescript(self, code: str, target_task: str) -> tuple[bool, str]:
        import subprocess, tempfile, re
        from pathlib import Path
        pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        parts = re.split(pattern, code)
        if len(parts) <= 1: return True, ""
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            ts_files = []
            for i in range(1, len(parts), 2):
                fpath, content = parts[i].strip(), parts[i+1].strip()
                if fpath.endswith(('.ts', '.tsx')):
                    t = tmp_path / fpath
                    t.parent.mkdir(parents=True, exist_ok=True)
                    t.write_text(content, encoding="utf-8")
                    ts_files.append(str(t))
            
            if not ts_files: return True, ""
            
            cmd = ["npx", "--yes", "tsc", "--noEmit", "--skipLibCheck", "--target", "es2022", "--module", "commonjs"] + ts_files
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=60)
                if res.returncode == 0: return True, ""
                return False, res.stdout + res.stderr
            except: return True, ""

    def _merge_code(self, base: str, delta: str) -> str:
        if not delta: return base
        import re
        pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        
        def parse_blocks(code):
            parts = re.split(pattern, code)
            blocks = {}
            if len(parts) > 1:
                for i in range(1, len(parts), 2):
                    filename = parts[i].strip()
                    content = parts[i+1].strip()
                    blocks[filename] = content
            elif code.strip() and not re.search(pattern, code):
                # Fallback pour le cas où delta ne contient pas de marqueurs de fichiers (si un seul fichier est retourné sans marqueur)
                # Mais BuildFix est censé retourner avec marqueurs. Dans le doute, on n'écrase pas tout si on ne peut pas parser.
                pass
            return blocks

        base_blocks = parse_blocks(base)
        delta_blocks = parse_blocks(delta)
        
        if not delta_blocks and delta.strip():
             # Si delta n'a pas pu être parsé mais n'est pas vide, c'est peut-être un fichier unique.
             # On essaie de deviner si c'est le cas (peu probable avec Speckit).
             pass

        # Update base with delta
        base_blocks.update(delta_blocks)
        
        merged_blocks = []
        for filename, content in base_blocks.items():
            merged_blocks.append(f"// Fichier : {filename}\n{content}")
        
        return "\n\n".join(merged_blocks)

    # route_after_diagnostic supprimé — diagnostic va toujours vers task_enforcer
            
    def _check_typescript_installed(self, project_dir: Path) -> bool:
        """Vérifie si typescript est installé dans le projet."""
        ts_path = project_dir / "node_modules" / "typescript"
        return ts_path.exists()

    def _compute_package_hash(self, pkg_path: Path) -> str:
        """Calcule le hash MD5 du contenu du package.json."""
        import hashlib
        if not pkg_path.exists():
            return ""
        try:
            content = pkg_path.read_text(encoding="utf-8")
            return hashlib.md5(content.encode()).hexdigest()
        except Exception:
            return ""

    def _get_cached_hash(self, project_dir: Path) -> str:
        """Récupère le hash stocké en cache (si existant)."""
        hash_file = project_dir / ".speckit_hash"
        if hash_file.exists():
            try:
                return hash_file.read_text(encoding="utf-8").strip()
            except Exception:
                return ""
        return ""

    def _save_package_hash(self, pkg_path: Path, current_hash: str) -> None:
        """Sauvegarde le hash du package.json dans .speckit_hash."""
        hash_file = pkg_path.parent / ".speckit_hash"
        try:
            hash_file.write_text(current_hash, encoding="utf-8")
            logger.info(f"💾 Hash package.json sauvegardé: {current_hash[:8]}...")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de sauvegarder le hash: {e}")

    def _extract_required_files(self, checklist_text: str) -> List[str]:
        """Extrait les chemins de fichiers obligatoires mentionnés dans la checklist.
        
        Stratégie multi-niveau pour extraire les chemins:
        
        Pattern 1: Chemin COMPLET en un seul bloc: `backend/src/middlewares/auth.ts`
        Pattern 2: Fichier + Répertoire séparés: `RegisterPage.tsx` ... `frontend/src/pages/`
        Pattern 3: Fallback simple regex pour les formats minimalistes
        Pattern 4: Cas spécial - si le chemin commence par `src/`, ajouter le module prefix
        
        Returns: Liste des chemins de fichiers trouvés (sans doublons)
        """
        import re
        if not checklist_text:
            return []
        
        required_files = []
        seen_full_paths = set()  # Pour éviter les doublons
        
        # Traiter chaque ligne de la checklist
        for line in checklist_text.split('\n'):
            if not line.strip():
                continue
            
            # Pattern 1: Chemin COMPLET avec module inclus
            # Cherche: `backend/src/..` ou `frontend/src/...` ou `path/to/file.ext`
            full_paths = re.findall(r'`([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)`', line)
            
            full_path_suffixes = set()  # Garder trace des fichiers trouvés avec chemin complet
            
            for path in full_paths:
                # Normaliser les backslashes en forward slashes
                path = path.replace('\\', '/')
                
                # Vérifier que ce n'est pas un chemin partiel comme "src/..."
                # (sera traité plus tard avec module detection)
                if path not in seen_full_paths:
                    required_files.append(path)
                    seen_full_paths.add(path)
                    # Garder trace du suffix du chemin (ex: components/RegisterForm.tsx)
                    full_path_suffixes.add(path.split('/')[-1])
            
            # Pattern 2: Cas particulier - fileName ET répertoire SÉPARÉS sur la même ligne
            # Exemple: ... `RegisterPage.tsx` ... dans `frontend/src/pages/`
            # Stratégie: 
            # - Trouver tous les backtick'd items
            # - Séparer les fichiers (.ext) des répertoires (contient /)
            # - Si 1 fichier et >=1 répertoires, combiner
            # - MAIS: Ignorer les fichiers déjà trouvés en Pattern 1
            
            # Extraire TOUS les items entre backticks
            all_backtick_items = re.findall(r'`([^`]+)`', line)
            
            # Classer en fichiers et répertoires
            files_in_line = []
            dirs_in_line = []
            
            for item in all_backtick_items:
                item = item.strip()
                # Vérifier si c'est déjà un chemin complet (contient /)
                if '/' in item or '\\' in item:
                    # C'est un chemin (fichier ou répertoire)
                    item = item.replace('\\', '/')
                    if item.endswith('/'):
                        dirs_in_line.append(item)
                    else:
                        # C'est un fichier avec chemin
                        if item not in seen_full_paths:
                            required_files.append(item)
                            seen_full_paths.add(item)
                else:
                    # C'est potentiellement un fichier (pas de /)
                    # MAIS: Ne l'ajouter QUE s'il n'était pas en Pattern 1
                    if '.' in item and item not in full_path_suffixes:
                        files_in_line.append(item)
            
            # Si on a exactement 1 fichier SANS chemin et 1+ répertoires, combiner
            if len(files_in_line) == 1 and len(dirs_in_line) >= 1:
                filename = files_in_line[0]
                # Utiliser le répertoire le plus spécifique (le plus long)
                directory = max(dirs_in_line, key=len)
                combined_path = f"{directory}{filename}".replace('//', '/')
                
                # Vérifier que ce chemin n'a pas déjà été extrait
                if combined_path not in seen_full_paths:
                    required_files.append(combined_path)
                    seen_full_paths.add(combined_path)
            
            # Pattern 3: Fallback SIMPLE regex pour les checklists minimalistes
            # Cherche des patterns simples comme: " - [ ] LoginForm.tsx en frontend/src/components/"
            # Format simple: nom_fichier.ext en repertoire/
            simple_matches = re.findall(r'(?:^|\s+)(?:[-*+]|\d\.)\s*(?:\[ ?\]|\[ ?x\])?\s*(\w+\.\w+)\s+(?:dans|en|in)\s+[`]?([^`,\n]+/?)[`]?', line, re.IGNORECASE)
            
            for filename, directory in simple_matches:
                directory = directory.strip().rstrip('/') + '/'
                combined_path = f"{directory}{filename}".replace('//', '/')
                
                if combined_path not in seen_full_paths:
                    required_files.append(combined_path)
                    seen_full_paths.add(combined_path)
                    logger.debug(f"📝 Pattern 3 (simple) matched: {combined_path}")
        
        if required_files:
            logger.info(f"📋 Fichiers obligatoires identifiés dans checklist: {required_files}")
        else:
            logger.debug(f"📋 Aucun fichier obligatoire identifié dans checklist")
        
        return required_files

    def _ensure_required_artifacts(self, required_files: List[str], written_paths: List[str]) -> List[str]:
        """Crée les fichiers obligatoires manquants en tant que stubs minimalistes.
        
        Pour chaque fichier obligatoire non écrit, génère un stub approprié.
        Args:
            required_files: Liste des chemins de fichiers obligatoires
            written_paths: Liste des fichiers déjà écrites par persist_code_to_disk
        Returns: Liste des fichiers créés
        """
        created_files = []
        
        for required_file in required_files:
            file_path = self.root / required_file
            
            # Vérifier si le fichier existe déjà (sur disque ou écrit par l'IA)
            if file_path.exists() or required_file in written_paths:
                logger.info(f"✅ Fichier obligatoire existant: {required_file}")
                continue
            
            # Créer les répertoires parents
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"❌ Erreur création répertoires pour {required_file}: {e}")
                continue
            
            # Générer un stub minimal basé sur l'extension
            ext = file_path.suffix.lower()
            stub_content = self._generate_stub_content(ext, required_file)
            
            try:
                file_path.write_text(stub_content, encoding="utf-8")
                logger.info(f"✨ Fichier obligatoire créé (stub): {required_file}")
                created_files.append(required_file)
            except Exception as e:
                logger.error(f"❌ Erreur écriture stub {required_file}: {e}")
        
        return created_files

    def _generate_stub_content(self, ext: str, file_path: str) -> str:
        """Génère un contenu de stub minimaliste approprié au type de fichier.
        
        Args:
            ext: Extension du fichier (ex: .ts, .json)
            file_path: Chemin complet du fichier (pour contexte)
        Returns: Contenu minimal du stub
        """
        if ext in [".ts", ".tsx"]:
            # TypeScript: export vide ou stub contextuel
            if "middleware" in file_path.lower():
                return "// Middleware stub - to be implemented\nexport {};\n"
            elif "controller" in file_path.lower():
                return "// Controller stub - to be implemented\nexport {};\n"
            elif "service" in file_path.lower():
                return "// Service stub - to be implemented\nexport {};\n"
            else:
                return "// Stub file - to be implemented\nexport {};\n"
        
        elif ext in [".js", ".jsx"]:
            # JavaScript
            return "// Stub file - to be implemented\nmodule.exports = {};\n"
        
        elif ext == ".json":
            # JSON - valid empty object
            return "{}\n"
        
        elif ext == ".md":
            # Markdown
            return "# Placeholder\n\nThis file is a placeholder and should be implemented.\n"
        
        elif ext in [".yaml", ".yml"]:
            # YAML - empty object
            return "{}\n"
        
        elif ext == ".css":
            # CSS - empty stylesheet
            return "/* Stub stylesheet */\n"
        
        elif ext == ".html":
            # HTML - minimal structure
            return "<!-- Stub HTML file -->\n"
        
        else:
            # Default fallback
            return "// Auto-generated stub file\n"

    def _file_exists_in_tree(self, file_to_find: str, file_tree_list: List[str]) -> bool:
        r"""Cherche un fichier dans l'arborescence avec stratégie multi-niveaux.
        
        Essaie de matcher:
        1. Le chemin exact
        2. Le chemin normalisé (\ → /)
        3. Juste le nom du fichier n'importe où dans l'arbo
        
        Args:
            file_to_find: Chemin ou nom du fichier à chercher (ex: "HomePage.tsx" ou "frontend/src/pages/HomePage.tsx")
            file_tree_list: Liste des fichiers dans l'arborescence
        
        Returns: True si le fichier est trouvé, False sinon
        """
        file_to_find_normalized = file_to_find.replace('\\', '/')
        file_name_only = file_to_find.split('/')[-1] if '/' in file_to_find else file_to_find
        
        for tree_file in file_tree_list:
            tree_file_normalized = tree_file.strip().replace('\\', '/')
            
            # Niveau 1 : correspondance exacte
            if tree_file_normalized == file_to_find_normalized:
                return True
            
            # Niveau 2 : endswith (pour chemins partiels)
            if tree_file_normalized.endswith(file_to_find_normalized):
                return True
            
            # Niveau 3 : corresponds au nom du fichier seul
            tree_file_name = tree_file_normalized.split('/')[-1]
            if tree_file_name == file_name_only:
                return True
        
        return False

    def diagnostic_node(self, state: AgentState) -> dict:
        """Nœud : Diagnostics réels (tsc --noEmit ou vite build selon le module cible).
        
        ⚠️ PROTECTION STRICTE : Si target_module est défini, teste UNIQUEMENT ce module.
        Ignore complètement les autres modules.
        """
        logger.info("🔍 Exécution des diagnostics réels...")
        import subprocess, re, json
        
        # ─── DÉTERMINER LE MODULE CIBLE ET L'OUTIL DE BUILD ───
        target_module = state.get("target_module")
        
        if target_module:
            # Un module cible est explicitement spécifié
            search_dirs = [self.root / target_module]
            logger.info(f"📍 Diagnostics STRICT : module {target_module} seulement (autres ignorés)")
        else:
            # Fallback : tous les modules disponibles
            search_dirs = [self.root, self.root / "backend", self.root / "frontend"]
            logger.info(f"📍 Diagnostics sur tous les modules")
        
        reports = []
        missing_modules = []
        module_errors = {}  # Tracker les erreurs par module
        
        for d in search_dirs:
            if not (d / "package.json").exists():
                continue
            
            # ─── Déterminer l'outil de build ───
            build_tool = self._get_build_tool(d.name if d != self.root else "")
            
            # ─── VÉRIFICATION PRE-TSC : typescript installé? ───
            if build_tool == "tsc":
                if not self._check_typescript_installed(d):
                    logger.warning(f"⚠️ TypeScript non installé dans {d.name}. Ajout à la liste des modules manquants.")
                    missing_modules.append("typescript")
                    reports.append(f"[TSC {d.name}] ❌ ÉCHEC\nTypeScript non installé dans node_modules. Exécutez: npm_path install --save-dev typescript")
                    continue
                
                try:
                    res = subprocess.run(
                        "npx --yes tsc --noEmit --pretty false",
                        shell=True, capture_output=True, text=True,
                        cwd=str(d), timeout=120
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    status = "✅" if res.returncode == 0 else "❌ ÉCHEC"
                    reports.append(f"[TSC {d.name}] {status}\n{output}")
                    
                    # ⚠️ Tracker si c'est le module cible
                    if res.returncode != 0:
                        module_errors[d.name or "root"] = "tsc"
                    
                    # Détection des modules manquants (UNIQUEMENT pour le module cible)
                    if target_module and d.name != target_module:
                        logger.info(f"⏭️ Skip détection modules pour {d.name} (non-target)")
                    else:
                        matches = re.findall(r"Cannot find module '([^']+)'", output)
                        if matches:
                            npm_matches = [
                                m for m in matches 
                                if not m.startswith('.') and not m.startswith('/') and not (m and m[0].isupper())
                            ]
                            missing_modules.extend(npm_matches)
                        
                except subprocess.TimeoutExpired:
                    reports.append(f"[TSC {d.name}] ❌ ÉCHEC\nTimeout après 120s")
                except Exception as e:
                    reports.append(f"[TSC {d.name}] ❌ ÉCHEC\n{str(e)}")
            
            elif build_tool == "vite":
                # Pour Vite, utiliser vite preview ou build
                try:
                    res = subprocess.run(
                        "npm_path run build",
                        shell=True, capture_output=True, text=True,
                        cwd=str(d), timeout=120
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    status = "✅" if res.returncode == 0 else "❌ ÉCHEC"
                    reports.append(f"[VITE {d.name}] {status}\n{output}")
                    
                    # ⚠️ Tracker si c'est le module cible
                    if res.returncode != 0:
                        module_errors[d.name or "root"] = "vite"
                    
                    # Détection des modules manquants (UNIQUEMENT pour le module cible)
                    if target_module and d.name != target_module:
                        logger.info(f"⏭️ Skip détection modules pour {d.name} (non-target)")
                    else:
                        matches = re.findall(r"Cannot find module '([^']+)'", output)
                        if matches:
                            npm_matches = [
                                m for m in matches 
                                if not m.startswith('.') and not m.startswith('/') and not (m and m[0].isupper())
                            ]
                            missing_modules.extend(npm_matches)
                        
                except subprocess.TimeoutExpired:
                    reports.append(f"[VITE {d.name}] ❌ ÉCHEC\nTimeout après 120s")
                except Exception as e:
                    reports.append(f"[VITE {d.name}] ❌ ÉCHEC\n{str(e)}")
            
            elif build_tool == "next":
                # Pour Next.js, utiliser npm run build ou next build
                try:
                    res = subprocess.run(
                        "npm_path run build",
                        shell=True, capture_output=True, text=True,
                        cwd=str(d), timeout=120
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    status = "✅" if res.returncode == 0 else "❌ ÉCHEC"
                    reports.append(f"[NEXT {d.name}] {status}\n{output}")
                    
                    # ⚠️ Tracker si c'est le module cible
                    if res.returncode != 0:
                        module_errors[d.name or "root"] = "next"
                    
                    # Détection des modules manquants (UNIQUEMENT pour le module cible)
                    if target_module and d.name != target_module:
                        logger.info(f"⏭️ Skip détection modules pour {d.name} (non-target)")
                    else:
                        matches = re.findall(r"Cannot find module '([^']+)'", output)
                        if matches:
                            npm_matches = [
                                m for m in matches 
                                if not m.startswith('.') and not m.startswith('/') and not (m and m[0].isupper())
                            ]
                            missing_modules.extend(npm_matches)
                        
                except subprocess.TimeoutExpired:
                    reports.append(f"[NEXT {d.name}] ❌ ÉCHEC\nTimeout après 120s")
                except Exception as e:
                    reports.append(f"[NEXT {d.name}] ❌ ÉCHEC\n{str(e)}")
        
        logger.info("🛠️ Diagnostics terminés.")
        
        # ⚠️ Si target_module est défini, retourner AUSSI info sur les erreurs non-target
        non_target_errors = {k: v for k, v in module_errors.items() if k != target_module}
        if non_target_errors and target_module:
            logger.warning(f"⚠️ Erreurs détectées dans modules non-cibles (IGNORÉES): {non_target_errors}")
        
        return {
            "terminal_diagnostics": "\n".join(reports),
            "missing_modules": list(set(missing_modules)),
            "non_target_errors": non_target_errors  # Pour éviter buildfix sur ces erreurs
        }
    
    def dependency_resolver_node(self, state: AgentState) -> dict:
        """Nœud : Détection proactive des dépendances manquantes via analyse d'imports.
        
        Scanne les fichiers source pour détecter les imports (import/require statements)
        et compare avec package.json pour identifier les dépendances manquantes.
        Cela prévient les erreurs TypeScript "Cannot find module" avant compilation.
        """
        import os, json, re
        from pathlib import Path
        
        logger.info("🔎 Analyse proactive des dépendances (Dependency Resolver)...")
        
        target_module = state.get("target_module")
        if target_module:
            search_dirs = [self.root / target_module]
            logger.info(f"📍 Resolver limité au module : {target_module}")
        else:
            search_dirs = [self.root, self.root / "backend", self.root / "frontend"]
        
        detected_missing = []
        
        for module_dir in search_dirs:
            src_dir = module_dir / "src"
            if not src_dir.exists():
                continue
            
            pkg_path = module_dir / "package.json"
            if not pkg_path.exists():
                continue
            
            # Lire les dépendances du package.json
            try:
                pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                installed = set()
                installed.update(pkg_data.get("dependencies", {}).keys())
                installed.update(pkg_data.get("devDependencies", {}).keys())
            except Exception:
                installed = set()
            
            # Parser tous les fichiers TypeScript/JavaScript pour les imports
            imports_found = set()
            
            for root_dir, dirs, files in os.walk(str(src_dir)):
                dirs[:] = [d for d in dirs if d not in {'node_modules', 'dist', '.git', '__pycache__'}]
                
                for file in files:
                    if not file.endswith(('.ts', '.tsx', '.js', '.jsx')):
                        continue
                    
                    filepath = Path(root_dir) / file
                    
                    try:
                        content = filepath.read_text(encoding="utf-8")
                        
                        # Regex 1: import { x } from 'module' ou "module"
                        regex_imports = r"import\s+(?:{[^}]+}|[^,]+)\s+from\s+['\"]([^'\"]+)['\"]"
                        matches = re.findall(regex_imports, content)
                        imports_found.update(matches)
                        
                        # Regex 2: require('module') ou require("module")
                        regex_require = r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
                        matches = re.findall(regex_require, content)
                        imports_found.update(matches)
                        
                        # Regex 3: import 'module' (side effects)
                        regex_side_effects = r"import\s+['\"]([^'\"]+)['\"]"
                        matches = re.findall(regex_side_effects, content)
                        imports_found.update(matches)
                    
                    except Exception:
                        pass
            
            # Filtrer les imports de fichiers relatifs et identifier les modules manquants
            for imp in imports_found:
                # Ignorer les imports relatifs
                if imp.startswith('.') or imp.startswith('/'):
                    continue
                
                # Extraire le nom du package principal (ex: "lodash" de "lodash/get")
                if '/' in imp and not imp.startswith('@'):
                    pkg_name = imp.split('/')[0]
                elif imp.startswith('@'):
                    # Scoped package: @org/package ou @org/package/sub
                    parts = imp.split('/')
                    pkg_name = f"{parts[0]}/{parts[1]}"
                else:
                    pkg_name = imp
                
                # Vérifier si le package est installé
                if pkg_name not in installed:
                    logger.warning(f"⚠️ Module manquant détecté (via import): {pkg_name} (source: {imp})")
                    detected_missing.append(pkg_name)
        
        # Fusionner avec les modules manquants détectés par diagnostic_node
        all_missing = list(set(detected_missing + state.get("missing_modules", [])))
        
        if all_missing:
            logger.info(f"🎯 Modules à installer: {all_missing}")
        else:
            logger.info("✅ Aucun module manquant détecté.")
        
        return {
            "missing_modules": all_missing
        }

    def route_after_impl(self, state: AgentState) -> str:
        if state["validation_status"] == "REJETÉ":
            if state.get("error_count", 0) >= MAX_RETRIES:
                logger.error(f"🛑 Limite de tentatives atteinte ({MAX_RETRIES}) après échec Génération.")
                return "verify_node"
            return "impl_node"
        return "persist_node"

    def route_from_install_deps(self, state: AgentState) -> str:
        """
        🔴 PROTECTION STRUCTURALE: Casse la boucle Diagnostics → TaskEnforcer → InstallDeps → Diagnostics
        
        Après install_deps_node, décide:
        - S'il y a vraiment des modules manquants → retour à diagnostic
        - Sinon ou cycle max atteint → sortie vers verify (fin)
        """
        # 🛡️ Compteur de cycles: si trop de cycles dépendances, sortir
        dep_cycles = state.get("dependency_cycles", 0)
        if dep_cycles >= MAX_DEPENDENCY_CYCLES:
            logger.warning(f"⚠️ Dependency cycle limit reached ({MAX_DEPENDENCY_CYCLES} cycles). Breaking cycle.")
            state["missing_modules"] = []
            return "verify_node"
        
        state["dependency_cycles"] = dep_cycles + 1
        logger.debug(f"📊 Dependency cycle {state['dependency_cycles']}/{MAX_DEPENDENCY_CYCLES}")
        
        # Si scanner a trouvé 0 modules → pas de raison de re-scanner
        scanner_missing = state.get("scanner_missing_modules", [])
        if not scanner_missing:
            logger.info("✅ Scanner confirme: 0 modules manquants après install_deps. Exiting dependency loop.")
            state["missing_modules"] = []
            return "verify_node"
        
        # Sinon, on relance le diagnostic
        logger.warning(f"🔄 Retour à diagnostics pour vérifier installation de {scanner_missing}...")
        return "diagnostic_node"

    def route_after_enf(self, state: AgentState) -> str:
        """Route après TaskEnforcer : vérifie à la fois les erreurs TSC et structurelles.
        
        ⚠️ PROTECTIONS MULTI-NIVEAUX:
        - graph_steps: limite totale des cycles du graphe
        - scanner_missing: source de vérité (TOOLS > LLM)
        - TEST_LIBS filter: ignore les modules de test halluciner
        - dep_attempts: limite des tentatives d'installation des dépendances
        - error_count: limite des essais de correction
        """
        
        # 🛡️ PROTECTION NIVEAU 1: Limite globale des cycles du graphe
        graph_steps = state.get("graph_steps", 0)
        if graph_steps >= MAX_GRAPH_STEPS:
            logger.error(f"🚨 Graph execution limit reached ({MAX_GRAPH_STEPS} steps). Exiting to verify.")
            return "verify_node"
        
        state["graph_steps"] = graph_steps + 1
        logger.debug(f"📊 Graph step {state['graph_steps']}/{MAX_GRAPH_STEPS}")
        
        # ─────────────────────────────────────────────────────────────
        
        # 🔴 PROTECTION ARCHITECTURALE: TOOLS > LLM
        # Si le scanner (outil fiable) dit 0 modules manquants,
        # on ignore ce que le LLM/diagnostic dit (peut halluciner)
        scanner_missing = state.get("scanner_missing_modules", [])
        llm_missing = state.get("missing_modules", [])
        
        if not scanner_missing and llm_missing:
            # Le scanner contredit le LLM
            logger.info(f"🧠 SCANNER > LLM: Scanner confirme 0 modules, LLM signale {llm_missing}. Ignoré.")
            logger.info(f"   (Les modules halluciner sont probablement obsolètes ou non-utilisés)")
            state["missing_modules"] = []
            llm_missing = []
        
        # 🛡️ Filtrer les modules de test (hallucinations classiques du LLM)
        TEST_LIBS = {
            "@testing-library/react-hooks",
            "@testing-library/react",
            "@testing-library/dom",
            "jest",
            "vitest",
            "react-test-utils",
            "react-dom/test-utils"
        }
        
        if llm_missing:
            filtered_missing = [m for m in llm_missing if m not in TEST_LIBS]
            if len(filtered_missing) < len(llm_missing):
                removed = set(llm_missing) - set(filtered_missing)
                logger.info(f"🧪 Modules de test ignorés (hallucinations classiques): {list(removed)}")
            state["missing_modules"] = filtered_missing
            llm_missing = filtered_missing
        
        # ─────────────────────────────────────────────────────────────
        
        target_module = state.get("target_module")
        terminal_diag = state.get("terminal_diagnostics", "")
        
        # ⚠️ Extraction des erreurs cibles vs non-cibles
        non_target_errors = state.get("non_target_errors", {})
        target_module_in_errors = target_module in non_target_errors or (not target_module and "root" in non_target_errors)
        
        # Vérifier si TSC est réussie POUR LE MODULE CIBLE
        has_tsc_errors_in_target = False
        if target_module:
            # Chercher seulement "[TSC backend]" ou "[VITE backend]" dans les rapports
            has_tsc_errors_in_target = f"[TSC {target_module}] ❌" in terminal_diag or f"[VITE {target_module}] ❌" in terminal_diag
            logger.info(f"📍 Erreurs TSC dans module cible ({target_module}): {has_tsc_errors_in_target}")
        else:
            has_tsc_errors_in_target = "❌ ÉCHEC" in terminal_diag
        
        has_structure_errors = state.get("validation_status") == "STRUCTURE_KO"
        has_missing_modules = len(llm_missing) > 0
        
        if state.get("error_count", 0) >= MAX_RETRIES and (has_tsc_errors_in_target or has_structure_errors or has_missing_modules):
            logger.error(f"🛑 Limite de tentatives atteinte ({MAX_RETRIES}).")
            return "verify_node"
            
        if has_missing_modules:
            # Protection contre les boucles infinies de dépendances
            dep_attempts = state.get("dep_attempts", 0)
            if dep_attempts < 3:
                logger.warning(f"📦 Modules manquants détectés {llm_missing}. Auto-installation ({dep_attempts+1}/3).")
                return "install_deps_node"
            else:
                logger.error(f"⚠️ Auto-installation a échoué 3 fois pour {llm_missing}. Délégation à l'IA.")
                pass
            
        if has_structure_errors:
            logger.warning("🔨 Manque de fichiers structuraux : route vers impl_node (PATCH).")
            return "impl_node"
            
        # ⚠️ CHANGE : Ne déclencher buildfix QUE si la cible a des erreurs
        if has_tsc_errors_in_target:
            logger.warning(f"🐛 Erreurs TypeScript dans module cible ({target_module}): route vers buildfix_node.")
            return "buildfix_node"
        elif target_module and non_target_errors:
            logger.warning(f"⚠️ Erreurs dans modules non-cibles IGNORÉES: {non_target_errors}. Validation continue.")
            return "verify_node"
            
        return "verify_node"

    def route_after_verify(self, state: AgentState) -> str:
        """Route après audit: APPROUVÉ → END, REJETÉ → retry impl_node (si < MAX_RETRIES)."""
        error_count = state.get("error_count", 0)
        validation_status = state.get("validation_status", "")
        
        if validation_status == "APPROUVÉ":
            logger.info(f"✅ AUDIT APPROVED: Task complete!")
            return END
        
        if error_count >= MAX_RETRIES:
            logger.error(f"🛑 AUDIT REJECTION LIMIT REACHED: {error_count}/{MAX_RETRIES} attempts exhausted")
            logger.error(f"❌ Audit errors: {state.get('audit_errors_history', [])}")
            return END
        
        logger.warning(f"⏮️ AUDIT REJECTED: Returning to impl_node for PATCH mode ({error_count}/{MAX_RETRIES} attempts used)")
        return "impl_node"

    def _build_graph(self):
        self.graph_builder.add_node("analysis_node", self.analysis_node)
        self.graph_builder.add_node("code_map_node", self.code_map_node)
        self.graph_builder.add_node("GraphicDesign_node", self.GraphicDesign_node)
        self.graph_builder.add_node("impl_node", self.impl_node)
        self.graph_builder.add_node("persist_node", self.persist_node)
        self.graph_builder.add_node("dependency_resolver_node", self.dependency_resolver_node)
        self.graph_builder.add_node("validate_dependency_node", self.validate_dependency_node)
        self.graph_builder.add_node("install_deps_node", self.install_deps_node)
        self.graph_builder.add_node("diagnostic_node", self.diagnostic_node)
        self.graph_builder.add_node("buildfix_node", self.buildfix_node)
        self.graph_builder.add_node("task_enforcer_node", self.task_enforcer_node)
        self.graph_builder.add_node("verify_node", self.verify_node)

        self.graph_builder.add_edge(START, "analysis_node")
        self.graph_builder.add_edge("analysis_node", "code_map_node")
        self.graph_builder.add_edge("code_map_node", "GraphicDesign_node")
        self.graph_builder.add_edge("GraphicDesign_node", "impl_node")
        
        self.graph_builder.add_conditional_edges("impl_node", self.route_after_impl, {"impl_node": "impl_node", "persist_node": "persist_node", "verify_node": "verify_node"})
        
        self.graph_builder.add_edge("persist_node", "dependency_resolver_node")
        self.graph_builder.add_edge("dependency_resolver_node", "validate_dependency_node")
        self.graph_builder.add_edge("validate_dependency_node", "install_deps_node")
        
        # 🔴 PROTECTION STRUCTURALE: Conditional edge après install_deps pour casser la boucle
        # Si scanner_missing_modules est vide → sorte du cycle vers verify_node
        # Sinon → retour à diagnostic_node pour vérifier installation
        self.graph_builder.add_conditional_edges("install_deps_node", self.route_from_install_deps, {
            "diagnostic_node": "diagnostic_node",
            "verify_node": "verify_node"
        })
        
        # diagnostic → task_enforcer → route (buildfix, verify, impl, install_deps)
        self.graph_builder.add_edge("diagnostic_node", "task_enforcer_node")
        self.graph_builder.add_conditional_edges("task_enforcer_node", self.route_after_enf, {
            "buildfix_node": "buildfix_node", 
            "verify_node": "verify_node",
            "impl_node": "impl_node",
            "install_deps_node": "install_deps_node"
        })
        
        # buildfix → diagnostic (verify fix worked, then decide next step)
        # Don't loop back to dependency_resolver or we'll re-detect same modules infinitely
        self.graph_builder.add_edge("buildfix_node", "diagnostic_node")
        
        self.graph_builder.add_conditional_edges("verify_node", self.route_after_verify, {END: END, "impl_node": "impl_node"})

        self.app = self.graph_builder.compile()
        logger.info("🧠 Cerveau LangGraph compilé - Nouvelle Architecture.")
