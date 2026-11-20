#!/usr/bin/env python3
import argparse
import json
import re
import sys
from typing import Dict, List, Any

class NeonClipAnalyzer:
    """
    محرك تحليل النصوص واكتشاف اللحظات الجذابة لإنشاء المقاطع الرأسية (9:16)
    مستوحى من neonclipping باستعمال مكتبات Python القياسية فقط.
    """
    def __init__(self):
        # كلمات مفتاحية محفزة للانتشار (Viral Keywords)
        self.viral_keywords = {
            "secret", "nobody", "proven", "stop", "never", "always",
            "mistake", "money", "fast", "easy", "crazy", "best", "trick",
            "سر", "خطأ", "كيف", "أفضل", "لا تكرر", "ربح", "تلميحة", "مهم"
        }

    def score_text(self, text: str) -> float:
        """حساب درجة جاذبية النص بناءً على كثافة الكلمات المفتاحية والطول"""
        words = re.findall(r'\w+', text.lower())
        if not words:
            return 0.0
        
        matches = sum(1 for w in words if w in self.viral_keywords)
        density_score = (matches / len(words)) * 100.0
        length_score = min(len(words) * 0.2, 10.0)  # مكافأة النصوص ذات الطول المناسب
        return round(density_score + length_score, 2)

    def generate_hook(self, text: str) -> str:
        """صياغة خطاف (Hook) جذاب للمقطع"""
        clean_text = text.strip()
        first_sentence = re.split(r'[.!?،؟]', clean_text)[0]
        if len(first_sentence) > 45:
            first_sentence = first_sentence[:42] + "..."
        return f"🔥 {first_sentence.upper()}"

    def build_ffmpeg_cmd(self, input_file: str, start: float, duration: float, output_file: str) -> str:
        """توليد أمر FFmpeg لتحويل الفيديو إلى مقطع رأسي 9:16"""
        vf_crop = "crop=ih*(9/16):ih"
        return f"ffmpeg -ss {start:.2f} -i '{input_file}' -t {duration:.2f} -vf '{vf_crop}' -c:a copy '{output_file}'"

    def process_segments(self, segments: List[Dict[str, Any]], input_video: str = "input.mp4") -> List[Dict[str, Any]]:
        """معالجة أجزاء النص واستخراج أفضل المقاطع الجاهزة للقص"""
        results = []
        for idx, seg in enumerate(segments):
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            duration = end - start
            text = seg.get("text", "")

            # الفلترة: قبول المقاطع بين 5 و 60 ثانية فقط (مثالية لـ Shorts/Reels)
            if duration < 5.0 or duration > 60.0:
                continue

            score = self.score_text(text)
            hook = self.generate_hook(text)
            out_name = f"clip_{idx + 1}_{int(start)}s.mp4"
            cmd = self.build_ffmpeg_cmd(input_video, start, duration, out_name)

            results.append({
                "clip_id": idx + 1,
                "start": start,
                "end": end,
                "duration": round(duration, 2),
                "viral_score": score,
                "text": text,
                "hook": hook,
                "ffmpeg_command": cmd
            })

        # ترتيب المقاطع من الأكثر جاذبية إلى الأقل
        results.sort(key=lambda x: x["viral_score"], reverse=True)
        return results


def run_self_test() -> bool:
    """تنفيذ اختبار ذاتي كامل ومتحقق منه بدون الاعتماد على ملفات خارجية"""
    print("=== بدء الاختبار الذاتي لنواة NeonClip MVP ===")
    
    sample_transcript = [
        {"start": 0.0, "end": 4.0, "text": "Hello world."},  # قصير جداً (سيتم استبعاده)
        {"start": 5.0, "end": 25.0, "text": "This secret money mistake is what nobody tells you about running a successful business!"},
        {"start": 30.0, "end": 55.0, "text": "Here is how you can optimize your video clips using simple Python code fast and easy."},
        {"start": 60.0, "end": 130.0, "text": "This is a very long boring segment that should exceed the 60 second limit."}  # طويل جداً
    ]

    analyzer = NeonClipAnalyzer()
    processed = analyzer.process_segments(sample_transcript, "test_video.mp4")

    # التحققات (Assertions)
    assert len(processed) == 2, f"متوقع مقطعين مقبولين فقط، تم استخراج: {len(processed)}"
    
    top_clip = processed[0]
    assert top_clip["viral_score"] > 0, "فشل حساب درجة الجاذبية (Score)"
    assert "crop=ih*(9/16):ih" in top_clip["ffmpeg_command"], "فشل توليد فلتر FFmpeg للقطع الرأسي"
    assert top_clip["duration"] == 20.0, "حساب مدة المقطع غير صحيح"
    
    print(f"[ناجح] تم استخراج {len(processed)} مقاطع بنجاح.")
    print(f"[ناجح] أعلى مقطع تقييماً (النتيجة: {top_clip['viral_score']}): {top_clip['hook']}")
    print(f"[ناجح] أمر القص المولد: {top_clip['ffmpeg_command']}")
    print("=== اكتمل الاختبار الذاتي بنجاح 100% ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="NeonClip Core - محرك أتمتة المقاطع القصيرة")
    parser.add_argument("--self-test", action="store_true", help="تشغيل الاختبار الذاتي والتحقق من صحة النظام")
    parser.add_argument("--input-json", type=str, help="مسار ملف JSON يحتوي على تفريغ نصي مع توقيتات")

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    if args.input_json:
        try:
            with open(args.input_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            analyzer = NeonClipAnalyzer()
            output = analyzer.process_segments(data)
            print(json.dumps(output, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"خطأ أثناء قراءة الملف: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
