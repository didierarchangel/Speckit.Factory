from __future__ import annotations

from itertools import chain
from typing import Any, Dict, Iterable, List


class PatternVisionDetector:
    """Module UI Pattern Detector (Vision) : détecte les tokens visuels."""

    def __init__(self, model: Any = None):
        self.model = model

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
        # On force le mode custom si un model est présent pour garantir une vraie IA
        is_custom = self.model is not None or any(kw in prompt.lower() for kw in ["design like", "style of", "pinterest", "gpt description", "modern", "minimalist", "premium", "hospital", "neon", "dark"])
        
        if is_custom and self.model:
            style = "custom"
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✨ AI Design Brain activated for prompt: {prompt[:50]}...")
            tokens = self._extract_tokens_with_llm(prompt)
        elif is_custom or image_meta:
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

    def _extract_tokens_with_llm(self, prompt: str) -> Dict[str, Any]:
        """Utilise le LLM pour imaginer et extraire des tokens de design uniques."""
        from langchain_core.messages import HumanMessage
        from langchain_core.output_parsers import JsonOutputParser
        import logging

        logger = logging.getLogger(__name__)
        
        system_instructions = """You are a World-Class UI/UX Designer. Based on the user's vibe description, extract the design tokens.
        
        You MUST return a VALID JSON structure following this schema exactly:
        {
          "colors": {
            "primary": "HEX",
            "secondary": "HEX",
            "accent": "HEX",
            "background": "HEX",
            "surface": "HEX",
            "success": "#059669",
            "warning": "#d97706",
            "error": "#dc2626",
            "on_primary": "#ffffff",
            "on_background": "HEX"
          },
          "typography": {
            "font_family": "FontName, sans-serif",
            "weights": {"regular": 400, "medium": 500, "bold": 700},
            "scale": {"h1": "3rem", "h2": "2.25rem", "body": "1rem"}
          },
          "tokens": {
            "radius": {"card": "rem", "button": "rem", "input": "rem"},
            "shadow": {"soft": "CSS Shadow", "elevated": "CSS Shadow", "glass": "CSS Shadow"},
            "spacing": {"small": "8px", "medium": "16px", "large": "32px"}
          }
        }
        
        Be creative! Use professional color palettes (not just blue/gray). 
        If the user wants 'Cyberpunk', use Neons. If 'Premium', use Golds/Deep Greens/Dark Grays.
        Return ONLY the JSON. No markdown backticks, no comments."""

        user_prompt = f"Description de la Vibe Design : \"{prompt}\".\nExtraite les tokens maintenant."
        
        try:
            # 🛡️ Direct LLM call with StrOutputParser for safety then manual parse
            message = [HumanMessage(content=system_instructions + "\n\n" + user_prompt)]
            response = self.model.invoke(message)
            raw_content = response.content
            
            # Parsing JSON
            import re
            import json
            # Nettoyage si jamais l'IA met des backticks
            json_match = re.search(r"({.*})", raw_content.replace("\n", " "), re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                tokens = json.loads(json_str)
                logger.info("✅ Vibe Design Tokens successfully extracted by AI.")
                return tokens
            else:
                logger.warning("⚠️ AI Design Brain returned invalid format. Falling back to regex.")
                return self._extract_custom_tokens(prompt, None)
                
        except Exception as e:
            logger.error(f"❌ AI Design extraction failed: {e}. Falling back.")
            return self._extract_custom_tokens(prompt, None)
