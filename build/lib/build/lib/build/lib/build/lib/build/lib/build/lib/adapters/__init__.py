"""
MindForge v5.0 适配器
OpenClaw · Claude Code · 通用 API
"""

from .openclaw_adapter import OpenClawAdapter
from .generic_api import GenericAPIAdapter
from .claude_adapter import ClaudeCodeAdapter

__all__ = [
    "OpenClawAdapter",
    "GenericAPIAdapter",
    "ClaudeCodeAdapter",
]
