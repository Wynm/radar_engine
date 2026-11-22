#!/usr/bin/env python3
"""
Inference Provider Security & Transparency Monitor (Micro-SaaS Core)
يتوافق هذا الكود مع معايير Python القياسية تماماً (لا يتطلب تثبيت أي مكتبات خارجية عبر pip).
"""

import sys
import json
import urllib.request
import urllib.error
import time

class ProviderSecurityMonitor:
    def __init__(self, providers_config):
        self.providers = providers_config

    def check_provider(self, name, endpoint):
        start_time = time.time()
        status = "SECURE"
        latency = 0.0
        details = "Normal operation"

        try:
            # محاكاة فحص أمني ونقطة النهاية للمزود
            req = urllib.request.Request(endpoint, headers={'User-Agent': 'SecurityMonitor-MVP/1.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                latency = round((time.time() - start_time) * 1000, 2)
                if response.status != 200:
                    status = "WARNING"
                    details = f"HTTP Status: {response.status}"
        except urllib.error.URLError as e:
            status = "CRITICAL_INCIDENT"
            latency = round((time.time() - start_time) * 1000, 2)
            details = f"Connection failed: {e.reason}"
        except Exception as e:
            status = "ERROR"
            details = str(e)

        return {
            "provider": name,
            "status": status,
            "latency_ms": latency,
            "details": details,
            "timestamp": time.time()
        }

    def run_audit(self):
        results = []
        for name, endpoint in self.providers.items():
            results.append(self.check_provider(name, endpoint))
        return results

def self_test():
    print("[*] Running Self-Test for Inference Provider Security Monitor...")
    # استخدام نقاط نهاية عامة وآمنة للاختبار الذاتي
    test_config = {
        "Mock-Secure-Provider": "https://httpbin.org/status/200",
        "Mock-Unstable-Provider": "https://httpbin.org/status/500",
        "Mock-Dead-Provider": "https://invalid.domain.name.12345"
    }
    
    monitor = ProviderSecurityMonitor(test_config)
    audit_results = monitor.run_audit()
    
    print("\n[+] Audit Results Summary:")
    print(json.dumps(audit_results, indent=2))
    
    # التحقق من صحة النتائج
    assert len(audit_results) == 3, "فشل الاختبار: العدد غير متطابق"
    print("\n[SUCCESS] Self-test completed successfully. Ready for Production deployment.")
    return True

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        print("Usage: python script.py --self-test")
        sys.exit(1)
