"""
MindForge v5.0 存储引擎
支持四层记忆架构：感官记忆 → 短期记忆 → 长期记忆 → 永久记忆
"""

import sqlite3
import json
import uuid
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from .types import PrivacyLevel, Importance, MemoryType, MemoryLayer
from .encryption import EncryptionEngine, EncryptedBlob


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    privacy: PrivacyLevel = PrivacyLevel.INTERNAL
    importance: Importance = Importance.MEDIUM
    memory_type: MemoryType = MemoryType.TEXT
    layer: MemoryLayer = MemoryLayer.SHORT_TERM
    source_session: str = ""
    source_agent: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    last_accessed_at: float = 0.0
    access_count: int = 0
    consolidation_count: int = 0
    forgetting_score: float = 0.0
    strength: float = 1.0
    starred: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    encrypted: bool = False
    ciphertext: Optional[bytes] = None
    nonce: Optional[bytes] = None
    salt: Optional[bytes] = None

    @property
    def preview(self) -> str:
        if self.encrypted and not self.content:
            return "[已加密]"
        return self.content[:100]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "privacy": self.privacy.value,
            "importance": self.importance.value,
            "memory_type": self.memory_type.value,
            "layer": self.layer.value,
            "source_session": self.source_session,
            "source_agent": self.source_agent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_accessed_at": self.last_accessed_at,
            "access_count": self.access_count,
            "consolidation_count": self.consolidation_count,
            "forgetting_score": self.forgetting_score,
            "strength": self.strength,
            "starred": self.starred,
            "metadata": self.metadata,
        }


@dataclass
class AuditRecord:
    """审计记录"""
    id: str
    action: str
    memory_id: str
    actor: str
    session_id: str
    privacy_level: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


class StorageEngine:
    """存储引擎"""

    def __init__(self, db_path: str = "./data/memory.db",
                 encryption: Optional[EncryptionEngine] = None,
                 encrypted: bool = True):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.encryption = encryption
        self.encrypted = encrypted and encryption is not None
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT,
                ciphertext BLOB,
                nonce BLOB,
                salt BLOB,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '[]',
                privacy TEXT DEFAULT 'INTERNAL',
                importance TEXT DEFAULT 'MEDIUM',
                memory_type TEXT DEFAULT 'text',
                layer TEXT DEFAULT 'short_term',
                source_session TEXT DEFAULT '',
                source_agent TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                last_accessed_at REAL,
                access_count INTEGER DEFAULT 0,
                consolidation_count INTEGER DEFAULT 0,
                forgetting_score REAL DEFAULT 0.0,
                strength REAL DEFAULT 1.0,
                starred INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                encrypted INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_privacy ON memories(privacy);
            CREATE INDEX IF NOT EXISTS idx_layer ON memories(layer);
            CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance);
            CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_starred ON memories(starred);

            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                content, category, tags,
                content=''
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                action TEXT,
                memory_id TEXT,
                actor TEXT,
                session_id TEXT,
                privacy_level TEXT,
                timestamp REAL,
                details TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_audit_memory ON audit_log(memory_id);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

            CREATE TABLE IF NOT EXISTS knowledge_graph (
                id TEXT PRIMARY KEY,
                entity TEXT,
                entity_type TEXT,
                description TEXT,
                metadata TEXT DEFAULT '{}',
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS graph_relations (
                id TEXT PRIMARY KEY,
                from_entity TEXT,
                to_entity TEXT,
                relation_type TEXT,
                weight REAL DEFAULT 1.0,
                memory_ids TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_kg_entity ON knowledge_graph(entity);
            CREATE INDEX IF NOT EXISTS idx_relation_from ON graph_relations(from_entity);
            CREATE INDEX IF NOT EXISTS idx_relation_to ON graph_relations(to_entity);
        """)
        conn.commit()

    def add_memory(self,
                   content: str,
                   category: str = "general",
                   tags: Optional[List[str]] = None,
                   privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
                   importance: Importance = Importance.MEDIUM,
                   memory_type: MemoryType = MemoryType.TEXT,
                   layer: MemoryLayer = MemoryLayer.SHORT_TERM,
                   source_session: str = "",
                   source_agent: str = "",
                   starred: bool = False,
                   metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        """添加记忆"""
        now = time.time()
        entry_id = str(uuid.uuid4())

        ciphertext = None
        nonce = None
        salt = None
        stored_content = content

        if self.encrypted and self.encryption:
            blob = self.encryption.encrypt(content)
            ciphertext = blob.ciphertext
            nonce = blob.nonce
            salt = blob.salt
            stored_content = ""

        entry = MemoryEntry(
            id=entry_id,
            content=stored_content,
            category=category,
            tags=tags or [],
            privacy=privacy,
            importance=importance,
            memory_type=memory_type,
            layer=layer,
            source_session=source_session,
            source_agent=source_agent,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
            metadata=metadata or {},
            starred=starred,
            encrypted=self.encrypted,
            ciphertext=ciphertext,
            nonce=nonce,
            salt=salt,
        )

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO memories (
                id, content, ciphertext, nonce, salt, category, tags,
                privacy, importance, memory_type, layer,
                source_session, source_agent, created_at, updated_at,
                last_accessed_at, access_count, consolidation_count,
                forgetting_score, strength, starred, metadata, encrypted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id, entry.content, entry.ciphertext, entry.nonce, entry.salt,
            entry.category, json.dumps(entry.tags, ensure_ascii=False),
            entry.privacy.value, entry.importance.value, entry.memory_type.value,
            entry.layer.value, entry.source_session, entry.source_agent,
            entry.created_at, entry.updated_at, entry.last_accessed_at,
            entry.access_count, entry.consolidation_count,
            entry.forgetting_score, entry.strength, int(entry.starred),
            json.dumps(entry.metadata, ensure_ascii=False), int(entry.encrypted)
        ))

        if not self.encrypted:
            conn.execute("""
                INSERT INTO memory_fts (rowid, content, category, tags)
                VALUES ((SELECT rowid FROM memories WHERE id = ?), ?, ?, ?)
            """, (entry.id, content, category, json.dumps(tags or [], ensure_ascii=False)))

        conn.commit()
        self._add_audit("add", entry.id, source_agent, source_session, privacy.value)

        return entry

    def get_memory(self, memory_id: str,
                   actor: str = "", session_id: str = "") -> Optional[MemoryEntry]:
        """获取记忆"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return None

        entry = self._row_to_entry(row)
        self._update_access(entry, actor, session_id)
        return entry

    def decrypt_content(self, entry: MemoryEntry) -> str:
        """解密记忆内容"""
        if not entry.encrypted or not self.encryption:
            return entry.content

        if entry.ciphertext and entry.nonce and entry.salt:
            blob = EncryptedBlob(
                ciphertext=entry.ciphertext,
                nonce=entry.nonce,
                salt=entry.salt,
            )
            return self.encryption.decrypt(blob)
        return entry.content

    def list_memories(self,
                      category: Optional[str] = None,
                      layer: Optional[MemoryLayer] = None,
                      privacy: Optional[PrivacyLevel] = None,
                      starred: Optional[bool] = None,
                      created_after: Optional[float] = None,
                      created_before: Optional[float] = None,
                      limit: int = 50,
                      offset: int = 0,
                      sort_by: str = "created_at",
                      sort_order: str = "desc") -> List[MemoryEntry]:
        """列出记忆"""
        conn = self._get_conn()
        query = "SELECT * FROM memories WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if layer:
            query += " AND layer = ?"
            params.append(layer.value)
        if privacy:
            query += " AND privacy = ?"
            params.append(privacy.value)
        if starred is not None:
            query += " AND starred = ?"
            params.append(1 if starred else 0)
        if created_after is not None:
            query += " AND created_at >= ?"
            params.append(created_after)
        if created_before is not None:
            query += " AND created_at <= ?"
            params.append(created_before)

        valid_sort_columns = ["created_at", "updated_at", "last_accessed_at", "access_count", "strength", "forgetting_score"]
        if sort_by not in valid_sort_columns:
            sort_by = "created_at"
        sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"

        query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def update_memory(self,
                      entry_id: str,
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
        """更新记忆

        v5.0.6 修复：更新 content/category/tags 时同步刷新 FTS 索引，
        避免搜索返回旧内容（与 v5.0.5 的 delete FTS 修复对应）。

        contentless FTS5 表的 'delete' 命令需要索引中**当前的值**（旧值）才能
        正确从倒排索引中移除 token。因此必须：先读旧值 → 用旧值 delete FTS
        → 更新 memories 表 → 用新值 insert FTS。
        """
        conn = self._get_conn()
        now = time.time()

        updates = []
        params = []
        fts_dirty = False  # 是否需要刷新 FTS

        if content is not None:
            if self.encrypted and self.encryption:
                blob = self.encryption.encrypt(content)
                updates.append("ciphertext = ?")
                updates.append("nonce = ?")
                updates.append("salt = ?")
                params.extend([blob.ciphertext, blob.nonce, blob.salt])
                updates.append("content = ?")
                params.append("")
            else:
                updates.append("content = ?")
                params.append(content)
                fts_dirty = True

        if category is not None:
            updates.append("category = ?")
            params.append(category)
            fts_dirty = True
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
            fts_dirty = True
        if privacy is not None:
            updates.append("privacy = ?")
            params.append(privacy.value)
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance.value)
        if layer is not None:
            updates.append("layer = ?")
            params.append(layer.value)
        if starred is not None:
            updates.append("starred = ?")
            params.append(1 if starred else 0)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates:
            return False

        # FTS 刷新步骤 1：更新前先读取旧值，用旧值删除 FTS 索引条目
        old_fts_row = None
        if fts_dirty and not self.encrypted:
            old_fts_row = conn.execute(
                "SELECT rowid, content, category, tags FROM memories WHERE id = ?",
                (entry_id,)
            ).fetchone()
            if old_fts_row:
                try:
                    conn.execute(
                        "INSERT INTO memory_fts(memory_fts, rowid, content, category, tags) "
                        "VALUES('delete', ?, ?, ?, ?)",
                        (old_fts_row[0], old_fts_row[1] or "", old_fts_row[2] or "", old_fts_row[3] or "[]")
                    )
                except Exception:
                    pass

        # 更新 memories 表
        updates.append("updated_at = ?")
        params.append(now)
        params.append(entry_id)
        conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", params)

        # FTS 刷新步骤 2：用新值重新插入 FTS 索引条目
        if old_fts_row is not None:
            new_row = conn.execute(
                "SELECT rowid, content, category, tags FROM memories WHERE id = ?",
                (entry_id,)
            ).fetchone()
            if new_row:
                try:
                    conn.execute(
                        "INSERT INTO memory_fts (rowid, content, category, tags) VALUES (?, ?, ?, ?)",
                        (new_row[0], new_row[1] or "", new_row[2] or "", new_row[3] or "[]")
                    )
                except Exception:
                    pass

        conn.commit()

        self._add_audit("update", entry_id, actor, session_id, privacy.value if privacy else "")
        return True

    def _refresh_fts(self, conn: sqlite3.Connection, entry_id: str):
        """刷新单条记忆的 FTS 索引（contentless FTS5：先 delete 旧条目再 insert 新条目）

        v5.0.6 新增：辅助方法，读取当前 memories 表中的值来刷新 FTS。
        注意：此方法用 memories 表的**当前值**做 delete 和 insert，仅适用于
        memories 表尚未被更新的场景（如索引修复）。update_memory 中的 FTS
        同步已内联实现（需在更新前读旧值），不调用此方法。
        """
        row = conn.execute(
            "SELECT rowid, content, category, tags FROM memories WHERE id = ?",
            (entry_id,)
        ).fetchone()
        if not row:
            return
        try:
            conn.execute(
                "INSERT INTO memory_fts(memory_fts, rowid, content, category, tags) "
                "VALUES('delete', ?, ?, ?, ?)",
                (row[0], row[1] or "", row[2] or "", row[3] or "[]")
            )
        except Exception:
            pass
        try:
            conn.execute(
                "INSERT INTO memory_fts (rowid, content, category, tags) VALUES (?, ?, ?, ?)",
                (row[0], row[1] or "", row[2] or "", row[3] or "[]")
            )
        except Exception:
            pass

    def rebuild_fts(self) -> dict:
        """重建 FTS 全文索引（v5.0.6 新增）

        清空并重新构建 memory_fts 表，消除孤立记录，确保索引与 memories 表一致。
        配合 health_check 发现的 fts_orphans 问题使用。

        注意：contentless FTS5 表（content=''）不支持 DELETE FROM，
        必须用 DROP + CREATE 重建表结构来清空。

        Returns:
            {
                "rebuilt": True,
                "indexed": int,      # 重建索引的条目数
                "duration_ms": float,
            }
        """
        import time as _time
        start = _time.time()
        conn = self._get_conn()

        # contentless FTS5 表不能用 DELETE FROM，用 DROP + CREATE 重建
        conn.execute("DROP TABLE IF EXISTS memory_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE memory_fts USING fts5(
                content, category, tags,
                content=''
            )
        """)

        # 重新索引所有非加密记忆
        rows = conn.execute(
            "SELECT rowid, content, category, tags FROM memories WHERE encrypted = 0"
        ).fetchall()
        indexed = 0
        for row in rows:
            try:
                conn.execute(
                    "INSERT INTO memory_fts (rowid, content, category, tags) VALUES (?, ?, ?, ?)",
                    (row[0], row[1] or "", row[2] or "", row[3] or "[]")
                )
                indexed += 1
            except Exception:
                pass

        conn.commit()
        elapsed = (_time.time() - start) * 1000
        return {
            "rebuilt": True,
            "indexed": indexed,
            "duration_ms": round(elapsed, 2),
        }

    def purge_trash(self,
                    actor: str = "system",
                    session_id: str = "") -> int:
        """清空回收站，永久删除所有 category='trash' 的记忆（v5.0.6 新增）

        软删除（delete_memory(hard_delete=False)）会把 category 改为 'trash'，
        本方法将这些记录彻底删除，并同步清理 FTS 索引。

        Args:
            actor: 操作者（审计日志用）
            session_id: 会话 ID

        Returns:
            永久删除的记忆数量
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, rowid, content, category, tags FROM memories WHERE category = 'trash'"
        ).fetchall()

        if not rows:
            return 0

        ids = [row[0] for row in rows]
        placeholders = ",".join(["?"] * len(ids))

        conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)

        # 同步清理 FTS（contentless FTS5 用 'delete' 命令）
        for row in rows:
            try:
                conn.execute(
                    "INSERT INTO memory_fts(memory_fts, rowid, content, category, tags) "
                    "VALUES('delete', ?, ?, ?, ?)",
                    (row[1], row[2] or "", row[3] or "", row[4] or "[]")
                )
            except Exception:
                pass

        conn.commit()
        for mid in ids:
            self._add_audit("purge", mid, actor, session_id, "")

        return len(ids)

    def delete_memory(self, entry_id: str,
                      actor: str = "", session_id: str = "",
                      hard_delete: bool = False) -> bool:
        """删除记忆

        v5.0.5 修复：硬删除时同步清理 FTS 索引，避免搜索时返回已删除的记忆。
        注意：contentless FTS5 表（content=''）不支持标准 DELETE，
        必须用 'delete' 特殊命令。
        """
        conn = self._get_conn()

        if hard_delete:
            # 先取 rowid 和 FTS 字段用于清理
            row = conn.execute(
                "SELECT rowid, content, category, tags FROM memories WHERE id = ?",
                (entry_id,)
            ).fetchone()
            conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
            if row:
                try:
                    # contentless FTS5 必须用 'delete' 命令
                    conn.execute(
                        "INSERT INTO memory_fts(memory_fts, rowid, content, category, tags) "
                        "VALUES('delete', ?, ?, ?, ?)",
                        (row[0], row[1] or "", row[2] or "", row[3] or "[]")
                    )
                except Exception:
                    pass
        else:
            now = time.time()
            # v5.1.1 修复：软删除时保存原分类到 metadata，便于恢复
            row = conn.execute(
                "SELECT category, metadata FROM memories WHERE id = ?",
                (entry_id,)
            ).fetchone()
            if row:
                try:
                    meta = json.loads(row["metadata"]) if row["metadata"] else {}
                except Exception:
                    meta = {}
                meta["_original_category"] = row["category"]
                conn.execute(
                    "UPDATE memories SET category = 'trash', updated_at = ?, metadata = ? WHERE id = ?",
                    (now, json.dumps(meta, ensure_ascii=False), entry_id)
                )
            else:
                conn.execute("UPDATE memories SET category = 'trash', updated_at = ? WHERE id = ?",
                             (now, entry_id))

        conn.commit()
        self._add_audit("delete", entry_id, actor, session_id, "")
        return True

    def batch_delete(self,
                     category: Optional[str] = None,
                     layer: Optional[MemoryLayer] = None,
                     starred: Optional[bool] = None,
                     created_after: Optional[float] = None,
                     created_before: Optional[float] = None,
                     hard_delete: bool = False,
                     actor: str = "",
                     session_id: str = "") -> int:
        """批量删除记忆，返回删除数量

        v5.0.5 修复：硬删除时同步清理 FTS 索引（用 'delete' 特殊命令）。
        """
        conn = self._get_conn()
        query = "SELECT id, rowid, content, category, tags FROM memories WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if layer:
            query += " AND layer = ?"
            params.append(layer.value)
        if starred is not None:
            query += " AND starred = ?"
            params.append(1 if starred else 0)
        if created_after is not None:
            query += " AND created_at >= ?"
            params.append(created_after)
        if created_before is not None:
            query += " AND created_at <= ?"
            params.append(created_before)

        rows = conn.execute(query, params).fetchall()

        if not rows:
            return 0

        ids = [row[0] for row in rows]
        now = time.time()

        if hard_delete:
            placeholders = ",".join(["?"] * len(ids))
            conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            # 同步清理 FTS（contentless FTS5 用 'delete' 命令）
            for row in rows:
                try:
                    conn.execute(
                        "INSERT INTO memory_fts(memory_fts, rowid, content, category, tags) "
                        "VALUES('delete', ?, ?, ?, ?)",
                        (row[1], row[2] or "", row[3] or "", row[4] or "[]")
                    )
                except Exception:
                    pass
        else:
            # v5.1.1 修复：批量软删除时也保存原分类到 metadata
            for row in rows:
                try:
                    meta = json.loads(row["metadata"]) if row.get("metadata") else {}
                except Exception:
                    meta = {}
                meta["_original_category"] = row["category"]
                conn.execute(
                    "UPDATE memories SET category = 'trash', updated_at = ?, metadata = ? WHERE id = ?",
                    (now, json.dumps(meta, ensure_ascii=False), row["id"])
                )

        conn.commit()
        for mid in ids:
            self._add_audit("delete", mid, actor, session_id, "")

        return len(ids)

    def restore_memory(self, entry_id: str,
                       actor: str = "", session_id: str = "") -> bool:
        """从回收站恢复记忆（v5.1.1 新增）

        将 category='trash' 的记忆恢复到软删除前的原分类；
        如果找不到原分类，则恢复到 'default'。
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT category, metadata FROM memories WHERE id = ?",
            (entry_id,)
        ).fetchone()

        if not row or row["category"] != "trash":
            return False

        try:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
        except Exception:
            meta = {}

        original_category = meta.pop("_original_category", "default")
        now = time.time()

        conn.execute(
            "UPDATE memories SET category = ?, metadata = ?, updated_at = ? WHERE id = ?",
            (original_category, json.dumps(meta, ensure_ascii=False), now, entry_id)
        )
        conn.commit()
        self._add_audit(
            "restore", entry_id, actor, session_id, "",
            details={"message": f"恢复到 {original_category}", "original_category": original_category}
        )
        return True

    def count_memories(self, category: Optional[str] = None,
                       layer: Optional[MemoryLayer] = None) -> int:
        """统计记忆数量"""
        conn = self._get_conn()
        query = "SELECT COUNT(*) FROM memories WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if layer:
            query += " AND layer = ?"
            params.append(layer.value)

        return conn.execute(query, params).fetchone()[0]

    def get_stats(self) -> dict:
        """获取统计信息"""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

        by_privacy = {}
        for row in conn.execute("SELECT privacy, COUNT(*) FROM memories GROUP BY privacy"):
            by_privacy[row[0]] = row[1]

        by_layer = {}
        for row in conn.execute("SELECT layer, COUNT(*) FROM memories GROUP BY layer"):
            by_layer[row[0]] = row[1]

        by_importance = {}
        for row in conn.execute("SELECT importance, COUNT(*) FROM memories GROUP BY importance"):
            by_importance[row[0]] = row[1]

        top_categories = {}
        for row in conn.execute(
            "SELECT category, COUNT(*) as c FROM memories GROUP BY category ORDER BY c DESC LIMIT 10"
        ):
            top_categories[row[0]] = row[1]

        starred_count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE starred = 1"
        ).fetchone()[0]

        tag_counts = {}
        for row in conn.execute("SELECT tags FROM memories"):
            if row[0]:
                try:
                    tags = json.loads(row[0])
                    for tag in tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

        top_tags = dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10])

        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total": total,
            "db_size_bytes": db_size,
            "db_path": str(self.db_path),
            "by_privacy": by_privacy,
            "by_layer": by_layer,
            "by_importance": by_importance,
            "top_categories": top_categories,
            "starred_count": starred_count,
            "top_tags": top_tags,
        }

    def search_by_tag(self, tag: str,
                      category: Optional[str] = None,
                      layer: Optional[MemoryLayer] = None,
                      limit: int = 50,
                      offset: int = 0) -> List[MemoryEntry]:
        """按标签搜索记忆

        v5.0.4 优化：移除双重过滤（SQL LIKE 已足够精确，Python 端再过滤是冗余）。
        仅在边界情况下（tags 字段非合法 JSON）跳过该项。
        """
        conn = self._get_conn()
        query = "SELECT * FROM memories WHERE tags LIKE ?"
        params = [f'%"{tag}"%']

        if category:
            query += " AND category = ?"
            params.append(category)
        if layer:
            query += " AND layer = ?"
            params.append(layer.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            entry = self._row_to_entry(row)
            # 仅校验 JSON 解析结果（防御性），不再做二次标签过滤
            if tag in entry.tags:
                results.append(entry)
        return results

    def deduplicate(self,
                    category: Optional[str] = None,
                    similarity_threshold: float = 0.95,
                    dry_run: bool = True,
                    actor: str = "system",
                    session_id: str = "") -> dict:
        """记忆去重 - 检测并合并高度相似的记忆条目

        v5.0.4 新增功能。

        算法：
        - 同分类下，对 content 做标准化（去空白/小写）后比较
        - 完全相同（相似度=1.0）：保留最早一条，删除其余
        - 高度相似（>= similarity_threshold）：保留 starred 优先 / 重要性更高 / 更新时间更晚的一条
        - dry_run=True 时仅返回报告，不实际删除

        Args:
            category: 限定分类，None 表示全部分类
            similarity_threshold: 相似度阈值，默认 0.95
            dry_run: 试运行模式，只报告不删除
            actor: 操作者（用于审计日志）
            session_id: 会话 ID

        Returns:
            {
                "duplicates_found": int,    # 发现的重复组数
                "would_remove": int,        # 待删除条数（dry_run=True 时）
                "removed": int,             # 实际删除条数（dry_run=False 时）
                "details": [...],           # 详情
            }
        """
        conn = self._get_conn()
        query = "SELECT * FROM memories WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at ASC"
        rows = conn.execute(query, params).fetchall()
        entries = [self._row_to_entry(r) for r in rows]

        def normalize(s: str) -> str:
            return "".join(s.lower().split())

        def similarity(a: str, b: str) -> float:
            na, nb = normalize(a), normalize(b)
            if not na or not nb:
                return 0.0
            if na == nb:
                return 1.0
            # 简单的字符级 Jaccard 相似度
            sa, sb = set(na), set(nb)
            inter = len(sa & sb)
            union = len(sa | sb)
            return inter / union if union else 0.0

        # 按分类分组
        groups: Dict[str, List[MemoryEntry]] = {}
        for e in entries:
            groups.setdefault(e.category, []).append(e)

        duplicates = []
        for cat, items in groups.items():
            n = len(items)
            for i in range(n):
                for j in range(i + 1, n):
                    sim = similarity(items[i].content, items[j].content)
                    if sim >= similarity_threshold:
                        duplicates.append((cat, sim, items[i], items[j]))

        details = []
        removed = 0
        for cat, sim, a, b in duplicates:
            # 选择保留哪一条：starred > importance > 更新时间更晚
            def keep_score(e: MemoryEntry) -> tuple:
                imp_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                return (
                    int(e.starred),
                    imp_order.get(e.importance.value, 2),
                    e.updated_at,
                )

            keeper, loser = (a, b) if keep_score(a) >= keep_score(b) else (b, a)
            details.append({
                "category": cat,
                "similarity": round(sim, 4),
                "keeper_id": keeper.id,
                "loser_id": loser.id,
                "keeper_preview": keeper.preview,
                "loser_preview": loser.preview,
            })

            if not dry_run:
                self.delete_memory(loser.id, hard_delete=True, actor=actor, session_id=session_id)
                removed += 1

        return {
            "duplicates_found": len(duplicates),
            "would_remove": len(duplicates) if dry_run else 0,
            "removed": removed,
            "details": details,
        }

    def export_as_markdown(self,
                           output_path: str,
                           category: Optional[str] = None,
                           layer: Optional[MemoryLayer] = None,
                           starred_only: bool = False) -> Path:
        """导出记忆为 Markdown 格式

        v5.0.4 新增功能。

        Args:
            output_path: 输出文件路径
            category: 限定分类
            layer: 限定层级
            starred_only: 仅导出收藏的记忆

        Returns:
            导出文件的 Path 对象
        """
        entries = self.list_memories(
            category=category,
            layer=layer,
            starred=starred_only if starred_only else None,
            limit=100000,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        def _fmt_time(ts: float) -> str:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

        lines = [
            "# MindForge 记忆导出",
            "",
            f"- 导出时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- 记忆总数：{len(entries)}",
            f"- 筛选条件：分类={category or '全部'}, 层级={layer.value if layer else '全部'}, 仅收藏={'是' if starred_only else '否'}",
            "",
            "---",
            "",
        ]

        # 按分类分组
        groups: Dict[str, List[MemoryEntry]] = {}
        for e in entries:
            groups.setdefault(e.category, []).append(e)

        for cat in sorted(groups.keys()):
            lines.append(f"## 📂 {cat}")
            lines.append("")
            for e in groups[cat]:
                star = "⭐ " if e.starred else ""
                lines.append(f"### {star}{e.preview[:60]}")
                lines.append("")
                lines.append(f"- **ID**: `{e.id}`")
                lines.append(f"- **层级**: {e.layer.value}")
                lines.append(f"- **隐私**: {e.privacy.value}")
                lines.append(f"- **重要性**: {e.importance.value}")
                lines.append(f"- **类型**: {e.memory_type.value}")
                lines.append(f"- **标签**: {', '.join(f'#{t}' for t in e.tags) if e.tags else '无'}")
                lines.append(f"- **创建**: {_fmt_time(e.created_at)}")
                lines.append(f"- **访问**: {e.access_count} 次")
                lines.append("")
                lines.append("**内容**：")
                lines.append("")
                lines.append(e.content)
                lines.append("")
                lines.append("---")
                lines.append("")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def health_check(self) -> dict:
        """数据库健康检查（v5.0.5 新增）

        检查项目：
        - 数据库完整性（PRAGMA integrity_check）
        - 索引完整性（确认所有预期索引存在）
        - FTS 索引同步状态（检测孤立 FTS 记录）
        - 孤立审计日志（指向已不存在的 memory_id）
        - 孤立 FTS 记录（FTS 中的 rowid 在 memories 中已不存在）
        - 加密一致性（是否有标记 encrypted 但缺 ciphertext 的条目）

        Returns:
            {
                "status": "healthy" | "warning" | "critical",
                "integrity_check": str,
                "indexes": {"expected": int, "found": int, "missing": [...]},
                "fts_orphans": int,            # FTS 中有但 memories 中没有的
                "audit_orphans": int,          # 审计日志指向已删除的 memory_id
                "encrypted_inconsistent": int, # 标记加密但缺密文的
                "total_memories": int,
                "db_size_bytes": int,
                "recommendations": [...],
            }
        """
        conn = self._get_conn()

        # 1. 完整性检查
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

        # 2. 索引检查
        expected_indexes = {
            "idx_category", "idx_privacy", "idx_layer", "idx_importance",
            "idx_created_at", "idx_memory_type", "idx_starred",
            "idx_audit_memory", "idx_audit_timestamp",
            "idx_kg_entity", "idx_relation_from", "idx_relation_to",
        }
        actual = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        found_indexes = {row[0] for row in actual}
        missing_indexes = expected_indexes - found_indexes

        # 3. FTS 孤立记录
        fts_orphans = conn.execute(
            "SELECT COUNT(*) FROM memory_fts WHERE rowid NOT IN (SELECT rowid FROM memories)"
        ).fetchone()[0]

        # 4. 审计日志孤立记录
        audit_orphans = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE memory_id != '' "
            "AND memory_id NOT IN (SELECT id FROM memories)"
        ).fetchone()[0]

        # 5. 加密一致性
        encrypted_inconsistent = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE encrypted = 1 "
            "AND (ciphertext IS NULL OR nonce IS NULL OR salt IS NULL)"
        ).fetchone()[0]

        # 6. 总数和大小
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        # 生成建议
        recommendations = []
        status = "healthy"

        if integrity != "ok":
            status = "critical"
            recommendations.append("数据库完整性检查失败，建议立即从备份恢复")

        if missing_indexes:
            status = "warning" if status == "healthy" else status
            recommendations.append(f"缺失索引：{', '.join(missing_indexes)}，建议重建数据库")

        if fts_orphans > 0:
            status = "warning" if status == "healthy" else status
            recommendations.append(f"发现 {fts_orphans} 条孤立 FTS 记录，建议执行 vacuum")

        if audit_orphans > 0:
            recommendations.append(f"发现 {audit_orphans} 条孤立审计日志（不影响功能，可忽略）")

        if encrypted_inconsistent > 0:
            status = "critical"
            recommendations.append(f"{encrypted_inconsistent} 条加密记忆缺密文，数据可能损坏")

        if not recommendations:
            recommendations.append("一切正常，无需操作")

        return {
            "status": status,
            "integrity_check": integrity,
            "indexes": {
                "expected": len(expected_indexes),
                "found": len(found_indexes & expected_indexes),
                "missing": sorted(missing_indexes),
            },
            "fts_orphans": fts_orphans,
            "audit_orphans": audit_orphans,
            "encrypted_inconsistent": encrypted_inconsistent,
            "total_memories": total,
            "db_size_bytes": db_size,
            "recommendations": recommendations,
        }

    def summarize(self,
                  category: Optional[str] = None,
                  group_by: str = "category") -> dict:
        """生成记忆摘要（v5.0.5 新增）

        Args:
            category: 限定分类，None 表示全部
            group_by: 分组维度，支持 'category' | 'layer' | 'importance' | 'privacy'

        Returns:
            {
                "total": int,
                "grouped": {group_key: {"count": int, "latest": str, "oldest": str, "samples": [...]}},
                "recent_activity": {"last_7d": int, "last_30d": int},
                "top_tags": [...],
            }
        """
        conn = self._get_conn()
        now = time.time()

        valid_groups = {"category", "layer", "importance", "privacy"}
        if group_by not in valid_groups:
            group_by = "category"

        where = " WHERE 1=1"
        params = []
        if category:
            where += " AND category = ?"
            params.append(category)

        total = conn.execute(f"SELECT COUNT(*) FROM memories{where}", params).fetchone()[0]

        # 分组统计
        grouped = {}
        rows = conn.execute(
            f"SELECT {group_by}, COUNT(*), MAX(created_at), MIN(created_at) "
            f"FROM memories{where} GROUP BY {group_by} ORDER BY COUNT(*) DESC",
            params
        ).fetchall()
        for row in rows:
            key = row[0] or "unknown"
            count = row[1]
            latest_ts = row[2]
            oldest_ts = row[3]
            # 取该组前 3 条预览
            samples = conn.execute(
                f"SELECT content FROM memories{where} AND {group_by} = ? "
                f"ORDER BY created_at DESC LIMIT 3",
                params + [row[0]]
            ).fetchall()
            grouped[key] = {
                "count": count,
                "latest": datetime.fromtimestamp(latest_ts, tz=timezone.utc).strftime("%Y-%m-%d") if latest_ts else "",
                "oldest": datetime.fromtimestamp(oldest_ts, tz=timezone.utc).strftime("%Y-%m-%d") if oldest_ts else "",
                "samples": [r[0][:80] for r in samples],
            }

        # 近期活动
        last_7d = conn.execute(
            f"SELECT COUNT(*) FROM memories{where} AND created_at >= ?",
            params + [now - 7 * 86400]
        ).fetchone()[0]
        last_30d = conn.execute(
            f"SELECT COUNT(*) FROM memories{where} AND created_at >= ?",
            params + [now - 30 * 86400]
        ).fetchone()[0]

        # 热门标签
        tag_counts: Dict[str, int] = {}
        for row in conn.execute(f"SELECT tags FROM memories{where}", params):
            if row[0]:
                try:
                    for t in json.loads(row[0]):
                        tag_counts[t] = tag_counts.get(t, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total": total,
            "grouped": grouped,
            "recent_activity": {
                "last_7d": last_7d,
                "last_30d": last_30d,
            },
            "top_tags": top_tags,
        }

    def get_audit_log(self,
                      memory_id: Optional[str] = None,
                      actor: Optional[str] = None,
                      limit: int = 100) -> List[AuditRecord]:
        """获取审计日志"""
        conn = self._get_conn()
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if memory_id:
            query += " AND memory_id = ?"
            params.append(memory_id)
        if actor:
            query += " AND actor = ?"
            params.append(actor)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [AuditRecord(
            id=row["id"],
            action=row["action"],
            memory_id=row["memory_id"],
            actor=row["actor"],
            session_id=row["session_id"],
            privacy_level=row["privacy_level"],
            timestamp=row["timestamp"],
            details=json.loads(row["details"]),
        ) for row in rows]

    def backup(self, backup_dir: str) -> Path:
        """备份数据库"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = backup_path / f"memory_backup_{timestamp}.db"

        import shutil
        shutil.copy2(self.db_path, dest)
        return dest

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            content=row["content"] or "",
            category=row["category"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            privacy=PrivacyLevel(row["privacy"]),
            importance=Importance(row["importance"]),
            memory_type=MemoryType(row["memory_type"]),
            layer=MemoryLayer(row["layer"]),
            source_session=row["source_session"],
            source_agent=row["source_agent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            access_count=row["access_count"],
            consolidation_count=row["consolidation_count"],
            forgetting_score=row["forgetting_score"],
            strength=row["strength"],
            starred=bool(row["starred"]) if "starred" in row.keys() else False,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            encrypted=bool(row["encrypted"]),
            ciphertext=row["ciphertext"],
            nonce=row["nonce"],
            salt=row["salt"],
        )

    def _update_access(self, entry: MemoryEntry, actor: str, session_id: str):
        """更新访问计数（v5.1.2 优化：不再每次 get 都写审计日志，减轻低配电脑负担）"""
        conn = self._get_conn()
        now = time.time()
        conn.execute("""
            UPDATE memories SET access_count = access_count + 1, last_accessed_at = ?
            WHERE id = ?
        """, (now, entry.id))
        conn.commit()

    def _add_audit(self, action: str, memory_id: str, actor: str,
                   session_id: str, privacy_level: str, details: Optional[dict] = None):
        """添加审计记录"""
        conn = self._get_conn()
        record_id = str(uuid.uuid4())
        now = time.time()
        conn.execute("""
            INSERT INTO audit_log (id, action, memory_id, actor, session_id, privacy_level, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_id, action, memory_id, actor, session_id,
            privacy_level, now, json.dumps(details or {}, ensure_ascii=False)
        ))
        conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def cleanup_expired(self, max_age_hours: int = 24, layer: str = "sensory") -> int:
        """清理过期记忆（v5.1.3 新增）

        Args:
            max_age_hours: 最大保留时长（小时），超过此时间的记忆将被软删除
            layer: 记忆层级（sensory/short_term/long_term/permanent）

        Returns:
            被清理的记忆数量
        """
        conn = self._get_conn()
        now = time.time()
        cutoff_time = now - (max_age_hours * 3600)

        rows = conn.execute("""
            SELECT id, category FROM memories
            WHERE layer = ? AND deleted = 0 AND created_at < ?
        """, (layer, cutoff_time)).fetchall()

        if not rows:
            return 0

        deleted_count = 0
        for row in rows:
            entry_id = row["id"]
            old_category = row["category"]

            try:
                conn.execute("""
                    UPDATE memories SET
                        deleted = 1,
                        category = 'trash',
                        metadata = JSON_SET(metadata, '$.original_category', ?),
                        updated_at = ?
                    WHERE id = ?
                """, (old_category, now, entry_id))

                if not self.encrypted:
                    conn.execute("""
                        INSERT INTO memory_fts(memory_fts, rowid, content, category, tags)
                        VALUES('delete', (SELECT rowid FROM memories WHERE id = ?), '', '', '')
                    """, (entry_id,))

                deleted_count += 1
            except Exception:
                pass

        conn.commit()
        return deleted_count

    def batch_add(self, entries: List[Dict[str, Any]]) -> int:
        """批量添加记忆（v5.1.3 新增）

        Args:
            entries: 记忆条目列表，每个条目包含 content、category、tags 等字段

        Returns:
            成功添加的记忆数量
        """
        conn = self._get_conn()
        now = time.time()
        added_count = 0

        for entry_data in entries:
            try:
                entry_id = str(uuid.uuid4())
                content = entry_data.get("content", "")
                category = entry_data.get("category", "general")
                tags = entry_data.get("tags", [])
                privacy_str = entry_data.get("privacy", "internal")
                importance_str = entry_data.get("importance", "medium")
                layer_str = entry_data.get("layer", "short_term")

                ciphertext = None
                nonce = None
                salt = None
                stored_content = content

                if self.encrypted and self.encryption:
                    blob = self.encryption.encrypt(content)
                    ciphertext = blob.ciphertext
                    nonce = blob.nonce
                    salt = blob.salt
                    stored_content = ""

                conn.execute("""
                    INSERT INTO memories (
                        id, content, ciphertext, nonce, salt, category, tags,
                        privacy, importance, memory_type, layer,
                        source_session, source_agent, created_at, updated_at,
                        last_accessed_at, access_count, consolidation_count,
                        forgetting_score, strength, starred, metadata, encrypted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_id, stored_content, ciphertext, nonce, salt,
                    category, json.dumps(tags, ensure_ascii=False),
                    privacy_str, importance_str, "text",
                    layer_str, "", "",
                    now, now, now,
                    0, 0, 0.0, 1.0, 0,
                    json.dumps({}, ensure_ascii=False), int(self.encrypted)
                ))

                if not self.encrypted:
                    conn.execute("""
                        INSERT INTO memory_fts (rowid, content, category, tags)
                        VALUES ((SELECT rowid FROM memories WHERE id = ?), ?, ?, ?)
                    """, (entry_id, content, category, json.dumps(tags, ensure_ascii=False)))

                added_count += 1
            except Exception:
                pass

        conn.commit()
        return added_count

    def find_similar(self, content: str, limit: int = 5, threshold: float = 0.3) -> List[MemoryEntry]:
        """查找相似记忆（v5.1.3 新增）

        使用简单的 Jaccard 相似度匹配，在低配电脑上也能快速运行

        Args:
            content: 参考内容
            limit: 返回数量限制
            threshold: 相似度阈值（0-1）

        Returns:
            相似记忆列表（按相似度降序）
        """
        import re

        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM memories WHERE deleted = 0 AND encrypted = 0
        """).fetchall()

        def jaccard_similarity(s1: str, s2: str) -> float:
            words1 = set(re.findall(r'\w+', s1.lower()))
            words2 = set(re.findall(r'\w+', s2.lower()))
            if not words1 and not words2:
                return 0.0
            intersection = words1 & words2
            union = words1 | words2
            return len(intersection) / len(union)

        similarities = []
        for row in rows:
            entry_content = row["content"] or ""
            if entry_content:
                sim = jaccard_similarity(content, entry_content)
                if sim >= threshold:
                    similarities.append((sim, row))

        similarities.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, row in similarities[:limit]:
            entry = self._row_to_entry(row)
            if self.encrypted and self.encryption:
                entry.content = self.encryption.decrypt(
                    EncryptedBlob(ciphertext=entry.ciphertext, nonce=entry.nonce, salt=entry.salt)
                )
            results.append(entry)

        return results

    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息（v5.1.4 新增）"""
        conn = self._get_conn()

        stats = {}

        row = conn.execute("SELECT COUNT(*) FROM memories WHERE category != 'trash'").fetchone()
        stats["total"] = row[0] if row else 0

        row = conn.execute("SELECT COUNT(*) FROM memories WHERE category = 'trash'").fetchone()
        stats["trash"] = row[0] if row else 0

        row = conn.execute("SELECT COUNT(*) FROM memories WHERE starred = 1 AND category != 'trash'").fetchone()
        stats["starred"] = row[0] if row else 0

        row = conn.execute("SELECT COUNT(*) FROM memories WHERE encrypted = 1 AND category != 'trash'").fetchone()
        stats["encrypted"] = row[0] if row else 0

        row = conn.execute("SELECT MIN(created_at), MAX(created_at) FROM memories WHERE category != 'trash'").fetchone()
        if row and row[0]:
            stats["first_created"] = row[0]
            stats["last_created"] = row[1]
        else:
            stats["first_created"] = None
            stats["last_created"] = None

        row = conn.execute("SELECT AVG(access_count), AVG(strength), AVG(forgetting_score) FROM memories WHERE category != 'trash'").fetchone()
        if row:
            stats["avg_access_count"] = round(row[0], 2) if row[0] else 0
            stats["avg_strength"] = round(row[1], 2) if row[1] else 0
            stats["avg_forgetting_score"] = round(row[2], 2) if row[2] else 0

        row = conn.execute("SELECT MAX(access_count), MIN(strength) FROM memories WHERE category != 'trash'").fetchone()
        if row:
            stats["max_access_count"] = row[0] if row[0] else 0
            stats["min_strength"] = round(row[1], 2) if row[1] else 0

        stats["by_category"] = {}
        rows = conn.execute("""
            SELECT category, COUNT(*) FROM memories WHERE category != 'trash' GROUP BY category ORDER BY COUNT(*) DESC
        """).fetchall()
        for cat, cnt in rows:
            stats["by_category"][cat] = cnt

        stats["by_layer"] = {}
        rows = conn.execute("""
            SELECT layer, COUNT(*) FROM memories WHERE category != 'trash' GROUP BY layer ORDER BY COUNT(*) DESC
        """).fetchall()
        for lay, cnt in rows:
            stats["by_layer"][lay] = cnt

        stats["by_privacy"] = {}
        rows = conn.execute("""
            SELECT privacy, COUNT(*) FROM memories WHERE category != 'trash' GROUP BY privacy ORDER BY COUNT(*) DESC
        """).fetchall()
        for pri, cnt in rows:
            stats["by_privacy"][pri] = cnt

        stats["by_importance"] = {}
        rows = conn.execute("""
            SELECT importance, COUNT(*) FROM memories WHERE category != 'trash' GROUP BY importance ORDER BY COUNT(*) DESC
        """).fetchall()
        for imp, cnt in rows:
            stats["by_importance"][imp] = cnt

        row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        stats["audit_records"] = row[0] if row else 0

        return stats

    def get_random_memories(self, count: int = 1,
                            category: Optional[str] = None,
                            layer: Optional[MemoryLayer] = None,
                            min_strength: Optional[float] = None) -> List[MemoryEntry]:
        """随机获取记忆（v5.1.7 新增）

        Args:
            count: 随机记忆数量
            category: 分类筛选
            layer: 记忆层级筛选
            min_strength: 最低记忆强度筛选

        Returns:
            随机记忆列表
        """
        conn = self._get_conn()
        query = "SELECT * FROM memories WHERE category != 'trash'"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if layer:
            query += " AND layer = ?"
            params.append(layer.value)
        if min_strength is not None:
            query += " AND strength >= ?"
            params.append(min_strength)

        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(count)

        rows = conn.execute(query, params).fetchall()
        results = [self._row_to_entry(row) for row in rows]

        if self.encrypted and self.encryption:
            for entry in results:
                try:
                    entry.content = self.encryption.decrypt(
                        EncryptedBlob(ciphertext=entry.ciphertext, nonce=entry.nonce, salt=entry.salt)
                    )
                except Exception:
                    pass

        return results

    def rename_tag(self, old_tag: str, new_tag: str) -> int:
        """重命名标签（v5.1.7 新增）

        Args:
            old_tag: 旧标签名
            new_tag: 新标签名

        Returns:
            受影响的记忆条数
        """
        conn = self._get_conn()
        count = 0

        rows = conn.execute("SELECT id, tags FROM memories WHERE category != 'trash'").fetchall()
        for row in rows:
            tags = json.loads(row["tags"]) if row["tags"] else []
            if old_tag in tags:
                new_tags = [new_tag if t == old_tag else t for t in tags]
                conn.execute("UPDATE memories SET tags = ?, updated_at = ? WHERE id = ?",
                             (json.dumps(new_tags, ensure_ascii=False), time.time(), row["id"]))
                count += 1

        conn.commit()
        return count

    def rename_category(self, old_cat: str, new_cat: str) -> int:
        """重命名分类（v5.1.7 新增）

        Args:
            old_cat: 旧分类名
            new_cat: 新分类名

        Returns:
            受影响的记忆条数
        """
        conn = self._get_conn()
        now = time.time()

        cursor = conn.execute("""
            UPDATE memories SET category = ?, updated_at = ?
            WHERE category = ? AND category != 'trash'
        """, (new_cat, now, old_cat))

        count = cursor.rowcount
        conn.commit()
        return count

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要（v5.1.7 新增）"""
        return {
            "db_path": str(self.db_path),
            "encrypted": self.encrypted,
            "db_size_mb": round(Path(self.db_path).stat().st_size / (1024 * 1024), 2) if Path(self.db_path).exists() else 0,
        }
