"""
ClawMemory OpenClaw 适配器
===========================
将 ClawMemory 集成到 OpenClaw 系统中。
提供：
- Memory Search Tool（供 Agent 调用）
- Session Context Injection（自动注入会话记忆）
- Privacy-Aware Memory Access（隐私分级）
- Trigger-Based Memory Recall（基于触发词主动召回）

集成方式：注册为 OpenClaw 的 memory adapter，通过内部 API 通信。
"""

import json
import time
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
from threading import Lock

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ..core import (
    QueryEngine, StorageEngine, IndexManager,
    PrivacyLevel, Importance, MemoryEntry, MemoryChunk,
    init_engine,
)
from ..modules import (
    RecallEngine, RecallConfig,
    PrivacyEngine, PrivacyScanResult,
    TaxonomyManager,
)


# ============================================================================
# OpenClaw Memory Adapter
# ============================================================================
class OpenClawMemoryAdapter:
    """
    OpenClaw 记忆适配器
    ====================
    注册到 OpenClaw 的 memory 子系统中，
    提供统一记忆访问接口给 Agent。
    
    使用方式：
    1. 在 OpenClaw 配置中设置 memory.adapter=clawmemory
    2. 在 Agent 的 system prompt 中自动注入相关记忆
    3. Agent 通过 memory_search / memory_add / memory_get 工具调用
    """

    NAME = "clawmemory"
    VERSION = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        self._initialized = False
        self._lock = Lock()
        self._query_engine: Optional[QueryEngine] = None
        self._storage: Optional[StorageEngine] = None
        self._index: Optional[IndexManager] = None
        self._recall: Optional[RecallEngine] = None
        self._privacy: Optional[PrivacyEngine] = None
        self._taxonomy: Optional[TaxonomyManager] = None

    # --------------------------------------------------------------------------
    # Initialization
    # --------------------------------------------------------------------------
    def init(self, password: Optional[str] = None) -> bool:
        """| 初始化适配器（首次运行或恢复）|"""
        with self._lock:
            if self._initialized:
                return True

            # Init encryption engine
            if password:
                init_engine(password)
            else:
                # Try auto-load from existing key
                from ..core import get_engine
                engine = get_engine()
                if not engine.has_key():
                    print("[ClawMemory] No encryption key found. Run init first.")
                    return False

            # Init core engines
            self._storage = StorageEngine()
            self._index = IndexManager()
            self._query_engine = QueryEngine(self._storage, self._index)
            self._recall = RecallEngine(self._query_engine, self._storage, self._index)
            self._privacy = PrivacyEngine(self._storage)
            self._taxonomy = TaxonomyManager()

            self._initialized = True
            print("[ClawMemory] Adapter initialized successfully.")
            return True

    def is_initialized(self) -> bool:
        return self._initialized

    # --------------------------------------------------------------------------
    # Agent Tools (注册为 OpenClaw 工具)
    # --------------------------------------------------------------------------
    def tool_search(
        self,
        query: str,
        agent_id: str = "openclaw",
        session_id: str = "default",
        max_results: int = 10,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """| memory_search 工具实现 |"""
        if not self._initialized:
            return {"error": "ClawMemory not initialized. Run init first.", "results": []}

        cfg = RecallConfig(
            max_results=max_results,
            include_categories=[category] if category else None,
        )
        result = self._recall.recall(query, agent_id, session_id, cfg)

        return {
            "found": result.total_found,
            "query_ms": result.query_time_ms,
            "strategy": result.strategy_used,
            "tokens_estimate": result.token_estimate,
            "results": [
                {
                    "id": c.id,
                    "content": c.content[:500],
                    "category": c.category,
                    "tags": c.tags,
                    "importance": c.importance,
                    "privacy": c.privacy,
                    "relevance_score": c.relevance_score,
                    "created_at": c.created_at,
                }
                for c in result.chunks
            ],
        }

    def tool_add(
        self,
        content: str,
        agent_id: str = "openclaw",
        session_id: str = "default",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy: str = "INTERNAL",
        importance: str = "MEDIUM",
        auto_categorize: bool = True,
    ) -> Dict[str, Any]:
        """| memory_add 工具实现 |"""
        if not self._initialized:
            return {"error": "ClawMemory not initialized. Run init first.", "id": None}

        # Auto-categorize
        if auto_categorize and not category:
            category = self._taxonomy.suggest_category(content)

        # Auto-tag
        if tags is None:
            tags = self._taxonomy.suggest_tags(content)

        # Privacy scan
        privacy_level = PrivacyLevel.from_string(privacy)
        if auto_categorize:
            scan_result = self._privacy.scan(content)
            if scan_result.suggested_privacy.to_int() > privacy_level.to_int():
                privacy_level = scan_result.suggested_privacy

        # Add memory
        entry = self._storage.add_memory(
            content=content,
            category=category or "general",
            tags=tags,
            privacy=privacy_level,
            importance=Importance.from_string(importance),
            source_session=session_id,
            source_agent=agent_id,
        )

        # Update index
        self._index.index_memory(
            entry.id, content,
            metadata={
                "category": category,
                "tags": tags,
                "importance": entry.importance.value,
                "created_at": entry.created_at,
            },
        )

        return {
            "id": entry.id,
            "category": category,
            "tags": tags,
            "privacy": privacy_level.value,
            "importance": importance,
            "suggested_privacy": scan_result.suggested_privacy.value if auto_categorize else None,
            "created_at": entry.created_at,
        }

    def tool_get(
        self,
        memory_id: str,
        agent_id: str = "openclaw",
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """| memory_get 工具实现 |"""
        if not self._initialized:
            return {"error": "ClawMemory not initialized.", "memory": None}

        entry = self._storage.get_memory(memory_id, agent_id, session_id)
        if not entry:
            return {"error": "Memory not found", "memory": None}

        # Privacy check
        allowed, reason = self._privacy.check_access(
            entry, agent_id, session_id, PrivacyLevel.INTERNAL,
        )
        if not allowed:
            return {"error": f"Access denied: {reason}", "memory": None}

        content = self._storage.decrypt_content(entry)
        return {
            "id": entry.id,
            "content": content,
            "category": entry.category,
            "tags": entry.tags,
            "privacy": entry.privacy.value,
            "importance": entry.importance.name,
            "source_session": entry.source_session,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "access_count": entry.access_count,
            "metadata": json.loads(entry.metadata_json),
        }

    def tool_list(
        self,
        agent_id: str = "openclaw",
        session_id: str = "default",
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """| memory_list 工具实现 |"""
        if not self._initialized:
            return {"error": "Not initialized", "memories": []}

        entries = self._storage.list_memories(
            category=category, limit=limit, offset=offset,
        )
        # Filter by privacy
        accessible = [
            e for e in entries
            if self._privacy.check_access(e, agent_id, session_id, PrivacyLevel.INTERNAL)[0]
        ]
        return {
            "total": self._storage.count_memories(category),
            "returned": len(accessible),
            "memories": [
                {
                    "id": e.id,
                    "category": e.category,
                    "tags": e.tags,
                    "privacy": e.privacy.value,
                    "importance": e.importance.name,
                    "created_at": e.created_at,
                    "preview": e.plaintext_preview,
                }
                for e in accessible
            ],
        }

    def tool_update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy: Optional[str] = None,
        importance: Optional[str] = None,
        agent_id: str = "openclaw",
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """| memory_update 工具实现 |"""
        if not self._initialized:
            return {"error": "Not initialized", "success": False}

        success = self._storage.update_memory(
            entry_id=memory_id,
            content=content,
            category=category,
            tags=tags,
            privacy=PrivacyLevel.from_string(privacy) if privacy else None,
            importance=Importance.from_string(importance) if importance else None,
            actor=agent_id,
            session_id=session_id,
        )
        if success and content:
            self._index.index_memory(memory_id, content, metadata={})

        return {"success": success}

    def tool_delete(
        self,
        memory_id: str,
        agent_id: str = "openclaw",
        session_id: str = "default",
        hard: bool = False,
    ) -> Dict[str, Any]:
        """| memory_delete 工具实现 |"""
        if not self._initialized:
            return {"error": "Not initialized", "success": False}

        success = self._storage.delete_memory(memory_id, agent_id, session_id, hard)
        if success:
            self._index.remove_memory(memory_id)

        return {"success": success}

    def tool_audit(
        self,
        memory_id: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """| memory_audit 工具：查询审计日志 |"""
        if not self._initialized:
            return {"error": "Not initialized", "records": []}

        records = self._storage.get_audit_log(memory_id, actor, limit)
        return {
            "records": [
                {
                    "id": r.id,
                    "memory_id": r.memory_id,
                    "action": r.action,
                    "actor": r.actor,
                    "timestamp": r.timestamp,
                    "privacy_level": r.privacy_level,
                    "fields_accessed": r.fields_accessed,
                    "session_id": r.session_id,
                }
                for r in records
            ]
        }

    def tool_stats(self) -> Dict[str, Any]:
        """| memory_stats 工具：获取统计信息 |"""
        if not self._initialized:
            return {"error": "Not initialized"}
        stats = self._storage.get_stats()
        return {
            "total_memories": stats["total"],
            "by_privacy": stats["by_privacy"],
            "by_importance": stats["by_importance"],
            "top_categories": stats["top_categories"],
            "db_size_mb": round(stats["db_size_bytes"] / 1024 / 1024, 2),
            "db_path": stats["db_path"],
        }

    # --------------------------------------------------------------------------
    # Session Context Injection (自动调用)
    # --------------------------------------------------------------------------
    def get_session_memory_context(
        self,
        question: str,
        agent_id: str = "openclaw",
        session_id: str = "default",
        max_chars: int = 2000,
    ) -> str:
        """| 获取会话记忆上下文（注入到 Agent prompt）|"""
        if not self._initialized:
            return ""
        return self._query_engine.build_memory_context(
            question=question,
            agent_id=agent_id,
            session_id=session_id,
            max_chars=max_chars,
        )

    def get_conversation_context(
        self,
        agent_id: str = "openclaw",
        session_id: str = "default",
    ) -> str:
        """| 获取当前会话上下文 |"""
        if not self._initialized:
            return ""
        chunks = self._query_engine.get_conversation_context(agent_id, session_id)
        if not chunks:
            return ""
        return "\n".join(c.to_prompt_fragment(300) for c in chunks[:3])

    # --------------------------------------------------------------------------
    # Privacy Tools
    # --------------------------------------------------------------------------
    def grant_memory_access(
        self,
        memory_id: str,
        to_agent: str,
        duration_hours: Optional[float] = None,
    ) -> Dict[str, Any]:
        """| 授予其他 Agent 访问权限 |"""
        if not self._initialized:
            return {"error": "Not initialized"}
        success = self._privacy.grant_access(memory_id, to_agent, duration_hours=duration_hours)
        return {"success": success}

    def revoke_memory_access(self, memory_id: str, to_agent: str) -> Dict[str, Any]:
        if not self._initialized:
            return {"error": "Not initialized"}
        success = self._privacy.revoke_access(memory_id, to_agent)
        return {"success": success}

    def scan_privacy(self, text: str) -> Dict[str, Any]:
        """| 扫描文本隐私敏感度 |"""
        if not self._initialized:
            return {"error": "Not initialized"}
        result = self._privacy.scan(text)
        return result.to_dict()

    def compliance_report(self) -> Dict[str, Any]:
        """| 生成合规报告 |"""
        if not self._initialized:
            return {"error": "Not initialized"}
        return self._privacy.generate_compliance_report()


# ============================================================================
# Singleton
# ============================================================================
_adapter: Optional[OpenClawMemoryAdapter] = None

def get_adapter(config: Optional[Dict] = None) -> OpenClawMemoryAdapter:
    global _adapter
    if _adapter is None:
        _adapter = OpenClawMemoryAdapter(config)
    return _adapter