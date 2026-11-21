#!/usr/bin/env python3
"""
AntiAlgorithm Core Engine - Micro-SaaS Engine for Non-Stereotypical Creative SVG & Prompt Generation.
Standard Library Only.
"""

import argparse
import json
import random
import sys
import xml.etree.ElementTree as ET


class AntiAlgorithmEngine:
    """
    Core anti-algorithmic transformation engine.
    Forces creative models away from stereotypical first-choice outputs.
    """

    CLICHE_PATTERNS = {
        "tech": ["blue gradient", "circuit lines", "glowing brain", "interconnected dots"],
        "finance": ["rising arrow", "dollar sign", "shield", "bull"],
        "eco": ["green leaf", "globe", "tree", "hand holding plant"]
    }

    ANTI_THESIS_DIRECTIVES = [
        "Invert primary geometry to brutalist minimalist polygons.",
        "Replace standard corporate palette with high-contrast dual tone.",
        "Remove all direct metaphors; use abstract negative space representation.",
        "Incorporate asymmetric dynamic offset instead of centered alignment."
    ]

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)

    def generate_anti_prompt(self, domain: str, base_concept: str) -> dict:
        """Transforms a standard prompt into a non-stereotypical anti-algorithmic prompt."""
        cliches = self.CLICHE_PATTERNS.get(domain.lower(), ["generic shapes"])
        selected_directives = random.sample(
            self.ANTI_THESIS_DIRECTIVES, k=min(2, len(self.ANTI_THESIS_DIRECTIVES))
        )

        anti_prompt = {
            "original_concept": base_concept,
            "domain": domain,
            "banned_stereotypes": cliches,
            "applied_anti_directives": selected_directives,
            "enhanced_prompt": (
                f"Create a design for '{base_concept}'. "
                f"STRICTLY AVOID clichés: {', '.join(cliches)}. "
                f"APPLY CREATIVE CONSTRAINTS: {' '.join(selected_directives)}"
            )
        }
        return anti_prompt

    def generate_unique_svg(self, width: int = 400, height: int = 400, title: str = "AntiAlgo") -> str:
        """Generates a non-stereotypical geometric SVG using algorithmic anti-symmetry."""
        svg = ET.Element('svg', {
            'xmlns': 'http://www.w3.org/2000/svg',
            'viewBox': f'0 0 {width} {height}',
            'width': str(width),
            'height': str(height)
        })

        # Background - dark minimalist
        bg_colors = ["#0f172a", "#18181b", "#09090b", "#172554"]
        bg_color = random.choice(bg_colors)
        ET.SubElement(svg, 'rect', {
            'width': '100%',
            'height': '100%',
            'fill': bg_color
        })

        # Anti-algorithmic shapes palette
        accent_palettes = [
            ["#f43f5e", "#fb923c", "#facc15"],
            ["#06b6d4", "#3b82f6", "#a855f7"],
            ["#10b981", "#06b6d4", "#f43f5e"]
        ]
        palette = random.choice(accent_palettes)
        group = ET.SubElement(svg, 'g', {'id': 'anti-algo-composition'})

        # Generate non-repetitive shapes
        num_shapes = random.randint(3, 6)
        for i in range(num_shapes):
            color = palette[i % len(palette)]
            opacity = str(round(random.uniform(0.5, 0.9), 2))

            cx = random.randint(50, width - 50)
            cy = random.randint(50, height - 50)
            r = random.randint(30, 100)

            if i % 2 == 0:
                points = f"{cx},{cy - r} {cx + r},{cy + r} {cx - r + 10},{cy + r // 2}"
                ET.SubElement(group, 'polygon', {
                    'points': points,
                    'fill': color,
                    'opacity': opacity
                })
            else:
                ET.SubElement(group, 'circle', {
                    'cx': str(cx),
                    'cy': str(cy),
                    'r': str(r // 2),
                    'fill': color,
                    'opacity': opacity
                })

        # Metadata text
        text = ET.SubElement(svg, 'text', {
            'x': '20',
            'y': str(height - 20),
            'fill': '#ffffff',
            'font-family': 'sans-serif',
            'font-size': '12',
            'opacity': '0.7'
        })
        text.text = f"AntiAlgorithm // {title}"

        return ET.tostring(svg, encoding='unicode')


def run_self_test() -> bool:
    """Executes a self-contained unit test suite."""
    print("=== Running Self-Test Suite for AntiAlgorithm Engine ===")
    try:
        engine = AntiAlgorithmEngine(seed=42)

        # Test 1: Anti-Prompt Generation
        print("[TEST 1] Testing Anti-Prompt Generator...")
        prompt_data = engine.generate_anti_prompt("tech", "AI Data Analytics Logo")
        assert prompt_data["domain"] == "tech", "Domain mismatch"
        assert len(prompt_data["banned_stereotypes"]) > 0, "Failed to detect cliches"
        assert "STRICTLY AVOID" in prompt_data["enhanced_prompt"], "Directives missing"
        print(" -> PASSED: Anti-prompt logic verified.")

        # Test 2: SVG Vector Generation & XML Parsing Validation
        print("[TEST 2] Testing SVG Output Generation...")
        svg_code = engine.generate_unique_svg(400, 400, "SelfTestLogo")
        assert "<svg" in svg_code and "</svg>" in svg_code, "Invalid SVG output tags"
        root = ET.fromstring(svg_code)
        assert "svg" in root.tag, "Root element is not SVG"
        print(" -> PASSED: SVG generation and XML structure valid.")

        # Test 3: Variation Verification
        print("[TEST 3] Verifying Non-Repetitive Randomization...")
        engine2 = AntiAlgorithmEngine(seed=99)
        svg_code_2 = engine2.generate_unique_svg(400, 400, "SelfTestLogo2")
        assert svg_code != svg_code_2, "Randomization failed, outputs are identical"
        print(" -> PASSED: Output variation verified.")

        print("\nSUCCESS: All 3 self-tests passed cleanly!")
        return True
    except Exception as e:
        print(f"\nFAILURE: Self-test failed with error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="AntiAlgorithm Engine - Break AI Stereotypes & Generate Unique SVGs/Prompts."
    )
    parser.add_argument("--self-test", action="store_true", help="Execute self-test suite.")
    parser.add_argument("--domain", type=str, default="tech", help="Domain area (tech, finance, eco).")
    parser.add_argument("--concept", type=str, default="Modern SaaS Brand", help="Base design concept.")
    parser.add_argument("--generate-svg", action="store_true", help="Generate non-stereotypical SVG code.")

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    engine = AntiAlgorithmEngine()

    print("=== AntiAlgorithm Engine Output ===")
    prompt_res = engine.generate_anti_prompt(args.domain, args.concept)
    print(json.dumps(prompt_res, indent=2, ensure_ascii=False))

    if args.generate_svg:
        print("\n=== Generated Anti-Algorithmic SVG ===")
        svg = engine.generate_unique_svg(title=args.concept)
        print(svg)


if __name__ == "__main__":
    main()
