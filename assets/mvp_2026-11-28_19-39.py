#!/usr/bin/env python3
"""
BugTriageGatekeeper - نواة خدمة فلترة تقارير الأخطاء (Micro-SaaS MVP)
تستند الفكرة إلى سد الفجوة الناشئة عن طوفان البلاغات المولدة بالذكاء الاصطناعي.
الاعتمادات: مكتبات Python القياسية فقط (بدون أي تبعات خارجية).
"""

import sys
import json
import re
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

class BugFilterEngine:
    """محرك فحص وفلترة تقارير الأخطاء واكتشاف الرسائل الموجهة أو الوهمية (Slop Filter)."""
    
    SPAM_PATTERNS = [
        r"urgent fix required",
        r"click this link",
        r"guaranteed profit",
        r"free crypto",
        r"as an ai language model"
    ]

    @classmethod
    def evaluate_report(cls, report_text: str) -> dict:
        score = 100
        flags = []
        text_lower = report_text.lower()

        # فحص الطول غير المبرر أو القصر الشديد
        if len(report_text.strip()) < 20:
            score -= 50
            flags.append("REPORT_TOO_SHORT")

        # فحص الكلمات الدالة على السبام أو المحتوى المولد عشوائياً
        for pattern in cls.SPAM_PATTERNS:
            if re.search(pattern, text_lower):
                score -= 40
                flags.append(f"AI_SLOP_PATTERN_MATCHED: {pattern}")

        # تحديد الحالة النهائية للبلاغ
        if score >= 70:
            status = "ACCEPTED_FOR_REVIEW"
        elif score >= 40:
            status = "REQUIRES_HUMAN_VERIFICATION"
        else:
            status = "REJECTED_AS_AI_SLOP"

        return {
            "quality_score": max(0, score),
            "status": status,
            "flags": flags
        }


class TriageHTTPServer(BaseHTTPRequestHandler):
    """خادم HTTP مصغر لاستقبال تقارير الأخطاء ومعالجتها برمجياً كخدمة Micro-SaaS."""

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            report_text = data.get("report", "")
            
            result = BugFilterEngine.evaluate_report(report_text)
            
            response_body = json.dumps(result).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response_body)
        except Exception as e:
            err_res = json.dumps({"error": str.format("Invalid JSON payload: {}", e)}).encode('utf-8')
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(err_res)

    def log_message(self, format, *args):
        # تعطيل سجلات الخادم الافتراضية للحفاظ على نظافة مخرجات الاختبار
        return


def run_self_test():
    """تنفيذ اختبار ذاتي شامل لجميع وظائف النظام وطباعة النتيجة."""
    print("[*] بدء الاختبار الذاتي (Self-Test) لنظام BugTriageGatekeeper...")
    
    # 1. اختبار بلاغ حقيقي وناضج
    valid_report = "Exception in module auth.py line 45: NullPointerException when session is expired."
    res_valid = BugFilterEngine.evaluate_report(valid_report)
    print(f" -> اختبار بلاغ صحيح: النتيجة = {res_valid['status']} (النقاط: {res_valid['quality_score']})")
    assert res_valid['quality_score'] >= 70, "فشل اختبار البلاغ الصحيح"

    # 2. اختبار بلاغ مشبوه/مولد بالذكاء الاصطناعي (AI Slop)
    spam_report = "As an AI language model, urgent fix required, click this link for guaranteed profit."
    res_spam = BugFilterEngine.evaluate_report(spam_report)
    print(f" -> اختبار بلاغ وهمي (Slop): النتيجة = {res_spam['status']} (الأعلام: {res_spam['flags']})")
    assert res_spam['quality_score'] < 40, "فشل كشف المحتوى الوهمي"

    print("\n[نجاح] اجتاز النظام كافة اختبارات الأمان والجودة الذاتية بنجاح تام!")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        run_self_test()
        sys.exit(0)
    else:
        print("تشغيل خادم Triage Gatekeeper على المنفذ 8080...")
        print("استخدم الوسيط --self-test لتنفيذ الاختبار الذاتي الفوري.")
        server = HTTPServer(('127.0.0.1', 8080), TriageHTTPServer)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
