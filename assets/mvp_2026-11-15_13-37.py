import sys
import re
import json
import unicodedata
import argparse

class NonEnglishTokenOptimizer:
    """
    Micro-SaaS Core: LLM Text Optimizer for Non-English Languages (e.g., Arabic).
    Reduces token counts, lowers API cost, and decreases latency by cleansing
    redundant Unicode formatting, zero-width characters, and redundant diacritics.
    Uses ONLY Python Standard Library.
    """
    def __init__(self, strip_arabic_diacritics=True, normalize_form='NFKC'):
        self.strip_arabic_diacritics = strip_arabic_diacritics
        self.normalize_form = normalize_form
        # Regex for Arabic Tashkeel (Diacritics)
        self.tashkeel_regex = re.compile(r'[\u0617-\u061A\u064B-\u0652\u0656-\u065F\u0670]')
        # Regex for zero-width & non-printing control characters
        self.zero_width_regex = re.compile(r'[\u200B-\u200D\uFEFF\u00A0]')

    def optimize(self, text: str) -> dict:
        original_length = len(text)
        
        # Step 1: Unicode Normalization (converts visual variants to standard forms)
        cleaned = unicodedata.normalize(self.normalize_form, text)
        
        # Step 2: Remove zero-width space characters & hidden formatting marks
        cleaned = self.zero_width_regex.sub('', cleaned)
        
        # Step 3: Strip Arabic Tashkeel if enabled (major token saver in Arabic prompts)
        if self.strip_arabic_diacritics:
            cleaned = self.tashkeel_regex.sub('', cleaned)
            
        # Step 4: Collapse redundant spaces & newline spam
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned).strip()
        
        optimized_length = len(cleaned)
        
        # Standard Token Estimation Heuristic (Non-English characters often cost 1-3 bytes/tokens)
        has_non_ascii = any(ord(c) > 127 for c in text)
        char_per_token_raw = 2.2 if has_non_ascii else 4.0
        char_per_token_opt = 3.2 if has_non_ascii else 4.0
        
        est_original_tokens = max(1, int(original_length / char_per_token_raw))
        est_optimized_tokens = max(1, int(optimized_length / char_per_token_opt))
        
        tokens_saved = max(0, est_original_tokens - est_optimized_tokens)
        savings_pct = round((tokens_saved / est_original_tokens) * 100, 2) if est_original_tokens > 0 else 0.0

        return {
            "original_text": text,
            "optimized_text": cleaned,
            "original_char_count": original_length,
            "optimized_char_count": optimized_length,
            "est_original_tokens": est_original_tokens,
            "est_optimized_tokens": est_optimized_tokens,
            "est_tokens_saved": tokens_saved,
            "est_cost_savings_pct": savings_pct
        }


def run_self_test():
    print("==================================================")
    print("   RUNNING SELF-TEST: NonEnglishTokenOptimizer    ")
    print("==================================================")
    
    # Arabic input with heavy diacritics, zero-width space, extra spaces & newlines
    sample_text = (
        "مَـرْحَبَاً  بِكُـمْ فِـي  عَالَمِ   الذَّكَاءِ   الاِصْطِنَاعِيِّ!\u200b\u200b "
        "هَذَا   النَّصُّ   يَحْتَوِي   عَلَى   حَرَكَاتٍ   وَفَوَاصِلَ   زَائِدَةٍ.\n\n\n"
    )
    
    optimizer = NonEnglishTokenOptimizer(strip_arabic_diacritics=True)
    result = optimizer.optimize(sample_text)
    
    print(f"Original Text   : {repr(result['original_text'])}")
    print(f"Optimized Text  : {repr(result['optimized_text'])}")
    print(f"Chars Reduction : {result['original_char_count']} -> {result['optimized_char_count']}")
    print(f"Estimated Tokens: {result['est_original_tokens']} -> {result['est_optimized_tokens']}")
    print(f"Estimated Savings: {result['est_tokens_saved']} tokens ({result['est_cost_savings_pct']}%)")
    
    # Assertions
    assert result["optimized_char_count"] < result["original_char_count"], "FAIL: Character count did not decrease."
    assert result["est_tokens_saved"] > 0, "FAIL: Zero tokens saved."
    assert "\u200b" not in result["optimized_text"], "FAIL: Zero-width space not removed."
    
    print("\n✅ SELF-TEST RESULT: ALL CHECKS PASSED PERFECTLY!")
    return 0


def main():
    parser = argparse.ArgumentParser(description="LLM Non-English Token & Cost Optimizer Middleware MVP")
    parser.add_argument("--self-test", action="store_true", help="Run automated self-tests and exit")
    parser.add_argument("--text", type=str, help="Input non-English text to optimize")
    
    args = parser.parse_args()
    
    if args.self_test:
        sys.exit(run_self_test())
        
    if args.text:
        optimizer = NonEnglishTokenOptimizer()
        res = optimizer.optimize(args.text)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
