import logging
from pathlib import Path
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class ConstitutionManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
        self.constitution_path = self.root / "Constitution" / "CONSTITUTION.md"
        self.mapping_component_path = self.root / "Constitution" / "MappingComponent.md"
        
        # Charger le template de base
        self.template_path = Path(__file__).parent / "templates" / "CONSTITUTION.template.md"
        self.mapping_template_path = Path(__file__).parent / "templates" / "MAPPING_COMPONENT.template.md"

    def _build_mapping_fallback(
        self,
        user_request: str,
        design_style: str = "premium",
    ) -> str:
        """Fallback local deterministic quand l'appel LLM de mapping échoue."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"""# 🧭 MAPPING COMPONENTS (VISION APPLICATION)
**Date:** {current_date}

> Fichier genere en mode fallback local (LLM indisponible ou erreur transitoire).
> A raffiner ensuite via `speckit specify` ou `speckit component`.

## 1. Vision Application
- Objectif produit: Derive de la demande utilisateur.
- Persona principal: Utilisateur final de l'application.
- Parcours critique:
  1. Acceder au dashboard.
  2. Naviguer vers les modules metier.
  3. Executer les operations CRUD principales.

## 2. Layout Canonique
- layout: App Shell standard.
- shell: Topbar + Sidebar + MainContent.
- sections_order: Topbar -> Sidebar -> MainContent.
- responsive_rules:
  - Desktop: sidebar fixe + contenu principal.
  - Mobile: navigation drawer + sections empilees.

## 3. Modules Metier
- module_1: Module principal derive du prompt.
- module_2: Module secondaire derive du prompt.
- design_style: {design_style}

## 4. Mapping Composant -> Zone
- header => shell.topbar
- sidebar => shell.sidebar
- dashboard_widget => main.dashboard_widgets
- table => main.tables
- form_input => main.forms

## 5. Regles d'Assemblage
- `frontend/src/layouts/AppLayout.tsx`: assemble Topbar, Sidebar, MainContent.
- `frontend/src/pages/Dashboard.tsx`: centralise les widgets de pilotage.
- Pages/modules metier: une page par module critique.
- Contraintes de navigation: routes explicites, UX coherente, responsive.

## 6. Prompt Source
{user_request}
"""

    def generate_mapping_component(
        self,
        user_request: str,
        constitution_content: str,
        design_style: str = "premium",
        semantic_map: str = "",
        existing_mapping: str = "",
    ) -> str:
        """Produit la vision de l'application (mapping composants/layout) depuis la demande utilisateur."""
        logger.info("Generation de Constitution/MappingComponent.md ...")
        current_date = datetime.now().strftime("%Y-%m-%d")

        mapping_template = ""
        if self.mapping_template_path.exists():
            mapping_template = self.mapping_template_path.read_text(encoding="utf-8")

        system_prompt = f"""Tu es le Vision Architect de Speckit.Factory.
Ta mission est de produire `Constitution/MappingComponent.md`, la VISION DE L'APPLICATION.

DATE DU JOUR : {current_date}

ORDRE DE VERITE OBLIGATOIRE :
1. `Constitution/CONSTITUTION.md` = regles, stack, contraintes non-negociables.
2. `Constitution/MappingComponent.md` = vision produit et mapping layout/components.
3. `design/constitution_design.yaml` et `design/image_meta.json` = execution design system et signaux visuels.

Tu DOIS fournir un document operationnel contenant :
- Vision produit (a partir de la demande utilisateur)
- Layout global (shell + sections + responsive)
- Modules metier prioritaires
- Mapping composant -> zone (placement explicite)
- Regles d'assemblage (ce qui va dans AppLayout, Dashboard, pages modules)

CONTRAINTES :
- Pas d'hallucination technologique en dehors de la Constitution.
- Pas de texte flou.
- Preferer des listes actionnables.
- Repondre UNIQUEMENT avec le contenu Markdown final.

Template de reference :
{mapping_template}
"""

        user_message = (
            f"DEMANDE UTILISATEUR :\n{user_request}\n\n"
            f"CONSTITUTION ACTUELLE :\n{constitution_content}\n\n"
            f"STYLE DESIGN CIBLE : {design_style}\n\n"
            f"SEMANTIC MAP (si disponible) :\n{semantic_map}\n\n"
            f"MAPPING COMPONENT EXISTANT (si disponible) :\n{existing_mapping}"
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        mapping_content = ""
        max_attempts = 2
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                raw_output = self.model.invoke(messages)
                parsed = StrOutputParser().parse(raw_output.content)
                if parsed and parsed.strip():
                    mapping_content = parsed
                    break
                last_error = ValueError("Reponse mapping vide.")
                logger.warning("Tentative %s/%s: contenu mapping vide.", attempt, max_attempts)
            except Exception as e:
                last_error = e
                logger.warning(
                    "Tentative %s/%s echouee pendant la generation de MappingComponent: %s",
                    attempt,
                    max_attempts,
                    e,
                )

        if not mapping_content:
            logger.warning(
                "Fallback active pour MappingComponent.md (cause: %s)",
                last_error if last_error else "erreur inconnue",
            )
            mapping_content = self._build_mapping_fallback(
                user_request=user_request,
                design_style=design_style,
            )

        self.mapping_component_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.mapping_component_path, "w", encoding="utf-8") as f:
            f.write(mapping_content)

        logger.info("Mapping composants genere dans %s", self.mapping_component_path)
        return mapping_content

    def generate_constitution(self, user_request: str, design_style: str = "premium") -> str:
        """Produit Constitution.md + MappingComponent.md via un appel LLM unique."""
        logger.info(f"Analyse de la demande utilisateur avec style de design {design_style}...")
        
        # Récupérer la date du jour
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Charger les préférences de stack depuis le lock
        lock_file = self.root / ".spec-lock.json"
        stack_info = "Libre (selon pertinence)"
        if lock_file.exists():
            try:
                with open(lock_file, "r") as f:
                    data = json.load(f)
                    prefs = data.get("stack_preferences", {})
                    if prefs:
                        stack_info = f"BACKEND: {prefs.get('backend')}, FRONTEND: {prefs.get('frontend')}"
            except Exception as e:
                logger.warning(f"Impossible de lire .spec-lock.json : {e}")

        base_template = ""
        if self.template_path.exists():
            base_template = self.template_path.read_text(encoding="utf-8")
        mapping_template = ""
        if self.mapping_template_path.exists():
            mapping_template = self.mapping_template_path.read_text(encoding="utf-8")

        system_prompt = f"""Tu es l'Architecte Suprême du framework Speckit.Factory.
            Ta mission est de transformer une demande utilisateur en deux documents:
            1) Constitution/CONSTITUTION.md
            2) Constitution/MappingComponent.md
            
            DATE DU JOUR : {current_date}
            
            La Constitution doit impérativement définir :
            1. L'Architecture (Folders, Layers)
            2. La Stack Technique (Langages, Frameworks, DB) - RESPECTE STRICTEMENT LES PRÉFÉRENCES SUIVANTES :
               - STACK IMPOSÉE : {stack_info}
               - Note : TOUS les projets (React, Next.js, Backend) DOIVENT impérativement être configurés en **ES Modules (ESM)**. Cela signifie `"type": "module"` dans le `package.json`.
               - Note : Pour Node.js et TypeScript, tu DOIS impérativement préciser la configuration : `TypeScript (Configuration : ES Modules, Target: ES2022)`.
            3. Les Standards de Code (Naming, Security).
            4. Le Schéma de Données (si applicable).
            5. Design Intelligence : Tu DOIS impérativement inclure la section "DESIGN CONSTITUTION".
               IMPORTANT : Tu DOIS imposer le système de design suivant : {design_style}. 
               Mentionne explicitement l'agent `GraphicDesign` et détaille les principes propres à {design_style}.
            6. L'Outillage et les Tests : Tu DOIS impérativement inclure Jest, Supertest (Backend) et Vitest (Frontend si Vite). Ne les oublie pas !

            ATTENTION AU FORMATAGE MARKDOWN :
            - Remplis les champs entre crochets du template (ex: [Ex: Jest...])
            - Ne crée pas de doublons de titres (ex: pas de double ## ou ---)
            - Sois propre et concis dans la génération.

            Utilise ce template comme base de structure :
            {base_template}
            
            Pour MappingComponent.md, inclus obligatoirement:
            - Vision produit
            - Layout global (shell + sections + responsive)
            - Modules metier prioritaires
            - Mapping composant -> zone
            - Regles d'assemblage (AppLayout, Dashboard, pages modules)

            Template CONSTITUTION:
            {base_template}

            Template MappingComponent:
            {mapping_template}

            FORMAT DE SORTIE OBLIGATOIRE:
            Reponds UNIQUEMENT en JSON valide (sans texte autour) avec ces cles exactes:
            {{
              "constitution_markdown": "...",
              "mapping_component_markdown": "..."
            }}

            Les deux valeurs doivent etre du Markdown final, complet et exploitable."""

        user_message = f"Demande utilisateur : {user_request}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        raw_output = self.model.invoke(messages)
        content = StrOutputParser().parse(raw_output.content)

        def _extract_docs(payload: str) -> tuple[str, str] | None:
            candidates = [payload.strip()]
            fenced = re.search(r"```json\s*(\{.*\})\s*```", payload, re.DOTALL | re.IGNORECASE)
            if fenced:
                candidates.insert(0, fenced.group(1).strip())

            inline_json = re.search(r"(\{.*\})", payload, re.DOTALL)
            if inline_json:
                candidates.append(inline_json.group(1).strip())

            for candidate in candidates:
                try:
                    parsed = json.loads(candidate)
                except Exception:
                    continue

                if not isinstance(parsed, dict):
                    continue

                constitution_md = parsed.get("constitution_markdown") or parsed.get("constitution")
                mapping_md = parsed.get("mapping_component_markdown") or parsed.get("mapping_component")

                if (
                    isinstance(constitution_md, str)
                    and constitution_md.strip()
                    and isinstance(mapping_md, str)
                    and mapping_md.strip()
                ):
                    return constitution_md.strip(), mapping_md.strip()

            return None

        parsed_docs = _extract_docs(content)
        if parsed_docs:
            constitution_content, mapping_content = parsed_docs
        else:
            logger.warning(
                "Impossible de parser la sortie JSON dual-doc. Fallback mapping local active."
            )
            constitution_content = content.strip()
            mapping_content = self._build_mapping_fallback(
                user_request=user_request,
                design_style=design_style,
            )

        # Sauvegarde
        self.constitution_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.constitution_path, "w", encoding="utf-8") as f:
            f.write(constitution_content)

        self.mapping_component_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.mapping_component_path, "w", encoding="utf-8") as f:
            f.write(mapping_content)

        logger.info(f"Constitution générée dans {self.constitution_path}")
        logger.info(f"Mapping composants généré dans {self.mapping_component_path}")
        return constitution_content

    def amend_constitution(self, user_request: str, semantic_map: str) -> str:
        """Amende la Constitution existante (ou la crée) pour ajouter une nouvelle fonctionnalité."""
        logger.info("Analyse de la demande technique pour amendement de la Constitution...")
        
        # Récupérer la date du jour
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        existing_content = ""
        if self.constitution_path.exists():
            existing_content = self.constitution_path.read_text(encoding="utf-8")
        existing_mapping = ""
        if self.mapping_component_path.exists():
            existing_mapping = self.mapping_component_path.read_text(encoding="utf-8")
        
        system_prompt = f"""Tu es l'Architecte de Maintenance de Speckit.Factory.
            Ta mission est d'amender une CONSTITUTION existante pour y intégrer une nouvelle COMPOSANTE (Fonctionnalité).
             
            DATE DU JOUR : {current_date}
            
            Tu reçois :
            1. La CONSTITUTION actuelle (si elle existe).
            2. Un SEMANTIC CODE MAP (scan du projet réel).
            3. La demande de nouvelle fonctionnalité.
            
            Tu DOIS :
            - Respecter les standards de code et l'architecture déjà définis dans la Constitution.
            - Ajouter les nouvelles sections nécessaires (Models, Routes, UI) pour cette fonctionnalité.
            - Ne jamais supprimer les règles de sécurité ou de stack existantes.
            - Si la Constitution n'existait pas, crée-la en te basant sur le Semantic Code Map pour déduire la stack.
            
            RÉPONDS UNIQUEMENT AVEC LE CONTENU COMPLET DU NOUVEAU FICHIER CONSTITUTION.MD."""

        user_message = f"CONSTITUTION ACTUELLE :\n{existing_content}\n\nSEMANTIC CODE MAP :\n{semantic_map}\n\nNOUVELLE DEMANDE : {user_request}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        raw_output = self.model.invoke(messages)
        content = StrOutputParser().parse(raw_output.content)

        self.constitution_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.constitution_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.generate_mapping_component(
            user_request=user_request,
            constitution_content=content,
            semantic_map=semantic_map,
            existing_mapping=existing_mapping,
        )

        logger.info(f"Constitution amendée dans {self.constitution_path}")
        return content
