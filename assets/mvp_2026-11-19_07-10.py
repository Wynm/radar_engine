import sqlite3
import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class LocalMemoryEngine:
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                fact_key TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                stage INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def upsert_fact(self, session_id, key, value, stage=1):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM memory_context WHERE session_id = ? AND fact_key = ?
        ''', (session_id, key))
        row = cursor.fetchone()
        
        if row:
            cursor.execute('''
                UPDATE memory_context SET fact_value = ?, stage = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND fact_key = ?
            ''', (value, stage, session_id, key))
        else:
            cursor.execute('''
                INSERT INTO memory_context (session_id, fact_key, fact_value, stage)
                VALUES (?, ?, ?, ?)
            ''', (session_id, key, value, stage))
        
        conn.commit()
        conn.close()
        return {"status": "success", "session_id": session_id, "key": key}

    def get_context(self, session_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT fact_key, fact_value, stage, updated_at FROM memory_context WHERE session_id = ?
        ''', (session_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{"key": r[0], "value": r[1], "stage": r[2], "updated_at": r[3]} for r in rows]

# تهيئة المحرك للتطبيق
memory_engine = LocalMemoryEngine()

class MemoryAPIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/memory':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                session_id = data.get('session_id', 'default')
                key = data.get('key')
                value = data.get('value')
                stage = data.get('stage', 1)
                
                if not key or not value:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"error": "Missing key or value"}')
                    return

                result = memory_engine.upsert_fact(session_id, key, value, stage)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == '/api/memory':
            query_params = parse_qs(parsed_url.query)
            session_id = query_params.get('session_id', ['default'])[0]
            
            context = memory_engine.get_context(session_id)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(context).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_self_test():
    print("[*] Running Self-Test for Local Memory Engine...")
    test_engine = LocalMemoryEngine(":memory:")
    
    # 1. Test Upsert
    res = test_engine.upsert_fact("session_99", "user_pref", "Dark Mode", stage=2)
    assert res["status"] == "success", "Upsert failed!"
    
    # 2. Test Conflict Update
    test_engine.upsert_fact("session_99", "user_pref", "Light Mode", stage=3)
    
    # 3. Test Retrieval
    ctx = test_engine.get_context("session_99")
    assert len(ctx) == 1, "Context count mismatch!"
    assert ctx[0]["value"] == "Light Mode", "Conflict resolution failed!"
    assert ctx[0]["stage"] == 3, "Stage update failed!"
    
    print("[+] Self-Test Passed Successfully! Core engine is operational.")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--self-test':
        run_self_test()
    else:
        port = 8080
        server = HTTPServer(('0.0.0.0', port), MemoryAPIHandler)
        print(f"[*] Riverse AI Agent Memory Micro-SaaS running on port {port}...")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.server_close()
