"""
MindForge v5.5.3 - AI Agent 终身记忆系统
=======================================
四层记忆架构 · 知识图谱引擎 · 多模态支持 · 人格化记忆 · 联邦网络 · AI短剧记忆
v5.5.2 新增：Memory TTL过期机制 · 多关键词搜索高亮 · 按分类/标签批量删除 · FTS5溢出修复 · 查询引擎性能优化 · 全面BOM修复

便捷导入模块，使 `from MindForge import MindForge` 在 pip install 后可用。
底层实现仍在 core/ 和 modules/ 子包中。
"""

__version__ = "5.5.3"
__author__ = "MindForge Project"
__license__ = "MIT + Privacy Addendum"

from core import (
    MindForge,
    MemoryEntry,
    MemoryLayer,
    PrivacyLevel,
    Importance,
    MemoryType,
    StorageEngine,
    EncryptionEngine,
    IndexEngine,
    QueryEngine,
)

from modules import (
    RecallEngine,
    RecallConfig,
    KnowledgeGraph,
    MemoryEvolution,
    PersonalityEngine,
    MultimodalMemory,
    FederatedMemory,
    TaxonomyManager,
    PrivacyEngine,
    MemoryIntegrator,
)

__all__ = [
    "MindForge",
    "MemoryEntry",
    "MemoryLayer",
    "PrivacyLevel",
    "Importance",
    "MemoryType",
    "StorageEngine",
    "EncryptionEngine",
    "IndexEngine",
    "QueryEngine",
    "RecallEngine",
    "RecallConfig",
    "KnowledgeGraph",
    "MemoryEvolution",
    "PersonalityEngine",
    "MultimodalMemory",
    "FederatedMemory",
    "TaxonomyManager",
    "PrivacyEngine",
    "MemoryIntegrator",
    "__version__",
]
