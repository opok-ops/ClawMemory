"""
ClawMemory Claude Code 适配器
===============================
将 ClawMemory 集成到 Claude Code（Codex）中。

使用方式：
1. 设置环境变量 CLAWMEMORY_DB_PATH 和 CLAWMEMORY_KEY_FILE
2. 在 Claude Code 的 system prompt 中引用 clawmemory:// 协议
3. 通过 claude_desktop_config.json 配置 MCP 工具

示例 system prompt 片段：
---
你有一个外部记忆系统 ClawMemory。当需要回忆过去的信息时，使用 
memory_search 工具搜索相关记忆。当完成重要工作后，使用 memory_add 
保存关键结果到记忆中。

记忆协议：
- memory_search(query, max_results=5)
- memory_add(content, category, tags, privacy)
- memory_get(memory_id)
- memory_list(category, limit=20)
---

环境变量：
- CLAWMEMORY_DB_PATH: SQLite 数据库路径
- CLAWMEMORY_KEY_FILE: 加密密钥文件路径
- CLAWMEMORY_PASSWORD: 密码（通过系统密钥链获取更安全）
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from ..core import (
    QueryEngine, StorageEngine, IndexManager,
    PrivacyLevel, Importance, MemoryEntry,
    init_engine, get_engine,
)
from ..modules import RecallEngine, RecallConfig, PrivacyEngine, TaxonomyManager


# ============================================================================
# Claude Code Config
# ============================================================================
def get_config() -> Dict[str, str]:
    return {
        "db_path": os.environ.get(
            "CLAWMEMORY_DB_PATH",
            str(Path.home() / ".clawmemory" / "data" / "store" / "memory.db")
        ),
        "key_file": os.environ.get(
            "CLAWMEMORY_KEY_FILE",
            str(Path.home() / ".clawmemory" / "data" / ".key")
        ),
        "password": os.environ.get("CLAWMEMORY_PASSWORD", ""),
    }


# ============================================================================
# Claude Code Tools (MCP-compatible)
# ============================================================================
class ClaudeCodeAdapter:
    """
    Claude Code / Codex 适配器
    提供 MCP (Model Context Protocol) 工具接口
    """

    def __init__(self):
        self._config = get_config()
        self._initialized = False
        self._engine: Optional[Any] = None
        self._storage: Optional[StorageEngine] = None
        self._recall: Optional[RecallEngine] = None
        self._privacy: Optional[PrivacyEngine] = None
        self._taxonomy: Optional[TaxonomyManager] = None

    def init(self) -> bool:
        """| 初始化 |"""
        password = self._config.get("password", "")
        if password:
            init_engine(password)
        else:
            from ..core import get_engine
            engine = get_engine()
            if not engine.has_key():
                print("[ClawMemory] No key found. Run python cli/main.py init first.")
                return False

        db_path = Path(self._config["db_path"])
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._storage = StorageEngine(db_path)
        self._index = IndexManager()
        self._recall = RecallEngine(storage=self._storage, index=self._index)
        self._privacy = PrivacyEngine(self._storage)
        self._taxonomy = TaxonomyManager()
        self._initialized = True
        return True

    # ---- Tool implementations (MCP style) ----

    def memory_search(self, query: str, max_results: int = 5, category: Optional[str] = None) -> Dict:
        """| 搜索记忆（Claude Code 工具）|"""
        if not self._initialized:
            return {"error": "Not initialized", "results": []}
        cfg = RecallConfig(
            max_results=max_results,
            include_categories=[category] if category else None,
        )
        result = self._recall.recall(
            query=query,
            agent_id="claude_code",
            session_id=os.environ.get("CODECRAFT_SESSION_ID", "default"),
            config=cfg,
        )
        return {
            "found": result.total_found,
            "query_ms": result.query_time_ms,
            "results": [
                {"id": c.id, "content": c.content[:300], "category": c.category,
                 "relevance": round(c.relevance_score, 3), "importance": c.importance}
                for c in result.chunks
            ],
        }

    def memory_add(
        self,
        content: str,
        category: str = "work",
        tags: Optional[List[str]] = None,
        privacy: str = "INTERNAL",
        importance: str = "MEDIUM",
    ) -> Dict:
        """| 添加记忆（Claude Code 工具）|"""
        if not self._initialized:
            return {"error": "Not initialized", "id": None}

        if tags is None:
            tags = self._taxonomy.suggest_tags(content)

        # Privacy scan
        privacy_level = PrivacyLevel.from_string(privacy)
        scan = self._privacy.scan(content)
        if scan.suggested_privacy.to_int() > privacy_level.to_int():
            privacy_level = scan.suggested_privacy

        entry = self._storage.add_memory(
            content=content,
            category=category,
            tags=tags,
            privacy=privacy_level,
            importance=Importance.from_string(importance),
            source_session=os.environ.get("CODECRAFT_SESSION_ID", "default"),
            source_agent="claude_code",
        )

        # Index
        self._index.index_memory(
            entry.id, content,
            metadata={"category": category, "tags": tags, "importance": entry.importance.value},
        )

        return {
            "id": entry.id,
            "category": category,
            "tags": tags,
            "privacy": privacy_level.value,
            "created_at": entry.created_at,
        }

    def memory_list(self, category: Optional[str] = None, limit: int = 20) -> Dict:
        """| 列出记忆 |"""
        if not self._initialized:
            return {"error": "Not initialized", "memories": []}
        entries = self._storage.list_memories(category=category, limit=limit)
        return {
            "total": self._storage.count_memories(category),
            "memories": [
                {"id": e.id, "category": e.category, "tags": e.tags,
                 "preview": e.plaintext_preview, "created_at": e.created_at}
                for e in entries
            ],
        }

    def memory_get(self, memory_id: str) -> Dict:
        """| 获取单条记忆 |"""
        if not self._initialized:
            return {"error": "Not initialized"}
        entry = self._storage.get_memory(memory_id)
        if not entry:
            return {"error": "Not found"}
        content = self._storage.decrypt_content(entry)
        return {
            "id": entry.id,
            "content": content,
            "category": entry.category,
            "tags": entry.tags,
            "privacy": entry.privacy.value,
            "created_at": entry.created_at,
        }

    def memory_delete(self, memory_id: str, hard: bool = False) -> Dict:
        if not self._initialized:
            return {"error": "Not initialized"}
        success = self._storage.delete_memory(memory_id, actor="claude_code")
        if success:
            self._index.remove_memory(memory_id)
        return {"success": success}

    def memory_stats(self) -> Dict:
        if not self._initialized:
            return {"error": "Not initialized"}
        stats = self._storage.get_stats()
        return {
            "total": stats["total"],
            "by_privacy": stats["by_privacy"],
            "top_categories": stats["top_categories"],
            "db_size_mb": round(stats["db_size_bytes"] / 1024 / 1024, 2),
        }

    def memory_context(self, query: str, max_chars: int = 1500) -> str:
        """| 获取记忆上下文字符串（用于注入 Claude Code prompt）|"""
        if not self._initialized:
            return ""
        from ..core import QueryEngine
        engine = QueryEngine(self._storage, self._index)
        return engine.build_memory_context(
            question=query,
            agent_id="claude_code",
            session_id=os.environ.get("CODECRAFT_SESSION_ID", "default"),
            max_chars=max_chars,
        )


# ============================================================================
# MCP Server Entry (for claude_desktop_config)
# ============================================================================
def run_mcp_server():
    """| 以 MCP 服务器模式运行（可通过 claude_desktop_config.json 接入）|"""
    adapter = ClaudeCodeAdapter()
    if not adapter.init():
        print("Failed to initialize ClawMemory adapter", file=sys.stderr)
        sys.exit(1)

    print("[ClawMemory] MCP Server running. Tools available:")
    print("  - memory_search  - memory_add  - memory_list")
    print("  - memory_get     - memory_delete - memory_stats")
    print("  - memory_context - memory_audit")

    # MCP stdin/stdout protocol
    import sys
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            request = json.loads(line.strip())
            method = request.get("method", "")
            params = request.get("params", {})

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "tools": [
                            {"name": "memory_search", "description": "Search memories"},
                            {"name": "memory_add", "description": "Add a memory"},
                            {"name": "memory_list", "description": "List memories"},
                            {"name": "memory_get", "description": "Get a memory by ID"},
                            {"name": "memory_delete", "description": "Delete a memory"},
                            {"name": "memory_stats", "description": "Get memory statistics"},
                            {"name": "memory_context", "description": "Get memory context for prompt injection"},
                        ]
                    }
                }
                print(json.dumps(response), flush=True)
            elif method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments", {})
                func = getattr(adapter, tool_name, None)
                if func:
                    result = func(**args)
                    response = {"jsonrpc": "2.0", "id": request.get("id"), "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}
                else:
                    response = {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}), flush=True)


if __name__ == "__main__":
    run_mcp_server()