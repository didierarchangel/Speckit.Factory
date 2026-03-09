class PatternRanker:
    """Algorithm to rank UI patterns based on UX, response, and aesthetic scores."""
    def score(self, pattern, constitution_score):
        """Calculates the final score for a pattern."""
        ux = pattern["scores"]["ux"]
        resp = pattern["scores"]["responsive"]
        aest = pattern["scores"]["aesthetic"]

        # weighted average including alignment with design constitution
        score = (
            ux * 0.35
            + resp * 0.25
            + aest * 0.25
            + constitution_score * 0.15
        )

        return score

    def rank(self, patterns, constitution_score):
        """Ranks a list of patterns and returns the best one."""
        if not patterns:
            return None
            
        scored = []
        for p in patterns:
            s = self.score(p, constitution_score)
            scored.append((s, p))

        # Sort by score descending
        scored.sort(reverse=True, key=lambda x: x[0])

        return scored[0][1]
