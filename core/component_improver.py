from __future__ import annotations

from typing import Any, Dict, Iterable, List


class ComponentImprover:
    """Module Component Improver : enrichit la liste de composants front utilisateurs."""

    def __init__(self, model: Any = None):
        self.model = model

    VARIANT_MAP = {
        "card": ["stats card", "insight card", "feature card"],
        "button": ["primary", "ghost", "outline"],
        "modal": ["confirmation", "form", "wizard"],
        "sidebar": ["compact", "expanded", "floating"],
    }

    def improve(self, raw_components: str | Iterable[str]) -> Dict[str, Any]:
        components = self._normalize(raw_components)
        improved_list = []
        for name in components:
            tags = self._derive_tags(name)
            variants = self._derive_variants(name)
            improved_list.append(
                {
                    "name": name,
                    "tags": tags,
                    "variants": variants,
                    "roles": self._annotate_roles(name),
                }
            )
        return {
            "components": improved_list,
            "missing_slots": self._detect_missing_components(components),
            "enriched_by": "ComponentImprover",
        }

    def _normalize(self, payload: str | Iterable[str]) -> List[str]:
        if isinstance(payload, str):
            lines = [line.strip() for line in payload.replace("•", "\n").splitlines()]
            payload = lines
        return [comp.title() for comp in payload if comp and len(comp.strip()) > 0]

    def _derive_tags(self, component: str) -> List[str]:
        tags = []
        lower = component.lower()
        if "modal" in lower:
            tags.append("overlay")
        if "card" in lower or "widget" in lower:
            tags.append("metric")
        if "navbar" in lower or "sidebar" in lower:
            tags.append("navigation")
        if "form" in lower or "input" in lower:
            tags.append("control")
        if not tags:
            tags.append("ui")
        return tags

    def _derive_variants(self, component: str) -> List[str]:
        lower = component.lower()
        for key, variants in self.VARIANT_MAP.items():
            if key in lower:
                return variants
        return ["default"]

    def _annotate_roles(self, component: str) -> List[str]:
        roles = []
        lower = component.lower()
        if any(term in lower for term in ("nav", "sidebar", "menu")):
            roles.append("navigation")
        if any(term in lower for term in ("card", "widget", "stat")):
            roles.append("data-display")
        if any(term in lower for term in ("form", "input", "login")):
            roles.append("interaction")
        if not roles:
            roles.append("layout")
        return roles

    def _detect_missing_components(self, normalized_components: List[str]) -> List[str]:
        expected = {"Sidebar", "Navbar", "Button", "Card", "Modal", "Stats Widget"}
        missing = expected - set(normalized_components)
        return sorted(missing)
