# Gestion de la création/mise à jour de la Constitution
# Le fichier constitution.py agit comme un gardien.
# Il utilise LangChain pour transformer la demande brute de l'utilisateur en une architecture structurée,
# puis la fige dans le marbre numérique.


from langchain_core.messages import HumanMessage, SystemMessage
from pathlib import Path
import hashlib

class ConstitutionManager:
    def __init__(self, model, constitution_path="Constitution/CONSTITUTION.md"):
        self.path = Path(constitution_path)
        self.llm = model

    def _calculate_hash(self, content: str) -> str:
        """Calcule le hash SHA256 pour détecter les changements."""
        return hashlib.sha256(content.encode()).hexdigest()

    def generate_constitution(self, user_request: str) -> str:
        """
        Génère ou améliore la constitution à partir de la demande utilisateur.

        Fusionne l'ancienne propose_architecture (qui améliorait la demande)
        et generate_constitution (qui structurait en 4 piliers) en une seule méthode.
        Le prompt enrichit automatiquement la demande avec les contraintes techniques
        FullStack avant de la structurer.
        """
        system_prompt = (
            "Tu es l'Architecte en Chef de Speckit.Factory.\n"
            "Transforme la demande utilisateur en une Constitution formelle.\n\n"
            "ÉTAPE 1 — Enrichissement :\n"
            "Améliore la demande en précisant les contraintes techniques et "
            "les fonctionnalités FullStack.\n\n"
            "ÉTAPE 2 — Structuration en 4 Piliers :\n"
            "La Constitution DOIT suivre exactement ce format Markdown :\n\n"
            "# 1. PILIER ARCHITECTURAL\n"
            "[Description de l'architecture logicielle]\n\n"
            "# 2. PILIER DE SÉCURITÉ\n"
            "[Règles de chiffrement, gestion des accès]\n\n"
            "# 3. PILIER DE PERFORMANCE\n"
            "[Exigences de latence, scalabilité]\n\n"
            "# 4. PILIER DE MAINTENANCE\n"
            "[Logs, tests, déploiement]\n\n"
            "Rends la réponse concise mais complète."
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_request)
        ]
        
        result = self.llm.invoke(messages)
        return result.content

    def update_constitution(self, new_content: str) -> bool:
        """Met à jour la constitution si le contenu a changé (comparaison par hash)."""
        # Lire le contenu actuel (s'il existe)
        current_content = ""
        if self.path.exists():
            current_content = self.path.read_text(encoding="utf-8")

        # Comparer les hashes
        if self._calculate_hash(current_content) == self._calculate_hash(new_content):
            print("✅ La Constitution est déjà à jour (Hash identique).")
            return False

        # Écrire le nouveau contenu
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(new_content, encoding="utf-8")
        print(f"✅ Constitution mise à jour et verrouillée (Hash: {self._calculate_hash(new_content)}).")
        return True

    def create_or_update(self, user_request: str) -> bool:
        """
        Méthode de commodité : génère la constitution via le LLM
        puis l'écrit sur disque si le contenu a changé.
        """
        new_content = self.generate_constitution(user_request)
        return self.update_constitution(new_content)