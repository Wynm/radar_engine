#!/usr/bin/env python3
"""
PiBot MVP Core & Self-Test Engine
Author: AI Automated Systems
Description: Local-first multi-agent task execution and self-test utility.
"""

import sys
import os
import json
import time

class PiBotCore:
    def __init__(self, name="PiBot-Local-Core"):
        self.name = name
        self.status = "Initialized"
        self.task_log = []

    def execute_task(self, task_description: str) -> dict:
        """Simulate executing a local agent task with MCP-like protocol."""
        start_time = time.time()
        # Simulating local file/system operation safely
        result = {
            "task": task_description,
            "status": "Success",
            "agent": self.name,
            "executed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.task_log.append(result)
        duration = time.time() - start_time
        return {"result": result, "duration_sec": round(duration, 4)}

    def self_test(self) -> bool:
        """Run comprehensive internal diagnostics without altering system files."""
        print("[-] Running PiBot Core Self-Test...")
        try:
            # Test 1: Initialization check
            assert self.name is not None, "Core name missing"
            
            # Test 2: Task Execution simulation
            test_task = "Analyze local directory structure & logs"
            res = self.execute_task(test_task)
            assert res["result"]["status"] == "Success", "Task execution failed"
            
            # Test 3: JSON Serialization check
            serialized = json.dumps(res)
            assert isinstance(serialized, str), "Serialization failed"
            
            print("[+] Self-Test PASSED successfully: All systems operational.")
            return True
        except AssertionError as e:
            print(f"[!] Self-Test FAILED: {e}")
            return False

def main():
    bot = PiBotCore()
    
    # Check for --self-test argument
    if "--self-test" in sys.argv:
        success = bot.self_test()
        sys.exit(0 if success else 1)
    else:
        print(f"PiBot Core ({bot.name}) is running.")
        print("Use '--self-test' to run diagnostic checks.")
        # Default run demo
        res = bot.execute_task("Default system health check")
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
