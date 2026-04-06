import os
import sys
from unittest.mock import MagicMock
from pathlib import Path

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from core.graph import SpecGraphManager
    from core.cli import get_llm
    
    # Mock LLM and project root
    mock_llm = MagicMock()
    mock_root = Path("./test_project")
    mock_root.mkdir(exist_ok=True)
    (mock_root / "design" / "dataset").mkdir(parents=True, exist_ok=True)
    (mock_root / "design" / "constitution_design.yaml").touch()
    
    print("Initializing SpecGraphManager...")
    manager = SpecGraphManager(model=mock_llm, project_root=str(mock_root))
    print("Initialization successful! No AttributeError.")
    
    # Check if helpers are instantiated
    helpers = [
        "project_enhancer", "component_improver", "pattern_vision_detector",
        "design_system_generator", "ux_flow_designer", "constitution_generator"
    ]
    for h in helpers:
        if hasattr(manager, h):
            print(f"Helper '{h}' is instantiated.")
        else:
            print(f"Helper '{h}' is MISSING.")
            
    # Mock state for node tests
    state = {
        "user_instruction": "Create a Pinterest-like dashboard with #FF0000 colors and rounded corners.",
        "target_task": "Dashboard design",
        "pattern_vision": {},
        "component_manifest": {},
        "project_brief": {},
        "design_system": {},
        "ux_flow": {}
    }
    
    print("\nTesting nodes...")
    
    # Test vision_pattern_node
    print("Running vision_pattern_node...")
    res_vision = manager.pattern_vision_node(state)
    state.update(res_vision)
    print(f"   Result style: {state['pattern_vision'].get('style')}")
    print(f"   Primary color extracted: {state['pattern_vision'].get('tokens', {}).get('colors', {}).get('primary')}")
    
    # Test component_improver_node
    print("Running component_improver_node...")
    res_comp = manager.component_improver_node(state)
    state.update(res_comp)
    print(f"   Components found: {len(state['component_manifest'].get('components', []))}")
    
    # Test design_system_node (Checks persistence)
    print("Running design_system_node...")
    res_ds = manager.design_system_node(state)
    state.update(res_ds)
    custom_pattern_path = mock_root / "design" / "dataset" / "custom_pattern.json"
    if custom_pattern_path.exists():
        print(f"custom_pattern.json was PERSISTED at {custom_pattern_path}")
    else:
        print("custom_pattern.json was NOT persisted.")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Verification FAILED: {e}")
finally:
    # Cleanup
    import shutil
    if os.path.exists("./test_project"):
        shutil.rmtree("./test_project")
