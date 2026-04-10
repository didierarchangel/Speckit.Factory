#!/usr/bin/env python3
"""Tests de non-regression: injection auto des @types React dans package.json."""

import json
import tempfile
from pathlib import Path

from core.graph import SpecGraphManager


def _run_sanitize(pkg_data: dict) -> dict:
    manager = object.__new__(SpecGraphManager)
    with tempfile.TemporaryDirectory() as tmp:
        pkg_path = Path(tmp) / "package.json"
        pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
        manager._sanitize_package_manifest(pkg_path)
        return json.loads(pkg_path.read_text(encoding="utf-8"))


def test_add_types_when_react_present() -> None:
    output = _run_sanitize(
        {
            "name": "frontend",
            "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
            "devDependencies": {},
        }
    )
    dev = output.get("devDependencies", {})
    assert dev.get("@types/react") == "latest"
    assert dev.get("@types/react-dom") == "latest"


def test_move_react_types_from_dependencies_to_devdependencies() -> None:
    output = _run_sanitize(
        {
            "name": "frontend",
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "@types/react": "^18.2.10",
            },
            "devDependencies": {"@types/react-dom": "^18.2.7"},
        }
    )
    deps = output.get("dependencies", {})
    dev = output.get("devDependencies", {})
    assert "@types/react" not in deps
    assert dev.get("@types/react") == "latest"
    assert dev.get("@types/react-dom") == "latest"


def test_react_dom_only_still_forces_both_types() -> None:
    output = _run_sanitize(
        {
            "name": "frontend",
            "dependencies": {"react-dom": "^18.2.0"},
            "devDependencies": {},
        }
    )
    dev = output.get("devDependencies", {})
    assert dev.get("@types/react") == "latest"
    assert dev.get("@types/react-dom") == "latest"


if __name__ == "__main__":
    test_add_types_when_react_present()
    test_move_react_types_from_dependencies_to_devdependencies()
    test_react_dom_only_still_forces_both_types()
    print("OK: React types dependency rule tests passed.")

