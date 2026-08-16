"""
MindForge v5.4.8 - AI Agent 终身记忆系统
=======================================
四层记忆架构 · 知识图谱引擎 · 多模态支持 · 人格化记忆 · 联邦网络 · AI短剧记忆
v5.4.8 新增：Agent 记忆强化/跨 Agent 共享/知识领域分析 + AI 短剧场景生成/情感时间线 + DSH 插件 v0.1.1
"""

__version__ = "5.4.8"
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
