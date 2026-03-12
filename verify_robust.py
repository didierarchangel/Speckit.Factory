
import sys
import os
from pathlib import Path
import logging

# Add project root to path
sys.path.append(os.getcwd())

from utils.file_manager import FileManager
from core.graph import SpecGraphManager
from core.etapes import EtapeManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_graph_extract_required_files_robust():
    logger.info("Testing SpecGraphManager._extract_required_files (Robust)...")
    class MockModel:
        def invoke(self, *args, **kwargs): return "mock"
    
    graph = SpecGraphManager(model=MockModel(), project_root="test_project_temp")
    
    # Test with backticks and WITHOUT backticks
    checklist = """
- [ ] Créer `frontend/src/routes/` avec backticks
- [ ] Créer frontend/src/pages/ sans backticks
- [ ] Créer `backend/src/services/auth.ts`
"""
    required = graph._extract_required_files(checklist)
    logger.info(f"Extracted files: {required}")
    
    assert "frontend/src/routes/" in required, "Should extract backticked directory"
    assert "frontend/src/pages/" in required, "Should extract non-backticked directory (standard module)"
    assert "backend/src/services/auth.ts" in required, "Should extract file"
    
    logger.info("✅ SpecGraphManager robust extraction tests passed!")

def test_etapes_auto_repair():
    logger.info("Testing EtapeManager auto-repair of directories...")
    test_root = Path("test_project_temp")
    
    class MockModel:
        def invoke(self, *args, **kwargs): return "mock"
        
    # Simulation of mark_step_as_completed
    em = EtapeManager(model=MockModel(), project_root=test_root)
    
    constitution_dir = test_root / "Constitution"
    constitution_dir.mkdir(parents=True, exist_ok=True)
    
    step_content = """
## [ ] Etape 3 : Config
- [ ] Créer `frontend/src/assets/`
"""
    etapes_file = constitution_dir / "etapes.md"
    etapes_file.write_text(step_content, encoding="utf-8")
    
    # The method we want to test is mark_step_as_completed
    # It takes step_id (str)
    em.mark_step_as_completed("Etape 3 : Config")
    
    # Check if directory was created
    assert (test_root / "frontend/src/assets").is_dir(), "Directory should have been auto-created"
    assert (test_root / "frontend/src/assets/.gitkeep").exists(), "Gitkeep should have been created"
    
    # Check if etapes.md was updated
    updated_content = etapes_file.read_text(encoding="utf-8")
    assert "[x] Créer `frontend/src/assets/`" in updated_content, "Checklist should be marked as done"
    
    logger.info("✅ EtapeManager auto-repair tests passed!")

if __name__ == "__main__":
    if Path("test_project_temp").exists():
        import shutil
        shutil.rmtree("test_project_temp")
    os.makedirs("test_project_temp")
    
    try:
        test_graph_extract_required_files_robust()
        test_etapes_auto_repair()
        logger.info("\n🏆 ALL ROBUST TESTS PASSED!")
    finally:
        if Path("test_project_temp").exists():
            import shutil
            shutil.rmtree("test_project_temp")
