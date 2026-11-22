#!/usr/bin/env python3
import sys
import json
import argparse
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

class PolymarketArbitrageScanner:
    """
    محرك فحص فرس المراجحة (Arbitrage) لأسواق التنبؤ باستخدام المكتبات القياسية لـ Python.
    يقوم باكتشاف الفروق السعرية حيث يكون مجموع شراء (YES + NO) أقل من 1.00 دولار.
    """

    def __init__(self, target_api_url: str = "https://gamma-api.polymarket.com/markets?limit=10&active=true&closed=false"):
        self.api_url = target_api_url

    def fetch_markets(self) -> List[Dict[str, Any]]:
        """جلب البيانات المباشرة من API أسواق Polymarket العامة."""
        req = urllib.request.Request(
            self.api_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    return data if isinstance(data, list) else []
        except Exception:
            return []
        return []

    def calculate_arbitrage(self, yes_price: float, no_price: float) -> Optional[Dict[str, float]]:
        """
        حساب نسبة الربح المضمون إذا كانت التكلفة الإجمالية للشراء أقل من 1.00 دولار.
        """
        total_cost = yes_price + no_price
        if total_cost <= 0 or total_cost >= 1.0:
            return None
        
        net_profit = 1.0 - total_cost
        roi_percentage = (net_profit / total_cost) * 100.0
        return {
            "total_cost": round(total_cost, 4),
            "guaranteed_payout": 1.00,
            "net_profit": round(net_profit, 4),
            "roi_percent": round(roi_percentage, 2)
        }

    def run_self_test(self) -> bool:
        """
        تنفيذ اختبار ذاتي آمن ومستقل للتأكد من صحة خوارزميات الحساب ودعم الخيارات.
        """
        print("=== [بدء الاختبار الذاتي / SELF-TEST] ===")
        
        # اختبار 1: اكتشاف فرصة مراجحة حقيقية (0.48 YES + 0.49 NO = 0.97)
        res1 = self.calculate_arbitrage(0.48, 0.49)
        assert res1 is not None, "فشل الاختبار 1: لم يتم اكتشاف فرصة المراجحة."
        assert res1["roi_percent"] > 0, "فشل الاختبار 1: نسبة العائد يجب أن تكون موجبة."
        print(f"[✓] الاختبار 1 نجح: تم كشف فرصة مراجحة (العائد: {res1['roi_percent']}%)")

        # اختبار 2: تجنب الأسواق غير المربحة (0.52 YES + 0.50 NO = 1.02)
        res2 = self.calculate_arbitrage(0.52, 0.50)
        assert res2 is None, "فشل الاختبار 2: تم احتساب فرصة خاسرة خاطئة."
        print("[✓] الاختبار 2 نجح: تم استبعاد الأسواق غير المربحة بنجاح.")

        # اختبار 3: التحقق من دقة الحسابات الرقمية
        res3 = self.calculate_arbitrage(0.45, 0.50)
        expected_roi = 5.26
        assert res3 is not None and abs(res3["roi_percent"] - expected_roi) < 0.1, "فشل الاختبار 3: خطأ في دقة الرياضيات."
        print(f"[✓] الاختبار 3 نجح: دقة الحسابات المعقدة صحيحة ({res3['roi_percent']}%).")

        print("=== [جميع الاختبارات الذاتية تمت بنجاح / PASSED] ===")
        return True

def main():
    parser = argparse.ArgumentParser(description="Polymarket Arbitrage Engine MVP")
    parser.add_argument("--self-test", action="store_true", help="تشغيل الاختبار الذاتي للتحقق من الكود")
    args = parser.parse_args()

    scanner = PolymarketArbitrageScanner()

    if args.self_test:
        success = scanner.run_self_test()
        sys.exit(0 if success else 1)

    print("جارٍ الفحص عن فرص المراجحة في أسواق Polymarket...")
    markets = scanner.fetch_markets()
    
    if not markets:
        print("[ملاحظة] تعذر الاتصال بالشبكة أو استخدام بيانات حية، يتم عرض محاكاة لعمل المحرك:")
        sample = scanner.calculate_arbitrage(0.47, 0.51)
        print(f"نتيجة تحليل عينة اختبارية: {sample}")
        return

    opportunities_found = 0
    for m in markets:
        try:
            outcome_prices = m.get("outcomePrices")
            if outcome_prices:
                prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
                if len(prices) >= 2:
                    p_yes = float(prices[0])
                    p_no = float(prices[1])
                    arb = scanner.calculate_arbitrage(p_yes, p_no)
                    if arb:
                        opportunities_found += 1
                        print(f"\n[فرصة مراجحة جديدة!] {m.get('question', 'بدون عنوان')}")
                        print(f"   سعر YES: ${p_yes} | سعر NO: ${p_no}")
                        print(f"   التكلفة الإجمالية: ${arb['total_cost']} | الربح الصافي: ${arb['net_profit']}")
                        print(f"   العائد الاستثماري (ROI): {arb['roi_percent']}%")
        except Exception:
            continue

    print(f"\nاكتمل الفحص. إجمالي الفرص المكتشفة: {opportunities_found}")

if __name__ == "__main__":
    main()
