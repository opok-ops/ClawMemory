"""
ClawMemory v5.0 主入口类
统一的 API 接口，集成所有核心功能
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import csv
import uuid

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
            starred: bool = False,
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
            starred=starred,
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
             starred: Optional[bool] = None,
             created_after: Optional[float] = None,
             created_before: Optional[float] = None,
             limit: int = 50,
             offset: int = 0) -> List[MemoryEntry]:
        """列出记忆"""
        return self._storage.list_memories(
            category=category,
            layer=layer,
            starred=starred,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )

    def star(self, memory_id: str, actor: str = "", session_id: str = "") -> bool:
        """收藏记忆（加星标）"""
        return self._storage.update_memory(
            entry_id=memory_id,
            starred=True,
            actor=actor,
            session_id=session_id,
        )

    def unstar(self, memory_id: str, actor: str = "", session_id: str = "") -> bool:
        """取消收藏（取消星标）"""
        return self._storage.update_memory(
            entry_id=memory_id,
            starred=False,
            actor=actor,
            session_id=session_id,
        )

    def update(self,
               memory_id: str,
               content: Optional[str] = None,
               category: Optional[str] = None,
               tags: Optional[List[str]] = None,
               privacy: Optional[PrivacyLevel] = None,
               importance: Optional[Importance] = None,
               layer: Optional[MemoryLayer] = None,
               starred: Optional[bool] = None,
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
            starred=starred,
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

    def batch_delete(self,
                     category: Optional[str] = None,
                     layer: Optional[MemoryLayer] = None,
                     starred: Optional[bool] = None,
                     created_after: Optional[float] = None,
                     created_before: Optional[float] = None,
                     hard_delete: bool = False,
                     actor: str = "",
                     session_id: str = "") -> int:
        """批量删除记忆，返回删除数量"""
        count = self._storage.batch_delete(
            category=category,
            layer=layer,
            starred=starred,
            created_after=created_after,
            created_before=created_before,
            hard_delete=hard_delete,
            actor=actor,
            session_id=session_id,
        )
        return count

    def search_by_tag(self, tag: str,
                      category: Optional[str] = None,
                      layer: Optional[MemoryLayer] = None,
                      limit: int = 50,
                      offset: int = 0):
        """按标签搜索记忆"""
        return self._storage.search_by_tag(
            tag=tag,
            category=category,
            layer=layer,
            limit=limit,
            offset=offset,
        )

    def deduplicate(self,
                    category: Optional[str] = None,
                    similarity_threshold: float = 0.95,
                    dry_run: bool = True,
                    actor: str = "system",
                    session_id: str = "") -> dict:
        """记忆去重 - 检测并合并高度相似的记忆（v5.0.4 新增）

        Args:
            category: 限定分类，None 表示全部
            similarity_threshold: 相似度阈值（0-1），默认 0.95
            dry_run: True=只报告不删除，False=实际删除
            actor: 操作者（审计日志用）
            session_id: 会话 ID

        Returns:
            dict: {duplicates_found, would_remove, removed, details}
        """
        return self._storage.deduplicate(
            category=category,
            similarity_threshold=similarity_threshold,
            dry_run=dry_run,
            actor=actor,
            session_id=session_id,
        )

    def export_as_markdown(self,
                           output_path: str,
                           category: Optional[str] = None,
                           layer: Optional[MemoryLayer] = None,
                           starred_only: bool = False):
        """导出记忆为 Markdown 格式（v5.0.4 新增）

        Args:
            output_path: 输出 .md 文件路径
            category: 限定分类
            layer: 限定层级
            starred_only: 仅导出收藏的记忆

        Returns:
            Path: 导出文件路径
        """
        return self._storage.export_as_markdown(
            output_path=output_path,
            category=category,
            layer=layer,
            starred_only=starred_only,
        )

    def health_check(self) -> dict:
        """数据库健康检查（v5.0.5 新增）

        检查项目：完整性、索引、FTS 同步、孤立审计日志、加密一致性。

        Returns:
            dict: 含 status (healthy/warning/critical) 和 recommendations 列表
        """
        return self._storage.health_check()

    def summarize(self,
                  category: Optional[str] = None,
                  group_by: str = "category") -> dict:
        """生成记忆摘要（v5.0.5 新增）

        Args:
            category: 限定分类，None=全部
            group_by: 分组维度 'category'|'layer'|'importance'|'privacy'

        Returns:
            dict: 含 total, grouped, recent_activity, top_tags
        """
        return self._storage.summarize(category=category, group_by=group_by)

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

    def export_json(self, output_path: str,
                    category: Optional[str] = None,
                    layer: Optional[MemoryLayer] = None,
                    include_private: bool = False) -> int:
        """导出记忆为 JSON 文件"""
        entries = self._storage.list_memories(
            category=category,
            layer=layer,
            limit=100000,
            offset=0,
        )

        if not include_private:
            entries = [
                e for e in entries
                if e.privacy in (PrivacyLevel.PUBLIC, PrivacyLevel.INTERNAL)
            ]

        data = {
            "version": "5.0.1",
            "export_time": "",
            "total": len(entries),
            "memories": [e.to_dict() for e in entries],
        }

        from datetime import datetime
        data["export_time"] = datetime.now().isoformat()

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return len(entries)

    def import_json(self, input_path: str,
                    skip_duplicates: bool = True,
                    target_layer: Optional[MemoryLayer] = None) -> Dict[str, int]:
        """从 JSON 文件导入记忆"""
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        memories = data.get("memories", [])
        stats = {"imported": 0, "skipped": 0, "failed": 0}

        for mem_data in memories:
            try:
                existing = self._storage.get_memory(mem_data.get("id", ""))
                if existing and skip_duplicates:
                    stats["skipped"] += 1
                    continue

                layer = target_layer
                if not layer and mem_data.get("layer"):
                    try:
                        layer = MemoryLayer(mem_data["layer"])
                    except ValueError:
                        layer = self.config.default_layer

                privacy = self.config.default_privacy
                if mem_data.get("privacy"):
                    try:
                        privacy = PrivacyLevel(mem_data["privacy"])
                    except ValueError:
                        pass

                importance = self.config.default_importance
                if mem_data.get("importance"):
                    try:
                        importance = Importance(mem_data["importance"])
                    except ValueError:
                        pass

                memory_type = MemoryType.TEXT
                if mem_data.get("memory_type"):
                    try:
                        memory_type = MemoryType(mem_data["memory_type"])
                    except ValueError:
                        pass

                new_id = str(uuid.uuid4()) if (skip_duplicates and existing) else mem_data.get("id", str(uuid.uuid4()))

                entry = self._storage.add_memory(
                    content=mem_data.get("content", ""),
                    category=mem_data.get("category", "general"),
                    tags=mem_data.get("tags", []),
                    privacy=privacy,
                    importance=importance,
                    memory_type=memory_type,
                    layer=layer or self.config.default_layer,
                    source_session=mem_data.get("source_session", ""),
                    source_agent=mem_data.get("source_agent", ""),
                    metadata=mem_data.get("metadata", {}),
                )

                self._index.index_memory(
                    entry.id,
                    mem_data.get("content", ""),
                    metadata={"category": mem_data.get("category", "general")},
                )

                stats["imported"] += 1
            except Exception:
                stats["failed"] += 1

        return stats

    def export_csv(self, output_path: str,
                   category: Optional[str] = None,
                   include_private: bool = False) -> int:
        """导出记忆为 CSV 文件"""
        entries = self._storage.list_memories(
            category=category,
            limit=100000,
            offset=0,
        )

        if not include_private:
            entries = [
                e for e in entries
                if e.privacy in (PrivacyLevel.PUBLIC, PrivacyLevel.INTERNAL)
            ]

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "content", "category", "tags", "privacy",
                "importance", "memory_type", "layer", "access_count",
                "created_at", "updated_at",
            ])

            for e in entries:
                writer.writerow([
                    e.id,
                    e.content,
                    e.category,
                    ",".join(e.tags),
                    e.privacy.value,
                    e.importance.value,
                    e.memory_type.value,
                    e.layer.value,
                    e.access_count,
                    e.created_at,
                    e.updated_at,
                ])

        return len(entries)

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

    @classmethod
    def from_config(cls, config_path: str) -> "ClawMemory":
        """从配置文件创建 ClawMemory 实例"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        config_kwargs = {}
        for key in [
            "db_path", "key_file", "encrypted",
            "default_privacy", "default_importance", "default_layer",
        ]:
            if key in config_data:
                if key == "default_privacy":
                    config_kwargs[key] = PrivacyLevel(config_data[key])
                elif key == "default_importance":
                    config_kwargs[key] = Importance(config_data[key])
                elif key == "default_layer":
                    config_kwargs[key] = MemoryLayer(config_data[key])
                else:
                    config_kwargs[key] = config_data[key]

        config = MemoryConfig(**config_kwargs)
        return cls(config=config)

    @classmethod
    def load_config(cls, config_path: str) -> dict:
        """加载配置文件为字典"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self, config_path: str):
        """保存当前配置到文件"""
        config_data = {
            "db_path": self.config.db_path,
            "key_file": self.config.key_file,
            "encrypted": self.config.encrypted,
            "default_privacy": self.config.default_privacy.value,
            "default_importance": self.config.default_importance.value,
            "default_layer": self.config.default_layer.value,
        }

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
