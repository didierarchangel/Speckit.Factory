# Ce module est le chef d'orchestre de votre workflow :
# il prend la Constitution validée et la transforme en une liste de tâches actionnables,
# tout en assurant le suivi de progression (Réalisé vs Non réalisé).

# Ce script utilise LangChain pour analyser la Constitution et
# générer le fichier etapes.md qui servira de feuille de route à tous les agents

import re
import logging
import json
import unicodedata
from pathlib import Path
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

def is_real_file(path: str):
    return path.endswith((
        ".ts", ".tsx",
        ".js", ".jsx",
        ".json", ".jsonc",
        ".py",
        ".md",
        ".env", ".yaml", ".yml",
        ".sh", ".css", ".html"
    ))
    
STARTUP_INSTRUCTIONS = """
---

## 🏃‍♂️ Démarrer votre application localement

Une fois les étapes ci-dessus terminées, suivez ces instructions pour lancer vos serveurs.

### 🏠 Backend
Avant de lancer le serveur pour la première fois :
```bash
cd backend
npm install
npm start
```

### 🎨 Frontend
Avant de lancer le serveur pour la première fois :
```bash
cd frontend
npm install
npm run dev
```
"""

class EtapeManager:
    def __init__(self, model, project_root: str = "."):
        self.model = model
        self.root = Path(project_root)
        self.constitution_path = self.root / "Constitution" / "CONSTITUTION.md"
        self.mapping_component_path = self.root / "Constitution" / "MappingComponent.md"
        self.etapes_path = self.root / "Constitution" / "etapes.md"
        self.history_path = self.root / "Constitution" / "EtapesAdd.md"
        self.image_meta_path = self.root / "design" / "image_meta.json"
        self.constitution_design_path = self.root / "design" / "constitution_design.yaml"

    def _load_design_inputs(self, constitution_content: str = "") -> dict:
        """Charge les sources de verite design et construit un blueprint de mapping."""
        image_meta_raw = ""
        constitution_design_raw = ""
        mapping_component_raw = ""
        detected_components_from_image: list[str] = []
        image_meta_payload: dict = {}

        if self.image_meta_path.exists():
            image_meta_raw = self.image_meta_path.read_text(encoding="utf-8")
            try:
                payload = json.loads(image_meta_raw)
                if isinstance(payload, dict):
                    image_meta_payload = payload
                raw_components = payload.get("detected_components", [])
                if isinstance(raw_components, list):
                    detected_components_from_image = [
                        str(component).strip()
                        for component in raw_components
                        if str(component).strip()
                    ]
            except Exception as e:
                logger.warning(
                    "Impossible de parser design/image_meta.json pour detected_components: %s",
                    e,
                )

        if self.constitution_design_path.exists():
            constitution_design_raw = self.constitution_design_path.read_text(encoding="utf-8")

        if self.mapping_component_path.exists():
            mapping_component_raw = self.mapping_component_path.read_text(encoding="utf-8")

        mapping_hints = self._extract_mapping_hints(mapping_component_raw)
        constitution_modules = self._extract_domain_modules_from_constitution(constitution_content)
        mapping_modules = mapping_hints.get("modules", [])
        domain_modules = list(dict.fromkeys(constitution_modules + mapping_modules))

        mapping_components = list((mapping_hints.get("placements") or {}).keys())
        detected_components = list(dict.fromkeys(detected_components_from_image + mapping_components))

        layout_blueprint = self._build_layout_blueprint(
            image_meta_payload=image_meta_payload,
            detected_components=detected_components,
            domain_modules=domain_modules,
            mapping_hints=mapping_hints,
        )
        layout_blueprint_text = self._format_layout_blueprint(layout_blueprint)

        return {
            "image_meta_raw": image_meta_raw or "(Fichier design/image_meta.json introuvable)",
            "constitution_design_raw": constitution_design_raw or "(Fichier design/constitution_design.yaml introuvable)",
            "mapping_component_raw": mapping_component_raw or "(Fichier Constitution/MappingComponent.md introuvable)",
            "detected_components": detected_components,
            "domain_modules": domain_modules,
            "constitution_modules": constitution_modules,
            "mapping_modules": mapping_modules,
            "mapping_hints": mapping_hints,
            "layout_blueprint": layout_blueprint,
            "layout_blueprint_text": layout_blueprint_text,
        }

    def _normalize_component_name(self, value: str) -> str:
        """Normalise un nom de composant pour comparaison robuste."""
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def _component_filename(self, component: str) -> str:
        """Construit un nom de fichier composant stable à partir du nom détecté."""
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", component.strip())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or "component"

    def _strip_accents(self, value: str) -> str:
        """Retire les accents pour simplifier le parsing heuristique."""
        return "".join(
            ch for ch in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(ch)
        )

    def _normalize_domain_module_candidate(self, candidate: str) -> str | None:
        """Normalise un candidat module pour extraire un nom metier propre."""
        if not candidate:
            return None

        text = self._strip_accents(candidate.lower())
        text = text.replace("’", "'")
        text = re.sub(r"\(.*?\)", " ", text)
        if ":" in text:
            text = text.split(":", 1)[0]
        text = re.sub(r"[_/\\-]+", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return None

        joined = text
        # Canonicalisation domaine HMS (et fallback generic)
        if "patient" in joined:
            return "patients"
        if "consult" in joined:
            return "consultations"
        if "prescri" in joined:
            return "prescriptions"
        if "factur" in joined or "bill" in joined:
            return "billing"
        if "alert" in joined:
            return "alerts"
        if "rendez" in joined or "appointment" in joined:
            return "appointments"

        stopwords = {
            "gestion", "module", "modules", "metier", "metiers", "business", "domain", "domaine",
            "feature", "features", "fonctionnalite", "fonctionnalites", "section", "sections",
            "de", "des", "du", "la", "le", "les", "et", "ou", "pour", "avec", "sur", "par",
            "app", "application", "dashboard", "layout",
        }
        technical = {
            "esm", "esnext", "typescript", "target", "es2022", "node", "nodejs", "react", "vite",
            "tailwind", "jwt", "mongodb", "mongoose", "zod", "cors", "dotenv", "openai",
            "graphicdesign", "tsc", "noemit", "frontend", "backend", "api", "rest",
            "auth", "login", "register", "protectedroute", "config", "configuration",
        }

        words = [w for w in text.split() if w]
        filtered = [
            w for w in words
            if w not in stopwords and w not in technical and not re.fullmatch(r"module\d+", w)
        ]
        if not filtered:
            return None

        token = filtered[-1]
        if len(token) < 3:
            return None
        if token in technical:
            return None
        if any(char.isdigit() for char in token):
            return None
        return token

    def _extract_domain_modules_from_constitution(self, constitution_content: str) -> list[str]:
        """Extrait une liste de modules metier depuis la CONSTITUTION."""
        if not constitution_content:
            return []

        modules: list[str] = []
        seen: set[str] = set()
        in_modules_block = False

        for raw_line in constitution_content.splitlines():
            line = raw_line.strip()
            if not line:
                in_modules_block = False
                continue

            if line.startswith("#"):
                header = self._strip_accents(line.lower())
                has_module_marker = any(
                    marker in header for marker in ("module", "entit", "feature", "fonctionnalit", "domain", "domaine")
                )
                has_business_marker = any(
                    marker in header for marker in ("metier", "business", "domain", "domaine", "feature", "fonction")
                )
                in_modules_block = has_module_marker and has_business_marker
                continue

            parse_line = in_modules_block and (
                line.startswith(("-", "*")) or "`" in line or ":" in line or re.match(r"^\d+\.", line)
            )
            if not parse_line:
                continue

            candidates = re.findall(r"`([^`]+)`", line)
            if not candidates:
                probe = re.sub(r"^[-*\d\.\)\s]+", "", line)
                candidates = re.split(r"[,;/|]", probe)

            for candidate in candidates:
                token = self._normalize_domain_module_candidate(candidate)
                if not token:
                    continue
                if token in seen:
                    continue
                seen.add(token)
                modules.append(token)

        return modules[:12]

    def _extract_mapping_hints(self, mapping_content: str) -> dict:
        """Extrait modules/sections/layout/placements depuis MappingComponent.md."""
        hints = {
            "layout": "",
            "sections": [],
            "modules": [],
            "placements": {},
        }
        if not mapping_content:
            return hints

        modules: list[str] = []
        sections: list[str] = []
        placements: dict[str, str] = {}
        in_modules = False
        in_mapping = False
        in_layout = False

        for raw_line in mapping_content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("## "):
                low_h = self._strip_accents(line.lower())
                in_modules = ("module" in low_h) and any(
                    marker in low_h for marker in ("metier", "business", "domain", "domaine", "feature")
                )
                in_mapping = ("mapping" in low_h and "composant" in low_h) or ("mapping" in low_h and "component" in low_h)
                in_layout = "layout" in low_h
                continue

            m_layout = re.search(r"\blayout\s*:\s*(.+)$", line, flags=re.IGNORECASE)
            if m_layout:
                layout_raw = self._strip_accents(m_layout.group(1).strip().lower())
                if "dashboard" in layout_raw:
                    hints["layout"] = "dashboard"
                elif "shell" in layout_raw:
                    hints["layout"] = "dashboard"
                elif layout_raw:
                    hints["layout"] = re.sub(r"[^a-z0-9_-]", "", layout_raw.split()[0])

            m_sections = re.search(r"\bsections_order\s*:\s*(.+)$", line, flags=re.IGNORECASE)
            if m_sections:
                raw_sections = m_sections.group(1).strip()
                parts = [seg.strip().strip("`") for seg in re.split(r"\s*->\s*", raw_sections) if seg.strip()]
                sections.extend(parts)
            elif in_layout and re.match(r"^[-*\d]", line):
                section_hint = self._strip_accents(line.lower())
                if "topbar" in section_hint or "header" in section_hint:
                    sections.append("hero")
                elif "sidebar" in section_hint:
                    sections.append("stats")
                elif "dashboard" in section_hint:
                    sections.append("dashboard_widgets")
                elif "table" in section_hint:
                    sections.append("tables")
                elif "form" in section_hint:
                    sections.append("forms")

            if in_modules and line.startswith(("-", "*")):
                backtick_items = re.findall(r"`([^`]+)`", line)
                if backtick_items:
                    candidates = backtick_items
                else:
                    probe = line[1:].strip()
                    candidates = [probe]
                for item in candidates:
                    token = self._normalize_domain_module_candidate(item)
                    if token and token not in modules:
                        modules.append(token)

            mapping_candidate = False
            if in_mapping and line.startswith(("-", "*")):
                mapping_candidate = True
            elif line.startswith(("-", "*")) and ("=>" in line or "->" in line):
                mapping_candidate = True

            if mapping_candidate:
                separator = r"(?:=>|->|:)" if in_mapping else r"(?:=>|->)"
                m_place = re.search(
                    rf"[-*]\s*`?([a-zA-Z0-9_.-]+)`?\s*{separator}\s*`?([a-zA-Z0-9_.-]+)`?",
                    line,
                )
                if m_place:
                    component = m_place.group(1).strip()
                    zone = m_place.group(2).strip()
                    if component and zone:
                        placements[component] = zone

        hints["sections"] = list(dict.fromkeys(sections))
        hints["modules"] = modules[:16]
        hints["placements"] = placements
        return hints

    # Mapping des composants détectés à des zones de layout typiques pour construire un blueprint de montage logique
    def _build_layout_blueprint(
        self,
        image_meta_payload: dict,
        detected_components: list[str],
        domain_modules: list[str],
        mapping_hints: dict | None = None,
    ) -> dict:
        """Construit un blueprint de montage logique (zones + ordre des sections)."""
        structure = image_meta_payload.get("STRUCTURE", {}) if isinstance(image_meta_payload, dict) else {}
        hints = mapping_hints or {}

        mapped_sections = hints.get("sections", []) if isinstance(hints, dict) else []
        raw_sections = mapped_sections or (structure.get("sections", []) if isinstance(structure, dict) else [])
        sections = (
            [str(section).strip() for section in raw_sections if str(section).strip()]
            if isinstance(raw_sections, list)
            else []
        )
        if not sections:
            sections = ["hero", "stats", "dashboard_widgets", "tables", "forms"]
        else:
            baseline_sections = ["hero", "stats", "dashboard_widgets", "tables", "forms"]
            present = {self._normalize_component_name(section) for section in sections}
            for section in baseline_sections:
                if self._normalize_component_name(section) not in present:
                    sections.append(section)
                    present.add(self._normalize_component_name(section))

        module_sections = [f"module_{self._component_filename(module_name)}" for module_name in domain_modules]
        sections_norm = [self._normalize_component_name(section) for section in sections]
        insert_at = 2 if len(sections) >= 2 else len(sections)
        for module_section in module_sections:
            module_norm = self._normalize_component_name(module_section)
            if module_norm in sections_norm:
                continue
            sections.insert(insert_at, module_section)
            sections_norm.insert(insert_at, module_norm)
            insert_at += 1

        placements = {}
        for component in detected_components:
            key = self._normalize_component_name(component)
            module_zone = None
            for module_name in domain_modules:
                module_norm = self._normalize_component_name(module_name)
                if module_norm and module_norm in key:
                    module_zone = f"main.modules.{self._component_filename(module_name)}"
                    break

            if module_zone:
                zone = module_zone
            elif key == "header":
                zone = "shell.topbar"
            elif key == "sidebar":
                zone = "shell.sidebar"
            elif key in {"featurecard", "card"}:
                zone = "main.hero"
            elif key == "statsblock":
                zone = "main.stats"
            elif key == "dashboardwidget":
                zone = "main.dashboard_widgets"
            elif key == "table":
                zone = "main.tables"
            elif key in {"forminput", "button"}:
                zone = "main.forms"
            elif key == "notification":
                zone = "shell.topbar.actions"
            elif key == "badge":
                zone = "main.cards.badges"
            elif key == "modal":
                zone = "overlay.global"
            else:
                zone = "main.shared"
            placements[component] = zone

        mapped_placements = hints.get("placements", {}) if isinstance(hints, dict) else {}
        if isinstance(mapped_placements, dict):
            for component, zone in mapped_placements.items():
                c = str(component).strip()
                z = str(zone).strip()
                if c and z:
                    placements[c] = z

        return {
            "layout": str(
                hints.get("layout")
                or (structure.get("layout", "dashboard") if isinstance(structure, dict) else "dashboard")
            ),
            "source_priority": [#Priorité des sources de vérité pour le mapping layout
                "Constitution/CONSTITUTION.md",
                "Constitution/MappingComponent.md",
                "design/constitution_design.yaml",
                "design/image_meta.json",
            ],
            "domain_modules": domain_modules,
            "modules_from_mapping": hints.get("modules", []) if isinstance(hints, dict) else [],
            "sections": sections,
            "placements": placements,
        }

    def _format_layout_blueprint(self, layout_blueprint: dict) -> str:
        """Formate le blueprint de layout pour injection dans le prompt."""
        sections = layout_blueprint.get("sections", [])
        source_priority = layout_blueprint.get("source_priority", [])
        domain_modules = layout_blueprint.get("domain_modules", [])
        modules_from_mapping = layout_blueprint.get("modules_from_mapping", [])
        sections_order = " -> ".join(str(s) for s in sections) if sections else "(non defini)"
        source_chain = " -> ".join(str(s) for s in source_priority) if source_priority else "(non defini)"
        modules_chain = ", ".join(f"`{module}`" for module in domain_modules) if domain_modules else "(non detectes)"
        mapping_modules_chain = ", ".join(f"`{module}`" for module in modules_from_mapping) if modules_from_mapping else "(non detectes)"
        lines = [
            f"source_priority: {source_chain}",
            f"layout: {layout_blueprint.get('layout', 'dashboard')}",
            f"resolved_domain_modules: {modules_chain}",
            f"domain_modules_from_mapping_component: {mapping_modules_chain}",
            f"sections_order: {sections_order}",
            "component_placements:",
        ]
        placements = layout_blueprint.get("placements", {})
        if placements:
            for component, zone in placements.items():
                lines.append(f"- {component}: {zone}")
        else:
            lines.append("- (aucun composant detecte)")
        return "\n".join(lines)

    def _find_step_ranges_by_suffix(self, lines: list[str], suffixes: list[str]) -> list[tuple[int, int, str]]:
        """Retourne les plages (start, end, step_id) des étapes correspondant à un suffixe d'ID."""
        headers: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("## "):
                continue
            match = re.match(r"^## \[[x ]\]\s+([A-Za-z0-9_]+)", stripped)
            if not match:
                continue
            step_id = match.group(1)
            if any(step_id.endswith(suffix) for suffix in suffixes):
                headers.append((idx, step_id))

        ranges: list[tuple[int, int, str]] = []
        for header_idx, step_id in headers:
            end_idx = len(lines)
            for j in range(header_idx + 1, len(lines)):
                if lines[j].startswith("## "):
                    end_idx = j
                    break
            ranges.append((header_idx, end_idx, step_id))
        return ranges

    def _enforce_frontend_components_step(
        self,
        markdown_steps: str,
        detected_components: list[str],
        layout_blueprint: dict | None = None,
    ) -> str:
        """Garantit que l'étape *_Frontend_Components couvre creation ET montage logique."""
        if not markdown_steps:
            return markdown_steps

        lines = markdown_steps.splitlines()
        step_ranges = self._find_step_ranges_by_suffix(lines, ["Frontend_Components"])
        if not step_ranges:
            return markdown_steps

        blueprint = layout_blueprint or {}
        sections = blueprint.get("sections", []) if isinstance(blueprint, dict) else []
        placements = blueprint.get("placements", {}) if isinstance(blueprint, dict) else {}
        domain_modules = blueprint.get("domain_modules", []) if isinstance(blueprint, dict) else []

        # Traiter de bas en haut pour stabiliser les index en cas d'insertion
        for start_index, end_index, _step_id in sorted(step_ranges, key=lambda item: item[0], reverse=True):
            existing_subtasks = [
                lines[k].strip()
                for k in range(start_index + 1, end_index)
                if lines[k].strip().startswith("- [")
            ]
            existing_text_raw = "\n".join(existing_subtasks).lower()
            existing_text_raw_norm = self._strip_accents(existing_text_raw)
            existing_text_norm = self._normalize_component_name(" ".join(existing_subtasks))

            additions = []
            if "valider le mapping des composants avec `constitution/constitution.md`" not in existing_text_raw_norm:
                additions.append(
                    "- [ ] Valider le mapping des composants avec `Constitution/CONSTITUTION.md` (regles/stack) en source primaire, puis `Constitution/MappingComponent.md` (vision app), puis `design/constitution_design.yaml` et `design/image_meta.json`"
                )

            if "assembler `frontend/src/layouts/applayout.tsx`" not in existing_text_raw_norm:
                additions.append(
                    "- [ ] Assembler `frontend/src/layouts/AppLayout.tsx` avec topbar, sidebar et zone main responsive (desktop/mobile)"
                )

            if sections and "orchestrer `frontend/src/pages/dashboard.tsx` avec l'ordre des sections" not in existing_text_raw_norm:
                sections_chain = " -> ".join(f"`{section}`" for section in sections)
                additions.append(
                    f"- [ ] Orchestrer `frontend/src/pages/Dashboard.tsx` avec l'ordre des sections {sections_chain}"
                )

            if domain_modules:
                modules_chain = ", ".join(f"`{module}`" for module in domain_modules)
                if "aligner les sections metier de `dashboard` sur les modules de `constitution/constitution.md`" not in existing_text_raw_norm:
                    additions.append(
                        f"- [ ] Aligner les sections metier de `Dashboard` sur les modules de `Constitution/CONSTITUTION.md` + `Constitution/MappingComponent.md`: {modules_chain}"
                    )
                for module_name in domain_modules:
                    section_name = f"module_{self._component_filename(module_name)}"
                    module_signature = self._normalize_component_name(f"{section_name}dashboardconstitution")
                    if module_signature not in existing_text_norm:
                        additions.append(
                            f"- [ ] Ajouter la section `{section_name}` dans `frontend/src/pages/Dashboard.tsx` pour le module metier `{module_name}`"
                        )

            for component in detected_components:
                normalized = self._normalize_component_name(component)
                if not normalized:
                    continue

                component_file = f"frontend/src/components/{self._component_filename(component)}.tsx"
                if normalized not in existing_text_norm:
                    additions.append(
                        f"- [ ] Creer `{component_file}` pour le composant {component} selon `Constitution/MappingComponent.md` et le design system (`design/constitution_design.yaml` + `design/image_meta.json`)"
                    )

                zone = str(placements.get(component, "main.shared"))
                placement_signature = self._normalize_component_name(f"{component}{zone}dashboard")
                if placement_signature not in existing_text_norm:
                    additions.append(
                        f"- [ ] Integrer `{component_file}` dans la zone {zone} via `frontend/src/pages/Dashboard.tsx` pour un layout logique"
                    )

            if additions:
                lines = lines[:end_index] + additions + lines[end_index:]

        return "\n".join(lines)

    def _enforce_backend_components_relation(
        self,
        markdown_steps: str,
        domain_modules: list[str],
    ) -> str:
        """Garantit le lien explicite routes/controllers <-> composants front."""
        if not markdown_steps:
            return markdown_steps

        lines = markdown_steps.splitlines()
        step_ranges = self._find_step_ranges_by_suffix(lines, ["Backend_API_Modules", "API_Modules"])
        if not step_ranges:
            return markdown_steps

        for start_index, end_index, _step_id in sorted(step_ranges, key=lambda item: item[0], reverse=True):
            existing_subtasks = [
                lines[k].strip()
                for k in range(start_index + 1, end_index)
                if lines[k].strip().startswith("- [")
            ]
            existing_text_raw = "\n".join(existing_subtasks).lower()
            existing_text_raw_norm = self._strip_accents(existing_text_raw)
            existing_text_norm = self._normalize_component_name(" ".join(existing_subtasks))

            additions = []
            if "relier les routes/controllers backend aux composants frontend de l'etape *_frontend_components" not in existing_text_raw_norm:
                additions.append(
                    "- [ ] Relier les routes/controllers backend aux composants frontend de l'etape `*_Frontend_Components` (contrat endpoint <-> UI)"
                )

            for module_name in domain_modules:
                module_slug = self._component_filename(module_name)
                module_signature = self._normalize_component_name(f"backend{module_slug}routecontrollerfrontend")
                if module_signature in existing_text_norm:
                    continue
                additions.append(
                    f"- [ ] Mapper le module `{module_name}` : `backend/src/routes/{module_slug}.routes.ts` + `backend/src/controllers/{module_slug}.controller.ts` avec la section frontend `module_{module_slug}`"
                )

            if additions:
                lines = lines[:end_index] + additions + lines[end_index:]

        return "\n".join(lines)

    def generate_steps_from_constitution(self, semantic_map: str = "") -> str:
        """Analyse la Constitution pour définir les étapes du projet avec des sous-tâches détaillées."""
        if not self.constitution_path.exists():
            raise FileNotFoundError(
                f"CONSTITUTION.md introuvable : {self.constitution_path}"
            )

        constitution_content = self.constitution_path.read_text(encoding="utf-8")
        existing_plan = ""
        if self.etapes_path.exists():
            existing_plan = self.etapes_path.read_text(encoding="utf-8")
        design_inputs = self._load_design_inputs(constitution_content=constitution_content)
        detected_components = design_inputs["detected_components"]
        domain_modules = design_inputs["domain_modules"]
        mapping_modules = design_inputs["mapping_modules"]
        layout_blueprint = design_inputs["layout_blueprint"]
        detected_components_text = ", ".join(detected_components) if detected_components else "(aucun composant detecte)"
        domain_modules_text = ", ".join(domain_modules) if domain_modules else "(aucun module detecte)"
        mapping_modules_text = ", ".join(mapping_modules) if mapping_modules else "(aucun module detecte)"

        system_prompt = """Tu es un chef de projet DevOps expert. Basé sur la CONSTITUTION fournie, l'état actuel du code (SEMANTIC MAP) et le PLAN EXISTANT,
            découpe le projet en étapes techniques majeures (ex: 01, 02, 03).
            
            Tu DOIS :
            1. Comparer la Constitution avec la SEMANTIC MAP et le PLAN EXISTANT.
            2. Générer la liste COMPLÈTE des étapes nécessaires pour tout le projet (historique inclus).
            3. PRÉSERVER le statut [x] pour toutes les étapes et sous-tâches déjà marquées comme terminées dans le PLAN EXISTANT.
            4. **RÈGLE RÉALITÉ & GOLDEN FILES** : Ne crée JAMAIS de tâche pour configurer un fichier déjà présent dans la SEMANTIC MAP s'il s'agit d'un fichier de structure géré par le framework (`tsconfig.json`, `.spec-lock.json`, `CONSTITUTION.md`). Ils sont marqués [x] dans l'Etape 01 et ne doivent plus apparaître dans les étapes suivantes.
            5. **INTERDICTION D'HALLUCINATION** : Si un fichier (ex: `package.json`, `.eslintrc.js`, `app.ts`) n'est PAS listé dans la SEMANTIC MAP, la tâche qui le concerne DOIT rester en [ ]. Ne suppose jamais qu'un standard est présent.
            6. Marquer [x] une sous-tâche UNIQUEMENT si tu vois la preuve directe de son accomplissement dans la SEMANTIC MAP (ex: le fichier mentionné est présent). 
            7. Découper le reste en étapes atomiques avec des sous-tâches actionnables (src/, routes/, models/).
            8. Utiliser un ordre de verite STRICT pour le mapping layout : `Constitution/CONSTITUTION.md` (source primaire, regles/stack) -> `Constitution/MappingComponent.md` (vision app) -> `design/constitution_design.yaml` -> `design/image_meta.json`.
            9. Pour l'étape `*_Frontend_Components` (ID dynamique, numéro non imposé), générer des sous-tâches orientées composants à partir de DESIGN_INPUTS.detected_components (au moins une sous-tâche par composant détecté, si disponible).
            10. Pour l'étape `*_Frontend_Components` (ID dynamique), ajouter le montage logique (component placement) en t'appuyant sur DESIGN_INPUTS.layout_blueprint (shell + ordre des sections + composant -> zone + modules metier Constitution + vision MappingComponent).
            11. Les étapes backend `*_Backend_API_Modules` / `*_API_Modules` doivent explicitement relier routes/controllers aux composants/pages de l'étape `*_Frontend_Components`.
            
            OBLIGATION DE STRUCTURE :
            Afin de standardiser la qualité des pipelines, tu DOIS inclure (ou adapter) la structure d'étapes suivante pour garantir une architecture de type Web moderne (API + Frontend) complète :
            - 00_Vibe_Design_Extraction : Extraction de l'identité visuelle UNIQUE par IA (Vibe Design Maker)
            - 03_Installation_Dependances_Backend_Core (inclure 'cors', 'dotenv')
            - 04_Installation_Dependances_Frontend_Core (inclure 'axios', 'react-hook-form', 'zod', '@hookform/resolvers', 'zustand')
            - 06_Configuration_Outillage_Qualite (inclure 'cypress' pour E2E)
            - 07_Creation_Structure_Dossiers (inclure backend/src/config, backend/src/tests, frontend/src/api, frontend/src/tests, frontend/src/types)
            - 08_Configuration_Environnement_Backend (inclure CORS_ORIGIN)
            - 09_Initialisation_Serveur_Backend (inclure cors() et express.json())
            - 10_Modelisation_Donnees_MongoDB (Modèles des entités et relations)
            - 11_Backend_Auth_JWT (Routes login/register, middlewares)
            - [ID dynamique]_Backend_API_Modules (Routes et controllers métier liés aux composants/pages frontend)
            - 13_Tests_Backend_API (Tests CRUD/Auth avec Jest et Supertest)
            - 14_Architecture_Frontend (React Router, Zustand, Axios instance)
            - 15_API_LAYER (Connexion Backend via axios)
            - [ID dynamique]_Frontend_Components (sous-tâches détaillées dérivées de DESIGN_INPUTS.detected_components + Auth + Entités métier + Dashboard)
            - 22_Integration_API (Connecter modules Frontend à API)
            - 23_Tests_Frontend (Tests unitaires / intégration Vue/React via Vitest)
            - 24_Test_CORS_Backend & 25_Test_CORS_Frontend (Vérifier cookies JWT/Headers et CORS)
            - 26_E2E_Tests (Cypress, flow complet tel que login et CRUD basique)
            - 27_Performance_Optimisation (Lazy loading, pagination)
            - 28_Securite (Sanitization, XSS, MongoDB protection)
            - 29_Documentation (README backend/frontend, Swagger)
            - 30_Deploiement (Backend, Frontend, MongoDB Atlas)
            - 30_Deploiement (Backend, Frontend, MongoDB Atlas)
            - IMPORTANT : Tu DOIS TOUJOURS inclure l'étape `## [ ] 00_Vibe_Design_Extraction` au tout début si elle n'est pas déjà marquée [x].
              Elle doit contenir ces sous-tâches :
              - [ ] Analyser `Constitution/MappingComponent.md` (vision app, layout cible, mapping composant->zone)
              - [ ] Analyser `design/image_meta.json` (palette, effets, composants detectes, identite visuelle) pour recuperer les signaux de style du design source
              - [ ] Analyser `design/constitution_design.yaml` (principes, layout, couleurs, typo, composants) comme base de system design
              - [ ] Fusionner les informations des sources (CONSTITUTION, MappingComponent, design) et extraire les tokens uniques (couleurs Hex/Tailwind, radius, shadows, spacing, typo) dans `design/tokens.yaml` via le Vibe Design Maker
              - [ ] En cas de conflit, prioriser `Constitution/CONSTITUTION.md` (regles/stack), puis `Constitution/MappingComponent.md` (vision app/layout), puis `design/constitution_design.yaml` (structure design system), puis `design/image_meta.json` (reference visuelle)
            - IMPORTANT : L'étape `## [ ] *_Frontend_Components` (ID dynamique) ne doit pas être sommaire. Elle doit lister les composants détectés dans DESIGN_INPUTS.detected_components (une sous-tâche claire par composant détecté), en plus des composants Auth/entités/dashboard.
            - IMPORTANT : L'étape `## [ ] *_Frontend_Components` (ID dynamique) doit inclure le montage explicite de chaque composant dans un layout logique (ex: topbar, sidebar, hero, stats, tables, forms) avec référence au shell `AppLayout`, à `Dashboard`, et aux modules metier de la Constitution.
            - IMPORTANT : L'étape `## [ ] *_Backend_API_Modules` (ou `*_API_Modules`) doit inclure des sous-tâches de mapping backend->frontend (routes/controllers alignés avec les composants/pages de `*_Frontend_Components`).

            Format de sortie STRICT :
            ## [x] 01_nom_etape : Titre (Préservé car déjà fait)
            - [x] Sous-tâche déjà faite
            
            ## [ ] 02_nom_etape : Titre (Nouvelle étape à faire)
            - [ ] Sous-tâche à réaliser
            
            IMPORTANT : Les IDs d'étape (01_nom_etape) doivent être courts, sans espaces, et utiliser des underscores."""

        user_message = (
            f"CONSTITUTION :\n{constitution_content}\n\n"
            f"SEMANTIC MAP (État du code actuel) :\n{semantic_map}\n\n"
            f"PLAN EXISTANT (etapes.md actuel) :\n{existing_plan}\n\n"
            f"DESIGN INPUTS :\n"
            f"- source_primary: Constitution/CONSTITUTION.md (bloc CONSTITUTION ci-dessus)\n"
            f"- source_secondary: Constitution/MappingComponent.md\n"
            f"- domain_modules_from_constitution: {domain_modules_text}\n\n"
            f"- domain_modules_from_mapping_component: {mapping_modules_text}\n\n"
            f"- detected_components (depuis design/image_meta.json): {detected_components_text}\n\n"
            f"- layout_blueprint (derive de CONSTITUTION + MappingComponent + design):\n{design_inputs['layout_blueprint_text']}\n\n"
            f"- Constitution/MappingComponent.md :\n{design_inputs['mapping_component_raw']}\n\n"
            f"- design/image_meta.json :\n{design_inputs['image_meta_raw']}\n\n"
            f"- design/constitution_design.yaml :\n{design_inputs['constitution_design_raw']}"
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        raw_output = self.model.invoke(messages)
        steps = StrOutputParser().parse(raw_output.content)
        steps = self._enforce_frontend_components_step(steps, detected_components, layout_blueprint)
        steps = self._enforce_backend_components_relation(steps, domain_modules)

        self.etapes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.etapes_path, "w", encoding="utf-8") as f:
            f.write("# ÉTAPES DU PROJET (etapes.md)\n\n")
            f.write("Ce fichier documente la progression détaillée du projet.\n\n")
            f.write(steps)
            f.write(STARTUP_INSTRUCTIONS)

        logger.info("Fichier etapes.md généré avec succès avec un format granulaire.")
        return steps

    def append_steps_from_constitution(self, semantic_map: str = "") -> str:
        """Analyse la Constitution pour ajouter uniquement les nouvelles étapes (Composantes) à la feuille de route."""
        if not self.constitution_path.exists():
            raise FileNotFoundError(f"CONSTITUTION.md introuvable.")

        constitution_content = self.constitution_path.read_text(encoding="utf-8")
        existing_etapes = ""
        if self.etapes_path.exists():
            existing_etapes = self.etapes_path.read_text(encoding="utf-8")
        design_inputs = self._load_design_inputs(constitution_content=constitution_content)
        detected_components = design_inputs["detected_components"]
        domain_modules = design_inputs["domain_modules"]
        mapping_modules = design_inputs["mapping_modules"]
        layout_blueprint = design_inputs["layout_blueprint"]
        detected_components_text = ", ".join(detected_components) if detected_components else "(aucun composant detecte)"
        domain_modules_text = ", ".join(domain_modules) if domain_modules else "(aucun module detecte)"
        mapping_modules_text = ", ".join(mapping_modules) if mapping_modules else "(aucun module detecte)"

        system_prompt = """Tu es un chef de projet DevOps. Ta mission est d'extraire la NOUVELLE fonctionnalité
            ajoutée à la Constitution et de la transformer en une ou plusieurs ÉTAPES TECHNIQUES à la suite du plan existant.
            
            Tu reçois :
            1. La CONSTITUTION amendée.
            2. Le plan d'étapes actuel (etapes.md).
            3. La SEMANTIC MAP (état actuel des fichiers).
            
            Tu DOIS :
            - Identifier ce qui est nouveau dans la Constitution par rapport au plan actuel et au code existant.
            - Créer une ou plusieurs étapes (ex: ## [ ] 04_nouveau_module) si la fonctionnalité est complexe.
            - Ne pas répéter les étapes déjà présentes dans le plan actuel.
            - **RÈGLE RÉALITÉ** : Marquer [x] UNIQUEMENT si le fichier est dans la Semantic Map.
            - Si un fichier n'est pas vu sur le disque, laisse la tâche en [ ].
            - Si la nouveauté concerne le Frontend/UI, utiliser l'ordre de verite suivant : `Constitution/CONSTITUTION.md` (en premier), `Constitution/MappingComponent.md` (en second), puis `design/constitution_design.yaml`, puis `design/image_meta.json`.
            - Si l'étape `*_Frontend_Components` est créée ou complétée (ID dynamique), détailler les sous-tâches à partir de DESIGN_INPUTS.detected_components (une sous-tâche par composant détecté).
            - Pour `*_Frontend_Components` (ID dynamique), inclure le montage logique (component placement) selon DESIGN_INPUTS.layout_blueprint, les modules metier de la Constitution, et la vision de MappingComponent.
            - Si une étape `*_Backend_API_Modules` / `*_API_Modules` est créée ou complétée, inclure explicitement le lien routes/controllers <-> composants/pages frontend.
            - RÉPONDRE UNIQUEMENT AVEC LE BLOC DES NOUVELLES ÉTAPES (format Markdown ## [ ] id : titre)."""

        user_message = (
            f"CONSTITUTION :\n{constitution_content}\n\n"
            f"PLAN ACTUEL :\n{existing_etapes}\n\n"
            f"SEMANTIC MAP :\n{semantic_map}\n\n"
            f"DESIGN INPUTS :\n"
            f"- source_primary: Constitution/CONSTITUTION.md (bloc CONSTITUTION ci-dessus)\n"
            f"- source_secondary: Constitution/MappingComponent.md\n"
            f"- domain_modules_from_constitution: {domain_modules_text}\n\n"
            f"- domain_modules_from_mapping_component: {mapping_modules_text}\n\n"
            f"- detected_components (depuis design/image_meta.json): {detected_components_text}\n\n"
            f"- layout_blueprint (derive de CONSTITUTION + MappingComponent + design):\n{design_inputs['layout_blueprint_text']}\n\n"
            f"- Constitution/MappingComponent.md :\n{design_inputs['mapping_component_raw']}\n\n"
            f"- design/image_meta.json :\n{design_inputs['image_meta_raw']}\n\n"
            f"- design/constitution_design.yaml :\n{design_inputs['constitution_design_raw']}"
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        raw_output = self.model.invoke(messages)
        new_steps = StrOutputParser().parse(raw_output.content)
        new_steps = self._enforce_frontend_components_step(new_steps, detected_components, layout_blueprint)
        new_steps = self._enforce_backend_components_relation(new_steps, domain_modules)

        # Append to etapes.md
        with open(self.etapes_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + new_steps)

        logger.info("Nouvelles étapes ajoutées à etapes.md")
        return new_steps

    def get_next_pending_step(self) -> str | None:
        """Récupère la première étape non cochée [ ] dans etapes.md."""
        if not self.etapes_path.exists():
            return None

        with open(self.etapes_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("## [ ]"):
                    match = re.search(r"## \[ \] (\w+)", line)
                    if match:
                        return match.group(1)
        return None

    def get_all_steps(self) -> list[dict]:
        """Retourne toutes les étapes avec leur statut (done/pending)."""
        if not self.etapes_path.exists():
            return []

        steps = []
        content = self.etapes_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            # Étape majeure : ## [x] 01_setup : Description
            match_done = re.search(r"## \[x\] (\w+)\s*:\s*(.*)", line)
            if match_done:
                steps.append({
                    "id": match_done.group(1),
                    "description": match_done.group(2).strip(),
                    "status": "done",
                })
                continue

            # Étape majeure : ## [ ] 02_api : Description
            match_pending = re.search(r"## \[ \] (\w+)\s*:\s*(.*)", line)
            if match_pending:
                steps.append({
                    "id": match_pending.group(1),
                    "description": match_pending.group(2).strip(),
                    "status": "pending",
                })
        return steps

    def get_progress(self) -> dict:
        """Retourne un résumé de la progression : total, done, pending, pourcentage."""
        steps = self.get_all_steps()
        total = len(steps)
        done = sum(1 for s in steps if s["status"] == "done")
        pending = total - done
        pct = round((done / total) * 100, 1) if total > 0 else 0.0

        return {
            "total": total,
            "done": done,
            "pending": pending,
            "progress_pct": pct,
        }

    def _get_step_regex(self, step_id: str, status_box: str = r"\[.\]") -> str:
        """Crée un regex flexible pour matcher l'ID d'étape avec ou sans zéro initial."""
        step_id = self._normalize_step_id(step_id)
        # Séparer la partie numérique initiale si elle existe (ex: "02_backend" -> "02", "backend")
        match = re.match(r"^(\d+)(_.*)$", step_id)
        if match:
            num, rest = match.groups()
            num_int = int(num)
            # Match ## [ ] 2_... ou ## [ ] 02_... ou ## [ ] 002_...
            return rf"^## {status_box} 0*{num_int}{re.escape(rest)}(?:\s*:|$)"
        else:
            # Match exact si pas de préfixe numérique
            return rf"^## {status_box} {re.escape(step_id)}(?:\s*:|$)"

    def _normalize_step_id(self, step_id: str) -> str:
        """Normalise les IDs d'etape provenant de la CLI (ex: '--00_x' -> '00_x')."""
        cleaned = (step_id or "").strip().strip('"').strip("'")
        return re.sub(r"^--+", "", cleaned)

    def get_subtasks_for_step(self, step_id: str) -> list[str]:
        """Retourne la liste des sous-tâches (texte brut) pour une étape donnée."""
        if not self.etapes_path.exists():
            return []
        
        lines = self.etapes_path.read_text(encoding="utf-8").splitlines()
        subtasks = []
        inside_target = False
        
        # Regex plus stricte mais flexible sur les zéros initiaux
        step_header_pattern = self._get_step_regex(step_id, status_box=r"\[.\]")
        
        for line in lines:
            if re.match(step_header_pattern, line):
                inside_target = True
                continue
            if line.startswith("## ") and inside_target:
                break
            if inside_target and line.strip().startswith("- ["):
                # Extraire le texte de la sous-tâche (sans le checkbox)
                text = re.sub(r'^-\s*\[.\]\s*', '', line.strip())
                # Normalisation garde-fou: package.js -> package.json (manifest npm)
                text = re.sub(r'(?i)\bpackage\.js\b', 'package.json', text)
                if text and text not in subtasks: # Éviter les doublons de lecture
                    subtasks.append(text)
        
        return subtasks

    def _file_exists(self, check_root: Path, path_str: str) -> bool:
        """Vérifie l'existence d'un fichier ou d'un dossier sur le disque."""
        # 1. Chemin direct
        if (check_root / path_str).exists():
            return True
            
        # 2. Normalisation
        clean_path = path_str.lstrip('/').lstrip('\\').replace('\\', '/')
        
        # 3. Test des préfixes standards
        prefixes = ["backend", "backend/src", "frontend", "frontend/src"]
        for prefix in prefixes:
            if clean_path.startswith(prefix + "/"):
                if (check_root / clean_path).exists(): return True
            elif (check_root / prefix / clean_path).exists():
                return True
        
        # 4. Fuzzy match : normaliser le nom de fichier pour gérer les variantes
        #    healthcheck.controller.ts ↔ healthcheckController.ts ↔ health-check.controller.ts
        def normalize_name(name: str) -> str:
            """Normalise un nom de fichier en retirant dots/hyphens/underscores et en lowercase."""
            stem = name.rsplit('.', 1)[0] if '.' in name else name  # Retirer l'extension
            normalized = stem.replace('.', '').replace('-', '').replace('_', '').lower()
            return normalized
        
        # Trouver le dossier parent attendu et vérifier son contenu
        target = Path(clean_path)
        target_normalized = normalize_name(target.name)
        
        # Chercher dans les dossiers candidats
        candidate_dirs = [check_root / target.parent]
        for prefix in prefixes:
            candidate_dirs.append(check_root / prefix / target.parent)
        
        for candidate_dir in candidate_dirs:
            if candidate_dir.exists() and candidate_dir.is_dir():
                for existing_file in candidate_dir.iterdir():
                    if normalize_name(existing_file.name) == target_normalized:
                        return True
        
        return False

    def _dependency_installed(self, check_root: Path, dep_name: str) -> bool:
        """Vérifie si une dépendance NPM est installée (via package.json)."""
        pkg_paths = [
            check_root / "package.json",
            check_root / "backend" / "package.json",
            check_root / "frontend" / "package.json"
        ]
        
        for pkg_path in pkg_paths:
            if pkg_path.exists():
                try:
                    data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if dep_name in dependencies:
                        return True
                except Exception:
                    continue
        return False

    def _script_exists(self, check_root: Path, script_name: str) -> bool:
        """Vérifie si un script npm existe dans le package.json."""
        pkg_paths = [
            check_root / "package.json",
            check_root / "backend" / "package.json",
            check_root / "frontend" / "package.json"
        ]
        
        for pkg_path in pkg_paths:
            if pkg_path.exists():
                try:
                    data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    scripts = data.get("scripts", {})
                    if script_name in scripts:
                        return True
                except Exception:
                    continue
        return False

    def mark_step_as_completed(
        self,
        step_id: str,
        synthesis: str | None = None,
        project_root: str | None = None,
    ) -> tuple[bool, int, int]:
        """Passe une étape majeure de [ ] à [x]. Les sous-tâches sont cochées intelligemment 
        en vérifiant l'existence des fichiers/dossiers mentionnés sur le disque."""
        if not self.etapes_path.exists():
            raise FileNotFoundError(f"etapes.md introuvable : {self.etapes_path}")

        # Déterminer la racine du projet pour la vérification des fichiers
        check_root = Path(project_root) if project_root else self.root

        lines = self.etapes_path.read_text(encoding="utf-8").splitlines()
        updated_lines = []
        inside_target_step = False
        found = False
        checked_count = 0
        total_subtasks = 0
        header_index = -1

        # Regex flexible sur les zéros initiaux
        step_pattern = self._get_step_regex(step_id, status_box=r"\[ \]")

        for line in lines:
            # Si on trouve le header de l'étape cible
            if re.match(step_pattern, line):
                header_index = len(updated_lines)
                updated_lines.append(line)
                inside_target_step = True
                found = True
                continue
            
            # Si on rentre dans une AUTRE étape majeure, on arrête
            if line.startswith("## ") and inside_target_step:
                inside_target_step = False
            
            # Pour les sous-tâches : vérification intelligente sur DISQUE
            if inside_target_step and line.strip().startswith("- [ ]"):
                total_subtasks += 1
                subtask_text = line.strip()
                
                # Patterns : `backend/tsconfig.json` ou `express`
                raw_paths = re.findall(r'`([^`]+)`', subtask_text)
                
                # Filtre universel : toute chaîne commençant par '/' est une URL (ex: /api/articles, /users, /products)
                # Peu importe le domaine du projet (articles, users, orders...) — la règle est générique.
                # On garde : fichiers avec extension valide, noms de packages (sans '/'), dossiers (finissant par '/')
                items_to_check = [
                    p for p in raw_paths
                    if not p.startswith("/") and (is_real_file(p) or "/" not in p or p.endswith('/'))
                ]
                
                if items_to_check:
                    all_ok = True
                    missing_items = []
                    
                    for item in items_to_check:
                        # Skip les glob patterns (src/**/* , *.ts, etc.)
                        if '*' in item:
                            continue
                        
                        # Skip les valeurs de config (CommonJS, ES2022, strict, etc.)
                        config_keywords = {'CommonJS', 'ES2022', 'ES2021', 'ES2020', 'ESNext', 
                                          'strict', 'true', 'false', 'node', 'commonjs',
                                          'dist', 'src', 'rootDir', 'outDir', 'target', 'module',
                                          'include', 'exclude', 'compilerOptions'}
                        if item in config_keywords:
                            continue
                        
                        # Skip les flags CLI (-y, --save, --dev, etc.)
                        if item.startswith('-'):
                            continue
                        
                        # Skip les commandes shell (contiennent des espaces ou commencent par npm/npx)
                        if ' ' in item or item.startswith(('npm ', 'npx ', 'node ', 'yarn ')):
                            # Mapping commande → artefact produit
                            if 'npm init' in item or 'yarn init' in item:
                                if self._file_exists(check_root, 'package.json') or self._file_exists(check_root, 'backend/package.json'):
                                    continue
                            continue
                        
                        # Skip les noms de scripts npm (dev, build, start, test)
                        if item in ('dev', 'build', 'start', 'test'):
                            # Vérifier dans les scripts du package.json
                            if self._script_exists(check_root, item):
                                continue
                            else:
                                all_ok = False
                                missing_items.append(item)
                                continue
                        
                        # Skip les clés JSON de package.json (dependencies, devDependencies, etc.)
                        # Ces keywords ne sont jamais des fichiers ou dépendances à chercher
                        json_config_keywords = {
                            'dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies',
                            'scripts', 'name', 'version', 'type', 'main', 'types', 'exports',
                            'description', 'author', 'license', 'repository', 'bugs', 'homepage',
                            'keywords', 'engines', 'files', 'bin', 'man', 'directories', 'config'
                        }
                        if item in json_config_keywords:
                            continue
                                
                        # Skip les extraits de code JS/TS fréquents (faux positifs pour des fichiers)
                        code_snippets = {
                            'express.json', 'express.urlencoded', 'cors()', 'helmet()', 'morgan()',
                            'NextFunction', 'Request', 'Response', 'app.use', 'connectDB()', 'errorHandler',
                            'CRUD', 'Model', 'Schema', 'z.object', 'z.string'
                        }
                        if item in code_snippets or item.endswith('()'):
                            continue
                            
                        # Skip les "Concepts" PascalCase (ex: `Article`) qui ne sont pas des chemins
                        # (Commence par Majuscule, pas de '/', pas d'extension '.' évidente)
                        if item and item[0].isupper() and '/' not in item and '.' not in item:
                            continue
                        
                        # On vérifie si c'est un fichier OU une dépendance
                        exists_as_file = self._file_exists(check_root, item)
                        exists_as_dep = self._dependency_installed(check_root, item)
                        
                        if not (exists_as_file or exists_as_dep):
                            # --- Directory Enforcer / Auto-Correction ---
                            if item.endswith('/') or item.endswith('\\'):
                                try:
                                    dir_path = check_root / item
                                    dir_path.mkdir(parents=True, exist_ok=True)
                                    (dir_path / ".gitkeep").touch()
                                    logger.info(f"✨ Auto-created missing directory: {item}")
                                    exists_as_file = True # Now it exists
                                except Exception as e:
                                    logger.error(f"❌ Failed to auto-create directory {item}: {e}")
                            
                            if not (exists_as_file or exists_as_dep):
                                all_ok = False
                                missing_items.append(item)
                    
                    if all_ok:
                        updated_lines.append(line.replace("[ ]", "[x]"))
                        checked_count += 1
                        logger.info(f"  ✅ Sous-tâche validée (Disque/Deps) : {subtask_text[:60]}")
                    else:
                        updated_lines.append(line)
                        logger.warning(f"  ❌ Sous-tâche NON validée (Manquant: {missing_items}) : {subtask_text[:60]}")
                else:
                    # Pas d'item spécifique -> Auto-validation par propagation
                    updated_lines.append(line.replace("[ ]", "[x]"))
                    checked_count += 1
            else:
                updated_lines.append(line)

        if not found:
            # Vérifier si déjà complétée avec le regex flexible
            already_done_pattern = self._get_step_regex(step_id, status_box=r"\[x\]")
            if re.search(already_done_pattern, self.etapes_path.read_text(encoding="utf-8"), re.MULTILINE):
                logger.info("Étape '%s' déjà marquée comme terminée.", step_id)
                if synthesis: self.add_step_to_history(step_id, synthesis)
                return True, 0, 0
            logger.warning("Étape '%s' non trouvée.", step_id)
            return False, 0, 0

        if header_index != -1 and checked_count == total_subtasks and total_subtasks > 0:
            updated_lines[header_index] = updated_lines[header_index].replace("[ ]", "[x]")
        elif header_index != -1 and total_subtasks == 0:
            updated_lines[header_index] = updated_lines[header_index].replace("[ ]", "[x]")

        self.etapes_path.write_text("\n".join(updated_lines), encoding="utf-8")
        logger.info(f"Étape '{step_id}' : {checked_count}/{total_subtasks} sous-tâches vérifiées et cochées.")

        if synthesis:
            self.add_step_to_history(step_id, synthesis)

        return True, checked_count, total_subtasks


    def add_step_to_history(self, step_id: str, synthesis: str):
        """Ajoute une étape réalisée avec sa synthèse dans EtapesAdd.md."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            
            header = ""
            if not self.history_path.exists():
                header = "# HISTORIQUE DES ÉTAPES RÉALISÉES (EtapesAdd.md)\\n\\n"
            
            with open(self.history_path, "a", encoding="utf-8") as f:
                if header:
                    f.write(header)
                f.write(f"### ✅ Étape : {step_id}\\n")
                f.write(f"{synthesis}\\n\\n---\\n\\n")
            
            logger.info("Synthèse ajoutée à EtapesAdd.md pour l'étape %s.", step_id)
            
            # Si toutes les étapes sont terminées, ajouter les instructions de démarrage à la fin
            progress = self.get_progress()
            if progress["pending"] == 0:
                 with open(self.history_path, "a", encoding="utf-8") as f:
                     f.write(STARTUP_INSTRUCTIONS)
                 logger.info("Instructions de démarrage ajoutées à la fin de EtapesAdd.md")
        except Exception as e:
            logger.error("Impossible d'écrire l'historique dans EtapesAdd.md : %s", e)
