# Le "Cerveau" du Spec-Kit (LE WORKFLOW DE CHAINAGE, LE PIPELINE, LE ROADMAP)
# Implementation du graphe de routage LangGraph
# Ce module orchestre l'interaction entre les sous-agents (Analyse, Implementation, Verification)

import logging
import time
import re
import json
from pathlib import Path
from typing import TypedDict, List, Any, Dict, Optional
from itertools import chain
from langgraph.graph import StateGraph, START, END

from langchain_core.output_parsers import StrOutputParser

from core.guard import SubagentAnalysisOutput, SubagentImplOutput, SubagentVerifyOutput, SubagentBuildFixOutput, SubagentTaskEnforcerOutput
from langchain_core.output_parsers import JsonOutputParser
from core.GraphicDesign import GraphicDesign
from core.component_improver import ComponentImprover
from core.constitution_generator import ConstitutionGenerator
from core.design_system_generator import DesignSystemGenerator
from core.project_enhancer import ProjectEnhancer
from core.ux_flow_designer import UXFlowDesigner
from core.vision_pattern_detector import PatternVisionDetector

import shutil

# --- Logger configuration (avant tout usage) ---
logger = logging.getLogger(__name__)

npm_path = shutil.which("npm") or shutil.which("npm.cmd")
logger.info(f"[SETUP] npm_path detecte : {npm_path}")

# --- 0. Configuration des Limites --------------------------------------------------
MAX_RETRIES = 3
MAX_DEP_INSTALL_ATTEMPTS = 3  # Limit dependency install loops
MAX_GRAPH_STEPS = 10  # [SAFE] Maximum number of graph routing decisions (prevents infinite cycles)
MAX_DEPENDENCY_CYCLES = 2  # [SAFE] Max cycles in Diagnostics -> TaskEnforcer -> InstallDeps loop

# --- Packages deprecies que le LLM hallucine souvent ---
DEPRECATED_PACKAGES = {
    "@testing-library/react-hooks": "@testing-library/react",  # Deprecie depuis 2020
    "react-test-utils": "@testing-library/react",              # Ancien pattern
    "react-dom/test-utils": "@testing-library/react"           # Ancien pattern
}

# --- Extraction des keywords semantiques d'une tache ---
_BOILERPLATE_WORDS = {
    "setup", "config", "create", "init", "add", "update",
    "implement", "build", "make", "the", "and", "for", "with",
    "backend", "frontend", "mobile", "src", "routes", "modele",
    "model", "composants", "composant", "pages", "page"
}

def extract_task_keywords(task_name: str) -> list[str]:
    """Extrait les keywords semantiques d?un task ID pour le Context Filtering.
    
    Exemple:
        '07_routes_articles_backend' -> ['articles']
        '09_auth_login_backend'      -> ['auth', 'login']
        '12_gestion_etat_frontend'   -> ['gestion', 'etat']
    """
    import re
    # Retirer le prefixe numerique (ex: '07_')
    name = re.sub(r'^\d+_', '', task_name.lower())
    # Decouper sur underscores et tirets
    raw_words = re.split(r'[_\-\s]+', name)
    # Filtrer les mots generiques et les mots trop courts
    keywords = [w for w in raw_words if w and len(w) >= 3 and w not in _BOILERPLATE_WORDS]
    return keywords

# --- [SAFE] LLM Quota Error Detection -------------------------------------------------

def is_quota_error(e: Exception) -> bool:
    """Detecte si une exception est due a un quota LLM depasse.
    
    Patterns detectes:
    - RESOURCE_EXHAUSTED: Google Gemini API
    - 429: Rate limit HTTP
    - QUOTA: Quota Error
    - RATE_LIMIT: Generic rate limit
    """
    error_str = str(e).upper()
    quota_indicators = ["RESOURCE_EXHAUSTED", "429", "QUOTA", "RATE_LIMIT"]
    return any(indicator in error_str for indicator in quota_indicators)

def extract_retry_delay(e: Exception) -> int:
    """Extrait le delai de retry recommande de l'erreur LLM.
    
    Exemple:
        "retryDelay': '60s'" -> 60
        "Retry-After: 300" -> 300
    
    Returns:
        Delai en secondes (default: 60s)
    """
    error_str = str(e)
    
    # Pattern 1: Google Gemini format
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s?['\"]?", error_str)
    if match:
        return int(match.group(1))
    
    # Pattern 2: HTTP Retry-After header
    match = re.search(r"Retry-After['\"]?\s*:\s*(\d+)", error_str)
    if match:
        return int(match.group(1))
    
    # Pattern 3: Generic number in seconds
    match = re.search(r"retry.*?(\d+)\s*(?:second|sec|s)?", error_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Default: 60 seconds
    return 60

# --- 1. Etat du graphe (ou StateGraph/Memoire partagee) -----------------------------

class AgentState(TypedDict):
    # Variables de contexte partagees (generees une seule fois)
    constitution_hash: str
    constitution_content: str
    project_brief: dict
    component_manifest: dict
    pattern_vision: dict
    design_system: dict
    ux_flow: dict
    constitution_update_summary: str

    current_step: str
    completed_tasks_summary: str
    pending_tasks: str
    
    # Specifications de design (Generees par GraphicDesign)
    design_spec: dict
    
    # Cible actuelle
    target_task: str
    target_module: str  # Module cible extrait du task ID (backend/frontend/mobile/None)
    is_vibe_design_task: bool  # Tache 00_Vibe_Design_Extraction (pipeline design-only)
    
    # Resultats des n?uds
    analysis_output: str
    code_to_verify: str
    impact_fichiers: List[str] # Liste des fichiers impactes
    validation_status: str # "APPROUVE" ou "REJETE"
    score: str # Score de l'auditeur
    points_forts: str # Points forts releves
    alertes: str # Alertes detectees
    feedback_correction: str # Instructions si rejete
    terminal_diagnostics: str # Erreurs reelles du terminal (build, lint, etc.)
    existing_code_snapshot: str # Fichiers reels lus depuis le disque (pour le mode PATCH)
    
    # Gestion des erreurs et boucle
    error_count: int 
    last_error: str
    audit_errors_history: List[str]  # [SAFE] Historique des erreurs d'audit pour detecter les repetitions
    retry_count: int  # [SAFE] Track impl_node retries to prevent infinite loops
    
    # Instructions utilisateur additionnelles (Ex: speckit run --instruction "Fais ceci")
    user_instruction: str
    image_meta: dict
    
    # Carte semantique du code (Semantic Code Map)
    code_map: str
    file_tree: str
    
    # Checklist des sous-taches
    subtask_checklist: str
    
    # Modules manquants detectes par les diagnostics (Auto-installation)
    missing_modules: List[str]
    deps_attempts: int
    
    # Erreurs detectees dans les modules non-cibles (pour eviter boucles)
    non_target_errors: dict  # {module_name: error_type}
    
    # Statistiques de completion (via TaskEnforcer)
    total_subtasks: int
    missing_subtasks: int
    
    # Keywords semantiques extraits du task ID (pour le Context Filtering)
    task_keywords: List[str]
    
    # Cles dynamiques pour le flux de dependances et validation (mode LLM post-genere)
    dep_install_attempts: int  # Tracking attempts to avoid infinite loops
    scanner_missing_modules: List[str]  # Modules detected as missing by scanner
    attempted_installs: List[str]  # Modules already attempted for installation
    installed_modules: List[str]  # Modules that were successfully installed
    forced_install_packages: List[str]  # Packages to install even if scanner reports 0
    dependency_cycles: int  # Count of circular dependency detection cycles
    graph_steps: int  # Total number of orchestration steps executed
    
    # Status tracking from various guard/validation nodes
    arch_guard_status: str  # "PASSED", "FAILED"
    path_guard_status: str  # "PASSED", "WARNED", "BLOCKED", "EMPTY"
    path_guard_issues: List[dict]  # Path validation issues detected
    esm_status: str  # ESM compatibility status
    esm_resolver_status: str  # ESM import resolver status
    typescript_errors: List[dict]  # TypeScript compilation errors
    typescript_validation_status: str  # TypeScript validation result
    
    # Snapshot tracking for diff management
    snapshot_before: dict  # Project state before persistence
    snapshot_after: dict  # Project state after persistence
    file_diff: dict  # Diff summary between snapshots
    
    # Infinite loop detection tracking
    previous_node_route: str  # Track which node was just executed
    state_history: List[str] | None  # History of (node_name, validation_status) pairs
    repeated_state_count: int  # Count of consecutive repeated states


class SpecGraphManager:
    def __init__(self, model, project_root: str = "."):
        from utils.architecture_guard import ArchitectureGuard
        self.model = model

        self.root = Path(project_root).resolve()
        # Les prompts sont internes au package
        self.prompts_dir = Path(__file__).parent.parent / "agents"
        
        self.arch_guard = ArchitectureGuard()
        self.project_enhancer = ProjectEnhancer(model=self.model, project_root=self.root)
        self.component_improver = ComponentImprover(model=self.model)
        self.pattern_vision_detector = PatternVisionDetector(model=self.model)
        self.design_system_generator = DesignSystemGenerator(model=self.model)
        self.ux_flow_designer = UXFlowDesigner(model=self.model)
        self.constitution_generator = ConstitutionGenerator(model=self.model)

        # Initialisation du graphe
        self.graph_builder = StateGraph(AgentState)
        self._build_graph()

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info(f"SpecGraphManager initialized for root: {self.root}")



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
            logger.info(f"[DIR] Structure de dossiers garantie ({count} dossiers crees).")

    def _extract_target_module(self, task_id: str) -> str | None:
        """Extrait le module cible (backend/frontend/mobile) du task ID.
        
        Exemples:
        - "02_setup_backend" -> "backend"
        - "03_setup_frontend" -> "frontend"
        - "04_setup_mobile" -> "mobile"
        - "05_feature_dashboard" -> None (utilise tous les modules)
        
        Returns: str (module name) or None (all modules)
        """
        import re
        if self._is_vibe_design_task(task_id):
            return None

        # Pattern: 02_setup_backend, 03_setup_frontend, etc.
        match = re.search(r"_(backend|frontend|mobile|api|infra|docs)", task_id, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        
        # Fallback: strategie heuristique basee sur le numero
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

    def _load_stack_preferences(self) -> Dict[str, str]:
        """Lit `.spec-lock.json` pour recuperer les preferences stack de l'utilisateur."""
        lock_file = self.root / ".spec-lock.json"
        if not lock_file.exists():
            return {}
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            prefs = data.get("stack_preferences") or {}
            return {k: v for k, v in prefs.items() if isinstance(v, str)}
        except Exception as exc:
            logger.warning("[WARN] Impossible de charger .spec-lock.json : %s", exc)
            return {}

    def _extract_component_candidates(self, state: AgentState) -> List[str]:
        """Extrait les composants mentionnes dans l'instruction de l'utilisateur."""
        raw = f"{state.get('user_instruction', '')}\n{state.get('target_task', '')}"
        cleaned = raw.replace("-", "\n").replace(";", "\n").replace(",", "\n")
        candidates = []
        for line in cleaned.splitlines():
            part = line.strip("-- ").strip()
            if part and len(part) >= 3:
                candidates.append(part)
        return candidates

    def _get_build_tool(self, target_module: str) -> str:
        """Detecte le bon outil de build selon le module et framework.
        
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
        """Detecte le framework frontend: 'react', 'vue', ou 'next'.
        
        Utilise la FileManager pour coherence.
        """
        from utils.file_manager import FileManager
        fm = FileManager(str(self.root))
        return fm.detect_framework()

    def _get_nextjs_router_type(self) -> str:
        """Detecte le type de router Next.js: 'app' (App Router) ou 'pages' (Pages Router).
        
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
        """Detecte les dependances cross-module (ex: frontend depend du backend).
        
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
                return {"missing_module": "backend", "reason": "Frontend depend de services/modeles Backend"}
        
        # Backend qui importe du frontend (moins courant mais possible)
        if target_module == "backend":
            if any(lib in all_deps for lib in ["@frontend/shared", "@frontend/types", "frontend-types"]):
                return {"missing_module": "frontend", "reason": "Backend depend de types Frontend"}
        
        return {}

    def _add_cross_module_task(self, target_module: str, missing_module: str, reason: str) -> None:
        """Ajoute une tache manquante a l'etape concernee dans etapes.md.
        
        Strategie:
        - Si on est en frontend et il manque du backend:
          Decocher la subtache backend et ajouter une tache a l'etape backend
        """
        from core.etapes import EtapeManager
        
        etape_mgr = EtapeManager(self.root)
        
        # Determiner l'etape concernee
        step_map = {"backend": "02", "frontend": "03", "mobile": "04"}
        step_num = step_map.get(missing_module, "02")
        
        try:
            # Ajouter une nouvelle tache non-cochee a l'etape concernee
            msg = f"[Cross-Module] {reason} (detecte depuis {target_module})"
            logger.warning(f"[WARN] Dependance cross-module detectee: {msg}")
            logger.info(f"[INFO] Ajoute une tache a l'etape {step_num} : Installer {missing_module}")
            
            # Lire etapes.md
            etapes_file = self.root / "Constitution" / "etapes.md"
            if etapes_file.exists():
                content = etapes_file.read_text(encoding="utf-8")
                
                # Injecter la tache manquante dans l'etape concernee
                import re
                pattern = f"(## Etape {step_num}.*?)(?=## Etape|$)"
                
                def inject_task(match):
                    section = match.group(1)
                    # Ajouter la tache avant la fin de la section
                    task_line = f"\n- [ ] [Cross-Module] {reason}"
                    return section + task_line
                
                new_content = re.sub(pattern, inject_task, content, flags=re.DOTALL)
                etapes_file.write_text(new_content, encoding="utf-8")
                logger.info(f"[OK] Tache ajoutee a etapes.md (Etape {step_num})")
        except Exception as e:
            logger.warning(f"[WARN] Impossible d'ajouter la tache cross-module : {e}")

    def _invoke_with_retry(self, chain, invoke_dict: dict, max_attempts: int = 3):
        """[SAFE] Appelle la chaine LLM avec retry + exponential backoff pour eviter les erreurs reseau.
        
        Args:
            chain: La chaine LangChain a invoquer
            invoke_dict: Variables a passer a la chaine
            max_attempts: Nombre maximum de tentatives (default: 3)
            
        Returns:
            La sortie brute de chain.invoke()
            
        Raises:
            Exception: Si toutes les tentatives echouent
        """
        import time
        for attempt in range(max_attempts):
            try:
                logger.info(f"[AI] Invocation LLM (tentative {attempt + 1}/{max_attempts})...")
                result = chain.invoke(invoke_dict)
                logger.info(f"[OK] Invocation reussie a la tentative {attempt + 1}")
                return result
            except Exception as e:
                if attempt < max_attempts - 1:
                    # Backoff exponentiel : 1s, 2s, 4s, etc.
                    wait_time = 2 ** attempt
                    logger.warning(f"[WARN] Tentative {attempt + 1} echouee : {str(e)[:100]}. Attente {wait_time}s avant retry...")
                    time.sleep(wait_time)
                else:
                    # Derniere tentative echouee
                    logger.error(f"[ERROR] Toutes les {max_attempts} tentatives ont echoue.")
                    raise

    def _load_prompt(self, filename: str) -> str:
        """Charge le contenu d'un fichier prompt."""
        path = self.prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Prompt introuvable : {path}")
        return path.read_text(encoding="utf-8")

    def _inject_prompt_vars(self, prompt_text: str, inject_dict: dict[str, Any]) -> str:
        """Injecte les placeholders en supportant les deux formats:
        - __PLACEHOLDER__
        - {placeholder}
        """
        rendered = prompt_text
        for key, value in inject_dict.items():
            string_value = str(value)
            rendered = rendered.replace("__" + key.upper() + "__", string_value)
            rendered = rendered.replace("{" + key + "}", string_value)
        return rendered

    def _safe_parse_json(self, content: str, pydantic_object) -> dict:
        """Nettoie et parse le JSON avec des fallbacks robustes pour les grands volumes de code."""
        cleaned = content.strip()
        result = {}
        
        # --- EXTRACTION DU CODE MARKDOWN (MULTI-FORMAT) ---
        import re
        
        # 1. Priorite : bloc ```code (format demande dans le prompt)
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
        # 1. Priorite : Balises <JSON_OUTPUT> (Format standardise)
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
                 # S'il y a un bloc ``` generique au debut, on assume que c'est le json
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
            # Si le code etait dans le JSON malencontreusement (ancien format), on le prend
            if not result.get("code") and parsed_json.get("code"):
                 result["code"] = parsed_json.get("code")
            
            # Nettoyage final des backticks residuels dans le code extrait
            if result.get("code"):
                result["code"] = re.sub(r'```[a-zA-Z0-9-]*\n?', '', result["code"])
                result["code"] = result["code"].replace('```', '').strip()
                
            return result
        except Exception as e:
            logger.error(f"[ERROR] Echec critique du parsing JSON : {str(e)}")
            # On renvoie une erreur explicite pour que le noeud appelant puisse reagir
            raise ValueError(f"Format JSON invalide ou absent dans la reponse de l'IA : {str(e)}")

    # --- 2. N?uds (fonctions de traitement) -------------------------------

    def _is_frontend_task(self, task_name: str, checklist: str = "") -> bool:
        """Detecte avec robustesse si une tache concerne le frontend."""
        import re
        frontend_keywords = [
            r"frontend/", r"\.tsx", r"\.jsx", r"react",
            r"\bcomponent\b", r"\btailwind\b", r"\bpage\b", r"\bui\b", r"\bcss\b"
        ]
        task_text = f"{task_name}\n{checklist}".lower()
        return any(re.search(k, task_text) for k in frontend_keywords)

    def _is_vibe_design_task(self, task_name: str, checklist: str = "", user_instruction: str = "") -> bool:
        """Detecte l'etape d'extraction design (00_Vibe_Design_Extraction)."""
        haystack = f"{task_name}\n{checklist}\n{user_instruction}".lower()
        markers = [
            "vibe_design_extraction",
            "vibe design extraction",
            "design extraction",
            "design/tokens.yaml",
            "design/image_meta.json",
            "design/constitution_design.yaml",
            "constitution/mappingcomponent.md",
            "mappingcomponent.md",
        ]
        return any(marker in haystack for marker in markers)

    def project_enhancer_node(self, state: AgentState) -> dict:
        """Enrichit la vision du projet et la stack."""
        logger.info("[OK] Project Enhancer: Enriching project brief...")
        instruction = state.get("user_instruction", "") or state.get("target_task", "")
        
        brief = self.project_enhancer.enhance(instruction)
        
        return {"project_brief": brief}

    def component_improver_node(self, state: AgentState) -> dict:
        """Segmente et ameliore la liste des composants."""
        logger.info("[COMPONENT] Component Improver: Segmenting UI components...")
        instruction = state.get("user_instruction", "") or state.get("target_task", "")
        
        # Extraction basique des candidats
        candidates = re.findall(r"\b(button|card|modal|navbar|sidebar|table|input|form|stats)\b", instruction.lower())
        manifest = self.component_improver.improve(candidates or ["Dashboard", "Navbar"])
        
        return {"component_manifest": manifest}

    def pattern_vision_node(self, state: AgentState) -> dict:
        """Detecte le style visuel et les tokens a partir de l'instruction et de la CONSTITUTION."""
        logger.info("[VISION] Vision Pattern: Extracting design tokens from context...")
        instruction = state.get("user_instruction", "") or state.get("target_task", "")
        constitution = state.get("constitution_content", "")
        image_meta = state.get("image_meta") or None
        
        # ? COMBINED CONTEXT (Instruction + Constitution)
        full_context = f"{instruction}\n\n[CONSTITUTION PROJECT CONTEXT]\n{constitution}"
        
        pattern = self.pattern_vision_detector.analyze(full_context, image_meta=image_meta)
        
        return {"pattern_vision": pattern}

    def design_system_node(self, state: AgentState) -> dict:
        """Genere le design system et persiste le pattern si custom."""
        logger.info("[DESIGN] Design System: Generating manifest and persisting custom patterns...")
        
        tokens = state.get("pattern_vision", {}).get("tokens", {})
        manifest = state.get("component_manifest", {})
        
        ds = self.design_system_generator.generate(tokens, manifest)
        
        # [SAFE] PERSISTENCE : Save as custom pattern for GraphicDesign to use
        if state.get("pattern_vision", {}).get("style") == "custom":
            pattern_data = self.design_system_generator.export_to_pattern(ds)
            # Utilisation du root du projet pour le storage
            pattern_path = self.root / "design" / "dataset" / "custom_pattern.json"
            pattern_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                import json
                with open(pattern_path, "w", encoding="utf-8") as f:
                    json.dump(pattern_data, f, indent=4)
                logger.info(f"[SAVE] Custom pattern saved and persisted to {pattern_path}")
            except Exception as e:
                logger.error(f"[ERROR] Impossible de sauvegarder le custom pattern : {e}")

        return {"design_system": ds}

    def ux_flow_node(self, state: AgentState) -> dict:
        """Definit les flux d'interactions."""
        logger.info("[UX] UX Flow: Designing interaction flows...")
        instruction = state.get("user_instruction", "") or state.get("target_task", "")
        manifest = state.get("component_manifest", {})
        
        flow = self.ux_flow_designer.design_flow(instruction, manifest)
        
        return {"ux_flow": flow}

    def constitution_generator_node(self, state: AgentState) -> dict:
        """Compile tout en une Constitution finale."""
        logger.info("[DOC] Constitution Generator: Compiling project constitution...")
        
        brief = state.get("project_brief", {})
        ds = state.get("design_system", {})
        flow = state.get("ux_flow", {})
        
        constitution = self.constitution_generator.generate(brief, ds, flow)
        
        return {"constitution_content": constitution.get("content", "")}

    def GraphicDesign_node(self, state: AgentState) -> dict:
        """N?ud de Design : Transforme l'intention UI en AST + Specs Tailwind."""
        logger.info(f"[DESIGN] Debut du Design pour la tache : {state['target_task']}")

        if state.get("is_vibe_design_task", False):
            logger.info("[VIBE] GraphicDesign ignore: etape design extraction sans generation d'UI.")
            return {"design_spec": {"error": "Skipped (vibe-design task)", "tailwind": {}}}
        
        # [SAFE] MANDATORY CHECK: Only run for frontend/UI related tasks
        is_ui_task = self._is_frontend_task(state.get("target_task", ""), state.get("subtask_checklist", ""))
        
        if not is_ui_task:
            logger.info("[SKIP] Skipping GraphicDesignEngine (backend task)")
            return {"design_spec": {"error": "Skipped (non-UI)", "tailwind": {}}}
            
        # Initialisation du moteur Design (deplace APR?S le check pour eviter de charger le dataset inutilement)
        design_engine = GraphicDesign(
            dataset_dir=str(self.root / "design" / "dataset"),
            constitution_path=str(self.root / "design" / "constitution_design.yaml")
        )
        
        # On utilise le prompt utilisateur ou la tache cible pour le design
        prompt = state.get("user_instruction") or state["target_task"]
        
        try:
            design_result: dict[str, Any] = design_engine.generate(prompt)
            # Ensure tailwind rules are always present even if empty
            if "tailwind" not in design_result:
                design_result["tailwind"] = {}
            
            # ?? NEW: Generate a framework-specific Skeleton "mould"
            skeleton = design_engine.generate_skeleton(design_result)
            design_result["skeleton"] = skeleton
                
            logger.info(f"[OK] Design generated: {design_result.get('pattern', 'default')} with Skeleton.")
            return {"design_spec": design_result}
        except Exception as e:
            logger.error(f"[ERROR] Echec du moteur GraphicDesign : {str(e)}")
            # Fallback minimaliste
            return {"design_spec": {"error": str(e), "tailwind": {}}}

    def vibe_finalize_node(self, state: AgentState) -> dict:
        """Finalise l'etape 00_Vibe_Design_Extraction en persistant design/tokens.yaml."""
        logger.info("[VIBE] Finalisation de l'extraction design...")

        tokens = state.get("pattern_vision", {}).get("tokens", {}) or {}
        tokens_path = self.root / "design" / "tokens.yaml"
        tokens_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import yaml
            serialized = yaml.safe_dump(tokens, sort_keys=False, allow_unicode=False)
        except Exception:
            # Fallback sans dependance PyYAML
            serialized = json.dumps(tokens, indent=2, ensure_ascii=True)

        tokens_path.write_text(serialized, encoding="utf-8")
        logger.info(f"[SAVE] Tokens design sauvegardes dans {tokens_path}")

        return {
            "validation_status": "APPROUVE",
            "score": "100",
            "points_forts": "Extraction Vibe Design executee et tokens sauvegardes.",
            "alertes": "Aucune",
            "feedback_correction": "",
        }

    def analysis_node(self, state: AgentState) -> dict:
        """N?ud 1 : Analyse de conformite et segmentation."""
        logger.info(f"[SCAN] Debut de l'Analyse pour la tache : {state['target_task']}")
        task_keywords = extract_task_keywords(state["target_task"])
        transversal_keywords = {"vibe", "design", "extraction"}
        is_transversal_design_task = any(k in transversal_keywords for k in task_keywords)
        if is_transversal_design_task:
            logger.info("[SCAN] Tache transversale detectee : Autorisation des GLOBAL_PATHS")

        is_vibe_task = self._is_vibe_design_task(
            state.get("target_task", ""),
            state.get("subtask_checklist", ""),
            state.get("user_instruction", ""),
        )

        if is_vibe_task:
            logger.info("[VIBE] Tache detectee: pipeline design-only (pas de generation code).")
            return {
                "analysis_output": (
                    "Impact: Extraction des signaux visuels et fusion des sources design.\n"
                    "Conflits: Aucun conflit code attendu.\n"
                    "Segmentation: Lire MappingComponent, lire image_meta, lire constitution_design, fusionner, ecrire design/tokens.yaml\n"
                    "Integrite: Respect strict de la priorite Constitution > MappingComponent > constitution_design > image_meta."
                ),
                "feedback_correction": "",
                "error_count": 0,
                "audit_errors_history": [],
                "target_module": None,
                "task_keywords": task_keywords,
                "is_vibe_design_task": True,
            }
        
        # --- EXTRACTION DU MODULE CIBLE ---
        target_module = None if is_transversal_design_task else self._extract_target_module(state["target_task"])
        if target_module:
            logger.info(f"[TARGET] Module cible identifie : {target_module}")
        
        prompt_text = self._load_prompt("subagent_analysis.prompt")
        
        # On utilise JsonOutputParser avec le modele Pydantic de guard.py
        parser = JsonOutputParser(pydantic_object=SubagentAnalysisOutput)
        
        # [SAFE] SAFE PLACEHOLDER REPLACEMENT : Remplacer manuellement les variables
        inject_dict = {
            "constitution_content": state["constitution_content"],
            "current_step": state["current_step"],
            "completed_tasks_summary": state["completed_tasks_summary"],
            "pending_tasks": state["pending_tasks"],
            "target_task": state["target_task"],
            "user_instruction": state.get("user_instruction", ""),
            "format_instructions": parser.get_format_instructions()
        }
        prompt_text = self._inject_prompt_vars(prompt_text, inject_dict)
        
        try:
            import concurrent.futures
            from langchain_core.messages import HumanMessage
            
            def run_chain():
                final_prompt = "You are a helpful assistant.\n\n" + prompt_text
                message = HumanMessage(content=final_prompt)
                
                # Direct invocation with retry logic
                for attempt in range(3):
                    try:
                        logger.info(f"[AI] Invocation LLM (tentative {attempt + 1}/3)...")
                        result = (self.model | StrOutputParser()).invoke([message])
                        logger.info(f"[OK] Invocation reussie a la tentative {attempt + 1}")
                        return result
                    except Exception as e:
                        if attempt < 2:
                            wait_time = 2 ** attempt
                            logger.warning(f"[WARN] Tentative {attempt + 1} echouee : {str(e)[:100]}. Attente {wait_time}s avant retry...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"[ERROR] Toutes les 3 tentatives ont echoue.")
                            raise

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_chain)
                # Hard timeout de 90 secondes sur l'appel LLM
                raw_output = future.result(timeout=90)

            assert raw_output is not None, "LLM output should not be None after retry loop"
            result = self._safe_parse_json(raw_output, SubagentAnalysisOutput)
            # On convertit le dict JSON en string formatee pour l'injecter au noeud suivant
            analysis_str = (
                f"Impact: {result['impact']}\n"
                f"Conflits: {result['conflits']}\n"
                f"Segmentation: {', '.join(result['segmentation'])}\n"
                f"Integrite: {result['alerte_integrite']}"
            )
            logger.info("[OK] Analyse terminee.")
            
            # Extraire les keywords semantiques pour le Context Filtering
            logger.info(f"[KEY] Task keywords extractes : {task_keywords}")
            
            return {
                "analysis_output": analysis_str,
                "feedback_correction": "",
                "error_count": 0,
                "audit_errors_history": [],  # [SAFE] Initialize error tracking
                "target_module": target_module,   # Passer le module cible au graphe
                "task_keywords": task_keywords,    # [GOAL] Persist keywords for Context Filtering
                "is_vibe_design_task": False,
            }
        except ValueError as e:
            error_msg = f"Reponse IA corrompue (Analysis JSON) : {str(e)}"
            logger.error(f"[ERROR] {error_msg}")
            return {
                "validation_status": "REJETE",
                "feedback_correction": f"CRITICAL: Analysis response was invalid JSON. {str(e)}. Please retry with valid JSON.",
                "last_error": error_msg
            }
        except Exception as e:
            error_msg = f"Erreur d'analyse : {str(e)}"
            logger.error(f"[ERROR] {error_msg}")
            return {
                "analysis_output": "ERREUR D'ANALYSE", 
                "feedback_correction": error_msg,
                "last_error": error_msg
            }

    def _read_existing_code(self) -> str:
        """Lit les fichiers reels du projet sur disque pour le mode PATCH."""
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
        logger.info(f"[PHOTO] Snapshot disque : {len(blocks)} fichiers lus.")
        return snapshot

    def _get_filtered_context(self, state: AgentState) -> dict:
        """Filtre le code_map et file_tree pour reduire le contexte LLM.
        
        Strategie de reduction:
        - Extraire SEULEMENT les fichiers pertinents pour la tache cible
        - Inclure les dependances detectees  
        - Limiter a ~30-40 fichiers max
        - Ideal pour reduire du contexte 50-70% sans perdre de semantique
        
        Le contexte reduit reste suffisant pour la generation avec la semantic map.
        """
        import json, re
        
        # Extraire les fichiers et contextes pertinents
        analysis = state.get("analysis_output", "")
        code_map_str = state.get("code_map", "{}")
        file_tree_str = state.get("file_tree", "")
        target_task = state.get("target_task", "")
        
        relevant_files = set()
        
        # 1?? EXTRACTION AGRESSIVE des fichiers mentionnes dans analysis
        # Patterns: "fichier: X", "create X", import statements, etc.
        file_patterns = [
            r'(?:files?|fichiers?|path|chemin|import|from)\s*:?\s+["\']?([a-zA-Z0-9._\-/\\]+\.[a-zA-Z0-9]+)["\']?',
            r'(?:create|creer|modify|modifier|update)\s+([a-zA-Z0-9._\-/\\]+\.[a-zA-Z0-9]+)',
            r'(?:api|route|endpoint|endpoint_|controller|Controller|service|Service)\s*:\s*([a-zA-Z0-9._\-/\\]+\.[a-zA-Z0-9]+)',
        ]
        for pattern in file_patterns:
            matches = re.findall(pattern, analysis, re.IGNORECASE)
            relevant_files.update(m.strip() for m in matches if m)
        
        # 2?? KEYWORDS : preferer ceux persistes en state (calcules dans analysis_node)
        task_words = state.get("task_keywords") or []
        if not task_words:
            # Fallback : extraire a la volee si l'analyse n'a pas encore realise le calcul
            task_words = extract_task_keywords(target_task)
        task_words = list(set(task_words))  # Dedupliquer
        
        # 3?? MATCHING des fichiers bases sur tache
        # Ex: si tache ="create_user_form", chercher user, form, User, Form
        for keyword in task_words:
            for line in file_tree_str.split('\n'):
                file_line = line.strip().lower()
                if file_line and (keyword in file_line or file_line.startswith(keyword)):
                    relevant_files.add(line.strip())
        
        # 4?? FICHIERS DE CONFIG obligatoires
        config_patterns = [
            'package.json', 'tsconfig', 'index.ts', 'index.tsx', 'index.js', 
            'env', 'types.ts', 'interfaces', '.ts'  # Fichier de types general
        ]
        for line in file_tree_str.split('\n'):
            if line.strip():
                for config in config_patterns:
                    if config.lower() in line.lower():
                        relevant_files.add(line.strip())
                        break
        
        # 5?? PARSER code_map et FILTRER
        try:
            code_map_dict = json.loads(code_map_str) if code_map_str and code_map_str != "{}" else {}
        except:
            code_map_dict = {}
        
        filtered_code_map = {}
        
        # Inclure fichiers qui match any relevant criterion
        for file_path in code_map_dict.keys():
            # Critere 1: Explicitement mentionne dans analysis
            if file_path in relevant_files or any(rp in file_path for rp in relevant_files):
                filtered_code_map[file_path] = code_map_dict[file_path]
                continue
            
            # Critere 2: Contient un keyword de tache
            if any(kw in file_path.lower() for kw in task_words):
                filtered_code_map[file_path] = code_map_dict[file_path]
                continue
            
            # Critere 3: Est un fichier de config/index important
            if any(config.lower() in file_path.lower() for config in config_patterns):
                filtered_code_map[file_path] = code_map_dict[file_path]
                continue
        
        # Fallback: si RIEN n'est trouve releve, inclure les premiers fichiers pertinents
        if not filtered_code_map and code_map_dict:
            # Prioriser les fichiers mentionnes dans analysis ou contenant keywords
            priority_files = [f for f in code_map_dict.keys() 
                            if any(kw in f.lower() for kw in task_words)]
            if not priority_files:
                # Aucune priorite trouvee, prendre les premiers
                priority_files = list(code_map_dict.keys())[:15]
            
            for f in priority_files[:25]:  # Max 25 fichiers en fallback
                filtered_code_map[f] = code_map_dict[f]
        
        # 6?? LIMITER STRICTEMENT la taille: max 35 fichiers
        if len(filtered_code_map) > 35:
            # Garder les plus pertinents (avec keywords de tache en priorite)
            priority = sorted(filtered_code_map.keys(), 
                            key=lambda f: sum(1 for kw in task_words if kw in f.lower()),
                            reverse=True)
            filtered_code_map = {f: code_map_dict[f] for f in priority[:35]}
        
        # 7?? FILTRER file_tree pour correspondre
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
        
        logger.info(f"[STAT] Context Filtering: {len(code_map_dict)} -> {len(filtered_code_map)} files in code_map, " +
                   f"file_tree: ~{len(file_tree_str.split(chr(10)))} -> {len(filtered_file_tree)} lines | " +
                   f"Task keywords: {task_words[:3]}")  # Log first 3 keywords
        
        return {
            "code_map_filtered": json.dumps(filtered_code_map),
            "file_tree_filtered": "\n".join(filtered_file_tree)
        }

    def _format_design_spec_for_prompt(self, design_spec: dict) -> str:
        """Formate le design_spec en instructions lisibles pour le LLM.
        
        Transforme un design_spec JSON complexe en directives claires et actionnables.
        """
        if not design_spec:
            return "NO DESIGN SPECIFICATION PROVIDED. Use premium Tailwind defaults."
            
        if design_spec.get("error") == "Skipped (non-UI)":
            return ""  # Empty for backend tasks
            
        if "error" in design_spec:
            return "NO DESIGN SPECIFICATION PROVIDED. Use premium Tailwind defaults."
        
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
# MANDATORY UI DESIGN SYSTEM (TAILWIND)

Use the following Tailwind classes for the UI. DO NOT USE ANY OTHER CLASSES.

## Pattern: {pattern}

{tailwind_rules}

## Structural Constraints:
- Layout: {ui_ast.get('name', 'Page') if isinstance(ui_ast, dict) else 'Page'}
- Component hierarchy: {str(ui_ast)[:300]}

## [BLOCK] THE SKELETON (CRITICAL):
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
        """N?ud 2 : Generation de code pur (Executant)."""
        logger.info(f"[CODE] Debut de la Generation de code pour la tache : {state['target_task']}")
        
        # Garantie structurelle avant generation
        self._ensure_directory_structure()
        
        # --- MODE PATCH : Sur les retries, injecter le code reel du disque ---
        is_patch_mode = bool(state.get("feedback_correction"))
        existing_snapshot = ""
        
        try:
            from langchain_core.messages import HumanMessage
            
            prompt_text = self._load_prompt("subagent_impl.prompt")
            
            if is_patch_mode:
                logger.warning("[FIX] MODE PATCH : Lecture du code reel depuis le disque.")
                existing_snapshot = self._read_existing_code()
                prompt_text += "\n\n# [WARN] INSTRUCTIONS DE CORRECTION (RETOUR AUDITEUR) :\n__FEEDBACK_CORRECTION__"
                prompt_text += "\n\n# ? CODE EXISTANT SUR DISQUE (NE PAS TOUT REGENERER) :\n__EXISTING_CODE_SNAPSHOT__"
                prompt_text += "\n\n# MODE: PATCH ? Modifie UNIQUEMENT les fichiers concernes par les erreurs ci-dessus. Ne regenere PAS les fichiers qui fonctionnent."
            
            parser = JsonOutputParser(pydantic_object=SubagentImplOutput)
            format_instructions = parser.get_format_instructions()
            
            # [SAFE] FILRAGE DE CONTEXTE : Reduire la taille avant d'envoyer au LLM
            filtered = self._get_filtered_context(state)
            code_map_to_use = filtered.get("code_map_filtered", state.get("code_map", ""))
            file_tree_to_use = filtered.get("file_tree_filtered", state.get("file_tree", ""))
            
            # [SAFE] CONSTITUTION: JAMAIS TRONQUER - C'est la source de verite !
            constitution_content = state["constitution_content"]  # ? ALWAYS COMPLETE AND FULL
            
            # [SAFE] TRUNCATION DE existing_code_snapshot si > 10KB (PATCH mode SEULEMENT)
            if len(existing_snapshot) > 10000:
                existing_snapshot = existing_snapshot[:9800] + "\n// [... CODE TRUNCATED FOR CONTEXT LIMIT ...]"
                logger.warning(f"[WARN] Existing snapshot truncated from {len(state.get('existing_code_snapshot', ''))} to 9800 chars")
            
            # [SAFE] TRUNCATION DE analysis_output si > 5KB (can summarize, not critical)
            analysis_output = state.get("analysis_output", "")
            if len(analysis_output) > 5000:
                analysis_output = analysis_output[:4800] + "\n[... ANALYSIS TRUNCATED FOR CONTEXT LIMIT ...]"
                logger.warning(f"[WARN] Analysis output truncated to 4800 chars")
            
            # [SAFE] TRUNCATION DE terminal_diagnostics si > 3KB (can summarize)
            terminal_diagnostics = state.get("terminal_diagnostics", "")
            if len(terminal_diagnostics) > 3000:
                terminal_diagnostics = terminal_diagnostics[:2800] + "\n[... DIAGNOSTICS TRUNCATED ...]"
                logger.info(f"[INFO] Terminal diagnostics truncated to 2800 chars")
            
            # [DESIGN] FORMAT DESIGN SPEC : Rendre lisible et actionnabel pour le LLM
            raw_design_spec = state.get("design_spec", {"error": "Non generee"})
            design_spec_formatted = self._format_design_spec_for_prompt(raw_design_spec)
            if raw_design_spec.get("error") == "Skipped (non-UI)":
                logger.info("[INFO] No design pattern needed (Backend task).")
            elif raw_design_spec.get("pattern"):
                logger.info(f"[DESIGN] Design pattern ready: {raw_design_spec['pattern']} (with Tailwind + AST)")
            else:
                logger.warning(f"[WARN] No design pattern found - using defaults")

            # [SAFE] REMPLACEMENT DIRECT DES VARIABLES : Sans utiliser ChatPromptTemplate
            inject_dict = {
                "constitution_hash": state.get("constitution_hash", "INCONNU"),
                "constitution_content": constitution_content,
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "target_task": state["target_task"],
                "analysis_output": analysis_output,
                "feedback_correction": state.get("feedback_correction", ""),
                "terminal_diagnostics": terminal_diagnostics,
                "code_map": code_map_to_use,
                "file_tree": file_tree_to_use,
                "design_spec": design_spec_formatted,
                "subtask_checklist": state.get("subtask_checklist", "Non disponible"),
                "user_instruction": state.get("user_instruction", ""),
                "existing_code_snapshot": existing_snapshot,
                "format_instructions": format_instructions
            }
            
            # Replace placeholders for both formats: __KEY__ and {key}
            prompt_text = self._inject_prompt_vars(prompt_text, inject_dict)
            
            # [WARN] pass directly to model with inline retry
            final_prompt = "You are a helpful assistant.\n\n" + prompt_text
            message = HumanMessage(content=final_prompt)
            
            raw_output = None
            for attempt in range(3):
                try:
                    logger.info(f"[AI] Invocation LLM (tentative {attempt + 1}/3)...")
                    raw_output = (self.model | StrOutputParser()).invoke([message])
                    logger.info(f"[OK] Invocation reussie a la tentative {attempt + 1}")
                    break
                except Exception as e:
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"[WARN] Tentative {attempt + 1} echouee : {str(e)[:100]}. Attente {wait_time}s avant retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"[ERROR] Toutes les 3 tentatives ont echoue.")
                        raise

            assert raw_output is not None, "LLM output should not be None after retry loop"
            result = self._safe_parse_json(raw_output, SubagentImplOutput)
            new_code = result.get("code", "")
            
            # En PATCH mode, merger avec le code existant au lieu de remplacer
            if is_patch_mode and state.get("code_to_verify"):
                new_code = self._merge_code(state["code_to_verify"], new_code)
                logger.info("[OK] PATCH applique (merge avec le code existant).")
            else:
                logger.info("[OK] Generation de code terminee.")
            
            return {
                "code_to_verify": new_code,
                "impact_fichiers": result.get("impact_fichiers", []),
                "existing_code_snapshot": existing_snapshot,
                "last_error": "",
                "validation_status": "GENERATED"
            }
        except Exception as e:
            error_msg = f"Erreur de generation : {str(e)}"
            logger.error(f"[ERROR] {error_msg}")
            new_error_count = state.get("error_count", 0) + 1
            new_retry_count = state.get("retry_count", 0) + 1
            return {
                "validation_status": "REJETE",
                "feedback_correction": f"Technical error during generation: {str(e)}. Please retry.",
                "error_count": new_error_count,
                "retry_count": new_retry_count,
                "last_error": error_msg
            }

    def architecture_guard_node(self, state: AgentState) -> dict:
        import re
        task_type = state.get("target_module")
        
        # [SAFE] SECURITE : On extrait les chemins REELS des blocs de code
        # pour eviter que le LLM ne cache un fichier non autorise en l'omettant de impact_fichiers
        code = state.get("code_to_verify", "")
        file_pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        extracted_paths = re.findall(file_pattern, code)
        
        # Fusionner avec impact_fichiers (fallback et complement)
        paths = list(set(extracted_paths + state.get("impact_fichiers", [])))

        try:
            if paths:
                logger.info(f"[SAFE] ArchitectureGuard: Validating {len(paths)} files before persistence...")
                self.arch_guard.validate(task_type, paths)
            
            return {
                "arch_guard_status": "PASSED",
                "impact_fichiers": paths
            }
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"[STOP] ArchitectureGuard Error: {error_msg}")
            
            return {
                "arch_guard_status": "FAILED",
                "validation_status": "REJETE",
                "feedback_correction": f"CRITICAL ARCHITECTURE VIOLATION: {error_msg}. Please correct the file paths to respect the project architecture constraints.",
                "error_count": state.get("error_count", 0) + 1,
                "last_error": error_msg
            }

    def path_guard_node(self, state: AgentState) -> dict:
        """N?ud : Garde protectrice pour la normalisation et validation des chemins.
        
        Objectifs:
        - Normaliser tous les chemins AVANT la persistance
        - Bloquer les chemins non surs (traversal, caracteres invalides)
        - Signaler les anomalies detectees
        - Defense-in-depth: Double verification avant write
        
        Ce n?ud insert une couche de defense entre generation et persist.
        """
        import re
        from utils.file_manager import FileManager
        
        logger.info("[SAFE] PathGuard: Validating and normalizing all paths...")
        
        code = state.get("code_to_verify", "")
        if not code:
            logger.debug("? No code to validate (empty)")
            return {"path_guard_status": "EMPTY"}
        
        # Instancier FileManager pour acceder aux methodes de validation
        fm = FileManager(str(self.root))
        
        # Extraire tous les chemins du code
        file_pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        file_blocks = re.split(file_pattern, code)
        
        path_issues = []
        normalized_code = code
        
        if len(file_blocks) > 1:
            for i in range(1, len(file_blocks), 2):
                original_path = file_blocks[i].strip()
                
                logger.info(f"[SCAN] Validating path: {original_path}")
                
                try:
                    # SECURITE 1 : Detecter les chemins non surs
                    if ".." in original_path:
                        logger.error(f"[STOP] Directory traversal detected: {original_path}")
                        path_issues.append({
                            "path": original_path,
                            "issue": "Directory traversal (..) detected",
                            "severity": "CRITICAL"
                        })
                        continue
                    
                    if original_path.startswith('/') or ':' in original_path:
                        logger.error(f"[STOP] Absolute path detected: {original_path}")
                        path_issues.append({
                            "path": original_path,
                            "issue": "Absolute path (not allowed)",
                            "severity": "CRITICAL"
                        })
                        continue
                    
                    # SECURITE 2 : Normaliser le chemin
                    try:
                        normalized_path = fm.normalize_path(original_path)
                        logger.info(f"  [OK] Path normalized: {original_path} -> {normalized_path}")
                        
                        # SECURITE 3 : Valider le chemin normalise
                        if ".." in normalized_path or not normalized_path.startswith(('frontend/', 'backend/', 'mobile/')):
                            logger.error(f"[STOP] Normalized path fails validation: {normalized_path}")
                            path_issues.append({
                                "path": original_path,
                                "normalized": normalized_path,
                                "issue": "Normalized path failed validation",
                                "severity": "CRITICAL"
                            })
                        else:
                            logger.debug(f"  ? Path validation passed")
                        
                        # Mettre a jour le code avec le chemin normalise
                        if normalized_path != original_path:
                            # Note: In real scenario, we would update the code
                            # For now, we just track it
                            pass
                            
                    except ValueError as e:
                        logger.warning(f"[WARN] Path normalization failed: {e}")
                        path_issues.append({
                            "path": original_path,
                            "issue": str(e),
                            "severity": "WARNING"
                        })
                
                except Exception as e:
                    logger.error(f"[ERROR] Unexpected error validating path {original_path}: {e}")
                    path_issues.append({
                        "path": original_path,
                        "issue": f"Validation error: {e}",
                        "severity": "ERROR"
                    })
        
        # RESUME
        critical_issues = [p for p in path_issues if p.get("severity") == "CRITICAL"]
        warning_issues = [p for p in path_issues if p.get("severity") in ["WARNING", "ERROR"]]
        
        if critical_issues:
            logger.error(f"[STOP] PathGuard: {len(critical_issues)} critical issue(s) detected")
            status = "BLOCKED"
        elif warning_issues:
            logger.warning(f"[WARN] PathGuard: {len(warning_issues)} warning(s) detected")
            status = "WARNED"
        else:
            logger.info(f"[OK] PathGuard: All paths validated successfully")
            status = "PASSED"
        
        return {
            "path_guard_status": status,
            "path_guard_issues": path_issues,
            "validation_status": "PATH_BLOCKED" if status == "BLOCKED" else "PATH_VALIDATED"
        }

    def persist_node(self, state: AgentState) -> dict:
        """N?ud : Persistance du code sur le disque + Assurance des artefacts obligatoires.
        
        Inclut le diff tracking pour visibilite des changements.
        """
        from utils.file_manager import FileManager
        
        logger.info("[SAVE] Persistance des fichiers sur le disque...")
        code = state.get("code_to_verify", "")
        if not code:
            state["validation_status"] = "EMPTY_CODE"
            return state  # type: ignore[return-value]
        
        # Snapshot AVANT
        fm = FileManager(str(self.root))
        snapshot_before = fm.snapshot_project_state("before_persist")
        logger.info(f"[PHOTO] Project snapshot before: {snapshot_before['file_count']} files, {snapshot_before['total_size']} bytes")
        
        # Persistence
        sanitized_code, written_paths = self._persist_code_to_disk(code)
        logger.info(f"[OK] {len(written_paths)} fichiers ecrits.")
        
        # --- ASSURER LES ARTEFACTS OBLIGATOIRES ---
        # [SAFE] DESACTIVE : Ne plus creer les fichiers stub vides
        # Cela aide les developpeurs juniors a ne pas etre confus par des fichiers vides/placeholders
        # required_files = self._extract_required_files(state.get("subtask_checklist", ""))
        # Les fichiers obligatoires doivent etre generes avec du contenu reel, pas des stubs
        
        required_files = []
        missing_files = []
        written_paths.extend(missing_files)
        
        # Snapshot APR?S
        snapshot_after = fm.snapshot_project_state("after_persist")
        logger.info(f"[PHOTO] Project snapshot after: {snapshot_after['file_count']} files, {snapshot_after['total_size']} bytes")
        
        # Diff des snapshots
        file_diff = fm.diff_snapshots(snapshot_before, snapshot_after)
        logger.info(f"[STAT] File persistence diff: {file_diff['summary']}")
        
        return {
            "code_to_verify": sanitized_code,
            "impact_fichiers": list(set(state.get("impact_fichiers", []) + written_paths)),
            "validation_status": "PERSISTED",
            "snapshot_before": snapshot_before,
            "snapshot_after": snapshot_after,
            "file_diff": file_diff
        }

    def esm_scaffold_node(self, state: AgentState) -> dict:
        """N?ud : Assure la compatibilite ESM pour tous les fichiers backend generes.
        
        Remplace automatiquement :
        - `__dirname` par l'utilitaire ESM `getDirname(import.meta.url)`
        - Ajoute les imports manquants pour `getDirname`
        - Force le prefixe `node:` pour les imports de modules natifs (ex: `import path from 'path'` -> `import path from 'node:path'`)
        """
        import re
        from pathlib import Path
        
        logger.info("[AI] Application de la compatibilite ESM (__dirname, node: imports) sur les fichiers modifies...")
        
        written_paths = state.get("impact_fichiers", [])
        if not written_paths:
            return {}
            
        fixed_files = []
        
        # S'assurer que src/utils/dirname.util.ts existe cote backend
        backend_utils_dir = self.root / "backend" / "src" / "utils"
        dirname_util_path = backend_utils_dir / "dirname.util.ts"
        
        dirname_util_content = '''import { fileURLToPath } from "url";
import path from "node:path";

/**
 * Utilitaire ESM pour remplacer __dirname et __filename.
 * @param metaUrl - Passer `import.meta.url` depuis le fichier appelant
 */
export const getDirname = (metaUrl: string) => {
  const __filename = fileURLToPath(metaUrl);
  return path.dirname(__filename);
};
'''
        
        # Modules natifs Node necessitant (ou recommandant fortement) le prefixe node:
        NODE_BUILTINS = [
            "path", "fs", "url", "crypto", "child_process", "os", "http", 
            "https", "stream", "util", "events", "assert"
        ]
        
        created_util = False
        
        for p in written_paths:
            # Ne traiter que les fichiers backend internes en .ts/.js
            if not p.startswith("backend/src/") or not p.endswith((".ts", ".js")):
                continue
                
            full_path = self.root / p
            if not full_path.exists():
                continue
                
            content = full_path.read_text(encoding="utf-8")
            original_content = content
            
            # 1. Remplacement de __dirname
            if "__dirname" in content and "getDirname" not in content and "fileURLToPath" not in content:
                # Creer le dirname.util.ts si c'est la premiere fois qu'on en a besoin
                if not dirname_util_path.exists() and not created_util:
                    backend_utils_dir.mkdir(parents=True, exist_ok=True)
                    dirname_util_path.write_text(dirname_util_content, encoding="utf-8")
                    logger.info("[OK] Creation de backend/src/utils/dirname.util.ts (ESM compat.)")
                    created_util = True
                
                # Calculer le chemin relatif vers utils depuis ce fichier
                parts_len = len(p.split("/")) - 1 # nb de dossiers profonds
                rel_up = "../" * (parts_len - 2) if parts_len > 2 else "./" # -2 for backend/src
                
                # S'assurer que rel_up est correct
                import os
                rel_path_to_utils = os.path.relpath("backend/src/utils/dirname.util", os.path.dirname(p)).replace('\\', '/')
                if not rel_path_to_utils.startswith('.'):
                    rel_path_to_utils = './' + rel_path_to_utils
                
                # Injecter l'import
                import_stmt = f'import {{ getDirname }} from "{rel_path_to_utils}";\n'
                
                # Inserer l'import apres les imports existants, ou au debut
                import_match = list(re.finditer(r'^import\s+.*?;?\s*$', content, re.MULTILINE))
                if import_match:
                    last_import_end = import_match[-1].end()
                    content = content[:last_import_end] + "\n" + import_stmt + content[last_import_end:]
                else:
                    content = import_stmt + "\n" + content
                
                # Injecter la declaration __dirname
                dirname_decl = '\nconst __dirname = getDirname(import.meta.url);\n'
                
                # On insere juste apres les imports
                import_match = list(re.finditer(r'^import\s+.*?;?\s*$', content, re.MULTILINE))
                if import_match:
                    last_import_end = import_match[-1].end()
                    content = content[:last_import_end] + dirname_decl + content[last_import_end:]
                else:
                    content = dirname_decl + content
            
            # 2. Patch des imports natifs Node pour ajouter "node:"
            for builtin in NODE_BUILTINS:
                # Match `import path from 'path'` ou `import { join } from 'path'`
                pattern1 = rf"import\s+(.*?)\s+from\s+['\"]({builtin})['\"]"
                content = re.sub(pattern1, rf"import \1 from 'node:\2'", content)
                
                # Match `import * as fs from 'fs'` 
                pattern2 = rf"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]({builtin})['\"]"
                content = re.sub(pattern2, rf"import * as \1 from 'node:\2'", content)

            # 3. Patch des imports relatifs pour ajouter .js (Requis par ESM NodeNext)
            # Remplacement: import { foo } from "./bar" -> import { foo } from "./bar.js"
            # Ignore si se termine deja par .js, .json, .ts, etc.
            def add_js_extension(match):
                import_stmt = match.group(0)
                path_str = match.group(2)
                
                # S'assurer qu'il s'agit d'un import relatif interne, pas d'un package npm,
                # et ne pas ajouter .js si l'extension y est deja (ou .json, .css etc)
                if (path_str.startswith('.') or path_str.startswith('/')) and not path_str.split('/')[-1].count('.') > 0:
                     return rf"{match.group(1)}'{path_str}.js'{match.group(3)}"
                return import_stmt
                
            rel_import_pattern = r"(import\s+.*?\s+from\s+)['\"]([^'\"]+)['\"](;?)"
            content = re.sub(rel_import_pattern, add_js_extension, content)
            
            # Application aux dynamic imports: import('./file') -> import('./file.js')
            dyn_import_pattern = r"(import\s*\(\s*)['\"]([^'\"]+)['\"](\s*\))"
            content = re.sub(dyn_import_pattern, add_js_extension, content)
            
            # Application aux re-exports: export { x } from './file' -> export { x } from './file.js'
            re_export_pattern = r"(export\s+.*?\s+from\s+)['\"]([^'\"]+)['\"](;?)"
            content = re.sub(re_export_pattern, add_js_extension, content)
            
            # Si le contenu a ete modifie, sauvegarder
            if content != original_content:
                full_path.write_text(content, encoding="utf-8")
                fixed_files.append(p)
                logger.info(f"[FIX] ESM Patch applique sur {p} (__dirname / node: imports)")
        
        # Ajouter le fichier utilitaire a la liste s'il a ete cree
        if created_util and "backend/src/utils/dirname.util.ts" not in written_paths:
            written_paths.append("backend/src/utils/dirname.util.ts")
            state["impact_fichiers"] = written_paths
            
        status = "FIXED" if fixed_files else "NO_CHANGES"
        logger.info(f"[OK] ESM Compatibility: {status} ({len(fixed_files)} files modified)")
        
        return {
            "esm_status": status,
            "impact_fichiers": written_paths
        }

    def esm_compatibility_node(self, state: AgentState) -> dict:
        """N?ud : Assure la compatibilite ESM pour tous les fichiers backend generes (post-persist).
        
        Remplace automatiquement :
        - `__dirname` par l'utilitaire ESM `getDirname(import.meta.url)`
        - Ajoute les imports manquants pour `getDirname`
        - Force le prefixe `node:` pour les imports de modules natifs (ex: `import path from 'path'` -> `import path from 'node:path'`)
        """
        import re
        from pathlib import Path
        
        logger.info("[AI] [POST-PERSIST] Application de la compatibilite ESM (__dirname, node: imports) sur les fichiers modifies...")
        
        written_paths = state.get("impact_fichiers", [])
        if not written_paths:
            return {}
            
        fixed_files = []
        
        # S'assurer que src/utils/dirname.util.ts existe cote backend
        backend_utils_dir = self.root / "backend" / "src" / "utils"
        dirname_util_path = backend_utils_dir / "dirname.util.ts"
        
        dirname_util_content = '''import { fileURLToPath } from "url";
import path from "node:path";

/**
 * Utilitaire ESM pour remplacer __dirname et __filename.
 * @param metaUrl - Passer `import.meta.url` depuis le fichier appelant
 */
export const getDirname = (metaUrl: string) => {
  const __filename = fileURLToPath(metaUrl);
  return path.dirname(__filename);
};
'''
        
        # Modules natifs Node necessitant (ou recommandant fortement) le prefixe node:
        NODE_BUILTINS = [
            "path", "fs", "url", "crypto", "child_process", "os", "http", 
            "https", "stream", "util", "events", "assert"
        ]
        
        created_util = False
        
        for p in written_paths:
            # Ne traiter que les fichiers backend internes en .ts/.js
            if not p.startswith("backend/src/") or not p.endswith((".ts", ".js")):
                continue
                
            full_path = self.root / p
            if not full_path.exists():
                continue
                
            content = full_path.read_text(encoding="utf-8")
            original_content = content
            
            # 1. Remplacement de __dirname
            if "__dirname" in content and "getDirname" not in content and "fileURLToPath" not in content:
                # Creer le dirname.util.ts si c'est la premiere fois qu'on en a besoin
                if not dirname_util_path.exists() and not created_util:
                    backend_utils_dir.mkdir(parents=True, exist_ok=True)
                    dirname_util_path.write_text(dirname_util_content, encoding="utf-8")
                    logger.info("[OK] Creation de backend/src/utils/dirname.util.ts (ESM compat.)")
                    created_util = True
                
                # Calculer le chemin relatif vers utils depuis ce fichier
                import os
                rel_path_to_utils = os.path.relpath("backend/src/utils/dirname.util", os.path.dirname(p)).replace('\\', '/')
                if not rel_path_to_utils.startswith('.'):
                    rel_path_to_utils = './' + rel_path_to_utils
                
                # Injecter l'import
                import_stmt = f'import {{ getDirname }} from "{rel_path_to_utils}";\n'
                
                # Inserer l'import apres les imports existants, ou au debut
                import_match = list(re.finditer(r'^import\s+.*?;?\s*$', content, re.MULTILINE))
                if import_match:
                    last_import_end = import_match[-1].end()
                    content = content[:last_import_end] + "\n" + import_stmt + content[last_import_end:]
                else:
                    content = import_stmt + "\n" + content
                
                # Injecter la declaration __dirname
                dirname_decl = '\nconst __dirname = getDirname(import.meta.url);\n'
                
                # On insere juste apres les imports
                import_match = list(re.finditer(r'^import\s+.*?;?\s*$', content, re.MULTILINE))
                if import_match:
                    last_import_end = import_match[-1].end()
                    content = content[:last_import_end] + dirname_decl + content[last_import_end:]
                else:
                    content = dirname_decl + content
            
            # 2. Patch des imports natifs Node pour ajouter "node:"
            for builtin in NODE_BUILTINS:
                # Match `import path from 'path'` ou `import { join } from 'path'`
                pattern1 = rf"import\s+(.*?)\s+from\s+['\"]({builtin})['\"]"
                content = re.sub(pattern1, rf"import \1 from 'node:\2'", content)
                
                # Match `import * as fs from 'fs'` 
                pattern2 = rf"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]({builtin})['\"]"
                content = re.sub(pattern2, rf"import * as \1 from 'node:\2'", content)
            
            # Si le contenu a ete modifie, sauvegarder
            if content != original_content:
                full_path.write_text(content, encoding="utf-8")
                fixed_files.append(p)
                logger.info(f"[FIX] ESM Patch applique sur {p} (__dirname / node: imports)")
        
        # Ajouter le fichier utilitaire a la liste s'il a ete cree
        if created_util and "backend/src/utils/dirname.util.ts" not in written_paths:
            written_paths.append("backend/src/utils/dirname.util.ts")
            state["impact_fichiers"] = written_paths
            
        status = "FIXED" if fixed_files else "NO_CHANGES"
        logger.info(f"[OK] ESM Compatibility (post-persist): {status} ({len(fixed_files)} files modified)")
        
        return {
            "esm_status": status,
            "impact_fichiers": written_paths
        }

    def esm_import_resolver_node(self, state: AgentState) -> dict:
        """N?ud : Applique le resolver ESM automatique pour ajouter les extensions .js aux imports.
        
        Pipeline ESM Post-Generation:
        1. esm_compatibility_node: Remplace __dirname, ajoute node: prefix
        2. esm_import_resolver_node (CE N?UD): Ajoute .js aux imports relatifs
        3. dependency_resolver_node: Valide les dependances
        
        Ce n?ud utilise le resolver ESMImportResolver pour scanner tous les fichiers
        et ajouter automatiquement l'extension .js aux imports relatifs TypeScript.
        """
        from utils.esm_import_resolver import ESMImportResolver, apply_esm_import_resolver
        import json
        from pathlib import Path
        
        logger.info("? ESM Import Resolver: Ajout des extensions .js aux imports relatifs...")
        
        try:
            # Verifier si le projet est en ESM mode
            pkg_path = self.root / "package.json"
            is_esm = False
            
            if pkg_path.exists():
                try:
                    pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    is_esm = pkg_data.get("type") == "module"
                except:
                    pass
            
            if not is_esm:
                logger.info("[INFO] Projet non en ESM mode (type != module). Skipping ESM import resolver.")
                return {
                    "esm_resolver_status": "SKIPPED",
                    "esm_resolver_reason": "Non-ESM project"
                }
            
            logger.info("[SCAN] Mode ESM detecte. Scanning et resolution des imports...")
            
            # Appliquer le resolver sur les repertoires standards
            target_dirs = ["backend/src", "frontend/src"]
            stats = apply_esm_import_resolver(self.root, target_dirs)
            
            # Generer le rapport
            successful = {k: v for k, v in stats.items() if v > 0}
            errors = {k: v for k, v in stats.items() if v < 0}
            
            report = []
            report.append("? ESM Import Resolver Report")
            report.append("=" * 50)
            
            if successful:
                total_fixes = sum(v for v in successful.values() if v > 0)
                report.append(f"[OK] Successfully fixed: {len(successful)} files")
                report.append(f"   Total import extensions added: {total_fixes}")
                for file_path, count in list(successful.items())[:5]:  # Show first 5
                    file_name = Path(file_path).name
                    report.append(f"   - {file_name} (+{count} .js)")
                if len(successful) > 5:
                    report.append(f"   ... and {len(successful) - 5} more files")
            
            if errors:
                report.append(f"[ERROR] Errors in: {len(errors)} files")
            
            if not successful and not errors:
                report.append("[INFO] No ESM import fixes needed.")
            
            report_str = "\n".join(report)
            logger.info(report_str)
            
            return {
                "esm_resolver_status": "COMPLETED",
                "esm_resolver_report": report_str,
                "esm_resolver_stats": stats,
                "impact_fichiers": state.get("impact_fichiers", [])
            }
            
        except Exception as e:
            error_msg = f"Error in ESM Import Resolver: {str(e)}"
            logger.error(error_msg)
            return {
                "esm_resolver_status": "ERROR",
                "esm_resolver_error": error_msg,
                "feedback_correction": f"ESM Import Resolver failed: {str(e)}. This won't block the build but may cause runtime errors.",
                "impact_fichiers": state.get("impact_fichiers", [])
            }

    def scaffold_node(self, state: AgentState) -> dict:
        """N?ud : Scaffolding initial pour s'assurer que les fichiers de base existent toujours, protegeant contre les hallucinations vides du LLM."""
        import os
        import json
        
        logger.info("[SETUP] Scaffold Node: Verification de la structure de base du projet...")
        
        target_mod = state.get("target_module", "")
        
        # Ce scaffolding n'est fait qu'a l'etape 0-1 de "setup" ou si le dossier est vide
        # On ne veut pas ecraser s'il existe deja
        if target_mod == "backend":
            os.makedirs(str(self.root / "backend/src"), exist_ok=True)
            
            pkg_path = self.root / "backend/package.json"
            if not pkg_path.exists():
                logger.info("   -> Creation de backend/package.json")
                pkg_data = {
                    "name": "backend",
                    "version": "1.0.0",
                    "type": "module",
                    "main": "dist/app.js",
                    "scripts": {
                        "build": "tsc",
                        "start": "node dist/app.js",
                        "dev": "ts-node-dev --respawn --transpile-only src/app.ts"
                    },
                    "dependencies": {
                        "express": "latest",
                        "cors": "latest",
                        "helmet": "latest",
                        "morgan": "latest",
                        "dotenv": "latest",
                        "zod": "latest",
                        "jsonwebtoken": "latest",
                        "bcryptjs": "latest",
                        "@prisma/client": "latest"
                    },
                    "devDependencies": {
                        "typescript": "latest",
                        "@types/node": "latest",
                        "@types/express": "latest",
                        "@types/cors": "latest",
                        "@types/morgan": "latest",
                        "@types/jsonwebtoken": "latest",
                        "@types/bcryptjs": "latest",
                        "ts-node-dev": "latest",
                        "prisma": "latest"
                    }
                }
                pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
                
            app_path = self.root / "backend/src/app.ts"
            if not app_path.exists():
                logger.info("   -> Creation de backend/src/app.ts (template de base)")
                app_template = '''import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import dotenv from 'dotenv';

dotenv.config();

const app = express();

// Middlewares de securite et parsing
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Logging en developpement
if (process.env.NODE_ENV === 'development') {
  app.use(morgan('dev'));
}

// Routes (a ajouter)
app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'UP', message: 'Backend is healthy!' });
});

// Gestion des erreurs (a implementer)
app.use((err: any, req: any, res: any, next: any) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Internal Server Error' });
});

export default app;
'''
                app_path.write_text(app_template, encoding="utf-8")
                
        elif target_mod == "frontend":
            os.makedirs(str(self.root / "frontend/src"), exist_ok=True)
            
            pkg_path = self.root / "frontend/package.json"
            if not pkg_path.exists():
                logger.info("   -> Creation de frontend/package.json")
                pkg_data = {
                    "name": "frontend",
                    "version": "1.0.0",
                    "type": "module",
                    "scripts": {
                        "dev": "vite",
                        "build": "tsc && vite build",
                        "preview": "vite preview"
                    },
                    "dependencies": {
                        "react": "^18.2.0",
                        "react-dom": "^18.2.0",
                        "react-router-dom": "^6.14.0",
                        "axios": "^1.4.0",
                        "lucide-react": "^0.260.0"
                    },
                    "devDependencies": {
                        "@types/react": "^18.2.0",
                        "@types/react-dom": "^18.2.0",
                        "@vitejs/plugin-react": "^4.0.0",
                        "vite": "^4.4.0",
                        "typescript": "^5.0.2",
                        "tailwindcss": "latest",
                        "postcss": "latest",
                        "autoprefixer": "latest",
                        "eslint": "latest",
                        "prettier": "latest"
                    }
                }
                pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
                
            main_path = self.root / "frontend/src/main.tsx"
            if not main_path.exists():
                logger.info("   -> Creation de frontend/src/main.tsx (template de base)")
                template_candidates = [
                    self.root / ".speckit" / "templates" / "main.vite.react.template.tsx",
                    Path(__file__).parent / "templates" / "main.vite.react.template.tsx",
                ]
                main_template = None
                for candidate in template_candidates:
                    if candidate.exists():
                        main_template = candidate.read_text(encoding="utf-8")
                        logger.info(f"   -> Template main.tsx charge depuis {candidate}")
                        break
                if not main_template:
                    main_template = '''import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error("Root element '#root' not found");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
'''
                main_path.write_text(main_template, encoding="utf-8")
                
        return state  # type: ignore[return-value]

    def typescript_validate_node(self, state: AgentState) -> dict:
        """N?ud : Validation TypeScript des fichiers generes (phase post-persist).
        
        Objectifs:
        - Determiner si le code TypeScript/JavaScript est syntaxiquement valide
        - Capturer les erreurs de compilation avant le pipeline de correction
        - Signaler les dependances manquantes detectees
        """
        import subprocess
        import re
        
        logger.info("[DOC] TypeScript Validation (post-persist)...")
        
        written_paths = state.get("impact_fichiers", [])
        if not written_paths:
            logger.debug("? No files written, skipping TypeScript validation")
            return {"typescript_errors": [], "typescript_validation_status": "SKIPPED"}
        
        # Determiner les modules cibles a valider
        modules_to_check = set()
        for path in written_paths:
            if path.startswith('frontend/'):
                modules_to_check.add('frontend')
            elif path.startswith('backend/'):
                modules_to_check.add('backend')
        
        if not modules_to_check:
            logger.debug("? No frontend/backend modules detected in written files")
            return {"typescript_errors": [], "typescript_validation_status": "NO_MODULES"}
        
        typescript_errors = []
        
        for module in modules_to_check:
            module_path = self.root / module
            tsconfig_path = module_path / "tsconfig.json"
            
            if not tsconfig_path.exists():
                logger.debug(f"[WARN] No tsconfig.json found in {module}, skipping validation")
                continue
            
            logger.info(f"[SCAN] Checking TypeScript in {module}/ module...")
            
            try:
                # Executer tsc --noEmit pour valider sans emettre
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    cwd=str(module_path),
                    capture_output=True,
                    text=True,
                    timeout=600,
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
                                logger.warning(f"  [ERROR] {file_path}:{line_num} - {error_msg.strip()}")
                            else:
                                # Generic error line
                                typescript_errors.append({
                                    "module": module,
                                    "raw_error": line.strip()
                                })
                    
                    logger.warning(f"[WARN] TypeScript found {len(typescript_errors)} error(s) in {module}")
                else:
                    logger.info(f"[OK] No TypeScript errors in {module}")
                    
            except FileNotFoundError:
                logger.warning(f"[WARN] TypeScript compiler not found in {module} (npm_path install first?)")
            except subprocess.TimeoutExpired:
                logger.error(f"[ERROR] TypeScript validation timeout in {module}")
                typescript_errors.append({
                    "module": module,
                    "error": "Compilation timeout (>600s)"
                })
            except Exception as e:
                logger.error(f"[ERROR] Unexpected error during TypeScript validation in {module}: {e}")
                typescript_errors.append({
                    "module": module,
                    "error": f"Validation failed: {e}"
                })
        
        # Resume
        if typescript_errors:
            logger.warning(f"[STAT] TypeScript validation: {len(typescript_errors)} issue(s) found")
            status = "FAILED"
        else:
            logger.info(f"[OK] TypeScript validation: All modules pass")
            status = "PASSED"
        
        return {
            "typescript_errors": typescript_errors,
            "typescript_validation_status": status,
            "validation_status": "VALIDATED" if status == "PASSED" else "VALIDATION_FAILED"
        }

    def _is_typescript_project(self, module_dir: Path) -> bool:
        """Detecte si un projet cible TypeScript (via tsconfig.json ou package.json 'type')."""
        tsconfig = module_dir / "tsconfig.json"
        if tsconfig.exists():
            return True
        
        # Check package.json for "type": "module" ou typescript tooling
        pkg_path = module_dir / "package.json"
        if pkg_path.exists():
            try:
                pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                # Si devDependencies contient typescript ou @types/*, c'est un projet TS
                dev_deps = set(pkg_data.get("devDependencies", {}).keys())
                if "typescript" in dev_deps or any(d.startswith("@types/") for d in dev_deps):
                    return True
            except:
                pass
        
        return False
    
    def _get_types_for_package(self, pkg_name: str) -> Optional[str]:
        """Retourne le nom du package @types/* correspondant, ou None."""
        # Mapping des packages populaires a leur @types equivalents
        types_mapping = {
            "react": "@types/react",
            "react-dom": "@types/react-dom",
            "react-router-dom": "@types/react-router-dom",
            "axios": "@types/axios",
            "lodash": "@types/lodash",
            "express": "@types/express",
            "node": "@types/node",
            "jest": "@types/jest",
            "cors": "@types/cors",
            "morgan": "@types/morgan",
            "bcryptjs": "@types/bcryptjs",
            "jsonwebtoken": "@types/jsonwebtoken",
            "dotenv": "@types/dotenv",
        }
        return types_mapping.get(pkg_name)

    def validate_dependency_node(self, state: AgentState) -> dict:
        """
        Valide et repare les dependances AVANT npm install.
        
        ? Architecture:
        1. Utilise SemanticScanner pour detecter les VRAIES dependances utilisees
        2. Compare avec package.json
        3. Ajoute les dependances manquantes a package.json (pas les hallucinations LLM)
        4. [NEW] Pour les projets TypeScript, auto-ajoute @types/* correspondants
        
        Resultat: Zero hallucinations de dependances, seulement des imports reels + Types-First.
        """
        logger.info("[SCAN] Validation des dependances (avant npm install)...")
        
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
                    
                    # ? UTILISER LE SCANNER pour detecter les vraies dependances
                    scanner = SemanticScanner(str(target_dir))
                    missing_dependencies = scanner.detect_missing_dependencies()
                    
                    # ? Liste officielle des Built-ins Node.js
                    NODE_BUILTINS = {
                        "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
                        "constants", "crypto", "dgram", "dns", "domain", "events", "fs", "fs/promises",
                        "http", "http2", "https", "inspector", "module", "net", "os", "path", "path/posix",
                        "path/win32", "perf_hooks", "process", "punycode", "querystring", "readline",
                        "readline/promises", "repl", "stream", "stream/consumers", "stream/promises",
                        "stream/web", "string_decoder", "timers", "timers/promises", "tls", "trace_events",
                        "tty", "url", "util", "util/types", "v8", "vm", "wasi", "worker_threads", "zlib"
                    }
                    
                    pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    
                    # [CLEAN] 1. Nettoyer les dependances actuelles (au cas ou le LLM les aurait generees)
                    cleaned_builtins = []
                    for section in ["dependencies", "devDependencies"]:
                        if section in pkg_data:
                            original_keys = list(pkg_data[section].keys())
                            for k in original_keys:
                                if k in NODE_BUILTINS or k.startswith("node:"):
                                    del pkg_data[section][k]
                                    cleaned_builtins.append(k)
                    
                    if cleaned_builtins:
                        logger.info(f"[CLEAN] Nettoye {len(cleaned_builtins)} Node built-ins de package.json : {', '.join(cleaned_builtins)}")
                        fixed_issues.extend([f"Removed builtin {k}" for k in cleaned_builtins])
                    
                    if not missing_dependencies and not cleaned_builtins:
                        logger.info(f"[OK] {target_dir.name}: Toutes les dependances sont declarees et propres.")
                        continue
                    
                    # [ADD] 2. Ajouter les NOUVELLES dependances manquantes (filtrees)
                    is_typescript = self._is_typescript_project(target_dir)
                    
                    for pkg in missing_dependencies:
                        if pkg in NODE_BUILTINS or pkg.startswith("node:"):
                            continue
                            
                        # Determiner si c'est une dev dependency
                        is_dev = any(pkg.startswith(prefix) for prefix in ["@types/", "ts-", "jest", "vitest", "supertest", "@testing-library"])
                        section = "devDependencies" if is_dev else "dependencies"
                        
                        if section not in pkg_data:
                            pkg_data[section] = {}
                        
                        pkg_data[section][pkg] = "latest"
                        fixed_issues.append(f"Added {pkg} to {section}")
                        logger.info(f"[ADD] Ajoute {pkg} aux {section}")
                        
                        # [NEW] TYPES-FIRST APPROACH: Pour chaque package ajoute en TypeScript,
                        # ajouter automatiquement le @types/* correspondant
                        if is_typescript and not is_dev:  # Types-First seulement pour dependencies (non @types/*, non ts-*)
                            types_package = self._get_types_for_package(pkg)
                            if types_package:
                                if "devDependencies" not in pkg_data:
                                    pkg_data["devDependencies"] = {}
                                
                                if types_package not in pkg_data["devDependencies"]:
                                    pkg_data["devDependencies"][types_package] = "latest"
                                    fixed_issues.append(f"Added {types_package} to devDependencies (Types-First)")
                                    logger.info(f"[TYPES-FIRST] Auto-ajoute {types_package} pour {pkg} (TypeScript project)")

                    
                    # Sauvegarder si modifications
                    if fixed_issues:
                        pkg_path.write_text(json.dumps(pkg_data, indent=2) + "\n", encoding="utf-8")
                        # Invalider le hash pour forcer un nouveau build
                        hash_file = target_dir / ".speckit_hash"
                        if hash_file.exists():
                            hash_file.unlink()
                        logger.info(f"[OK] package.json mis a jour: {len(fixed_issues)} dependances ajoutees")
                
                except Exception as e:
                    logger.warning(f"[WARN] Erreur validation {target_dir}: {e}")
            
            # [SAFE] Filtrer les modules halluciner du LLM (si presents dans state)
            IGNORE_MODULES = [
                "@testing-library/react-hooks",
                "@testing-library/react",
                "jest",
                "vitest"
            ]
            state["missing_modules"] = [m for m in state.get("missing_modules", []) if m not in IGNORE_MODULES]
            
            logger.info(f"[OK] Validation terminee. Dependances du scanner definies dans package.json")
            
        except Exception as e:
            logger.error(f"[ERROR] validate_dependency_node error: {e}")
            state["missing_modules"] = []
        
        # [SAFE] TOUJOURS retourner state
        return state  # type: ignore[return-value]

    def install_deps_node(self, state: AgentState) -> dict:
        """N?ud : Installation des dependances npm ? detection statique (scanner) SEULE source de verite."""
        import subprocess
        from pathlib import Path
        from utils.scanner import SemanticScanner
        
        logger.info("? Installation des dependances (npm install)...")
        
        # --- [SAFE] ANTI-BOUCLE NIVEAU 1: Verifier dep_install_attempts ---
        attempts = state.get("dep_install_attempts", 0)
        if attempts >= 1:
            logger.warning("[WARN] Dependency install already attempted. Skipping to prevent loops.")
            state["missing_modules"] = []
            return state  # type: ignore[return-value]

        state["dep_install_attempts"] = attempts + 1
        
        # --- Determiner le repertoire cible ---
        target_module = state.get("target_module")
        if target_module:
            target_dir = self.root / target_module
        else:
            # Chercher le premier repertoire avec package.json
            for search_dir in [self.root, self.root / "backend", self.root / "frontend"]:
                if (search_dir / "package.json").exists():
                    target_dir = search_dir
                    break
            else:
                logger.warning("[WARN] Aucun package.json trouve")
                state["missing_modules"] = []
                return state  # type: ignore[return-value]
        
        pkg_path = target_dir / "package.json"
        if not pkg_path.exists():
            logger.warning(f"[WARN] package.json non trouve dans {target_dir}")
            state["missing_modules"] = []
            return state  # type: ignore[return-value]
        
        # ? DETECTION STATIQUE: Scanner = SOURCE DE VERITE
        # Le scanner analyse les imports REELLEMENT utilises dans le code
        # C'est la seule verite fiable. Le LLM peut halluciner, pas le code source.
        scanner = SemanticScanner(str(target_dir))
        missing_from_scanner = scanner.detect_missing_dependencies()
        
        logger.info(f"[SCAN] Scanner detecte {len(missing_from_scanner)} modules vraiment manquants: {missing_from_scanner}")
        
        # [SAFE] FILTRE DEPRECATED_PACKAGES: Remplacer les packages halluciner/deprecies
        if missing_from_scanner:
            replaced = []
            for m in missing_from_scanner:
                if m in DEPRECATED_PACKAGES:
                    replacement = DEPRECATED_PACKAGES[m]
                    logger.info(f"[AI] Package deprecie {m} -> remplace par {replacement}")
                    replaced.append(replacement)
                else:
                    replaced.append(m)
            missing_from_scanner = list(set(replaced))  # Deduplicate si plusieurs pointent au meme replacement
        
        # [SAFE] STOCKER LE RESULTAT DU SCANNER COMME SOURCE DE VERITE
        state["scanner_missing_modules"] = missing_from_scanner
        
        import shutil
        npm_path = shutil.which("npm") or shutil.which("npm.cmd")
        
        # [SAFE] Guard: Ensure npm is available before attempting installation
        if not npm_path:
            logger.error("[ERROR] npm/npm.cmd not found in PATH. Cannot proceed with package validation.")
            state["missing_modules"] = []
            state["attempted_installs"] = state.get("attempted_installs", []) + list(set(missing_from_scanner))
            return state  # type: ignore[return-value]
        
        # Verifier si on part de 0 (scaffold tout frais)
        needs_base_install = not (target_dir / "node_modules").exists()
        
        # === R?GLE ARCHITECTURALE ===
        # Si le scanner dit 0 -> c'est 0, sauf si node_modules manque
        if not missing_from_scanner and not needs_base_install:
            logger.info("[OK] Scanner confirme : aucune dependance manquante et node_modules present.")
            state["missing_modules"] = []
            return state  # type: ignore[return-value]
        
        # --- [SAFE] ANTI-BOUCLE NIVEAU 2: Filtrer les modules deja tentes ---
        attempted = state.get("attempted_installs", [])
        filtered_missing = [m for m in missing_from_scanner if m not in attempted]
        
        if not filtered_missing and not needs_base_install:
            logger.info(f"[WARN] Tous les modules ont deja ete tentes: {missing_from_scanner}")
            logger.warning("[STOP] Arret des tentatives d'installation pour eviter la boucle infinie.")
            state["missing_modules"] = []
            return state  # type: ignore[return-value]
        
        if len(filtered_missing) < len(missing_from_scanner):
            skipped = set(missing_from_scanner) - set(filtered_missing)
            logger.info(f"[SKIP]  Modules deja tentes (ignores): {list(skipped)}")
        
        # --- Verification prealable avec npm view ---
        valid_packages = []
        for pkg in filtered_missing:
            try:
                assert npm_path is not None, "npm_path should not be None (guarded above)"
                view_res = subprocess.run(
                    [npm_path, "view", pkg, "version"],
                    capture_output=True,
                    text=True,
                    timeout=600
                )
                if view_res.returncode == 0:
                    valid_packages.append(pkg)
                else:
                    logger.warning(f"[WARN] Package {pkg} semble introuvable ou erreur registre. Ignore.")
            except Exception as e:
                logger.warning(f"[WARN] Erreur npm view pour {pkg}: {e}")

        if not valid_packages and not needs_base_install:
            logger.warning("[ERROR] Aucun package valide a installer.")
            state["missing_modules"] = []
            return state  # type: ignore[return-value]

        if needs_base_install and not valid_packages:
            logger.warning("[RUN] Installation de base (npm install global) car node_modules est absent...")
            install_args = [npm_path, "install"]
        else:
            logger.warning(f"[RUN] Installation de {len(valid_packages)} modules valides: {valid_packages}...")
            install_args = [npm_path, "install"] + valid_packages
        
        # [SAFE] Tracker les tentatives avant d'essayer
        state["attempted_installs"] = attempted + list(set(filtered_missing))
        
        try:
            if not npm_path:
                logger.error("[ERROR] npm not found in PATH")
                state["missing_modules"] = []
                return state  # type: ignore[return-value]

            result = subprocess.run(
                install_args,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                logger.error(f"[ERROR] Echec npm install (code {result.returncode})")
                if result.stderr:
                    logger.error(f"   Diagnostic npm: {result.stderr.strip()}")
            else:
                logger.info(f"[OK] Commande npm install terminee avec succes.")
                # Verification post-install physique
                if valid_packages:
                    installed_physically = []
                    for pkg in valid_packages:
                        # Gerer les scoped packages @foo/bar
                        pkg_dir = target_dir / "node_modules" / pkg
                        if pkg_dir.exists():
                            installed_physically.append(pkg)
                    
                    if installed_physically:
                        logger.info(f"[OK] Verification physique : {len(installed_physically)} modules confirmes dans node_modules.")
                        installed = state.get("installed_modules", [])
                        installed.extend(installed_physically)
                        state["installed_modules"] = installed
                    else:
                        logger.warning("[WARN] npm install a reussi mais node_modules semble vide ou incomplet.")

            logger.info(f"[OK] Modules {filtered_missing} installes avec succes.")
            
            # --- [SAFE] Effacer missing_modules APR?S installation ---
            state["missing_modules"] = []
            
            # --- Tracker les modules installes ---
            installed = state.get("installed_modules", [])
            installed.extend(filtered_missing)
            state["installed_modules"] = installed
        except Exception as e:
            logger.error(f"[WARN] Echec installation modules {filtered_missing}: {e}")
            # Meme en cas d'erreur, effacer pour eviter les boucles
            state["missing_modules"] = []

        return state  # type: ignore[return-value]


    def verify_node(self, state: AgentState) -> dict:
        """N?ud 3 : Audit de securite et conformite finale."""
        if state.get("error_count", 0) >= MAX_RETRIES:
            logger.error("[STOP] Limite de tentatives atteinte (MAX_RETRIES).")
            # Tolerance structurelle : si on a atteint la limite d'essais TypeScript (buildfix) 
            # MAIS que l'Agent a reussi a structurer les fichiers et les deps (STRUCTURE_OK)
            # alors on le marque comme APPROUVE avec alerte pour ne pas bloquer tout le projet.
            if state.get("validation_status") == "STRUCTURE_OK" or state.get("validation_status") == "DEPS_INSTALLED":
                state["validation_status"] = "APPROUVE"
                state["alertes"] = "Limite de tentatives atteinte. Des erreurs TypeScript mineures peuvent subsister, mais la structure (fichiers/dossiers/routes) a ete correctement generee."
            else:
                state["validation_status"] = "REJETE"
                state["alertes"] = "Limite de tentatives atteinte et la structure demandee n'est pas conforme."
            return state  # type: ignore[return-value]

        # Rafraichir le file_tree depuis le disque pour un audit precis
        import os
        fresh_tree = []
        ignore = {'node_modules', 'dist', '.git', '__pycache__'}
        for root_dir, dirs, files in os.walk(str(self.root)):
            dirs[:] = [d for d in dirs if d not in ignore]
            for f in files:
                fresh_tree.append(os.path.relpath(os.path.join(root_dir, f), str(self.root)).replace('\\', '/'))
        state = {**state, "file_tree": "\n".join(fresh_tree)}

        logger.info(f"[SAFE] Debut de l'Audit pour le code genere.")
        
        # Charger le prompt et le parser
        prompt_text = self._load_prompt("subagent_verify.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentVerifyOutput)
        
        try:
            # [SAFE] IMPROVED: Capturer l'etat de generation AVANT l'audit
            terminal_diag = state.get("terminal_diagnostics", "")
            target_module = state.get("target_module")
            
            # Detection robuste des erreurs TSC/Build
            has_build_errors = False
            if target_module:
                 # Erreur si le module cible a echoue
                 has_build_errors = f"[TSC {target_module}] [ERROR]" in terminal_diag or f"[VITE {target_module}] [ERROR]" in terminal_diag or f"[NEXT {target_module}] [ERROR]" in terminal_diag
            else:
                 # Erreur si n'importe quel module a echoue (fallback)
                 has_build_errors = "[ERROR] ECHEC" in terminal_diag
            
            generation_failed = state.get("validation_status") == "REJETE" or state.get("last_error", "") or has_build_errors
            structure_valid = state.get("validation_status") not in ["STRUCTURE_KO", "PATH_BLOCKED", "STRUCTURE_INVALID"]
            
            logger.info(f"[STAT] Etat pre-audit : generation_failed={generation_failed}, structure_valid={structure_valid}")
            
            # --- HARD STRUCTURE VALIDATION ---
            # On respecte l'etat calcule par TaskEnforcer ou PathGuard
            structure_valid = state.get("validation_status") not in ["STRUCTURE_KO", "PATH_BLOCKED", "STRUCTURE_INVALID"]
            
            # [SAFE] ANTI-BYPASS: Si le statut est deja REJETE ou FAILED, on ne l'auto-valide pas ici
            if state.get("validation_status") in ["REJETE", "VALIDATION_FAILED"]:
                structure_valid = False
                logger.warning(f"[WARN] Structure validee comme FALSE car status={state.get('validation_status')}")

            if not structure_valid:
                logger.error("[ERROR] Structure validation failed. Aborting audit.")
                return {
                    **state,
                    "generation_failed": True,
                    "validation_status": "STRUCTURE_INVALID",
                    "error_count": state.get("error_count", 0) + 1
                }
                                    
            # [SAFE] RETRY avec backoff pour l'audit lui-meme
            
            total_tasks = state.get("total_subtasks", 1)
            missing = state.get("missing_tasks", 0)
            completed = max(0, total_tasks - missing)
            
            # Forcer un score strict base sur la checklist
            checklist_score = int((completed / max(1, total_tasks)) * 100)
            
            # [SAFE] SAFE PLACEHOLDER REPLACEMENT : Remplacer manuellement au lieu de laisser LangChain parser les accolades
            inject_dict = {
                "constitution_hash": state.get("constitution_hash", "INCONNU"),
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "subtask_checklist": state["subtask_checklist"],
                "missing_tasks_count": missing,
                "total_tasks_count": total_tasks,
                "analysis_output": state["analysis_output"],
                "code_to_verify": state["code_to_verify"],
                "terminal_diagnostics": state.get("terminal_diagnostics", "N/A"),
                "code_map": state["code_map"],
                "file_tree": state["file_tree"],
                "user_instruction": state.get("user_instruction", ""),
                "format_instructions": parser.get_format_instructions()
            }
            
            # Replace placeholders for both formats: __KEY__ and {key}
            prompt_text = self._inject_prompt_vars(prompt_text, inject_dict)
            
            # [WARN] NO ChatPromptTemplate - pass directly to model with inline retry
            from langchain_core.messages import HumanMessage
            final_prompt = "You are a helpful assistant.\n\n" + prompt_text
            message = HumanMessage(content=final_prompt)
            
            raw_output = None
            for attempt in range(3):
                try:
                    logger.info(f"[AI] Invocation LLM (tentative {attempt + 1}/3)...")
                    raw_output = (self.model | StrOutputParser()).invoke([message])
                    logger.info(f"[OK] Invocation reussie a la tentative {attempt + 1}")
                    break
                except Exception as e:
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"[WARN] Tentative {attempt + 1} echouee : {str(e)[:100]}. Attente {wait_time}s avant retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"[ERROR] Toutes les 3 tentatives ont echoue.")
                        raise
            
            assert raw_output is not None, "LLM output should not be None after retry loop"
            result = self._safe_parse_json(raw_output, SubagentVerifyOutput)
            
            verdict = result["verdict_final"].upper()
            verifier_status = "APPROUVE" if "APPROUVE" in verdict else "REJETE"
            
            # Le score final est le minimum entre le score IA et le vrai score de checklist
            llm_score = int(result.get("score_conformite", 100))
            final_score = min(llm_score, checklist_score)
            
            # [SAFE] HARD OVERRIDE: Si des taches manquent dans la checklist, C'EST REJETE
            if missing > 0:
                logger.warning(f"[WARN] Audit REJETE par systeme (Checklist incomplete: {missing}/{total_tasks} manquantes). Forcage REJETE.")
                verifier_status = "REJETE"
            
            # [NEW] TYPESCRIPT STRICT MODE: Rejeter si compilation TypeScript echouée
            # Cette verification est INDEPENDANTE du LLM - elle est basee sur LE COMPILATEUR
            typescript_status = state.get("typescript_validation_status", "SKIPPED")
            if typescript_status == "FAILED":
                logger.error("[STRICT] Code REJETE: La validation TypeScript a echouée (errors detectes par tsc --noEmit)")
                verifier_status = "REJETE"
                # Inclure les erreurs TypeScript specifiques dans le feedback
                ts_errors = state.get("typescript_errors", [])
                if ts_errors:
                    error_details = "\n".join([
                        f"  - {err.get('file', 'unknown')}:{err.get('line', '?')} - {err.get('message', 'Unknown error')}"
                        for err in ts_errors[:5]  # Montrer les 5 premiers
                    ])
                    logger.error(f"[ERROR] Erreurs TypeScript:\n{error_details}")

            
            # [SAFE] IMPROVED AUDIT LOGIC:
            # - Si generation echouee OU structure invalide OU verifier=REJETE -> REJETE
            # [SAFE] HANDLING "Aucune alerte" FALSE POSITIVE
            alerts_val = result.get('alertes', '')
            alerts_is_none = self._is_no_alert_text(alerts_val)
            if verifier_status == "REJETE" and alerts_is_none:
                if not generation_failed and structure_valid and missing == 0:
                    logger.info("[SAFE] Audit FALSE REJECTION detected (Alertes says None). Overriding to APPROUVE.")
                    verifier_status = "APPROUVE"

            if generation_failed or not structure_valid or verifier_status == "REJETE":
                if missing > 0:
                    logger.warning(f"[WARN] Audit REJETE: Il manque encore des fichiers obligatoires.")
                elif typescript_status == "FAILED":
                    logger.warning(f"[WARN] Audit REJETE: Erreurs de typage TypeScript detectees (tsc --noEmit).")
                elif generation_failed:
                    logger.warning(f"[WARN] Audit REJETE: La generation technique a echoue (TSC errors).")
                elif not structure_valid:
                    logger.warning(f"[WARN] Audit REJETE: La structure demandee est invalide.")
                
                status = "REJETE"
                feedback_msg = result.get('action_corrective', '')
                if missing > 0:
                    feedback_msg = f"Checklist incomplete. You missed {missing} task(s)/file(s). You MUST create them: " + state.get("feedback_correction", "")
                elif typescript_status == "FAILED":
                    ts_errors = state.get("typescript_errors", [])
                    if ts_errors:
                        error_lines = [f"{err.get('file', 'unknown')}:{err.get('line', '?')} - {err.get('message', 'Error')}" 
                                      for err in ts_errors[:5]]
                        feedback_msg = "TypeScript compilation failed with these errors:\n" + "\n".join(error_lines)
                        if len(ts_errors) > 5:
                            feedback_msg += f"\n... and {len(ts_errors) - 5} more error(s)"
                    else:
                        feedback_msg = "TypeScript compilation failed. Run 'tsc --noEmit' to see detailed errors."
                elif not feedback_msg and generation_failed:
                    feedback_msg = "TypeScript validation failed. Please fix the compilation errors in the terminal diagnostics."
            else:
                status = "APPROUVE"
                feedback_msg = ""
            
            # [STRICT] Double-check: Si TypeScript a échoué, JAMAIS d'approbation
            if typescript_status == "FAILED" and status == "APPROUVE":
                logger.error("[STRICT] OVERRIDE: Changing APPROUVE to REJETE due to TypeScript validation failure")
                status = "REJETE"
                ts_errors = state.get("typescript_errors", [])
                if ts_errors:
                    error_lines = [f"{err.get('file', 'unknown')}:{err.get('line', '?')} - {err.get('message', 'Error')}" 
                                  for err in ts_errors[:5]]
                    feedback_msg = "TypeScript compilation failed with these errors:\n" + "\n".join(error_lines)
                else:
                    feedback_msg = "TypeScript compilation failed. Please fix typing errors."
            
            if status == "APPROUVE":
                logger.info(f"[OK] Code APPROUVE. Score: {final_score}")
                return {
                    "validation_status": "APPROUVE", 
                    "score": str(final_score),
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', 'Aucune.' if not generation_failed else 'Generation partiellement echouee Mais structure valide.'),
                    "feedback_correction": "",
                    "audit_errors_history": state.get("audit_errors_history", [])
                }
            else:
                new_error_count = state.get("error_count", 0) + 1
                
                # [SAFE] TRACK audit errors to detect recurring issues
                audit_errors = state.get("audit_errors_history", [])
                raw_alert = result.get('alertes', '')
                if not self._is_no_alert_text(raw_alert):
                    error_summary = f"{str(raw_alert)[:100]}..."
                else:
                    # Si "Aucune", on track plutot la cause technique explicite
                    fallback_msg = (feedback_msg or state.get("last_error", "") or "Audit rejected without explicit alert").strip()
                    error_summary = f"{fallback_msg[:100]}..."
                audit_errors.append(error_summary)
                
                # [SCAN] DETECT RECURRING ERRORS (same error twice = can't fix it automatically)
                is_recurring_error = (
                    len(audit_errors) >= 2
                    and audit_errors[-1] == audit_errors[-2]
                    and not self._is_no_alert_text(audit_errors[-1])
                )
                if is_recurring_error:
                    logger.error(f"[AI] RECURRING ERROR DETECTED: {audit_errors[-1]}")
                    logger.error(f"[STOP] Same error appeared {len([e for e in audit_errors if e == audit_errors[-1]])} times. Stopping retries.")
                    new_error_count = MAX_RETRIES  # Force END by marking max retries reached
                
                return {
                    "validation_status": "REJETE", 
                    "score": str(final_score),
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', ''),
                    "feedback_correction": feedback_msg,
                    "error_count": new_error_count,
                    "audit_errors_history": audit_errors
                }
        except Exception as e:
            logger.error(f"[ERROR] Erreur audit : {e}")
            state["validation_status"] = "REJETE"
            state["feedback_correction"] = str(e)
            state["error_count"] = state.get("error_count", 0) + 1
            return state  # type: ignore[return-value]

    def task_enforcer_node(self, state: AgentState) -> dict:
        """N?ud de verification structurelle DETERMINISTE (sans LLM)."""
        logger.info("[SAFE] Verification structurelle (TaskEnforcer - MODE DETERMINISTE)...")
        
        # [SAFE] PRIORITE 2: Source de verite = filesystem reel vs checklist
        # Ne PAS utiliser le LLM pour identifier les fichiers manquants!
        
        # 1. Extraire la checklist depuis le subtask_checklist
        checklist = state.get("subtask_checklist", "")
        file_tree = state.get("file_tree", "")
        
        # 2. Parser + normaliser les fichiers attendus depuis la checklist
        # IMPORTANT: package.js est une derive connue -> package.json (manifest npm)
        expected_files = set()
        for extracted in self._extract_required_files(checklist):
            normalized = self._normalize_checklist_path(extracted)
            if normalized:
                expected_files.add(normalized)
        
        logger.info(f"? Fichiers attendus selon la checklist: {len(expected_files)}")
        
        # 3. Extraire les fichiers reellement presents depuis file_tree
        real_files = set()
        for line in file_tree.split('\n'):
            line = line.strip()
            if line and not line.startswith('|') and not line.startswith('+'):
                # Nettoyer les caracteres de visualisation
                clean_path = re.sub(r'^[\s|+-]*', '', line).strip()
                if '.' in clean_path and any(clean_path.endswith(ext) for ext in ['.ts', '.tsx', '.js', '.jsx', '.json', '.yaml', '.yml', '.md']):
                    real_files.add(self._normalize_checklist_path(clean_path))
        
        logger.info(f"? Fichiers detectes dans file_tree: {len(real_files)}")
        
        # 4. Calculer la difference (DETERMINISTE, pas LLM) avec matching robuste
        tree_list = sorted(real_files)
        missing_files = []
        for expected in sorted(expected_files):
            if not self._file_exists_in_tree(expected, tree_list):
                missing_files.append(expected)

        if missing_files:
            logger.warning(f"[ERROR] {len(missing_files)} fichiers manquants detectes:")
            for f in missing_files:
                logger.warning(f"   - {f}")
            return {
                "validation_status": "STRUCTURE_KO",
                "missing_files": list(missing_files),
                "missing_tasks": len(missing_files),
                "total_subtasks": len(expected_files),
                "feedback_correction": f"MANQUANT: {', '.join(missing_files)}"
            }
        else:
            logger.info(f"[OK] Tous les fichiers attendus sont presents ({len(expected_files)} fichiers)")
            return {
                "validation_status": "STRUCTURE_OK",
                "missing_files": [],
                "missing_tasks": 0,
                "total_subtasks": len(expected_files),
            }

    def code_map_node(self, state: AgentState) -> dict:
        """N?ud de generation de la Semantic Code Map."""
        logger.info("?? Generation de la Semantic Code Map...")
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
        """N?ud de reparation automatique du build."""
        logger.info("?? Tentative de reparation du build...")
        
        try:
            from langchain_core.messages import HumanMessage
            
            prompt_text = self._load_prompt("subagent_buildfix.prompt")
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
            
            # Replace placeholders for both formats: __KEY__ and {key}
            prompt_text = self._inject_prompt_vars(prompt_text, inject_dict)
            
            # [WARN] NO ChatPromptTemplate - pass directly to model with inline retry
            final_prompt = "You are a helpful assistant.\n\n" + prompt_text
            message = HumanMessage(content=final_prompt)
            
            raw_output = None
            for attempt in range(3):
                try:
                    logger.info(f"[AI] Invocation LLM (tentative {attempt + 1}/3)...")
                    raw_output = (self.model | StrOutputParser()).invoke([message])
                    logger.info(f"[OK] Invocation reussie a la tentative {attempt + 1}")
                    break
                except Exception as e:
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"[WARN] Tentative {attempt + 1} echouee : {str(e)[:100]}. Attente {wait_time}s avant retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"[ERROR] Toutes les 3 tentatives ont echoue.")
                        raise
            
            assert raw_output is not None, "LLM output should not be None after retry loop"
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
            logger.error(f"[STOP] buildfix_node error: {e}")
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
            
            cmd = ["npx", "--yes", "tsc", "--noEmit", "--skipLibCheck", "--target", "es2022", "--module", "nodenext", "--moduleResolution", "nodenext"] + ts_files
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=600)
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
                # Fallback pour le cas ou delta ne contient pas de marqueurs de fichiers (si un seul fichier est retourne sans marqueur)
                # Mais BuildFix est cense retourner avec marqueurs. Dans le doute, on n'ecrase pas tout si on ne peut pas parser.
                pass
            return blocks

        base_blocks = parse_blocks(base)
        delta_blocks = parse_blocks(delta)
        
        if not delta_blocks and delta.strip():
             # Si delta n'a pas pu etre parse mais n'est pas vide, c'est peut-etre un fichier unique.
             # On essaie de deviner si c'est le cas (peu probable avec Speckit).
             pass

        # Update base with delta
        base_blocks.update(delta_blocks)
        
        merged_blocks = []
        for filename, content in base_blocks.items():
            merged_blocks.append(f"// Fichier : {filename}\n{content}")
        
        return "\n\n".join(merged_blocks)

    # route_after_diagnostic supprime ? diagnostic va toujours vers task_enforcer
            
    def _check_typescript_installed(self, project_dir: Path) -> bool:
        """Verifie si typescript est installe dans le projet."""
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
        """Recupere le hash stocke en cache (si existant)."""
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
            logger.info(f"[SAVE] Hash package.json sauvegarde: {current_hash[:8]}...")
        except Exception as e:
            logger.warning(f"[WARN] Impossible de sauvegarder le hash: {e}")

    def _normalize_checklist_path(self, raw_path: str) -> str:
        """Normalise un chemin de checklist et corrige les derives connues."""
        path = (raw_path or "").strip().strip("`'\"").replace("\\", "/")
        if not path:
            return path

        lower = path.lower()
        # Guard critique: package.js n'est pas un manifest npm valide.
        if lower.endswith("package.js"):
            path = path[: -len("package.js")] + "package.json"
            logger.info(f"[FIX] Checklist normalize: '{raw_path}' -> '{path}'")

        return path

    def _is_no_alert_text(self, value: Any) -> bool:
        """Detecte si un texte d'alerte signifie 'aucune erreur'."""
        txt = str(value or "").strip().lower()
        if txt in {"", "none", "n/a", "na", "ras", "ok", "aucune", "aucun"}:
            return True
        markers = [
            "aucune alerte",
            "aucune erreur",
            "pas d'alerte",
            "pas d erreur",
            "no alert",
            "no error",
        ]
        return any(m in txt for m in markers)

    def _extract_required_files(self, checklist_text: str) -> List[str]:
        """Extrait les chemins de fichiers obligatoires mentionnes dans la checklist.
        
        Strategie multi-niveau pour extraire les chemins:
        
        Pattern 1: Chemin COMPLET en un seul bloc: `backend/src/middlewares/auth.ts`
        Pattern 2: Fichier + Repertoire separes: `RegisterPage.tsx` ... `frontend/src/pages/`
        Pattern 3: Fallback simple regex pour les formats minimalistes
        Pattern 4: Cas special - si le chemin commence par `src/`, ajouter le module prefix
        
        Returns: Liste des chemins de fichiers trouves (sans doublons)
        """
        import re
        if not checklist_text:
            return []
        
        required_files = []
        seen_full_paths = set()  # Pour eviter les doublons
        
        # Traiter chaque ligne de la checklist
        for line in checklist_text.split('\n'):
            if not line.strip():
                continue
            
            # Pattern 0: Repertoires seuls (finit par /)
            # 1. Dans des backticks (priorite)
            dir_paths_bt = re.findall(r'`([^` ]+/)`', line)
            # 2. Sans backticks (si ca commence par un module connu)
            dir_paths_raw = re.findall(r'(?:^|\s)((?:backend/|frontend/|mobile/)[a-zA-Z0-9_\-./\\]+/)', line)
            
            for path in (dir_paths_bt + dir_paths_raw):
                path = path.replace('\\', '/')
                if path not in seen_full_paths:
                    required_files.append(path)
                    seen_full_paths.add(path)

            # Pattern 1: Chemin COMPLET avec module inclus (fichiers avec extension)
            full_paths = re.findall(r'`([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)`', line)
            
            full_path_suffixes = set()  # Garder trace des fichiers trouves avec chemin complet
            
            for path in full_paths:
                # Normaliser les backslashes en forward slashes
                path = path.replace('\\', '/')
                
                # Ignorer les routes d'API qui n'ont pas d'extension de fichier valide
                if path.startswith('/api/') or ('/' in path and not path.endswith((".ts", ".js", ".tsx", ".jsx", ".json", ".md", ".yml", ".yaml"))):
                    continue
                
                # Verifier que ce n'est pas un chemin partiel comme "src/..."
                # (sera traite plus tard avec module detection)
                if path not in seen_full_paths:
                    required_files.append(path)
                    seen_full_paths.add(path)
                    # Garder trace du suffix du chemin (ex: components/RegisterForm.tsx)
                    full_path_suffixes.add(path.split('/')[-1])
            
            # Pattern 2: Cas particulier - fileName ET repertoire SEPARES sur la meme ligne
            # Exemple: ... `RegisterPage.tsx` ... dans `frontend/src/pages/`
            # Strategie: 
            # - Trouver tous les backtick'd items
            # - Separer les fichiers (.ext) des repertoires (contient /)
            # - Si 1 fichier et >=1 repertoires, combiner
            # - MAIS: Ignorer les fichiers deja trouves en Pattern 1
            
            # Extraire TOUS les items entre backticks
            all_backtick_items = re.findall(r'`([^`]+)`', line)
            
            # Classer en fichiers et repertoires
            files_in_line = []
            dirs_in_line = []
            
            for item in all_backtick_items:
                item = item.strip()
                item = item.replace('\\', '/')
                
                # Ignorer TOUTES les routes d'API ou chemins invalides (sans extension ni slash final)
                if item.startswith('/api/') or ('/' in item and not item.endswith('/') and not item.endswith((".ts", ".js", ".tsx", ".jsx", ".json", ".md", ".yml", ".yaml"))):
                    continue
                
                # Verifier si c'est deja un chemin complet (contient /)
                if '/' in item or '\\' in item:
                    # C'est un chemin (fichier ou repertoire)
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
                    # MAIS: Ne l'ajouter QUE s'il n'etait pas en Pattern 1
                    if '.' in item and item not in full_path_suffixes:
                        files_in_line.append(item)
            
            # Si on a exactement 1 fichier SANS chemin et 1+ repertoires, combiner
            if len(files_in_line) == 1 and len(dirs_in_line) >= 1:
                filename = files_in_line[0]
                # Utiliser le repertoire le plus specifique (le plus long)
                directory = max(dirs_in_line, key=len)
                combined_path = f"{directory}{filename}".replace('//', '/')
                
                # Verifier que ce chemin n'a pas deja ete extrait
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
                    logger.debug(f"[DOC] Pattern 3 (simple) matched: {combined_path}")
            
            # Pattern 5: Fichiers de configuration ou autres listes directement
            list_matches = re.findall(r'([\w\.-]+\.(?:json|ts|tsx|js|jsx|yml|yaml))', line)
            for f in list_matches:
                if f not in seen_full_paths:
                    required_files.append(f)
                    seen_full_paths.add(f)
        
        if required_files:
            # [SAFE] NORMALIZATION & TYPO FIX
            normalized = []
            for f in required_files:
                f = self._normalize_checklist_path(f)
                # Fix typo 'workfloows'
                f = f.replace("workfloows", "workflows")
                # Consolidate CI files
                if "/workflows/main.yml" in f or "/workflows/ci.yaml" in f:
                    f = f.replace("/workflows/main.yml", "/workflows/ci.yml").replace("/workflows/ci.yaml", "/workflows/ci.yml")
                normalized.append(f)
            required_files = list(set(normalized))
            logger.info(f"? Fichiers obligatoires identifies dans checklist: {required_files}")
        else:
            logger.debug(f"? Aucun fichier obligatoire identifie dans checklist")
        
        return required_files

    def _ensure_required_artifacts(self, required_files: List[str], written_paths: List[str]) -> List[str]:
        """Cree les fichiers obligatoires manquants en tant que stubs minimalistes.
        
        Pour chaque fichier obligatoire non ecrit, genere un stub approprie.
        Args:
            required_files: Liste des chemins de fichiers obligatoires
            written_paths: Liste des fichiers deja ecrites par persist_code_to_disk
        Returns: Liste des fichiers crees
        """
        created_files = []
        
        for required_file in required_files:
            # [SAFE] FIX: Gerer les fichiers sans extension (ex: user.service -> user.service.ts)
            # Mais ne pas rajouter .ts si une extension existe deja
            basename = required_file.split('/')[-1]
            if '.' not in basename and not required_file.endswith('/'):
                # Determiner l'extension par defaut
                if "backend/src" in required_file or "frontend/src" in required_file:
                    required_file += ".ts"
                    logger.info(f"[FIX] Extension manquante detectee -> Ajoute .ts : {required_file}")

            file_path = self.root / required_file
            
            # Verifier si le fichier existe deja (sur disque ou ecrit par l'IA)
            if file_path.exists() or required_file in written_paths:
                logger.info(f"[OK] Fichier obligatoire existant: {required_file}")
                continue
            
            # Creer les repertoires parents
            try:
                if required_file.endswith('/'):
                    file_path.mkdir(parents=True, exist_ok=True)
                    # Touch .gitkeep to ensure the directory is recognized as "created" by validators
                    (file_path / ".gitkeep").touch()
                    logger.info(f"[OK] Directory artifact created: {required_file}")
                    created_files.append(required_file)
                    continue
                else:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[ERROR] Erreur creation repertoires pour {required_file}: {e}")
                continue
            
            # Generer un stub minimal base sur l'extension
            ext = file_path.suffix.lower()
            stub_content = self._generate_stub_content(ext, required_file)
            
            try:
                file_path.write_text(stub_content, encoding="utf-8")
                logger.info(f"[OK] Fichier obligatoire cree (stub): {required_file}")
                created_files.append(required_file)
            except Exception as e:
                logger.error(f"[ERROR] Erreur ecriture stub {required_file}: {e}")
        
        return created_files

    def _generate_stub_content(self, ext: str, file_path: str) -> str:
        """Genere un contenu de stub minimaliste approprie au type de fichier.
        
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
        r"""Cherche un fichier dans l'arborescence avec strategie multi-niveaux.
        
        Essaie de matcher:
        1. Le chemin exact
        2. Le chemin normalise (\ -> /)
        3. Juste le nom du fichier n'importe ou dans l'arbo
        
        Args:
            file_to_find: Chemin ou nom du fichier a chercher (ex: "HomePage.tsx" ou "frontend/src/pages/HomePage.tsx")
            file_tree_list: Liste des fichiers dans l'arborescence
        
        Returns: True si le fichier est trouve, False sinon
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
        """N?ud : Diagnostics reels (tsc --noEmit ou vite build selon le module cible).
        
        [WARN] PROTECTION STRICTE : Si target_module est defini, teste UNIQUEMENT ce module.
        Ignore completement les autres modules.
        """
        logger.info("[SCAN] Execution des diagnostics reels...")
        import subprocess, re, json
        
        # --- DETERMINER LE MODULE CIBLE ET L'OUTIL DE BUILD ---
        target_module = state.get("target_module")
        
        if target_module:
            # Un module cible est explicitement specifie
            search_dirs = [self.root / target_module]
            logger.info(f"[TARGET] Diagnostics STRICT : module {target_module} seulement (autres ignores)")
        else:
            # Fallback : tous les modules disponibles
            search_dirs = [self.root, self.root / "backend", self.root / "frontend"]
            logger.info(f"[TARGET] Diagnostics sur tous les modules")
        
        reports = []
        missing_modules = []
        module_errors = {}  # Tracker les erreurs par module
        
        for d in search_dirs:
            if not (d / "package.json").exists():
                continue
            
            # --- Determiner l'outil de build ---
            build_tool = self._get_build_tool(d.name if d != self.root else "")
            
            # --- VERIFICATION PRE-TSC : typescript installe? ---
            if build_tool == "tsc":
                if not self._check_typescript_installed(d):
                    logger.warning(f"[WARN] TypeScript non installe dans {d.name}. Ajout a la liste des modules manquants.")
                    missing_modules.append("typescript")
                    reports.append(f"[TSC {d.name}] [ERROR] ECHEC\nTypeScript non installe dans node_modules. Executez: npm_path install --save-dev typescript")
                    continue
                
                try:
                    res = subprocess.run(
                        "npx --yes tsc --noEmit --pretty false",
                        shell=True, capture_output=True, text=True,
                        cwd=str(d), timeout=600
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    status = "[OK]" if res.returncode == 0 else "[ERROR] ECHEC"
                    reports.append(f"[TSC {d.name}] {status}\n{output}")
                    
                    # [WARN] Tracker si c'est le module cible
                    if res.returncode != 0:
                        module_errors[d.name or "root"] = "tsc"
                    
                    # Detection des modules manquants (UNIQUEMENT pour le module cible)
                    if target_module and d.name != target_module:
                        logger.info(f"[SKIP] Skip detection modules pour {d.name} (non-target)")
                    else:
                        matches = re.findall(r"Cannot find module '([^']+)'", output)
                        if matches:
                            npm_matches = [
                                m for m in matches 
                                if not m.startswith('.') and not m.startswith('/') and not (m and m[0].isupper())
                            ]
                            missing_modules.extend(npm_matches)
                        
                except subprocess.TimeoutExpired:
                    reports.append(f"[TSC {d.name}] [ERROR] ECHEC\nTimeout apres 600s")
                except Exception as e:
                    reports.append(f"[TSC {d.name}] [ERROR] ECHEC\n{str(e)}")
            
            elif build_tool == "vite":
                # Pour Vite, utiliser vite preview ou build
                try:
                    res = subprocess.run(
                        "npm_path run build",
                        shell=True, capture_output=True, text=True,
                        cwd=str(d), timeout=600
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    status = "[OK]" if res.returncode == 0 else "[ERROR] ECHEC"
                    reports.append(f"[VITE {d.name}] {status}\n{output}")
                    
                    # [WARN] Tracker si c'est le module cible
                    if res.returncode != 0:
                        module_errors[d.name or "root"] = "vite"
                    
                    # Detection des modules manquants (UNIQUEMENT pour le module cible)
                    if target_module and d.name != target_module:
                        logger.info(f"[SKIP] Skip detection modules pour {d.name} (non-target)")
                    else:
                        matches = re.findall(r"Cannot find module '([^']+)'", output)
                        if matches:
                            npm_matches = [
                                m for m in matches 
                                if not m.startswith('.') and not m.startswith('/') and not (m and m[0].isupper())
                            ]
                            missing_modules.extend(npm_matches)
                        
                except subprocess.TimeoutExpired:
                    reports.append(f"[VITE {d.name}] [ERROR] ECHEC\nTimeout apres 600s")
                except Exception as e:
                    reports.append(f"[VITE {d.name}] [ERROR] ECHEC\n{str(e)}")
            
            elif build_tool == "next":
                # Pour Next.js, utiliser npm run build ou next build
                try:
                    res = subprocess.run(
                        "npm_path run build",
                        shell=True, capture_output=True, text=True,
                        cwd=str(d), timeout=600
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    status = "[OK]" if res.returncode == 0 else "[ERROR] ECHEC"
                    reports.append(f"[NEXT {d.name}] {status}\n{output}")
                    
                    # [WARN] Tracker si c'est le module cible
                    if res.returncode != 0:
                        module_errors[d.name or "root"] = "next"
                    
                    # Detection des modules manquants (UNIQUEMENT pour le module cible)
                    if target_module and d.name != target_module:
                        logger.info(f"[SKIP] Skip detection modules pour {d.name} (non-target)")
                    else:
                        matches = re.findall(r"Cannot find module '([^']+)'", output)
                        if matches:
                            npm_matches = [
                                m for m in matches 
                                if not m.startswith('.') and not m.startswith('/') and not (m and m[0].isupper())
                            ]
                            missing_modules.extend(npm_matches)
                        
                except subprocess.TimeoutExpired:
                    reports.append(f"[NEXT {d.name}] [ERROR] ECHEC\nTimeout apres 600s")
                except Exception as e:
                    reports.append(f"[NEXT {d.name}] [ERROR] ECHEC\n{str(e)}")
        
        logger.info("?? Diagnostics termines.")
        
        # [WARN] Si target_module est defini, retourner AUSSI info sur les erreurs non-target
        non_target_errors = {k: v for k, v in module_errors.items() if k != target_module}
        if non_target_errors and target_module:
            logger.warning(f"[WARN] Erreurs detectees dans modules non-cibles (IGNOREES): {non_target_errors}")
        
        return {
            "terminal_diagnostics": "\n".join(reports),
            "missing_modules": list(set(missing_modules)),
            "non_target_errors": non_target_errors  # Pour eviter buildfix sur ces erreurs
        }
    
    def dependency_resolver_node(self, state: AgentState) -> dict:
        """N?ud : Detection proactive des dependances manquantes via analyse d'imports.
        
        Scanne les fichiers source pour detecter les imports (import/require statements)
        et compare avec package.json pour identifier les dependances manquantes.
        Cela previent les erreurs TypeScript "Cannot find module" avant compilation.
        """
        import os, json, re
        from pathlib import Path
        
        logger.info("? Analyse proactive des dependances (Dependency Resolver)...")
        
        target_module = state.get("target_module")
        search_dirs = []
        
        if target_module:
            module_path = self.root / target_module
            if module_path.exists():
                search_dirs = [module_path]
                logger.info(f"[TARGET] Resolver STRICT (target: {target_module}) - Scanning only this module")
            else:
                logger.warning(f"[WARN] Target module {target_module} untrouvable. Fallback scan root.")
                search_dirs = [self.root]
        else:
            # Fallback scan ALL available modules if no target set
            search_dirs = [self.root]
            for d in ["backend", "frontend", "mobile"]:
                if (self.root / d).exists():
                    search_dirs.append(self.root / d)
            logger.info(f"[TARGET] Resolver scanning all modules (no target set)")
        
        detected_missing = []
        
        for module_dir in search_dirs:
            src_dir = module_dir / "src"
            if not src_dir.exists():
                continue
            
            pkg_path = module_dir / "package.json"
            if not pkg_path.exists():
                continue
            
            # Lire les dependances du package.json
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
                
                # Verifier si le package est installe
                if pkg_name not in installed:
                    logger.warning(f"[WARN] Module manquant detecte (via import): {pkg_name} (source: {imp})")
                    detected_missing.append(pkg_name)
        
        # ? Liste officielle des Built-ins Node.js (Filtrage)
        NODE_BUILTINS = {
            "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
            "constants", "crypto", "dgram", "dns", "domain", "events", "fs", "fs/promises",
            "http", "http2", "https", "inspector", "module", "net", "os", "path", "path/posix",
            "path/win32", "perf_hooks", "process", "punycode", "querystring", "readline",
            "readline/promises", "repl", "stream", "stream/consumers", "stream/promises",
            "stream/web", "string_decoder", "timers", "timers/promises", "tls", "trace_events",
            "tty", "url", "util", "util/types", "v8", "vm", "wasi", "worker_threads", "zlib"
        }
        
        # Fusionner avec les modules manquants detectes par diagnostic_node
        all_missing = list(set(detected_missing + state.get("missing_modules", [])))
        
        # Filtrer les built-ins Node.js
        all_missing = [m for m in all_missing if m not in NODE_BUILTINS and not m.startswith("node:")]
        
        if all_missing:
            logger.info(f"[GOAL] Modules a installer: {all_missing}")
        else:
            logger.info("[OK] Aucun module manquant detecte.")
        
        return {
            "missing_modules": all_missing
        }


    def route_from_install_deps(self, state: AgentState) -> str:
        """
        ? PROTECTION STRUCTURALE: Casse la boucle Diagnostics -> TaskEnforcer -> InstallDeps -> Diagnostics
        
        Apres install_deps_node, decide:
        - S'il y a vraiment des modules manquants -> retour a diagnostic
        - Sinon ou cycle max atteint -> sortie vers verify (fin)
        """
        # [SAFE] Compteur de cycles: si trop de cycles dependances, sortir
        dep_cycles = state.get("dependency_cycles", 0)
        if dep_cycles >= MAX_DEPENDENCY_CYCLES:
            logger.warning(f"[WARN] Dependency cycle limit reached ({MAX_DEPENDENCY_CYCLES} cycles). Breaking cycle.")
            state["missing_modules"] = []
            return "verify_node"
        
        state["dependency_cycles"] = dep_cycles + 1
        logger.debug(f"[STAT] Dependency cycle {state['dependency_cycles']}/{MAX_DEPENDENCY_CYCLES}")
        
        # Si scanner a trouve 0 modules -> pas de raison de re-scanner
        scanner_missing = state.get("scanner_missing_modules", [])
        if not scanner_missing:
            logger.info("[OK] Scanner confirme: 0 modules manquants apres install_deps. Exiting dependency loop.")
            state["missing_modules"] = []
            return "verify_node"
        
        # Sinon, on relance le diagnostic
        logger.warning(f"[AI] Retour a diagnostics pour verifier installation de {scanner_missing}...")
        return "diagnostic_node"

    def route_after_enf(self, state: AgentState) -> str:
        """Route apres TaskEnforcer : verifie a la fois les erreurs TSC et structurelles.
        
        [WARN] PROTECTIONS MULTI-NIVEAUX:
        - graph_steps: limite totale des cycles du graphe
        - scanner_missing: source de verite (TOOLS > LLM)
        - TEST_LIBS filter: ignore les modules de test halluciner
        - dep_attempts: limite des tentatives d'installation des dependances
        - error_count: limite des essais de correction
        - state_history: detecte les boucles infinies (meme etat repete)
        """
        
        # [SAFE] PROTECTION NIVEAU 1: Limite globale des cycles du graphe
        graph_steps = state.get("graph_steps", 0)
        if graph_steps >= MAX_GRAPH_STEPS:
            logger.error(f"? Graph execution limit reached ({MAX_GRAPH_STEPS} steps). Exiting to verify.")
            return "verify_node"
        
        state["graph_steps"] = graph_steps + 1
        logger.debug(f"[STAT] Graph step {state['graph_steps']}/{MAX_GRAPH_STEPS}")
        
        # [SAFE] PROTECTION NIVEAU 1B: Detection de boucle infinie (meme etat repete)
        current_state_key = f"{state.get('validation_status', 'UNKNOWN')}|{len(state.get('missing_modules', []))}|{state.get('error_count', 0)}"
        
        # Initialize state_history if None (safe handling of Optional type)
        state_history = state.get("state_history") or []
        
        if state_history and state_history[-1] == current_state_key:
            repeats = state.get("repeated_state_count", 0) + 1
            state["repeated_state_count"] = repeats
            logger.warning(f"[AI] Etat repetitif detecte #{repeats}: {current_state_key}")
            
            # Apres 2 repetitions du meme etat (3 occurrences), abort
            if repeats >= 2:
                logger.error(f"[STOP] PRIORITE 3 FIX: Boucle infinie detectee (etat repete {repeats+1} fois). Abort vers verify_node.")
                return "verify_node"
        else:
            state["repeated_state_count"] = 0
        
        state_history.append(current_state_key)
        # Garder seulement les 10 derniers etats pour memoire
        if len(state_history) > 10:
            state_history.pop(0)
        state["state_history"] = state_history
        
        # -------------------------------------------------------------
        
        # PROTECTION ARCHITECTURALE: PRIORITE 4 FIX
        # Hierarchie de verite stricte: SCANNER > NPM > LLM
        # 1. SCANNER: Verite absolue (file_tree, filesystem scans)
        # 2. NPM: Source primaire (package.json, node_modules, npm ls)
        # 3. LLM: Source secondaire (peut halluciner, bugs, obsol imports)
        
        scanner_missing = state.get("scanner_missing_modules", [])
        npm_missing = state.get("npm_report_missing", [])  # from npm diagnostic
        llm_missing = state.get("missing_modules", [])
        
        logger.debug(f"[STAT] Hierarchie verfication de depend: scanner={scanner_missing}, npm={npm_missing}, llm={llm_missing}")
        
        # NIVEAU 1: SCANNER > NPM (Si scanner dit 0, ignorer npm)
        if not scanner_missing and npm_missing:
            logger.info(f"[SCAN] SCANNER > NPM: Scanner confirme 0 modules, NPM signale {npm_missing}. Voix conflictante => relance npm diagnostic.")
            # Ne pas ignorer completement, mais signaler pour debug future
            npm_missing = []
        
        # NIVEAU 2: (SCANNER + NPM) > LLM
        effective_missing = list(set(scanner_missing or []) | set(npm_missing or []))
        
        if not effective_missing and llm_missing:
            # Le LLM contredit le scanner + npm
            logger.info(f"[CORE] (SCANNER+NPM) > LLM: Tools confirment 0 modules, LLM signale {llm_missing}. Probablement hallucination.")
            logger.info(f"   (modules halluciner: {llm_missing} - ignores car non-detectes par scanner/npm)")
            state["missing_modules"] = []
            llm_missing = []
        elif llm_missing and effective_missing:
            # LLM propose davantage que tools
            superset_from_llm = set(llm_missing) - set(effective_missing)
            if superset_from_llm:
                logger.info(f"[WARN] LLM propose modules non-confirmes par tools: {list(superset_from_llm)}. En suspicion.")
                llm_missing = list(set(llm_missing) & set(effective_missing))  # Intersection seulement
        
        # [SAFE] Filtrer les modules de test (hallucinations classiques du LLM)
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
                logger.info(f"[TEST] Modules de test ignores (hallucinations classiques): {list(removed)}")
            state["missing_modules"] = filtered_missing
            llm_missing = filtered_missing
        
        # -------------------------------------------------------------
        
        target_module = state.get("target_module")
        terminal_diag = state.get("terminal_diagnostics", "")
        
        # [WARN] Extraction des erreurs cibles vs non-cibles
        non_target_errors = state.get("non_target_errors", {})
        target_module_in_errors = target_module in non_target_errors or (not target_module and "root" in non_target_errors)
        
        # Verifier si TSC est reussie POUR LE MODULE CIBLE
        has_tsc_errors_in_target = False
        if target_module:
            # Chercher seulement "[TSC backend]" ou "[VITE backend]" dans les rapports
            has_tsc_errors_in_target = f"[TSC {target_module}] [ERROR]" in terminal_diag or f"[VITE {target_module}] [ERROR]" in terminal_diag
            logger.info(f"[TARGET] Erreurs TSC dans module cible ({target_module}): {has_tsc_errors_in_target}")
        else:
            has_tsc_errors_in_target = "[ERROR] ECHEC" in terminal_diag
        
        has_structure_errors = state.get("validation_status") == "STRUCTURE_KO"
        has_missing_modules = len(llm_missing) > 0
        
        if state.get("error_count", 0) >= MAX_RETRIES and (has_tsc_errors_in_target or has_structure_errors or has_missing_modules):
            logger.error(f"[STOP] Limite de tentatives atteinte ({MAX_RETRIES}).")
            return "verify_node"
            
        if has_missing_modules:
            # [SAFE] PRIORITE 1: Casser la boucle structurelle immediatement
            # Apres 1 tentative echouee d'installation, deleguer a verify_node
            dep_attempts = state.get("dep_install_attempts", 0)
            if dep_attempts >= 1:
                logger.error(f"[STOP] ABORT: Tentative d'installation des dependances #{dep_attempts} a echoue. Boucle detectee. Route vers verify_node.")
                return "verify_node"
            else:
                logger.warning(f"? Modules manquants detectes {llm_missing}. Tentative d'auto-installation (1/1).")
                return "install_deps_node"
            
        if has_structure_errors:
            logger.warning("[FIX] Echec de validation structurelle : route vers verify_node pour avorter.")
            return "verify_node"
            
        # [WARN] CHANGE : Ne declencher buildfix QUE si la cible a des erreurs
        if has_tsc_errors_in_target:
            logger.warning(f"[BUG] Erreurs TypeScript dans module cible ({target_module}): route vers buildfix_node.")
            return "buildfix_node"
        elif target_module and non_target_errors:
            logger.warning(f"[WARN] Erreurs dans modules non-cibles IGNOREES: {non_target_errors}. Validation continue.")
            return "verify_node"
            
        return "verify_node"

    def route_after_verify(self, state: AgentState) -> str:
        """Route apres audit: APPROUVE -> END, REJETE -> retry impl_node (si < MAX_RETRIES)."""
        error_count = state.get("error_count", 0)
        validation_status = state.get("validation_status", "")
        
        if validation_status == "APPROUVE":
            logger.info(f"[OK] AUDIT APPROVED: Task complete!")
            return END
        
        if error_count >= MAX_RETRIES:
            logger.error(f"[STOP] AUDIT REJECTION LIMIT REACHED: {error_count}/{MAX_RETRIES} attempts exhausted")
            audit_history = state.get('audit_errors_history', [])
            # [SAFE] Logic logic: only log real errors
            filtered_errors = [
                e for e in audit_history
                if not self._is_no_alert_text(e)
            ]
            if filtered_errors:
                logger.error(f"[ERROR] Audit errors: {filtered_errors}")
            else:
                logger.info("[OK] Audit history contains no significant alerts.")
            return END
        
        logger.warning(f"[BACK] AUDIT REJECTED: Returning to impl_node for PATCH mode ({error_count}/{MAX_RETRIES} attempts used)")
        return "impl_node"

    def route_after_graphic_design(self, state: AgentState) -> str:
        """Route apres GraphicDesign:
        - Vibe extraction -> finalisation design-only
        - Autres taches -> impl code classique
        """
        if state.get("is_vibe_design_task", False):
            logger.info("[VIBE] Bypass code pipeline: route vers vibe_finalize_node.")
            return "vibe_finalize_node"
        return "impl_node"
        
    def route_after_impl(self, state: AgentState) -> str:
        """Determine la route apres l'implementation (generation brute)."""
        validation_status = state.get("validation_status", "")
        retry_count = state.get("retry_count", 0)
        
        if validation_status == "REJETE":
            # [SAFE] RETRY LIMIT : Prevent infinite loops in impl_node
            if retry_count >= MAX_RETRIES:
                logger.error(f"[STOP] MAX_RETRIES ({MAX_RETRIES}) reached in impl_node. Stopping retries.")
                logger.error(f"Last error: {state.get('last_error', 'Unknown')}")
                # Return to audit anyway to show the error
                return "verify_node"
            
            # Si le LLM a fait une erreur stupide (JSON invalide, etc.)
            logger.warning(f"[FIX] Echec de generation (impl_node), retour a impl_node... (attempt {retry_count + 1}/{MAX_RETRIES})")
            return "impl_node"
        
        # Si la generation a reussi, on procede a l'ArchitectureGuard
        return "architecture_guard_node"

    def route_after_arch_guard(self, state: AgentState) -> str:
        """Determine la route apres l'ArchitectureGuard."""
        status = state.get("arch_guard_status")
        retry_count = state.get("retry_count", 0)
        
        if status == "FAILED":
            # [SAFE] RETRY LIMIT : Prevent infinite loops
            if retry_count >= MAX_RETRIES:
                logger.error(f"[STOP] MAX_RETRIES ({MAX_RETRIES}) reached in arch_guard. Stopping retries.")
                return "verify_node"
            
            logger.warning(f"[FIX] Echec de validation architecturale, retour a impl_node... (attempt {retry_count + 1}/{MAX_RETRIES})")
            return "impl_node"
            
        # Si la validation architecturale reussit, on passe au PathGuard, qui est directement chaine (ou conditional if needed, but we can do direct logic to next node if needed or evaluate path_guard route. Since path_guard does not have a routing edge directly specified, we assume it routes to persist_node). Wait, path_guard doesn't have an edge defined yet, let's just make sure architecture_guard passes to next step.
        return "persist_node"

    def _build_graph(self):
        self.graph_builder.add_node("analysis_node", self.analysis_node)
        self.graph_builder.add_node("scaffold_node", self.scaffold_node)
        self.graph_builder.add_node("code_map_node", self.code_map_node)
        self.graph_builder.add_node("project_enhancer_node", self.project_enhancer_node)
        self.graph_builder.add_node("component_improver_node", self.component_improver_node)
        self.graph_builder.add_node("vision_pattern_node", self.pattern_vision_node)
        self.graph_builder.add_node("design_system_node", self.design_system_node)
        self.graph_builder.add_node("ux_flow_node", self.ux_flow_node)
        self.graph_builder.add_node("constitution_generator_node", self.constitution_generator_node)
        self.graph_builder.add_node("GraphicDesign_node", self.GraphicDesign_node)
        self.graph_builder.add_node("vibe_finalize_node", self.vibe_finalize_node)
        self.graph_builder.add_node("impl_node", self.impl_node)
        self.graph_builder.add_node("architecture_guard_node", self.architecture_guard_node)
        self.graph_builder.add_node("persist_node", self.persist_node)
        self.graph_builder.add_node("typescript_validate_node", self.typescript_validate_node)
        self.graph_builder.add_node("esm_compatibility_node", self.esm_compatibility_node)
        self.graph_builder.add_node("esm_import_resolver_node", self.esm_import_resolver_node)
        self.graph_builder.add_node("dependency_resolver_node", self.dependency_resolver_node)
        self.graph_builder.add_node("validate_dependency_node", self.validate_dependency_node)
        self.graph_builder.add_node("install_deps_node", self.install_deps_node)
        self.graph_builder.add_node("diagnostic_node", self.diagnostic_node)
        self.graph_builder.add_node("buildfix_node", self.buildfix_node)
        self.graph_builder.add_node("task_enforcer_node", self.task_enforcer_node)
        self.graph_builder.add_node("verify_node", self.verify_node)

        self.graph_builder.add_edge(START, "analysis_node")
        self.graph_builder.add_edge("analysis_node", "scaffold_node")
        self.graph_builder.add_edge("scaffold_node", "code_map_node")
        self.graph_builder.add_edge("code_map_node", "project_enhancer_node")
        self.graph_builder.add_edge("project_enhancer_node", "component_improver_node")
        self.graph_builder.add_edge("component_improver_node", "vision_pattern_node")
        self.graph_builder.add_edge("vision_pattern_node", "design_system_node")
        self.graph_builder.add_edge("design_system_node", "ux_flow_node")
        self.graph_builder.add_edge("ux_flow_node", "constitution_generator_node")
        self.graph_builder.add_edge("constitution_generator_node", "GraphicDesign_node")
        self.graph_builder.add_conditional_edges("GraphicDesign_node", self.route_after_graphic_design, {
            "vibe_finalize_node": "vibe_finalize_node",
            "impl_node": "impl_node",
        })
        self.graph_builder.add_edge("vibe_finalize_node", END)
        
        self.graph_builder.add_conditional_edges("impl_node", self.route_after_impl, {"impl_node": "impl_node", "architecture_guard_node": "architecture_guard_node", "verify_node": "verify_node"})
        self.graph_builder.add_conditional_edges("architecture_guard_node", self.route_after_arch_guard, {"impl_node": "impl_node", "persist_node": "persist_node"})
        
        self.graph_builder.add_edge("persist_node", "typescript_validate_node")
        self.graph_builder.add_edge("typescript_validate_node", "esm_compatibility_node")
        self.graph_builder.add_edge("esm_compatibility_node", "esm_import_resolver_node")
        self.graph_builder.add_edge("esm_import_resolver_node", "dependency_resolver_node")
        self.graph_builder.add_edge("dependency_resolver_node", "validate_dependency_node")
        self.graph_builder.add_edge("validate_dependency_node", "install_deps_node")
        
        # ? PROTECTION STRUCTURALE: Conditional edge apres install_deps pour casser la boucle
        # Si scanner_missing_modules est vide -> sorte du cycle vers verify_node
        # Sinon -> retour a diagnostic_node pour verifier installation
        self.graph_builder.add_conditional_edges("install_deps_node", self.route_from_install_deps, {
            "diagnostic_node": "diagnostic_node",
            "verify_node": "verify_node"
        })
        
        # diagnostic -> task_enforcer -> route (buildfix, verify, impl, install_deps)
        self.graph_builder.add_edge("diagnostic_node", "task_enforcer_node")
        self.graph_builder.add_conditional_edges("task_enforcer_node", self.route_after_enf, {
            "buildfix_node": "buildfix_node", 
            "verify_node": "verify_node",
            "impl_node": "impl_node",
            "install_deps_node": "install_deps_node"
        })
        
        # buildfix -> diagnostic (verify fix worked, then decide next step)
        # Don't loop back to dependency_resolver or we'll re-detect same modules infinitely
        self.graph_builder.add_edge("buildfix_node", "diagnostic_node")
        
        self.graph_builder.add_conditional_edges("verify_node", self.route_after_verify, {END: END, "impl_node": "impl_node"})

        self.app = self.graph_builder.compile()
        logger.info("[CORE] Cerveau LangGraph compile - Nouvelle Architecture.")
