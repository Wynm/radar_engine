import sys
import json
import time
import urllib.request
import urllib.error

class SteamIdlerSimulator:
    """
    نواة محاكاة أتمتة وإدارة حسابات Steam (Micro-SaaS Core)
    تقوم بمحاكاة تشغيل الألعاب لإدارة ساعات اللعب وحالة الحساب.
    """
    def __init__(self, config=None):
        self.config = config or {"username": "DefaultUser", "games": [730, 570], "status": "Online"}
        self.running_sessions = {}

    def start_idle(self, game_id):
        session_id = f"session_{game_id}_{int(time.time())}"
        self.running_sessions[game_id] = {
            "session_id": session_id,
            "start_time": time.time(),
            "status": "Idling"
        }
        return f"Started idling for Game ID: {game_id} [Session: {session_id}]"

    def stop_idle(self, game_id):
        if game_id in self.running_sessions:
            duration = time.time() - self.running_sessions[game_id]["start_time"]
            del self.running_sessions[game_id]
            return f"Stopped idling for Game ID: {game_id}. Total duration: {round(duration, 2)}s"
        return f"Game ID {game_id} not found in active sessions."

    def run_self_test(self):
        print("[*] Running SteamIdler Simulator Self-Test...")
        # اختبار بدء الجلسة
        msg1 = self.start_idle(730)
        print(f"  - Test 1: {msg1}")
        assert 730 in self.running_sessions, "Failed to start idle session!"

        # اختبار إيقاف الجلسة
        msg2 = self.stop_idle(730)
        print(f"  - Test 2: {msg2}")
        assert 730 not in self.running_sessions, "Failed to stop idle session!"

        print("[+] Self-Test Completed Successfully: 100% Operational.")
        return True

if __name__ == "__main__":
    app = SteamIdlerSimulator()
    if "--self-test" in sys.argv:
        success = app.run_self_test()
        sys.exit(0 if success else 1)
    else:
        print("Steam Idler Micro-SaaS Core is ready. Run with --self-test to verify.")
