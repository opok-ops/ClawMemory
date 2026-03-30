# ClawMemory - AI Agent 终身记忆系统
# Copyright (c) 2026 ClawMemory Project
# License: MIT + ClawMemory Privacy Addendum

__version__ = "1.0.0"
__author__ = "ClawMemory Project"

from .core import (
    EncryptionEngine, StorageEngine, IndexManager, QueryEngine,
    PrivacyLevel, Importance, MemoryEntry, MemoryChunk,
)
from .modules import (
    RecallEngine, PrivacyEngine, TaxonomyManager,
)
from .adapters import OpenClawMemoryAdapter, ClaudeCodeAdapter

__all__ = [
    "__version__",
    "EncryptionEngine", "StorageEngine", "IndexManager", "QueryEngine",
    "PrivacyLevel", "Importance", "MemoryEntry", "MemoryChunk",
    "RecallEngine", "PrivacyEngine", "TaxonomyManager",
    "OpenClawMemoryAdapter", "ClaudeCodeAdapter",
]
