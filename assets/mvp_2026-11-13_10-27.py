import sys
import unittest
from datetime import datetime

class PredictionMarketAnalyzer:
    """أداة تحليل بيانات التنبؤ واتخاذ القرار محلياً دون تبعات خارجية."""
    
    def __init__(self, market_id: str, current_probability: float):
        self.market_id = market_id
        self.probability = max(0.0, min(1.0, current_probability))
        self.timestamp = datetime.utcnow().isoformat()

    def detect_edge(self, model_estimate: float) -> dict:
        """كشف الفجوات الاحتمالية (Edge Detection) بين تقدير النموذج وسعر السوق."""
        model_estimate = max(0.0, min(1.0, model_estimate))
        edge = model_estimate - self.probability
        return {
            "market_id": self.market_id,
            "market_probability": self.probability,
            "model_estimate": model_estimate,
            "edge": round(edge, 4),
            "recommendation": "BUY" if edge > 0.05 else ("SELL" if edge < -0.05 else "HOLD"),
            "timestamp": self.timestamp
        }


class TestPredictionMarketAnalyzer(unittest.TestCase):
    """فحص ذاتي متكامل يعمل دون اتصال بالشبكة أو تعديل ملفات المستخدم."""
    
    def test_edge_detection_buy(self):
        analyzer = PredictionMarketAnalyzer("TEST-01", 0.40)
        result = analyzer.detect_edge(0.55)
        self.assertEqual(result["recommendation"], "BUY")
        self.assertEqual(result["edge"], 0.15)

    def test_edge_detection_sell(self):
        analyzer = PredictionMarketAnalyzer("TEST-02", 0.70)
        result = analyzer.detect_edge(0.60)
        self.assertEqual(result["recommendation"], "SELL")
        self.assertEqual(result["edge"], -0.10)

    def test_edge_detection_hold(self):
        analyzer = PredictionMarketAnalyzer("TEST-03", 0.50)
        result = analyzer.detect_edge(0.52)
        self.assertEqual(result["recommendation"], "HOLD")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        # تشغيل الفحص الذاتي واعتراض المخرجات لتجنب تأثير الوسائط الخارجية
        suite = unittest.TestLoader().loadTestsFromTestCase(TestPredictionMarketAnalyzer)
        runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        # مثال تشغيل سريع للاختبار المحلي
        bot = PredictionMarketAnalyzer("US-ELECTION-2026", 0.48)
        analysis = bot.detect_edge(0.58)
        print("Market Analysis Result:", analysis)
