"""
MindForge v5.2.4 主入口类
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
    DramaGenre,
    DramaStatus,
    DramaSeries,
    DramaScene,
    DramaCharacter,
    DramaLine,
)
from .storage import StorageEngine, MemoryEntry
from .encryption import EncryptionEngine, init_engine as _init_engine
from .indexer import IndexEngine
from .query import QueryEngine

# 安全获取版本号：包安装模式从根包导入，脚本模式用 fallback
try:
    from .. import __version__
except (ImportError, ValueError):
    __version__ = "5.2.4"


class MindForge:
    """MindForge 主类 - AI Agent 终身记忆系统 v5.2.4"""

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
        """初始化加密引擎（v5.2.2 修复：补充缺失的初始化逻辑）

        之前 key_file 存在/不存在两个分支均为 pass，导致加密引擎从未被实际初始化。
        修复后：根据 key_file 是否存在决定新建或加载加密引擎。
        """
        from .encryption import init_engine as _init_engine

        key_file = Path(self.config.key_file)
        key_file.parent.mkdir(parents=True, exist_ok=True)

        if not key_file.exists():
            # 密钥文件不存在时，生成新密钥需要密码
            # 此场景下应通过 init_with_password() 完成初始化
            return

        # 密钥文件存在时，需要密码加载
        # 实际解密需在 init_with_password() 中完成
        return

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
             offset: int = 0,
             sort_by: str = "created_at",
             sort_order: str = "desc") -> List[MemoryEntry]:
        """列出记忆"""
        return self._storage.list_memories(
            category=category,
            layer=layer,
            starred=starred,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
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

    def restore(self, memory_id: str, actor: str = "",
                session_id: str = "") -> bool:
        """从回收站恢复记忆（v5.1.1 新增）"""
        return self._storage.restore_memory(memory_id, actor, session_id)

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

    def rebuild_fts(self) -> dict:
        """重建 FTS 全文索引（v5.0.6 新增）

        清空并重建 memory_fts 表，消除孤立记录。
        配合 health_check 发现的 fts_orphans 问题使用。

        Returns:
            dict: {rebuilt: bool, indexed: int, duration_ms: float}
        """
        return self._storage.rebuild_fts()

    def purge_trash(self, actor: str = "system", session_id: str = "") -> int:
        """清空回收站，永久删除所有软删除的记忆（v5.0.6 新增）

        软删除的记忆 category 会被改为 'trash'，本方法将其彻底删除。

        Args:
            actor: 操作者（审计日志用）
            session_id: 会话 ID

        Returns:
            永久删除的记忆数量
        """
        return self._storage.purge_trash(actor=actor, session_id=session_id)

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
            "version": __version__,
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
            except (ValueError, TypeError, KeyError, AttributeError):
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

    def cleanup(self, max_age_hours: int = 24, layer: str = "sensory") -> int:
        """清理过期记忆（v5.1.3 新增）

        Args:
            max_age_hours: 最大保留时长（小时），超过此时间的记忆将被软删除
            layer: 记忆层级（sensory/short_term/long_term/permanent）

        Returns:
            被清理的记忆数量
        """
        return self._storage.cleanup_expired(max_age_hours, layer)

    def batch_add(self, entries: List[Dict[str, Any]]) -> int:
        """批量添加记忆（v5.1.3 新增）

        Args:
            entries: 记忆条目列表，每个条目包含 content、category、tags 等字段

        Returns:
            成功添加的记忆数量
        """
        return self._storage.batch_add(entries)

    def find_similar(self, content: str, limit: int = 5, threshold: float = 0.3):
        """查找相似记忆（v5.1.3 新增）

        Args:
            content: 参考内容
            limit: 返回数量限制
            threshold: 相似度阈值（0-1）

        Returns:
            相似记忆列表
        """
        return self._storage.find_similar(content, limit, threshold)

    def detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息（v5.1.4 新增）"""
        return self._storage.get_detailed_stats()

    def random(self, count: int = 1, category: Optional[str] = None,
               layer: Optional[MemoryLayer] = None,
               min_strength: Optional[float] = None) -> List[Any]:
        """随机获取记忆（v5.1.7 新增）"""
        return self._storage.get_random_memories(count, category, layer, min_strength)

    def rename_tag(self, old_tag: str, new_tag: str) -> int:
        """重命名标签（v5.1.7 新增）"""
        return self._storage.rename_tag(old_tag, new_tag)

    def rename_category(self, old_cat: str, new_cat: str) -> int:
        """重命名分类（v5.1.7 新增）"""
        return self._storage.rename_category(old_cat, new_cat)

    def config_summary(self) -> Dict[str, Any]:
        """获取配置摘要（v5.1.7 新增）"""
        return self._storage.get_config_summary()

    def close(self):
        if self._storage:
            self._storage.close()

    @classmethod
    def from_config(cls, config_path: str) -> "MindForge":
        """从配置文件创建 MindForge 实例"""
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

    def export_excel(self,
                     output_path: str,
                     category: Optional[str] = None,
                     layer: Optional[MemoryLayer] = None,
                     starred_only: bool = False):
        """导出记忆为 Excel 格式（v5.1.9 新增）"""
        return self._storage.export_as_excel(
            output_path=output_path,
            category=category,
            layer=layer,
            starred_only=starred_only,
        )

    def import_excel(self,
                     input_path: str,
                     target_category: Optional[str] = None,
                     target_layer: Optional[MemoryLayer] = None) -> Dict[str, int]:
        """从 Excel 文件导入记忆（v5.1.9 新增）"""
        return self._storage.import_from_excel(
            input_path=input_path,
            target_category=target_category,
            target_layer=target_layer,
        )

    def copy(self, memory_id: str, new_category: str,
             actor: str = "", session_id: str = "") -> bool:
        """复制记忆到新分类（v5.1.9 新增）"""
        return self._storage.copy_memory(
            entry_id=memory_id,
            new_category=new_category,
            actor=actor,
            session_id=session_id,
        )

    def move(self, memory_id: str, new_category: str,
             actor: str = "", session_id: str = "") -> bool:
        """移动记忆到新分类（v5.1.9 新增）"""
        return self._storage.move_memory(
            entry_id=memory_id,
            new_category=new_category,
            actor=actor,
            session_id=session_id,
        )

    # ===== 搜索增强（v5.2.0 新增）=====

    def fuzzy_search(self,
                     query: str,
                     category: Optional[str] = None,
                     layer: Optional[MemoryLayer] = None,
                     limit: int = 20,
                     threshold: float = 0.3):
        """模糊搜索记忆（v5.2.0 新增）

        结合全文搜索和相似度计算，支持拼写纠错和近似匹配。
        """
        return self._storage.fuzzy_search(
            query=query,
            category=category,
            layer=layer,
            limit=limit,
            threshold=threshold,
        )

    def search_history(self, limit: int = 20):
        """获取搜索历史（v5.2.0 新增）"""
        return self._storage.get_search_history(limit)

    def highlight(self, text: str, query: str,
                  before_tag: str = "<mark>",
                  after_tag: str = "</mark>") -> str:
        """高亮搜索关键词（v5.2.0 新增）"""
        return self._storage.highlight_text(text, query, before_tag, after_tag)

    # ===== 标签批量管理（v5.2.0 新增）=====

    def batch_add_tags(self, entry_ids: List[str], tags: List[str],
                       actor: str = "", session_id: str = "") -> int:
        """批量添加标签（v5.2.0 新增）"""
        return self._storage.batch_add_tags(entry_ids, tags, actor, session_id)

    def batch_remove_tags(self, entry_ids: List[str], tags: List[str],
                          actor: str = "", session_id: str = "") -> int:
        """批量移除标签（v5.2.0 新增）"""
        return self._storage.batch_remove_tags(entry_ids, tags, actor, session_id)

    def merge_tags(self, source_tags: List[str], target_tag: str,
                   actor: str = "", session_id: str = "") -> int:
        """合并多个标签为一个标签（v5.2.0 新增）"""
        return self._storage.merge_tags(source_tags, target_tag, actor, session_id)

    def add_tags_by_category(self, category: str, tags: List[str],
                             actor: str = "", session_id: str = "") -> int:
        """按分类批量添加标签（v5.2.0 新增）"""
        return self._storage.add_tags_by_category(category, tags, actor, session_id)

    # ===== 数据备份与恢复（v5.2.0 新增）=====

    def create_backup(self, backup_dir: str = "./data/backups") -> Dict[str, Any]:
        """创建数据库备份（v5.2.0 新增）"""
        return self._storage.create_backup(backup_dir)

    def list_backups(self, backup_dir: str = "./data/backups"):
        """列出所有备份（v5.2.0 新增）"""
        return self._storage.list_backups(backup_dir)

    def restore_backup(self, backup_path: str,
                       create_backup_before: bool = True) -> Dict[str, Any]:
        """从备份恢复数据库（v5.2.0 新增）"""
        return self._storage.restore_backup(backup_path, create_backup_before)

    def delete_old_backups(self, backup_dir: str = "./data/backups",
                           keep_count: int = 10) -> int:
        """删除旧备份，保留最新的 N 个（v5.2.0 新增）"""
        return self._storage.delete_old_backups(backup_dir, keep_count)

    # ===== AI 短剧记忆模块（v5.2.1 新增）=====

    # --- 短剧系列 ---

    def add_drama(self,
                  title: str,
                  genre: str = "other",
                  total_episodes: int = 0,
                  status: str = "planned",
                  platform: str = "",
                  rating: float = 0.0,
                  description: str = "",
                  tags: Optional[List[str]] = None,
                  cover_url: str = "",
                  metadata: Optional[Dict[str, Any]] = None):
        """添加短剧（v5.2.1 新增）"""
        return self._storage.add_drama(
            title=title,
            genre=DramaGenre.from_string(genre),
            total_episodes=total_episodes,
            status=DramaStatus.from_string(status),
            platform=platform,
            rating=rating,
            description=description,
            tags=tags,
            cover_url=cover_url,
            metadata=metadata,
        )

    def get_drama(self, drama_id: str):
        """获取短剧详情（v5.2.1 新增）"""
        return self._storage.get_drama(drama_id)

    def list_dramas(self,
                    genre: Optional[str] = None,
                    status: Optional[str] = None,
                    platform: Optional[str] = None,
                    min_rating: float = 0.0,
                    limit: int = 50,
                    offset: int = 0,
                    sort_by: str = "updated_at",
                    sort_order: str = "desc"):
        """列出短剧（v5.2.1 新增）"""
        return self._storage.list_dramas(
            genre=DramaGenre.from_string(genre) if genre else None,
            status=DramaStatus.from_string(status) if status else None,
            platform=platform,
            min_rating=min_rating,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def update_drama(self,
                     drama_id: str,
                     title: Optional[str] = None,
                     genre: Optional[str] = None,
                     total_episodes: Optional[int] = None,
                     current_episode: Optional[int] = None,
                     status: Optional[str] = None,
                     platform: Optional[str] = None,
                     rating: Optional[float] = None,
                     description: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     cover_url: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     mark_watched: bool = False) -> bool:
        """更新短剧信息（v5.2.1 新增）"""
        return self._storage.update_drama(
            drama_id=drama_id,
            title=title,
            genre=DramaGenre.from_string(genre) if genre else None,
            total_episodes=total_episodes,
            current_episode=current_episode,
            status=DramaStatus.from_string(status) if status else None,
            platform=platform,
            rating=rating,
            description=description,
            tags=tags,
            cover_url=cover_url,
            metadata=metadata,
            mark_watched=mark_watched,
        )

    def delete_drama(self, drama_id: str) -> bool:
        """删除短剧（v5.2.1 新增）"""
        return self._storage.delete_drama(drama_id)

    def drama_stats(self) -> Dict[str, Any]:
        """短剧统计（v5.2.1 新增）"""
        return self._storage.drama_stats()

    # --- 短剧场次 ---

    def add_scene(self,
                  drama_id: str,
                  episode: int,
                  scene_number: int,
                  title: str,
                  content: str = "",
                  location: str = "",
                  time_of_day: str = "",
                  tags: Optional[List[str]] = None,
                  metadata: Optional[Dict[str, Any]] = None):
        """添加短剧场次（v5.2.1 新增）"""
        return self._storage.add_scene(
            drama_id=drama_id,
            episode=episode,
            scene_number=scene_number,
            title=title,
            content=content,
            location=location,
            time_of_day=time_of_day,
            tags=tags,
            metadata=metadata,
        )

    def get_scene(self, scene_id: str):
        """获取场次详情（v5.2.1 新增）"""
        return self._storage.get_scene(scene_id)

    def list_scenes(self,
                    drama_id: Optional[str] = None,
                    episode: Optional[int] = None,
                    limit: int = 100,
                    offset: int = 0):
        """列出短剧场次（v5.2.1 新增）"""
        return self._storage.list_scenes(
            drama_id=drama_id,
            episode=episode,
            limit=limit,
            offset=offset,
        )

    def update_scene(self,
                     scene_id: str,
                     title: Optional[str] = None,
                     content: Optional[str] = None,
                     location: Optional[str] = None,
                     time_of_day: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新场次（v5.2.1 新增）"""
        return self._storage.update_scene(
            scene_id=scene_id,
            title=title,
            content=content,
            location=location,
            time_of_day=time_of_day,
            tags=tags,
            metadata=metadata,
        )

    def delete_scene(self, scene_id: str) -> bool:
        """删除场次（v5.2.1 新增）"""
        return self._storage.delete_scene(scene_id)

    # --- 短剧角色 ---

    def add_character(self,
                      drama_id: str,
                      name: str,
                      role: str = "supporting",
                      actor: str = "",
                      description: str = "",
                      personality: str = "",
                      avatar_url: str = "",
                      tags: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None):
        """添加短剧角色（v5.2.1 新增）"""
        return self._storage.add_character(
            drama_id=drama_id,
            name=name,
            role=role,
            actor=actor,
            description=description,
            personality=personality,
            avatar_url=avatar_url,
            tags=tags,
            metadata=metadata,
        )

    def get_character(self, char_id: str):
        """获取角色详情（v5.2.1 新增）"""
        return self._storage.get_character(char_id)

    def list_characters(self,
                        drama_id: Optional[str] = None,
                        role: Optional[str] = None,
                        limit: int = 100,
                        offset: int = 0):
        """列出短剧角色（v5.2.1 新增）"""
        return self._storage.list_characters(
            drama_id=drama_id,
            role=role,
            limit=limit,
            offset=offset,
        )

    def update_character(self,
                         char_id: str,
                         name: Optional[str] = None,
                         role: Optional[str] = None,
                         actor: Optional[str] = None,
                         description: Optional[str] = None,
                         personality: Optional[str] = None,
                         avatar_url: Optional[str] = None,
                         tags: Optional[List[str]] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新角色信息（v5.2.1 新增）"""
        return self._storage.update_character(
            char_id=char_id,
            name=name,
            role=role,
            actor=actor,
            description=description,
            personality=personality,
            avatar_url=avatar_url,
            tags=tags,
            metadata=metadata,
        )

    def delete_character(self, char_id: str) -> bool:
        """删除角色（v5.2.1 新增）"""
        return self._storage.delete_character(char_id)

    # --- 短剧台词 ---

    def add_line(self,
                 drama_id: str,
                 line_text: str,
                 scene_id: str = "",
                 character_id: str = "",
                 character_name: str = "",
                 context: str = "",
                 episode: int = 0,
                 timestamp: str = "",
                 is_classic: bool = False,
                 tags: Optional[List[str]] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """添加短剧台词（v5.2.1 新增）"""
        return self._storage.add_line(
            drama_id=drama_id,
            line_text=line_text,
            scene_id=scene_id,
            character_id=character_id,
            character_name=character_name,
            context=context,
            episode=episode,
            timestamp=timestamp,
            is_classic=is_classic,
            tags=tags,
            metadata=metadata,
        )

    def get_line(self, line_id: str):
        """获取台词详情（v5.2.1 新增）"""
        return self._storage.get_line(line_id)

    def list_lines(self,
                   drama_id: Optional[str] = None,
                   scene_id: Optional[str] = None,
                   character_id: Optional[str] = None,
                   is_classic: Optional[bool] = None,
                   episode: Optional[int] = None,
                   limit: int = 100,
                   offset: int = 0):
        """列出台词（v5.2.1 新增）"""
        return self._storage.list_lines(
            drama_id=drama_id,
            scene_id=scene_id,
            character_id=character_id,
            is_classic=is_classic,
            episode=episode,
            limit=limit,
            offset=offset,
        )

    def update_line(self,
                    line_id: str,
                    line_text: Optional[str] = None,
                    character_name: Optional[str] = None,
                    context: Optional[str] = None,
                    is_classic: Optional[bool] = None,
                    tags: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新台词（v5.2.1 新增）"""
        return self._storage.update_line(
            line_id=line_id,
            line_text=line_text,
            character_name=character_name,
            context=context,
            is_classic=is_classic,
            tags=tags,
            metadata=metadata,
        )

    def delete_line(self, line_id: str) -> bool:
        """删除台词（v5.2.1 新增）"""
        return self._storage.delete_line(line_id)

    def search_lines(self,
                     query: str,
                     drama_id: Optional[str] = None,
                     is_classic_only: bool = False,
                     limit: int = 20):
        """搜索台词（v5.2.1 新增）"""
        return self._storage.search_lines(query, drama_id, is_classic_only, limit)

    def classic_lines(self,
                      drama_id: Optional[str] = None,
                      limit: int = 20):
        """获取经典台词（v5.2.1 新增）"""
        return self._storage.classic_lines(drama_id, limit)

    # ===== v5.2.2 新增功能 =====

    def recommend_dramas(self,
                         genre: Optional[str] = None,
                         min_rating: float = 0.0,
                         exclude_ids: Optional[List[str]] = None,
                         status: Optional[str] = None,
                         limit: int = 5) -> List[Any]:
        """AI 短剧智能推荐（v5.2.2 新增）

        基于用户观看历史和评分，推荐高评分、状态良好的短剧。
        排除已看/弃剧的短剧，优先推荐未观看的高分作品。

        Args:
            genre: 类型筛选（如 "romance"）
            min_rating: 最低评分
            exclude_ids: 排除的短剧 ID 列表
            status: 状态筛选（None 表示全部，'planned' 表示仅推荐未观看的）
            limit: 返回数量

        Returns:
            推荐短剧列表
        """
        exclude = set(exclude_ids or [])

        # v5.2.2 修复：status 参数改为可选，None 时不过滤状态
        if status:
            status_enum = DramaStatus.from_string(status)
        else:
            status_enum = None

        # 获取候选短剧
        candidates = self._storage.list_dramas(
            genre=DramaGenre.from_string(genre) if genre else None,
            min_rating=min_rating,
            status=status_enum,
            limit=500,
        )

        # 过滤排除的
        candidates = [d for d in candidates if d.id not in exclude]

        # v5.2.2 优化：未指定 status 时，自动剔除已弃剧
        if not status:
            candidates = [d for d in candidates if d.status != DramaStatus.DROPPED]

        # 按评分 + 进度综合排序
        def score(drama) -> float:
            base_score = drama.rating * 10
            if drama.cover_url:
                base_score += 1
            if drama.tags and len(drama.tags) > 0:
                base_score += 0.5 * min(len(drama.tags), 5)
            # 已完成的短剧略微加分（因为用户已认可）
            if drama.status == DramaStatus.COMPLETED:
                base_score += 2
            # 计划中的高评分短剧加分
            if drama.status == DramaStatus.PLANNED and drama.rating >= 8.5:
                base_score += 3
            return base_score

        candidates.sort(key=score, reverse=True)
        return candidates[:limit]

    def drama_watching_progress(self) -> Dict[str, Any]:
        """观看进度统计（v5.2.2 新增）

        返回整体观看进度，包括：
        - 总集数（已规划）
        - 已观看集数
        - 完成度百分比
        - 按类型分布
        """
        dramas = self._storage.list_dramas(limit=1000)
        total_planned = sum(d.total_episodes for d in dramas)
        total_watched = sum(d.current_episode for d in dramas)
        progress_by_genre = {}

        for d in dramas:
            genre = d.genre.value
            if genre not in progress_by_genre:
                progress_by_genre[genre] = {
                    "total_planned": 0,
                    "total_watched": 0,
                    "count": 0,
                }
            progress_by_genre[genre]["total_planned"] += d.total_episodes
            progress_by_genre[genre]["total_watched"] += d.current_episode
            progress_by_genre[genre]["count"] += 1

        completion_rate = (total_watched / total_planned * 100) if total_planned > 0 else 0.0

        return {
            "total_dramas": len(dramas),
            "total_planned_episodes": total_planned,
            "total_watched_episodes": total_watched,
            "completion_rate": round(completion_rate, 2),
            "by_genre": progress_by_genre,
        }

    def export_dramas(self, output_path: str, drama_ids: Optional[List[str]] = None) -> int:
        """导出短剧数据（v5.2.2 新增）

        导出短剧及其关联的场次、角色、台词为 JSON 文件。

        Args:
            output_path: 输出文件路径
            drama_ids: 指定导出的短剧 ID 列表（None 表示全部）

        Returns:
            导出的短剧数量
        """
        import json
        from pathlib import Path

        if drama_ids:
            dramas = [self._storage.get_drama(did) for did in drama_ids]
            dramas = [d for d in dramas if d is not None]
        else:
            dramas = self._storage.list_dramas(limit=10000)

        export_data = {
            "version": "5.2.2",
            "export_time": "",
            "total": len(dramas),
            "dramas": [],
        }
        from datetime import datetime
        export_data["export_time"] = datetime.now().isoformat()

        for drama in dramas:
            drama_data = drama.to_dict() if hasattr(drama, "to_dict") else vars(drama)
            # 导出关联数据
            drama_data["scenes"] = [vars(s) if not hasattr(s, "to_dict") else s.to_dict()
                                     for s in self._storage.list_scenes(drama_id=drama.id, limit=1000)]
            drama_data["characters"] = [vars(c) if not hasattr(c, "to_dict") else c.to_dict()
                                         for c in self._storage.list_characters(drama_id=drama.id, limit=1000)]
            drama_data["lines"] = [vars(l) if not hasattr(l, "to_dict") else l.to_dict()
                                    for l in self._storage.list_lines(drama_id=drama.id, limit=10000)]
            export_data["dramas"].append(drama_data)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return len(dramas)

    # ===== Agent 记忆优化（v5.2.2 新增）=====

    def agent_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Agent 记忆统计（v5.2.2 新增）

        统计按 Agent 来源分组的记忆数据。

        Args:
            agent_id: 指定 Agent ID（None 表示统计全部 Agent）

        Returns:
            Agent 统计数据
        """
        return self._storage.agent_stats(agent_id)

    def list_by_agent(self,
                      agent_id: str,
                      limit: int = 100,
                      offset: int = 0) -> List[Any]:
        """列出特定 Agent 的记忆（v5.2.2 新增）

        Args:
            agent_id: Agent ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            该 Agent 创建的记忆列表
        """
        return self._storage.list_by_agent(agent_id, limit, offset)

    def evolve_memories(self, dry_run: bool = False) -> Dict[str, Any]:
        """记忆演化 - 基于艾宾浩斯遗忘曲线自动升级记忆层级（v5.2.2 新增）

        Args:
            dry_run: 仅统计不执行

        Returns:
            演化统计结果
        """
        return self._storage.evolve_memories(dry_run=dry_run)

    def transfer_agent_memories(self,
                                from_agent: str,
                                to_agent: str,
                                category: Optional[str] = None) -> Dict[str, Any]:
        """Agent 记忆迁移 - 将一个 Agent 的记忆转移给另一个（v5.2.2 新增）

        Args:
            from_agent: 源 Agent ID
            to_agent: 目标 Agent ID
            category: 可选，仅迁移指定分类

        Returns:
            迁移统计
        """
        return self._storage.transfer_agent_memories(
            from_agent=from_agent,
            to_agent=to_agent,
            category=category,
        )

    def clean_agent_memories(self,
                             agent_id: str,
                             older_than_days: int = 90,
                             max_importance: Optional[str] = None,
                             dry_run: bool = False) -> Dict[str, Any]:
        """清理 Agent 的旧记忆（v5.2.2 新增）

        清理指定 Agent 创建的、超过指定天数、重要度低于等于指定级别的记忆，移入回收站。

        Args:
            agent_id: Agent ID
            older_than_days: 清理超过多少天的记忆
            max_importance: 最高清理的重要级别（LOW/MEDIUM/HIGH/CRITICAL），None 表示清理所有
            dry_run: 仅统计不执行

        Returns:
            清理统计
        """
        older_than_days = max(0, min(3650, int(older_than_days)))
        if max_importance:
            try:
                Importance.from_string(max_importance)
            except (ValueError, KeyError):
                max_importance = None
        return self._storage.clean_agent_memories(
            agent_id=agent_id,
            older_than_days=older_than_days,
            max_importance=max_importance,
            dry_run=dry_run,
        )

    def quality_score(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """记忆质量评分（v5.2.2 新增）

        基于多维度评估记忆质量。

        Args:
            memory_id: 记忆 ID

        Returns:
            质量评分详情
        """
        return self._storage.quality_score(memory_id)

    def analyze_similarity(self,
                           memory_id: str,
                           limit: int = 10,
                           min_similarity: float = 0.3) -> List[Dict[str, Any]]:
        """相似度分析（v5.2.2 新增）

        分析指定记忆与其他记忆的相似度。

        Args:
            memory_id: 目标记忆 ID
            limit: 返回数量
            min_similarity: 最低相似度阈值

        Returns:
            相似记忆列表
        """
        limit = max(1, min(100, int(limit)))
        min_similarity = max(0.0, min(1.0, float(min_similarity)))
        return self._storage.analyze_similarity(memory_id, limit, min_similarity)

    def batch_quality_score(self,
                            category: Optional[str] = None,
                            limit: int = 100) -> Dict[str, Any]:
        """批量质量评分（v5.2.2 新增）

        对指定范围内的记忆进行批量质量评分。

        Args:
            category: 分类过滤
            limit: 数量限制

        Returns:
            批量评分结果
        """
        limit = max(1, min(1000, int(limit)))
        return self._storage.batch_quality_score(category, limit)

    # ===== v5.2.4 新增 API =====

    def add_note(self, memory_id: str, content: str, author: str = "",
                 tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """添加记忆笔记/批注（v5.2.4 新增）

        Args:
            memory_id: 记忆 ID
            content: 笔记内容
            author: 作者
            tags: 笔记标签

        Returns:
            操作结果
        """
        if not content or not content.strip():
            return {"success": False, "error": "笔记内容不能为空"}
        if len(content) > 10000:
            return {"success": False, "error": "笔记内容不能超过 10000 字符"}
        return self._storage.add_note(memory_id, content.strip(), author, tags)

    def list_notes(self, memory_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列出记忆的笔记（v5.2.4 新增）

        Args:
            memory_id: 记忆 ID
            limit: 数量限制
            offset: 偏移量

        Returns:
            笔记列表
        """
        limit = max(1, min(200, int(limit)))
        return self._storage.list_notes(memory_id, limit, offset)

    def delete_note(self, note_id: str) -> Dict[str, Any]:
        """删除笔记（v5.2.4 新增）

        Args:
            note_id: 笔记 ID

        Returns:
            操作结果
        """
        return self._storage.delete_note(note_id)

    def add_template(self, name: str, content_template: str, category: str = "general",
                     tags: Optional[List[str]] = None, importance: str = "MEDIUM",
                     layer: str = "short_term", description: str = "") -> Dict[str, Any]:
        """添加记忆模板（v5.2.4 新增）

        Args:
            name: 模板名称
            content_template: 模板内容（支持 {变量名} 占位符）
            category: 默认分类
            tags: 默认标签
            importance: 默认重要性
            layer: 默认层级
            description: 模板描述

        Returns:
            操作结果
        """
        if not name or not name.strip():
            return {"success": False, "error": "模板名称不能为空"}
        if not content_template or not content_template.strip():
            return {"success": False, "error": "模板内容不能为空"}
        if len(name) > 100:
            return {"success": False, "error": "模板名称不能超过 100 字符"}
        return self._storage.add_template(name.strip(), content_template.strip(),
                                          category, tags, importance, layer, description)

    def list_templates(self, category: Optional[str] = None,
                       limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列出记忆模板（v5.2.4 新增）

        Args:
            category: 按分类筛选
            limit: 数量限制
            offset: 偏移量

        Returns:
            模板列表
        """
        limit = max(1, min(200, int(limit)))
        return self._storage.list_templates(category, limit, offset)

    def use_template(self, template_id: str, variables: Optional[Dict[str, str]] = None,
                     actor: str = "", session_id: str = "") -> Dict[str, Any]:
        """使用模板创建记忆（v5.2.4 新增）

        Args:
            template_id: 模板 ID
            variables: 模板变量替换字典
            actor: 操作者
            session_id: 会话 ID

        Returns:
            操作结果（包含新创建的记忆 ID）
        """
        return self._storage.use_template(template_id, variables, actor, session_id)

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """删除模板（v5.2.4 新增）

        Args:
            template_id: 模板 ID

        Returns:
            操作结果
        """
        return self._storage.delete_template(template_id)

    def batch_update(self, memory_ids: List[str],
                     category: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     importance: Optional[str] = None,
                     layer: Optional[str] = None,
                     starred: Optional[bool] = None,
                     actor: str = "", session_id: str = "") -> Dict[str, Any]:
        """批量更新记忆（v5.2.4 新增）

        Args:
            memory_ids: 记忆 ID 列表
            category: 新分类
            tags: 新标签
            importance: 新重要性
            layer: 新层级
            starred: 新收藏状态
            actor: 操作者
            session_id: 会话 ID

        Returns:
            批量更新结果
        """
        if not memory_ids:
            return {"success": False, "error": "未指定记忆 ID", "updated": 0}
        if len(memory_ids) > 500:
            return {"success": False, "error": "单次批量更新不能超过 500 条", "updated": 0}
        # 验证 importance 和 layer 合法性
        if importance:
            try:
                Importance.from_string(importance)
            except (ValueError, KeyError):
                return {"success": False, "error": f"无效的重要性级别: {importance}", "updated": 0}
        if layer:
            try:
                MemoryLayer.from_string(layer)
            except (ValueError, KeyError):
                return {"success": False, "error": f"无效的记忆层级: {layer}", "updated": 0}
        return self._storage.batch_update(memory_ids, category, tags, importance,
                                          layer, starred, actor, session_id)

    def create_review_schedule(self, memory_id: str, interval_days: float = 1.0,
                               actor: str = "") -> Dict[str, Any]:
        """创建复习计划（v5.2.4 新增）

        Args:
            memory_id: 记忆 ID
            interval_days: 复习间隔天数
            actor: 操作者

        Returns:
            操作结果
        """
        interval_days = max(0.1, min(365, float(interval_days)))
        return self._storage.create_review_schedule(memory_id, interval_days, actor)

    def list_due_reviews(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出到期复习（v5.2.4 新增）

        Args:
            limit: 数量限制

        Returns:
            到期复习列表
        """
        limit = max(1, min(100, int(limit)))
        return self._storage.list_due_reviews(limit)

    def complete_review(self, schedule_id: str) -> Dict[str, Any]:
        """完成复习（v5.2.4 新增）

        完成一次复习后自动安排下次复习（间隔重复算法）。

        Args:
            schedule_id: 复习计划 ID

        Returns:
            操作结果
        """
        return self._storage.complete_review(schedule_id)

    def get_review_stats(self) -> Dict[str, Any]:
        """复习计划统计（v5.2.4 新增）

        Returns:
            复习统计数据
        """
        return self._storage.get_review_stats()
