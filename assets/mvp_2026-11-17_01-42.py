import argparse
import datetime
import json
import sys


class CalComYieldEngine:
    """محرك أتمتة وحساب التسعير الديناميكي للمواعيد المدفوعة عبر Cal.com v7"""

    def __init__(self, base_rate: float = 100.0):
        self.base_rate = base_rate

    def calculate_dynamic_price(
        self, booking_datetime: datetime.datetime, is_vip: bool = False
    ) -> dict:
        """حساب السعر الديناميكي بناءً على مدى قرب الموعد، عطلة نهاية الأسبوع، وفئة العملاء"""
        now = datetime.datetime.now()
        hours_until_event = (booking_datetime - now).total_seconds() / 3600.0

        if hours_until_event < 0:
            hours_until_event = 0

        multiplier = 1.0

        # زيادة السعر للمواعيد المستعجلة (Surge Pricing)
        if hours_until_event < 24:
            multiplier *= 1.50  # زيادة 50% للمواعيد خلال أقل من 24 ساعة
        elif hours_until_event < 72:
            multiplier *= 1.20  # زيادة 20% للمواعيد خلال أقل من 3 أيام

        # زيادة السعر لعطلة نهاية الأسبوع (السبت والأحد)
        if booking_datetime.weekday() in (5, 6):
            multiplier *= 1.25

        # خصم للعملاء المميزين
        if is_vip:
            multiplier *= 0.85

        final_price = round(self.base_rate * multiplier, 2)

        return {
            "base_rate": self.base_rate,
            "final_price": final_price,
            "surge_multiplier": round(multiplier, 2),
            "hours_until_event": round(hours_until_event, 1),
            "is_weekend": booking_datetime.weekday() in (5, 6),
            "is_vip": is_vip,
        }

    def generate_calcom_payload(
        self,
        event_type_id: int,
        start_time_iso: str,
        attendee_email: str,
        attendee_name: str,
        calculated_price: float,
    ) -> dict:
        """توليد الحمولة البرمجية القياسية المتوافقة مع API الخاص بـ Cal.com v7"""
        return {
            "eventTypeId": event_type_id,
            "start": start_time_iso,
            "responses": {
                "name": attendee_name,
                "email": attendee_email,
                "location": {"optionValue": "", "value": "integrations:daily"},
            },
            "metadata": {
                "dynamic_price_usd": calculated_price,
                "pricing_engine": "CalComYieldEngine-v1",
            },
            "timeZone": "UTC",
            "language": "ar",
        }

    def summarize_revenue(self, bookings_data: list) -> dict:
        """تحليل ومعالجة إجمالي العوائد المتوقعة من قائمة المواعيد"""
        if not bookings_data:
            return {"total_revenue": 0.0, "average_price": 0.0, "count": 0}

        total = sum(item.get("final_price", 0.0) for item in bookings_data)
        return {
            "total_revenue": round(total, 2),
            "average_price": round(total / len(bookings_data), 2),
            "count": len(bookings_data),
        }


def run_self_test():
    """تنفيذ اختبار ذاتي حقيقي للتأكد من سلامة جميع وظائف النظام دون الاعتماد على ملفات خارجية"""
    print("[+] بدء الاختبار الذاتي لمحرك Cal.com Dynamic Pricing...")

    engine = CalComYieldEngine(base_rate=100.0)

    # 1. اختبار حساب السعر المستعجل (< 24 ساعة)
    urgent_time = datetime.datetime.now() + datetime.timedelta(hours=10)
    res_urgent = engine.calculate_dynamic_price(urgent_time)
    assert (
        res_urgent["final_price"] >= 150.0
    ), f"فشل اختبار السعر المستعجل: {res_urgent}"
    print("  ✓ تم اجتياز اختبار تسعير المواعيد المستعجلة.")

    # 2. اختبار توليد صيغة Cal.com API Payload
    payload = engine.generate_calcom_payload(
        event_type_id=42,
        start_time_iso="2026-04-01T10:00:00Z",
        attendee_email="client@example.com",
        attendee_name="أحمد علي",
        calculated_price=150.0,
    )
    assert payload["eventTypeId"] == 42, "فشل اختبار eventTypeId"
    assert (
        payload["metadata"]["dynamic_price_usd"] == 150.0
    ), "فشل اختبار metadata السعر"
    print("  ✓ تم اجتياز اختبار توليد بيانات Cal.com API.")

    # 3. اختبار تحليل العوائد
    mock_batch = [{"final_price": 100.0}, {"final_price": 150.0}]
    stats = engine.summarize_revenue(mock_batch)
    assert stats["total_revenue"] == 250.0, "فشل حساب إجمالي العوائد"
    assert stats["count"] == 2, "فشل حساب عدد المواعيد"
    print("  ✓ تم اجتياز اختبار تحليل البيانات وإحصاء العوائد.")

    print(
        "\n[SUCCESS] جميع الاختبارات الذاتية تمت بنجاح وبسرعة دون أي أخطاء أو مكتبات خارجية!"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Cal.com Dynamic Pricing Engine Micro-SaaS MVP"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="تشغيل الاختبار الذاتي للوحدة"
    )
    parser.add_argument(
        "--base-rate",
        type=float,
        default=100.0,
        help="السعر الأساسي للحجز بالساعة",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    # العرض التوضيحي التشغيلي (Demo)
    engine = CalComYieldEngine(base_rate=args.base_rate)
    sample_booking_time = datetime.datetime.now() + datetime.timedelta(
        hours=18
    )
    quote = engine.calculate_dynamic_price(sample_booking_time)

    print("=== محرك تسعير المواعيد المدفوعة (Cal.com v7 Yield Engine) ===")
    print(f"السعر الأساسي: ${quote['base_rate']}")
    print(f"السعر المحسوب ديناميكياً: ${quote['final_price']}")
    print(f"معامل الزيادة (Surge): {quote['surge_multiplier']}x")

    payload = engine.generate_calcom_payload(
        event_type_id=101,
        start_time_iso=sample_booking_time.isoformat(),
        attendee_email="demo@example.com",
        attendee_name="عميل تجريبي",
        calculated_price=quote["final_price"],
    )

    print("\nبيانات Payload الجاهزة للإرسال لـ Cal.com API:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
