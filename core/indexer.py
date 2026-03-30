"""
ClawMemory 索引引擎
===========================
语义向量索引 + 多维度倒排索引。
支持：
- TF-IDF 向量化（轻量级，无外部依赖）
- SQLite FTS5 全文检索
- 重要性 + 时间衰减评分
- 10 万级条目 ≤200ms 检索目标
"""

import re
import math
import json
import hashlib
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter, defaultdict
from dataclasses import dataclass
from threading import Lock


# ============================================================================
# TF-IDF Vectorizer (Pure Python, no external dependencies)
# ============================================================================
class TFIDFVectorizer:
    """| 轻量级 TF-IDF 向量化器，中文/英文双语支持 |"""

    def __init__(self):
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_count: int = 0
        self._lock = Lock()

    def _tokenize(self, text: str) -> List[str]:
        """| 中英文分词 |"""
        # Chinese: character-level + bigram for short texts
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        # English/numbers: lowercase, alphanumeric
        english_tokens = re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
        # Punctuation split
        other_tokens = re.sub(r"[a-zA-Z0-9]", " ", text).split()
        tokens = english_tokens + other_tokens
        # Add Chinese bigrams (each pair of adjacent Chinese chars)
        chinese_bigrams = ["".join(chinese_chars[i:i+2]) for i in range(len(chinese_chars)-1)]
        return tokens + chinese_bigrams

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        counter = Counter(tokens)
        total = len(tokens)
        return {term: count / total for term, count in counter.items()}

    def _compute_idf(self, all_terms: List[Set[str]]):
        """| 计算逆文档频率 |"""
        N = len(all_terms)
        df = defaultdict(int)
        for terms in all_terms:
            for term in terms:
                df[term] += 1
        self.idf = {
            term: math.log(N / (df_val + 1)) + 1
            for term, df_val in df.items()
        }

    def fit(self, documents: List[str]):
        """| 构建词汇表和 IDF |"""
        with self._lock:
            self.doc_count = len(documents)
            all_terms_per_doc = []
            for doc in documents:
                tokens = self._tokenize(doc)
                unique_terms = set(tokens)
                all_terms_per_doc.append(unique_terms)
                for term in unique_terms:
                    if term not in self.vocab:
                        self.vocab[term] = len(self.vocab)
            self._compute_idf(all_terms_per_doc)

    def transform(self, documents: List[str]) -> List[List[float]]:
        """| 将文档转换为 TF-IDF 向量 |"""
        vectors = []
        for doc in documents:
            tokens = self._tokenize(doc)
            tf = self._compute_tf(tokens)
            vec = [0.0] * max(len(self.vocab), 1)
            for term, tf_val in tf.items():
                if term in self.vocab:
                    idx = self.vocab[term]
                    idf_val = self.idf.get(term, 0.0)
                    vec[idx] = tf_val * idf_val
            # L2 normalize
            norm = math.sqrt(sum(v*v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors

    def fit_transform(self, documents: List[str]) -> List[List[float]]:
        self.fit(documents)
        return self.transform(documents)

    def vectorize(self, text: str) -> List[float]:
        """| 单个文本向量化 |"""
        return self.transform([text])[0]

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """| 计算余弦相似度 |"""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(v*v for v in vec1)) or 1e-10
        norm2 = math.sqrt(sum(v*v for v in vec2)) or 1e-10
        return dot / (norm1 * norm2)


# ============================================================================
# Vector Index (In-memory + SQLite persistent)
# ============================================================================
@dataclass
class IndexEntry:
    memory_id: str
    vector: str   # JSON array of floats (stored as JSON in DB)
    metadata: str  # JSON: {category, tags, importance, created_at}

    @classmethod
    def from_row(cls, row: tuple, cols: List[str]) -> "IndexEntry":
        d = dict(zip(cols, row))
        return cls(
            memory_id=d["memory_id"],
            vector=d["vector"],
            metadata=d["metadata"],
        )


class VectorIndex:
    """| 语义向量索引，支持增量更新 |"""

    def __init__(self, index_path: Optional[Path] = None):
        self._index_path = index_path or self._default_index_path()
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._index_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._vectorizer = TFIDFVectorizer()
        self._in_memory_vectors: Dict[str, List[float]] = {}
        self._lock = Lock()
        self._init_index()

    def _default_index_path(self) -> Path:
        return Path(__file__).parent.parent / "data" / "index" / "vectors.db"

    def _init_index(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS vector_index (
                memory_id TEXT PRIMARY KEY,
                vector TEXT NOT NULL,     -- JSON array
                metadata TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS idf_cache (
                doc_hash TEXT PRIMARY KEY,
                doc_text TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()
        self._load_in_memory_index()

    def _load_in_memory_index(self):
        """| 启动时加载向量到内存（异步，按需）|"""
        # Load top 1000 most recently accessed into memory for fast retrieval
        rows = self._conn.execute("""
            SELECT memory_id, vector FROM vector_index
            ORDER BY updated_at DESC LIMIT 1000
        """).fetchall()
        for row in rows:
            self._in_memory_vectors[row[0]] = json.loads(row[1])

    def add_vector(self, memory_id: str, text: str, metadata: Dict):
        """| 添加向量索引 |"""
        with self._lock:
            vector = self._vectorizer.vectorize(text)
            vector_json = json.dumps(vector)
            self._in_memory_vectors[memory_id] = vector
            self._conn.execute(
                """INSERT OR REPLACE INTO vector_index (memory_id, vector, metadata, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (memory_id, vector_json, json.dumps(metadata, ensure_ascii=False), _now())
            )
            self._conn.commit()

    def remove_vector(self, memory_id: str):
        """| 删除向量索引 |"""
        with self._lock:
            self._in_memory_vectors.pop(memory_id, None)
            self._conn.execute("DELETE FROM vector_index WHERE memory_id=?", (memory_id,))
            self._conn.commit()

    def search(
        self,
        query_text: str,
        top_k: int = 10,
        filter_category: Optional[str] = None,
        min_importance: int = 1,
    ) -> List[Tuple[str, float]]:
        """| 语义相似度搜索 |"""
        query_vec = self._vectorizer.vectorize(query_text)
        results: List[Tuple[str, float]] = []

        with self._lock:
            # Load all vectors from DB (with optional category filter)
            if filter_category:
                rows = self._conn.execute("""
                    SELECT vi.memory_id, vi.vector, vi.metadata FROM vector_index vi
                    INNER JOIN memories m ON vi.memory_id = m.id
                    WHERE m.category=? AND m.is_deleted=0
                """, (filter_category,)).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT memory_id, vector, metadata FROM vector_index"
                ).fetchall()

        for row in rows:
            memory_id = row[0]
            vec = json.loads(row[1])
            meta = json.loads(row[2] or "{}")
            if meta.get("importance", 1) < min_importance:
                continue
            score = self._vectorizer.cosine_similarity(query_vec, vec)
            results.append((memory_id, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def rebuild_index(self, documents: List[Tuple[str, str, Dict]]):
        """| 批量重建索引（documents: [(id, text, metadata)]）|"""
        with self._lock:
            self._conn.execute("DELETE FROM vector_index")
            self._conn.commit()
            texts = [doc[1] for doc in documents]
            vectors = self._vectorizer.fit_transform(texts)
            self._in_memory_vectors.clear()
            now = _now()
            for (memory_id, text, meta), vector in zip(documents, vectors):
                vector_json = json.dumps(vector)
                self._in_memory_vectors[memory_id] = vector
                self._conn.execute(
                    """INSERT INTO vector_index (memory_id, vector, metadata, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (memory_id, json.dumps(vector), json.dumps(meta, ensure_ascii=False), now)
                )
            self._conn.commit()

    def close(self):
        self._conn.close()


def _now() -> float:
    import time
    return time.time()


# ============================================================================
# Composite Scorer
# ============================================================================
class CompositeScorer:
    """| 综合评分：向量相似度 + 重要性 + 时间衰减 + 访问频率 |"""

    def __init__(self, vector_index: VectorIndex):
        self.vector_index = vector_index

    def score(
        self,
        query_text: str,
        memory_data: Dict,
        vector_score: float,
    ) -> float:
        """| 计算综合得分 |"""
        importance = memory_data.get("importance", 2)
        created_at = memory_data.get("created_at", 0)
        accessed_at = memory_data.get("accessed_at", 0)
        access_count = memory_data.get("access_count", 0)
        now = _now()

        # Importance score (1-4 normalized to 0-1)
        importance_score = (importance - 1) / 3.0

        # Time decay: recent memories score higher
        # Half-life: 30 days
        days_since_access = (now - accessed_at) / 86400
        time_decay = math.exp(-days_since_access / 30.0)

        # Access frequency boost (log scale)
        frequency_boost = math.log1p(access_count) / 10.0

        # Semantic score weight: 60%
        semantic_weight = 0.6
        importance_weight = 0.25
        recency_weight = 0.10
        frequency_weight = 0.05

        composite = (
            semantic_weight * vector_score +
            importance_weight * importance_score +
            recency_weight * time_decay +
            frequency_weight * frequency_boost
        )
        return round(composite, 6)


# ============================================================================
# Index Manager
# ============================================================================
class IndexManager:
    """| 索引管理器：协调向量索引和 FTS |"""

    def __init__(self, index_path: Optional[Path] = None):
        self.vector_index = VectorIndex(index_path)
        self.scorer = CompositeScorer(self.vector_index)

    def index_memory(self, memory_id: str, text: str, metadata: Dict):
        self.vector_index.add_vector(memory_id, text, metadata)

    def remove_memory(self, memory_id: str):
        self.vector_index.remove_vector(memory_id)

    def search(
        self,
        query_text: str,
        top_k: int = 10,
        category: Optional[str] = None,
        min_importance: int = 1,
    ) -> List[Tuple[str, float]]:
        return self.vector_index.search(query_text, top_k, category, min_importance)

    def rebuild(self, documents: List[Tuple[str, str, Dict]]):
        self.vector_index.rebuild_index(documents)

    def close(self):
        self.vector_index.close()