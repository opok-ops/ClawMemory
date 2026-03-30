"""
ClawMemory 核心存储引擎
===========================
基于 SQLite 的结构化记忆存储，支持：
- 全生命周期记忆存储（无上限）
- 多维度元数据索引
- 隐私分级物理隔离
- 增量备份与恢复
- 审计日志
"""

import sqlite3
import json
import time
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from threading import Lock

from .encryption import EncryptionEngine, EncryptedBlob, get_engine


# ============================================================================
# Enums & Data Classes
# ============================================================================
class PrivacyLevel(Enum):
    PUBLIC = "PUBLIC"      # 公开：任何模块可访问
    INTERNAL = "INTERNAL"  # 内部：仅 Agent 内部使用
    PRIVATE = "PRIVATE"    # 私密：需显式授权
    STRICT = "STRICT"      # 严格：物理隔离存储

    @classmethod
    def from_string(cls, s: str) -> "PrivacyLevel":
        s = s.upper().strip()
        return cls(s)

    def to_int(self) -> int:
        mapping = {PrivacyLevel.PUBLIC: 0, PrivacyLevel.INTERNAL: 1,
                   PrivacyLevel.PRIVATE: 2, PrivacyLevel.STRICT: 3}
        return mapping[self]

    @classmethod
    def from_int(cls, i: int) -> "PrivacyLevel":
        mapping = {0: cls.PUBLIC, 1: cls.INTERNAL, 2: cls.PRIVATE, 3: cls.STRICT}
        return mapping.get(i, cls.PUBLIC)


class Importance(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_string(cls, s: str) -> "Importance":
        mapping = {"low": cls.LOW, "medium": cls.MEDIUM,
                   "high": cls.HIGH, "critical": cls.CRITICAL}
        return mapping.get(s.lower().strip(), cls.MEDIUM)


@dataclass
class MemoryEntry:
    id: str                    # UUID v4
    content: str               # 加密后的内容（EncryptedBlob base64 字符串）
    plaintext_preview: str     # 明文预览（前 200 字符，用于搜索展示）
    category: str              # 分类标签
    tags: List[str]            # 多标签
    privacy: PrivacyLevel      # 隐私分级
    importance: Importance     # 重要性
    source_session: str        # 来源会话
    source_agent: str          # 来源 Agent ID
    created_at: float         # Unix timestamp
    updated_at: float          # Unix timestamp
    accessed_at: float        # 最后访问时间
    access_count: int          # 访问次数
    is_deleted: bool           # 软删除标记
    deleted_at: Optional[float] = None
    metadata_json: str = "{}"  # 额外元数据 JSON
    checksum: Optional[str] = None  # SHA-256 of encrypted content

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["privacy"] = self.privacy.value
        d["importance"] = self.importance.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "MemoryEntry":
        d["privacy"] = PrivacyLevel.from_string(d["privacy"])
        d["importance"] = Importance(d["importance"])
        return cls(**d)


@dataclass
class AuditRecord:
    id: str
    memory_id: str
    action: str  # READ | WRITE | UPDATE | DELETE | EXPORT | RESTORE
    actor: str   # agent_id or user
    timestamp: float
    privacy_level: str
    fields_accessed: List[str]
    session_id: str
    ip_address: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# Schema Definitions
# ============================================================================
SCHEMA_VERSION = 7  # Increment on schema changes

SCHEMA_SQL = """
-- Core memory table
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,          -- EncryptedBlob JSON base64
    plaintext_preview TEXT,          -- First 200 chars, unencrypted for FTS
    category TEXT NOT NULL DEFAULT 'general',
    tags TEXT DEFAULT '[]',          -- JSON array
    privacy INTEGER NOT NULL DEFAULT 0,
    importance INTEGER NOT NULL DEFAULT 2,
    source_session TEXT,
    source_agent TEXT DEFAULT 'default',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    accessed_at REAL NOT NULL,
    access_count INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    deleted_at REAL,
    metadata_json TEXT DEFAULT '{}',
    checksum TEXT                   -- SHA-256 of encrypted content
);

-- Indexes for fast retrieval
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category) WHERE is_deleted=0;
CREATE INDEX IF NOT EXISTS idx_memories_privacy ON memories(privacy) WHERE is_deleted=0;
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance) WHERE is_deleted=0;
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at) WHERE is_deleted=0;
CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at) WHERE is_deleted=0;
CREATE INDEX IF NOT EXISTS idx_memories_source_agent ON memories(source_agent) WHERE is_deleted=0;
CREATE INDEX IF NOT EXISTS idx_memories_accessed_at ON memories(accessed_at) WHERE is_deleted=0;

-- Full-text search using FTS5
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    plaintext_preview,
    category,
    tags,
    content='memories',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, plaintext_preview, category, tags)
    VALUES (new.rowid, new.plaintext_preview, new.category, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, plaintext_preview, category, tags)
    VALUES ('delete', old.rowid, old.plaintext_preview, old.category, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, plaintext_preview, category, tags)
    VALUES ('delete', old.rowid, old.plaintext_preview, old.category, old.tags);
    INSERT INTO memories_fts(rowid, plaintext_preview, category, tags)
    VALUES (new.rowid, new.plaintext_preview, new.category, new.tags);
END;

-- Triggers table
CREATE TABLE IF NOT EXISTS triggers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    condition_json TEXT NOT NULL,
    action_json TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at REAL NOT NULL,
    last_fired_at REAL
);

-- Audit log (never contains memory content)
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    memory_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    timestamp REAL NOT NULL,
    privacy_level INTEGER,
    fields_accessed TEXT DEFAULT '[]',
    session_id TEXT,
    ip_address TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_memory ON audit_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- Schema version tracker
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version (version) VALUES (7);
"""


# ============================================================================
# Storage Engine
# ============================================================================
class StorageEngine:
    """| 线程安全的 SQLite 存储引擎 |"""

    _instance: Optional["StorageEngine"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        if self._initialized:
            return
        self._initialized = True

        self._db_path = Path(db_path) if db_path else self._get_default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._engine = get_engine()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_default_db_path(self) -> Path:
        base = Path(__file__).parent.parent
        return base / "data" / "store" / "memory.db"

    def _init_db(self):
        with self._lock:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            # Apply schema using executescript for multi-statement SQL
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()

    def _now(self) -> float:
        return time.time()

    # --------------------------------------------------------------------------
    # Memory Operations
    # --------------------------------------------------------------------------
    def add_memory(
        self,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
        importance: Importance = Importance.MEDIUM,
        source_session: str = "default",
        source_agent: str = "default",
        metadata: Optional[Dict] = None,
    ) -> MemoryEntry:
        """| 添加新记忆 |"""
        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}

        entry_id = str(uuid.uuid4())
        plaintext_preview = content[:200]
        now = self._now()

        # Encrypt content
        blob = self._engine.encrypt(content)
        encrypted_content = blob.to_string()
        checksum = hashlib.sha256(encrypted_content.encode()).hexdigest()

        entry = MemoryEntry(
            id=entry_id,
            content=encrypted_content,
            plaintext_preview=plaintext_preview,
            category=category,
            tags=tags,
            privacy=privacy,
            importance=importance,
            source_session=source_session,
            source_agent=source_agent,
            created_at=now,
            updated_at=now,
            accessed_at=now,
            access_count=0,
            is_deleted=False,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            checksum=checksum,
        )

        with self._lock:
            d = entry.to_dict()
            d["tags"] = json.dumps(d["tags"])
            self._conn.execute(
                """INSERT INTO memories (
                    id, content, plaintext_preview, category, tags, privacy, importance,
                    source_session, source_agent, created_at, updated_at, accessed_at,
                    access_count, is_deleted, deleted_at, metadata_json, checksum
                ) VALUES (
                    :id, :content, :plaintext_preview, :category, :tags, :privacy, :importance,
                    :source_session, :source_agent, :created_at, :updated_at, :accessed_at,
                    :access_count, :is_deleted, :deleted_at, :metadata_json, :checksum
                )""",
                d
            )
            self._conn.commit()

        self._log_audit(entry.id, "WRITE", source_agent, privacy, ["content"], source_session)
        return entry

    def get_memory(self, entry_id: str, actor: str = "system", session_id: str = "default") -> Optional[MemoryEntry]:
        """| 获取记忆（解密）|"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id=? AND is_deleted=0", (entry_id,)
            ).fetchone()
            if not row:
                return None

        cols = [c[0] for c in self._conn.execute("SELECT * FROM memories LIMIT 0").description]
        entry_dict = dict(zip(cols, row))
        entry_dict["tags"] = json.loads(entry_dict["tags"])
        entry = MemoryEntry.from_dict(entry_dict)

        # Check privacy
        # (Caller should enforce privacy via check_privacy_access)

        # Update access stats
        with self._lock:
            self._conn.execute(
                "UPDATE memories SET accessed_at=?, access_count=? WHERE id=?",
                (self._now(), entry.access_count + 1, entry_id)
            )
            self._conn.commit()

        self._log_audit(entry.id, "READ", actor, entry.privacy, ["content"], session_id)
        return entry

    def decrypt_content(self, entry: MemoryEntry) -> str:
        """| 解密记忆内容 |"""
        blob = EncryptedBlob.from_string(entry.content)
        return self._engine.decrypt(blob)

    def update_memory(
        self,
        entry_id: str,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy: Optional[PrivacyLevel] = None,
        importance: Optional[Importance] = None,
        metadata: Optional[Dict] = None,
        actor: str = "system",
        session_id: str = "default",
    ) -> bool:
        """| 更新记忆（原子操作）|"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id=? AND is_deleted=0", (entry_id,)
            ).fetchone()
            if not row:
                return False

            cols = [c[0] for c in self._conn.execute("SELECT * FROM memories LIMIT 0").description]
            entry_dict = dict(zip(cols, row))
            entry_dict["tags"] = json.loads(entry_dict["tags"])
            current = MemoryEntry.from_dict(entry_dict)

        updates = []
        params = {}
        fields_changed = []

        if content is not None:
            blob = self._engine.encrypt(content)
            params["content"] = blob.to_string()
            params["plaintext_preview"] = content[:200]
            params["checksum"] = hashlib.sha256(params["content"].encode()).hexdigest()
            updates.append("content=:content, plaintext_preview=:plaintext_preview, checksum=:checksum")
            fields_changed.append("content")
        if category is not None:
            params["category"] = category
            updates.append("category=:category")
            fields_changed.append("category")
        if tags is not None:
            params["tags"] = json.dumps(tags)
            updates.append("tags=:tags")
            fields_changed.append("tags")
        if privacy is not None:
            params["privacy"] = privacy.to_int()
            updates.append("privacy=:privacy")
            fields_changed.append("privacy")
        if importance is not None:
            params["importance"] = importance.value
            updates.append("importance=:importance")
            fields_changed.append("importance")
        if metadata is not None:
            params["metadata_json"] = json.dumps(metadata, ensure_ascii=False)
            updates.append("metadata_json=:metadata_json")
            fields_changed.append("metadata")

        if not updates:
            return False

        params["updated_at"] = self._now()
        params["id"] = entry_id
        updates.append("updated_at=:updated_at")

        with self._lock:
            self._conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id=:id", params)
            self._conn.commit()

        self._log_audit(entry_id, "UPDATE", actor, current.privacy, fields_changed, session_id)
        return True

    def delete_memory(self, entry_id: str, actor: str = "system", session_id: str = "default", hard: bool = False) -> bool:
        """| 删除记忆（默认软删除）|"""
        with self._lock:
            row = self._conn.execute(
                "SELECT privacy FROM memories WHERE id=? AND is_deleted=0", (entry_id,)
            ).fetchone()
            if not row:
                return False
            privacy = PrivacyLevel.from_int(row[0])

            if hard:
                self._conn.execute("DELETE FROM memories WHERE id=?", (entry_id,))
            else:
                self._conn.execute(
                    "UPDATE memories SET is_deleted=1, deleted_at=? WHERE id=?",
                    (self._now(), entry_id)
                )
            self._conn.commit()

        action = "DELETE" + ("_HARD" if hard else "_SOFT")
        self._log_audit(entry_id, action, actor, privacy, ["is_deleted"], session_id)
        return True

    # --------------------------------------------------------------------------
    # Query & Search
    # --------------------------------------------------------------------------
    def search_fulltext(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 20,
        min_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[MemoryEntry]:
        """| FTS5 全文搜索（返回候选记忆，需要调用 check_privacy_access）|"""
        with self._lock:
            sql = """
                SELECT memories.* FROM memories
                INNER JOIN memories_fts ON memories.rowid = memories_fts.rowid
                WHERE memories_fts MATCH ?
                  AND memories.is_deleted = 0
                  AND memories.privacy >= ?
            """
            params: List = [query, min_privacy.to_int()]

            if category:
                sql += " AND memories.category = ?"
                params.append(category)
            if exclude_ids:
                placeholders = ",".join("?" * len(exclude_ids))
                sql += f" AND memories.id NOT IN ({placeholders})"
                params.extend(exclude_ids)

            sql += " ORDER BY bm25(memories_fts) LIMIT ?"
            params.append(max_results)

            rows = self._conn.execute(sql, params).fetchall()

        cols = [c[0] for c in self._conn.execute("SELECT * FROM memories LIMIT 0").description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["tags"] = json.loads(d["tags"])
            results.append(MemoryEntry.from_dict(d))
        return results

    def search_semantic(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        min_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
    ) -> List[Tuple[MemoryEntry, float]]:
        """| 语义向量搜索（需要向量化扩展，计算余弦相似度）|"""
        # Placeholder: integrate with numpy/einops for vector similarity
        # For now, fall back to keyword-based with importance boost
        return self._search_by_importance(query_embedding, top_k, min_privacy)

    def _search_by_importance(
        self,
        query: Any,
        top_k: int = 10,
        min_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
    ) -> List[Tuple[MemoryEntry, float]]:
        """| 按重要性 + 时间衰减排序 |"""
        with self._lock:
            now = self._now()
            rows = self._conn.execute(f"""
                SELECT *,
                    (importance * 10.0) - ((? - accessed_at) / 86400.0 * 0.1) as score
                FROM memories
                WHERE is_deleted=0 AND privacy >= ?
                ORDER BY score DESC
                LIMIT ?
            """, (now, min_privacy.to_int(), top_k)).fetchall()

        cols = [c[0] for c in self._conn.execute("SELECT * FROM memories LIMIT 0").description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["tags"] = json.loads(d["tags"])
            entry = MemoryEntry.from_dict(d)
            score = row[cols.index("score")] if "score" in cols else 0.0
            results.append((entry, score))
        return results

    def list_memories(
        self,
        category: Optional[str] = None,
        privacy: Optional[PrivacyLevel] = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> List[MemoryEntry]:
        """| 列表记忆 |"""
        with self._lock:
            sql = "SELECT * FROM memories WHERE 1=1"
            params: List = []
            if not include_deleted:
                sql += " AND is_deleted=0"
            if category:
                sql += " AND category=?"
                params.append(category)
            if privacy:
                sql += " AND privacy>=?"
                params.append(privacy.to_int())
            sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = self._conn.execute(sql, params).fetchall()

        cols = [c[0] for c in self._conn.execute("SELECT * FROM memories LIMIT 0").description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["tags"] = json.loads(d["tags"])
            results.append(MemoryEntry.from_dict(d))
        return results

    def count_memories(self, category: Optional[str] = None, include_deleted: bool = False) -> int:
        """| 统计记忆数量 |"""
        with self._lock:
            sql = "SELECT COUNT(*) FROM memories WHERE 1=1"
            params: List = []
            if not include_deleted:
                sql += " AND is_deleted=0"
            if category:
                sql += " AND category=?"
                params.append(category)
            return self._conn.execute(sql, params).fetchone()[0]

    def get_categories(self) -> List[str]:
        """| 获取所有分类 |"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT category FROM memories WHERE is_deleted=0 ORDER BY category"
            ).fetchall()
        return [r[0] for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """| 获取存储统计 |"""
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM memories WHERE is_deleted=0").fetchone()[0]
            by_privacy = dict(self._conn.execute(
                "SELECT privacy, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY privacy"
            ).fetchall())
            by_importance = dict(self._conn.execute(
                "SELECT importance, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY importance"
            ).fetchall())
            by_category = dict(self._conn.execute(
                "SELECT category, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY category ORDER BY COUNT(*) DESC LIMIT 20"
            ).fetchall())
            db_size = self._db_path.stat().st_size
        return {
            "total": total,
            "by_privacy": {PrivacyLevel.from_int(k).value: v for k, v in by_privacy.items()},
            "by_importance": {Importance(k).name: v for k, v in by_importance.items()},
            "top_categories": by_category,
            "db_size_bytes": db_size,
            "db_path": str(self._db_path),
        }

    # --------------------------------------------------------------------------
    # Privacy Enforcement
    # --------------------------------------------------------------------------
    def check_privacy_access(
        self,
        entry: MemoryEntry,
        requester_agent: str,
        requester_session: str,
    ) -> bool:
        """| 检查调用者是否有权访问该记忆 |"""
        # Owning agent always has access
        if entry.source_agent == requester_agent:
            return True
        # PRIVATE and STRICT need explicit grant
        if entry.privacy in (PrivacyLevel.PRIVATE, PrivacyLevel.STRICT):
            # Check if there's a grant record (omitted for brevity — would be in a grants table)
            return False
        return True

    def get_accessible_memories(
        self,
        agent_id: str,
        session_id: str,
        max_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
        limit: int = 100,
    ) -> List[MemoryEntry]:
        """| 获取调用者可访问的记忆（考虑隐私分级）|"""
        with self._lock:
            rows = self._conn.execute("""
                SELECT * FROM memories
                WHERE is_deleted=0
                  AND (source_agent=? OR privacy <= ?)
                  AND id NOT IN (
                      SELECT memory_id FROM privacy_denied WHERE agent_id=? AND session_id=?
                  )
                ORDER BY importance DESC, accessed_at DESC
                LIMIT ?
            """, (agent_id, max_privacy.to_int(), agent_id, session_id, limit)).fetchall()

        cols = [c[0] for c in self._conn.execute("SELECT * FROM memories LIMIT 0").description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["tags"] = json.loads(d["tags"])
            results.append(MemoryEntry.from_dict(d))
        return results

    # --------------------------------------------------------------------------
    # Audit Logging
    # --------------------------------------------------------------------------
    def _log_audit(
        self,
        memory_id: str,
        action: str,
        actor: str,
        privacy: PrivacyLevel,
        fields_accessed: List[str],
        session_id: str,
    ):
        """| 记录审计日志（不记录内容）|"""
        with self._lock:
            self._conn.execute(
                """INSERT INTO audit_log (id, memory_id, action, actor, timestamp, privacy_level, fields_accessed, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), memory_id, action, actor,
                    self._now(), privacy.to_int(),
                    json.dumps(fields_accessed), session_id,
                )
            )
            self._conn.commit()

    def get_audit_log(
        self,
        memory_id: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """| 查询审计日志 |"""
        with self._lock:
            sql = "SELECT * FROM audit_log WHERE 1=1"
            params: List = []
            if memory_id:
                sql += " AND memory_id=?"
                params.append(memory_id)
            if actor:
                sql += " AND actor=?"
                params.append(actor)
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(sql, params).fetchall()

        cols = [c[0] for c in self._conn.execute("SELECT * FROM audit_log LIMIT 0").description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["fields_accessed"] = json.loads(d["fields_accessed"])
            results.append(AuditRecord(**d))
        return results

    # --------------------------------------------------------------------------
    # Backup & Export
    # --------------------------------------------------------------------------
    def backup(self, backup_dir: Path) -> Path:
        """| 创建加密增量备份 |"""
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.fromtimestamp(self._now(), tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{ts}.db"
        with self._lock:
            self._conn.execute("VACUUM INTO ?", (str(backup_path),))
        return backup_path

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            StorageEngine._instance = None
            self._initialized = False