"""
MindForge v5.4.6 REST API Server
================================

标准 REST API，让非 Python 应用（JS、Go、移动端）也能直接调用 MindForge。

基于 Python 内置 http.server，无需额外依赖（FastAPI/Flask 可选）。

端点概览：
  GET    /api/memories          列出记忆（?limit=&offset=&category=）
  POST   /api/memories          添加记忆
  GET    /api/memories/{id}     获取单条记忆
  PUT    /api/memories/{id}     更新记忆
  DELETE /api/memories/{id}     删除记忆
  GET    /api/search            搜索记忆（?q=&limit=&min_relevance=）
  GET    /api/stats             统计信息
  GET    /api/health            健康检查
  GET    /api/tags              标签列表
  POST   /api/import            导入记忆（JSON body）
  GET    /api/export            导出记忆（JSON）

启动方式：
  MindForge serve --api
  MindForge serve --api --port 9000
  MindForge serve --api --host 0.0.0.0
"""

import json
import logging
import sys
import os
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)


class MindForgeAPIHandler(BaseHTTPRequestHandler):
    """REST API 请求处理器"""

    # MindForge 实例由 server 注入
    mindforge = None

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def do_OPTIONS(self):
        self._send_json({"status": "ok"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                result = self.mindforge.health_check()
                self._send_json(result)

            elif path == "/api/stats":
                result = self.mindforge.stats()
                self._send_json(result)

            elif path == "/api/tags":
                entries = self.mindforge.list(limit=100000)
                tag_counts = {}
                for e in entries:
                    for tag in e.tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                self._send_json({"tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)})

            elif path == "/api/search":
                q = qs.get("q", [""])[0]
                if not q:
                    self._send_json({"error": "Missing query parameter 'q'"}, 400)
                    return
                limit = int(qs.get("limit", ["10"])[0])
                min_relevance = float(qs.get("min_relevance", ["0.3"])[0])
                categories = qs.get("categories", None)
                result = self.mindforge.search(
                    query=q,
                    max_results=limit,
                    min_relevance=min_relevance,
                    categories=categories,
                )
                chunks = []
                if hasattr(result, "chunks"):
                    for chunk in result.chunks:
                        chunks.append({
                            "id": chunk.memory_id,
                            "content": chunk.content,
                            "category": chunk.category,
                            "relevance_score": chunk.relevance_score,
                            "tags": chunk.tags if hasattr(chunk, "tags") else [],
                        })
                self._send_json({"query": q, "results": chunks, "total": len(chunks)})

            elif path == "/api/memories":
                limit = int(qs.get("limit", ["50"])[0])
                offset = int(qs.get("offset", ["0"])[0])
                category = qs.get("category", [None])[0]
                entries = self.mindforge.list(
                    category=category,
                    limit=limit,
                    offset=offset,
                )
                memories = []
                for e in entries:
                    memories.append(e.to_dict() if hasattr(e, "to_dict") else vars(e))
                self._send_json({"memories": memories, "total": len(memories), "limit": limit, "offset": offset})

            elif path.startswith("/api/memories/"):
                mem_id = path.split("/api/memories/")[1]
                entry = self.mindforge.get(mem_id)
                if entry:
                    self._send_json(entry.to_dict() if hasattr(entry, "to_dict") else vars(entry))
                else:
                    self._send_json({"error": "Memory not found"}, 404)

            elif path == "/api/export":
                entries = self.mindforge.list(limit=100000)
                memories = [e.to_dict() if hasattr(e, "to_dict") else vars(e) for e in entries]
                self._send_json({"version": "5.4.6", "total": len(memories), "memories": memories})

            elif path == "/":
                self._send_json({
                    "name": "MindForge REST API",
                    "version": "5.4.6",
                    "endpoints": [
                        "GET /api/memories", "POST /api/memories",
                        "GET /api/memories/{id}", "PUT /api/memories/{id}",
                        "DELETE /api/memories/{id}",
                        "GET /api/search", "GET /api/stats",
                        "GET /api/health", "GET /api/tags",
                        "POST /api/import", "GET /api/export",
                    ],
                })

            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.exception("API error")
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            body = self._read_body()
            if body is None:
                self._send_json({"error": "Invalid JSON body"}, 400)
                return

            if path == "/api/memories":
                content = body.get("content", "")
                if not content:
                    self._send_json({"error": "Missing 'content' field"}, 400)
                    return
                entry = self.mindforge.add(
                    content=content,
                    category=body.get("category", "general"),
                    tags=body.get("tags", []),
                )
                self._send_json(entry.to_dict() if hasattr(entry, "to_dict") else vars(entry), 201)

            elif path == "/api/import":
                memories = body.get("memories", [])
                imported = 0
                failed = 0
                for mem in memories:
                    try:
                        self.mindforge.add(
                            content=mem.get("content", ""),
                            category=mem.get("category", "general"),
                            tags=mem.get("tags", []),
                        )
                        imported += 1
                    except Exception:
                        failed += 1
                self._send_json({"imported": imported, "failed": failed})

            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.exception("API error")
            self._send_json({"error": str(e)}, 500)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            body = self._read_body()
            if body is None:
                self._send_json({"error": "Invalid JSON body"}, 400)
                return

            if path.startswith("/api/memories/"):
                mem_id = path.split("/api/memories/")[1]
                success = self.mindforge.update(
                    memory_id=mem_id,
                    content=body.get("content"),
                    category=body.get("category"),
                    tags=body.get("tags"),
                )
                if success:
                    self._send_json({"status": "updated", "id": mem_id})
                else:
                    self._send_json({"error": "Update failed or memory not found"}, 404)
            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.exception("API error")
            self._send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path.startswith("/api/memories/"):
                mem_id = path.split("/api/memories/")[1]
                success = self.mindforge.delete(mem_id)
                if success:
                    self._send_json({"status": "deleted", "id": mem_id})
                else:
                    self._send_json({"error": "Delete failed or memory not found"}, 404)
            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.exception("API error")
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)


def start_api_server(mindforge_instance, host="127.0.0.1", port=8080):
    """启动 REST API 服务器

    Args:
        mindforge_instance: MindForge 实例
        host: 绑定地址
        port: 端口
    """
    MindForgeAPIHandler.mindforge = mindforge_instance

    server = HTTPServer((host, port), MindForgeAPIHandler)
    print(f"MindForge REST API serving on http://{host}:{port}")
    print(f"  Endpoints: /api/memories, /api/search, /api/stats, /api/health, ...")
    print(f"  Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAPI server stopped.")
        server.server_close()
