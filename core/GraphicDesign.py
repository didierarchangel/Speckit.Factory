import yaml
import logging
from pathlib import Path
from core.pattern_engine import PatternEngine
from core.pattern_ranker import PatternRanker
from core.ui_ast import UIComponent, UIAST
from core.design_validator import DesignValidator

logger = logging.getLogger(__name__)

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
        """🎨 Analyses the prompt to detect the UI category/pattern.
        
        Maps natural language intent to UI patterns:
        - dashboard/admin → multi-component layout with cards + table
        - home/landing → hero + features + CTA
        - form → form with inputs
        - table/list → data grid
        - hero/header → large banner
        - button/badge → atomic component
        """
        prompt = prompt.lower()
        
        # 🎯 More precise intention detection aligned with project terms
        if any(kw in prompt for kw in ["dashboard", "admin", "analytics", "homepage", "home"]):
            return "hero" if "home" in prompt else "table" # Use hero for home, table for admin as default
        
        if any(kw in prompt for kw in ["articlelist", "list", "table", "data", "grid"]):
            return "table"
            
        if any(kw in prompt for kw in ["form", "register", "login", "input", "forms", "contact"]):
            return "form"
            
        if any(kw in prompt for kw in ["hero", "header", "banner", "welcome"]):
            return "hero"
        
        if any(kw in prompt for kw in ["badge", "tag", "chip", "status"]):
            return "badge"
        
        if any(kw in prompt for kw in ["button", "cta", "action"]):
            return "button"
        
        # Default: safe card component
        return "card"

    def select_pattern(self, category, preferred_system=None):
        """Selects the best pattern based on category and optional preference."""
        patterns = self.engine.search(category=category)
        
        if not patterns:
            # Fallback to any pattern if category not found
            patterns = self.engine.patterns[:5]
            
        if preferred_system:
             # Filter using the SYSTEM field
             filtered = [p for p in patterns if p.get("system") == preferred_system.lower()]
             if filtered:
                 patterns = filtered
                 logger.info(f"   ✅ Using patterns from preferred system: {preferred_system}")
             else:
                 logger.warning(f"⚠️ No patterns found for system: {preferred_system} in category: {category}")
                 # Fallback logic: try standard if premium was requested and failed
                 if preferred_system.lower() == "premium":
                     standard_fallback = [p for p in patterns if p.get("system") == "standard"]
                     if standard_fallback:
                         patterns = standard_fallback
                         logger.info(f"   🔄 Falling back to 'standard' system for category: {category}")

        # Rank and return the best one
        best = self.ranker.rank(patterns, 9) # Arbitrary 9 for constitution alignment for now
        return best

    def build_ast(self, pattern):
        """🏗️ Constructs a realistic UI AST from a selected pattern.
        
        Instead of creating a single component, builds a component hierarchy
        that reflects real UI structure (Layout → Components → Details).
        """
        ast = UIAST()
        
        category = pattern.get("category", "component")
        pattern_id = pattern.get("id", "unknown")
        tailwind = pattern.get("tailwind", {})
        
        # Base layout container for all patterns
        layout = UIComponent(
            "Layout",
            props={
                "container": tailwind.get("container", "max-w-7xl mx-auto px-6")
            }
        )
        
        # 🎯 Category-specific component hierarchy
        if category == "dashboard":
            # Dashboard: Layout → Stats Cards → Data Table
            
            # Stats/Info Cards (multiple)
            card_props = {k: v for k, v in tailwind.items() 
                         if "card" in k.lower() or "stat" in k.lower() or k in ["container", "title", "value"]}
            if card_props:
                stats_card = UIComponent("StatsCard", props=card_props)
                layout.children.append(stats_card)
            
            # Data Table
            table_props = {k: v for k, v in tailwind.items() 
                          if "table" in k.lower() or k in ["header", "row", "cell", "pagination"]}
            if table_props:
                data_table = UIComponent("DataTable", props=table_props)
                layout.children.append(data_table)
            
        elif category == "hero":
            # Hero: Layout → Hero Banner → Features → CTA
            
            # Hero Banner
            hero_props = {k: v for k, v in tailwind.items() 
                         if "hero" in k.lower() or k in ["container", "title", "subtitle", "button"]}
            if hero_props:
                hero = UIComponent("HeroBanner", props=hero_props)
                layout.children.append(hero)
            
            # Feature Grid
            feature_props = {k: v for k, v in tailwind.items() 
                            if "feature" in k.lower() or "card" in k.lower() or k in ["item"]}
            if feature_props:
                features = UIComponent("FeatureGrid", props=feature_props)
                layout.children.append(features)
            
            # CTA Button
            cta_props = {k: v for k, v in tailwind.items() 
                        if "button" in k.lower() or "cta" in k.lower()}
            if cta_props:
                cta = UIComponent("CTAButton", props=cta_props)
                layout.children.append(cta)
        
        elif category == "form":
            # Form: Layout → FormContainer → InputFields → SubmitButton
            
            form_props = {k: v for k, v in tailwind.items() 
                         if "form" in k.lower() or k in ["container"]}
            if not form_props:
                form_props = tailwind
            
            form = UIComponent("FormContainer", props=form_props)
            
            # Input fields
            input_props = {k: v for k, v in tailwind.items() 
                          if "input" in k.lower() or "field" in k.lower()}
            if input_props:
                inputs = UIComponent("InputFields", props=input_props)
                form.children.append(inputs)
            
            # Submit button
            button_props = {k: v for k, v in tailwind.items() 
                           if "button" in k.lower()}
            if button_props:
                submit = UIComponent("SubmitButton", props=button_props)
                form.children.append(submit)
            
            layout.children.append(form)
        
        elif category in ["table", "dashboard"]:
            # Table/Dashboard: Layout → DataTable → Pagination
            table_props = tailwind
            table = UIComponent("DataTable", props=table_props)
            
            if "pagination" in tailwind or "pagination" in pattern_id.lower():
                pagination = UIComponent("Pagination", props=tailwind)
                table.children.append(pagination)
            
            layout.children.append(table)
        
        elif category in ["card", "component", "button", "badge"]:
            # Simple component
            comp_name = pattern.get("category", "Component").title()
            # Standardize component names for React/Vue
            if comp_name == "Button": comp_name = "Button"
            elif comp_name == "Badge": comp_name = "Badge"
            
            comp = UIComponent(comp_name, props=tailwind)
            layout.children.append(comp)
        
        # Add layout to AST
        ast.add_component(layout)
        
        logger.info(f"🏗️ AST built: {category} pattern with {len(layout.children)} child components")
        
        return ast

    def generate(self, prompt):
        """🎨 Main entry point: Intent → Pattern selection → AST generation.
        
        This is the UI compilation pipeline that should influence all React/Vue code generation.
        """
        print("🎨 GraphicDesign ENGINE RUNNING")
        logger.info(f"🎨 GraphicDesign.generate() ACTIVATED for: {prompt[:50]}...")
        
        category = self.parse_intent(prompt)
        logger.info(f"   📋 Intent detected: {category}")
        
        # 🔍 Design system detection (premium ou Standard)
        system = None
        framework = "react" # Default
        
        # 1. Check prompt for preference
        if any(kw in prompt.lower() for kw in ["premium", "business", "clean", "pro", "modern"]):
            system = "premium"
            logger.info(f"   ✅ Premium system detected in prompt")
        elif "standard" in prompt.lower():
            system = "standard"
            logger.info(f"   ✅ Standard system detected in prompt")
            
        # 2. Check keyword for framework hints
        if "vue" in prompt.lower(): framework = "vue"
        elif "next" in prompt.lower(): framework = "nextjs"

        # 3. If not in prompt, check .spec-lock.json
        lock_file = Path(".spec-lock.json")
        if lock_file.exists():
            try:
                import json
                with open(lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    stack = data.get("stack_preferences", {})
                    if not system:
                        system = stack.get("design")
                    framework = stack.get("framework", framework)
                    logger.info(f"   ✅ Specs from lock: system={system}, framework={framework}")
            except Exception as e:
                logger.debug(f"   ℹ️ Could not read .spec-lock.json: {e}")
        
        # 4. Default to standard
        system = system or "standard"
        logger.info(f"   🎯 Final system: {system} | Framework: {framework}")
            
        # Select pattern
        pattern = self.select_pattern(category, preferred_system=system)
        
        if not pattern:
            logger.error(f"❌ No pattern found for category: {category}")
            return {"error": f"No pattern found for category: {category}"}
            
        logger.info(f"   🎀 Pattern selected: {pattern.get('id', 'unknown')}")
        
        # Build AST
        ast = self.build_ast(pattern)
        
        result = {
            "pattern": pattern["id"],
            "category": category,
            "design_system": system,
            "framework": framework,
            "ui_ast": ast.to_json(),
            "tailwind": pattern.get("tailwind", {}),
            "scores": pattern.get("scores", {})
        }
        
        logger.info(f"✅ 🎨 GraphicDesign generation complete!")
        logger.info(f"   📦 Pattern: {result['pattern']}")
        logger.info(f"   🎯 System: {result['design_system']}")
        logger.info(f"   📐 Tailwind classes: {len(result['tailwind'])} keys")
        
        return result

    def generate_skeleton(self, design_result: dict) -> str:
        """Génère un squelette de composant basé sur le pattern et le framework."""
        framework = design_result.get("framework", "react").lower()
        
        if framework == "vue":
            return self._generate_vue_skeleton(design_result)
        elif framework == "nextjs":
            return self._generate_nextjs_skeleton(design_result)
        else:
            return self._generate_react_skeleton(design_result)

    def _generate_react_skeleton(self, design_result: dict) -> str:
        """Squelette React/Vite standard."""
        category = design_result.get("category", "component")
        tailwind = design_result.get("tailwind", {})
        
        if category == "hero":
            return f"""
export default function HeroSection() {{
  return (
    <section className="{tailwind.get('container', 'py-20 text-center')}">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h1 className="{tailwind.get('title', 'text-4xl font-extrabold')}">Title</h1>
        <p className="{tailwind.get('subtitle', 'mt-4 text-xl')}">Description</p>
        <div className="mt-10">
          <button className="{tailwind.get('button', 'px-8 py-3 rounded-md')}">Action</button>
        </div>
      </div>
    </section>
  )
}}
"""
        elif category == "table":
            return f"""
export default function DataTable() {{
  return (
    <div className="{tailwind.get('container', 'bg-white shadow rounded-lg overflow-hidden')}">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="{tailwind.get('header', 'bg-gray-50')}">
          <tr>
            <th className="{tailwind.get('header_cells', 'px-6 py-3 text-left font-medium uppercase')}">Col 1</th>
            <th className="{tailwind.get('header_cells', 'px-6 py-3 text-left font-medium uppercase')}">Col 2</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          <tr className="{tailwind.get('row', 'hover:bg-gray-50')}">
            <td className="{tailwind.get('cell', 'px-6 py-4')}">Data</td>
            <td className="{tailwind.get('cell', 'px-6 py-4')}">Value</td>
          </tr>
        </tbody>
      </table>
      <div className="{{tailwind.get('pagination', 'px-6 py-3 border-t')}}">
         {{/* Pagination */}}
      </div>
    </div>
  )
}}
"""
        else:
            return f"""
<div className="{tailwind.get('container', 'bg-white rounded-xl shadow-md p-6')}">
  <h2 className="{tailwind.get('title', 'text-xl font-bold')}">Title</h2>
</div>
"""

    def _generate_vue_skeleton(self, design_result: dict) -> str:
        """Squelette Vue.js 3 (Script Setup)."""
        category = design_result.get("category", "component")
        tailwind = design_result.get("tailwind", {})
        
        if category == "hero":
            return f"""
<template>
  <section class="{tailwind.get('container', 'py-20 text-center')}">
    <div class="max-w-7xl mx-auto px-4">
      <h1 class="{tailwind.get('title', 'text-4xl font-extrabold')}">Title</h1>
      <p class="{tailwind.get('subtitle', 'mt-4 text-xl')}">Description</p>
      <div class="mt-10">
        <button class="{tailwind.get('button', 'px-8 py-3 rounded-md')}">Action</button>
      </div>
    </div>
  </section>
</template>
<script setup></script>
"""
        elif category == "table":
            return f"""
<template>
  <div class="{tailwind.get('container', 'bg-white shadow rounded-lg overflow-hidden')}">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="{tailwind.get('header', 'bg-gray-50')}">
        <tr>
          <th class="{tailwind.get('header_cells', 'px-6 py-3 text-left uppercase')}">Header</th>
        </tr>
      </thead>
      <tbody class="bg-white divide-y divide-gray-200">
        <tr class="{tailwind.get('row', 'hover:bg-gray-50')}">
          <td class="{tailwind.get('cell', 'px-6 py-4')}">Cell Data</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup></script>
"""
        else:
            return f"""
<template>
  <div class="{tailwind.get('container', 'bg-white rounded-xl p-6 shadow-md')}">
    <h2 class="{tailwind.get('title', 'text-xl font-bold')}">Title</h2>
  </div>
</template>
<script setup></script>
"""

    def _generate_nextjs_skeleton(self, design_result: dict) -> str:
        """Squelette Next.js (App Router / Server Components)."""
        # Next.js uses React syntax, but we add "use client" if needed or specific markers
        return "'use client';\n" + self._generate_react_skeleton(design_result)
