"""
MindForge v5.4.8 REST API Server
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
import time
import hmac
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
from MindForge import __version__ as MF_VERSION

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

# v5.4.8 安全修复：请求体大小限制（10MB）
MAX_BODY_SIZE = 10 * 1024 * 1024


# v5.4.7 修复 H-7：简单速率限制器
class _RateLimiter:
    """基于 IP 的请求速率限制"""
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, client_ip: str) -> bool:
        """返回 True 表示允许，False 表示限流"""
        now = time.time()
        with self._lock:
            # 清理过期记录
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if now - t < self.window
            ]
            if len(self._requests[client_ip]) >= self.max_requests:
                return False
            self._requests[client_ip].append(now)
            return True


# v5.4.8 安全修复：分端点速率限制
_rate_limiter = _RateLimiter(max_requests=100, window_seconds=60)      # 通用：100次/分钟
_rate_limiter_import = _RateLimiter(max_requests=10, window_seconds=60) # 导入：10次/分钟
_rate_limiter_search = _RateLimiter(max_requests=60, window_seconds=60) # 搜索：60次/分钟


def _safe_int(value, default=10, min_val=1, max_val=10000):
    """v5.4.7 修复 H-1：安全解析整数参数"""
    try:
        v = int(value)
        return max(min_val, min(max_val, v))
    except (ValueError, TypeError):
        return default


def _safe_float(value, default=0.3, min_val=0.0, max_val=1.0):
    """v5.4.7 修复 H-1：安全解析浮点参数"""
    try:
        v = float(value)
        return max(min_val, min(max_val, v))
    except (ValueError, TypeError):
        return default


class MindForgeAPIHandler(BaseHTTPRequestHandler):
    """REST API 请求处理器"""

    # MindForge 实例由 server 注入
    mindforge = None

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # v5.4.8 安全修复：CORS 限制为配置的源（默认仅允许同源）
        allowed_origin = os.environ.get("MINDFORGE_CORS_ORIGIN", "")
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        # v5.4.8 安全修复：请求体大小限制
        if content_length > MAX_BODY_SIZE:
            self._send_json({"error": f"Request body too large (max {MAX_BODY_SIZE // 1024 // 1024}MB)"}, 413)
            return None
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _check_auth(self):
        """验证 Bearer Token（通过 MINDFORGE_API_KEY 环境变量配置）
        
        v5.4.8 安全策略：
        - 设置了 MINDFORGE_API_KEY：正常验证 Bearer Token
        - 未设置时：
          - 绑定 localhost (127.0.0.1/::1)：允许访问（开发模式）
          - 绑定其他地址：拒绝所有请求，除非显式设置 MINDFORGE_ALLOW_NO_AUTH=1
        """
        api_key = os.environ.get("MINDFORGE_API_KEY", "")
        if not api_key:
            # 检查是否绑定到非本地地址
            server_addr = self.server.server_address[0] if self.server else "127.0.0.1"
            is_local = server_addr in ("127.0.0.1", "::1", "localhost")
            allow_no_auth = os.environ.get("MINDFORGE_ALLOW_NO_AUTH", "") == "1"
            
            if is_local or allow_no_auth:
                # 本地开发模式：记录一次性警告
                if not getattr(self.__class__, '_auth_warned', False):
                    logger.warning(
                        "MINDFORGE_API_KEY not set — running in development mode (localhost only). "
                        "Set MINDFORGE_API_KEY for production use."
                    )
                    self.__class__._auth_warned = True
                return True
            else:
                # 非本地绑定且未设 API Key：拒绝
                if not getattr(self.__class__, '_no_key_rejected_warned', False):
                    logger.error(
                        "Rejecting request: MINDFORGE_API_KEY not set and server bound to %s. "
                        "Set MINDFORGE_API_KEY or MINDFORGE_ALLOW_NO_AUTH=1 to allow unauthenticated access.",
                        server_addr
                    )
                    self.__class__._no_key_rejected_warned = True
                self._send_json({"error": "Authentication required — set MINDFORGE_API_KEY"}, 401)
                return False
        
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if hmac.compare_digest(token, api_key):
                return True
        self._send_json({"error": "Unauthorized"}, 401)
        return False

    def do_OPTIONS(self):
        self._send_json({"status": "ok"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        # v5.4.8 安全修复：分端点速率限制
        client_ip = self.client_address[0]
        if path == "/api/search":
            if not _rate_limiter_search.check(client_ip):
                self._send_json({"error": "Search rate limit exceeded (60/min). Try again later."}, 429)
                return
        else:
            if not _rate_limiter.check(client_ip):
                self._send_json({"error": "Rate limit exceeded. Try again later."}, 429)
                return

        if path != "/api/health" and not self._check_auth():
            return

        try:
            if path == "/api/health":
                result = self.mindforge.health_check()
                # v5.4.8 安全修复：未认证时只返回基本状态
                api_key = os.environ.get("MINDFORGE_API_KEY", "")
                if not api_key:
                    result = {
                        "status": result.get("status", "unknown"),
                        "total_memories": result.get("total_memories", 0),
                    }
                self._send_json(result)

            elif path == "/api/stats":
                result = self.mindforge.stats()
                self._send_json(result)

            elif path == "/api/tags":
                conn = self.mindforge.storage._get_conn()
                rows = conn.execute(
                    "SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != '' AND tags != '[]'"
                ).fetchall()
                tag_counts = {}
                for row in rows:
                    try:
                        tags = json.loads(row[0]) if row[0].strip().startswith('[') else [t.strip() for t in row[0].split(',') if t.strip()]
                    except (json.JSONDecodeError, TypeError):
                        continue
                    for tag in tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                self._send_json({"tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)})

            elif path == "/api/search":
                q = qs.get("q", [""])[0]
                if not q:
                    self._send_json({"error": "Missing query parameter 'q'"}, 400)
                    return
                # v5.4.7 修复 H-1：安全解析参数
                limit = _safe_int(qs.get("limit", ["10"])[0], default=10, min_val=1, max_val=1000)
                min_relevance = _safe_float(qs.get("min_relevance", ["0.3"])[0], default=0.3, min_val=0.0, max_val=1.0)
                categories = qs.get("categories", None)
                # v5.4.9 新增：标签、时间范围、高亮参数
                tags = qs.get("tags", None)
                if tags and isinstance(tags, list) and len(tags) == 1:
                    tags = [t.strip() for t in tags[0].split(",") if t.strip()]
                created_after = qs.get("created_after", [None])[0]
                created_before = qs.get("created_before", [None])[0]
                highlight = qs.get("highlight", ["0"])[0] in ("1", "true", "True")

                search_kwargs = {
                    "query": q,
                    "max_results": limit,
                    "min_relevance": min_relevance,
                    "categories": categories,
                    "tags": tags,
                    "highlight": highlight,
                }
                if created_after:
                    try:
                        search_kwargs["created_after"] = float(created_after)
                    except (ValueError, TypeError):
                        pass
                if created_before:
                    try:
                        search_kwargs["created_before"] = float(created_before)
                    except (ValueError, TypeError):
                        pass

                result = self.mindforge.search(**search_kwargs)
                chunks = []
                if hasattr(result, "chunks"):
                    for chunk in result.chunks:
                        item = {
                            "id": chunk.memory_id,
                            "content": chunk.content,
                            "category": chunk.category,
                            "relevance_score": chunk.relevance_score,
                            "tags": chunk.tags if hasattr(chunk, "tags") else [],
                        }
                        # v5.4.9：返回高亮内容
                        if highlight and hasattr(chunk, "highlighted_content") and chunk.highlighted_content:
                            item["highlighted_content"] = chunk.highlighted_content
                        chunks.append(item)
                self._send_json({
                    "query": q,
                    "results": chunks,
                    "total": len(chunks),
                    "strategy": getattr(result, "strategy_used", ""),
                    "query_time_ms": getattr(result, "query_time_ms", 0),
                })

            elif path == "/api/memories":
                # v5.4.7 修复 H-1：安全解析参数
                limit = _safe_int(qs.get("limit", ["50"])[0], default=50, min_val=1, max_val=10000)
                offset = _safe_int(qs.get("offset", ["0"])[0], default=0, min_val=0, max_val=1000000)
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
                # v5.4.9：子端点路由
                if "/" in mem_id:
                    parts = mem_id.split("/", 1)
                    mem_id = parts[0]
                    sub = parts[1]
                    if sub == "versions":
                        # GET /api/memories/{id}/versions
                        versions = self.mindforge.list_versions(mem_id)
                        self._send_json({"memory_id": mem_id, "versions": versions, "total": len(versions)})
                        return
                    elif sub == "diff":
                        # GET /api/memories/{id}/diff?version_a=...&version_b=...
                        version_a = qs.get("version_a", [None])[0]
                        version_b = qs.get("version_b", [None])[0]
                        diff = self.mindforge.diff_versions(mem_id, version_a, version_b)
                        self._send_json(diff)
                        return
                entry = self.mindforge.get(mem_id)
                if entry:
                    self._send_json(entry.to_dict() if hasattr(entry, "to_dict") else vars(entry))
                else:
                    self._send_json({"error": "Memory not found"}, 404)

            elif path == "/api/export":
                entries = self.mindforge.list(limit=100000)
                memories = [e.to_dict() if hasattr(e, "to_dict") else vars(e) for e in entries]
                self._send_json({"version": MF_VERSION, "total": len(memories), "memories": memories})

            # v5.4.9 新增：Webhook 管理端点
            elif path == "/api/webhooks":
                webhooks = self.mindforge.event_bus.list_webhooks()
                self._send_json({"webhooks": webhooks, "total": len(webhooks)})

            elif path == "/api/events/stats":
                stats = self.mindforge.event_bus.stats()
                history = self.mindforge.event_bus.delivery_history(limit=20)
                self._send_json({"stats": stats, "recent_deliveries": history})

            elif path == "/":
                self._send_json({
                    "name": "MindForge REST API",
                    "version": MF_VERSION,
                    "endpoints": [
                        "GET /api/memories", "POST /api/memories",
                        "GET /api/memories/{id}", "PUT /api/memories/{id}",
                        "DELETE /api/memories/{id}",
                        "GET /api/memories/{id}/versions",
                        "GET /api/memories/{id}/diff",
                        "GET /api/search", "GET /api/stats",
                        "GET /api/health", "GET /api/tags",
                        "POST /api/import", "GET /api/export",
                        "GET /api/webhooks", "POST /api/webhooks",
                        "DELETE /api/webhooks?url=...",
                        "GET /api/events/stats",
                    ],
                })

            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.error("API error: %s", type(e).__name__)
            self._send_json({"error": "Internal server error"}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # v5.4.8 安全修复：导入端点单独限流
        client_ip = self.client_address[0]
        if path == "/api/import":
            if not _rate_limiter_import.check(client_ip):
                self._send_json({"error": "Import rate limit exceeded (10/min). Try again later."}, 429)
                return
        else:
            if not _rate_limiter.check(client_ip):
                self._send_json({"error": "Rate limit exceeded. Try again later."}, 429)
                return

        if not self._check_auth():
            return

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
                    importance=body.get("importance"),
                    starred=body.get("starred"),
                    source_agent=body.get("source_agent", ""),
                )
                self._send_json(entry.to_dict() if hasattr(entry, "to_dict") else vars(entry), 201)

            elif path == "/api/import":
                memories = body.get("memories", [])
                # v5.4.8 安全修复：导入批次大小限制
                MAX_IMPORT_BATCH = 10000
                if len(memories) > MAX_IMPORT_BATCH:
                    self._send_json({"error": f"Too many memories (max {MAX_IMPORT_BATCH})"}, 400)
                    return
                imported = 0
                failed = 0
                for mem in memories:
                    try:
                        self.mindforge.add(
                            content=mem.get("content", ""),
                            category=mem.get("category", "general"),
                            tags=mem.get("tags", []),
                            importance=mem.get("importance"),
                            starred=mem.get("starred"),
                            source_agent=mem.get("source_agent", ""),
                        )
                        imported += 1
                    except Exception:
                        failed += 1
                self._send_json({"imported": imported, "failed": failed})

            # v5.4.9 新增：注册 Webhook
            elif path == "/api/webhooks":
                url = body.get("url", "")
                if not url:
                    self._send_json({"error": "Missing 'url' field"}, 400)
                    return
                events = body.get("events")
                secret = body.get("secret", "")
                timeout = body.get("timeout", 10.0)
                max_retries = body.get("max_retries", 3)
                config = self.mindforge.event_bus.register_webhook(
                    url=url, events=events, secret=secret,
                    timeout=timeout, max_retries=max_retries,
                )
                self._send_json({"success": True, "webhook": config.to_dict()}, 201)

            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.error("API error: %s", type(e).__name__)
            self._send_json({"error": "Internal server error"}, 500)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if not self._check_auth():
            return

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
                    importance=body.get("importance"),
                    starred=body.get("starred"),
                )
                if success:
                    self._send_json({"status": "updated", "id": mem_id})
                else:
                    self._send_json({"error": "Update failed or memory not found"}, 404)
            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.error("API error: %s", type(e).__name__)
            self._send_json({"error": "Internal server error"}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if not self._check_auth():
            return

        try:
            if path.startswith("/api/memories/"):
                mem_id = path.split("/api/memories/")[1]
                success = self.mindforge.delete(mem_id)
                if success:
                    self._send_json({"status": "deleted", "id": mem_id})
                else:
                    self._send_json({"error": "Delete failed or memory not found"}, 404)
            # v5.4.9 新增：注销 Webhook
            elif path == "/api/webhooks":
                parsed = urlparse(self.path)
                qs = parse_qs(parsed.query)
                url = qs.get("url", [""])[0]
                if not url:
                    self._send_json({"error": "Missing 'url' query parameter"}, 400)
                    return
                removed = self.mindforge.event_bus.unregister_webhook(url)
                if removed:
                    self._send_json({"success": True, "removed": url})
                else:
                    self._send_json({"error": "Webhook not found"}, 404)
            else:
                self._send_json({"error": "Not found", "path": path}, 404)

        except Exception as e:
            logger.error("API error: %s", type(e).__name__)
            self._send_json({"error": "Internal server error"}, 500)

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
