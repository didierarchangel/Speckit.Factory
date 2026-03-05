import logging
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

class ConstitutionManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
        self.constitution_path = self.root / "Constitution" / "CONSTITUTION.md"
        
        # Charger le template de base
        self.template_path = Path(__file__).parent.parent / "templates" / "CONSTITUTION.template.md"

    def generate_constitution(self, user_request: str) -> str:
        """Produit la Constitution (Architecture, Standards, Stack) à partir d'une demande utilisateur."""
        logger.info("Analyse de la demande utilisateur pour génération de Constitution...")
        
        base_template = ""
        if self.template_path.exists():
            base_template = self.template_path.read_text(encoding="utf-8")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es l'Architecte Suprême du framework Speckit.Factory.
            Ta mission est de transformer une demande utilisateur en une CONSTITUTION rigoureuse.
            
            La Constitution doit impérativement définir :
            1. L'Architecture (Folders, Layers)
            2. La Stack Technique (Langages, Frameworks, DB) - LE BACKEND DOIT ÊTRE EN NODE.JS (SOIS PRÉCIS sur les versions).
               - Privilégie Express ou NestJS pour le backend.
            3. Les Standards de Code (Naming, Security).
            4. Le Schéma de Données (si applicable).

            Utilise ce template comme base de structure :
            {template}
            
            SOIS EXHAUSTIF. Ne fais pas de suppositions floues. Si l'utilisateur demande MongoDB, liste les collections nécessaires."""),
            ("user", "Demande utilisateur : {request}")
        ])

        chain = prompt | self.model | StrOutputParser()
        content = chain.invoke({"template": base_template, "request": user_request})

        # Sauvegarde
        self.constitution_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.constitution_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Constitution générée dans {self.constitution_path}")
        return content
