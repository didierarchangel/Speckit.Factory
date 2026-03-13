import re
from pathlib import Path

def test_extension_fix(required_file):
    # Simuler la logique implémentée dans _ensure_required_artifacts
    if '.' not in required_file.split('/')[-1] and not required_file.endswith('/'):
        if "backend/src" in required_file or "frontend/src" in required_file:
            required_file += ".ts"
    return required_file

def test_guard_extraction(code):
    # Simuler la logique implémentée dans architecture_guard_node
    file_pattern = r'(?m)^(?://|#)\s*(?:\[DEBUT_FICHIER:\s*|Fichier\s*:\s*|File\s*:\s*)([a-zA-Z0-9._\-/\\ ]+\.[a-zA-Z0-9]+)\]?.*$'
    extracted_paths = re.findall(file_pattern, code)
    return extracted_paths

# Test 1: Extensions
print("Testing Extension Fix:")
print(f"user.service -> {test_extension_fix('backend/src/services/user.service')}")
print(f"medication.service -> {test_extension_fix('backend/src/services/medication.service')}")
print(f"HomeView -> {test_extension_fix('frontend/src/views/HomeView')}")
print(f"package.json (keep) -> {test_extension_fix('backend/package.json')}")

# Test 2: Guard Extraction
code_sample = """
// Fichier : backend/src/app.ts
console.log("hello");

# File : backend/src/controllers/user.controller.ts
export class UserController {}

// [DEBUT_FICHIER: backend/unauthorized.ts]
MALICIOUS CODE
"""
print("\nTesting Guard Extraction:")
extracted = test_guard_extraction(code_sample)
print(f"Extracted paths: {extracted}")
if "backend/unauthorized.ts" in extracted:
    print("SUCCESS: Hidden file detected!")
else:
    print("FAILURE: Hidden file missed!")
