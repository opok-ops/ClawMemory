"""
ClawMemory 整合器模块
===========================
将多条相关记忆整合为结构化的上下文摘要。
支持：
- 多记忆片段聚合
- 话题一致性分析
- 时间线重建
- 关键信息提取
- 摘要压缩（降低 token 消耗）
"""

import json
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from core import MemoryChunk, MemoryEntry, StorageEngine


@dataclass
class MemorySummary:
    """| 记忆摘要 |"""
    topic: str
    summary_text: str
    key_facts: List[str]
    sentiment: str  # positive / neutral / negative / mixed
    period: str    # e.g. "2026-03-01 to 2026-03-15"
    memory_count: int
    confidence: float  # 0-1

    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "summary": self.summary_text,
            "key_facts": self.key_facts,
            "sentiment": self.sentiment,
            "period": self.period,
            "memory_count": self.memory_count,
            "confidence": self.confidence,
        }


@dataclass
class MemoryTimeline:
    """| 记忆时间线 |"""
    events: List[Dict]  # [{date, content, category, importance}]
    period: str

    def to_list(self) -> List[Dict]:
        return self.events


class MemoryIntegrator:
    """| 记忆整合器：将多个碎片整合为连贯上下文 |"""

    def __init__(self, storage: Optional[StorageEngine] = None):
        self._storage = storage or StorageEngine()

    def integrate(
        self,
        chunks: List[MemoryChunk],
        mode: str = "summary",
    ) -> Dict:
        """| 主整合接口 |"""
        if not chunks:
            return {"type": "empty", "content": ""}

        if mode == "summary":
            return self._summarize(chunks)
        elif mode == "timeline":
            return self._build_timeline(chunks)
        elif mode == "facts":
            return self._extract_facts(chunks)
        elif mode == "full":
            summary = self._summarize(chunks)
            timeline = self._build_timeline(chunks)
            return {"type": "full", "summary": summary, "timeline": timeline}
        else:
            return {"type": "raw", "chunks": [c.to_dict() for c in chunks]}

    def _summarize(self, chunks: List[MemoryChunk]) -> Dict:
        """| 生成记忆摘要 |"""
        if not chunks:
            return {"type": "summary", "content": ""}

        # Extract common topic from categories
        categories = [c.category for c in chunks]
        most_common_cat = max(set(categories), key=categories.count)

        # Extract key facts (first sentences of each chunk)
        key_facts = []
        for chunk in chunks[:5]:
            sentences = chunk.content.split("。")
            if sentences:
                key_facts.append(sentences[0].strip())

        # Sentiment detection (simple keyword-based)
        positive_words = ["好", "开心", "成功", "喜欢", "满意", "棒", "赞", "good", "great", "happy"]
        negative_words = ["难", "问题", "失败", "不好", "糟糕", "坏", "sad", "bad", "fail"]
        text_all = " ".join(c.content for c in chunks)
        pos_count = sum(1 for w in positive_words if w in text_all)
        neg_count = sum(1 for w in negative_words if w in text_all)
        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Period detection
        from datetime import datetime, timezone
        if chunks:
            earliest = min(c.created_at for c in chunks)
            latest = max(c.created_at for c in chunks)
            from_str = datetime.fromtimestamp(earliest, tz=timezone.utc).strftime("%Y-%m-%d")
            to_str = datetime.fromtimestamp(latest, tz=timezone.utc).strftime("%Y-%m-%d")
            period = f"{from_str} to {to_str}"
        else:
            period = "unknown"

        # Generate summary text
        content_bullets = "\\n".join(f"- {c.content[:100]}" for c in chunks[:3])
        summary_text = (
            f"关于「{most_common_cat}」的话题，共涉及 {len(chunks)} 条记忆。\n"
            f"关键要点：\n{content_bullets}\n"
            f"整体情感：{sentiment}。"
        )

        return MemorySummary(
            topic=most_common_cat,
            summary_text=summary_text,
            key_facts=key_facts[:5],
            sentiment=sentiment,
            period=period,
            memory_count=len(chunks),
            confidence=min(1.0, len(chunks) * 0.2 + 0.3),
        ).to_dict()

    def _build_timeline(self, chunks: List[MemoryChunk]) -> Dict:
        """| 构建时间线 |"""
        from datetime import datetime, timezone
        events = []
        for chunk in sorted(chunks, key=lambda c: c.created_at):
            dt = datetime.fromtimestamp(chunk.created_at, tz=timezone.utc)
            events.append({
                "date": dt.strftime("%Y-%m-%d %H:%M"),
                "content": chunk.content[:200],
                "category": chunk.category,
                "importance": chunk.importance,
            })
        if events:
            period = f"{events[0]['date']} ~ {events[-1]['date']}"
        else:
            period = "unknown"
        return MemoryTimeline(events=events, period=period).to_list()

    def _extract_facts(self, chunks: List[MemoryChunk]) -> Dict:
        """| 提取关键事实（用于快速问答）|"""
        facts = []
        fact_patterns = [
            r"(\w+)是(\w+)",  # X is Y
            r"在(\d{4})年",  # In year X
            r"花了(\d+)(分钟|小时|天)",
            r"花了([0-9.]+)",
        ]
        for chunk in chunks:
            for pattern in fact_patterns:
                matches = __import__("re").findall(pattern, chunk.content)
                for match in matches:
                    if match:
                        facts.append({"pattern": pattern, "match": str(match), "source_id": chunk.id})
        return {"type": "facts", "facts": facts[:20], "total_chunks": len(chunks)}

    def compress_chunks(
        self,
        chunks: List[MemoryChunk],
        max_chars: int = 1500,
    ) -> List[MemoryChunk]:
        """| 压缩记忆碎片以适应 token 限制 |"""
        total = sum(len(c.content) for c in chunks)
        if total <= max_chars:
            return chunks

        # Proportional compression
        ratio = max_chars / total
        compressed = []
        for chunk in chunks:
            budget = int(len(chunk.content) * ratio)
            # Create a compressed copy (keep metadata, trim content)
            from core import MemoryChunk as MC
            compressed.append(MC(
                id=chunk.id,
                content=chunk.content[:budget],
                category=chunk.category,
                tags=chunk.tags,
                importance=chunk.importance,
                privacy=chunk.privacy,
                relevance_score=chunk.relevance_score,
                source_session=chunk.source_session,
                created_at=chunk.created_at,
                metadata={**chunk.metadata, "_compressed": True},
            ))
        return compressed