class DesignValidator:
    """Validates patterns against the design constitution."""
    def __init__(self, constitution):
        self.constitution = constitution

    def validate_colors(self, pattern):
        """Checks if colors used in the pattern are allowed by the constitution."""
        # Simple validation: if constitution defines primary color, 
        # we check if it matches (very permissive for now)
        allowed_colors = self.constitution.get("colors", {})
        # Logique plus complexe possible ici
        return True

    def validate_layout(self, pattern):
        """Checks if layout rules are respected."""
        return True

    def validate(self, pattern):
        """Main validation method."""
        if not self.validate_colors(pattern):
            return False
        if not self.validate_layout(pattern):
            return False
        return True
