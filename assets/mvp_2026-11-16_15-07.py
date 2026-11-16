#!/usr/bin/env python3
"""
Micro-SaaS Prototype: WebGL Flight Simulator Asset & License Manager
------------------------------------------------------------------
هذا السكريبت يمثل نواة خدمة مصغرة لإدارة رخص الأصول وتوليد بيئات الطيران
الإجرائية (Procedural Seed Generator) وتقديم إحصاءات الاستخدام الفورية.
"""

import sys
import json
import hashlib
import time

class FlightSimMicroSaaS:
    def __init__(self):
        self.licenses = {}
        self.active_sessions = 0

    def generate_seed_terrain(self, seed_string: str) -> dict:
        """توليد معلمات البيئة ثلاثية الأبعاد بناءً على Seed محدد"""
        hash_object = hashlib.sha256(seed_string.encode())
        hex_dig = hash_object.hexdigest()
        
        # استخراج خصائص التضاريس محاكاةً لمحرك WebGL
        terrain_data = {
            "seed": seed_string,
            "elevation_map_hash": hex_dig[:16],
            "roughness": int(hex_dig[0:2], 16) / 255.0,
            "water_level": int(hex_dig[2:4], 16) / 255.0,
            "generated_at": time.time()
        }
        return terrain_data

    def issue_license(self, client_email: str, tier: str = "Pro") -> str:
        """إصدار رخصة استخدام للمتصفح"""
        token_data = f"{client_email}:{tier}:{time.time()}"
        license_key = hashlib.md5(token_data.encode()).hexdigest().upper()
        self.licenses[license_key] = {"email": client_email, "tier": tier, "active": True}
        return license_key

    def verify_license(self, license_key: str) -> bool:
        """التحقق من صلاحية الرخصة"""
        return license_key in self.licenses and self.licenses[license_key]["active"]

    def run_self_test(self):
        """تنفيذ اختبار ذاتي شامل للتحقق من سلامة النواة"""
        print("[*] Starting FlightSimMicroSaaS Self-Test...")
        
        # 1. اختبار توليد التضاريس
        test_seed = "HackerNews_WebGL_Flight"
        terrain = self.generate_seed_terrain(test_seed)
        assert terrain["seed"] == test_seed, "Terrain seed mismatch!"
        print(f"[+] Terrain Generation Test Passed: {json.dumps(terrain, indent=2)}")

        # 2. اختبار إدارة الرخص
        email = "pilot@test-saas.com"
        lic = self.issue_license(email, "Enterprise")
        is_valid = self.verify_license(lic)
        assert is_valid == True, "License verification failed!"
        print(f"[+] License Management Test Passed. Key: {lic}")

        print("[SUCCESS] All self-tests passed successfully. Ready for deployment!")

if __name__ == "__main__":
    app = FlightSimMicroSaaS()
    
    if "--self-test" in sys.argv:
        app.run_self_test()
    else:
        print("Run this script with '--self-test' to execute the automated diagnostic.")
