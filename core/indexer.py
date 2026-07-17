"""
ClawMemory v5.0 索引引擎
支持 TF-IDF、向量索引、FTS5 全文检索
"""

import math
import re
import json
import sqlite3
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class IndexedDocument:
    """索引文档"""
    doc_id: str
    text: str
    metadata: Dict
    vector: List[float]


class TFIDFVectorizer:
    """TF-IDF 向量化器"""

    def __init__(self):
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_count: int = 0

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text)
        return [t for t in tokens if len(t) > 1]

    def fit(self, documents: List[str]):
        self.doc_count = len(documents)
        df = defaultdict(int)

        all_tokens = set()
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                df[token] += 1
                all_tokens.add(token)

        self.vocab = {word: idx for idx, word in enumerate(sorted(all_tokens))}

        for word, idx in self.vocab.items():
            self.idf[word] = math.log((self.doc_count + 1) / (df[word] + 1)) + 1

    def transform(self, text: str) -> Dict[int, float]:
        tokens = self._tokenize(text)
        if not tokens:
            return {}

        tf = Counter(tokens)
        max_tf = max(tf.values())

        vector = {}
        for token, count in tf.items():
            if token in self.vocab:
                idx = self.vocab[token]
                tf_norm = 0.5 + 0.5 * count / max_tf
                vector[idx] = tf_norm * self.idf.get(token, 0)

        norm = math.sqrt(sum(v * v for v in vector.values()))
        if norm > 0:
            vector = {k: v / norm for k, v in vector.items()}

        return vector

    def cosine_similarity(self, v1: Dict[int, float], v2: Dict[int, float]) -> float:
        common = set(v1.keys()) & set(v2.keys())
        dot = sum(v1[k] * v2[k] for k in common)
        return dot


class VectorIndex:
    """向量索引（简易版）"""

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.vectors: Dict[str, List[float]] = {}
        self.metadata: Dict[str, Dict] = {}

    def add(self, doc_id: str, vector: List[float], metadata: Optional[Dict] = None):
        self.vectors[doc_id] = vector
        if metadata:
            self.metadata[doc_id] = metadata

    def remove(self, doc_id: str):
        self.vectors.pop(doc_id, None)
        self.metadata.pop(doc_id, None)

    def search(self, query_vector: List[float], top_k: int = 10) -> List[Tuple[str, float]]:
        if not self.vectors:
            return []

        scores = []
        for doc_id, vec in self.vectors.items():
            score = self._cosine(query_vector, vec)
            scores.append((doc_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _cosine(self, v1: List[float], v2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        if n1 == 0 or n2 == 0:
            return 0
        return dot / (n1 * n2)


class IndexEngine:
    """索引引擎"""

    def __init__(self, db_path: str = "./data/memory.db"):
        self.db_path = db_path
        self.vectorizer = TFIDFVectorizer()
        self.vector_index = VectorIndex()
        self._fitted = False
        self._doc_texts: Dict[str, str] = {}

    def index_memory(self, doc_id: str, text: str, metadata: Optional[Dict] = None):
        """索引记忆"""
        self._doc_texts[doc_id] = text

        if not self._fitted and len(self._doc_texts) >= 5:
            self._fit_vectorizer()

        if self._fitted:
            vector_dict = self.vectorizer.transform(text)
            vec_len = len(self.vectorizer.vocab)
            vector = [0.0] * vec_len
            for idx, val in vector_dict.items():
                vector[idx] = val
            self.vector_index.add(doc_id, vector, metadata)

    def remove_memory(self, doc_id: str):
        """移除索引"""
        self._doc_texts.pop(doc_id, None)
        self.vector_index.remove(doc_id)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """搜索"""
        if not self._fitted and self._doc_texts:
            self._fit_vectorizer()

        if not self._fitted:
            return self._keyword_search(query, top_k)

        query_vec_dict = self.vectorizer.transform(query)
        vec_len = len(self.vectorizer.vocab)
        query_vec = [0.0] * vec_len
        for idx, val in query_vec_dict.items():
            query_vec[idx] = val

        return self.vector_index.search(query_vec, top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """关键词搜索（降级方案）"""
        query_lower = query.lower()
        scores = []

        for doc_id, text in self._doc_texts.items():
            text_lower = text.lower()
            score = 0
            for word in query_lower.split():
                if word in text_lower:
                    score += text_lower.count(word)
            if score > 0:
                scores.append((doc_id, score / len(text) * 1000))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _fit_vectorizer(self):
        texts = list(self._doc_texts.values())
        self.vectorizer.fit(texts)

        for doc_id, text in self._doc_texts.items():
            vector_dict = self.vectorizer.transform(text)
            vec_len = len(self.vectorizer.vocab)
            vector = [0.0] * vec_len
            for idx, val in vector_dict.items():
                vector[idx] = val
            self.vector_index.add(doc_id, vector)

        self._fitted = True

    def fts_search(self, conn: sqlite3.Connection, query: str,
                   top_k: int = 10) -> List[Tuple[str, float]]:
        """FTS5 全文搜索"""
        try:
            rows = conn.execute("""
                SELECT m.id, bm25(memory_fts) as score
                FROM memory_fts
                JOIN memories m ON memory_fts.rowid = (
                    SELECT rowid FROM memories WHERE id = m.id
                )
                WHERE memory_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """, (query, top_k)).fetchall()
            return [(row[0], 1.0 / (1.0 + row[1])) for row in rows]
        except Exception:
            return []
