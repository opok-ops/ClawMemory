"""
MindForge v5.0 功能模块
知识图谱 · 记忆演化 · 人格化 · 多模态 · 联邦记忆
"""

from .recall import RecallEngine, RecallConfig
from .knowledge_graph import KnowledgeGraph, KnowledgeEntity, KnowledgeRelation
from .evolution import MemoryEvolution, ForgettingCurve
from .personality import PersonalityEngine, UserProfile
from .multimodal import MultimodalMemory, MultimodalType
from .federated import FederatedMemory, FederatedPeer
from .categorizer import TaxonomyManager
from .privacy import PrivacyEngine, PrivacyScanResult
from .integrator import MemoryIntegrator

__all__ = [
    "RecallEngine",
    "RecallConfig",
    "KnowledgeGraph",
    "KnowledgeEntity",
    "KnowledgeRelation",
    "MemoryEvolution",
    "ForgettingCurve",
    "PersonalityEngine",
    "UserProfile",
    "MultimodalMemory",
    "MultimodalType",
    "FederatedMemory",
    "FederatedPeer",
    "TaxonomyManager",
    "PrivacyEngine",
    "PrivacyScanResult",
    "MemoryIntegrator",
]
