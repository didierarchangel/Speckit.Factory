#!/usr/bin/env python3
"""Test that placeholders are correctly replaced without ChatPromptTemplate."""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_placeholders")

def test_placeholder_replacement():
    """Verify that placeholders can be replaced without ChatPromptTemplate errors."""
    logger.info("Testing placeholder replacement logic...")
    
    # Simulate a prompt with code containing curly braces (like TypeScript)
    mock_prompt = """
    You are a code generator.
    
    Here are some TypeScript examples:
    
    // Example 1: Import with braces
    import {{ getUser }} from "./users";
    import {{ z }} from "zod";
    
    // Example 2: Type definition
    export interface User {{
      id: string;
      name: string;
    }}
    
    // Example 3: Function
    const handler = (req: Request, res: Response) => {{
      const user = {{ getUser }}(req.user.id);
      return res.json(user);
    }};
    
    Now apply the following context:
    Constitution: {{constitution_content}}
    Task: {{target_task}}
    Code map: {{code_map}}
    """
    
    # Test data to inject
    inject_dict = {
        "constitution_content": "# My Constitution Rules",
        "target_task": "02_backend_setup",
        "code_map": "{\"backend/app.ts\": \"...\"}"
    }
    
    # Replace placeholders
    modified_prompt = mock_prompt
    for key, value in inject_dict.items():
        placeholder = "{" + key + "}"
        modified_prompt = modified_prompt.replace(placeholder, str(value))
    
    logger.info("Original prompt size: %d chars", len(mock_prompt))
    logger.info("Modified prompt size: %d chars", len(modified_prompt))
    
    # Verify replacements
    checks = [
        ("Double braces preserved", "{{ getUser }}" in modified_prompt),
        ("TypeScript braces preserved", "{ id: string;" in modified_prompt),
        ("Constitution replaced", "# My Constitution Rules" in modified_prompt),
        ("Target task replaced", "02_backend_setup" in modified_prompt),
    ]
    
    all_pass = True
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {check_name}")
        if not result:
            all_pass = False
    
    if all_pass:
        logger.info("\n✅ All placeholder replacement tests passed!")
        logger.info("   → Code with {{ }} and {{ }} are preserved")
        logger.info("   → Only {variable_name} patterns are replaced")
        return True
    else:
        logger.error("\n❌ Some tests failed")
        logger.error("Modified prompt:\n%s", modified_prompt[:500])
        return False

if __name__ == "__main__":
    import sys
    success = test_placeholder_replacement()
    sys.exit(0 if success else 1)
