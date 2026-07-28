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

from .types import (
    PrivacyLevel, Importance, MemoryType, MemoryLayer,
    DramaGenre, DramaStatus, DramaSeries, DramaScene,
    DramaCharacter, DramaLine,
)
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

            -- AI 短剧记忆模块（v5.2.1 新增）
            CREATE TABLE IF NOT EXISTS drama_series (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                genre TEXT DEFAULT 'other',
                total_episodes INTEGER DEFAULT 0,
                current_episode INTEGER DEFAULT 0,
                status TEXT DEFAULT 'planned',
                platform TEXT DEFAULT '',
                rating REAL DEFAULT 0.0,
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                cover_url TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                created_at REAL,
                updated_at REAL,
                last_watched_at REAL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_drama_genre ON drama_series(genre);
            CREATE INDEX IF NOT EXISTS idx_drama_status ON drama_series(status);
            CREATE INDEX IF NOT EXISTS idx_drama_rating ON drama_series(rating);

            CREATE TABLE IF NOT EXISTS drama_scenes (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                episode INTEGER DEFAULT 0,
                scene_number INTEGER DEFAULT 0,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                location TEXT DEFAULT '',
                time_of_day TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_scene_drama ON drama_scenes(drama_id);
            CREATE INDEX IF NOT EXISTS idx_scene_episode ON drama_scenes(episode);

            CREATE TABLE IF NOT EXISTS drama_characters (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'supporting',
                actor TEXT DEFAULT '',
                description TEXT DEFAULT '',
                personality TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_char_drama ON drama_characters(drama_id);
            CREATE INDEX IF NOT EXISTS idx_char_name ON drama_characters(name);

            CREATE TABLE IF NOT EXISTS drama_lines (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                scene_id TEXT DEFAULT '',
                character_id TEXT DEFAULT '',
                character_name TEXT DEFAULT '',
                line_text TEXT NOT NULL,
                context TEXT DEFAULT '',
                episode INTEGER DEFAULT 0,
                timestamp TEXT DEFAULT '',
                is_classic INTEGER DEFAULT 0,
                memory_id TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_line_drama ON drama_lines(drama_id);
            CREATE INDEX IF NOT EXISTS idx_line_character ON drama_lines(character_id);
            CREATE INDEX IF NOT EXISTS idx_line_classic ON drama_lines(is_classic);

            -- 记忆笔记/批注（v5.2.4 新增）
            CREATE TABLE IF NOT EXISTS memory_notes (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_note_memory ON memory_notes(memory_id);
            CREATE INDEX IF NOT EXISTS idx_note_author ON memory_notes(author);

            -- 记忆模板（v5.2.4 新增）
            CREATE TABLE IF NOT EXISTS memory_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                content_template TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '[]',
                importance TEXT DEFAULT 'MEDIUM',
                layer TEXT DEFAULT 'short_term',
                description TEXT DEFAULT '',
                use_count INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_template_name ON memory_templates(name);
            CREATE INDEX IF NOT EXISTS idx_template_category ON memory_templates(category);

            -- 复习计划（v5.2.4 新增）
            CREATE TABLE IF NOT EXISTS review_schedules (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                scheduled_at REAL NOT NULL,
                interval_days REAL DEFAULT 1.0,
                review_count INTEGER DEFAULT 0,
                last_reviewed_at REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_schedule_memory ON review_schedules(memory_id);
            CREATE INDEX IF NOT EXISTS idx_schedule_status ON review_schedules(status);
            CREATE INDEX IF NOT EXISTS idx_schedule_due ON review_schedules(scheduled_at);
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
                except sqlite3.OperationalError:
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
                except sqlite3.OperationalError:
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
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "INSERT INTO memory_fts (rowid, content, category, tags) VALUES (?, ?, ?, ?)",
                (row[0], row[1] or "", row[2] or "", row[3] or "[]")
            )
        except sqlite3.OperationalError:
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
            except sqlite3.OperationalError:
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
            except sqlite3.OperationalError:
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
                except sqlite3.OperationalError:
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
                except (json.JSONDecodeError, TypeError):
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
                except sqlite3.OperationalError:
                    pass
        else:
            # v5.1.1 修复：批量软删除时也保存原分类到 metadata
            for row in rows:
                try:
                    meta = json.loads(row["metadata"]) if row.get("metadata") else {}
                except (json.JSONDecodeError, TypeError):
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
        except (json.JSONDecodeError, TypeError):
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

    def agent_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Agent 记忆统计（v5.2.2 新增）

        统计按 Agent 来源分组的记忆数据，支持查询特定 Agent。

        Args:
            agent_id: 指定 Agent ID（None 表示统计全部 Agent）

        Returns:
            {
                "total_agents": 总 Agent 数,
                "by_agent": {agent_id: {count, last_active, top_categories}},
                "agent_detail": 指定 Agent 的详情（如果提供了 agent_id）
            }
        """
        conn = self._get_conn()

        if agent_id:
            # 查询特定 Agent
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE source_agent = ?",
                (agent_id,)
            ).fetchone()[0]

            categories = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM memories WHERE source_agent = ? GROUP BY category ORDER BY cnt DESC LIMIT 10",
                (agent_id,)
            ).fetchall()

            last_active = conn.execute(
                "SELECT MAX(created_at) FROM memories WHERE source_agent = ?",
                (agent_id,)
            ).fetchone()[0] or 0

            layers = conn.execute(
                "SELECT layer, COUNT(*) as cnt FROM memories WHERE source_agent = ? GROUP BY layer",
                (agent_id,)
            ).fetchall()

            return {
                "agent_id": agent_id,
                "total_memories": total,
                "last_active": last_active,
                "by_category": {r[0]: r[1] for r in categories},
                "by_layer": {r[0]: r[1] for r in layers},
            }

        # 统计所有 Agent
        agents = conn.execute(
            "SELECT source_agent, COUNT(*) as cnt, MAX(created_at) as last_active "
            "FROM memories WHERE source_agent != '' GROUP BY source_agent ORDER BY cnt DESC"
        ).fetchall()

        by_agent = {}
        for row in agents:
            agent = row[0]
            count = row[1]
            last_active = row[2]

            # 获取每个 Agent 的 top 分类
            top_cats = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM memories WHERE source_agent = ? "
                "GROUP BY category ORDER BY cnt DESC LIMIT 5",
                (agent,)
            ).fetchall()

            by_agent[agent] = {
                "count": count,
                "last_active": last_active,
                "top_categories": [r[0] for r in top_cats[:5]],
            }

        return {
            "total_agents": len(by_agent),
            "by_agent": by_agent,
        }

    def list_by_agent(self,
                      agent_id: str,
                      limit: int = 100,
                      offset: int = 0) -> List[MemoryEntry]:
        """列出特定 Agent 的记忆（v5.2.2 新增）"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE source_agent = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (agent_id, limit, offset)
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def evolve_memories(self,
                        dry_run: bool = False,
                        actor: str = "system",
                        session_id: str = "evolve") -> Dict[str, Any]:
        """记忆演化 - 基于艾宾浩斯遗忘曲线自动升级记忆层级（v5.2.2 新增）

        规则：
        - 短期记忆创建超过 24 小时且被访问过 → 升级为长期记忆
        - 长期记忆创建超过 7 天且收藏/重要 → 升级为永久记忆
        - 超过 30 天未访问的短期记忆 → 标记为待清理

        Args:
            dry_run: 仅统计不执行
            actor: 操作者
            session_id: 会话 ID

        Returns:
            演化统计结果
        """
        conn = self._get_conn()
        now = time.time()
        day_seconds = 86400

        short_to_long_days = 1
        long_to_perm_days = 7
        stale_days = 30

        # 统计可升级的短期记忆
        short_upgrade = conn.execute(
            "SELECT COUNT(*) FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND created_at < ? AND access_count > 0",
            (MemoryLayer.SHORT_TERM.value, now - short_upgrade_days * day_seconds)
        ).fetchone()[0] if False else 0

        short_to_long_candidates = conn.execute(
            "SELECT id FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND created_at < ? AND access_count > 0 "
            "LIMIT 100",
            (MemoryLayer.SHORT_TERM.value, now - short_upgrade_days * day_seconds)
        ).fetchall() if False else []

        # 重新计算
        short_to_long = conn.execute(
            "SELECT COUNT(*) FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND (julianday('now') - julianday(created_at, 'unixepoch')) >= 1 "
            "AND access_count > 0",
            (MemoryLayer.SHORT_TERM.value,)
        ).fetchone()[0]

        long_to_perm = conn.execute(
            "SELECT COUNT(*) FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND (julianday('now') - julianday(created_at, 'unixepoch')) >= 7 "
            "AND (starred = 1 OR importance >= 4)",
            (MemoryLayer.LONG_TERM.value,)
        ).fetchone()[0]

        stale_short = conn.execute(
            "SELECT COUNT(*) FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND (julianday('now') - julianday(created_at, 'unixepoch')) >= 30 "
            "AND access_count = 0",
            (MemoryLayer.SHORT_TERM.value,)
        ).fetchone()[0]

        result = {
            "short_to_long": short_to_long,
            "long_to_permanent": long_to_perm,
            "stale_short_term": stale_short,
            "total_evolvable": short_to_long + long_to_perm,
            "executed": not dry_run,
        }

        if dry_run:
            return result

        # 执行升级
        upgraded_short = 0
        rows = conn.execute(
            "SELECT id FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND (julianday('now') - julianday(created_at, 'unixepoch')) >= 1 "
            "AND access_count > 0 LIMIT 200",
            (MemoryLayer.SHORT_TERM.value,)
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE memories SET layer = ?, updated_at = ? WHERE id = ?",
                (MemoryLayer.LONG_TERM.value, now, row[0])
            )
            self._add_audit("evolve", row[0], actor, session_id, "short_term→long_term")
            upgraded_short += 1

        upgraded_long = 0
        rows = conn.execute(
            "SELECT id FROM memories "
            "WHERE layer = ? AND category != 'trash' "
            "AND (julianday('now') - julianday(created_at, 'unixepoch')) >= 7 "
            "AND (starred = 1 OR importance >= 4) LIMIT 100",
            (MemoryLayer.LONG_TERM.value,)
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE memories SET layer = ?, updated_at = ? WHERE id = ?",
                (MemoryLayer.PERMANENT.value, now, row[0])
            )
            self._add_audit("evolve", row[0], actor, session_id, "long_term→permanent")
            upgraded_long += 1

        conn.commit()
        result["upgraded_to_long"] = upgraded_short
        result["upgraded_to_permanent"] = upgraded_long
        return result

    def transfer_agent_memories(self,
                                from_agent: str,
                                to_agent: str,
                                category: Optional[str] = None,
                                actor: str = "system",
                                session_id: str = "transfer") -> Dict[str, Any]:
        """Agent 记忆迁移 - 将一个 Agent 的记忆转移给另一个（v5.2.2 新增）

        Args:
            from_agent: 源 Agent ID
            to_agent: 目标 Agent ID
            category: 可选，仅迁移指定分类
            actor: 操作者
            session_id: 会话 ID

        Returns:
            迁移统计
        """
        conn = self._get_conn()
        now = time.time()

        query = "SELECT id FROM memories WHERE source_agent = ?"
        params = [from_agent]

        if category:
            query += " AND category = ?"
            params.append(category)

        rows = conn.execute(query, params).fetchall()
        total = len(rows)

        for row in rows:
            conn.execute(
                "UPDATE memories SET source_agent = ?, updated_at = ? WHERE id = ?",
                (to_agent, now, row[0])
            )
            self._add_audit(
                "agent_transfer", row[0], actor, session_id,
                f"{from_agent}→{to_agent}"
            )

        conn.commit()
        return {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "transferred": total,
            "category_filter": category,
        }

    def clean_agent_memories(self,
                             agent_id: str,
                             older_than_days: int = 90,
                             max_importance: Optional[str] = None,
                             dry_run: bool = False,
                             actor: str = "system",
                             session_id: str = "clean") -> Dict[str, Any]:
        """清理 Agent 的旧记忆（v5.2.2 新增）

        清理指定 Agent 创建的、超过指定天数、重要度低于等于指定级别的记忆，移入回收站。

        Args:
            agent_id: Agent ID
            older_than_days: 清理超过多少天的记忆
            max_importance: 最高清理的重要级别（LOW/MEDIUM/HIGH/CRITICAL），None 表示清理所有
            dry_run: 仅统计不执行
            actor: 操作者
            session_id: 会话 ID

        Returns:
            清理统计
        """
        conn = self._get_conn()
        now = time.time()

        importance_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        clean_importances = []

        if max_importance:
            try:
                max_imp = Importance.from_string(max_importance)
                max_idx = importance_order.index(max_imp.value)
                clean_importances = importance_order[:max_idx + 1]
            except (ValueError, KeyError):
                clean_importances = importance_order
        else:
            clean_importances = importance_order

        query = (
            "SELECT id, content FROM memories "
            "WHERE source_agent = ? AND category != 'trash' "
            "AND (julianday('now') - julianday(created_at, 'unixepoch')) >= ? "
            "AND importance IN ({}) AND starred = 0"
        ).format(",".join(["?"] * len(clean_importances)))
        params = [agent_id, older_than_days] + clean_importances

        rows = conn.execute(query, params).fetchall()
        total = len(rows)

        result = {
            "agent_id": agent_id,
            "older_than_days": older_than_days,
            "max_importance": max_importance,
            "clean_importances": clean_importances,
            "to_clean": total,
            "cleaned": 0,
            "executed": not dry_run,
        }

        if dry_run:
            return result

        for row in rows:
            conn.execute(
                "UPDATE memories SET category = 'trash', updated_at = ? WHERE id = ?",
                (now, row[0])
            )
            self._add_audit("agent_clean", row[0], actor, session_id, "")

        conn.commit()
        result["cleaned"] = total
        return result

    def quality_score(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """记忆质量评分（v5.2.2 新增）

        基于多维度评估记忆质量：
        - 内容长度：合理长度加分
        - 访问频率：高访问加分
        - 收藏状态：收藏加分
        - 重要性：高重要性加分
        - 标签丰富度：有标签加分
        - 时间衰减：新记忆加分

        Args:
            memory_id: 记忆 ID

        Returns:
            质量评分详情，包含总分和各项得分
        """
        entry = self.get_memory(memory_id)
        if not entry:
            return None

        import time
        now = time.time()

        scores = {}
        total = 0.0

        # 1. 内容长度评分（0-20分）
        content_len = len(entry.content)
        if 50 <= content_len <= 500:
            scores["content_length"] = 20
        elif content_len < 50:
            scores["content_length"] = max(5, content_len // 10)
        elif content_len <= 1000:
            scores["content_length"] = 15
        else:
            scores["content_length"] = 10
        total += scores["content_length"]

        # 2. 访问频率评分（0-25分）
        access_count = entry.access_count
        if access_count >= 10:
            scores["access_frequency"] = 25
        elif access_count >= 5:
            scores["access_frequency"] = 20
        elif access_count >= 2:
            scores["access_frequency"] = 15
        elif access_count >= 1:
            scores["access_frequency"] = 10
        else:
            scores["access_frequency"] = 5
        total += scores["access_frequency"]

        # 3. 收藏状态（0-15分）
        scores["starred"] = 15 if entry.starred else 0
        total += scores["starred"]

        # 4. 重要性评分（0-20分）
        importance_scores = {
            "CRITICAL": 20,
            "HIGH": 15,
            "MEDIUM": 10,
            "LOW": 5,
        }
        scores["importance"] = importance_scores.get(entry.importance.value, 10)
        total += scores["importance"]

        # 5. 标签丰富度（0-10分）
        tag_count = len(entry.tags)
        if tag_count >= 5:
            scores["tag_richness"] = 10
        elif tag_count >= 3:
            scores["tag_richness"] = 7
        elif tag_count >= 1:
            scores["tag_richness"] = 5
        else:
            scores["tag_richness"] = 0
        total += scores["tag_richness"]

        # 6. 时间衰减（0-10分）
        age_days = (now - entry.created_at) / 86400
        if age_days <= 1:
            scores["freshness"] = 10
        elif age_days <= 7:
            scores["freshness"] = 8
        elif age_days <= 30:
            scores["freshness"] = 6
        elif age_days <= 90:
            scores["freshness"] = 4
        else:
            scores["freshness"] = 2
        total += scores["freshness"]

        # 7. 记忆层级加分（0-5分）
        layer_scores = {
            "permanent": 5,
            "long_term": 3,
            "short_term": 1,
            "sensory": 0,
        }
        scores["layer_bonus"] = layer_scores.get(entry.layer.value, 0)
        total += scores["layer_bonus"]

        return {
            "memory_id": memory_id,
            "total_score": round(total, 1),
            "max_score": 100,
            "percentage": round(total, 1),
            "grade": self._score_to_grade(total),
            "breakdown": scores,
        }

    def _score_to_grade(self, score: float) -> str:
        """分数转等级"""
        if score >= 85:
            return "优秀"
        elif score >= 70:
            return "良好"
        elif score >= 55:
            return "中等"
        elif score >= 40:
            return "及格"
        else:
            return "需改进"

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
            相似记忆列表，包含相似度分数
        """
        entry = self.get_memory(memory_id)
        if not entry:
            return []

        conn = self._get_conn()

        # 使用 FTS5 全文搜索找相似内容
        try:
            rows = conn.execute(
                "SELECT id, content, category, layer, importance, starred, "
                "bm25(memories_fts) as relevance "
                "FROM memories_fts "
                "WHERE memories_fts MATCH ? AND id != ? "
                "ORDER BY relevance "
                "LIMIT ?",
                (entry.content[:200], memory_id, limit * 2)
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS 搜索失败，回退到 LIKE 搜索
            keywords = entry.content.split()[:5]
            if not keywords:
                return []

            query = "SELECT id, content, category, layer, importance, starred FROM memories WHERE id != ? AND ("
            params = [memory_id]
            conditions = []
            for kw in keywords[:3]:
                conditions.append("content LIKE ?")
                params.append(f"%{kw}%")
            query += " OR ".join(conditions) + ") LIMIT ?"
            params.append(limit * 2)

            rows = conn.execute(query, params).fetchall()

        results = []
        for row in rows:
            other_id = row[0]
            other_content = row[1]

            # 计算相似度（基于内容重叠）
            similarity = self._calculate_similarity(entry.content, other_content)

            if similarity >= min_similarity:
                results.append({
                    "memory_id": other_id,
                    "similarity": round(similarity, 3),
                    "content_preview": other_content[:100] + "..." if len(other_content) > 100 else other_content,
                    "category": row[2],
                    "layer": row[3],
                    "importance": row[4],
                    "starred": bool(row[5]),
                })

        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简化版 Jaccard 相似度）"""
        if not text1 or not text2:
            return 0.0

        # 简单的词集合相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        if union == 0:
            return 0.0

        return intersection / union

    def batch_quality_score(self,
                            category: Optional[str] = None,
                            limit: int = 100) -> Dict[str, Any]:
        """批量质量评分（v5.2.2 新增）

        对指定范围内的记忆进行批量质量评分。

        Args:
            category: 分类过滤
            limit: 数量限制

        Returns:
            批量评分结果，包含统计信息
        """
        entries = self.list_memories(category=category, limit=limit)
        scores = []
        grades = {"优秀": 0, "良好": 0, "中等": 0, "及格": 0, "需改进": 0}

        for entry in entries:
            score_data = self.quality_score(entry.id)
            if score_data:
                scores.append(score_data)
                grades[score_data["grade"]] = grades.get(score_data["grade"], 0) + 1

        if not scores:
            return {"total": 0, "average_score": 0, "grades": grades, "scores": []}

        avg_score = sum(s["total_score"] for s in scores) / len(scores)

        return {
            "total": len(scores),
            "average_score": round(avg_score, 1),
            "grades": grades,
            "top_scores": sorted(scores, key=lambda x: x["total_score"], reverse=True)[:10],
            "low_scores": sorted(scores, key=lambda x: x["total_score"])[:10],
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
            details=self._safe_json_loads(row["details"], {}),
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

    @staticmethod
    def _safe_json_loads(data: Optional[str], default: Any = None) -> Any:
        """安全解析 JSON，损坏时返回默认值（v5.2.3 安全加固）"""
        if not data:
            return default
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return default

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            content=row["content"] or "",
            category=row["category"],
            tags=self._safe_json_loads(row["tags"], []),
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
            metadata=self._safe_json_loads(row["metadata"], {}),
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
            WHERE layer = ? AND category != 'trash' AND created_at < ?
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
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
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
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
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
            SELECT * FROM memories WHERE category != 'trash' AND encrypted = 0
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
                except (ValueError, TypeError):
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
            tags = self._safe_json_loads(row["tags"], [])
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

    # ===== 数据库迁移（v5.1.8 新增）=====

    _LATEST_DB_VERSION = 1

    def get_db_version(self) -> int:
        """获取当前数据库版本（v5.1.8 新增）"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT value FROM schema_version WHERE id = 1"
            ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0

    def get_latest_db_version(self) -> int:
        """获取最新数据库版本（v5.1.8 新增）"""
        return self._LATEST_DB_VERSION

    def migrate_to_latest(self) -> Dict[str, Any]:
        """迁移数据库到最新版本（v5.1.8 新增）"""
        import time as _time
        start = _time.time()
        conn = self._get_conn()
        current = self.get_db_version()
        scripts_applied = 0

        # 确保 schema_version 表存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY,
                value INTEGER NOT NULL
            )
        """)

        # 迁移脚本（当前只有占位，未来版本可在此扩展）
        # if current < 2:
        #     ... 迁移逻辑 ...
        #     scripts_applied += 1

        # 更新版本号
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (id, value) VALUES (1, ?)",
            (self._LATEST_DB_VERSION,)
        )
        conn.commit()

        return {
            "scripts_applied": scripts_applied,
            "duration_ms": round((_time.time() - start) * 1000, 2),
            "final_version": self._LATEST_DB_VERSION,
        }

    def export_as_excel(self,
                        output_path: str,
                        category: Optional[str] = None,
                        layer: Optional[MemoryLayer] = None,
                        starred_only: bool = False) -> Path:
        """导出记忆为 Excel 格式（v5.1.9 新增）

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

        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "记忆数据"

            header_fill = PatternFill(start_color="4A90D9", end_color="4A90D9", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            headers = [
                "ID", "内容", "分类", "标签", "隐私等级", "重要性",
                "类型", "层级", "访问次数", "创建时间", "更新时间", "收藏"
            ]
            ws.append(headers)

            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
                cell.border = thin_border

            def _fmt_time(ts: float) -> str:
                return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

            for row_num, entry in enumerate(entries, 2):
                ws.append([
                    entry.id[:20],
                    entry.content[:500],
                    entry.category,
                    ", ".join(entry.tags) if entry.tags else "",
                    entry.privacy.value,
                    entry.importance.value,
                    entry.memory_type.value,
                    entry.layer.value,
                    entry.access_count,
                    _fmt_time(entry.created_at),
                    _fmt_time(entry.updated_at),
                    "⭐" if entry.starred else "",
                ])

                for col_num in range(1, len(headers) + 1):
                    cell = ws.cell(row=row_num, column=col_num)
                    cell.border = thin_border
                    cell.alignment = center_align

            ws.column_dimensions['A'].width = 22
            ws.column_dimensions['B'].width = 50
            ws.column_dimensions['C'].width = 15
            ws.column_dimensions['D'].width = 25
            ws.column_dimensions['E'].width = 12
            ws.column_dimensions['F'].width = 10
            ws.column_dimensions['G'].width = 12
            ws.column_dimensions['H'].width = 14
            ws.column_dimensions['I'].width = 10
            ws.column_dimensions['J'].width = 18
            ws.column_dimensions['K'].width = 18
            ws.column_dimensions['L'].width = 6

            wb.save(str(out))
        except ImportError:
            import csv
            with open(str(out).replace('.xlsx', '.csv'), 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "内容", "分类", "标签", "隐私等级", "重要性", "类型", "层级", "访问次数", "创建时间", "更新时间", "收藏"])
                for entry in entries:
                    writer.writerow([
                        entry.id,
                        entry.content,
                        entry.category,
                        ", ".join(entry.tags) if entry.tags else "",
                        entry.privacy.value,
                        entry.importance.value,
                        entry.memory_type.value,
                        entry.layer.value,
                        entry.access_count,
                        entry.created_at,
                        entry.updated_at,
                        entry.starred,
                    ])
                out = Path(str(out).replace('.xlsx', '.csv'))

        return out

    def import_from_excel(self,
                          input_path: str,
                          target_category: Optional[str] = None,
                          target_layer: Optional[MemoryLayer] = None) -> Dict[str, int]:
        """从 Excel 文件导入记忆（v5.1.9 新增）

        Args:
            input_path: Excel 文件路径
            target_category: 目标分类（覆盖文件中的分类）
            target_layer: 目标记忆层级

        Returns:
            {imported, skipped, failed}
        """
        path = Path(input_path)
        if not path.exists():
            return {"imported": 0, "skipped": 0, "failed": 0}

        entries = []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path))
            ws = wb.active

            headers = {}
            for col_num, cell in enumerate(next(ws.iter_rows(values_only=True)), 1):
                headers[str(cell).strip().lower()] = col_num

            content_col = headers.get("内容", 2)
            category_col = headers.get("分类", 3)
            tags_col = headers.get("标签", 4)
            privacy_col = headers.get("隐私等级", 5)
            importance_col = headers.get("重要性", 6)
            layer_col = headers.get("层级", 8)

            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[content_col - 1] and str(row[content_col - 1]).strip():
                    content = str(row[content_col - 1]).strip()
                    category = target_category or (str(row[category_col - 1]).strip() if row[category_col - 1] else "general")
                    tags_str = str(row[tags_col - 1]).strip() if row[tags_col - 1] else ""
                    tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
                    privacy_str = str(row[privacy_col - 1]).strip() if row[privacy_col - 1] else "internal"
                    importance_str = str(row[importance_col - 1]).strip() if row[importance_col - 1] else "medium"
                    layer_str = str(row[layer_col - 1]).strip() if row[layer_col - 1] else "short_term"

                    entries.append({
                        "content": content,
                        "category": category,
                        "tags": tags,
                        "privacy": privacy_str,
                        "importance": importance_str,
                        "layer": layer_str,
                    })
        except ImportError:
            import csv
            with open(str(path), 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("内容") and row["内容"].strip():
                        content = row["内容"].strip()
                        category = target_category or (row.get("分类", "").strip() or "general")
                        tags_str = row.get("标签", "")
                        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
                        privacy_str = row.get("隐私等级", "internal").strip()
                        importance_str = row.get("重要性", "medium").strip()
                        layer_str = row.get("层级", "short_term").strip()

                        entries.append({
                            "content": content,
                            "category": category,
                            "tags": tags,
                            "privacy": privacy_str,
                            "importance": importance_str,
                            "layer": layer_str,
                        })

        imported = 0
        skipped = 0
        failed = 0

        for entry_data in entries:
            try:
                existing = None
                rows = self._get_conn().execute(
                    "SELECT id FROM memories WHERE content = ? AND category = ?",
                    (entry_data["content"], entry_data["category"])
                ).fetchall()
                if rows:
                    existing = rows[0][0]

                if existing:
                    skipped += 1
                    continue

                self.add_memory(
                    content=entry_data["content"],
                    category=entry_data["category"],
                    tags=entry_data["tags"],
                    privacy=PrivacyLevel.from_string(entry_data["privacy"]),
                    importance=Importance.from_string(entry_data["importance"]),
                    layer=target_layer or MemoryLayer.from_string(entry_data["layer"]),
                )
                imported += 1
            except (ValueError, TypeError, KeyError):
                failed += 1

        return {"imported": imported, "skipped": skipped, "failed": failed}

    def copy_memory(self,
                    entry_id: str,
                    new_category: str,
                    actor: str = "",
                    session_id: str = "") -> bool:
        """复制记忆到新分类（v5.1.9 新增）

        创建一条新的记忆条目，内容与原条目相同，但分类为新分类。

        Args:
            entry_id: 原记忆 ID
            new_category: 新分类名
            actor: 操作者
            session_id: 会话 ID

        Returns:
            是否复制成功
        """
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            return False

        original = self._row_to_entry(row)

        new_entry = self.add_memory(
            content=original.content,
            category=new_category,
            tags=original.tags,
            privacy=original.privacy,
            importance=original.importance,
            memory_type=original.memory_type,
            layer=original.layer,
            source_session=original.source_session,
            source_agent=original.source_agent,
            starred=original.starred,
            metadata={"_copied_from": original.id, **original.metadata},
        )

        self._add_audit(
            "copy", entry_id, actor, session_id, original.privacy.value,
            details={"message": f"复制到 {new_category}", "new_id": new_entry.id}
        )
        return True

    def move_memory(self,
                    entry_id: str,
                    new_category: str,
                    actor: str = "",
                    session_id: str = "") -> bool:
        """移动记忆到新分类（v5.1.9 新增）

        修改记忆的分类为新分类，同时同步更新 FTS 索引。

        Args:
            entry_id: 记忆 ID
            new_category: 新分类名
            actor: 操作者
            session_id: 会话 ID

        Returns:
            是否移动成功
        """
        conn = self._get_conn()
        row = conn.execute("SELECT category FROM memories WHERE id = ?", (entry_id,)).fetchone()
        if not row or row["category"] == "trash":
            return False

        old_category = row["category"]
        now = time.time()

        self.update_memory(
            entry_id=entry_id,
            category=new_category,
            actor=actor,
            session_id=session_id,
        )

        self._add_audit(
            "move", entry_id, actor, session_id, "",
            details={"message": f"从 {old_category} 移动到 {new_category}"}
        )
        return True

    # ===== 搜索增强（v5.2.0 新增）=====

    def fuzzy_search(self,
                     query: str,
                     category: Optional[str] = None,
                     layer: Optional[MemoryLayer] = None,
                     limit: int = 20,
                     threshold: float = 0.3) -> List[Dict[str, Any]]:
        """模糊搜索记忆（v5.2.0 新增）

        结合全文搜索和相似度计算，支持拼写纠错和近似匹配。

        Args:
            query: 搜索关键词
            category: 限定分类
            layer: 限定层级
            limit: 返回结果数量
            threshold: 相似度阈值（0-1）

        Returns:
            带分数的搜索结果列表 [{entry, score, highlights}]
        """
        conn = self._get_conn()
        query_lower = query.lower()

        base_query = "SELECT * FROM memories WHERE category != 'trash'"
        params = []

        if category:
            base_query += " AND category = ?"
            params.append(category)
        if layer:
            base_query += " AND layer = ?"
            params.append(layer.value)

        rows = conn.execute(base_query, params).fetchall()
        entries = [self._row_to_entry(r) for r in rows]

        scored = []
        for entry in entries:
            content_lower = entry.content.lower()
            tags_lower = [t.lower() for t in entry.tags]
            cat_lower = entry.category.lower()

            score = 0.0
            highlights = []

            if query_lower in content_lower:
                score += 0.8
                pos = content_lower.find(query_lower)
                highlights.append({
                    "field": "content",
                    "start": pos,
                    "end": pos + len(query),
                    "text": entry.content[max(0, pos - 20):pos + len(query) + 20]
                })

            if query_lower in cat_lower:
                score += 0.5

            for tag in tags_lower:
                if query_lower in tag:
                    score += 0.4
                    break

            if score == 0:
                words = set(query_lower.split())
                content_words = set(content_lower.split())
                if words and content_words:
                    overlap = len(words & content_words)
                    score = overlap / max(len(words), 1) * 0.3

            if score >= threshold:
                scored.append({
                    "entry": entry,
                    "score": round(score, 4),
                    "highlights": highlights
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取搜索历史（v5.2.0 新增）

        Args:
            limit: 返回条数

        Returns:
            搜索历史列表 [{query, count, last_used}]
        """
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT query, MAX(timestamp) as last_used, COUNT(*) as cnt
                FROM audit_log
                WHERE action = 'search'
                GROUP BY query
                ORDER BY last_used DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [
                {"query": row["query"], "count": row["cnt"], "last_used": row["last_used"]}
                for row in rows if row["query"]
            ]
        except sqlite3.OperationalError:
            return []

    def highlight_text(self, text: str, query: str,
                       before_tag: str = "<mark>",
                       after_tag: str = "</mark>") -> str:
        """高亮搜索关键词（v5.2.0 新增）

        Args:
            text: 原始文本
            query: 搜索关键词
            before_tag: 高亮起始标签
            after_tag: 高亮结束标签

        Returns:
            带高亮标记的文本
        """
        if not query or not text:
            return text

        import re
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return pattern.sub(lambda m: before_tag + m.group() + after_tag, text)

    # ===== 标签批量管理（v5.2.0 新增）=====

    def batch_add_tags(self,
                       entry_ids: List[str],
                       tags: List[str],
                       actor: str = "",
                       session_id: str = "") -> int:
        """批量添加标签（v5.2.0 新增）

        Args:
            entry_ids: 记忆 ID 列表
            tags: 要添加的标签列表
            actor: 操作者
            session_id: 会话 ID

        Returns:
            受影响的记忆条数
        """
        conn = self._get_conn()
        count = 0
        now = time.time()

        for entry_id in entry_ids:
            row = conn.execute(
                "SELECT tags FROM memories WHERE id = ? AND category != 'trash'",
                (entry_id,)
            ).fetchone()
            if not row:
                continue

            existing_tags = self._safe_json_loads(row["tags"], [])
            new_tags = list(set(existing_tags + tags))
            if new_tags != existing_tags:
                conn.execute(
                    "UPDATE memories SET tags = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(new_tags, ensure_ascii=False), now, entry_id)
                )
                self._add_audit(
                    "batch_add_tags", entry_id, actor, session_id, "",
                    details={"added_tags": tags, "result_tags": new_tags}
                )
                count += 1

        conn.commit()
        return count

    def batch_remove_tags(self,
                          entry_ids: List[str],
                          tags: List[str],
                          actor: str = "",
                          session_id: str = "") -> int:
        """批量移除标签（v5.2.0 新增）

        Args:
            entry_ids: 记忆 ID 列表
            tags: 要移除的标签列表
            actor: 操作者
            session_id: 会话 ID

        Returns:
            受影响的记忆条数
        """
        conn = self._get_conn()
        count = 0
        now = time.time()

        for entry_id in entry_ids:
            row = conn.execute(
                "SELECT tags FROM memories WHERE id = ? AND category != 'trash'",
                (entry_id,)
            ).fetchone()
            if not row:
                continue

            existing_tags = self._safe_json_loads(row["tags"], [])
            new_tags = [t for t in existing_tags if t not in tags]
            if new_tags != existing_tags:
                conn.execute(
                    "UPDATE memories SET tags = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(new_tags, ensure_ascii=False), now, entry_id)
                )
                self._add_audit(
                    "batch_remove_tags", entry_id, actor, session_id, "",
                    details={"removed_tags": tags, "result_tags": new_tags}
                )
                count += 1

        conn.commit()
        return count

    def merge_tags(self,
                   source_tags: List[str],
                   target_tag: str,
                   actor: str = "",
                   session_id: str = "") -> int:
        """合并多个标签为一个标签（v5.2.0 新增）

        Args:
            source_tags: 要合并的源标签列表
            target_tag: 目标标签名
            actor: 操作者
            session_id: 会话 ID

        Returns:
            受影响的记忆条数
        """
        conn = self._get_conn()
        count = 0
        now = time.time()

        rows = conn.execute(
            "SELECT id, tags FROM memories WHERE category != 'trash'"
        ).fetchall()

        for row in rows:
            tags = self._safe_json_loads(row["tags"], [])
            has_source = any(t in source_tags for t in tags)
            if not has_source:
                continue

            new_tags = [t for t in tags if t not in source_tags]
            if target_tag not in new_tags:
                new_tags.append(target_tag)

            if new_tags != tags:
                conn.execute(
                    "UPDATE memories SET tags = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(new_tags, ensure_ascii=False), now, row["id"])
                )
                self._add_audit(
                    "merge_tags", row["id"], actor, session_id, "",
                    details={"source_tags": source_tags, "target_tag": target_tag}
                )
                count += 1

        conn.commit()
        return count

    def add_tags_by_category(self,
                             category: str,
                             tags: List[str],
                             actor: str = "",
                             session_id: str = "") -> int:
        """按分类批量添加标签（v5.2.0 新增）

        Args:
            category: 分类名
            tags: 要添加的标签列表
            actor: 操作者
            session_id: 会话 ID

        Returns:
            受影响的记忆条数
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id FROM memories WHERE category = ? AND category != 'trash'",
            (category,)
        ).fetchall()
        entry_ids = [r["id"] for r in rows]
        return self.batch_add_tags(entry_ids, tags, actor, session_id)

    # ===== 数据备份与恢复（v5.2.0 新增）=====

    def create_backup(self, backup_dir: str = "./data/backups") -> Dict[str, Any]:
        """创建数据库备份（v5.2.0 新增）

        Args:
            backup_dir: 备份目录

        Returns:
            {path, size_mb, timestamp, success}
        """
        import shutil
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"memory_backup_{timestamp}.db"

        try:
            shutil.copy2(str(self.db_path), str(backup_file))
            size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)
            return {
                "success": True,
                "path": str(backup_file),
                "size_mb": size_mb,
                "timestamp": timestamp,
                "filename": backup_file.name,
            }
        except (OSError, IOError) as e:
            return {
                "success": False,
                "error": str(e),
                "path": str(backup_file),
            }

    def list_backups(self, backup_dir: str = "./data/backups") -> List[Dict[str, Any]]:
        """列出所有备份（v5.2.0 新增）

        Args:
            backup_dir: 备份目录

        Returns:
            备份列表 [{filename, path, size_mb, created_at}]
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return []

        backups = []
        for f in sorted(backup_path.glob("memory_backup_*.db"), reverse=True):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": stat.st_ctime,
            })
        return backups

    def restore_backup(self, backup_path: str,
                       create_backup_before: bool = True) -> Dict[str, Any]:
        """从备份恢复数据库（v5.2.0 新增）

        Args:
            backup_path: 备份文件路径
            create_backup_before: 恢复前是否先备份当前数据库

        Returns:
            {success, restored_from, backup_created, error}
        """
        import shutil
        backup_file = Path(backup_path)
        if not backup_file.exists():
            return {"success": False, "error": "备份文件不存在"}

        result = {
            "success": False,
            "restored_from": str(backup_file),
            "backup_created": None,
        }

        try:
            if create_backup_before:
                pre_backup = self.create_backup()
                if pre_backup["success"]:
                    result["backup_created"] = pre_backup["path"]

            if self._conn:
                self._conn.close()
                self._conn = None

            shutil.copy2(str(backup_file), str(self.db_path))

            self._init_db()
            result["success"] = True
        except (OSError, IOError) as e:
            result["error"] = str(e)

        return result

    def delete_old_backups(self, backup_dir: str = "./data/backups",
                           keep_count: int = 10) -> int:
        """删除旧备份，保留最新的 N 个（v5.2.0 新增）

        Args:
            backup_dir: 备份目录
            keep_count: 保留数量

        Returns:
            删除的备份数量
        """
        backups = self.list_backups(backup_dir)
        if len(backups) <= keep_count:
            return 0

        deleted = 0
        for backup in backups[keep_count:]:
            try:
                Path(backup["path"]).unlink()
                deleted += 1
            except (OSError, IOError):
                pass
        return deleted

    # ===== AI 短剧记忆模块（v5.2.1 新增）=====

    # --- 安全验证辅助方法（v5.2.1 新增）---

    @staticmethod
    def _validate_str(value: str, name: str, max_len: int = 1000) -> str:
        """字符串输入验证（v5.2.1 新增）"""
        if value is None:
            return ""
        value = str(value)
        if len(value) > max_len:
            value = value[:max_len]
        return value

    @staticmethod
    def _validate_int(value: int, name: str, min_val: int = 0, max_val: int = 100000) -> int:
        """整数输入验证（v5.2.1 新增）"""
        try:
            value = int(value)
        except (TypeError, ValueError):
            return min_val
        if value < min_val:
            return min_val
        if value > max_val:
            return max_val
        return value

    @staticmethod
    def _validate_float(value: float, name: str, min_val: float = 0.0, max_val: float = 100.0) -> float:
        """浮点数输入验证（v5.2.1 新增）"""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return min_val
        if value < min_val:
            return min_val
        if value > max_val:
            return max_val
        return value

    # --- 短剧系列 ---

    def add_drama(self,
                  title: str,
                  genre: DramaGenre = DramaGenre.OTHER,
                  total_episodes: int = 0,
                  status: DramaStatus = DramaStatus.PLANNED,
                  platform: str = "",
                  rating: float = 0.0,
                  description: str = "",
                  tags: Optional[List[str]] = None,
                  cover_url: str = "",
                  metadata: Optional[Dict[str, Any]] = None) -> DramaSeries:
        """添加短剧（v5.2.1 新增）"""
        now = time.time()
        drama_id = str(uuid.uuid4())

        title = self._validate_str(title, "title", max_len=200)
        platform = self._validate_str(platform, "platform", max_len=100)
        rating = self._validate_float(rating, "rating", min_val=0.0, max_val=10.0)
        description = self._validate_str(description, "description", max_len=5000)
        cover_url = self._validate_str(cover_url, "cover_url", max_len=500)
        total_episodes = self._validate_int(total_episodes, "total_episodes", min_val=0, max_val=10000)

        if not isinstance(genre, DramaGenre):
            genre = DramaGenre.OTHER
        if not isinstance(status, DramaStatus):
            status = DramaStatus.PLANNED

        drama = DramaSeries(
            id=drama_id,
            title=title,
            genre=genre,
            total_episodes=total_episodes,
            current_episode=0,
            status=status,
            platform=platform,
            rating=rating,
            description=description,
            tags=tags or [],
            cover_url=cover_url,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
            last_watched_at=0.0,
        )

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO drama_series (
                id, title, genre, total_episodes, current_episode,
                status, platform, rating, description, tags,
                cover_url, metadata, created_at, updated_at, last_watched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            drama.id, drama.title, drama.genre.value,
            drama.total_episodes, drama.current_episode,
            drama.status.value, drama.platform, drama.rating,
            drama.description, json.dumps(drama.tags, ensure_ascii=False),
            drama.cover_url, json.dumps(drama.metadata, ensure_ascii=False),
            drama.created_at, drama.updated_at, drama.last_watched_at,
        ))
        conn.commit()
        return drama

    def get_drama(self, drama_id: str) -> Optional[DramaSeries]:
        """获取短剧详情（v5.2.1 新增）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM drama_series WHERE id = ?",
            (drama_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_drama(row)

    def list_dramas(self,
                    genre: Optional[DramaGenre] = None,
                    status: Optional[DramaStatus] = None,
                    platform: Optional[str] = None,
                    min_rating: float = 0.0,
                    limit: int = 50,
                    offset: int = 0,
                    sort_by: str = "updated_at",
                    sort_order: str = "desc") -> List[DramaSeries]:
        """列出短剧（v5.2.1 新增）"""
        conn = self._get_conn()
        query = "SELECT * FROM drama_series WHERE 1=1"
        params = []

        if genre:
            query += " AND genre = ?"
            params.append(genre.value)
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if min_rating > 0:
            query += " AND rating >= ?"
            params.append(min_rating)

        valid_sorts = ["created_at", "updated_at", "rating", "last_watched_at", "title"]
        if sort_by not in valid_sorts:
            sort_by = "updated_at"
        sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"

        query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_drama(r) for r in rows]

    def update_drama(self,
                     drama_id: str,
                     title: Optional[str] = None,
                     genre: Optional[DramaGenre] = None,
                     total_episodes: Optional[int] = None,
                     current_episode: Optional[int] = None,
                     status: Optional[DramaStatus] = None,
                     platform: Optional[str] = None,
                     rating: Optional[float] = None,
                     description: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     cover_url: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     mark_watched: bool = False) -> bool:
        """更新短剧信息（v5.2.1 新增）"""
        conn = self._get_conn()
        now = time.time()

        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(self._validate_str(title, "title", max_len=200))
        if genre is not None:
            if not isinstance(genre, DramaGenre):
                genre = DramaGenre.OTHER
            updates.append("genre = ?")
            params.append(genre.value)
        if total_episodes is not None:
            updates.append("total_episodes = ?")
            params.append(self._validate_int(total_episodes, "total_episodes", min_val=0, max_val=10000))
        if current_episode is not None:
            updates.append("current_episode = ?")
            params.append(self._validate_int(current_episode, "current_episode", min_val=0, max_val=10000))
        if status is not None:
            if not isinstance(status, DramaStatus):
                status = DramaStatus.PLANNED
            updates.append("status = ?")
            params.append(status.value)
        if platform is not None:
            updates.append("platform = ?")
            params.append(self._validate_str(platform, "platform", max_len=100))
        if rating is not None:
            updates.append("rating = ?")
            params.append(self._validate_float(rating, "rating", min_val=0.0, max_val=10.0))
        if description is not None:
            updates.append("description = ?")
            params.append(self._validate_str(description, "description", max_len=5000))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if cover_url is not None:
            updates.append("cover_url = ?")
            params.append(self._validate_str(cover_url, "cover_url", max_len=500))
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates and not mark_watched:
            return False

        updates.append("updated_at = ?")
        params.append(now)

        if mark_watched:
            updates.append("last_watched_at = ?")
            params.append(now)

        params.append(drama_id)

        cursor = conn.execute(
            f"UPDATE drama_series SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_drama(self, drama_id: str) -> bool:
        """删除短剧（v5.2.1 新增）
        同时删除关联的场次、角色、台词
        """
        conn = self._get_conn()
        conn.execute("DELETE FROM drama_lines WHERE drama_id = ?", (drama_id,))
        conn.execute("DELETE FROM drama_characters WHERE drama_id = ?", (drama_id,))
        conn.execute("DELETE FROM drama_scenes WHERE drama_id = ?", (drama_id,))
        cursor = conn.execute("DELETE FROM drama_series WHERE id = ?", (drama_id,))
        conn.commit()
        return cursor.rowcount > 0

    def drama_stats(self) -> Dict[str, Any]:
        """短剧统计（v5.2.1 新增）"""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) as cnt FROM drama_series").fetchone()["cnt"]
        by_genre = {}
        by_status = {}

        for row in conn.execute("SELECT genre, COUNT(*) as cnt FROM drama_series GROUP BY genre"):
            by_genre[row["genre"]] = row["cnt"]
        for row in conn.execute("SELECT status, COUNT(*) as cnt FROM drama_series GROUP BY status"):
            by_status[row["status"]] = row["cnt"]

        watching = conn.execute(
            "SELECT COUNT(*) as cnt FROM drama_series WHERE status = 'watching'"
        ).fetchone()["cnt"]
        completed = conn.execute(
            "SELECT COUNT(*) as cnt FROM drama_series WHERE status = 'completed'"
        ).fetchone()["cnt"]
        total_lines = conn.execute("SELECT COUNT(*) as cnt FROM drama_lines").fetchone()["cnt"]
        classic_lines = conn.execute(
            "SELECT COUNT(*) as cnt FROM drama_lines WHERE is_classic = 1"
        ).fetchone()["cnt"]

        return {
            "total": total,
            "by_genre": by_genre,
            "by_status": by_status,
            "watching": watching,
            "completed": completed,
            "total_lines": total_lines,
            "classic_lines": classic_lines,
        }

    def _row_to_drama(self, row) -> DramaSeries:
        return DramaSeries(
            id=row["id"],
            title=row["title"],
            genre=DramaGenre(row["genre"]) if row["genre"] else DramaGenre.OTHER,
            total_episodes=row["total_episodes"] or 0,
            current_episode=row["current_episode"] or 0,
            status=DramaStatus(row["status"]) if row["status"] else DramaStatus.PLANNED,
            platform=row["platform"] or "",
            rating=row["rating"] or 0.0,
            description=row["description"] or "",
            tags=self._safe_json_loads(row["tags"], []),
            cover_url=row["cover_url"] or "",
            metadata=self._safe_json_loads(row["metadata"], {}),
            created_at=row["created_at"] or 0.0,
            updated_at=row["updated_at"] or 0.0,
            last_watched_at=row["last_watched_at"] or 0.0,
        )

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
                  metadata: Optional[Dict[str, Any]] = None) -> DramaScene:
        """添加短剧场次（v5.2.1 新增）"""
        now = time.time()
        scene_id = str(uuid.uuid4())

        title = self._validate_str(title, "title", max_len=200)
        content = self._validate_str(content, "content", max_len=10000)
        location = self._validate_str(location, "location", max_len=200)
        time_of_day = self._validate_str(time_of_day, "time_of_day", max_len=50)
        episode = self._validate_int(episode, "episode", min_val=0, max_val=10000)
        scene_number = self._validate_int(scene_number, "scene_number", min_val=0, max_val=10000)

        scene = DramaScene(
            id=scene_id,
            drama_id=drama_id,
            episode=episode,
            scene_number=scene_number,
            title=title,
            content=content,
            location=location,
            time_of_day=time_of_day,
            tags=tags or [],
            metadata=metadata or {},
            created_at=now,
        )

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO drama_scenes (
                id, drama_id, episode, scene_number, title,
                content, location, time_of_day, tags, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scene.id, scene.drama_id, scene.episode, scene.scene_number,
            scene.title, scene.content, scene.location, scene.time_of_day,
            json.dumps(scene.tags, ensure_ascii=False),
            json.dumps(scene.metadata, ensure_ascii=False),
            scene.created_at,
        ))
        conn.commit()
        return scene

    def get_scene(self, scene_id: str) -> Optional[DramaScene]:
        """获取场次详情（v5.2.1 新增）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM drama_scenes WHERE id = ?",
            (scene_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_scene(row)

    def list_scenes(self,
                    drama_id: Optional[str] = None,
                    episode: Optional[int] = None,
                    limit: int = 100,
                    offset: int = 0) -> List[DramaScene]:
        """列出短剧场次（v5.2.1 新增）"""
        conn = self._get_conn()
        query = "SELECT * FROM drama_scenes WHERE 1=1"
        params = []

        if drama_id:
            query += " AND drama_id = ?"
            params.append(drama_id)
        if episode is not None:
            query += " AND episode = ?"
            params.append(episode)

        query += " ORDER BY episode ASC, scene_number ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_scene(r) for r in rows]

    def update_scene(self,
                     scene_id: str,
                     title: Optional[str] = None,
                     content: Optional[str] = None,
                     location: Optional[str] = None,
                     time_of_day: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新场次（v5.2.1 新增）"""
        conn = self._get_conn()
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(self._validate_str(title, "title", max_len=200))
        if content is not None:
            updates.append("content = ?")
            params.append(self._validate_str(content, "content", max_len=10000))
        if location is not None:
            updates.append("location = ?")
            params.append(self._validate_str(location, "location", max_len=200))
        if time_of_day is not None:
            updates.append("time_of_day = ?")
            params.append(self._validate_str(time_of_day, "time_of_day", max_len=50))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates:
            return False

        params.append(scene_id)
        cursor = conn.execute(
            f"UPDATE drama_scenes SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_scene(self, scene_id: str) -> bool:
        """删除场次（v5.2.1 新增）"""
        conn = self._get_conn()
        conn.execute("DELETE FROM drama_lines WHERE scene_id = ?", (scene_id,))
        cursor = conn.execute("DELETE FROM drama_scenes WHERE id = ?", (scene_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_scene(self, row) -> DramaScene:
        return DramaScene(
            id=row["id"],
            drama_id=row["drama_id"],
            episode=row["episode"] or 0,
            scene_number=row["scene_number"] or 0,
            title=row["title"] or "",
            content=row["content"] or "",
            location=row["location"] or "",
            time_of_day=row["time_of_day"] or "",
            tags=self._safe_json_loads(row["tags"], []),
            metadata=self._safe_json_loads(row["metadata"], {}),
            created_at=row["created_at"] or 0.0,
        )

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
                      metadata: Optional[Dict[str, Any]] = None) -> DramaCharacter:
        """添加短剧角色（v5.2.1 新增）"""
        now = time.time()
        char_id = str(uuid.uuid4())

        name = self._validate_str(name, "name", max_len=100)
        role = self._validate_str(role, "role", max_len=50)
        actor = self._validate_str(actor, "actor", max_len=100)
        description = self._validate_str(description, "description", max_len=2000)
        personality = self._validate_str(personality, "personality", max_len=1000)
        avatar_url = self._validate_str(avatar_url, "avatar_url", max_len=500)

        character = DramaCharacter(
            id=char_id,
            drama_id=drama_id,
            name=name,
            role=role,
            actor=actor,
            description=description,
            personality=personality,
            avatar_url=avatar_url,
            tags=tags or [],
            metadata=metadata or {},
            created_at=now,
        )

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO drama_characters (
                id, drama_id, name, role, actor, description,
                personality, avatar_url, tags, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            character.id, character.drama_id, character.name,
            character.role, character.actor, character.description,
            character.personality, character.avatar_url,
            json.dumps(character.tags, ensure_ascii=False),
            json.dumps(character.metadata, ensure_ascii=False),
            character.created_at,
        ))
        conn.commit()
        return character

    def get_character(self, char_id: str) -> Optional[DramaCharacter]:
        """获取角色详情（v5.2.1 新增）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM drama_characters WHERE id = ?",
            (char_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_character(row)

    def list_characters(self,
                        drama_id: Optional[str] = None,
                        role: Optional[str] = None,
                        limit: int = 100,
                        offset: int = 0) -> List[DramaCharacter]:
        """列出短剧角色（v5.2.1 新增）"""
        conn = self._get_conn()
        query = "SELECT * FROM drama_characters WHERE 1=1"
        params = []

        if drama_id:
            query += " AND drama_id = ?"
            params.append(drama_id)
        if role:
            query += " AND role = ?"
            params.append(role)

        query += " ORDER BY created_at ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_character(r) for r in rows]

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
        conn = self._get_conn()
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(self._validate_str(name, "name", max_len=100))
        if role is not None:
            updates.append("role = ?")
            params.append(self._validate_str(role, "role", max_len=50))
        if actor is not None:
            updates.append("actor = ?")
            params.append(self._validate_str(actor, "actor", max_len=100))
        if description is not None:
            updates.append("description = ?")
            params.append(self._validate_str(description, "description", max_len=2000))
        if personality is not None:
            updates.append("personality = ?")
            params.append(self._validate_str(personality, "personality", max_len=1000))
        if avatar_url is not None:
            updates.append("avatar_url = ?")
            params.append(self._validate_str(avatar_url, "avatar_url", max_len=500))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates:
            return False

        params.append(char_id)
        cursor = conn.execute(
            f"UPDATE drama_characters SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_character(self, char_id: str) -> bool:
        """删除角色（v5.2.1 新增）"""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM drama_characters WHERE id = ?", (char_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_character(self, row) -> DramaCharacter:
        return DramaCharacter(
            id=row["id"],
            drama_id=row["drama_id"],
            name=row["name"],
            role=row["role"] or "supporting",
            actor=row["actor"] or "",
            description=row["description"] or "",
            personality=row["personality"] or "",
            avatar_url=row["avatar_url"] or "",
            tags=self._safe_json_loads(row["tags"], []),
            metadata=self._safe_json_loads(row["metadata"], {}),
            created_at=row["created_at"] or 0.0,
        )

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
                 metadata: Optional[Dict[str, Any]] = None) -> DramaLine:
        """添加短剧台词（v5.2.1 新增）"""
        now = time.time()
        line_id = str(uuid.uuid4())

        line_text = self._validate_str(line_text, "line_text", max_len=2000)
        character_name = self._validate_str(character_name, "character_name", max_len=100)
        context = self._validate_str(context, "context", max_len=2000)
        episode = self._validate_int(episode, "episode", min_val=0, max_val=10000)
        timestamp_float = self._validate_float(timestamp if timestamp else 0.0, "timestamp", min_val=0.0, max_val=100000.0)
        timestamp = str(timestamp_float)

        line = DramaLine(
            id=line_id,
            drama_id=drama_id,
            scene_id=scene_id,
            character_id=character_id,
            character_name=character_name,
            line_text=line_text,
            context=context,
            episode=episode,
            timestamp=timestamp,
            is_classic=is_classic,
            memory_id="",
            tags=tags or [],
            metadata=metadata or {},
            created_at=now,
        )

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO drama_lines (
                id, drama_id, scene_id, character_id, character_name,
                line_text, context, episode, timestamp, is_classic,
                memory_id, tags, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            line.id, line.drama_id, line.scene_id, line.character_id,
            line.character_name, line.line_text, line.context,
            line.episode, line.timestamp, int(line.is_classic),
            line.memory_id, json.dumps(line.tags, ensure_ascii=False),
            json.dumps(line.metadata, ensure_ascii=False), line.created_at,
        ))
        conn.commit()
        return line

    def get_line(self, line_id: str) -> Optional[DramaLine]:
        """获取台词详情（v5.2.1 新增）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM drama_lines WHERE id = ?",
            (line_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_line(row)

    def list_lines(self,
                   drama_id: Optional[str] = None,
                   scene_id: Optional[str] = None,
                   character_id: Optional[str] = None,
                   is_classic: Optional[bool] = None,
                   episode: Optional[int] = None,
                   limit: int = 100,
                   offset: int = 0) -> List[DramaLine]:
        """列出台词（v5.2.1 新增）"""
        conn = self._get_conn()
        query = "SELECT * FROM drama_lines WHERE 1=1"
        params = []

        if drama_id:
            query += " AND drama_id = ?"
            params.append(drama_id)
        if scene_id:
            query += " AND scene_id = ?"
            params.append(scene_id)
        if character_id:
            query += " AND character_id = ?"
            params.append(character_id)
        if is_classic is not None:
            query += " AND is_classic = ?"
            params.append(1 if is_classic else 0)
        if episode is not None:
            query += " AND episode = ?"
            params.append(episode)

        query += " ORDER BY episode ASC, created_at ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_line(r) for r in rows]

    def update_line(self,
                    line_id: str,
                    line_text: Optional[str] = None,
                    character_name: Optional[str] = None,
                    context: Optional[str] = None,
                    is_classic: Optional[bool] = None,
                    tags: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新台词（v5.2.1 新增）"""
        conn = self._get_conn()
        updates = []
        params = []

        if line_text is not None:
            updates.append("line_text = ?")
            params.append(self._validate_str(line_text, "line_text", max_len=2000))
        if character_name is not None:
            updates.append("character_name = ?")
            params.append(self._validate_str(character_name, "character_name", max_len=100))
        if context is not None:
            updates.append("context = ?")
            params.append(self._validate_str(context, "context", max_len=2000))
        if is_classic is not None:
            updates.append("is_classic = ?")
            params.append(1 if is_classic else 0)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates:
            return False

        params.append(line_id)
        cursor = conn.execute(
            f"UPDATE drama_lines SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_line(self, line_id: str) -> bool:
        """删除台词（v5.2.1 新增）"""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM drama_lines WHERE id = ?", (line_id,))
        conn.commit()
        return cursor.rowcount > 0

    def search_lines(self,
                     query: str,
                     drama_id: Optional[str] = None,
                     is_classic_only: bool = False,
                     limit: int = 20) -> List[DramaLine]:
        """搜索台词（v5.2.1 新增）"""
        conn = self._get_conn()
        sql = "SELECT * FROM drama_lines WHERE line_text LIKE ?"
        params = [f"%{query}%"]

        if drama_id:
            sql += " AND drama_id = ?"
            params.append(drama_id)
        if is_classic_only:
            sql += " AND is_classic = 1"

        sql += " LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_line(r) for r in rows]

    def classic_lines(self,
                      drama_id: Optional[str] = None,
                      limit: int = 20) -> List[DramaLine]:
        """获取经典台词（v5.2.1 新增）"""
        return self.list_lines(
            drama_id=drama_id,
            is_classic=True,
            limit=limit,
        )

    def _row_to_line(self, row) -> DramaLine:
        return DramaLine(
            id=row["id"],
            drama_id=row["drama_id"],
            scene_id=row["scene_id"] or "",
            character_id=row["character_id"] or "",
            character_name=row["character_name"] or "",
            line_text=row["line_text"],
            context=row["context"] or "",
            episode=row["episode"] or 0,
            timestamp=row["timestamp"] or "",
            is_classic=bool(row["is_classic"]),
            memory_id=row["memory_id"] or "",
            tags=self._safe_json_loads(row["tags"], []),
            metadata=self._safe_json_loads(row["metadata"], {}),
            created_at=row["created_at"] or 0.0,
        )

    # ===== v5.2.4 新增方法 =====

    def add_note(self, memory_id: str, content: str, author: str = "",
                 tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """添加记忆笔记/批注（v5.2.4 新增）"""
        conn = self._get_conn()
        # 验证记忆存在
        row = conn.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"记忆不存在: {memory_id}"}

        now = time.time()
        note_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO memory_notes (id, memory_id, content, author, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (note_id, memory_id, content, author,
              json.dumps(tags or [], ensure_ascii=False), now, now))
        conn.commit()
        self._add_audit("add_note", memory_id, author, "", "INTERNAL")
        return {"success": True, "note_id": note_id, "memory_id": memory_id}

    def list_notes(self, memory_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列出记忆的笔记（v5.2.4 新增）"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM memory_notes WHERE memory_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (memory_id, limit, offset)).fetchall()
        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "memory_id": row["memory_id"],
                "content": row["content"],
                "author": row["author"],
                "tags": self._safe_json_loads(row["tags"], []),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
        return results

    def delete_note(self, note_id: str) -> Dict[str, Any]:
        """删除笔记（v5.2.4 新增）"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM memory_notes WHERE id = ?", (note_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"笔记不存在: {note_id}"}
        conn.execute("DELETE FROM memory_notes WHERE id = ?", (note_id,))
        conn.commit()
        self._add_audit("delete_note", row["memory_id"], "", "", "INTERNAL")
        return {"success": True, "note_id": note_id}

    def add_template(self, name: str, content_template: str, category: str = "general",
                     tags: Optional[List[str]] = None, importance: str = "MEDIUM",
                     layer: str = "short_term", description: str = "") -> Dict[str, Any]:
        """添加记忆模板（v5.2.4 新增）"""
        conn = self._get_conn()
        # 检查名称重复
        existing = conn.execute("SELECT id FROM memory_templates WHERE name = ?", (name,)).fetchone()
        if existing:
            return {"success": False, "error": f"模板名称已存在: {name}"}

        now = time.time()
        template_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO memory_templates (id, name, content_template, category, tags,
                                          importance, layer, description, use_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (template_id, name, content_template, category,
              json.dumps(tags or [], ensure_ascii=False), importance, layer, description, now, now))
        conn.commit()
        return {"success": True, "template_id": template_id, "name": name}

    def list_templates(self, category: Optional[str] = None,
                       limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列出记忆模板（v5.2.4 新增）"""
        conn = self._get_conn()
        query = "SELECT * FROM memory_templates WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY use_count DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "name": row["name"],
                "content_template": row["content_template"],
                "category": row["category"],
                "tags": self._safe_json_loads(row["tags"], []),
                "importance": row["importance"],
                "layer": row["layer"],
                "description": row["description"],
                "use_count": row["use_count"],
                "created_at": row["created_at"],
            })
        return results

    def use_template(self, template_id: str, variables: Optional[Dict[str, str]] = None,
                     actor: str = "", session_id: str = "") -> Dict[str, Any]:
        """使用模板创建记忆（v5.2.4 新增）"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM memory_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"模板不存在: {template_id}"}

        # 替换模板变量 {var_name}
        content = row["content_template"]
        if variables:
            for key, value in variables.items():
                content = content.replace("{" + key + "}", value)

        # 创建记忆
        entry = self.add_memory(
            content=content,
            category=row["category"],
            tags=self._safe_json_loads(row["tags"], []),
            importance=Importance.from_string(row["importance"]) if hasattr(Importance, 'from_string') else Importance.MEDIUM,
            layer=MemoryLayer.from_string(row["layer"]) if hasattr(MemoryLayer, 'from_string') else MemoryLayer.SHORT_TERM,
            source_session=session_id,
            source_agent=actor,
        )

        # 更新使用次数
        conn.execute("UPDATE memory_templates SET use_count = use_count + 1, updated_at = ? WHERE id = ?",
                     (time.time(), template_id))
        conn.commit()

        return {"success": True, "memory_id": entry.id, "template_name": row["name"], "content": content}

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """删除模板（v5.2.4 新增）"""
        conn = self._get_conn()
        row = conn.execute("SELECT id, name FROM memory_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"模板不存在: {template_id}"}
        conn.execute("DELETE FROM memory_templates WHERE id = ?", (template_id,))
        conn.commit()
        return {"success": True, "template_id": template_id, "name": row["name"]}

    def batch_update(self, memory_ids: Optional[List[str]] = None,
                     category: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     importance: Optional[str] = None,
                     layer: Optional[str] = None,
                     starred: Optional[bool] = None,
                     actor: str = "", session_id: str = "") -> Dict[str, Any]:
        """批量更新记忆（v5.2.4 新增）

        Args:
            memory_ids: 要更新的记忆 ID 列表
            category: 新分类（None 表示不修改）
            tags: 新标签（None 表示不修改）
            importance: 新重要性（None 表示不修改）
            layer: 新层级（None 表示不修改）
            starred: 新收藏状态（None 表示不修改）
        """
        if not memory_ids:
            return {"success": False, "error": "未指定记忆 ID", "updated": 0}

        conn = self._get_conn()
        now = time.time()
        updated = 0
        errors = []

        for mid in memory_ids:
            row = conn.execute("SELECT id FROM memories WHERE id = ?", (mid,)).fetchone()
            if not row:
                errors.append(mid)
                continue

            updates = ["updated_at = ?"]
            params = [now]

            if category is not None:
                updates.append("category = ?")
                params.append(category)
            if tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(tags, ensure_ascii=False))
            if importance is not None:
                updates.append("importance = ?")
                params.append(importance)
            if layer is not None:
                updates.append("layer = ?")
                params.append(layer)
            if starred is not None:
                updates.append("starred = ?")
                params.append(1 if starred else 0)

            params.append(mid)
            conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", params)
            updated += 1

        conn.commit()
        self._add_audit("batch_update", ",".join(memory_ids[:5]), actor, session_id, "INTERNAL",
                        {"updated": updated, "category": category, "importance": importance})
        return {"success": True, "updated": updated, "errors": errors, "total": len(memory_ids)}

    def create_review_schedule(self, memory_id: str, interval_days: float = 1.0,
                               actor: str = "") -> Dict[str, Any]:
        """创建复习计划（v5.2.4 新增）"""
        conn = self._get_conn()
        row = conn.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"记忆不存在: {memory_id}"}

        now = time.time()
        schedule_id = str(uuid.uuid4())
        scheduled_at = now + interval_days * 86400

        conn.execute("""
            INSERT INTO review_schedules (id, memory_id, scheduled_at, interval_days,
                                          review_count, last_reviewed_at, status, created_at)
            VALUES (?, ?, ?, ?, 0, 0.0, 'pending', ?)
        """, (schedule_id, memory_id, scheduled_at, interval_days, now))
        conn.commit()
        return {"success": True, "schedule_id": schedule_id, "memory_id": memory_id,
                "scheduled_at": scheduled_at, "interval_days": interval_days}

    def list_due_reviews(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出到期复习（v5.2.4 新增）"""
        conn = self._get_conn()
        now = time.time()
        rows = conn.execute("""
            SELECT rs.*, m.content, m.category, m.importance, m.layer
            FROM review_schedules rs
            JOIN memories m ON rs.memory_id = m.id
            WHERE rs.status = 'pending' AND rs.scheduled_at <= ?
            ORDER BY rs.scheduled_at ASC
            LIMIT ?
        """, (now, limit)).fetchall()
        results = []
        for row in rows:
            results.append({
                "schedule_id": row["id"],
                "memory_id": row["memory_id"],
                "content": row["content"][:100] if row["content"] else "[已加密]",
                "category": row["category"],
                "importance": row["importance"],
                "layer": row["layer"],
                "scheduled_at": row["scheduled_at"],
                "interval_days": row["interval_days"],
                "review_count": row["review_count"],
            })
        return results

    def complete_review(self, schedule_id: str) -> Dict[str, Any]:
        """完成复习，自动安排下次（v5.2.4 新增）

        使用间隔重复算法：每次复习后间隔翻倍（1天→2天→4天→7天→15天→30天）
        """
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM review_schedules WHERE id = ?", (schedule_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"复习计划不存在: {schedule_id}"}

        now = time.time()
        new_count = row["review_count"] + 1
        # 间隔重复：1, 2, 4, 7, 15, 30 天
        intervals = [1, 2, 4, 7, 15, 30]
        new_interval = intervals[min(new_count, len(intervals) - 1)]
        next_scheduled = now + new_interval * 86400

        conn.execute("""
            UPDATE review_schedules
            SET review_count = ?, last_reviewed_at = ?, interval_days = ?,
                scheduled_at = ?, status = 'pending'
            WHERE id = ?
        """, (new_count, now, new_interval, next_scheduled, schedule_id))

        # 更新记忆的巩固次数和强度
        conn.execute("""
            UPDATE memories SET consolidation_count = consolidation_count + 1,
                   strength = MIN(strength + 0.1, 2.0), last_accessed_at = ?
            WHERE id = ?
        """, (now, row["memory_id"]))

        conn.commit()
        self._add_audit("complete_review", row["memory_id"], "", "", "INTERNAL")
        return {"success": True, "schedule_id": schedule_id, "review_count": new_count,
                "next_interval_days": new_interval, "next_scheduled_at": next_scheduled}

    def get_review_stats(self) -> Dict[str, Any]:
        """复习计划统计（v5.2.4 新增）"""
        conn = self._get_conn()
        now = time.time()
        total = conn.execute("SELECT COUNT(*) as cnt FROM review_schedules").fetchone()["cnt"]
        pending = conn.execute("SELECT COUNT(*) as cnt FROM review_schedules WHERE status = 'pending'").fetchone()["cnt"]
        due = conn.execute("SELECT COUNT(*) as cnt FROM review_schedules WHERE status = 'pending' AND scheduled_at <= ?",
                           (now,)).fetchone()["cnt"]
        total_reviews = conn.execute("SELECT COALESCE(SUM(review_count), 0) as cnt FROM review_schedules").fetchone()["cnt"]
        return {
            "total_schedules": total,
            "pending": pending,
            "due_now": due,
            "total_reviews_completed": total_reviews,
        }
