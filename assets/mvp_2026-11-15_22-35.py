#!/usr/bin/env python3
"""
Blender AI MCP Core Engine MVP
A standard-library-only implementation of an AI-to-Blender (bpy) translation core.
Supports script generation, syntax validation via AST, and self-test mode.
"""

import argparse
import ast
import json
import sys
from typing import Any, Dict, Tuple


class BlenderMCPBridge:
    """Core engine converting natural language intent into verified Blender bpy scripts."""

    def __init__(self):
        self.version = "1.0.0-mcp"

    def parse_prompt_to_bpy(self, prompt: str) -> str:
        """Parses simple text commands into executable Blender Python (bpy) code."""
        prompt_lower = prompt.lower()
        code_lines = [
            "# Auto-generated code by Blender AI MCP Engine",
            "import bpy",
            "",
            "# Clear existing mesh objects for clean scene",
            "bpy.ops.object.select_all(action='DESELECT')",
            "bpy.ops.object.select_by_type(type='MESH')",
            "bpy.ops.object.delete()",
            "",
        ]

        has_object = False

        if "cube" in prompt_lower or "مكعب" in prompt_lower:
            code_lines.append(
                "bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))"
            )
            has_object = True

        if "sphere" in prompt_lower or "كرة" in prompt_lower:
            code_lines.append(
                "bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(3.0, 0.0, 1.5))"
            )
            has_object = True

        if (
            "light" in prompt_lower
            or "إضاءة" in prompt_lower
            or "ضوء" in prompt_lower
        ):
            code_lines.extend(
                [
                    "bpy.ops.object.light_add(type='SUN', location=(5.0, 5.0, 10.0))",
                    "bpy.context.object.data.energy = 4.0",
                ]
            )

        if "red" in prompt_lower or "أحمر" in prompt_lower:
            code_lines.extend(
                [
                    "mat = bpy.data.materials.new(name='RedMaterial')",
                    "mat.use_nodes = True",
                    "bsdf = mat.node_tree.nodes.get('Principled BSDF')",
                    "if bsdf:",
                    "    bsdf.inputs['Base Color'].default_value = (1.0, 0.05, 0.05, 1.0)",
                    "if bpy.context.active_object:",
                    "    bpy.context.active_object.data.materials.append(mat)",
                ]
            )

        if not has_object:
            # Fallback object if no specific geometry was requested
            code_lines.append(
                "bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.5))"
            )

        return "\n".join(code_lines)

    def validate_script_syntax(self, script_code: str) -> Tuple[bool, str]:
        """Validates python code syntax using standard AST parsing."""
        try:
            ast.parse(script_code)
            return True, "Valid Python/bpy syntax."
        except SyntaxError as err:
            return False, f"Syntax Error: {err}"

    def process_request(self, prompt: str) -> Dict[str, Any]:
        """Processes request and returns structured MCP payload."""
        script = self.parse_prompt_to_bpy(prompt)
        is_valid, validation_msg = self.validate_script_syntax(script)

        return {
            "status": "success" if is_valid else "error",
            "prompt": prompt,
            "generated_bpy_script": script,
            "syntax_validation": validation_msg,
            "engine_version": self.version,
        }


def run_self_test() -> bool:
    """Performs an isolated self-test protocol without modifying system files."""
    print("=== STARTING BLENDER AI MCP SELF-TEST ===")
    bridge = BlenderMCPBridge()

    test_prompt = "Create a red cube with sun light"
    result = bridge.process_request(test_prompt)

    # Assertion 1: Verify output status
    assert (
        result["status"] == "success"
    ), "Test Failed: Response status is not success."
    print("[PASS] MCP Engine returned success status.")

    # Assertion 2: Verify generated logic contains expected bpy operations
    script = result["generated_bpy_script"]
    assert (
        "primitive_cube_add" in script
    ), "Test Failed: Missing cube primitive generation."
    assert "RedMaterial" in script, "Test Failed: Missing material generation."
    print("[PASS] Generated valid Blender (bpy) code logic.")

    # Assertion 3: AST Syntax parsing
    is_valid, msg = bridge.validate_script_syntax(script)
    assert is_valid is True, f"Test Failed: AST validation error: {msg}"
    print("[PASS] AST Python syntax verification passed.")

    print("\n=== SELF-TEST RESULT: ALL TESTS PASSED (100%) ===")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Blender AI MCP Bridge Core Automation Engine"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run self-test suite and output verification results.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="create a red cube and light",
        help="Prompt to convert into Blender Python code.",
    )

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    bridge = BlenderMCPBridge()
    output = bridge.process_request(args.prompt)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
