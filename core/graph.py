# Le "Cerveau" du Spec-Kit
# Implémentation du graphe de routage LangGraph
# Ce module orchestre l'interaction entre les sous-agents (Analyse, Implémentation, Vérification)

import logging
from pathlib import Path
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.guard import SubagentAnalysisOutput, SubagentImplOutput, SubagentVerifyOutput
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

# ─── 1. État du graphe (Mémoire partagée) ─────────────────────────────

class AgentState(TypedDict):
    # Variables de contexte partagées (générées une seule fois)
    constitution_content: str
    current_step: str
    completed_tasks_summary: str
    pending_tasks: str
    
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

    # ─── 2. Nœuds (fonctions de traitement) ───────────────────────────────

    def analysis_node(self, state: AgentState) -> dict:
        """Nœud 1 : Analyse de conformité et segmentation."""
        logger.info(f"🔍 Début de l'Analyse pour la tâche : {state['target_task']}")
        
        prompt_text = self._load_prompt("subagent_analysis.prompt")
        
        # On utilise JsonOutputParser avec le modèle Pydantic de guard.py
        parser = JsonOutputParser(pydantic_object=SubagentAnalysisOutput)
        
        # Injection des instructions Pydantic dans le prompt
        prompt_text += "\n\n{format_instructions}"
        prompt = ChatPromptTemplate.from_template(prompt_text)
        
        chain = prompt | self.model | parser
        
        try:
            result = chain.invoke({
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "target_task": state["target_task"],
                "format_instructions": parser.get_format_instructions()
            })
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
        chain = prompt | self.model | parser
        
        try:
            result = chain.invoke({
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "target_task": state["target_task"],
                "analysis_output": state["analysis_output"],
                "feedback_correction": state.get("feedback_correction", ""),
                "format_instructions": parser.get_format_instructions()
            })
            logger.info("✅ Implémentation terminée.")
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
        chain = prompt | self.model | parser
        
        try:
            result = chain.invoke({
                "constitution_content": state["constitution_content"],
                "current_step": state["current_step"],
                "completed_tasks_summary": state["completed_tasks_summary"],
                "pending_tasks": state["pending_tasks"],
                "analysis_output": state["analysis_output"],
                "code_to_verify": state["code_to_verify"],
                "terminal_diagnostics": state.get("terminal_diagnostics", "N/A"),
                "format_instructions": parser.get_format_instructions()
            })
            
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
            
    def diagnostic_node(self, state: AgentState) -> dict:
        """Nœud Intermédiaire : Exécution réelle des commandes de diagnostic."""
        logger.info("🛠️ Lancement des diagnostics réels du terminal...")
        
        commands = []
        if (self.root / "package.json").exists():
            commands.append("npm run build")
        elif (self.root / "pyproject.toml").exists():
            commands.append("pytest")
            
        if not commands:
            logger.info("ℹ️ Aucun script de diagnostic automatisé trouvé à la racine.")
            return {"terminal_diagnostics": "Aucun outil de diagnostic configuré."}
            
        diagnostics = []
        import subprocess
        
        for cmd in commands:
            logger.info(f"🏃 Exécution de : {cmd}")
            try:
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    cwd=str(self.root),
                    timeout=60
                )
                
                if result.returncode != 0:
                    error_report = f"❌ ÉCHEC de [{cmd}] :\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
                    diagnostics.append(error_report)
                else:
                    diagnostics.append(f"✅ SUCCÈS de [{cmd}]")
                    
            except subprocess.TimeoutExpired:
                diagnostics.append(f"⚠️ TIMEOUT sur [{cmd}]")
            except Exception as e:
                diagnostics.append(f"❌ ERREUR fatale lors de l'exécution de [{cmd}] : {str(e)}")
                
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
        self.graph_builder.add_edge(START, "analysis_node")
        self.graph_builder.add_edge("analysis_node", "impl_node")
        self.graph_builder.add_edge("impl_node", "diagnostic_node")
        self.graph_builder.add_edge("diagnostic_node", "verify_node")

        # Branchement conditionnel (Boucle de correction)
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