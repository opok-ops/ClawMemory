"""
MindForge v5.4.0 - AI Agent 终身记忆系统
=======================================
四层记忆架构 · 知识图谱引擎 · 多模态支持 · 人格化记忆 · 联邦网络 · AI短剧记忆
v5.4.0 新增：联邦细粒度 ACL / created_by 溯源 / 共享记忆冲突解决（LWW + 版本链）
v5.3.9 新增：意图路由/矛盾衰减/技能转化/混合检索增强/会话焦点
"""

__version__ = "5.4.0"
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
