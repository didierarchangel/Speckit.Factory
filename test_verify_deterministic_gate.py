#!/usr/bin/env python3
"""Regression test for deterministic audit success gate."""

from core.graph import SpecGraphManager


def _make_manager() -> SpecGraphManager:
    return object.__new__(SpecGraphManager)


def test_deterministic_gate_approves_green_state() -> None:
    manager = _make_manager()
    ok = manager._is_deterministic_audit_success(
        missing_tasks=0,
        structure_valid=True,
        typescript_status="PASSED",
        has_build_errors=False,
    )
    assert ok is True


def test_deterministic_gate_rejects_when_missing_tasks() -> None:
    manager = _make_manager()
    ok = manager._is_deterministic_audit_success(
        missing_tasks=1,
        structure_valid=True,
        typescript_status="PASSED",
        has_build_errors=False,
    )
    assert ok is False


if __name__ == "__main__":
    test_deterministic_gate_approves_green_state()
    test_deterministic_gate_rejects_when_missing_tasks()
    print("ok")
