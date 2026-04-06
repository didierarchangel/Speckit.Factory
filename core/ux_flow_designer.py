from __future__ import annotations

from typing import Any, Dict, Iterable, List


class UXFlowDesigner:
    """Module UX Flow Designer : structure les flux d'interactions."""

    def __init__(self, model: Any = None):
        self.model = model

    def design_flow(
        self,
        ux_instruction: str,
        component_manifest: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        transitions = self._extract_transitions(ux_instruction)
        pages = self._identify_pages(ux_instruction, component_manifest)
        return {
            "pages": pages,
            "transitions": transitions,
            "interactions": self._highlight_interactions(ux_instruction),
            "rules": [
                "Favor scroll-jacking-free navigation",
                "Always provide confirmation modals on destructive actions",
                "Transition animations follow 200ms ease-out",
            ],
        }

    def _extract_transitions(self, ux_instruction: str) -> List[str]:
        sentences = [s.strip() for s in ux_instruction.split(".") if s.strip()]
        transitions = []
        for sentence in sentences:
            if "when" in sentence.lower() or "quand" in sentence.lower():
                transitions.append(sentence)
        if not transitions:
            transitions.append("Default flow: Home → Dashboard → Detail")
        return transitions

    def _identify_pages(
        self, ux_instruction: str, component_manifest: Dict[str, Any] | None
    ) -> List[str]:
        pages = []
        lower = ux_instruction.lower()
        for candidate in ["dashboard", "profile", "settings", "login", "products"]:
            if candidate in lower:
                pages.append(candidate.title())
        if component_manifest:
            for comp in component_manifest.get("components", []):
                tags = comp.get("tags", [])
                if "navigation" in tags and "Layout" not in pages:
                    pages.append("Navigation")
        if not pages:
            pages = ["Home", "Dashboard"]
        return pages

    def _highlight_interactions(self, ux_instruction: str) -> List[str]:
        interactions = []
        words = ["hover", "click", "tap", "swipe", "drag"]
        for action in words:
            if action in ux_instruction.lower():
                interactions.append(action)
        if not interactions:
            interactions.append("click")
        return interactions
