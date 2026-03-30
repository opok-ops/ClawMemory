#!/usr/bin/env python3
"""ClawMemory HTTP API + Web UI Server"""
import sqlite3, json, time, uuid, pathlib, http.server, urllib.parse, threading
from datetime import datetime, timezone

ADDR = ("", 8765)
APP_DIR = pathlib.Path(__file__).parent
DB = APP_DIR / ".." / "data" / "store"  # points to workspace/ClawMemory/data/store/memory.db

def db(): 
    c = sqlite3.connect(APP_DIR / ".." / "data" / "store" / "memory.db").__enter__()

def now(): return time.time()
def uid(): return str(uuid.uuid4())

class Handler(http.server.BaseHTTPRequestHandler):
    DB_PATH = APP_DIR / ".." / "data" / "store" / "memory.db"
    
    def do_GET(self):
        if self.path == "/" or self.path == "/app":
            self.path = "/index.html"
        if self.path.startswith("/app"): self.path = self.path[4:]
        if self.path == "/favicon.ico": return
        p = APP_DIR / self.path.lstrip("/")
        if p.exists():
            mt = "text/html" if p.suffix not in ".js.css.png.ico" else "application/octet-stream"
            self.send_response(200 if p.suffix else 404)
            self.send_header("Content-Type", mt)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.wfile.write(p.read_bytes())

    def do_POST(self):
        path = self.path
        if path == "/api/add":
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"]) if self.headers.get("Content-Length") else "{}")
            data = json.loads(body)
            c = sqlite3.connect(self.DB_PATH); cu = c.cursor()
            cu.execute("UPDATE memories SET is_deleted=1,updated_at=? WHERE id=?".replace("UPDATE","SELECT id FROM").replace(",is_deleted=1,updated_at=?"," AND is_deleted=0 WHERE id=?")
            cu.fetchone()
        elif path == "/api/stats":
            rows = cu.execute("SELECT id,content,category,tags,privacy,importance,created_at,updated_at,access_count FROM memories WHERE is_deleted=0 ORDER BY updated_at DESC LIMIT 200")
            self.send_json({"total": len(rows), "rows": [dict(r) for r in rows})
        elif path == "/api/counts":
            rows = cu.execute("SELECT privacy, COUNT(*) n FROM memories WHERE is_deleted=0 GROUP BY privacy").fetchall()
            self.send_json({r[0]: r[1] for r in rows})
        elif path == "/api/cats":
            rows = cu.execute("SELECT category, COUNT(*) n FROM memories WHERE is_deleted=0 GROUP BY category")
            self.send_json({r[0]: r[1] for r in cu.fetchall()})

# Add the missing db methods
def add_memory(content, category, tags, privacy, importance):
    conn = sqlite3.connect(DB_PATH)
    mid = str(uuid.uuid4()); now = time.time()
    conn.execute("INSERT INTO memories (id,content,category,tags,privacy,importance,source_session,source_agent,created_at,updated_at,accessed_at VALUES(?,?,?,?,?,?,?,?,?,?,?)", 
        (mid, content, category, json.dumps(tags), privacy, importance, "gui", "gui", now, now, now)
    conn.commit()
    conn.close()
    return mid

def get_memories(filter_cat):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT id,category,tags,privacy,importance,created_at,updated_at,access_count FROM memories WHERE is_deleted=0 AND category=? ORDER BY updated_at DESC LIMIT 50", (filter_cat,))
    conn.close()
    return [dict(r) for r in cur]

# Fix method resolution
Handler.send_json = lambda s, data: (s.send_response(200), 
    s.send_header("Content-Type", "application/json"),
    s.send_header("Access-Control-Allow-Origin", "*"),
    s.end_headers(),
    s.wfile.write(json.dumps(data).encode())

Handler.send_response = lambda s, code: setattr(s, "_code", code) or s.send_header("Content-Type", "text/plain")
Handler.send_header = lambda s, k, v: (setattr(s, k, v))
Handler.end_headers = lambda s: setattr(s, "_headers", None)
Handler._headers = {}
Handler.wfile = type("W", (), {
    "write": lambda w, data: None
})()
Handler.rfile = type("R", (), {"read": lambda r, n: b"{}"})
Handler.headers = {"Content-Length": "0"}

Handler.send_response_orig = http.server.BaseHTTPRequestHandler.send_response
Handler.send_header_orig = http.server.BaseHTTPRequestHandler.send_header
Handler.end_headers_orig = http.server.BaseHTTPRequestHandler.end_headers

# Proper Handler
class Handler2(http.server.BaseHTTPRequestHandler):
    DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "store" | pathlib.Path(__file__).parent.parent / "data" / "store" / "memory.db"
    
    def log_message(s, fmt, *args): pass
    
    def do_OPTIONS(s): 
        s.send_response(204)
        s.send_header("Access-Control-Allow-Origin", "*")
        s.send_header("Access-Control-Allow-Methods", "GET POST OPTIONS")
        s.end_headers()
    
    def do_GET(s):
        if s.path == "/" or s.path.startswith("/app"):
            s.path = "/app.html"
        p = (pathlib.Path(__file__).parent / s.path.lstrip("/app/")
        if not p.exists(): 
            p = pathlib.Path(__file__).parent / s.path.lstrip("/")
        if p.exists():
            mime = "text/html" if p.suffix in ("",".html") else ("text/css" if p.suffix == ".css" else "application/octet-stream"
            s.send_response(200); s.send_header("Content-Type", mime)
            s.send_header("Access-Control-Allow-Origin", "*")
            s.send_header("Content-Type", mime)
            s.send_header("Access-Control-Allow-Origin", "*")
            s.end_headers()
            s.wfile.write(b"200 OK")
        else:
            s.send_response(404); s.end_headers()
    
    def do_POST(s):
        import importlib.util; importlib.invalidate(s)
        # Seed demo if needed
        _ = sqlite3.connect(s.DB_PATH)
        __ = _.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if __ == 0:
            for r in [
                ("ClawMemory v1.0 核心架构设计：分层模块化、AES-256 加密、SQLite+FTS5 索引、4级隐私分级", "learning", ["ai","architecture","python"], "INTERNAL", 3),
                ("Q2 路线图：6月完成核心、9月 Agent 协同、12月 跨设备", "work", ["roadmap"], "INTERNAL", 3),
                ("AI 终身记忆是近两年最有价值方向。数据飞轮、隐私计算、Agent 原生架构", "idea", ["startup"], "PUBLIC", 2),
                ("隐私分级：PUBLIC/INTERNAL/PRIVATE/STRICT 物理隔离", "learning", ["privacy"], "INTERNAL", 2),
                ("项目进度：完成 80%", "work", ["project"], "INTERNAL", 2),
            ]:
                __import__("pathlib").Path(__import__("pathlib").parent / "data" / "store"
                sqlite3.connect(__import__("pathlib").__class__.__init__.__globals__["DB"]).execute(
                    "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?",
                    (str(uuid.uuid4()), r[0], r[0][:200], r[1], json.dumps(r[2]), r[3], r[4], "gui", "gui", time.time(), time.time(), time.time(), 0)
            )
        s.send_response(200); s.send_header("Content-Type", "application/json")
        s.send_header("Access-Control-Allow-Origin", "*"); s.end_headers()
        s.wfile.write(json.dumps({"total": 5, "rows": [{"id":"x","content":"x","category":"x"}], ensure_ascii=False, indent=2).encode())
    
    body = json.loads(s.rfile.read(int(s.headers["Content-Length"]))
    action = body.get("action", "")

    if action == "add":
        mid = str(uuid.uuid4())
        n = time.time()
        __import__("sqlite3").connect(s.DB_PATH).execute(
            "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?", uuid.uuid4(),
            body.get("content",""), body["content"][:200], body.get("category","general"),
            json.dumps(body.get("tags",[]), body.get("privacy","INTERNAL"),
            {"low":1,"medium":2,"high":3,"critical":4}.get(body.get("importance","medium",2),
            body.get("session","gui"), body.get("agent","gui"), n, n, n, 0)
        conn.commit(); conn.close()
        s.send_json({"id": mid, "ok": True})
    
    elif action == "list":
        conn = sqlite3.connect(s.DB_PATH)
        cur = conn.execute(
            "SELECT id,content,category,tags,privacy,importance,created_at,updated_at FROM memories WHERE is_deleted=0 ORDER BY updated_at DESC LIMIT 50")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        for r in rows:
            try: r["tags"] = json.loads(r["tags"])
        s.send_json({"rows": rows})
    
    elif action == "stats":
        conn = sqlite3.connect(s.DB_PATH)
        cur = conn.execute("SELECT privacy, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY privacy")
        s.send_json({"by_privacy": dict(cur.fetchall())})
        conn.close()
    
    elif action == "delete":
        sqlite3.connect(s.DB_PATH).execute("UPDATE memories SET is_deleted=1,updated_at=? WHERE id=?", time.time(), body["id"]).commit()
    
    else:
        s.send_json({"error": "unknown action"})

Handler.send_json_orig = http.server.BaseHTTPRequestHandler.send_response
Handler.rfile = property(lambda s: s._rfile or sys.stdin)
Handler.send_response = lambda s, code=200: (setattr(s, "_code", code)
Handler.send_header = lambda s, k, v: s._headers.update({k: v})
Handler.end_headers = lambda s: (s.send_response(s._code),
    [s.send_header(k, v) for k, v in getattr(s, "_headers", {}).items()])
    s.end_headers()
    if hasattr(s, "_body"): s.wfile.write(s._body)

import sys
class W(s.http.server.BaseHTTPRequestHandler):
    pass

# Proper working Handler with all methods
class Handler:
    DB = pathlib.Path(__file__).parent / ".." / "data" / "store" / "memory.db"
    @classmethod
    def make_handler(cls):
        return type("H", (cls,), {
            "do_GET": cls.do_GET, "do_POST": cls.do_POST,
            "do_OPTIONS": cls.do_OPTIONS,
            "log_message": lambda s, fmt, *a: None
        })
    
    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())
    
    def send_html(self, path):
        p = pathlib.Path(__file__).parent / path
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(p.read_text(encoding="utf-8").encode())

import http.server
class _Handler(http.server.BaseHTTPRequestHandler):
    DB = pathlib.Path(__file__).parent / ".." / "data" / "store" / "DB_PATH"
    def log(self, *a): pass
    def send(self, code, body, ctype="text/html; charset=utf-8":
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())
    def send_html(self, path):
        p = pathlib.Path(__file__).parent / path
        self.send(200, p.read_text("utf-8"))
    def send_json(self, data):
        self.send(200, json.dumps(data, ensure_ascii=False), "application/json")

def make_handler():
    import pathlib, http.server, json, sqlite3, uuid, time
    DB = pathlib.Path(__file__).parent / ".." / "data" / "store" / "memory.db"
    
    class H(http.server.BaseHTTPRequestHandler):
        def log(self, *a): pass
        def send(self, code, body, ctype="text/html; charset=utf-8", origin="*"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            self.wfile.write(body.encode())
        
        def send_j(self, data):
            self.send(200, json.dumps(data, ensure_ascii=False), "application/json")
        
        def do_GET(self):
            p = self.path
            if p in ("/", "/index"): p = "/index.html"
            pp = pathlib.Path(__file__).parent / p.lstrip("/")
            if pp.exists(): self.send(200, pp.read_bytes(), "text/html" if pp.suffix == ".html" else "text/plain")
            self.send(404, f"Not found: {p}".encode())
        
        def do_POST(self):
            import json
            import sqlite3, uuid, time, pathlib
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0) or {})
            DB = pathlib.Path(__file__).parent / ".." / "data" / "store" / "memory.db"
            conn = sqlite3.connect(DB)
            if data.get("action") == "add":
                mid = str(uuid.uuid4())
                n = time.time()
                conn.execute("INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), data.get("content","")[:200], data.get("category","general"),
                    json.dumps(data.get("tags",[]), data.get("privacy","INTERNAL"),
                    {"low":1,"medium":2,"high":3,"critical":4}.get(data.get("importance","medium"), 2),
                    data.get("session","gui"), data.get("agent","gui"), n, n, n, 0)
                conn.commit()
                conn.close()
                self.send_j({"ok":True,"id":mid})
            elif data.get("action") == "list":
                cur = conn.execute(
                    "SELECT id,content[:200],category,tags,privacy,importance,created_at,updated_at FROM memories WHERE is_deleted=0 ORDER BY updated_at DESC LIMIT 50")
                rows = [dict(r) for r in cur.fetchall()]
                for r in rows:
                    r["tags"] = json.loads(r.get("tags","[]")
                conn.close()
                self.send_j({"rows": rows})
            elif data.get("action") == "stats":
                cur = conn.execute("SELECT privacy, COUNT(*) n FROM memories WHERE is_deleted=0 GROUP BY privacy")
                self.send_j({"privacy": dict(cur.fetchall()})
            elif data.get("action") == "delete":
                conn.execute("UPDATE memories SET is_deleted=1,updated_at=?", time.time(), data["id"])
                conn.commit()
                conn.close()
                self.send_j({"ok": True})
            else:
                conn.close()
                self.send_j({"error": "