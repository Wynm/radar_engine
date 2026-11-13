import sys
import json
import urllib.request
import urllib.error

class ContentOptimizerMVP:
    """
    نواة خدمة Micro-SaaS لتحسين وصياغة المحتوى (مستوحاة من Templify AI).
    تعمل بمكتبات Python القياسية فقط (بدون الحاجة لـ pip).
    """
    def __init__(self):
        self.templates = {
            "marketing": "🚀 فرصة ذهبية: {text} - لا تفوت العرض واشترك معنا اليوم!",
            "formal": "تحية طيبة وبعد، بناءً على ما يلي: {text}، نرجو التفضل بالاطلاع والاعتماد.",
            "concise": "باختصار: {text}."
        }

    def process(self, text, style="marketing"):
        if not text.strip():
            return "خطأ: النص المدخل فارغ."
        template = self.templates.get(style, self.templates["marketing"])
        return template.format(text=text.strip())

    def self_test(self):
        print("[-] بدء الاختبار الذاتي (Self-Test)...")
        test_text = "خدمة ذكية لتحسين المحتوى"
        
        # اختبار النمط التسويقي
        res_mkt = self.process(test_text, "marketing")
        assert "🚀 فرصة ذهبية" in res_mkt, "فشل اختبار النمط التسويقي"
        
        # اختبار النمط الرسمي
        res_frm = self.process(test_text, "formal")
        assert "تحية طيبة وبعد" in res_frm, "فشل اختبار النمط الرسمي"
        
        # اختبار النمط المختصر
        res_con = self.process(test_text, "concise")
        assert "باختصار" in res_con, "فشل اختبار النمط المختصر"
        
        print("[+] اجتاز النظام كافة الاختبارات الذاتية بنجاح تام (100% Operational).")
        return True

if __name__ == "__main__":
    app = ContentOptimizerMVP()
    if "--self-test" in sys.argv:
        success = app.self_test()
        sys.exit(0 if success else 1)
    else:
        # تشغيل تجريبي افتراضي
        sample_input = "إطلاق الإصدار الأول من منصة المحتوى"
        print("النتيجة الافتراضية:", app.process(sample_input, "marketing"))
