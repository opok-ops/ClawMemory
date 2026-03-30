"""
ClawMemory 召回引擎模块
===========================
负责从记忆库中精准召回与当前任务相关的记忆片段。
支持策略：
- 语义相似度召回（向量检索）
- 关键词召回（FTS）
- 时间衰减召回（近期优先）
- 重要性加权召回
- 对话连续性召回（session 内上下文）
- 主动推送（基于触发器条件）
"""

import re
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from core import (
    QueryEngine, StorageEngine, IndexManager,
    PrivacyLevel, Importance, MemoryEntry, MemoryChunk,
)


@dataclass
class RecallConfig:
    """| 召回配置参数 |"""
    max_results: int = 10
    max_chars: int = 4000
    min_relevance: float = 0.05
    include_categories: Optional[List[str]] = None
    exclude_ids: Optional[List[str]] = None
    min_importance: int = 1
    privacy: PrivacyLevel = PrivacyLevel.INTERNAL
    time_decay_enabled: bool = True
    semantic_weight: float = 0.6
    keyword_weight: float = 0.3
    recency_weight: float = 0.1


@dataclass
class RecallResult:
    chunks: List[MemoryChunk]
    total_found: int
    query_time_ms: float
    strategy_used: str
    token_estimate: int  # Approximate token count for LLM context

    def to_prompt(self, system_prompt_template: str = "") -> str:
        """| 构建 RAG prompt |"""
        if not self.chunks:
            return ""
        fragments = [c.to_prompt_fragment(800) for c in self.chunks]
        combined = "\n\n".join(fragments)
        total_chars = sum(len(f) for f in fragments)
        return (
            f"{system_prompt_template}\n\n"
            f"【相关记忆】（共 {len(self.chunks)} 条，~{self.token_estimate} tokens）\n"
            f"{combined}\n"
            f"【记忆结束】"
        )


class RecallEngine:
    """| 记忆召回引擎 |"""

    def __init__(
        self,
        query_engine: Optional[QueryEngine] = None,
        storage: Optional[StorageEngine] = None,
        index: Optional[IndexManager] = None,
    ):
        self._query = query_engine or QueryEngine(storage, index)
        self._storage = storage or StorageEngine()
        self._config = RecallConfig()

    def recall(
        self,
        query: str,
        agent_id: str = "default",
        session_id: str = "default",
        config: Optional[RecallConfig] = None,
    ) -> RecallResult:
        """| 主召回入口 |"""
        cfg = config or self._config
        start = time.time()

        chunks = self._query.query(
            question=query,
            agent_id=agent_id,
            session_id=session_id,
            max_privacy=cfg.privacy,
            top_k=cfg.max_results,
            categories=cfg.include_categories,
            exclude_ids=cfg.exclude_ids,
        )

        # Filter by relevance
        chunks = [c for c in chunks if c.relevance_score >= cfg.min_relevance]

        # Token estimate (rough: 1 token ≈ 4 chars for Chinese, 3.5 for mixed)
        total_chars = sum(len(c.content) for c in chunks)
        token_estimate = total_chars // 3

        elapsed = (time.time() - start) * 1000

        return RecallResult(
            chunks=chunks,
            total_found=len(chunks),
            query_time_ms=round(elapsed, 2),
            strategy_used="hybrid_semantic",
            token_estimate=token_estimate,
        )

    def recall_by_category(
        self,
        category: str,
        agent_id: str = "default",
        session_id: str = "default",
        limit: int = 5,
        privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
    ) -> RecallResult:
        """| 按分类召回 |"""
        start = time.time()
        entries = self._storage.get_accessible_memories(
            agent_id, session_id, privacy, limit=limit,
        )
        entries = [e for e in entries if e.category == category]

        chunks = []
        for entry in entries:
            content = self._storage.decrypt_content(entry)
            from core import MemoryChunk
            chunk = MemoryChunk(
                id=entry.id, content=content,
                category=entry.category, tags=entry.tags,
                importance=entry.importance.value,
                privacy=entry.privacy.value,
                relevance_score=1.0,
                source_session=entry.source_session,
                created_at=entry.created_at,
                metadata={},
            )
            chunks.append(chunk)

        elapsed = (time.time() - start) * 1000
        return RecallResult(
            chunks=chunks,
            total_found=len(chunks),
            query_time_ms=round(elapsed, 2),
            strategy_used="category_filter",
            token_estimate=sum(len(c.content) for c in chunks) // 3,
        )

    def recall_conversation_history(
        self,
        session_id: str,
        agent_id: str = "default",
        limit: int = 5,
    ) -> RecallResult:
        """| 获取同一会话的历史记忆（对话连续性）|"""
        chunks = self._query.get_conversation_context(
            agent_id, session_id,
            max_privacy=PrivacyLevel.INTERNAL,
            recent_count=limit,
        )
        return RecallResult(
            chunks=chunks,
            total_found=len(chunks),
            query_time_ms=0,
            strategy_used="session_context",
            token_estimate=sum(len(c.content) for c in chunks) // 3,
        )

    def recall_today(
        self,
        agent_id: str = "default",
        session_id: str = "default",
    ) -> RecallResult:
        """| 召回今天的记忆 |"""
        import time
        today_start = time.time() - (time.time() % 86400)
        entries = self._storage.list_memories(
            limit=20,
            privacy=PrivacyLevel.INTERNAL,
        )
        today_entries = [e for e in entries if e.created_at >= today_start]
        chunks = []
        for entry in today_entries[:5]:
            content = self._storage.decrypt_content(entry)
            from core import MemoryChunk
            chunk = MemoryChunk(
                id=entry.id, content=content,
                category=entry.category, tags=entry.tags,
                importance=entry.importance.value,
                privacy=entry.privacy.value,
                relevance_score=0.9,
                source_session=entry.source_session,
                created_at=entry.created_at,
                metadata={},
            )
            chunks.append(chunk)
        return RecallResult(
            chunks=chunks,
            total_found=len(chunks),
            query_time_ms=0,
            strategy_used="today_filter",
            token_estimate=sum(len(c.content) for c in chunks) // 3,
        )

    def proactive_recall(
        self,
        trigger_keywords: List[str],
        agent_id: str = "default",
        session_id: str = "default",
    ) -> List[RecallResult]:
        """| 主动召回：基于触发关键词（如日程、话题切换）|"""
        results = []
        for kw in trigger_keywords:
            result = self.recall(kw, agent_id, session_id)
            if result.total_found > 0:
                results.append(result)
        return results


# ============================================================================
# Context Window Optimizer
# ============================================================================
class ContextWindowOptimizer:
    """| 上下文窗口优化器：将多条记忆压缩为最小可用上下文 |"""

    def __init__(self, max_tokens: int = 3000):
        self.max_tokens = max_tokens

    def pack(self, chunks: List[MemoryChunk]) -> str:
        """| 将记忆碎片打包为紧凑的上下文字符串 |"""
        if not chunks:
            return ""
        # Sort by relevance descending
        sorted_chunks = sorted(chunks, key=lambda c: c.relevance_score, reverse=True)
        total_chars = self.max_tokens * 3  # Rough chars per token
        result_parts = []
        current_chars = 0

        for chunk in sorted_chunks:
            # Take a proportional slice of each chunk (fair allocation)
            budget = total_chars // len(sorted_chunks)
            preview = chunk.content[:budget]
            part = f"[{chunk.category}] {preview}"
            if current_chars + len(part) <= total_chars:
                result_parts.append(part)
                current_chars += len(part)
            else:
                break

        return "\n".join(result_parts)

    def pack_as_json(self, chunks: List[MemoryChunk]) -> str:
        import json
        packed = [c.to_dict() for c in chunks[:self.max_tokens // 3]]
        return json.dumps(packed, ensure_ascii=False)