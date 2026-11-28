#!/usr/bin/env python3
"""
AI Guardrail Middleware - MVP (Pure Python Standard Library)
Filters LLM inputs/outputs to prevent dangerous commitments, financial promises, 
or unauthorized policy overrides (e.g., rent delays, unauthorized discounts).
"""

import sys
import json
import re

class AIGuardrailMiddleware:
    def __init__(self):
        # قائمة الحظر والعبارات الخطرة التي يمنع على الذكاء الاصطناعي الوعد بها
        self.forbidden_patterns = [
            r"delay.*rent",
            r"extend.*deadline",
            r"discount.*%",
            r"guarantee.*refund",
            r"waive.*fee",
            r"approved.*automatically"
        ]

    def inspect_output(self, response_text: str) -> dict:
        """يفحص استجابة الذكاء الاصطناعي قبل وصولها للمستخدم النهائي لمنع الوعود غير القانونية."""
        matched_threats = []
        for pattern in self.forbidden_patterns:
            if re.search(pattern, response_text, re.IGNORECASE):
                matched_threats.append(pattern)

        if matched_threats:
            return {
                "status": "BLOCKED",
                "reason": "AI attempted unauthorized commitment or policy violation.",
                "detected_patterns": matched_threats,
                "safe_fallback": "I'm sorry, but I don't have the authority to approve financial or policy changes. Please consult management."
            }
        
        return {
            "status": "APPROVED",
            "clean_response": response_text
        }

def run_self_test():
    """تنفيذ اختبار ذاتي حقيقي للتحقق من كفاءة أداة الحوكمة دون تعديل النظام."""
    print("--- [AI Guardrail Middleware] Starting Self-Test ---")
    guardrail = AIGuardrailMiddleware()

    test_cases = [
        "Yes, you can delay your rent payment until next month without penalties.", # يجب أن تحظر
        "Hello! How can I help you find a property today?",                        # يجب أن تمرر بأمان
        "We can waive the late fee and offer a 20% discount on your lease."       # يجب أن تحظر
    ]

    failed = 0
    for i, test in enumerate(test_cases, 1):
        result = guardrail.inspect_output(test)
        print(f"\nTest Case {i}: '{test}'")
        print(f"Result Status: {result['status']}")
        
        if result['status'] == "BLOCKED" and "delay" in test.lower():
            print("-> PASS (Correctly blocked dangerous promise)")
        elif result['status'] == "APPROVED" and "help" in test.lower():
            print("-> PASS (Correctly allowed safe message)")
        elif result['status'] == "BLOCKED" and "waive" in test.lower():
            print("-> PASS (Correctly blocked financial waiver)")
        else:
            print("-> FAIL")
            failed += 1

    print("\n---------------------------------------------------")
    if failed == 0:
        print("Self-Test Status: SUCCESS. All guardrail checks passed perfectly.")
        sys.exit(0)
    else:
        print(f"Self-Test Status: FAILED ({failed} tests failed).")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        run_self_test()
    else:
        print("Usage: python3 script.py --self-test")
        sys.exit(0)
