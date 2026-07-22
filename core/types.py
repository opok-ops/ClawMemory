"""
MindForge v5.0 类型定义
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


class PrivacyLevel(Enum):
    """隐私级别"""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    STRICT = "STRICT"

    @classmethod
    def from_string(cls, value: str) -> "PrivacyLevel":
        try:
            return cls(value.upper())
        except ValueError:
            return cls.INTERNAL

    def to_int(self) -> int:
        mapping = {"PUBLIC": 0, "INTERNAL": 1, "PRIVATE": 2, "STRICT": 3}
        return mapping[self.value]


class Importance(Enum):
    """重要性级别"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, value: str) -> "Importance":
        try:
            return cls(value.upper())
        except ValueError:
            return cls.MEDIUM

    def to_int(self) -> int:
        mapping = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        return mapping[self.value]


class MemoryType(Enum):
    """记忆类型（多模态）"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    CODE = "code"
    STRUCTURED = "structured"
    MULTIMODAL = "multimodal"

    @classmethod
    def from_string(cls, value: str) -> "MemoryType":
        try:
            return cls(value.lower())
        except ValueError:
            return cls.TEXT


class MemoryLayer(Enum):
    """记忆层级（四层架构）"""
    SENSORY = "sensory"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    PERMANENT = "permanent"

    @classmethod
    def from_string(cls, value: str) -> "MemoryLayer":
        try:
            return cls(value.lower())
        except ValueError:
            return cls.SHORT_TERM

    def to_int(self) -> int:
        mapping = {"sensory": 0, "short_term": 1, "long_term": 2, "permanent": 3}
        return mapping[self.value]


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    db_path: str = "./data/memory.db"
    key_file: str = "./data/.key"
    encrypted: bool = True
    default_privacy: PrivacyLevel = PrivacyLevel.INTERNAL
    default_importance: Importance = Importance.MEDIUM
    default_layer: MemoryLayer = MemoryLayer.SHORT_TERM
    auto_consolidate: bool = True
    consolidate_interval_hours: int = 24
    forget_curve_enabled: bool = True
    vector_dim: int = 384
    max_short_term_items: int = 100
    sensory_buffer_size: int = 50
    sensory_retention_seconds: int = 30
