import sys
import json
import urllib.request
import urllib.error

class AdCampaignMVP:
    """
    نموذج أولي مبسط (MVP) لخدمة إدارة وتوليد الحملات الإعلانية ومحاكاة واجهة Creatify Max.
    يقوم بإنشاء خطة إعلانية استراتيجية وتحليل العائد المتوقع.
    """
    def __init__(self, product_name: str, target_audience: str, budget: float):
        self.product_name = product_name
        self.target_audience = target_audience
        self.budget = budget

    def generate_campaign_strategy(self) -> dict:
        # توليد استراتيجية إعلانية محاكاة بناءً على المعطيات
        estimated_reach = self.budget * 150
        estimated_clicks = int(estimated_reach * 0.04)
        estimated_conversions = int(estimated_clicks * 0.025)
        
        strategy = {
            "product": self.product_name,
            "audience": self.target_audience,
            "budget": self.budget,
            "metrics": {
                "estimated_reach": estimated_reach,
                "estimated_clicks": estimated_clicks,
                "estimated_conversions": estimated_conversions
            },
            "ad_variants": [
                f"اكتشف قوة {self.product_name} المصمم خصيصاً لـ {self.target_audience}!",
                f"هل تعاني من مشاكل في مجالك؟ {self.product_name} هو الحل الأمثل.",
                f"عرض لفترة محدودة لـ {self.target_audience}: احصل على {self.product_name} الآن."
            ]
        }
        return strategy

def run_self_test():
    print("--- بدء الاختبار الذاتي لنظام الإعلانات (Self-Test) ---")
    try:
        mvp = AdCampaignMVP(
            product_name="AI Video Creator",
            target_audience="Digital Marketers",
            budget=500.0
        )
        result = mvp.generate_campaign_strategy()
        
        # التحقق من صحة النتائج
        assert result["product"] == "AI Video Creator", "خطأ في اسم المنتج"
        assert result["metrics"]["estimated_reach"] == 75000.0, "خطأ في حساب الوصول"
        assert len(result["ad_variants"]) == 3, "خطأ في عدد الإعلانات المولدةئة"
        
        print("البيانات المولدة بنجاح:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\n[نجاح] اجتاز النظام اختبار Self-Test بنجاح تام!")
        return 0
    except Exception as e:
        print(f"[فشل] حدث خطأ أثناء الاختبار الذاتي: {e}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        sys.exit(run_self_test())
    else:
        print("تشغيل النظام التجاري. استخدم المعامل --self-test لتنفيذ الاختبار الذاتي.")
        campaign = AdCampaignMVP("Smart SaaS", "Small Businesses", 1000.0)
        print(json.dumps(campaign.generate_campaign_strategy(), ensure_ascii=False, indent=2))
