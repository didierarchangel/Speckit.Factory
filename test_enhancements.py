#!/usr/bin/env python3
"""Test script for Phase 5 enhancements"""

import sys
import logging
from pathlib import Path
from utils.file_manager import FileManager

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_enhancements():
    """Test all Phase 5 enhancements"""
    
    root = Path(__file__).parent
    fm = FileManager(str(root))
    
    print("\n" + "="*70)
    print("🧪 TESTING PHASE 5 ENHANCEMENTS")
    print("="*70 + "\n")
    
    # TEST 1: Path normalization and security
    print("TEST 1: Path Normalization & Security")
    print("-" * 70)
    
    test_paths = [
        ("src/components/Button.tsx", "frontend/src/components/Button.tsx"),
        ("components/Card.tsx", "frontend/src/components/Card.tsx"),
        ("services/api.ts", "frontend/src/services/api.ts"),
        ("controllers/auth.ts", "backend/src/controllers/auth.ts"),
        ("LoginForm.tsx", "frontend/src/components/LoginForm.tsx"),  # Heuristic detection
    ]
    
    for input_path, expected_output in test_paths:
        try:
            result = fm.normalize_path(input_path)
            status = "✅" if result == expected_output else "⚠️"
            print(f"{status} {input_path:40} → {result}")
            if result != expected_output:
                print(f"   Expected: {expected_output}")
        except Exception as e:
            print(f"❌ {input_path:40} → ERROR: {e}")
    
    # TEST 2: Unsafe path detection
    print("\nTEST 2: Unsafe Path Detection")
    print("-" * 70)
    
    unsafe_paths = [
        "../../../etc/passwd",
        "../../src/sensitive.ts",
        "/abs/path/file.ts",
        "C:\\Windows\\System32\\file.ts",
    ]
    
    for unsafe_path in unsafe_paths:
        try:
            result = fm.normalize_path(unsafe_path)
            print(f"❌ {unsafe_path:40} → SHOULD HAVE FAILED: {result}")
        except ValueError as e:
            print(f"✅ {unsafe_path:40} → BLOCKED")
    
    # TEST 3: Framework detection
    print("\nTEST 3: Framework Detection")
    print("-" * 70)
    
    framework = fm.detect_framework()
    print(f"Detected framework: {framework}")
    
    config = fm.get_framework_config(framework)
    print(f"Framework config keys: {list(config.keys())}")
    print(f"Build command: {config.get('build_command', 'N/A')}")
    print(f"Validation command: {config.get('validation_command', 'N/A')}")
    
    # TEST 4: Snapshot and diff tracking
    print("\nTEST 4: Project Snapshot & Diff Tracking")
    print("-" * 70)
    
    snap1 = fm.snapshot_project_state("test_before")
    print(f"📸 Snapshot 1: {snap1['file_count']} files, {snap1['total_size']} bytes")
    print(f"   Sample files: {list(snap1['files'].keys())[:3]}")
    
    snap2 = fm.snapshot_project_state("test_after")
    print(f"📸 Snapshot 2: {snap2['file_count']} files, {snap2['total_size']} bytes")
    
    diff = fm.diff_snapshots(snap1, snap2)
    print(f"📊 Diff: {diff['summary']}")
    
    # TEST 5: FRAMEWORK MAP
    print("\nTEST 5: Framework Mapping Table")
    print("-" * 70)
    
    for fw_name in ["react_vite", "nextjs", "vuejs", "django"]:
        fw_config = fm.FRAMEWORK_MAP.get(fw_name)
        if fw_config:
            print(f"\n{fw_name}:")
            print(f"  Modules: {fw_config.get('modules')}")
            print(f"  Extensions: {fw_config.get('extensions')}")
            print(f"  Build: {fw_config.get('build_command')}")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_enhancements()
