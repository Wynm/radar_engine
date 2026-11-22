import argparse
import json
import sys
from typing import Dict, List


class WaterFillCompressor:
    """برمجية وسيطة لضغط سجلات ومخرجات النظام قبل إرسالها للنموذج اللغوي

    تعتمد على خوارزمية Water-Fill توزيع الميزانية بالتساوي وتخصيص الفائض
    للمصادر الأكبر.
    """

    def __init__(self, max_char_budget: int = 500):
        self.max_char_budget = max_char_budget

    def compress(self, log_streams: Dict[str, List[str]]) -> Dict[str, str]:
        if not log_streams:
            return {}

        sources = list(log_streams.keys())
        full_texts = {src: "\n".join(log_streams[src]) for src in sources}
        needs = {src: len(full_texts[src]) for src in sources}

        # تطبيق خوارزمية Water-Fill لتوزيع الميزانية (Budget Allocation)
        allocations = {}
        remaining_budget = self.max_char_budget
        active_sources = list(sources)

        while active_sources:
            fair_share = remaining_budget // len(active_sources)
            allocated_in_this_pass = False

            for src in list(active_sources):
                if needs[src] <= fair_share:
                    allocations[src] = needs[src]
                    remaining_budget -= needs[src]
                    active_sources.remove(src)
                    allocated_in_this_pass = True

            if not allocated_in_this_pass:
                # توزيع المتبقي بالتساوي على السجلات الكبيرة
                fair_share = remaining_budget // len(active_sources)
                for src in active_sources:
                    allocations[src] = fair_share
                break

        # اقتطاع النصوص وحفظ البداية والنهاية (Head/Tail Preserving)
        result = {}
        for src, text in full_texts.items():
            budget = allocations.get(src, 0)
            result[src] = self._truncate(text, budget)

        return result

    def _truncate(self, text: str, budget: int) -> str:
        if len(text) <= budget:
            return text
        if budget < 30:
            return text[:budget]

        marker = "\n... [TRUNCATED LOGS] ...\n"
        available = budget - len(marker)
        if available <= 0:
            return text[:budget]

        head_len = available // 2
        tail_len = available - head_len

        return text[:head_len] + marker + text[-tail_len:]


def run_self_test():
    print("=== [SELF-TEST] بدء اختبار أداة ضغط السجلات (Water-Fill) ===")

    mock_logs = {
        "stderr_stacktrace": [
            "Traceback (most recent call last):",
            "  File 'server.py', line 102, in <module>",
            "    res = db.execute('SELECT * FROM large_table')",
            "TimeoutError: Database query timed out after 30000ms",
        ]
        * 10,  # نص طويل مكرر
        "stdout_metrics": [
            "INFO 10:00:01 - Memory usage: 45%",
            "INFO 10:00:02 - CPU load: 12%",
        ],
        "system_events": [
            "EVENT: User 402 logged in",
            "EVENT: Session started",
        ],
    }

    original_total = sum(
        sum(len(line) for line in lines) for lines in mock_logs.values()
    )
    budget = 400

    compressor = WaterFillCompressor(max_char_budget=budget)
    compressed_output = compressor.compress(mock_logs)

    compressed_total = sum(len(v) for v in compressed_output.values())

    print(f"[✓] الحجم الأصلي للسجلات: {original_total} حرف")
    print(f"[✓] الحجم بعد الضغط: {compressed_total} حرف (الميزانية: {budget})")
    print("\n--- نتيجة الضغط المجهزة للـ LLM ---")
    print(json.dumps(compressed_output, indent=2, ensure_ascii=False))

    # التثبت العملي من النتيجة
    assert (
        compressed_total <= budget + 20
    ), "فشل الاختبار: حجم المخرجات تجاوز الميزانية المحددة!"
    assert (
        "... [TRUNCATED LOGS] ..." in compressed_output["stderr_stacktrace"]
    ), "فشل الاختبار: لم يتم اقتطاع السجل الطويل بشكل صحيح!"

    print("\n>>> اكتمل الاختبار الذاتي بنجاح (Passed 100%) <<<")


def main():
    parser = argparse.ArgumentParser(
        description="LLM Context Water-Fill Compressor Middleware"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="تشغيل الاختبار الذاتي للتحقق من الكود",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=500,
        help="الميزانية القصوى للأحرف (Max Characters)",
    )

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
