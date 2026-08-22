"""
MindForge v5.5.1 - AI Agent 终身记忆系统
=======================================
四层记忆架构 · 知识图谱引擎 · 多模态支持 · 人格化记忆 · 联邦网络 · AI短剧记忆
v5.5.1 新增：Agent 记忆快照/去重/健康检查/重要度重校准 + AI短剧分集生成/角色台词/剧情反转/剧本导出 + 终极Bug修复

便捷导入模块，使 `from MindForge import MindForge` 在 pip install 后可用。
底层实现仍在 core/ 和 modules/ 子包中。
"""

__version__ = "5.5.1"
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
