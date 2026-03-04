# Output Schema Strict (Anti-Hallucination) pour garantir la qualité des réponses.
# Ce module centralise tous les modèles Pydantic utilisés pour contraindre
# les réponses des différents agents (Analyste, Implémenteur, Auditeur),
# garantissant ainsi qu'ils respectent parfaitement la structure attendue.

from pydantic import BaseModel, Field
from typing import List

# ==============================================================================
# SCHÉMAS POUR LES GESTIONNAIRES CORE
# ==============================================================================

class TaskAppOutput(BaseModel):
    """Schéma de sortie attendu pour l'initialisation des dossiers Task_App."""
    task_app1: str = Field(description="Contenu Markdown listant les tâches non réalisées (- [ ] Tâche)")
    task_app2: str = Field(description="Contenu Markdown listant les tâches réalisées (généralement vide au départ)")


# ==============================================================================
# SCHÉMAS POUR LES SOUS-AGENTS (SUBAGENTS)
# ==============================================================================

class SubagentAnalysisOutput(BaseModel):
    """Schéma de sortie attendu pour subagent_analysis.prompt."""
    impact: str = Field(description="Évaluation de l'impact : quelles parties du code sont touchées.")
    conflits: str = Field(description="Détection de conflits avec la Constitution ou 'Aucun conflit détecté.'")
    segmentation: List[str] = Field(description="Liste des sous-tâches atomiques à réaliser.")
    alerte_integrite: str = Field(description="Phrase confirmant ou infirmant le respect de l'historique validé.")


class SubagentImplOutput(BaseModel):
    """Schéma de sortie attendu pour subagent_impl.prompt."""
    resume: str = Field(description="Explication concise de ce que le code accomplit.")
    impact_fichiers: List[str] = Field(description="Liste des fichiers créés ou modifiés.")
    code: str = Field(description="Le code source complet généré, sans bloc markdown autour (le code brut).")


class SubagentVerifyOutput(BaseModel):
    """Schéma de sortie attendu pour subagent_verify.prompt."""
    score_conformite: str = Field(description="Score sur 10 (ex: '9/10').")
    points_forts: str = Field(description="Ce qui est bien réalisé.")
    alertes: str = Field(description="Écarts avec la Constitution ou failles. Ou 'Aucune alerte.'")
    verdict_final: str = Field(description="Doit être STRICTEMENT 'APPROUVÉ' ou 'REJETÉ'.")
    action_corrective: str = Field(description="Instructions de correction si REJETÉ, sinon 'N/A'.")