"""
MindForge v5.0 查询引擎
语义检索 + 知识图谱查询 + 上下文优化
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .storage import StorageEngine, MemoryEntry
from .indexer import IndexEngine
from .types import MemoryLayer


@dataclass
class MemoryChunk:
    """记忆片段"""
    memory_id: str
    content: str
    category: str = "general"
    relevance_score: float = 0.0
    layer: MemoryLayer = MemoryLayer.SHORT_TERM
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecallResult:
    """召回结果"""
    chunks: List[MemoryChunk]
    total_found: int
    query_time_ms: float
    strategy_used: str
    token_estimate: int
    layers_used: List[str] = field(default_factory=list)


class QueryEngine:
    """查询引擎"""

    def __init__(self, storage: StorageEngine, index: IndexEngine):
        self.storage = storage
        self.index = index

    def search(self,
               query: str,
               max_results: int = 10,
               min_relevance: float = 0.3,
               categories: Optional[List[str]] = None,
               layers: Optional[List[MemoryLayer]] = None,
               agent_id: str = "",
               session_id: str = "") -> RecallResult:
        """搜索记忆"""
        import time
        start = time.time()

        raw_results = self.index.search(query, top_k=max_results * 3)

        chunks = []
        for doc_id, score in raw_results:
            if score < min_relevance:
                break

            entry = self.storage.get_memory(doc_id, agent_id, session_id)
            if not entry:
                continue

            if categories and entry.category not in categories:
                continue
            if layers and entry.layer not in layers:
                continue

            content = entry.content
            if entry.encrypted:
                content = self.storage.decrypt_content(entry)

            chunk = MemoryChunk(
                memory_id=entry.id,
                content=content,
                category=entry.category,
                relevance_score=score,
                layer=entry.layer,
                tags=entry.tags,
                metadata=entry.metadata,
            )
            chunks.append(chunk)

            if len(chunks) >= max_results:
                break

        elapsed = (time.time() - start) * 1000
        token_estimate = sum(len(c.content) for c in chunks) // 4

        used_layers = list(set(c.layer.value for c in chunks))

        return RecallResult(
            chunks=chunks,
            total_found=len(chunks),
            query_time_ms=round(elapsed, 2),
            strategy_used="semantic_vector",
            token_estimate=token_estimate,
            layers_used=used_layers,
        )

    def get_session_context(self,
                            session_id: str,
                            max_items: int = 20) -> List[MemoryEntry]:
        """获取会话上下文记忆"""
        all_memories = self.storage.list_memories(limit=max_items * 2)
        session_memories = [
            m for m in all_memories
            if m.source_session == session_id
        ]
        return session_memories[:max_items]

    def get_by_layer(self, layer: MemoryLayer, limit: int = 50) -> List[MemoryEntry]:
        """按层级获取记忆"""
        return self.storage.list_memories(layer=layer, limit=limit)
