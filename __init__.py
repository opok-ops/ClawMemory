"""
MindForge v5.4.4 - AI Agent 终身记忆系统
=======================================
四层记忆架构 · 知识图谱引擎 · 多模态支持 · 人格化记忆 · 联邦网络 · AI短剧记忆
v5.4.2 新增：联邦记忆细粒度 ACL（默认拒绝/优先级/信任阈值）+ 共享记忆冲突解决（lww/keep_both）
"""

__version__ = "5.4.4"
__author__ = "MindForge Project"
__license__ = "MIT + Privacy Addendum"

try:
    from .core import (
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
    from .modules import (
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
except ImportError:
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
