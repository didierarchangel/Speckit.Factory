from __future__ import annotations

from itertools import chain
from typing import Any, Dict, Iterable, List


class PatternVisionDetector:
    """Module UI Pattern Detector (Vision) : détecte les tokens visuels."""

    BASE_COLORS = {
        "primary": "#2563eb",
        "secondary": "#1e293b",
        "accent": "#6366f1",
        "background": "#f8fafc",
        "surface": "#ffffff",
        "success": "#059669",
        "warning": "#d97706",
        "error": "#dc2626",
        "on_primary": "#ffffff",
        "on_background": "#0f172a",
    }

    BASE_TYPO = {
        "font_family": "Inter, 'Space Grotesk', system-ui",
        "weights": {"regular": 400, "medium": 500, "bold": 700},
        "scale": {"h1": "3rem", "h2": "2.5rem", "body": "1rem"},
    }

    BASE_TOKENS = {
        "radius": {"card": "1.25rem", "button": "1rem", "pill": "999px"},
        "shadow": {"elevated": "0 20px 45px -30px rgba(15, 23, 42, 0.55)"},
        "spacing": {"small": "8px", "medium": "16px", "large": "32px"},
    }

    def analyze(
        self,
        prompt: str,
        image_meta: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Analyse le prompt et les métadonnées image pour extraire des tokens de design."""
        
        # 1. Détecter si on est sur un style custom (LLM description/Pinterest reference)
        is_custom = any(kw in prompt.lower() for kw in ["design like", "style of", "pinterest", "gpt description", "modern", "minimalist"])
        
        if is_custom or image_meta:
            style = "custom"
            tokens = self._extract_custom_tokens(prompt, image_meta)
        else:
            style = self._infer_style(prompt, image_meta)
            color_palette = self._build_palette(style)
            tokens = {
                "colors": color_palette,
                "typography": self.BASE_TYPO,
                "tokens": self.BASE_TOKENS,
            }
            
        components = self._extract_components(prompt, image_meta)
        
        return {
            "style": style,
            "tokens": tokens,
            "components": components,
            "image_metadata": image_meta or {},
        }

    def _extract_custom_tokens(self, prompt: str, image_meta: dict | None) -> Dict[str, Any]:
        """Extrait des tokens spécifiques à partir d'une description textuelle ou meta image."""
        import re
        
        # Initialisation avec les bases
        palette = dict(self.BASE_COLORS)
        radius = dict(self.BASE_TOKENS["radius"])
        
        lower_prompt = prompt.lower()
        
        # -- 🎨 Couleurs --
        # Détection de codes Hex
        hex_colors = re.findall(r'#([A-Fa-f0-9]{3,6})', prompt)
        if hex_colors:
            if len(hex_colors) >= 1: palette["primary"] = f"#{hex_colors[0]}"
            if len(hex_colors) >= 2: palette["accent"] = f"#{hex_colors[1]}"
            if len(hex_colors) >= 3: palette["background"] = f"#{hex_colors[2]}"

        # Mots clés de couleurs
        if "glass" in lower_prompt or "glassmorphism" in lower_prompt:
            palette["surface"] = "rgba(255, 255, 255, 0.1)"
            palette["on_background"] = "#ffffff"
        if "dark" in lower_prompt or "black" in lower_prompt:
            palette["background"] = "#0f172a"
            palette["surface"] = "#1e293b"
            palette["on_background"] = "#f8fafc"

        # -- 📐 Radius --
        if any(kw in lower_prompt for kw in ["rounded", "soft", "organic"]):
            radius["card"] = "1.5rem"
            radius["button"] = "999px"
        elif any(kw in lower_prompt for kw in ["sharp", "square", "brutalist"]):
            radius["card"] = "0px"
            radius["button"] = "0px"

        return {
            "colors": palette,
            "typography": self.BASE_TYPO,
            "tokens": {
                "radius": radius,
                "shadow": self.BASE_TOKENS["shadow"],
                "spacing": self.BASE_TOKENS["spacing"],
            }
        }

    def _infer_style(self, prompt: str, image_meta: Dict[str, Any] | None) -> str:
        lower = prompt.lower()
        if "material" in lower:
            return "material"
        if "fluent" in lower:
            return "fluent"
        if "premium" in lower or "dashboard" in lower:
            return "premium"
        if image_meta and image_meta.get("dominant_style"):
            return image_meta["dominant_style"]
        return "premium"

    def _build_palette(self, style: str) -> Dict[str, str]:
        palette = dict(self.BASE_COLORS)
        if style == "material":
            palette.update({"primary": "#3b82f6", "accent": "#10b981"})
        elif style == "fluent":
            palette.update({"primary": "#0ea5e9", "accent": "#22d3ee"})
        elif style == "premium":
            palette.update({"primary": "#1d4ed8", "accent": "#8b5cf6", "surface": "#f3f4f6"})
        return palette

    def _extract_components(
        self, prompt: str, image_meta: Dict[str, Any] | None
    ) -> List[str]:
        candidates = []
        for token in ["button", "card", "modal", "navbar", "sidebar", "stats"]:
            if token in prompt.lower():
                candidates.append(token)
        if image_meta:
            candidates.extend(image_meta.get("detected_components", []))
        return sorted(set(candidates))
