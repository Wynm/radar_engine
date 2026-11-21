import sys
import os
import tempfile

class BinaryHexAnalyzerMVP:
    """
    نواة أداة تحليل وتعديل البيانات الثنائية (Hex Dump / Binary) 
    تخدم سوق أتمتة فحص الملفات التنفيذية وتطبيق التعديلات البرمجية مباشرة.
    """
    def __init__(self, data: bytes):
        self.data = bytearray(data)

    def to_hex_dump(self, bytes_per_line: int = 16) -> str:
        """تحويل البيانات الثنائية إلى صيغة Hex Dump مقروءة."""
        lines = []
        for i in range(0, len(self.data), bytes_per_line):
            chunk = self.data[i:i + bytes_per_line]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{i:08X}  {hex_part:<{bytes_per_line*3}}  |{ascii_part}|")
        return "\n".join(lines)

    def patch_bytes(self, offset: int, new_bytes: bytes) -> bool:
        """تعديل بايتات محددة في الموقع المطلوب (Offset)."""
        if 0 <= offset + len(new_bytes) <= len(self.data):
            for idx, b in enumerate(new_bytes):
                self.data[offset + idx] = b
            return True
        return False

    def self_test(self) -> bool:
        """تنفيذ اختبار ذاتي حقيقي للتأكد من سلامة الوظائف دون تأثير على النظام."""
        try:
            # 1. إنشاء بيانات تجريبية (محاكاة ملف تنفيذي مصغر)
            sample_data = b"Hello, Binary World! 2026"
            analyzer = BinaryHexAnalyzerMVP(sample_data)
            
            # 2. اختبار توليد الـ Hex Dump
            dump = analyzer.to_hex_dump(8)
            assert len(dump) > 0, "فشل توليد الـ Hex Dump"
            
            # 3. اختبار التعديل (Patching)
            success = analyzer.patch_bytes(0, b"JCP")
            assert success and analyzer.data[0:3] == b"JCP", "فشل تعديل البايتات"
            
            print("[+] Self-Test Passed Successfully: Binary analysis & patching core operational.")
            return True
        except AssertionError as e:
            print(f"[-] Self-Test Failed: {e}")
            return False
        except Exception as e:
            print(f"[-] Unexpected Error during Self-Test: {e}")
            return False

if __name__ == "__main__":
    # التعامل مع معامل الاختبار الذاتي المطلوبة
    if "--self-test" in sys.argv:
        analyzer = BinaryHexAnalyzerMVP(b"")
        result = analyzer.self_test()
        sys.exit(0 if result else 1)
    else:
        # تشغيل افتراضي كمثال استعراضي
        sample = b"AI and Binary Execution Engine MVP."
        analyzer = BinaryHexAnalyzerMVP(sample)
        print("--- Hex Dump Preview ---")
        print(analyzer.to_hex_dump())
        print("\nRun with '--self-test' to execute the automated test suite.")
