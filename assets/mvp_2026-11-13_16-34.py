#!/usr/bin/env python3
"""
Burnstate MVP Simulator & Token Rate-Limit Monitor
يقوم هذا السكربت بمحاكاة مراقبة استهلاك الرموز (Tokens) لأدوات الذكاء الاصطناعي
مع دعم الفحص الذاتي المباشر عبر معامل --self-test.
"""

import sys
import json
import time

class BurnstateMonitor:
    def __init__(self, limit_per_minute=10000):
        self.limit = limit_per_minute
        self.current_usage = 0

    def record_usage(self, tokens):
        self.current_usage += tokens
        percentage = (self.current_usage / self.limit) * 100
        status = "CRITICAL" if percentage > 80 else ("WARNING" if percentage > 50 else "NORMAL")
        return {
            "current_usage": self.current_usage,
            "limit": self.limit,
            "percentage": round(percentage, 2),
            "status": status
        }

    def self_test(self):
        print("[-] Starting Burnstate Self-Test...")
        # محاكاة استخدام متزايد للرموز
        test_steps = [1500, 3000, 4500]
        results = []
        for step in test_steps:
            res = self.record_usage(step)
            results.append(res)
            print(f"  > Added {step} tokens -> Usage: {res['percentage']}% [{res['status']}]")
        
        # التحقق من صحة النتائج
        assert len(results) == 3, "Test failed: Expected 3 steps."
        assert results[-1]["status"] == "CRITICAL", "Test failed: Expected CRITICAL status at the end."
        print("[+] Burnstate Self-Test Passed Successfully!")
        return True

def main():
    monitor = BurnstateMonitor(limit_per_minute=10000)
    
    # تنفيذ الفحص الذاتي إذا تم تمرير المعامل --self-test
    if "--self-test" in sys.argv:
        success = monitor.self_test()
        sys.exit(0 if success else 1)
    
    # التشغيل العادي كنموذج أولي
    print("Burnstate Token Monitor Initialized. Use --self-test to run automated tests.")
    sample_report = monitor.record_usage(2500)
    print(json.dumps(sample_report, indent=2))

if __name__ == "__main__":
    main()
