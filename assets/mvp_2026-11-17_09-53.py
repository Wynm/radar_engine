#!/usr/bin/env python3
"""
Quantitative Range-Dip Mean Reversion Engine with Dynamic Flush Switch
A self-contained algorithmic trading signal and risk-management micro-engine.
Standard Library Only (Zero external dependencies).
"""

import sys
import math
import json
import argparse
from typing import List, Dict, Optional, Tuple

class MarketDataPoint:
    def __init__(self, timestamp: int, price: float, volume: float = 1.0):
        self.timestamp = timestamp
        self.price = float(price)
        self.volume = float(volume)

class RangeDipEngine:
    def __init__(self, 
                 window_size: int = 20, 
                 dip_threshold_std: float = 1.8, 
                 exit_threshold_std: float = 0.5,
                 flush_drop_pct: float = 0.04):
        """
        :param window_size: عدد الشموع لحساب المتوسط والانحراف المعياري
        :param dip_threshold_std: معامل الانحراف المعياري لرصد الشراء عند القاع
        :param exit_threshold_std: معامل الانحراف المعياري لجني الأرباح عند المتوسط
        :param flush_drop_pct: نسبة الهبوط العنيف لتفعيل قاطع الدائرة (Flush Switch)
        """
        self.window_size = window_size
        self.dip_threshold_std = dip_threshold_std
        self.exit_threshold_std = exit_threshold_std
        self.flush_drop_pct = flush_drop_pct
        self.history: List[MarketDataPoint] = []
        self.is_flushed: bool = False

    def reset(self):
        self.history.clear()
        self.is_flushed = False

    def update(self, point: MarketDataPoint) -> Dict[str, any]:
        self.history.append(point)
        if len(self.history) < self.window_size:
            return {
                "timestamp": point.timestamp,
                "price": point.price,
                "action": "HOLD",
                "reason": "INSUFFICIENT_DATA",
                "flush_active": False
            }

        # اقتطاع النافذة الزمنية الحالية
        recent_prices = [p.price for p in self.history[-self.window_size:]]
        mean = sum(recent_prices) / self.window_size
        variance = sum((x - mean) ** 2 for x in recent_prices) / self.window_size
        std_dev = math.sqrt(variance) if variance > 0 else 1e-8

        current_price = point.price
        recent_peak = max(recent_prices)
        current_drop = (recent_peak - current_price) / recent_peak

        # فحص قاطع الدائرة (Flush Switch)
        if current_drop >= self.flush_drop_pct:
            self.is_flushed = True
            return {
                "timestamp": point.timestamp,
                "price": current_price,
                "action": "CLOSE_AND_HALT",
                "reason": f"FLUSH_TRIGGERED_DROP_{current_drop*100:.2f}%",
                "flush_active": True,
                "mean": round(mean, 2),
                "std": round(std_dev, 2)
            }

        # إعادة ضبط حالة القاطع إذا استقرت الأسعار داخل نطاق آمن
        if self.is_flushed and current_drop < (self.flush_drop_pct * 0.5):
            self.is_flushed = False

        if self.is_flushed:
            return {
                "timestamp": point.timestamp,
                "price": current_price,
                "action": "HALT",
                "reason": "SAFETY_LOCK_ENGAGED",
                "flush_active": True
            }

        # حساب z-score
        z_score = (current_price - mean) / std_dev

        # منطق التداول: ارتداد من القاع (Range-Dip) وجني الأرباح (Reversion)
        if z_score <= -self.dip_threshold_std:
            action = "BUY"
            reason = f"DIP_OVERSOLD_Z_{z_score:.2f}"
        elif z_score >= self.exit_threshold_std:
            action = "SELL"
            reason = f"MEAN_REVERSION_TARGET_MET_Z_{z_score:.2f}"
        else:
            action = "HOLD"
            reason = f"IN_RANGE_Z_{z_score:.2f}"

        return {
            "timestamp": point.timestamp,
            "price": current_price,
            "action": action,
            "z_score": round(z_score, 3),
            "mean": round(mean, 2),
            "std": round(std_dev, 2),
            "flush_active": False,
            "reason": reason
        }

def run_simulation(prices: List[float]) -> Dict[str, any]:
    engine = RangeDipEngine(window_size=10, dip_threshold_std=1.5, flush_drop_pct=0.05)
    capital = 1000.0
    units = 0.0
    trades = 0
    trade_log = []

    for idx, p in enumerate(prices):
        dp = MarketDataPoint(timestamp=1000 + idx * 60, price=p)
        res = engine.update(dp)
        action = res["action"]

        if action == "BUY" and capital > 0:
            units = capital / p
            capital = 0.0
            trades += 1
            trade_log.append({"step": idx, "action": "BUY", "price": p})
        elif (action in ["SELL", "CLOSE_AND_HALT"]) and units > 0:
            capital = units * p
            units = 0.0
            trades += 1
            trade_log.append({"step": idx, "action": action, "price": p})

    final_portfolio = capital + (units * prices[-1] if units > 0 else 0.0)
    pnl_pct = ((final_portfolio - 1000.0) / 1000.0) * 100

    return {
        "initial_capital": 1000.0,
        "final_value": round(final_portfolio, 2),
        "total_trades": trades,
        "pnl_percent": round(pnl_pct, 2),
        "trade_log": trade_log
    }

def run_self_test() -> bool:
    print("[*] Starting Range-Dip & Flush Switch Self-Test...")
    
    # 1. اختبار الحسابات الرياضية وتماسك البيانات
    engine = RangeDipEngine(window_size=5, dip_threshold_std=1.5, flush_drop_pct=0.10)
    flat_series = [100.0] * 5
    for idx, p in enumerate(flat_series):
        res = engine.update(MarketDataPoint(idx, p))
    assert res["action"] == "HOLD", "Flat prices should result in HOLD"
    assert res["z_score"] == 0.0, f"Expected Z-Score 0.0, got {res['z_score']}"

    # 2. اختبار توليد إشارة الشراء (Dip Oversold)
    dip_res = engine.update(MarketDataPoint(6, 90.0))
    # المتوسط = 98، الانحراف ~ 4.0، السعر 90 ينشئ z-score سالب
    assert dip_res["action"] == "BUY", f"Expected BUY signal on dip, got {dip_res['action']}"
    print("[+] Dip Reversion Signal: PASSED")

    # 3. اختبار قاطع الدائرة ضد الانهيار الخاطف (Flush Switch)
    flush_engine = RangeDipEngine(window_size=5, flush_drop_pct=0.08)
    for idx, p in enumerate([100.0, 101.0, 100.5, 102.0, 101.5]):
        flush_engine.update(MarketDataPoint(idx, p))
    # هبوط مفاجئ بأكثر من 8%
    crash_res = flush_engine.update(MarketDataPoint(6, 91.0))
    assert crash_res["action"] == "CLOSE_AND_HALT", f"Flush switch failed, got {crash_res['action']}"
    assert crash_res["flush_active"] is True, "Flush active flag must be True"
    print("[+] Circuit Breaker (Flush Switch): PASSED")

    # 4. محاكاة دورة تداول كاملة
    sim_data = [
        100, 101, 100, 99, 100, 100, 98, 95, 93, 91, # انخفاض للشراء
        94, 98, 102, 104, 101,                         # ارتداد للبيع
        100, 99, 85, 80, 82                            # انهيار لتفعيل القاطع
    ]
    sim_res = run_simulation(sim_data)
    assert sim_res["total_trades"] > 0, "Simulation failed to execute trades"
    print(f"[+] Market Simulation Cycle: PASSED (PnL: {sim_res['pnl_percent']}%)")
    
    print("\n[SUCCESS] All self-tests passed cleanly with 100% precision.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Range-Dip Mean Reversion Trading & Risk Engine")
    parser.add_argument("--self-test", action="store_true", help="Run comprehensive built-in verification suite")
    parser.add_argument("--feed", type=str, help="JSON list of float prices for live batch evaluation")
    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    if args.feed:
        try:
            prices = json.loads(args.feed)
            engine = RangeDipEngine()
            results = []
            for i, p in enumerate(prices):
                res = engine.update(MarketDataPoint(timestamp=i, price=float(p)))
                results.append(res)
            print(json.dumps(results, indent=2))
        except Exception as e:
            print(json.dumps({"error": f"Invalid feed format: {str(e)}"}))
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
