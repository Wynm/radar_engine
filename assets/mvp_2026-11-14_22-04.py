#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Micro-SaaS API Wrapper & Self-Test Engine
Standard Library Only (No external pip dependencies required)
"""

import sys
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class SaaSHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/v1/send-notification':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                recipient = data.get("recipient")
                message = data.get("message")
                
                if not recipient or not message:
                    self._send_response(400, {"status": "error", "message": "Missing recipient or message"})
                    return
                
                # محاكاة إرسال الرسالة عبر بوابة خارجية بأمان
                response_payload = {
                    "status": "success",
                    "transaction_id": "TXN-987654321",
                    "recipient": recipient,
                    "provider": "Secure-Wrapper-API"
                }
                self._send_response(200, response_payload)
            except Exception as e:
                self._send_response(500, {"status": "error", "message": str(e)})
        else:
            self._send_response(404, {"status": "error", "message": "Endpoint not found"})

    def _send_response(self, code, payload):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def log_message(self, format, *args):
        # تعطيل طباعة السجلات الافتراضية للحفاظ على نظافة المخرجات
        return

def run_server(port=8080):
    server = HTTPServer(('127.0.0.1', port), SaaSHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server

def self_test():
    print("[*] Starting Micro-SaaS Wrapper Self-Test...")
    port = 8090
    server = HTTPServer(('127.0.0.1', port), SaaSHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    time.sleep(0.5)

    url = f"http://127.0.0.1:{port}/api/v1/send-notification"
    payload = json.dumps({"recipient": "+123456789", "message": "Hello via Micro-SaaS Wrapper!"}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if response.status == 200 and res_data.get("status") == "success":
                print("[SUCCESS] Self-Test Passed Successfully! API Wrapper is fully operational.")
                sys.exit(0)
            else:
                print(f"[FAILED] Unexpected response: {res_data}")
                sys.exit(1)
    except Exception as e:
        print(f"[FAILED] Self-Test encountered an exception: {e}")
        sys.exit(1)
    finally:
        server.shutdown()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--self-test':
        self_test()
    else:
        print("Running Micro-SaaS Server on http://127.0.0.1:8080 (Use --self-test to verify)")
        srv = HTTPServer(('127.0.0.1', 8080), SaaSHandler)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped by user.")
