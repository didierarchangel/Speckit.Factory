# Le "Cerveau" du Spec-Kit
# Implémentation du graphe de routage LangGraph
# Ce module orchestre l'interaction entre les sous-agents (Analyse, Implémentation, Vérification)

import logging
from pathlib import Path
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.guard import SubagentAnalysisOutput, SubagentImplOutput, SubagentVerifyOutput, SubagentBuildFixOutput
from langchain_core.output_parsers import JsonOutputParser
from core.GraphicDesign import GraphicDesign

logger = logging.getLogger(__name__)

# ─── 1. État du graphe (Mémoire partagée) ─────────────────────────────

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


class SpecGraphManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
        # Les prompts sont internes au package
        self.prompts_dir = Path(__file__).parent.parent / "agents"
        
        # Initialisation du graphe
        self.graph_builder = StateGraph(AgentState)
        self._build_graph()

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
        
        # 3. Fallback ultime : chercher les marqueurs de fichiers HORS des blocs fenced
        if not code_blocks:
            # Supprimer tous les blocs fenced (JSON inclus) pour isoler le code brut
            stripped = re.sub(r'```\w*\s*.*?\s*```', '', cleaned, flags=re.DOTALL)
            # Chercher les blocs commençant par un marqueur de fichier
            raw_blocks = re.findall(r'((?:// Fichier|// \[DEBUT_FICHIER|# Fichier).*?)(?=(?:// Fichier|// \[DEBUT_FICHIER|# Fichier)|$)', stripped, re.DOTALL)
            if raw_blocks:
                code_blocks = [b.strip() for b in raw_blocks if b.strip()]
        
        if code_blocks:
            result["code"] = "\n\n".join(code_blocks)
        else:
            result["code"] = ""
                
        # --- EXTRACTION DU JSON ---
        # 1. Nettoyage des backticks Markdown (```json ... ```)
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
            return result
        except Exception as e:
            logger.warning(f"⚠️ Échec du parsing JSON standard : {str(e)}. Lancement du Fallback d'extraction agressive...")
            
            # 3. Fallback : Extraction manuelle par Regex si LangChain échoue
            try:
                # Extraction du champ "resume" ou "verdict_final"
                resume_match = re.search(r'"(?:resume|verdict_final)"\s*:\s*"((?:\\.|[^"\\])*)"', json_content, re.DOTALL)
                if resume_match:
                    val = resume_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                    result["resume"] = val
                    result["verdict_final"] = val
                else:
                    result["resume"] = "Correction effectuée (sans description)"
                    result["verdict_final"] = "REJETÉ"

                # Extraction du score
                score_match = re.search(r'"score_conformite"\s*:\s*"([^"]+)"', json_content)
                if score_match: result["score_conformite"] = score_match.group(1)

                # Extraction des alertes
                alertes_match = re.search(r'"alertes"\s*:\s*"([^"]+)"', json_content)
                if alertes_match: result["alertes"] = alertes_match.group(1)

                # Extraction de l'action corrective
                action_match = re.search(r'"action_corrective"\s*:\s*"([^"]+)"', json_content)
                if action_match: result["action_corrective"] = action_match.group(1)
                    
                # Extraction du champ "impact_fichiers" (Liste JSON)
                impact_match = re.search(r'"impact_fichiers"\s*:\s*\[(.*?)\]', json_content, re.DOTALL)
                if impact_match:
                    impact_list = impact_match.group(1)
                    # Trouve toutes les chaînes entre guillemets
                    files = re.findall(r'"([^"]+)"', impact_list)
                    result["impact_fichiers"] = files
                else:
                    if "impact_fichiers" not in result:
                        result["impact_fichiers"] = []
                    
                # Si l'ancien format 'code dans JSON' était utilisé mais cassé
                if not result.get("code"):
                    code_match = re.search(r'"code"\s*:\s*"(.*)"\s*}?\s*$', json_content, re.DOTALL)
                    if code_match:
                        raw_code = code_match.group(1)
                        raw_code = raw_code.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
                        raw_code = re.sub(r'"\s*}\s*$', '', raw_code)
                        result["code"] = raw_code
                        
                # Si on a un code ou un impact_fichiers, c'est suffisant pour impl_node
                if result.get("code") or result.get("impact_fichiers"):
                    logger.info("✅ Fallback d'extraction réussi.")
                    return result
                
                # Si on est dans verify_node et qu'on a le verdict, c'est bon
                if result.get("verdict_final"):
                    logger.info("✅ Fallback d'extraction réussi (Verify).")
                    return result
                    
                raise ValueError("Le fallback n'a pas pu extraire de données significatives.")
                    
            except Exception as fallback_error:
                logger.error(f"❌ Échec total du parsing JSON et du fallback : {str(fallback_error)}")
                raise e # On relève l'erreur originale de LangChain

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
        logger.info(f"💻 Début de l'Implémentation pour la tâche : {state['target_task']}")
        
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
                "user_instruction": state.get("user_instruction", ""),
                "format_instructions": parser.get_format_instructions()
            })
            result = self._safe_parse_json(raw_output, SubagentImplOutput)
            logger.info("✅ Implémentation terminée.")
            
            # Persistance immédiate des fichiers sur le disque
            if result.get("code"):
                self._persist_code_to_disk(result["code"])
                
            return {
                "code_to_verify": result["code"],
                "impact_fichiers": result.get("impact_fichiers", []),
                "last_error": ""
            }
        except Exception as e:
            error_msg = f"Erreur d'implémentation : {str(e)}"
            logger.error(f"❌ {error_msg}")
            # On passe l'erreur comme "code" pour que l'auditeur la voit si besoin, 
            # mais on incrémentera le compteur d'erreurs plus tard
            return {
                "code_to_verify": f"ERREUR TECHNIQUE LORS DE LA GÉNÉRATION : {str(e)}",
                "last_error": error_msg
            }

    def verify_node(self, state: AgentState) -> dict:
        """Nœud 3 : Audit de sécurité et conformité finale."""
        logger.info(f"🛡️ Début de l'Audit pour le code généré.")
        
        prompt_text = self._load_prompt("subagent_verify.prompt")
        parser = JsonOutputParser(pydantic_object=SubagentVerifyOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            # Injection du checklist des sous-tâches pour vérification granulaire
            subtask_checklist = state.get("subtask_checklist", "Non disponible")
            
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
                "subtask_checklist": subtask_checklist,
                "format_instructions": parser.get_format_instructions()
            })
            result = self._safe_parse_json(raw_output, SubagentVerifyOutput)
            
            verdict = result["verdict_final"].upper()
            status = "APPROUVÉ" if "APPROUVÉ" in verdict else "REJETÉ"
            
            # Si le code envoyé était une erreur technique, on force le rejet
            if "ERREUR TECHNIQUE" in state["code_to_verify"]:
                status = "REJETÉ"
                result['alertes'] = f"Le code n'a pas pu être généré : {state['code_to_verify']}"
                result['action_corrective'] = "Réessaye de générer le code en respectant strictement le format JSON."

            if status == "APPROUVÉ":
                logger.info(f"✅ Code APPROUVÉ par l'Auditeur (Score: {result['score_conformite']}).")
                return {
                    "validation_status": "APPROUVÉ", 
                    "score": result['score_conformite'],
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', 'Aucune alerte.'),
                    "feedback_correction": "",
                    "error_count": 0
                }
            else:
                new_error_count = state.get("error_count", 0) + 1
                logger.warning(f"❌ Code REJETÉ par l'Auditeur ({new_error_count}/3). Raison : {result['alertes']}")
                return {
                    "validation_status": "REJETÉ", 
                    "score": result['score_conformite'],
                    "points_forts": result.get('points_forts', ''),
                    "alertes": result.get('alertes', ''),
                    "feedback_correction": result["action_corrective"],
                    "error_count": new_error_count
                }
                
        except Exception as e:
            error_msg = f"Erreur de parser (Audit) : {str(e)}"
            logger.error(f"❌ {error_msg}")
            new_error_count = state.get("error_count", 0) + 1
            return {
                "validation_status": "REJETÉ", 
                "feedback_correction": f"L'audit a échoué techniquement : {error_msg}. Réessaye avec un format JSON valide.",
                "error_count": new_error_count,
                "last_error": error_msg
            }

    def code_map_node(self, state: AgentState) -> dict:
        """Nœud de génération de la Semantic Code Map."""
        logger.info("🗺️ Génération de la Semantic Code Map...")
        
        import os
        import re
        import json
        
        code_map = {
            "file_tree": [],
            "semantics": {}
        }
        
        # Extensions à scanner pour la sémantique
        source_extensions = ('.ts', '.js', '.tsx', '.jsx')
        # Dossiers à ignorer
        ignore_dirs = {'node_modules', 'dist', '.git', '__pycache__', '.speckit-rules'}
        
        for root, dirs, files in os.walk(str(self.root)):
            # Filtrage des dossiers
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), str(self.root)).replace('\\', '/')
                code_map["file_tree"].append(rel_path)
                
                if file.endswith(source_extensions):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            # Extraction simplifiée des imports
                            # Match : import ... from 'lib' ou import * as ... from 'lib' ou import 'lib'
                            imports = re.findall(r"import\s+(?:(?:\*|[\w\s,{}]+)\s+from\s+)?['\"]([^'\"]+)['\"]", content)
                            
                            # Extraction simplifiée des exports
                            # Match : export const ..., export function ..., export class ..., export default ...
                            exports = re.findall(r"export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type|async\s+function)\s+([\w$]+)", content)
                            
                            # Extraction des fonctions/méthodes (approximation)
                            # Match : function name(...) { or async function name(...) { or const name = (...) => {
                            functions = re.findall(r"(?:function|const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", content)
                            functions += re.findall(r"(?:async\s+)?function\s+([\w$]+)\s*\(", content)
                            functions += re.findall(r"(?:async\s+)?([\w$]+)\s*\([^)]*\)\s*\{", content) # Pour les méthodes de classe
                            
                            # Filtrage des doublons et mots clés JS dans les extractions
                            functions = list(set([fn for fn in functions if fn not in ('if', 'for', 'while', 'switch', 'catch', 'constructor')]))
                            
                            code_map["semantics"][rel_path] = {
                                "imports": list(set(imports)),
                                "exports": list(set(exports)),
                                "functions": functions[:15] # Limite pour rester compact
                            }
                    except Exception as e:
                        logger.warning(f"⚠️ Impossible de parser {rel_path} pour la Code Map : {str(e)}")
        
        # Formatage compact en JSON string
        code_map_str = json.dumps(code_map["semantics"], indent=2)
        file_tree_str = "\n".join(code_map["file_tree"])
        
        logger.info(f"✅ Code Map générée ({len(code_map['file_tree'])} fichiers référencés).")
        
        return {
            "code_map": code_map_str,
            "file_tree": file_tree_str
        }

    def buildfix_node(self, state: AgentState) -> dict:
        """Nœud de réparation automatique du build (TypeScript/Node)."""
        # Si le build est déjà un succès, on passe directement.
        diagnostics = state.get("terminal_diagnostics", "")
        if "✅ SUCCÈS" in diagnostics and "❌ ÉCHEC" not in diagnostics:
            # logger.info("✅ Build déjà réussi, buildfix_node ignoré.")
            return {"feedback_correction": ""}

        logger.info("🛠️ Tentative de réparation automatique du build...")
        prompt_text = self._load_prompt("subagent_buildfix.prompt")
        
        parser = JsonOutputParser(pydantic_object=SubagentBuildFixOutput)
        prompt_text += "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.model | StrOutputParser()
        
        try:
            raw_output = chain.invoke({
                "code_map": state.get("code_map", "Non générée"),
                "file_tree": state.get("file_tree", "Non générée"),
                "code_to_verify": state["code_to_verify"],
                "terminal_diagnostics": state.get("terminal_diagnostics", ""),
                "constitution_content": state["constitution_content"],
                "format_instructions": parser.get_format_instructions()
            })
            result = self._safe_parse_json(raw_output, SubagentBuildFixOutput)
            logger.info("✅ Réparation du build terminée.")
            
            # Persistance immédiate des corrections sur le disque
            if result.get("code"):
                self._persist_code_to_disk(result["code"])
                
            # FUSION du code : on fusionne les corrections avec le code de base
            merged_code = self._merge_code(state.get("code_to_verify", ""), result.get("code", ""))
                
            new_error_count = state.get("error_count", 0) + 1
            return {
                "code_to_verify": merged_code,
                "impact_fichiers": list(set(state.get("impact_fichiers", []) + result.get("impact_fichiers", []))),
                "error_count": new_error_count,
                "feedback_correction": f"BUILD FIX APPLIED (Attempt {new_error_count}): {result.get('resume', 'Aucun résumé')}"
            }
        except Exception as e:
            logger.warning(f"⚠️ Échec du BuildFixer : {str(e)}")
            return {"feedback_correction": f"BUILD FIX FAILED: {str(e)}"}

    def _persist_code_to_disk(self, code: str) -> list:
        """Extrait les blocs de fichiers du code généré et les écrit physiquement sur le disque."""
        from utils.file_manager import FileManager
        fm = FileManager(base_path=str(self.root))
        
        if not code:
            return []
            
        written_files = fm.extract_and_write(code)
        if written_files:
            logger.info(f"💾 {len(written_files)} fichiers persistés sur le disque.")
            
        return written_files

    def _merge_code(self, base_code: str, delta_code: str) -> str:
        """Fusionne deux blocs de code multi-fichiers. Le delta écrase la base si conflit."""
        import re
        if not delta_code:
            return base_code
        if not base_code:
            return delta_code
            
        pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
        
        def parse_to_dict(code):
            blocks = re.split(pattern, code)
            file_dict = {}
            if len(blocks) > 1:
                for i in range(1, len(blocks), 2):
                    fname = blocks[i].strip()
                    # On cherche l'en-tête pour la reconstruction
                    header_match = re.search(fr'(?m)^.*{re.escape(fname)}.*$', code)
                    header = header_match.group(0) if header_match else f"// [DEBUT_FICHIER: {fname}]"
                    file_dict[fname] = {
                        "header": header,
                        "content": blocks[i+1]
                    }
            return file_dict

        base_dict = parse_to_dict(base_code)
        delta_dict = parse_to_dict(delta_code)
        
        # Fusion : delta gagne
        base_dict.update(delta_dict)
        
        # Reconstruction
        merged = []
        for fname, data in base_dict.items():
            merged.append(data["header"])
            merged.append(data["content"])
            # On ajoute un marqueur de fin générique pour la propreté
            merged.append(f"// [FIN_FICHIER: {fname}]")
            
        return "\n".join(merged)

    def route_after_diagnostic(self, state: AgentState) -> str:
        """Route après le diagnostic : buildfix_node si erreur technique, sinon verify_node."""
        diagnostics = state.get("terminal_diagnostics", "")
        
        # On ne tente le buildfix que s'il y a un échec réel de build ou de tests
        if "❌ ÉCHEC" in diagnostics or "❌ ERREUR" in diagnostics:
             # Protection contre boucle infinie (on réutilise le compteur global)
             if state.get("error_count", 0) < 3:
                 logger.info("🔧 Échec du build détecté. Routage vers buildfix_node...")
                 return "buildfix_node"
        
        return "verify_node"
            
    def diagnostic_node(self, state: AgentState) -> dict:
        """Nœud Intermédiaire : Exécution réelle des commandes de diagnostic."""
        logger.info("🛠️ Lancement des diagnostics réels du terminal...")
        
        # 0. S'assurer que le code de l'état est bien sur le disque
        code = state.get("code_to_verify", "")
        written_files = self._persist_code_to_disk(code)
        
        diagnostics = []
        import subprocess
        
        search_dirs = [self.root, self.root / "backend", self.root / "frontend"]
        found_something = False
        
        for target_dir in search_dirs:
            if (target_dir / "package.json").exists():
                found_something = True
                dir_name = target_dir.name if target_dir.name else "racine"
                
                # Toujours réinstaller les dépendances si on a écrit un package.json dans ce dossier
                pkg_written = any(fp.replace('\\', '/').startswith(dir_name + '/package.json') or fp == 'package.json' for fp in written_files)
                if not (target_dir / "node_modules").exists() or pkg_written:
                    logger.info(f"⏳ Installation des dépendances (npm install) dans {dir_name}...")
                    try:
                        # On capture la sortie pour pouvoir la fournir à l'agent de correction si ça échoue
                        res_install = subprocess.run("npm install", shell=True, capture_output=True, text=True, cwd=str(target_dir), timeout=180)
                        if res_install.returncode != 0:
                            logger.error(f"❌ npm install a échoué dans {dir_name}. stderr: {res_install.stderr[:200]}...")
                            diagnostics.append(f"❌ ÉCHEC DE L'INSTALLATION (npm install) dans {dir_name} :\nSTDOUT: {res_install.stdout}\nSTDERR: {res_install.stderr}")
                        else:
                            logger.info(f"✅ npm install réussi dans {dir_name}.")
                    except Exception as e:
                        diagnostics.append(f"❌ ERREUR CRITIQUE lors de npm install dans {dir_name}: {str(e)}")
                
                # 2. Détection de dépendances manquantes (npm ls)
                logger.info(f"🔍 Vérification des dépendances dans {dir_name}...")
                try:
                    res_ls = subprocess.run("npm ls --depth=0", shell=True, capture_output=True, text=True, cwd=str(target_dir), timeout=60)
                    if res_ls.returncode != 0:
                        diagnostics.append(f"⚠️ DÉPENDANCES MANQUANTES/INVALIDES dans {dir_name} :\n{res_ls.stdout}\n{res_ls.stderr}")
                    else:
                        diagnostics.append(f"✅ Dépendances OK dans {dir_name}")
                except Exception as e:
                    diagnostics.append(f"❌ Erreur lors de npm ls dans {dir_name}: {str(e)}")

                # 3. Vérification de compilation TypeScript (tsc --noEmit)
                logger.info(f"🔍 Compilation TypeScript (--noEmit) dans {dir_name}...")
                # On utilise npx --yes pour éviter de bloquer sur une demande de confirmation d'installation
                try:
                    res_tsc = subprocess.run("npx --yes tsc --noEmit", shell=True, capture_output=True, text=True, cwd=str(target_dir), timeout=90)
                    if res_tsc.returncode != 0:
                        diagnostics.append(f"❌ ÉCHEC de [tsc --noEmit] dans {dir_name} :\nSTDOUT: {res_tsc.stdout}\nSTDERR: {res_tsc.stderr}")
                    else:
                        diagnostics.append(f"✅ SUCCÈS de [tsc --noEmit] dans {dir_name}")
                except Exception as e:
                    diagnostics.append(f"❌ Erreur lors de tsc --noEmit dans {dir_name}: {str(e)}")

                # 4. Exécution du build (npm run build)
                cmd = "npm run build"
                logger.info(f"🏃 Exécution de : {cmd} dans {dir_name}")
                try:
                    result = subprocess.run(
                        cmd, 
                        shell=True, 
                        capture_output=True, 
                        text=True, 
                        cwd=str(target_dir),
                        timeout=90
                    )
                    
                    if result.returncode != 0:
                        # Si le script 'build' n'existe pas, npm renvoie une erreur spécifique, on peut l'ignorer ou le signaler
                        if "Missing script: \"build\"" in result.stderr or "Missing script: build" in result.stderr:
                            diagnostics.append(f"ℹ️ Aucun script 'build' dans {dir_name}.")
                        else:
                            error_report = f"❌ ÉCHEC de [{cmd}] dans {dir_name} :\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
                            diagnostics.append(error_report)
                    else:
                        diagnostics.append(f"✅ SUCCÈS de [{cmd}] dans {dir_name}")
                        
                except subprocess.TimeoutExpired:
                    diagnostics.append(f"⚠️ TIMEOUT sur [{cmd}] dans {dir_name}")
                except Exception as e:
                    diagnostics.append(f"❌ ERREUR fatale lors de l'exécution de [{cmd}] dans {dir_name} : {str(e)}")

            if (target_dir / "pyproject.toml").exists() or (target_dir / "requirements.txt").exists():
                found_something = True
                dir_name = target_dir.name if target_dir.name else "racine"
                
                import os
                has_tests = False
                if (target_dir / "tests").exists() and any((target_dir / "tests").iterdir()):
                    has_tests = True
                else:
                    try:
                        for f in os.listdir(target_dir):
                            if f.startswith("test_") and f.endswith(".py"):
                                has_tests = True
                                break
                    except:
                        pass
                
                if not has_tests:
                    diagnostics.append(f"ℹ️ Aucun test détecté dans {dir_name}, pytest ignoré.")
                else:
                    cmd = "pytest"
                    logger.info(f"🏃 Exécution de : {cmd} dans {dir_name}")
                    try:
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(target_dir), timeout=90)
                        if result.returncode != 0:
                            diagnostics.append(f"❌ ÉCHEC de [{cmd}] dans {dir_name}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
                        else:
                            diagnostics.append(f"✅ SUCCÈS de [{cmd}] dans {dir_name}")
                    except Exception as e:
                        diagnostics.append(f"❌ ERREUR exécutant [{cmd}] dans {dir_name}: {str(e)}")
            
        if not found_something:
            logger.info("ℹ️ Aucun script de diagnostic automatisé trouvé (ni package.json, ni Python config).")
            return {"terminal_diagnostics": "Aucun outil de diagnostic configuré."}
            
        full_report = "\n---\n".join(diagnostics)
        logger.info("✅ Diagnostics terminés.")
        return {"terminal_diagnostics": full_report}


    # ─── 3. Fonctions de routage (conditions) ─────────────────────────────

    def route_after_verify(self, state: AgentState) -> str:
        """Après l'audit : terminer (END) ou ré-implémenter (impl_node)."""
        if state.get("validation_status") == "APPROUVÉ":
            return END
        
        # Limite de boucles pour éviter de vider le quota en cas d'erreur persistante
        if state.get("error_count", 0) >= 3:
            logger.error("🛑 Limite de tentatives (3) atteinte. Abandon pour éviter une boucle infinie.")
            return END
            
        logger.info(f"🔄 Routage vers l'Implémentateur pour correction (Tentative {state.get('error_count', 0)}/3)...")
        return "impl_node"

    # ─── 4. Construction du graphe ─────────────────────────────────────────

    def _build_graph(self):
        # Ajout des nœuds
        self.graph_builder.add_node("analysis_node", self.analysis_node)
        self.graph_builder.add_node("impl_node", self.impl_node)
        self.graph_builder.add_node("verify_node", self.verify_node)

        # Transitions (flux)
        self.graph_builder.add_node("diagnostic_node", self.diagnostic_node)
        self.graph_builder.add_node("buildfix_node", self.buildfix_node)
        self.graph_builder.add_node("code_map_node", self.code_map_node)
        self.graph_builder.add_node("GraphicDesign_node", self.GraphicDesign_node)
        
        self.graph_builder.add_edge(START, "analysis_node")
        self.graph_builder.add_edge("analysis_node", "code_map_node")
        self.graph_builder.add_edge("code_map_node", "GraphicDesign_node")
        self.graph_builder.add_edge("GraphicDesign_node", "impl_node")
        self.graph_builder.add_edge("impl_node", "diagnostic_node")
        
        # Branchement conditionnel (Correction automatique du build)
        self.graph_builder.add_conditional_edges(
            "diagnostic_node",
            self.route_after_diagnostic,
            {
                "buildfix_node": "buildfix_node",
                "verify_node": "verify_node"
            }
        )
        self.graph_builder.add_edge("buildfix_node", "diagnostic_node") # Boucle pour vérifier la correction

        # Branchement conditionnel (Boucle de correction finale / Audit)
        self.graph_builder.add_conditional_edges(
            "verify_node",
            self.route_after_verify,
            {
                END: END,
                "impl_node": "impl_node",
            }
        )

        # Compilation
        self.app = self.graph_builder.compile()
        logger.info("🧠 Cerveau LangGraph compilé et prêt.")