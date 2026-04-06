from __future__ import annotations

from typing import Any, Dict, Iterable


class ConstitutionGenerator:
    """Module Constitution Generator : rassemble brief, design et UX."""

    def __init__(self, model: Any = None):
        self.model = model

    def generate(
        self,
        project_brief: Dict[str, Any],
        design_system: Dict[str, Any],
        ux_flow: Dict[str, Any],
    ) -> Dict[str, Any]:
        vision = project_brief.get("summary", "")
        workflow = project_brief.get("workflow", [])
        tokens = design_system.get("tokens", {})
        components = design_system.get("components", [])
        pages = ux_flow.get("pages", [])
        rules = ux_flow.get("rules", [])

        content_lines = [
            "# 📜 Constitution Speckit.UI/UX Maker",
            "",
            "## 🎯 Vision",
            vision,
            "",
            "## 🧱 Architecture Technique",
            f"- Stack recommandé: {', '.join(project_brief.get('stack_recommendations', {}).values())}",
            f"- Modules activés: {', '.join(project_brief.get('modules', []))}",
            "",
            "## 🎨 Design System Généré",
            f"- Style: {design_system.get('style', 'premium')}",
            f"- Tokens clés: {', '.join(tokens.get('colors', {}).keys())}",
            f"- Components: {', '.join([c['name'] for c in components[:3]])}",
            "",
            "## 🧭 UX Flow",
            f"- Pages prioritaires: {', '.join(pages)}",
            f"- Règles: {', '.join(rules)}",
            "",
            "## 🧠 Workflow Speckit.UI/UX Maker",
        ]
        for idx, step in enumerate(workflow, start=1):
            content_lines.append(f"{idx:02d}. {step}")
        content_lines.append("")
        content_lines.append("## 🔐 Playbook Constitution")
        content_lines.append("- Documenter les tokens dans `design/templates/tokens.yaml`.")
        content_lines.append("- Mettre à jour `design/constitution_design.yaml` avec les nouveaux DS-xx.")

        return {
            "content": "\n".join(content_lines),
            "summary": f"Vision: {vision}; Pages: {', '.join(pages)}",
            "design_system_ref": design_system.get("style", "premium"),
        }
