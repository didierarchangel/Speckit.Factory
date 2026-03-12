#!/usr/bin/env python3
"""Test GraphicDesign engine to verify it outputs design specs."""

import json
from pathlib import Path
from core.GraphicDesign import GraphicDesign

def test_graphic_design():
    try:
        # Initialize
        root = Path(".")
        design_engine = GraphicDesign(
            dataset_dir=str(root / "design" / "dataset"),
            constitution_path=str(root / "design" / "constitution_design.yaml")
        )
        print("✅ GraphicDesign initialized")
        
        # Test 1: Dashboard with premium
        print("\n" + "="*60)
        print("TEST 1: Dashboard with premium design")
        print("="*60)
        result = design_engine.generate("create a dashboard with premium design")
        
        if "error" in result:
            print(f"❌ ERROR: {result['error']}")
        else:
            print(f"✅ Success!")
            print(f"   Pattern ID: {result.get('pattern', 'N/A')}")
            tailwind = result.get('tailwind', {})
            print(f"   Tailwind classes: {json.dumps(tailwind, indent=6)}")
            ui_ast = result.get('ui_ast', {})
            print(f"   UI AST: {str(ui_ast)[:200]}")
        
        # Test 2: Form
        print("\n" + "="*60)
        print("TEST 2: Form design")
        print("="*60)
        result = design_engine.generate("create a registration form")
        print(f"   Pattern ID: {result.get('pattern', 'N/A')}")
        print(f"   Tailwind: {list(result.get('tailwind', {}).keys())}")
        
        # Test 3: Standard (no keyword)
        print("\n" + "="*60)
        print("TEST 3: Standard design (no premium keyword)")
        print("="*60)
        result = design_engine.generate("create a button")
        print(f"   Pattern ID: {result.get('pattern', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_graphic_design()
