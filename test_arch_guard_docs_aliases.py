#!/usr/bin/env python3
"""Regression tests for documentation paths and front/back aliases."""

from utils.architecture_guard import ArchitectureGuard


def test_frontend_and_backend_readme_are_allowed() -> None:
    guard = ArchitectureGuard()
    frontend_ok = guard.validate("frontend", ["frontend/README.md"])
    backend_ok = guard.validate("backend", ["backend/README.md"])
    assert frontend_ok == ["frontend/README.md"]
    assert backend_ok == ["backend/README.md"]


def test_alias_front_and_back_are_normalized() -> None:
    guard = ArchitectureGuard()
    # task_type intentionally empty -> auto-detection path
    normalized_front = guard.validate("", ["front/src/api-docs/swagger.yaml"])
    normalized_back = guard.validate("", ["back/src/openapi/swagger.yaml"])
    assert normalized_front == ["frontend/src/api-docs/swagger.yaml"]
    assert normalized_back == ["backend/src/openapi/swagger.yaml"]


if __name__ == "__main__":
    test_frontend_and_backend_readme_are_allowed()
    test_alias_front_and_back_are_normalized()
    print("ok")
