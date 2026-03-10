# Le "Cerveau" du Spec-Kit (LE WORKFLOW DE CHAINAGE, LE PIPELINE, LE ROADMAP)
# Implémentation du graphe de routage LangGraph
# Ce module orchestre l'interaction entre les sous-agents (Analyse, Implémentation, Vérification)

import logging
from pathlib import Path
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.guard import SubagentAnalysisOutput, SubagentImplOutput, SubagentVerifyOutput, SubagentBuildFixOutput, SubagentTaskEnforcerOutput
from langchain_core.output_parsers import JsonOutputParser
from core.GraphicDesign import GraphicDesign

logger = logging.getLogger(__name__)

# ─── 0. Configuration des Limites ──────────────────────────────────────────────────
MAX_RETRIES = 3

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
    
    # Gestion des erreurs et boucle
    error_count: int 
    last_error: str
    
    # Instructions utilisateur additionnelles (Ex: speckit run --instruction "Fais ceci")
    user_instruction: str
    
    # Carte sémantique du code (Semantic Code Map)
    code_map: str
    file_tree: str
    
    # Checklist des sous-tâches
    subtask_checklist: str
    
    # Statistiques de complétion (via TaskEnforcer)
    total_subtasks: int
    missing_subtasks: int


class SpecGraphManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
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
        code_blocks = re.findall(r"```code\s*(.*?)\s*```", cleaned, re.DOTALL)
        
        # 2. Fallback : TOUS les blocs fenced sauf ```json (car c'est le JSON d'analyse)
        if not code_blocks:
            # On capture tous les blocs ``` qui ne sont PAS du JSON d'analyse
            all_blocks = re.findall(r"```(?!json\b)(\w*)\s*(.*?)\s*```", cleaned, re.DOTALL)
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
        json_match = re.search(r"<JSON_OUTPUT>\s*(.*?)\s*</JSON_OUTPUT>", cleaned, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
        else:
            # 2. Nettoyage des backticks Markdown (```json ... ```)
            json_content = cleaned
            if "```json" in json_content:
                match = re.search(r"```json\s*(.*?)\s*```", json_content, re.DOTALL)
                if match:
                    json_content = match.group(1).strip()
                else:
                    json_content = re.sub(r"^```json\s*", "", json_content)
            elif "```" in json_content:
                 # S'il y a un bloc ``` générique au début, on assume que c'est le json
                 match = re.search(r"^```\s*(\{.*?\})\s*```", json_content, re.DOTALL)
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
        
        try:
            design_result = design_engine.generate(prompt)
            logger.info(f"✅ Design terminé (Pattern: {design_result.get('pattern', 'Inconnu')}).")
            return {"design_spec": design_result}
        except Exception as e:
            logger.error(f"❌ Échec du moteur GraphicDesign : {str(e)}")
            # Fallback minimaliste
            return {"design_spec": {"error": str(e), "tailwind": {}}}

    def analysis_node(self, state: AgentState) -> dict:
        """Nœud 1 : Analyse de conformité et segmentation."""
        logger.info(f"🔍 Début de l'Analyse pour la tâche : {state['target_task']}")
        
        prompt_text = self._load_prompt("subagent_analysis.prompt")
        
        # On utilise JsonOutputParser avec le modèle Pydantic de guard.py
        parser = JsonOutputParser(pydantic_object=SubagentAnalysisOutput)
        
        # Injection des instructions Pydantic dans le prompt
        prompt_text += "\n\n{format_instructions}"
        prompt = ChatPromptTemplate.from_template(prompt_text)
        
        chain = prompt | self.model | StrOutputParser()
        
        try:
            raw_output = chain.invoke({
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "target_task": state["target_task"],
                "user_instruction": state.get("user_instruction", ""),
                "format_instructions": parser.get_format_instructions()
            })
            result = self._safe_parse_json(raw_output, SubagentAnalysisOutput)
            # On convertit le dict JSON en string formatée pour l'injecter au noeud suivant
            analysis_str = (
                f"Impact: {result['impact']}\n"
                f"Conflits: {result['conflits']}\n"
                f"Segmentation: {', '.join(result['segmentation'])}\n"
                f"Intégrité: {result['alerte_integrite']}"
            )
            logger.info("✅ Analyse terminée.")
            return {"analysis_output": analysis_str, "feedback_correction": "", "error_count": 0}
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

    def impl_node(self, state: AgentState) -> dict:
        """Nœud 2 : Génération de code pur (Exécutant)."""
        logger.info(f"💻 Début de la Génération de code pour la tâche : {state['target_task']}")
        
        # Garantie structurelle avant génération
        self._ensure_directory_structure()
        
        prompt_text = self._load_prompt("subagent_impl.prompt")
        
        # Si on revient d'une erreur (feedback_correction n'est pas vide), on l'ajoute
        if state.get("feedback_correction"):
            logger.warning("🔄 Application des corrections demandées par l'Auditeur.")
            prompt_text += "\n\n# ⚠️ INSTRUCTIONS DE CORRECTION (RETOUR AUDITEUR) :\n{feedback_correction}"
            
        parser = JsonOutputParser(pydantic_object=SubagentImplOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            raw_output = chain.invoke({
                "constitution_hash": state.get("constitution_hash", "INCONNU"),
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "target_task": state["target_task"],
                "analysis_output": state["analysis_output"],
                "feedback_correction": state.get("feedback_correction", ""),
                "terminal_diagnostics": state.get("terminal_diagnostics", ""),
                "code_map": state.get("code_map", "Non générée"),
                "file_tree": state.get("file_tree", "Non générée"),
                "design_spec": state.get("design_spec", "Non générée"),
                "subtask_checklist": state.get("subtask_checklist", "Non disponible"),
                "user_instruction": state.get("user_instruction", ""),
                "format_instructions": parser.get_format_instructions()
            })

            result = self._safe_parse_json(raw_output, SubagentImplOutput)
            logger.info("✅ Génération de code terminée.")
            
            return {
                "code_to_verify": result.get("code", ""),
                "impact_fichiers": result.get("impact_fichiers", []),
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

    def persist_node(self, state: AgentState) -> dict:
        """Nœud : Persistance du code sur le disque."""
        logger.info("💾 Persistance des fichiers sur le disque...")
        code = state.get("code_to_verify", "")
        if not code:
            return {"validation_status": "EMPTY_CODE"}
            
        sanitized_code, written_paths = self._persist_code_to_disk(code)
        logger.info(f"✅ {len(written_paths)} fichiers écrits.")
        
        return {
            "code_to_verify": sanitized_code,
            "impact_fichiers": list(set(state.get("impact_fichiers", []) + written_paths)),
            "validation_status": "PERSISTED"
        }

    def install_deps_node(self, state: AgentState) -> dict:
        """Nœud : Installation des dépendances npm."""
        import subprocess
        logger.info("📦 Installation des dépendances (npm install)...")
        
        found_pkg = False
        search_dirs = [self.root, self.root / "backend", self.root / "frontend"]
        
        for target_dir in search_dirs:
            if (target_dir / "package.json").exists():
                found_pkg = True
                logger.info(f"⏳ npm install dans {target_dir.name or 'racine'}...")
                try:
                    subprocess.run(["npm", "install"], cwd=str(target_dir), shell=True, capture_output=True, timeout=180)
                except Exception as e:
                    logger.warning(f"⚠️ npm install a échoué dans {target_dir}: {e}")
        
        return {"validation_status": "DEPS_INSTALLED" if found_pkg else "NO_PACKAGE_JSON"}


    def verify_node(self, state: AgentState) -> dict:
        """Nœud 3 : Audit de sécurité et conformité finale."""
        if state.get("error_count", 0) >= 3:
            logger.error("🛑 Limite atteinte")
            return {"validation_status": "REJETÉ", "alertes": "Limite de tentatives atteinte."}

        logger.info(f"🛡️ Début de l'Audit pour le code généré.")
        
        prompt_text = self._load_prompt("subagent_verify.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentVerifyOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            raw_output = chain.invoke({
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
            })
            result = self._safe_parse_json(raw_output, SubagentVerifyOutput)
            
            verdict = result["verdict_final"].upper()
            status = "APPROUVÉ" if "APPROUVÉ" in verdict else "REJETÉ"
            
            # --- GROUND TRUTH : Vérification réelle sur DISQUE ---
            from core.etapes import EtapeManager
            etape_manager = EtapeManager(self.model, project_root=str(self.root))
            
            _, checked_count, total_count = etape_manager.mark_step_as_completed(
                state["current_step"], 
                synthesis=result.get("resume", ""),
                project_root=str(self.root)
            )
            
            task_score = int((checked_count / total_count * 100)) if total_count > 0 else 100
            audit_score = int(result.get("score_conformite", 0))
            final_score = min(audit_score, task_score)
            
            if status == "APPROUVÉ":
                logger.info(f"✅ Code APPROUVÉ. Score: {final_score}")
                return {
                    "validation_status": "APPROUVÉ", 
                    "score": str(final_score),
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', 'Aucune.'),
                    "feedback_correction": ""
                }
            else:
                new_error_count = state.get("error_count", 0) + 1
                return {
                    "validation_status": "REJETÉ", 
                    "score": str(final_score),
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', ''),
                    "feedback_correction": result["action_corrective"],
                    "error_count": new_error_count
                }
        except Exception as e:
            logger.error(f"❌ Erreur audit : {e}")
            return {"validation_status": "REJETÉ", "feedback_correction": str(e), "error_count": state.get("error_count", 0)+1}

    def task_enforcer_node(self, state: AgentState) -> dict:
        """Nœud de vérification structurelle."""
        logger.info("🛡️ Vérification structurelle (TaskEnforcer)...")
        prompt_text = self._load_prompt("subagent_Speckit-TaskEnforcer.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentTaskEnforcerOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            raw_output = chain.invoke({
                "subtask_checklist": state.get("subtask_checklist", ""),
                "file_tree": state.get("file_tree", ""),
                "format_instructions": parser.get_format_instructions()
            })
            result = self._safe_parse_json(raw_output, SubagentTaskEnforcerOutput)
            
            if result["verdict"] == "CONFORME":
                return {"validation_status": "STRUCTURE_OK"}
            else:
                return {
                    "validation_status": "STRUCTURE_KO",
                    "feedback_correction": f"MANQUANT: {', '.join(result['missing_files'])}",
                    "error_count": state.get("error_count", 0) + 1
                }
        except Exception as e:
            return {"validation_status": "STRUCTURE_KO", "feedback_correction": str(e)}

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
        prompt_text = self._load_prompt("subagent_buildfix.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentBuildFixOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            raw_output = chain.invoke({
                "code_map": state.get("code_map", ""),
                "file_tree": state.get("file_tree", ""),
                "code_to_verify": state["code_to_verify"],
                "terminal_diagnostics": state.get("terminal_diagnostics", ""),
                "constitution_content": state["constitution_content"],
                "feedback_correction": state.get("feedback_correction", ""),
                "format_instructions": parser.get_format_instructions()
            })
            result = self._safe_parse_json(raw_output, SubagentBuildFixOutput)
            sanitized_fix, written = self._persist_code_to_disk(result.get("code", ""))
            merged = self._merge_code(state.get("code_to_verify", ""), sanitized_fix)
            
            return {
                "code_to_verify": merged,
                "error_count": state.get("error_count", 0) + 1,
                "feedback_correction": f"BUILD FIX: {result.get('resume', '')}"
            }
        except: return {"feedback_correction": "BUILD FIX FAILED"}

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

    def route_after_diagnostic(self, state: AgentState) -> str:
        diag = state.get("terminal_diagnostics", "")
        if ("❌ ÉCHEC" in diag or "❌ ERREUR" in diag) and state.get("error_count", 0) < 3:
            return "buildfix_node"
        return "task_enforcer_node"
            
    def diagnostic_node(self, state: AgentState) -> dict:
        logger.info("🛠️ Diagnostics terminés.")
        import subprocess
        reports = []
        for d in [self.root, self.root / "backend", self.root / "frontend"]:
            if (d / "package.json").exists():
                res = subprocess.run("npx --yes tsc --noEmit", shell=True, capture_output=True, text=True, cwd=str(d))
                reports.append(f"TS {d.name}: {'✅' if res.returncode==0 else '❌'}\n{res.stdout}")
        return {"terminal_diagnostics": "\n".join(reports)}

    def route_after_impl(self, state: AgentState) -> str:
        if state["validation_status"] == "REJETÉ":
            if state.get("error_count", 0) >= MAX_RETRIES:
                logger.error(f"🛑 Limite de tentatives atteinte ({MAX_RETRIES}) après échec Génération.")
                return "verify_node"
            return "impl_node"
        return "persist_node"

    def route_after_enf(self, state: AgentState) -> str:
        if state["validation_status"] == "STRUCTURE_KO":
            if state.get("error_count", 0) >= MAX_RETRIES:
                logger.error(f"🛑 Limite de tentatives atteinte ({MAX_RETRIES}) après échec TaskEnforcer.")
                return "verify_node"
            return "impl_node"
        return "verify_node"

    def route_after_verify(self, state: AgentState) -> str:
        if state.get("validation_status") == "APPROUVÉ" or state.get("error_count", 0) >= MAX_RETRIES:
            return END
        return "impl_node"

    def _build_graph(self):
        self.graph_builder.add_node("analysis_node", self.analysis_node)
        self.graph_builder.add_node("code_map_node", self.code_map_node)
        self.graph_builder.add_node("GraphicDesign_node", self.GraphicDesign_node)
        self.graph_builder.add_node("impl_node", self.impl_node)
        self.graph_builder.add_node("persist_node", self.persist_node)
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
        
        self.graph_builder.add_edge("persist_node", "install_deps_node")
        self.graph_builder.add_edge("install_deps_node", "diagnostic_node")
        
        self.graph_builder.add_conditional_edges("diagnostic_node", self.route_after_diagnostic, {"buildfix_node": "buildfix_node", "task_enforcer_node": "task_enforcer_node"})
        self.graph_builder.add_edge("buildfix_node", "diagnostic_node")
        
        self.graph_builder.add_conditional_edges("task_enforcer_node", self.route_after_enf, {"impl_node": "impl_node", "verify_node": "verify_node"})
        
        self.graph_builder.add_conditional_edges("verify_node", self.route_after_verify, {END: END, "impl_node": "impl_node"})

        self.app = self.graph_builder.compile()
        logger.info("🧠 Cerveau LangGraph compilé - Nouvelle Architecture.")
