"""
ClawMemory v5.0 主入口类
统一的 API 接口，集成所有核心功能
"""

from typing import Optional, List, Dict, Any
from pathlib import Path

from .types import (
    PrivacyLevel,
    Importance,
    MemoryType,
    MemoryLayer,
    MemoryConfig,
)
from .storage import StorageEngine, MemoryEntry
from .encryption import EncryptionEngine, init_engine as _init_engine
from .indexer import IndexEngine
from .query import QueryEngine


class ClawMemory:
    """ClawMemory 主类 - AI Agent 终身记忆系统 v5.0"""

    def __init__(self, config: Optional[MemoryConfig] = None, **kwargs):
        if config is None:
            config = MemoryConfig(**kwargs)
        self.config = config
        self._encryption: Optional[EncryptionEngine] = None
        self._storage: Optional[StorageEngine] = None
        self._index: Optional[IndexEngine] = None
        self._query: Optional[QueryEngine] = None

        if self.config.encrypted:
            self._init_encryption()

        self._init_storage()
        self._init_index()
        self._init_query()

    def _init_encryption(self):
        key_file = Path(self.config.key_file)
        if key_file.exists():
            pass
        else:
            pass

    def _init_storage(self):
        self._storage = StorageEngine(
            db_path=self.config.db_path,
            encryption=self._encryption,
            encrypted=self.config.encrypted and self._encryption is not None,
        )

    def _init_index(self):
        self._index = IndexEngine(db_path=self.config.db_path)

    def _init_query(self):
        if self._storage and self._index:
            self._query = QueryEngine(self._storage, self._index)

    def init_with_password(self, password: str):
        """使用密码初始化加密引擎"""
        if not self.config.encrypted:
            return

        engine = _init_engine(password, self.config.key_file)
        self._encryption = engine

        self._storage = StorageEngine(
            db_path=self.config.db_path,
            encryption=engine,
            encrypted=True,
        )
        self._query = QueryEngine(self._storage, self._index)

    def add(self,
            content: str,
            category: str = "general",
            tags: Optional[List[str]] = None,
            privacy: PrivacyLevel = None,
            importance: Importance = None,
            memory_type: MemoryType = None,
            layer: MemoryLayer = None,
            source_session: str = "",
            source_agent: str = "",
            metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        """添加记忆"""
        privacy = privacy or self.config.default_privacy
        importance = importance or self.config.default_importance
        layer = layer or self.config.default_layer
        memory_type = memory_type or MemoryType.TEXT

        entry = self._storage.add_memory(
            content=content,
            category=category,
            tags=tags,
            privacy=privacy,
            importance=importance,
            memory_type=memory_type,
            layer=layer,
            source_session=source_session,
            source_agent=source_agent,
            metadata=metadata,
        )

        self._index.index_memory(
            entry.id,
            content,
            metadata={"category": category, "tags": tags or [], "importance": importance.value},
        )

        return entry

    def get(self, memory_id: str, actor: str = "", session_id: str = "") -> Optional[MemoryEntry]:
        """获取记忆"""
        return self._storage.get_memory(memory_id, actor, session_id)

    def search(self,
               query: str,
               max_results: int = 10,
               min_relevance: float = 0.3,
               categories: Optional[List[str]] = None,
               layers: Optional[List[MemoryLayer]] = None,
               agent_id: str = "",
               session_id: str = ""):
        """搜索记忆"""
        return self._query.search(
            query=query,
            max_results=max_results,
            min_relevance=min_relevance,
            categories=categories,
            layers=layers,
            agent_id=agent_id,
            session_id=session_id,
        )

    def list(self,
             category: Optional[str] = None,
             layer: Optional[MemoryLayer] = None,
             limit: int = 50,
             offset: int = 0) -> List[MemoryEntry]:
        """列出记忆"""
        return self._storage.list_memories(
            category=category,
            layer=layer,
            limit=limit,
            offset=offset,
        )

    def update(self,
               memory_id: str,
               content: Optional[str] = None,
               category: Optional[str] = None,
               tags: Optional[List[str]] = None,
               privacy: Optional[PrivacyLevel] = None,
               importance: Optional[Importance] = None,
               layer: Optional[MemoryLayer] = None,
               metadata: Optional[Dict[str, Any]] = None,
               actor: str = "",
               session_id: str = "") -> bool:
        """更新记忆"""
        success = self._storage.update_memory(
            entry_id=memory_id,
            content=content,
            category=category,
            tags=tags,
            privacy=privacy,
            importance=importance,
            layer=layer,
            metadata=metadata,
            actor=actor,
            session_id=session_id,
        )

        if success and content:
            self._index.index_memory(memory_id, content, metadata={})

        return success

    def delete(self, memory_id: str, actor: str = "",
               session_id: str = "", hard_delete: bool = False) -> bool:
        """删除记忆"""
        success = self._storage.delete_memory(
            memory_id, actor, session_id, hard_delete
        )
        if success and hard_delete:
            self._index.remove_memory(memory_id)
        return success

    def stats(self) -> dict:
        """获取统计信息"""
        return self._storage.get_stats()

    def audit_log(self, memory_id: Optional[str] = None,
                  actor: Optional[str] = None,
                  limit: int = 100):
        """获取审计日志"""
        return self._storage.get_audit_log(memory_id, actor, limit)

    def backup(self, backup_dir: str = "./data/backup"):
        """备份"""
        return self._storage.backup(backup_dir)

    @property
    def storage(self) -> StorageEngine:
        return self._storage

    @property
    def index(self) -> IndexEngine:
        return self._index

    @property
    def query(self) -> QueryEngine:
        return self._query

    def close(self):
        if self._storage:
            self._storage.close()
