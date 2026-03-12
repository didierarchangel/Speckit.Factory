
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock
import json

# Add project root to sys.path
project_root = Path("d:/NEXT_AI/Speckit.Factory")
sys.path.append(str(project_root))

from core.graph import SpecGraphManager
from core.GraphicDesign import GraphicDesign

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dependency_resolver():
    logger.info("🧪 Testing Dependency Resolver (Broad Scan)...")
    
    # Setup mock project structure
    test_root = project_root / "tmp_test_resolver"
    test_root.mkdir(exist_ok=True)
    
    backend_dir = test_root / "backend"
    backend_dir.mkdir(exist_ok=True)
    backend_pkg = backend_dir / "package.json"
    backend_pkg.write_text(json.dumps({
        "dependencies": {
            "express": "^4.18.2"
        }
    }), encoding="utf-8")
    
    frontend_dir = test_root / "frontend"
    frontend_dir.mkdir(exist_ok=True)
    frontend_pkg = frontend_dir / "package.json"
    frontend_pkg.write_text(json.dumps({
        "dependencies": {
            "react": "^18.2.0"
        }
    }), encoding="utf-8")
    
    # Create a backend file that imports express
    backend_src = backend_dir / "src"
    backend_src.mkdir(exist_ok=True)
    app_ts = backend_src / "app.ts"
    app_ts.write_text("import express from 'express';", encoding="utf-8")
    
    # Create a frontend file
    frontend_src = frontend_dir / "src"
    frontend_src.mkdir(exist_ok=True)
    app_tsx = frontend_src / "App.tsx"
    app_tsx.write_text("import React from 'react';", encoding="utf-8")
    
    # Initialize Manager
    gm = SpecGraphManager(model=MagicMock(), project_root=str(test_root))
    
    # State with target_module="frontend"
    state = {
        "target_module": "frontend",
        "missing_modules": [],
        "deps_attempts": 0
    }
    
    # Run the node
    result = gm.dependency_resolver_node(state)
    
    # Verify that it didn't crash and scanned both
    # Note: If express is in package.json AND app.ts, it's NOT missing.
    # Let's remove express from backend/package.json to see if it's detected as missing
    backend_pkg.write_text(json.dumps({"dependencies": {}}), encoding="utf-8")
    
    result = gm.dependency_resolver_node(state)
    
    logger.info(f"Detected missing modules: {result.get('missing_modules')}")
    # It should detect express as missing because it's imported in backend/src/app.ts but not in backend/package.json
    # even though target_module=frontend
    
    assert "express" in result.get("missing_modules", []), "Express should be detected as missing in backend even if target is frontend"
    logger.info("✅ Dependency Resolver broad scan passed!")

def test_graphic_design_fallback():
    logger.info("🧪 Testing GraphicDesign Fallback...")
    
    dataset_dir = project_root / "design" / "dataset"
    constitution_path = project_root / "design" / "constitution_design.yaml"
    
    gd = GraphicDesign(dataset_dir=str(dataset_dir), constitution_path=str(constitution_path))
    
    # We know "hero" has no "premium" patterns. Let's test fallback.
    result = gd.select_pattern(category="hero", preferred_system="premium")
    
    assert result is not None, "Should have selected a pattern even with fallback"
    assert result.get("system") == "standard", "Should have fallen back to standard for hero"
    logger.info(f"✅ GraphicDesign fallback passed! Selected: {result.get('id')}")

if __name__ == "__main__":
    try:
        test_dependency_resolver()
        test_graphic_design_fallback()
        print("\n🏆 ALL EXECUTION TESTS PASSED!")
    except Exception as e:
        logger.error(f"❌ Tests failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(project_root / "tmp_test_resolver", ignore_errors=True)
