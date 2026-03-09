import yaml
from pathlib import Path
from core.pattern_engine import PatternEngine
from core.pattern_ranker import PatternRanker
from core.ui_ast import UIComponent, UIAST
from core.design_validator import DesignValidator

class GraphicDesign:
    """Main subagent engine for UI Intelligence."""
    def __init__(self, dataset_dir, constitution_path):
        self.engine = PatternEngine(dataset_dir)
        self.ranker = PatternRanker()
        
        # Load constitution
        with open(constitution_path, 'r', encoding='utf-8') as f:
            self.constitution = yaml.safe_load(f)
            
        self.validator = DesignValidator(self.constitution)

    def parse_intent(self, prompt):
        """Analyses the prompt to detect the UI category."""
        prompt = prompt.lower()
        
        if "dashboard" in prompt or "admin" in prompt:
            return "card" # Dashboards are often card-based
        if "hero" in prompt or "header" in prompt:
            return "hero"
        if "form" in prompt or "input" in prompt:
            return "form"
        if "table" in prompt or "list" in prompt or "data" in prompt:
            return "table"
        if "badge" in prompt or "tag" in prompt:
            return "badge"
        if "button" in prompt:
            return "button"
            
        return "card" # default

    def select_pattern(self, category, preferred_system=None):
        """Selects the best pattern based on category and optional preference."""
        patterns = self.engine.search(category=category)
        
        if not patterns:
            # Fallback to any pattern if category not found
            patterns = self.engine.patterns[:5]
            
        if preferred_system:
             # Filter by system if mentioned (e.g. "pronanut")
             filtered = [p for p in patterns if preferred_system.lower() in p["id"].lower()]
             if filtered:
                 patterns = filtered

        # Rank and return the best one
        best = self.ranker.rank(patterns, 9) # Arbitrary 9 for constitution alignment for now
        return best

    def build_ast(self, pattern):
        """Constructs the UI AST from a selected pattern."""
        ast = UIAST()
        
        comp = UIComponent(
            pattern.get("category", "Component"),
            props=pattern.get("tailwind", {})
        )
        
        ast.add_component(comp)
        return ast

    def generate(self, prompt):
        """Main entry point: Intent -> Pattern selection -> AST generation."""
        category = self.parse_intent(prompt)
        
        # Détection du système de design (premium ou Standard)
        # Priorité : Prompt > Lockfile > Default (Standard)
        system = None
        
        # 1. Vérification dans le prompt
        if any(kw in prompt.lower() for kw in ["premium", "business", "clean", "pro"]):
            system = "premium"
        elif "standard" in prompt.lower():
            system = "Standard"
            
        # 2. Si non présent dans le prompt, vérification dans le .spec-lock.json
        if not system:
            lock_file = Path(".spec-lock.json")
            if lock_file.exists():
                try:
                    import json
                    with open(lock_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        system = data.get("stack_preferences", {}).get("design")
                except:
                    pass
        
        # 3. Fallback par défaut si aucune préférence trouvée
        system = system or "Standard"
            
        pattern = self.select_pattern(category, preferred_system=system)
        
        if not pattern:
            return {"error": "No pattern found for category: " + category}
            
        ast = self.build_ast(pattern)
        
        return {
            "pattern": pattern["id"],
            "ui_ast": ast.to_json(),
            "tailwind": pattern["tailwind"]
        }
