#!/usr/bin/env python3
"""Test the design spec formatting function."""

from core.graph import SpecGraphManager
from core.GraphicDesign import GraphicDesign
from pathlib import Path

# Create a manager instance to access _format_design_spec_for_prompt
manager = SpecGraphManager(model=None, project_root=".")

# Test 1: Real design spec from GraphicDesign
print("Test 1: Formatting real design spec from GraphicDesign engine")
print("="*60)
design_engine = GraphicDesign(
    dataset_dir=str(Path(".") / "design" / "dataset"),
    constitution_path=str(Path(".") / "design" / "constitution_design.yaml")
)
real_design = design_engine.generate("create a dashboard with premium design")
formatted = manager._format_design_spec_for_prompt(real_design)
print(formatted)

# Test 2: Empty/error design spec
print("\n\nTest 2: Formatting error/empty design spec")
print("="*60)
error_design = {"error": "No pattern found"}
formatted = manager._format_design_spec_for_prompt(error_design)
print(formatted)

# Test 3: No design spec
print("\n\nTest 3: Formatting None/missing design spec")
print("="*60)
formatted = manager._format_design_spec_for_prompt({})
print(formatted)

print("\n✅ All formatting tests completed!")
