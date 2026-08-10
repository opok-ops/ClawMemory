"""
MindForge v5.4.5 嵌入引擎

可选依赖 sentence-transformers，支持本地 CPU 推理的语义嵌入。
未安装时自动降级，不影响核心功能。

默认模型: all-MiniLM-L6-v2 (384 维, ~80MB, CPU 友好)
"""

import struct
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认模型名
DEFAULT_MODEL = "all-MiniLM-L6-v2"

# 默认维度（all-MiniLM-L6-v2 输出 384 维）
DEFAULT_DIMENSION = 384


class EmbeddingEngine:
    """语义嵌入引擎

    封装 sentence-transformers，提供：
    - 文本 → 向量编码（encode / encode_batch）
    - 向量序列化（serialize / deserialize，用于 SQLite BLOB 存储）
    - 余弦相似度计算
    - 懒加载：首次 encode 时才加载模型

    使用方式：
        engine = EmbeddingEngine()  # 不加载模型
        if engine.is_available:
            vec = engine.encode("hello world")
    """

    _instance = None  # 单例（避免重复加载模型）

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = DEFAULT_MODEL):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._model_name = model_name
        self._model = None
        self._dimension = DEFAULT_DIMENSION
        self._load_attempted = False
        self._available = False

    @property
    def is_available(self) -> bool:
        """sentence-transformers 是否可用"""
        if not self._load_attempted:
            self._try_load()
        return self._available

    @property
    def dimension(self) -> int:
        """嵌入向量维度"""
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _try_load(self):
        """懒加载 sentence-transformers 模型"""
        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            # 获取实际维度
            test_vec = self._model.encode("test", show_progress_bar=False)
            self._dimension = len(test_vec)
            self._available = True
            logger.info("EmbeddingEngine 加载成功: %s (dim=%d)",
                        self._model_name, self._dimension)
        except ImportError:
            logger.warning(
                "sentence-transformers 未安装，向量检索不可用。"
                "安装: pip install sentence-transformers")
            self._available = False
        except Exception as e:
            logger.warning("EmbeddingEngine 加载失败: %s", e)
            self._available = False

    def encode(self, text: str) -> Optional[List[float]]:
        """编码单条文本为向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量 (List[float])，或 None（模型不可用时）
        """
        if not self.is_available or not text:
            return None
        try:
            vec = self._model.encode(text, show_progress_bar=False,
                                     normalize_embeddings=True)
            return vec.tolist()
        except Exception as e:
            logger.warning("encode 失败: %s", e)
            return None

    def encode_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """批量编码文本为向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表，或 None（模型不可用时）
        """
        if not self.is_available or not texts:
            return None
        try:
            vecs = self._model.encode(
                texts, show_progress_bar=False,
                normalize_embeddings=True, batch_size=32)
            return [v.tolist() for v in vecs]
        except Exception as e:
            logger.warning("encode_batch 失败: %s", e)
            return None

    @staticmethod
    def serialize(vec: List[float]) -> bytes:
        """将向量序列化为 bytes（用于 SQLite BLOB 存储）

        格式: 4 字节 float32 数组（小端序）
        """
        return struct.pack(f'<{len(vec)}f', *vec)

    @staticmethod
    def deserialize(blob: bytes) -> List[float]:
        """从 bytes 反序列化向量"""
        if not blob:
            return []
        count = len(blob) // 4
        return list(struct.unpack(f'<{count}f', blob))

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """计算两个向量的余弦相似度

        向量已归一化时，点积即余弦相似度。
        """
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        # 归一化后的向量直接点积
        dot = sum(a * b for a, b in zip(v1, v2))
        return max(-1.0, min(1.0, dot))

    @staticmethod
    def cosine_similarity_batch(
        query_vec: List[float],
        candidates: List[Tuple[str, List[float]]],
        top_k: int = 20
    ) -> List[Tuple[str, float]]:
        """批量计算余弦相似度并返回 top_k 结果

        Args:
            query_vec: 查询向量
            candidates: [(memory_id, embedding_vec), ...]
            top_k: 返回前 k 个结果

        Returns:
            [(memory_id, score), ...] 按分数降序
        """
        if not query_vec or not candidates:
            return []
        scored = []
        for mem_id, vec in candidates:
            if not vec or len(vec) != len(query_vec):
                continue
            score = EmbeddingEngine.cosine_similarity(query_vec, vec)
            scored.append((mem_id, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
