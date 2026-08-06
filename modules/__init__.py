"""
MindForge v5.0 功能模块
知识图谱 · 记忆演化 · 人格化 · 多模态 · 联邦记忆 · 多Agent记忆空间
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
from .multi_agent import MultiAgentMemoryManager, AgentSpace, SpaceMember, SpaceRole
# v5.3.9 新增五大能力
from .intent_router import IntentRouter, IntentResult, INTENT_DEFS, DEFAULT_INTENT
from .conflict_detector import ConflictDetector, ConflictPair, DecayAction, ANTONYM_PAIRS
from .skill_extractor import SkillExtractor, SkillTemplate, SkillSlot
from .hybrid_search import (QueryExpander, ExpansionResult,
                            CrossEncoderReranker, RerankResult, RerankWeights)
from .session_focus import SessionFocus, TopicCluster, FocusSummary
# v5.4.2 新增两大能力
from .federated_acl import FederatedACLManager
from .share_conflict import SharedConflictResolver

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
    "MultiAgentMemoryManager",
    "AgentSpace",
    "SpaceMember",
    "SpaceRole",
    # v5.3.9
    "IntentRouter",
    "IntentResult",
    "INTENT_DEFS",
    "DEFAULT_INTENT",
    "ConflictDetector",
    "ConflictPair",
    "DecayAction",
    "ANTONYM_PAIRS",
    "SkillExtractor",
    "SkillTemplate",
    "SkillSlot",
    "QueryExpander",
    "ExpansionResult",
    "CrossEncoderReranker",
    "RerankResult",
    "RerankWeights",
    "SessionFocus",
    "TopicCluster",
    "FocusSummary",
    # v5.4.2
    "FederatedACLManager",
    "SharedConflictResolver",
]
