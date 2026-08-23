"""
MindForge v5.5.1 查询引擎
语义检索 + 知识图谱查询 + 上下文优化
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .storage import StorageEngine, MemoryEntry
from .indexer import IndexEngine
from .types import MemoryLayer

logger = logging.getLogger(__name__)

# v5.4.8 P2-002/P3-003 修复：向量降级只警告一次
_vector_degradation_warned = False


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
               session_id: str = "",
               use_embedding: bool = True) -> RecallResult:
        """搜索记忆

        v5.4.5 新增向量检索两阶段搜索：
        1. 向量召回：通过嵌入向量余弦相似度召回语义相近的记忆
        2. 多路融合：TF-IDF + FTS5 + Fuzzy + 向量，按 id 合并取最高分
        3. 精排：按综合分数排序，取 top_k

        当 use_embedding=False 或 EmbeddingEngine 不可用时，
        自动降级为 TF-IDF + Fuzzy 两路搜索（v5.4.5 之前的行为）。
        """
        import time
        start = time.time()

        # v5.2.8 修复：CLI 等短生命周期进程中，内存 TF-IDF 索引为空，
        # 导致跨进程搜索永远返回 0 结果。搜索前先从持久层水合索引。
        if self.index.needs_hydration:
            self.index.hydrate(self.storage.get_indexable_documents())

        # ===== 第一阶段：多路召回 =====
        # score_map: {memory_id: score}，多路结果按 id 合并取最高分
        score_map = {}

        # 路 1：TF-IDF
        tfidf_results = self.index.search(query, top_k=max_results * 3)
        for doc_id, s in tfidf_results:
            if s >= score_map.get(doc_id, 0.0):
                score_map[doc_id] = s

        # 路 2：Fuzzy（TF-IDF 召回不足时补充）
        positive = sum(1 for _, s in tfidf_results if s >= min_relevance)
        if positive < max_results:
            supplements = self.storage.fuzzy_search(
                query, limit=max_results * 2, threshold=0.1)
            for item in supplements:
                entry = item["entry"]
                s = min(0.95, float(item["score"]))
                if s >= score_map.get(entry.id, 0.0):
                    score_map[entry.id] = s

        # 路 3：FTS5 全文检索
        fts5_used = False
        try:
            conn = self.storage._get_conn()
            fts_results = self.index.fts_search(conn, query, top_k=max_results * 3)
            for doc_id, s in fts_results:
                if s >= score_map.get(doc_id, 0.0):
                    score_map[doc_id] = s
            if fts_results:
                fts5_used = True
                strategy_used = "tfidf+fuzzy+fts5"
            else:
                strategy_used = "tfidf+fuzzy"
        except Exception:
            strategy_used = "tfidf+fuzzy"

        # 路 4：向量召回（v5.4.5 新增，v5.4.8 P2-002/P3-003 修复）
        global _vector_degradation_warned
        if use_embedding:
            # 先检查 engine 是否可用，避免无谓的异常
            engine = self.storage.embedding_engine
            engine_available = engine is not None and getattr(engine, 'is_available', False)

            if engine_available:
                try:
                    vector_results = self.storage.vector_search(
                        query, top_k=max_results * 3,
                        categories=categories, layers=layers)
                    if vector_results:
                        strategy_used = "vector+tfidf+fuzzy" + ("+fts5" if fts5_used else "")
                        for item in vector_results:
                            entry = item["entry"]
                            s = float(item["score"])
                            # v5.4.8 P0 修复：向量分数不做人为提升，取各路最高分
                            # 避免向量分数覆盖更准确的 TF-IDF 匹配
                            existing = score_map.get(entry.id, 0.0)
                            if s > existing:
                                score_map[entry.id] = s
                except Exception as e:
                    # 向量搜索异常（非 engine 不可用情况）
                    if not _vector_degradation_warned:
                        _vector_degradation_warned = True
                        logger.warning(
                            "向量搜索异常，降级为纯文本检索: %s。"
                            "此警告仅显示一次。", e
                        )
            else:
                # engine 不可用，只警告一次
                if not _vector_degradation_warned:
                    _vector_degradation_warned = True
                    logger.warning(
                        "向量引擎不可用（可能未安装 sentence-transformers），"
                        "降级为 TF-IDF + FTS5 + Fuzzy 三路检索。"
                        "语义相似但用词不同的记忆可能无法召回。"
                        "安装命令: pip install sentence-transformers"
                    )

        # 预过滤：按 categories/layers 筛选 score_map，避免非匹配记忆占据排序位
        if categories or layers:
            filtered_map = {}
            for doc_id, score in list(score_map.items()):
                entry = self.storage.get_memory(doc_id)
                if not entry:
                    continue
                if categories and entry.category not in categories:
                    continue
                if layers and entry.layer not in layers:
                    continue
                filtered_map[doc_id] = score
            score_map = filtered_map

        # 合并排序
        raw_results = sorted(score_map.items(), key=lambda x: x[1], reverse=True)

        # ===== 第二阶段：构建结果 =====
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

            content_text = entry.content
            if entry.encrypted:
                content_text = self.storage.decrypt_content(entry)

            chunk = MemoryChunk(
                memory_id=entry.id,
                content=content_text,
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
            strategy_used=strategy_used,
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
