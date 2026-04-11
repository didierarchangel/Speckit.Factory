#!/usr/bin/env python3
"""Regression test: ArchitectureGuard node strips cross-module file blocks."""

from core.graph import SpecGraphManager
from utils.architecture_guard import ArchitectureGuard


def _make_manager() -> SpecGraphManager:
    manager = object.__new__(SpecGraphManager)
    manager.arch_guard = ArchitectureGuard()
    return manager


def test_frontend_arch_guard_strips_backend_blocks() -> None:
    manager = _make_manager()
    code = """// Fichier : backend/src/middleware/cors.middleware.js
export const corsMiddleware = () => {}

// Fichier : frontend/src/tests/cors.test.ts
export const testCors = () => true
"""
    state = {
        "target_module": "frontend",
        "code_to_verify": code,
        "impact_fichiers": [],
        "arch_guard_last_error": "",
        "arch_guard_same_error_count": 0,
    }
    result = manager.architecture_guard_node(state)  # type: ignore[arg-type]
    assert result["arch_guard_status"] == "PASSED"
    assert "backend/src/middleware/cors.middleware.js" not in result["impact_fichiers"]
    assert "frontend/src/tests/cors.test.ts" in result["impact_fichiers"]


if __name__ == "__main__":
    test_frontend_arch_guard_strips_backend_blocks()
    print("ok")
