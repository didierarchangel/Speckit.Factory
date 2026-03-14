import logging
from pathlib import Path
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
import json

logger = logging.getLogger(__name__)

class ConstitutionManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
        self.constitution_path = self.root / "Constitution" / "CONSTITUTION.md"
        
        # Charger le template de base
        self.template_path = Path(__file__).parent / "templates" / "CONSTITUTION.template.md"

    def generate_constitution(self, user_request: str, design_style: str = "Standard") -> str:
        """Produit la Constitution (Architecture, Standards, Stack) à partir d'une demande utilisateur."""
        logger.info(f"Analyse de la demande utilisateur avec style de design {design_style}...")
        
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

        system_prompt = f"""Tu es l'Architecte Suprême du framework Speckit.Factory.
            Ta mission est de transformer une demande utilisateur en une CONSTITUTION rigoureuse.
            
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
            
            SOIS EXHAUSTIF. Ne fais pas de suppositions floues."""

        user_message = f"Demande utilisateur : {user_request}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        raw_output = self.model.invoke(messages)
        content = StrOutputParser().parse(raw_output.content)

        # Sauvegarde
        self.constitution_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.constitution_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Constitution générée dans {self.constitution_path}")
        return content

    def amend_constitution(self, user_request: str, semantic_map: str) -> str:
        """Amende la Constitution existante (ou la crée) pour ajouter une nouvelle fonctionnalité."""
        logger.info("Analyse de la demande technique pour amendement de la Constitution...")
        
        existing_content = ""
        if self.constitution_path.exists():
            existing_content = self.constitution_path.read_text(encoding="utf-8")
        
        system_prompt = """Tu es l'Architecte de Maintenance de Speckit.Factory.
            Ta mission est d'amender une CONSTITUTION existante pour y intégrer une nouvelle COMPOSANTE (Fonctionnalité).
            
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

        logger.info(f"Constitution amendée dans {self.constitution_path}")
        return content
