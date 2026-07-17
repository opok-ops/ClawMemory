"""
ClawMemory v5.0 - AI Agent 终身记忆系统
=======================================
四层记忆架构 · 知识图谱引擎 · 多模态支持 · 人格化记忆 · 联邦网络
"""

__version__ = "5.0.0"
__author__ = "ClawMemory Project"
__license__ = "MIT + Privacy Addendum"

from .core import (
    ClawMemory,
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

__all__ = [
    "ClawMemory",
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
