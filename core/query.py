"""
ClawMemory 查询引擎
===========================
混合检索：语义向量 + FTS 全文 + 规则过滤 + 综合评分。
Agent 调用统一入口。
"""

import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .storage import StorageEngine, PrivacyLevel, Importance, MemoryEntry
from .indexer import IndexManager


# ============================================================================
# Query Result
# ============================================================================
@dataclass
class MemoryChunk:
    """| 供给 Agent 的记忆碎片（已解密）|"""
    id: str
    content: str
    category: str
    tags: List[str]
    importance: int
    privacy: str
    relevance_score: float
    source_session: str
    created_at: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "importance": self.importance,
            "privacy": self.privacy,
            "relevance_score": self.relevance_score,
            "source_session": self.source_session,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def to_prompt_fragment(self, max_chars: int = 1500) -> str:
        """| 转换为 Agent 可直接使用的 prompt 片段 |"""
        content_preview = self.content[:max_chars]
        return (
            f"[记忆#{self.id[:8]}] [{self.category}] [重要性:{self.importance}] "
            f"[相关性:{self.relevance_score:.3f}]\n"
            f"{content_preview}\n"
            f"---标签: {', '.join(self.tags) if self.tags else '无'}"
        )


# ============================================================================
# Query Engine
# ============================================================================
class QueryEngine:
    """| 统一查询引擎，支持多种检索策略 |"""

    def __init__(
        self,
        storage: Optional[StorageEngine] = None,
        index_manager: Optional[IndexManager] = None,
    ):
        self._storage = storage or StorageEngine()
        self._index = index_manager or IndexManager()
        self._query_cache: Dict[str, Tuple[List[MemoryChunk], float]] = {}
        self._cache_ttl = 60.0  # 60s cache

    # --------------------------------------------------------------------------
    # Primary: Semantic Hybrid Search
    # --------------------------------------------------------------------------
    def query(
        self,
        question: str,
        agent_id: str = "default",
        session_id: str = "default",
        max_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
        top_k: int = 10,
        categories: Optional[List[str]] = None,
        exclude_ids: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> List[MemoryChunk]:
        """| 主要查询接口：混合语义检索 |"""
        start = time.time()
        cache_key = f"{question}|{agent_id}|{max_privacy.value}|{top_k}"
        if use_cache and cache_key in self._query_cache:
            chunks, _ = self._query_cache[cache_key]
            return chunks

        # Step 1: Semantic vector search
        raw_results = self._index.search(
            question, top_k=top_k * 2,
            category=categories[0] if categories and len(categories) == 1 else None,
        )

        # Step 2: FTS5 fallback for keyword hits
        fts_results = self._storage.search_fulltext(
            question, max_results=top_k * 2, min_privacy=PrivacyLevel.PUBLIC,
            exclude_ids=[r[0] for r in raw_results] if raw_results else None,
        )

        # Step 3: Merge and deduplicate
        seen_ids = set()
        merged: List[Tuple[MemoryEntry, float]] = []

        for memory_id, vec_score in raw_results:
            if memory_id in seen_ids:
                continue
            seen_ids.add(memory_id)
            entry = self._storage.get_memory(memory_id, agent_id, session_id)
            if entry and self._check_access(entry, agent_id, session_id, max_privacy):
                merged.append((entry, vec_score))

        for entry in fts_results:
            if entry.id in seen_ids:
                continue
            seen_ids.add(entry.id)
            if self._check_access(entry, agent_id, session_id, max_privacy):
                # FTS results use a lower base score
                merged.append((entry, 0.5))

        # Step 4: Score and rank
        chunks = self._build_chunks(merged, question)
        chunks = [c for c in chunks if c.relevance_score > 0.05]

        # Step 5: Privacy filter (final check)
        chunks = [
            c for c in chunks
            if PrivacyLevel.from_string(c.privacy).to_int() <= max_privacy.to_int()
        ]

        elapsed = time.time() - start
        if elapsed > 0.2:
            print(f"[QueryEngine] Slow query ({elapsed:.3f}s): {question[:50]}")

        if use_cache:
            self._query_cache[cache_key] = (chunks, elapsed)

        return chunks[:top_k]

    # --------------------------------------------------------------------------
    # Conversational Context: recent memories + session continuity
    # --------------------------------------------------------------------------
    def get_conversation_context(
        self,
        agent_id: str,
        session_id: str,
        max_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
        recent_count: int = 5,
    ) -> List[MemoryChunk]:
        """| 获取对话上下文：最近的记忆碎片 |"""
        entries = self._storage.get_accessible_memories(
            agent_id=agent_id,
            session_id=session_id,
            max_privacy=max_privacy,
            limit=recent_count,
        )
        chunks = []
        for entry in entries:
            if entry.source_session == session_id:
                content = self._storage.decrypt_content(entry)
                chunks.append(self._entry_to_chunk(entry, content, 0.8))
        return chunks

    # --------------------------------------------------------------------------
    # Agent Memory Injection (RAG-ready fragments)
    # --------------------------------------------------------------------------
    def build_memory_context(
        self,
        question: str,
        agent_id: str = "default",
        session_id: str = "default",
        max_chars: int = 3000,
        privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
    ) -> str:
        """| 构建可直接注入 Agent 的记忆上下文（RAG prompt fragment）|"""
        chunks = self.query(
            question=question,
            agent_id=agent_id,
            session_id=session_id,
            max_privacy=privacy,
            top_k=5,
        )
        fragments = [c.to_prompt_fragment(max_chars // len(chunks) if chunks else 500) for c in chunks]
        combined = "\n\n".join(fragments)
        return (
            f"【相关记忆片段】（共 {len(chunks)} 条）\n"
            f"{combined}\n"
            f"【记忆片段结束】"
        ) if chunks else ""

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    def _check_access(
        self,
        entry: MemoryEntry,
        agent_id: str,
        session_id: str,
        max_privacy: PrivacyLevel,
    ) -> bool:
        if entry.privacy.to_int() > max_privacy.to_int():
            return False
        return self._storage.check_privacy_access(entry, agent_id, session_id)

    def _build_chunks(
        self,
        entries_with_scores: List[Tuple[MemoryEntry, float]],
        query: str,
    ) -> List[MemoryChunk]:
        chunks = []
        for entry, vec_score in entries_with_scores:
            try:
                content = self._storage.decrypt_content(entry)
            except Exception:
                continue  # Skip if decryption fails
            meta = {}
            try:
                import json
                meta = json.loads(entry.metadata_json)
            except Exception:
                pass
            chunk = MemoryChunk(
                id=entry.id,
                content=content,
                category=entry.category,
                tags=entry.tags,
                importance=entry.importance.value,
                privacy=entry.privacy.value,
                relevance_score=vec_score,
                source_session=entry.source_session,
                created_at=entry.created_at,
                metadata=meta,
            )
            chunks.append(chunk)
        # Sort by composite score: relevance * importance_boost
        chunks.sort(
            key=lambda c: c.relevance_score * (1.0 + 0.2 * (c.importance - 1)),
            reverse=True,
        )
        return chunks

    def _entry_to_chunk(self, entry: MemoryEntry, content: str, score: float) -> MemoryChunk:
        import json
        meta = {}
        try:
            meta = json.loads(entry.metadata_json)
        except Exception:
            pass
        return MemoryChunk(
            id=entry.id,
            content=content,
            category=entry.category,
            tags=entry.tags,
            importance=entry.importance.value,
            privacy=entry.privacy.value,
            relevance_score=score,
            source_session=entry.source_session,
            created_at=entry.created_at,
            metadata=meta,
        )

    def clear_cache(self):
        self._query_cache.clear()


# ============================================================================
# Lightweight Session Context (for heartbeat/session use)
# ============================================================================
def get_session_context(
    agent_id: str = "default",
    session_id: str = "default",
) -> str:
    """| 获取轻量级会话上下文（单次快速调用）|"""
    engine = QueryEngine()
    chunks = engine.get_conversation_context(agent_id, session_id, recent_count=3)
    if not chunks:
        return ""
    return "\n".join(c.to_prompt_fragment(500) for c in chunks)