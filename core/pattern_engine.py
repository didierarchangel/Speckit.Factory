import json
import random
from pathlib import Path

class PatternEngine:
    """Logic to search and generate pattern variants from multiple datasets."""
    def __init__(self, dataset_dir):
        self.patterns = []
        self._load_all_patterns(dataset_dir)

    def _load_all_patterns(self, dataset_dir):
        """Loads all .json files from the dataset directory."""
        path = Path(dataset_dir)
        if not path.exists():
            return
            
        for json_file in path.glob("*.json"):
            if json_file.name == "generator_rules.json" or json_file.name == "pattern_index.json":
                continue
            try:
                with open(json_file, encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.patterns.extend(data)
                    elif isinstance(data, dict):
                        self.patterns.append(data)
            except Exception as e:
                print(f"Error loading {json_file}: {e}")

    def search(self, category=None, pattern_id=None):
        """Searches for patterns by category or ID."""
        if pattern_id:
            return [p for p in self.patterns if p.get("id") == pattern_id]
        if category:
            return [p for p in self.patterns if p.get("category") == category]
        return self.patterns

    def random_variant(self, pattern):
        """Generates a random variant of a pattern (e.g. adding hover effects)."""
        variant = json.loads(json.dumps(pattern)) # deep copy
        
        # Simple example enhancement: add a subtle hover effect if it's a card/container
        if "container" in variant.get("tailwind", {}):
            if "hover:" not in variant["tailwind"]["container"]:
                variant["tailwind"]["container"] += " hover:shadow-lg transition-shadow"

        return variant
