#!/usr/bin/env python3
"""Regression test: architecture_guard_node conditional mapping includes verify_node."""

from pathlib import Path


def test_arch_guard_conditional_edges_include_verify_node() -> None:
    graph_path = Path(__file__).parent / "core" / "graph.py"
    content = graph_path.read_text(encoding="utf-8")
    assert '"verify_node": "verify_node"' in content


if __name__ == "__main__":
    test_arch_guard_conditional_edges_include_verify_node()
    print("ok")
