#!/usr/bin/env python3
"""Test script to verify impl_node works correctly."""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_impl_node")

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from core.graph import SpecGraphManager
from langchain_google_genai import ChatGoogleGenerativeAI

def test_impl_node():
    """Test that impl_node executes successfully."""
    logger.info("Starting test_impl_node...")
    
    # Initialize
    api_key = "AIzaSyDMf3P_X1FOoHBkERkRJjYiK-KxdQQym4Q"
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
    
    graph_mgr = SpecGraphManager(model, project_root=".")
    
    # Load constitution from file if exists, otherwise use dummy
    const_file = Path("Constitution/CONSTITUTION.md")
    if const_file.exists():
        constitution = const_file.read_text(encoding="utf-8")
    else:
        constitution = "# Default Constitution (test)"
    
    # Create minimal state
    state = {
        "target_task": "02_backend_setup",
        "current_step": "02",
        "constitution_content": constitution,
        "constitution_hash": "test_hash",
        "completed_tasks_summary": "Step 01 completed",
        "pending_tasks": "Step 02, 03, 04",
        "analysis_output": "Backend setup required",
        "feedback_correction": "",
        "terminal_diagnostics": "",
        "code_map": "{}",
        "file_tree": "backend/\nbackend/src/\nbackend/package.json",
        "design_spec": {"error": "Skipped (non-UI)"},
        "subtask_checklist": "- [ ] Setup",
        "user_instruction": "",
        "existing_code_snapshot": "",
        "validation_status": "PENDING",
        "error_count": 0,
        "retry_count": 0,
        "last_error": ""
    }
    
    # Test impl_node
    try:
        logger.info("Calling impl_node...")
        result = graph_mgr.impl_node(state)
        
        if "error" in str(result).lower() or "exception" in str(result).lower():
            logger.error(f"impl_node returned error: {result}")
            return False
        
        logger.info(f"impl_node succeeded! Generated {len(result.get('code_to_verify', ''))} chars of code")
        return True
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during test: {error_msg[:200]}")
        return False

if __name__ == "__main__":
    success = test_impl_node()
    sys.exit(0 if success else 1)
