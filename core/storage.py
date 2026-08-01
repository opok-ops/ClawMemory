"""
MindForge v5.2.9 存储引擎
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


# ===== 路径安全校验（v5.2.9 新增：存储层统一防护）=====

def _safe_path(path_str, must_exist=False, allow_symlinks=False,
               max_size=None, allowed_exts=None, max_len=4096):
    """校验文件路径安全性，防止路径遍历攻击"""
    if not path_str or not isinstance(path_str, str):
        raise ValueError("路径不能为空")
    if len(path_str) > max_len:
        raise ValueError(f"路径过长（上限 {max_len} 字符）")

    target = Path(path_str)
    if not target.is_absolute():
        target = Path.cwd() / target

    try:
        resolved = target.resolve()
    except (OSError, RuntimeError) as e:
        raise ValueError(f"路径解析失败: {e}")

    if not allow_symlinks:
        check_path = resolved
        while check_path != check_path.parent:
            if check_path.is_symlink():
                raise ValueError(f"不允许操作符号链接: {check_path}")
            check_path = check_path.parent

    if allowed_exts is not None:
        ext = resolved.suffix.lower()
        if ext not in allowed_exts:
            raise ValueError(
                f"不支持的文件类型: {ext}（允许: {', '.join(sorted(allowed_exts))}）"
            )

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"文件不存在: {resolved}")

    if max_size is not None and resolved.exists() and resolved.is_file():
        size = resolved.stat().st_size
        if size > max_size:
            raise ValueError(f"文件过大: {size} 字节（上限 {max_size}）")

    return resolved


# v5.3.3 安全加固：LIKE 通配符转义，防止 % 和 _ 被解释为 SQL LIKE 通配符
def _escape_like(value: str) -> str:
    """转义 LIKE 模式中的通配符 % 和 _，防止通配符注入"""
    if not isinstance(value, str):
        return ""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# v5.3.3 安全加固：HTML/XSS 消毒，防止存储型 XSS 攻击
_XSS_RE = __import__("re").compile(
    r'<[^>]*>|javascript:|on\w+\s*=|<script|</script|<iframe|</iframe|<object|<embed',
    __import__("re").IGNORECASE
)

def _sanitize_html(value: str, max_len: int = 10000) -> str:
    """清洗 HTML 内容，防止存储型 XSS

    移除 HTML 标签和危险的事件处理器属性。
    """
    if not isinstance(value, str):
        return ""
    if len(value) > max_len:
        value = value[:max_len]
    # 移除 HTML 标签和危险内容
    cleaned = _XSS_RE.sub("", value)
    return cleaned


# v5.3.3 安全加固：敏感操作频率限制器
class _RateLimiter:
    """简单的内存频率限制器，防止暴力攻击"""

    def __init__(self):
        self._windows: Dict[str, List[float]] = {}

    def check(self, key: str, max_calls: int = 10, window_seconds: int = 60) -> bool:
        """检查是否超过频率限制

        Args:
            key: 限制键（如 agent_id + operation）
            max_calls: 窗口内最大调用次数
            window_seconds: 时间窗口（秒）

        Returns:
            True=允许，False=超限
        """
        now = time.time()
        if key not in self._windows:
            self._windows[key] = []

        # 清理过期记录
        self._windows[key] = [t for t in self._windows[key] if now - t < window_seconds]

        if len(self._windows[key]) >= max_calls:
            return False

        self._windows[key].append(now)
        return True


_rate_limiter = _RateLimiter()


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
    pinned: bool = False
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
            "pinned": self.pinned,
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
                pinned INTEGER DEFAULT 0,
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
            CREATE INDEX IF NOT EXISTS idx_pinned ON memories(pinned);

            -- 记忆关联（v5.2.5 新增）
            CREATE TABLE IF NOT EXISTS memory_links (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                link_type TEXT DEFAULT 'related',
                note TEXT DEFAULT '',
                created_at REAL,
                UNIQUE(source_id, target_id)
            );
            CREATE INDEX IF NOT EXISTS idx_link_source ON memory_links(source_id);
            CREATE INDEX IF NOT EXISTS idx_link_target ON memory_links(target_id);
            CREATE INDEX IF NOT EXISTS idx_link_type ON memory_links(link_type);

            -- 记忆版本历史（v5.2.7 新增）
            CREATE TABLE IF NOT EXISTS memory_versions (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                importance TEXT,
                actor TEXT DEFAULT '',
                changed_at REAL,
                FOREIGN KEY (memory_id) REFERENCES memories(id),
                UNIQUE(memory_id, version_number)
            );
            CREATE INDEX IF NOT EXISTS idx_versions_memory_id ON memory_versions(memory_id);
            CREATE INDEX IF NOT EXISTS idx_versions_changed_at ON memory_versions(changed_at);

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
        # v5.3.0 安全加固：内容长度上限防 DoS
        MAX_CONTENT_LEN = 50000
        if content and isinstance(content, str) and len(content) > MAX_CONTENT_LEN:
            content = content[:MAX_CONTENT_LEN]
        if category and isinstance(category, str) and len(category) > 128:
            category = category[:128]
        if source_agent and isinstance(source_agent, str) and len(source_agent) > 128:
            source_agent = source_agent[:128]

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

    def get_indexable_documents(self, limit: int = 100000) -> Dict[str, str]:
        """返回可索引的 {memory_id: content} 映射（v5.2.8 新增）

        用于 IndexEngine 在新进程启动时水合 TF-IDF 内存索引，
        修复 CLI 跨进程搜索不到历史记忆的问题。
        跳过回收站与加密条目（密文无法直接索引）。

        Args:
            limit: 最大加载条数（安全上限）

        Returns:
            {memory_id: content} 字典
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, content FROM memories"
            " WHERE category != 'trash' AND encrypted = 0"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return {row["id"]: (row["content"] or "") for row in rows}

    def list_memories(self,
                      category: Optional[str] = None,
                      layer: Optional[MemoryLayer] = None,
                      privacy: Optional[PrivacyLevel] = None,
                      starred: Optional[bool] = None,
                      pinned: Optional[bool] = None,
                      created_after: Optional[float] = None,
                      created_before: Optional[float] = None,
                      limit: int = 50,
                      offset: int = 0,
                      sort_by: str = "created_at",
                      sort_order: str = "desc") -> List[MemoryEntry]:
        """列出记忆（v5.2.5 新增 pinned 筛选和置顶优先排序）"""
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
        if pinned is not None:
            query += " AND pinned = ?"
            params.append(1 if pinned else 0)
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

        # v5.2.5: 置顶记忆优先展示
        query += f" ORDER BY pinned DESC, {sort_by} {sort_order} LIMIT ? OFFSET ?"
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
                      pinned: Optional[bool] = None,
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
        if pinned is not None:
            updates.append("pinned = ?")
            params.append(1 if pinned else 0)
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

        # v5.2.7: 更新前读取旧内容，用于保存历史版本
        old_entry = None
        if content is not None:
            old_row = conn.execute(
                "SELECT content, category, tags, importance FROM memories WHERE id = ?",
                (entry_id,)
            ).fetchone()
            if old_row:
                old_entry = {
                    "content": old_row[0] or "",
                    "category": old_row[1] or "",
                    "tags": old_row[2],
                    "importance": old_row[3] or "",
                }

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

        # v5.2.7: 保存历史版本（仅当 content 变更时）
        if content is not None and old_entry:
            try:
                old_tags = old_entry.get("tags", "")
                if isinstance(old_tags, str) and old_tags.startswith("["):
                    try:
                        old_tags = json.loads(old_tags)
                    except Exception:
                        pass
                self.save_version(
                    memory_id=entry_id,
                    content=old_entry.get("content", ""),
                    category=old_entry.get("category", ""),
                    tags=old_tags,
                    importance=old_entry.get("importance", ""),
                    actor=actor,
                )
            except Exception:
                pass  # 版本保存失败不影响主流程

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
        # v5.3.3 安全加固：LIKE 通配符转义
        safe_tag = tag[:128] if isinstance(tag, str) else ""
        query = "SELECT * FROM memories WHERE tags LIKE ? ESCAPE '\\'"
        params = [f'%"{_escape_like(safe_tag)}"%']

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
        import html as _html

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
            f"- 筛选条件：分类={_html.escape(str(category)) if category else '全部'}, 层级={layer.value if layer else '全部'}, 仅收藏={'是' if starred_only else '否'}",
            "",
            "---",
            "",
        ]

        # 按分类分组
        groups: Dict[str, List[MemoryEntry]] = {}
        for e in entries:
            groups.setdefault(e.category, []).append(e)

        for cat in sorted(groups.keys()):
            lines.append(f"## 📂 {_html.escape(str(cat))}")
            lines.append("")
            for e in groups[cat]:
                star = "⭐ " if e.starred else ""
                lines.append(f"### {star}{_html.escape(str(e.preview[:60]))}")
                lines.append("")
                lines.append(f"- **ID**: `{_html.escape(str(e.id))}`")
                lines.append(f"- **层级**: {e.layer.value}")
                lines.append(f"- **隐私**: {e.privacy.value}")
                lines.append(f"- **重要性**: {e.importance.value}")
                lines.append(f"- **类型**: {e.memory_type.value}")
                lines.append(f"- **标签**: {', '.join(f'#{_html.escape(str(t))}' for t in e.tags) if e.tags else '无'}")
                lines.append(f"- **创建**: {_fmt_time(e.created_at)}")
                lines.append(f"- **访问**: {e.access_count} 次")
                lines.append("")
                lines.append("**内容**：")
                lines.append("")
                lines.append(_html.escape(str(e.content)))
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
        """记忆质量评分（v5.2.2 新增）"""
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

    # ===== Agent 记忆增强（v5.2.9 新增）=====

    def rank_agents(self,
                    by: str = "count",
                    limit: int = 20) -> List[Dict[str, Any]]:
        """Agent 排行榜（v5.2.9 新增）

        Args:
            by: 排序维度（count / last_active / avg_importance / starred）
            limit: 返回数量

        Returns:
            Agent 排名列表
        """
        conn = self._get_conn()
        # v5.2.9 安全加固：by 白名单枚举校验
        _ALLOWED = {"count", "last_active", "avg_importance", "starred"}
        if by not in _ALLOWED:
            by = "count"

        imp_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "TRIVIAL": 0}

        rows = conn.execute(
            "SELECT source_agent, COUNT(*) as cnt, MAX(created_at) as last_active, "
            "SUM(starred) as starred_cnt FROM memories "
            "WHERE source_agent != '' GROUP BY source_agent"
        ).fetchall()

        result = []
        for r in rows:
            agent = r[0]
            count = r[1]
            last_active = r[2] or 0
            starred_cnt = r[3] or 0
            avg_imp = 0.0
            if count > 0:
                imps = conn.execute(
                    "SELECT importance FROM memories WHERE source_agent = ?", (agent,)
                ).fetchall()
                total_imp = sum(imp_weights.get(str(i[0]), 2) for i in imps)
                avg_imp = total_imp / count

            result.append({
                "agent_id": agent,
                "count": count,
                "last_active": last_active,
                "starred_count": starred_cnt,
                "avg_importance": round(avg_imp, 2),
            })

        sort_map = {
            "count": lambda x: -x["count"],
            "last_active": lambda x: -x["last_active"],
            "avg_importance": lambda x: -x["avg_importance"],
            "starred": lambda x: -x["starred_count"],
        }
        result.sort(key=sort_map[by])
        return result[:limit]

    def forget_agent_memories(self,
                              agent_id: str,
                              min_quality_score: int = 30,
                              older_than_days: int = 30,
                              dry_run: bool = False,
                              actor: str = "cli",
                              session_id: str = "forget") -> Dict[str, Any]:
        """遗忘 Agent 低质量旧记忆（v5.2.9 新增）

        Args:
            agent_id: 目标 Agent ID
            min_quality_score: 低于此质量分数的记忆才会被清理
            older_than_days: 只清理超过此天数未更新的记忆
            dry_run: 仅预览
            actor: 操作者
            session_id: 会话 ID

        Returns:
            {evaluated, selected, cleaned}
        """
        conn = self._get_conn()
        # v5.2.9 安全加固：数值边界
        min_quality_score = max(0, min(100, int(min_quality_score)))
        older_than_days = max(0, int(older_than_days))
        if not agent_id or not isinstance(agent_id, str) or len(agent_id) > 128:
            return {"evaluated": 0, "selected": 0, "cleaned": 0,
                    "error": "无效 agent_id"}

        now = time.time()
        cutoff = now - older_than_days * 86400

        mems = conn.execute(
            "SELECT id, source_agent, updated_at FROM memories "
            "WHERE source_agent = ? AND updated_at < ? AND category != 'trash'",
            (agent_id[:128], cutoff)
        ).fetchall()

        selected_ids = []
        for r in mems:
            mid = r[0]
            qs = self.quality_score(mid)
            if qs and qs["total_score"] < min_quality_score:
                selected_ids.append(mid)

        if not dry_run and selected_ids:
            placeholders = ",".join("?" * len(selected_ids))
            conn.execute(
                f"UPDATE memories SET category='trash', updated_at=? "
                f"WHERE id IN ({placeholders})",
                [now] + selected_ids,
            )
            for mid in selected_ids:
                self._add_audit("agent_forget", mid, actor, session_id, "")
            conn.commit()

        return {
            "agent_id": agent_id,
            "evaluated": len(mems),
            "selected": len(selected_ids),
            "cleaned": 0 if dry_run else len(selected_ids),
            "selected_ids": selected_ids[:20],
        }

    # ===== AI 短剧增强（v5.2.9 新增）=====

    def list_lines_by_scene(self,
                            scene_id: str,
                            limit: int = 500,
                            offset: int = 0) -> List[DramaLine]:
        """按场次列出所有台词（v5.2.9 新增）"""
        conn = self._get_conn()
        # 安全：ID 长度限制
        sid = scene_id[:64] if isinstance(scene_id, str) else ""
        limit = max(1, min(10000, int(limit)))
        offset = max(0, int(offset))
        rows = conn.execute(
            "SELECT * FROM drama_lines WHERE scene_id = ? "
            "ORDER BY COALESCE(episode, 0), COALESCE(created_at, 0) LIMIT ? OFFSET ?",
            (sid, limit, offset),
        ).fetchall()
        return [self._row_to_line(r) for r in rows]

    def list_lines_by_character(self,
                                character_id: str,
                                drama_id: Optional[str] = None,
                                limit: int = 500,
                                offset: int = 0) -> List[DramaLine]:
        """按角色列出所有台词（v5.2.9 新增）"""
        conn = self._get_conn()
        cid = character_id[:64] if isinstance(character_id, str) else ""
        limit = max(1, min(10000, int(limit)))
        offset = max(0, int(offset))

        if drama_id:
            did = drama_id[:64] if isinstance(drama_id, str) else ""
            rows = conn.execute(
                "SELECT * FROM drama_lines WHERE character_id = ? AND drama_id = ? "
                "ORDER BY COALESCE(episode, 0), COALESCE(created_at, 0) LIMIT ? OFFSET ?",
                (cid, did, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM drama_lines WHERE character_id = ? "
                "ORDER BY drama_id, COALESCE(episode, 0), COALESCE(created_at, 0) LIMIT ? OFFSET ?",
                (cid, limit, offset),
            ).fetchall()
        return [self._row_to_line(r) for r in rows]

    def top_rated_dramas(self,
                         genre: Optional[str] = None,
                         min_rating: float = 0.0,
                         limit: int = 50) -> List[DramaSeries]:
        """高分短剧排行榜（v5.2.9 新增，别名 drama-stars）"""
        conn = self._get_conn()
        limit = max(1, min(1000, int(limit)))
        min_rating = max(0.0, min(10.0, float(min_rating)))

        sql = "SELECT * FROM drama_series WHERE rating >= ?"
        params: List[Any] = [min_rating]

        # 枚举白名单校验 genre
        _ALLOWED_GENRES = {g.value for g in DramaGenre}
        if genre:
            g = genre.strip().upper() if isinstance(genre, str) else ""
            if g in _ALLOWED_GENRES:
                sql += " AND genre = ?"
                params.append(g)

        sql += " ORDER BY rating DESC, current_episode DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_drama(r) for r in rows]

    def import_dramas_from_json(self,
                                input_path: str,
                                skip_existing: bool = True) -> Dict[str, int]:
        """从 JSON 文件批量导入短剧（v5.2.9 新增）

        导入结构与 export_dramas 相同，包含：dramas[], scenes[], characters[], lines[]。

        Args:
            input_path: JSON 文件路径（已在核心层外部做路径校验更好，此处也再校验一次）
            skip_existing: 跳过已存在的短剧（按 title 匹配）

        Returns:
            {dramas, scenes, characters, lines, skipped, failed}
        """
        # v5.2.9 安全加固：路径二次校验
        safe_path = _safe_path(input_path, must_exist=True,
                               allowed_exts={".json"}, max_size=500 * 1024 * 1024)

        import json
        with open(str(safe_path), "r", encoding="utf-8") as f:
            data = json.load(f)

        stats = {"dramas": 0, "scenes": 0, "characters": 0, "lines": 0,
                 "skipped": 0, "failed": 0}

        conn = self._get_conn()
        dramas_raw = data.get("dramas", [])
        if len(dramas_raw) > 1000:
            dramas_raw = dramas_raw[:1000]

        for drama_data in dramas_raw:
            try:
                title = str(drama_data.get("title", ""))[:512]
                if not title:
                    stats["failed"] += 1
                    continue

                # skip_existing
                if skip_existing:
                    exists = conn.execute(
                        "SELECT id FROM drama_series WHERE title = ?", (title,)
                    ).fetchone()
                    if exists:
                        stats["skipped"] += 1
                        continue

                # 创建短剧
                genre_str = str(drama_data.get("genre", "OTHER"))[:64]
                try:
                    genre_enum = DramaGenre(genre_str)
                except ValueError:
                    genre_enum = DramaGenre.OTHER

                status_str = str(drama_data.get("status", "PLANNED"))[:64]
                try:
                    status_enum = DramaStatus(status_str)
                except ValueError:
                    status_enum = DramaStatus.PLANNED

                new_drama = self.add_drama(
                    title=title,
                    description=str(drama_data.get("description", ""))[:5000],
                    genre=genre_enum,
                    total_episodes=max(0, int(drama_data.get("total_episodes", 0) or 0)),
                    current_episode=max(0, int(drama_data.get("current_episode", 0) or 0)),
                    rating=max(0.0, min(10.0, float(drama_data.get("rating", 0) or 0))),
                    platform=str(drama_data.get("platform", ""))[:128],
                    cover_url=str(drama_data.get("cover_url", ""))[:512],
                    tags=list(drama_data.get("tags", []) or [])[:64],
                    actors=list(drama_data.get("actors", []) or [])[:128],
                    director=str(drama_data.get("director", ""))[:128],
                    status=status_enum,
                )
                stats["dramas"] += 1
                new_did = new_drama.id

                # 导入场次
                for scene_data in drama_data.get("scenes", [])[:1000]:
                    try:
                        s = self.add_scene(
                            drama_id=new_did,
                            title=str(scene_data.get("title", ""))[:512],
                            description=str(scene_data.get("description", ""))[:5000],
                            episode=max(0, int(scene_data.get("episode", 0) or 0)),
                            location=str(scene_data.get("location", ""))[:256],
                            time_of_day=str(scene_data.get("time_of_day", ""))[:64],
                            notes=str(scene_data.get("notes", ""))[:5000],
                        )
                        stats["scenes"] += 1
                    except Exception:
                        stats["failed"] += 1

                # 导入角色
                for char_data in drama_data.get("characters", [])[:500]:
                    try:
                        c = self.add_character(
                            drama_id=new_did,
                            name=str(char_data.get("name", ""))[:128],
                            actor_name=str(char_data.get("actor_name", ""))[:128],
                            description=str(char_data.get("description", ""))[:5000],
                            role_type=str(char_data.get("role_type", "supporting"))[:64],
                            tags=list(char_data.get("tags", []) or [])[:64],
                        )
                        stats["characters"] += 1
                    except Exception:
                        stats["failed"] += 1

                # 导入台词
                for line_data in drama_data.get("lines", [])[:50000]:
                    try:
                        l = self.add_line(
                            drama_id=new_did,
                            scene_id=str(line_data.get("scene_id", ""))[:64],
                            character_id=str(line_data.get("character_id", ""))[:64],
                            line_text=str(line_data.get("line_text", ""))[:5000],
                            character_name=str(line_data.get("character_name", ""))[:128],
                            context=str(line_data.get("context", ""))[:5000],
                            episode=max(0, int(line_data.get("episode", 0) or 0)),
                            timestamp=str(line_data.get("timestamp", ""))[:32],
                            is_classic=bool(line_data.get("is_classic", False)),
                            tags=list(line_data.get("tags", []) or [])[:64],
                        )
                        stats["lines"] += 1
                    except Exception:
                        stats["failed"] += 1

            except Exception:
                stats["failed"] += 1

        return stats

    # ===== Agent 记忆增强（v5.3.0 新增）=====

    def agent_profile(self, agent_id: str) -> Dict[str, Any]:
        """Agent 记忆画像（v5.3.0 新增）

        聚合分析指定 Agent 的记忆全景：总量/质量分布/层级分布/分类分布/
        活跃时间线/知识领域（标签 Top-N）/收藏与置顶统计。

        Args:
            agent_id: Agent ID

        Returns:
            画像字典
        """
        # v5.3.0 安全加固：ID 长度限制
        if not agent_id or not isinstance(agent_id, str) or len(agent_id) > 128:
            return {"error": "无效 agent_id"}

        conn = self._get_conn()
        aid = agent_id[:128]

        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE source_agent = ?", (aid,)
        ).fetchone()[0]

        if total == 0:
            return {"agent_id": aid, "total_memories": 0, "message": "该 Agent 暂无记忆"}

        # 层级分布
        layers = conn.execute(
            "SELECT layer, COUNT(*) as cnt FROM memories WHERE source_agent = ? GROUP BY layer",
            (aid,)
        ).fetchall()

        # 分类分布 Top-10
        cats = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM memories WHERE source_agent = ? "
            "GROUP BY category ORDER BY cnt DESC LIMIT 10",
            (aid,)
        ).fetchall()

        # 重要度分布
        imps = conn.execute(
            "SELECT importance, COUNT(*) as cnt FROM memories WHERE source_agent = ? GROUP BY importance",
            (aid,)
        ).fetchall()

        # 收藏/置顶统计
        starred = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE source_agent = ? AND starred = 1", (aid,)
        ).fetchone()[0]
        pinned = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE source_agent = ? AND pinned = 1", (aid,)
        ).fetchone()[0]

        # 标签 Top-10（知识领域）
        tag_rows = conn.execute(
            "SELECT tags FROM memories WHERE source_agent = ? AND tags != ''", (aid,)
        ).fetchall()
        tag_counter: Dict[str, int] = {}
        for r in tag_rows:
            for t in self._safe_json_loads(r[0], []):
                t = str(t)[:64]
                tag_counter[t] = tag_counter.get(t, 0) + 1
        top_tags = sorted(tag_counter.items(), key=lambda x: -x[1])[:10]

        # 活跃时间线（按天聚合，最近 30 天）
        now = time.time()
        cutoff = now - 30 * 86400
        timeline = conn.execute(
            "SELECT created_at FROM memories WHERE source_agent = ? AND created_at >= ?",
            (aid, cutoff)
        ).fetchall()
        daily: Dict[str, int] = {}
        for r in timeline:
            ts = r[0] or 0
            day = time.strftime("%Y-%m-%d", time.localtime(ts))
            daily[day] = daily.get(day, 0) + 1

        # 质量分布（采样最多 200 条，避免大 Agent 性能问题）
        sample_ids = conn.execute(
            "SELECT id FROM memories WHERE source_agent = ? LIMIT 200", (aid,)
        ).fetchall()
        quality_dist = {"优秀": 0, "良好": 0, "中等": 0, "及格": 0, "需改进": 0}
        for r in sample_ids:
            qs = self.quality_score(r[0])
            if qs:
                quality_dist[qs["grade"]] = quality_dist.get(qs["grade"], 0) + 1

        last_active = conn.execute(
            "SELECT MAX(created_at) FROM memories WHERE source_agent = ?", (aid,)
        ).fetchone()[0] or 0
        first_active = conn.execute(
            "SELECT MIN(created_at) FROM memories WHERE source_agent = ?", (aid,)
        ).fetchone()[0] or 0

        return {
            "agent_id": aid,
            "total_memories": total,
            "first_active": first_active,
            "last_active": last_active,
            "by_layer": {r[0]: r[1] for r in layers},
            "by_category": {r[0]: r[1] for r in cats},
            "by_importance": {r[0]: r[1] for r in imps},
            "starred_count": starred,
            "pinned_count": pinned,
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "activity_timeline_30d": daily,
            "quality_distribution_sample": quality_dist,
            "quality_sample_size": len(sample_ids),
        }

    def merge_agent_memories(self,
                             from_agent: str,
                             to_agent: str,
                             dedup: str = "exact",
                             dry_run: bool = False,
                             actor: str = "cli",
                             session_id: str = "merge") -> Dict[str, Any]:
        """合并两个 Agent 的记忆（v5.3.0 新增）

        将 from_agent 的记忆迁移到 to_agent，支持去重：
        - exact: 内容完全相同则跳过
        - none: 不去重，全部迁移

        Args:
            from_agent: 源 Agent ID
            to_agent: 目标 Agent ID
            dedup: 去重模式（exact / none）
            dry_run: 仅预览
            actor: 操作者
            session_id: 会话 ID

        Returns:
            {evaluated, migrated, skipped_duplicates, failed}
        """
        # v5.3.0 安全加固
        if not from_agent or not isinstance(from_agent, str) or len(from_agent) > 128:
            return {"evaluated": 0, "migrated": 0, "error": "无效 from_agent"}
        if not to_agent or not isinstance(to_agent, str) or len(to_agent) > 128:
            return {"evaluated": 0, "migrated": 0, "error": "无效 to_agent"}
        if from_agent == to_agent:
            return {"evaluated": 0, "migrated": 0, "error": "源和目标 Agent 相同"}

        _ALLOWED_DEDUP = {"exact", "none"}
        if dedup not in _ALLOWED_DEDUP:
            dedup = "exact"

        conn = self._get_conn()
        fa = from_agent[:128]
        ta = to_agent[:128]

        src_rows = conn.execute(
            "SELECT id, content FROM memories WHERE source_agent = ?", (fa,)
        ).fetchall()

        # 如果去重，预取目标 Agent 已有内容集合
        existing_contents: set = set()
        if dedup == "exact":
            tgt_rows = conn.execute(
                "SELECT content FROM memories WHERE source_agent = ?", (ta,)
            ).fetchall()
            for r in tgt_rows:
                existing_contents.add(r[0])

        now = time.time()
        migrated = 0
        skipped = 0
        failed = 0

        for r in src_rows:
            mid = r[0]
            content = r[1]
            if dedup == "exact" and content in existing_contents:
                skipped += 1
                continue
            if not dry_run:
                try:
                    conn.execute(
                        "UPDATE memories SET source_agent = ?, updated_at = ? WHERE id = ?",
                        (ta, now, mid)
                    )
                    self._add_audit("agent_merge", mid, actor, session_id,
                                    f"{fa} -> {ta}")
                except Exception:
                    failed += 1
                    continue
            migrated += 1

        if not dry_run and migrated > 0:
            conn.commit()

        return {
            "from_agent": fa,
            "to_agent": ta,
            "dedup": dedup,
            "evaluated": len(src_rows),
            "migrated": migrated,
            "skipped_duplicates": skipped,
            "failed": failed,
        }

    def export_agent_memories(self,
                              agent_id: str,
                              output_path: str,
                              include_audit: bool = False) -> Dict[str, Any]:
        """导出 Agent 全部记忆为独立 JSON 包（v5.3.0 新增）

        Args:
            agent_id: Agent ID
            output_path: 输出 JSON 路径
            include_audit: 是否包含审计日志

        Returns:
            {agent_id, total, file_path}
        """
        # v5.3.0 安全加固
        if not agent_id or not isinstance(agent_id, str) or len(agent_id) > 128:
            return {"error": "无效 agent_id"}

        # 路径校验
        path = _safe_path(output_path, allowed_exts={".json"})

        aid = agent_id[:128]
        entries = self.list_by_agent(agent_id=aid, limit=100000, offset=0)

        export_data: Dict[str, Any] = {
            "version": __version__,
            "export_type": "agent_memories",
            "agent_id": aid,
            "export_time": "",
            "total": len(entries),
            "memories": [],
        }
        from datetime import datetime
        export_data["export_time"] = datetime.now().isoformat()

        for e in entries:
            d = e.to_dict() if hasattr(e, "to_dict") else vars(e)
            export_data["memories"].append(d)

        if include_audit:
            conn = self._get_conn()
            audits = conn.execute(
                "SELECT * FROM audit_log WHERE memory_id IN "
                "(SELECT id FROM memories WHERE source_agent = ?) LIMIT 10000",
                (aid,)
            ).fetchall()
            export_data["audit_logs"] = [dict(r) for r in audits]

        path.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        # v5.3.0 安全加固：权限收紧
        try:
            import stat
            import os
            os.chmod(str(path), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except (OSError, ImportError):
            pass

        return {
            "agent_id": aid,
            "total": len(entries),
            "file_path": str(path),
        }

    # ===== AI 短剧增强（v5.3.0 新增）=====

    def drama_detail_stats(self, drama_id: str) -> Optional[Dict[str, Any]]:
        """短剧深度统计（v5.3.0 新增）

        Args:
            drama_id: 短剧 ID

        Returns:
            包含台词数/角色数/场次数/总字数/经典占比等
        """
        conn = self._get_conn()
        did = drama_id[:64] if isinstance(drama_id, str) else ""
        if not did:
            return None

        drama = self.get_drama(did)
        if not drama:
            return None

        scene_count = conn.execute(
            "SELECT COUNT(*) FROM drama_scenes WHERE drama_id = ?", (did,)
        ).fetchone()[0]
        char_count = conn.execute(
            "SELECT COUNT(*) FROM drama_characters WHERE drama_id = ?", (did,)
        ).fetchone()[0]
        line_count = conn.execute(
            "SELECT COUNT(*) FROM drama_lines WHERE drama_id = ?", (did,)
        ).fetchone()[0]
        classic_count = conn.execute(
            "SELECT COUNT(*) FROM drama_lines WHERE drama_id = ? AND is_classic = 1", (did,)
        ).fetchone()[0]

        # 总字数 & 平均台词长度
        text_info = conn.execute(
            "SELECT SUM(LENGTH(line_text)) as total_chars, "
            "AVG(LENGTH(line_text)) as avg_len FROM drama_lines WHERE drama_id = ?",
            (did,)
        ).fetchone()
        total_chars = text_info[0] or 0
        avg_line_len = round(text_info[1] or 0, 1)

        # 每集台词数分布
        ep_dist = conn.execute(
            "SELECT episode, COUNT(*) as cnt FROM drama_lines "
            "WHERE drama_id = ? GROUP BY episode ORDER BY episode", (did,)
        ).fetchall()

        # 台词最多的角色 Top-5
        top_chars = conn.execute(
            "SELECT character_name, COUNT(*) as cnt FROM drama_lines "
            "WHERE drama_id = ? AND character_name != '' "
            "GROUP BY character_name ORDER BY cnt DESC LIMIT 5", (did,)
        ).fetchall()

        classic_ratio = round(classic_count / line_count * 100, 1) if line_count > 0 else 0.0

        return {
            "drama_id": did,
            "title": drama.title,
            "genre": drama.genre.value if hasattr(drama.genre, "value") else str(drama.genre),
            "status": drama.status.value if hasattr(drama.status, "value") else str(drama.status),
            "rating": drama.rating,
            "total_episodes": drama.total_episodes,
            "current_episode": drama.current_episode,
            "scene_count": scene_count,
            "character_count": char_count,
            "line_count": line_count,
            "classic_line_count": classic_count,
            "classic_ratio": classic_ratio,
            "total_text_chars": total_chars,
            "avg_line_length": avg_line_len,
            "episode_distribution": {str(r[0]): r[1] for r in ep_dist},
            "top_characters_by_lines": [
                {"name": r[0], "line_count": r[1]} for r in top_chars
            ],
        }

    def random_lines(self,
                     drama_id: Optional[str] = None,
                     character_id: Optional[str] = None,
                     is_classic: Optional[bool] = None,
                     count: int = 1) -> List[DramaLine]:
        """随机抽取台词（v5.3.0 新增）

        Args:
            drama_id: 限定短剧
            character_id: 限定角色
            is_classic: 仅经典台词
            count: 抽取数量

        Returns:
            随机台词列表
        """
        conn = self._get_conn()
        count = max(1, min(100, int(count)))

        sql = "SELECT * FROM drama_lines WHERE 1=1"
        params: List[Any] = []

        if drama_id:
            sql += " AND drama_id = ?"
            params.append(drama_id[:64])
        if character_id:
            sql += " AND character_id = ?"
            params.append(character_id[:64])
        if is_classic is not None:
            sql += " AND is_classic = ?"
            params.append(1 if is_classic else 0)

        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(count)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_line(r) for r in rows]

    def character_profile(self,
                          character_id: str,
                          drama_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """角色画像分析（v5.3.0 新增）

        Args:
            character_id: 角色 ID
            drama_id: 限定短剧（可选）

        Returns:
            角色画像：台词数/经典台词数/出场场次/平均台词长度/台词风格
        """
        conn = self._get_conn()
        cid = character_id[:64] if isinstance(character_id, str) else ""
        if not cid:
            return None

        # 查找角色信息
        char = None
        if drama_id:
            did = drama_id[:64]
            chars = conn.execute(
                "SELECT * FROM drama_characters WHERE id = ? AND drama_id = ?",
                (cid, did)
            ).fetchall()
        else:
            chars = conn.execute(
                "SELECT * FROM drama_characters WHERE id = ?", (cid,)
            ).fetchall()

        if chars:
            char = self._row_to_character(chars[0])
        else:
            # 可能角色 ID 不在 characters 表但台词中有记录
            name_row = conn.execute(
                "SELECT character_name FROM drama_lines WHERE character_id = ? LIMIT 1",
                (cid,)
            ).fetchone()
            if not name_row:
                return None

        # 统计台词
        if drama_id:
            did = drama_id[:64]
            line_sql = "SELECT COUNT(*), SUM(is_classic), SUM(LENGTH(line_text)), " \
                       "COUNT(DISTINCT scene_id) FROM drama_lines " \
                       "WHERE character_id = ? AND drama_id = ?"
            line_params = [cid, did]
        else:
            line_sql = "SELECT COUNT(*), SUM(is_classic), SUM(LENGTH(line_text)), " \
                       "COUNT(DISTINCT scene_id) FROM drama_lines " \
                       "WHERE character_id = ?"
            line_params = [cid]

        info = conn.execute(line_sql, line_params).fetchone()
        total_lines = info[0] or 0
        classic_lines = info[1] or 0
        total_chars = info[2] or 0
        scene_count = info[3] or 0

        avg_line_len = round(total_chars / total_lines, 1) if total_lines > 0 else 0.0

        # 出场短剧列表
        dramas = conn.execute(
            "SELECT DISTINCT drama_id FROM drama_lines WHERE character_id = ?", (cid,)
        ).fetchall()

        # 最长台词（代表性台词）
        longest = conn.execute(
            "SELECT line_text FROM drama_lines WHERE character_id = ? "
            "ORDER BY LENGTH(line_text) DESC LIMIT 1", (cid,)
        ).fetchone()
        longest_line = longest[0] if longest else ""

        # 经典台词数
        classic_ratio = round(classic_lines / total_lines * 100, 1) if total_lines > 0 else 0.0

        name = ""
        if char:
            name = char.name
        elif info:
            name_row = conn.execute(
                "SELECT character_name FROM drama_lines WHERE character_id = ? LIMIT 1", (cid,)
            ).fetchone()
            name = name_row[0] if name_row else ""

        return {
            "character_id": cid,
            "name": name,
            "drama_id": drama_id[:64] if drama_id else None,
            "total_lines": total_lines,
            "classic_lines": classic_lines,
            "classic_ratio": classic_ratio,
            "scene_appearances": scene_count,
            "drama_appearances": len(dramas),
            "drama_ids": [r[0] for r in dramas],
            "avg_line_length": avg_line_len,
            "total_text_chars": total_chars,
            "longest_line": longest_line[:300],
        }

    # ===== v5.3.1 新增 =====

    def search_agent_memories(self,
                              agent_id: str,
                              keyword: str,
                              limit: int = 50,
                              offset: int = 0) -> List[Any]:
        """在指定 Agent 的记忆中搜索关键词（v5.3.1 新增）

        Args:
            agent_id: Agent ID
            keyword: 搜索关键词
            limit: 返回数量上限
            offset: 偏移量

        Returns:
            匹配的记忆列表
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        kw = keyword[:200] if isinstance(keyword, str) else ""
        if not aid or not kw:
            return []

        limit = max(1, min(500, int(limit)))
        offset = max(0, int(offset))

        # v5.3.1 安全加固：参数化查询防 SQL 注入；软删除通过 category='trash' 标记
        # v5.3.3 安全加固：LIKE 通配符转义，防 % 和 _ 注入
        pattern = f"%{_escape_like(kw)}%"
        rows = conn.execute(
            "SELECT * FROM memories WHERE source_agent = ? AND category != 'trash' "
            "AND (content LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\') "
            "ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?",
            (aid, pattern, pattern, pattern, limit, offset)
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def compare_agents(self,
                       agent_a: str,
                       agent_b: str) -> Dict[str, Any]:
        """对比两个 Agent 的记忆差异（v5.3.1 新增）

        Args:
            agent_a: Agent A ID
            agent_b: Agent B ID

        Returns:
            对比结果：各自记忆数、共同分类、独有分类、共同标签
        """
        conn = self._get_conn()
        aid_a = agent_a[:128] if isinstance(agent_a, str) else ""
        aid_b = agent_b[:128] if isinstance(agent_b, str) else ""
        if not aid_a or not aid_b:
            return {"error": "Agent ID 不能为空"}

        # 各自记忆总数（软删除通过 category='trash' 标记）
        count_a = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE source_agent = ? AND category != 'trash'",
            (aid_a,)
        ).fetchone()[0]
        count_b = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE source_agent = ? AND category != 'trash'",
            (aid_b,)
        ).fetchone()[0]

        # 各自分类集合
        cats_a = set(r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM memories WHERE source_agent = ? AND category != 'trash' AND category IS NOT NULL",
            (aid_a,)
        ).fetchall())
        cats_b = set(r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM memories WHERE source_agent = ? AND category != 'trash' AND category IS NOT NULL",
            (aid_b,)
        ).fetchall())

        # 各自标签集合
        tags_a = set()
        for r in conn.execute(
            "SELECT DISTINCT tags FROM memories WHERE source_agent = ? AND category != 'trash' AND tags IS NOT NULL",
            (aid_a,)
        ).fetchall():
            if r[0]:
                tags_a.update(t.strip() for t in r[0].split(",") if t.strip())
        tags_b = set()
        for r in conn.execute(
            "SELECT DISTINCT tags FROM memories WHERE source_agent = ? AND category != 'trash' AND tags IS NOT NULL",
            (aid_b,)
        ).fetchall():
            if r[0]:
                tags_b.update(t.strip() for t in r[0].split(",") if t.strip())

        # 平均重要度
        avg_a = conn.execute(
            "SELECT AVG(CASE importance WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END) "
            "FROM memories WHERE source_agent = ? AND category != 'trash'",
            (aid_a,)
        ).fetchone()[0] or 0
        avg_b = conn.execute(
            "SELECT AVG(CASE importance WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END) "
            "FROM memories WHERE source_agent = ? AND category != 'trash'",
            (aid_b,)
        ).fetchone()[0] or 0

        common_cats = sorted(cats_a & cats_b)
        only_a_cats = sorted(cats_a - cats_b)
        only_b_cats = sorted(cats_b - cats_a)
        common_tags = sorted(tags_a & tags_b)

        return {
            "agent_a": aid_a,
            "agent_b": aid_b,
            "count_a": count_a,
            "count_b": count_b,
            "avg_importance_a": round(avg_a, 2),
            "avg_importance_b": round(avg_b, 2),
            "common_categories": common_cats,
            "only_a_categories": only_a_cats,
            "only_b_categories": only_b_cats,
            "common_tags": common_tags[:50],
            "tags_a_count": len(tags_a),
            "tags_b_count": len(tags_b),
        }

    def search_dramas(self,
                      keyword: str,
                      genre: Optional[str] = None,
                      min_rating: float = 0.0,
                      limit: int = 50,
                      offset: int = 0) -> List[Any]:
        """按关键词搜索短剧（v5.3.1 新增）

        Args:
            keyword: 搜索关键词（匹配标题/描述/标签）
            genre: 类型过滤
            min_rating: 最低评分
            limit: 返回数量上限
            offset: 偏移量

        Returns:
            匹配的短剧列表
        """
        conn = self._get_conn()
        kw = keyword[:200] if isinstance(keyword, str) else ""
        if not kw:
            return []

        limit = max(1, min(500, int(limit)))
        offset = max(0, int(offset))
        min_rating = max(0.0, min(10.0, float(min_rating)))

        # v5.3.3 安全加固：LIKE 通配符转义，防 % 和 _ 注入
        pattern = f"%{_escape_like(kw)}%"
        query = ("SELECT * FROM drama_series WHERE "
                 "(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')")
        params = [pattern, pattern, pattern]

        if genre:
            query += " AND genre = ?"
            params.append(genre)
        if min_rating > 0:
            query += " AND rating >= ?"
            params.append(min_rating)

        query += " ORDER BY rating DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_drama(r) for r in rows]

    def character_ranking(self,
                          drama_id: Optional[str] = None,
                          sort_by: str = "lines",
                          limit: int = 20) -> List[Dict[str, Any]]:
        """角色台词排行榜（v5.3.1 新增）

        Args:
            drama_id: 限定短剧（可选，不指定则全局排行）
            sort_by: 排序维度 lines/classic/scenes
            limit: 返回数量上限

        Returns:
            角色排行列表
        """
        conn = self._get_conn()
        limit = max(1, min(100, int(limit)))

        valid_sorts = {"lines": "total_lines", "classic": "classic_lines", "scenes": "scene_count"}
        sort_col = valid_sorts.get(sort_by, "total_lines")

        if drama_id:
            did = drama_id[:64] if isinstance(drama_id, str) else ""
            sql = (
                "SELECT character_id, character_name, "
                "COUNT(*) as total_lines, "
                "SUM(is_classic) as classic_lines, "
                "COUNT(DISTINCT scene_id) as scene_count, "
                "SUM(LENGTH(line_text)) as total_chars "
                "FROM drama_lines WHERE drama_id = ? "
                "GROUP BY character_id, character_name "
                f"ORDER BY {sort_col} DESC LIMIT ?"
            )
            rows = conn.execute(sql, (did, limit)).fetchall()
        else:
            sql = (
                "SELECT character_id, character_name, "
                "COUNT(*) as total_lines, "
                "SUM(is_classic) as classic_lines, "
                "COUNT(DISTINCT scene_id) as scene_count, "
                "SUM(LENGTH(line_text)) as total_chars "
                "FROM drama_lines "
                "GROUP BY character_id, character_name "
                f"ORDER BY {sort_col} DESC LIMIT ?"
            )
            rows = conn.execute(sql, (limit,)).fetchall()

        result = []
        for i, r in enumerate(rows):
            total = r[2] or 0
            classic = r[3] or 0
            scenes = r[4] or 0
            chars = r[5] or 0
            result.append({
                "rank": i + 1,
                "character_id": r[0] or "",
                "name": r[1] or "",
                "total_lines": total,
                "classic_lines": classic,
                "classic_ratio": round(classic / total * 100, 1) if total > 0 else 0.0,
                "scene_count": scenes,
                "total_chars": chars,
                "avg_line_length": round(chars / total, 1) if total > 0 else 0.0,
            })
        return result

    # ===== v5.3.2 新增 =====

    def agent_diff_memories(self,
                            agent_id: str,
                            days_a: int = 7,
                            days_b: int = 1) -> Dict[str, Any]:
        """对比同一 Agent 在不同时间段的记忆差异（v5.3.2 新增）

        Args:
            agent_id: Agent ID
            days_a: 时间段 A 回溯天数（较早，如 7 天前至今）
            days_b: 时间段 B 回溯天数（较近，如 1 天前至今）

        Returns:
            差异报告字典
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        if not aid:
            return {"error": "Agent ID 不能为空"}

        days_a = max(1, min(3650, int(days_a)))
        days_b = max(1, min(3650, int(days_b)))
        if days_b > days_a:
            days_a, days_b = days_b, days_a

        now = __import__("time").time()
        ts_a = now - days_a * 86400
        ts_b = now - days_b * 86400

        # v5.3.2 安全加固：参数化 SQL
        # A 时间段（从 ts_a 到 ts_b 的增量）
        period_a_rows = conn.execute(
            "SELECT id, content, category, importance, created_at FROM memories "
            "WHERE source_agent = ? AND category != 'trash' AND created_at >= ? AND created_at < ?",
            (aid, ts_a, ts_b)
        ).fetchall()

        # B 时间段（从 ts_b 到现在）
        period_b_rows = conn.execute(
            "SELECT id, content, category, importance, created_at FROM memories "
            "WHERE source_agent = ? AND category != 'trash' AND created_at >= ?",
            (aid, ts_b)
        ).fetchall()

        # 分类聚合
        def _agg(rows):
            cats = {}
            imp_sum = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
            for r in rows:
                cat = r[2] or "general"
                cats[cat] = cats.get(cat, 0) + 1
                imp = r[3] or "MEDIUM"
                imp_sum[imp] = imp_sum.get(imp, 0) + 1
            return {"count": len(rows), "by_category": cats, "by_importance": imp_sum}

        period_a = _agg(period_a_rows)
        period_b = _agg(period_b_rows)

        # 分类差集
        cats_a = set(period_a["by_category"].keys())
        cats_b = set(period_b["by_category"].keys())
        new_cats = sorted(cats_b - cats_a)
        dropped_cats = sorted(cats_a - cats_b)

        return {
            "agent_id": aid,
            "period_a": {"days": days_a, **period_a, "time_range": f"[{days_a}天前 ~ {days_b}天前)"},
            "period_b": {"days": days_b, **period_b, "time_range": f"[{days_b}天前 ~ 现在]"},
            "new_categories": new_cats,
            "dropped_categories": dropped_cats,
            "total_diff": period_b["count"] - period_a["count"],
        }

    def agent_purge(self,
                    agent_id: str,
                    actor: str = "system",
                    session_id: str = "",
                    dry_run: bool = True) -> Dict[str, Any]:
        """清空指定 Agent 的全部记忆（v5.3.2 新增，高危操作）

        v5.3.3 安全加固：添加频率限制，防止暴力清空攻击。

        Args:
            agent_id: 目标 Agent ID
            actor: 操作者（审计日志）
            session_id: 会话 ID
            dry_run: True=仅预览，False=实际执行

        Returns:
            清理结果字典
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        if not aid:
            return {"error": "Agent ID 不能为空"}

        # v5.3.3 安全加固：频率限制，实际执行时每分钟最多 3 次
        if not dry_run:
            rate_key = f"purge:{aid}"
            if not _rate_limiter.check(rate_key, max_calls=3, window_seconds=60):
                return {"error": "操作过于频繁，请 60 秒后重试（频率限制）"}

        # 找出所有目标记忆（含软删除也一并清，因为是 purge）
        rows = conn.execute(
            "SELECT id, rowid FROM memories WHERE source_agent = ?",
            (aid,)
        ).fetchall()

        total = len(rows)
        if total == 0:
            return {"agent_id": aid, "total_found": 0, "purged": 0, "dry_run": dry_run}

        if dry_run:
            # 预览各分类数量
            cat_stats = {}
            for r in conn.execute(
                "SELECT category, COUNT(*) FROM memories WHERE source_agent = ? GROUP BY category",
                (aid,)
            ).fetchall():
                cat_stats[r[0] or "general"] = r[1]
            return {
                "agent_id": aid,
                "total_found": total,
                "by_category": cat_stats,
                "purged": 0,
                "dry_run": True,
                "note": "加 --force 参数执行实际删除",
            }

        # 实际删除（v5.3.2 安全：批量 id 列表参数化）
        ids = [r[0] for r in rows]
        rowids = [r[1] for r in rows]
        placeholders = ",".join(["?"] * len(ids))

        # 清理关联表：memory_versions、memory_links、memory_notes（以记忆 id 为外键）
        for table, col in [("memory_versions", "memory_id"),
                           ("memory_links", "source_id"),
                           ("memory_links", "target_id"),
                           ("memory_notes", "memory_id")]:
            try:
                conn.execute(
                    f"DELETE FROM {table} WHERE {col} IN ({placeholders})", ids
                )
            except Exception:
                pass

        # 清理 FTS（contentless FTS5 特殊语法）
        for rid in rowids:
            try:
                conn.execute(
                    "INSERT INTO memory_fts(memory_fts, rowid, content, category, tags) "
                    "VALUES('delete', ?, ?, ?, ?)",
                    (rid, "", "", "[]")
                )
            except Exception:
                pass

        conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)

        # 审计日志
        try:
            conn.execute(
                "INSERT INTO audit_log(action, actor, session_id, details, created_at) "
                "VALUES(?, ?, ?, ?, ?)",
                ("agent_purge", actor[:64], session_id[:64],
                 f'{{"agent_id": "{aid}", "count": {total}}}',
                 __import__("time").time())
            )
        except Exception:
            pass

        conn.commit()
        return {"agent_id": aid, "total_found": total, "purged": total, "dry_run": False}

    def drama_update_progress(self,
                               drama_id: str,
                               current_episode: int,
                               status: Optional[str] = None,
                               user_rating: Optional[float] = None,
                               actor: str = "system") -> Dict[str, Any]:
        """更新短剧观看进度（v5.3.2 新增）

        利用 drama_series 表的 metadata 字段存储用户个性化进度，
        无需新增数据库列即可实现该功能。

        Args:
            drama_id: 短剧 ID
            current_episode: 当前看到第几集（≥1）
            status: 观看状态 WATCHING/COMPLETED/DROPPED/PLANNING（可选）
            user_rating: 用户评分 0-10（可选）
            actor: 操作者

        Returns:
            更新结果字典
        """
        conn = self._get_conn()
        did = drama_id[:64] if isinstance(drama_id, str) else ""
        if not did:
            return {"error": "短剧 ID 不能为空"}

        current_episode = max(1, min(10000, int(current_episode)))

        # v5.3.2 安全：status 枚举白名单
        valid_status = {"WATCHING", "COMPLETED", "DROPPED", "PLANNING"}
        if status:
            status = status.upper()
            if status not in valid_status:
                status = None

        if user_rating is not None:
            user_rating = max(0.0, min(10.0, float(user_rating)))

        # 检查短剧是否存在
        row = conn.execute(
            "SELECT id, metadata FROM drama_series WHERE id = ?",
            (did,)
        ).fetchone()
        if not row:
            return {"error": f"短剧不存在: {did}"}

        # 解析现有 metadata（v5.3.2 安全：统一 safe json 加载）
        import json as _json
        try:
            metadata = _json.loads(row[1]) if (row[1] and row[1].strip()) else {}
        except Exception:
            metadata = {}

        # 写入进度字段（前缀 user_progress 避免与官方字段冲突）
        prog = metadata.get("user_progress", {})
        prog["current_episode"] = current_episode
        prog["updated_at"] = __import__("time").time()
        if status:
            prog["status"] = status
        if user_rating is not None:
            prog["user_rating"] = user_rating
        metadata["user_progress"] = prog

        try:
            meta_json = _json.dumps(metadata, ensure_ascii=False)[:10000]
        except Exception:
            meta_json = "{}"

        conn.execute(
            "UPDATE drama_series SET metadata = ?, updated_at = ? WHERE id = ?",
            (meta_json, __import__("time").time(), did)
        )
        conn.commit()

        # 返回完整当前进度
        return {
            "drama_id": did,
            "current_episode": current_episode,
            "status": prog.get("status"),
            "user_rating": prog.get("user_rating"),
            "updated_at": prog.get("updated_at"),
        }

    def drama_recommend_v2(self,
                            genre: Optional[str] = None,
                            min_rating: float = 0.0,
                            mode: str = "unwatched",
                            limit: int = 20) -> List[Dict[str, Any]]:
        """短剧智能推荐 v2（v5.3.2 新增）

        支持按观看状态过滤：优先推荐未观看 / 正在追 / 已弃剧。

        Args:
            genre: 类型过滤（枚举白名单）
            min_rating: 最低评分
            mode: 推荐模式 unwatched/watching/dropped/all
            limit: 返回数量上限

        Returns:
            推荐短剧列表
        """
        conn = self._get_conn()
        import json as _json

        limit = max(1, min(200, int(limit)))
        min_rating = max(0.0, min(10.0, float(min_rating)))

        # v5.3.2 安全：白名单
        valid_genres = {"ROMANCE", "ACTION", "COMEDY", "THRILLER", "SCIFI",
                        "HISTORICAL", "URBAN", "FANTASY", "MYSTERY", "DRAMA"}
        if genre:
            genre = genre.upper()
            if genre not in valid_genres:
                genre = None

        valid_modes = {"unwatched", "watching", "dropped", "all"}
        if mode not in valid_modes:
            mode = "unwatched"

        rows = conn.execute("SELECT * FROM drama_series ORDER BY rating DESC").fetchall()

        candidates = []
        for r in rows:
            d = self._row_to_drama(r)
            if genre and (getattr(d, "genre", "") or "").upper() != genre:
                continue
            rating_val = getattr(d, "rating", 0) or 0
            if rating_val < min_rating:
                continue

            # 从 metadata 解析进度
            status = ""
            cur_ep = 0
            try:
                md = getattr(d, "metadata", {}) or {}
                if isinstance(md, str):
                    md = _json.loads(md) if md.strip() else {}
                prog = md.get("user_progress", {})
                status = prog.get("status", "") or ""
                cur_ep = prog.get("current_episode", 0) or 0
            except Exception:
                pass

            # 模式过滤
            total_eps = getattr(d, "total_episodes", 0) or 0
            if mode == "unwatched":
                if status == "COMPLETED" or (cur_ep > 0 and cur_ep >= total_eps and total_eps > 0):
                    continue
                if status == "WATCHING":  # 追剧中不算未观看
                    continue
                if cur_ep > 0:
                    continue
            elif mode == "watching":
                if status != "WATCHING" and not (0 < cur_ep < (total_eps or 9999)):
                    continue
            elif mode == "dropped":
                if status != "DROPPED":
                    continue

            meta_safe = getattr(d, "metadata", {})
            if isinstance(meta_safe, str):
                try:
                    meta_safe = _json.loads(meta_safe) if meta_safe.strip() else {}
                except Exception:
                    meta_safe = {}
            prog = (meta_safe or {}).get("user_progress", {})
            candidates.append({
                "drama_id": getattr(d, "id", ""),
                "title": getattr(d, "title", ""),
                "genre": getattr(d, "genre", ""),
                "rating": rating_val,
                "status": getattr(d, "status", ""),
                "total_episodes": total_eps,
                "watch_status": prog.get("status", ""),
                "current_episode": prog.get("current_episode", 0),
                "user_rating": prog.get("user_rating"),
            })

        # 按综合分排序：官方评分 * 0.7 + （未看加权 1.3）
        def _score(c):
            s = c["rating"] * 0.7
            if not c["current_episode"]:
                s *= 1.3
            if c["watch_status"] != "DROPPED":
                s += 0.5
            return s

        candidates.sort(key=_score, reverse=True)
        return candidates[:limit]

    # ===== v5.3.3 新增：Agent 记忆时间线 & 热力图 =====

    def agent_timeline(self,
                       agent_id: str,
                       days: int = 30) -> Dict[str, Any]:
        """Agent 记忆时间线分析（v5.3.3 新增）

        按天/小时统计记忆创建趋势，识别 Agent 活跃时段。

        Args:
            agent_id: Agent ID
            days: 回溯天数（1-365）

        Returns:
            时间线分析结果：按天计数、按小时分布、活跃峰、趋势
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        if not aid:
            return {"error": "Agent ID 不能为空"}

        days = max(1, min(365, int(days)))
        now = time.time()
        since = now - days * 86400

        # v5.3.3 安全加固：参数化 SQL
        rows = conn.execute(
            "SELECT created_at FROM memories "
            "WHERE source_agent = ? AND category != 'trash' AND created_at >= ?",
            (aid, since)
        ).fetchall()

        if not rows:
            return {
                "agent_id": aid,
                "days": days,
                "total_memories": 0,
                "by_day": {},
                "by_hour": {},
                "peak_day": None,
                "peak_hour": None,
                "trend": "no_data",
            }

        from datetime import datetime as _dt

        by_day: Dict[str, int] = {}
        by_hour: Dict[int, int] = {h: 0 for h in range(24)}

        for r in rows:
            ts = r[0] or 0
            if ts <= 0:
                continue
            dt = _dt.fromtimestamp(ts)
            day_key = dt.strftime("%Y-%m-%d")
            by_day[day_key] = by_day.get(day_key, 0) + 1
            by_hour[dt.hour] = by_hour.get(dt.hour, 0) + 1

        # 找活跃峰
        peak_day = max(by_day, key=by_day.get) if by_day else None
        peak_hour = max(by_hour, key=by_hour.get) if by_hour else None

        # 趋势分析：后半段 vs 前半段
        sorted_days = sorted(by_day.keys())
        mid = len(sorted_days) // 2
        if mid > 0:
            first_half = sum(by_day[d] for d in sorted_days[:mid])
            second_half = sum(by_day[d] for d in sorted_days[mid:])
            if second_half > first_half * 1.1:
                trend = "rising"
            elif first_half > second_half * 1.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # 活跃时段标签
        active_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)
        top_hours = [h for h, c in active_hours[:3] if c > 0]

        return {
            "agent_id": aid,
            "days": days,
            "total_memories": len(rows),
            "by_day": by_day,
            "by_hour": {str(h): by_hour[h] for h in range(24) if by_hour[h] > 0},
            "peak_day": {"date": peak_day, "count": by_day[peak_day]} if peak_day else None,
            "peak_hour": {"hour": peak_hour, "count": by_hour[peak_hour]} if peak_hour is not None else None,
            "top_active_hours": top_hours,
            "trend": trend,
            "avg_per_day": round(len(rows) / days, 2) if days > 0 else 0,
        }

    def agent_heatmap(self,
                      agent_id: str,
                      days: int = 30) -> Dict[str, Any]:
        """Agent 记忆热力图矩阵（v5.3.3 新增）

        生成 分类 × 重要度 的记忆密度矩阵，可视化 Agent 记忆分布。

        Args:
            agent_id: Agent ID
            days: 回溯天数（1-365）

        Returns:
            热力图矩阵：分类行 × 重要度列的计数矩阵
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        if not aid:
            return {"error": "Agent ID 不能为空"}

        days = max(1, min(365, int(days)))
        now = time.time()
        since = now - days * 86400

        # v5.3.3 安全加固：参数化 SQL
        rows = conn.execute(
            "SELECT category, importance FROM memories "
            "WHERE source_agent = ? AND category != 'trash' AND created_at >= ?",
            (aid, since)
        ).fetchall()

        importance_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        matrix: Dict[str, Dict[str, int]] = {}

        for r in rows:
            cat = (r[0] or "general")[:128]
            imp = (r[1] or "MEDIUM").upper()
            if imp not in importance_levels:
                imp = "MEDIUM"
            if cat not in matrix:
                matrix[cat] = {lv: 0 for lv in importance_levels}
            matrix[cat][imp] += 1

        # 计算行/列总计和密度
        row_totals = {cat: sum(vals.values()) for cat, vals in matrix.items()}
        col_totals = {lv: sum(matrix[cat][lv] for cat in matrix) for lv in importance_levels}
        grand_total = sum(row_totals.values())

        # 找密度最高的单元格
        max_cell = None
        max_count = 0
        for cat, vals in matrix.items():
            for imp, cnt in vals.items():
                if cnt > max_count:
                    max_count = cnt
                    max_cell = {"category": cat, "importance": imp, "count": cnt}

        return {
            "agent_id": aid,
            "days": days,
            "total_memories": grand_total,
            "matrix": matrix,
            "row_totals": row_totals,
            "col_totals": col_totals,
            "importance_levels": importance_levels,
            "categories": sorted(matrix.keys()),
            "max_density_cell": max_cell,
        }

    # ===== v5.3.3 新增：AI 短剧追剧统计 & 角色关系网络 =====

    def drama_binge_stats(self,
                          drama_id: Optional[str] = None) -> Dict[str, Any]:
        """追剧统计（v5.3.3 新增）

        统计观看进度记录，包括连续观看天数、最长追剧周期、平均完成时长。

        Args:
            drama_id: 指定短剧（可选，None=全部）

        Returns:
            追剧统计结果
        """
        conn = self._get_conn()
        import json as _json

        # v5.3.3 安全加固：参数化 SQL + ID 长度限制
        if drama_id:
            did = drama_id[:64] if isinstance(drama_id, str) else ""
            rows = conn.execute(
                "SELECT id, title, total_episodes, current_episode, status, "
                "updated_at, last_watched_at, metadata, rating "
                "FROM drama_series WHERE id = ?",
                (did,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, total_episodes, current_episode, status, "
                "updated_at, last_watched_at, metadata, rating "
                "FROM drama_series"
            ).fetchall()

        if not rows:
            return {
                "total_dramas": 0,
                "watching": 0,
                "completed": 0,
                "dropped": 0,
                "planned": 0,
                "binge_stats": {},
            }

        total = len(rows)
        watching = 0
        completed = 0
        dropped = 0
        planned = 0
        total_episodes_watched = 0
        total_episodes_planned = 0
        watch_records = []

        for r in rows:
            status = r[4] or "planned"
            cur_ep = r[3] or 0
            total_ep = r[2] or 0
            rating = r[8] or 0.0
            last_watched = r[6] or 0
            updated = r[5] or 0

            if status == "watching":
                watching += 1
            elif status == "completed":
                completed += 1
            elif status == "dropped":
                dropped += 1
            else:
                planned += 1

            total_episodes_watched += cur_ep
            total_episodes_planned += total_ep

            # 从 metadata 解析进度历史
            watch_history = []
            try:
                md_raw = r[7]
                if isinstance(md_raw, str) and md_raw.strip():
                    md = _json.loads(md_raw)
                elif isinstance(md_raw, dict):
                    md = md_raw
                else:
                    md = {}
                watch_history = md.get("user_progress", {}).get("history", [])
            except Exception:
                pass

            watch_records.append({
                "drama_id": r[0],
                "title": r[1],
                "status": status,
                "current_episode": cur_ep,
                "total_episodes": total_ep,
                "rating": rating,
                "last_watched_at": last_watched,
                "updated_at": updated,
                "watch_history_count": len(watch_history),
            })

        # 完成率
        completion_rate = round(
            (total_episodes_watched / total_episodes_planned * 100)
            if total_episodes_planned > 0 else 0.0, 2
        )

        # 最近观看的短剧 Top-5
        recent_watched = sorted(
            [w for w in watch_records if w["last_watched_at"] > 0],
            key=lambda x: x["last_watched_at"], reverse=True
        )[:5]

        # 评分分布
        rated = [w for w in watch_records if w["rating"] > 0]
        avg_rating = round(sum(w["rating"] for w in rated) / len(rated), 2) if rated else 0.0

        return {
            "total_dramas": total,
            "watching": watching,
            "completed": completed,
            "dropped": dropped,
            "planned": planned,
            "total_episodes_watched": total_episodes_watched,
            "total_episodes_planned": total_episodes_planned,
            "completion_rate": completion_rate,
            "average_rating": avg_rating,
            "rated_count": len(rated),
            "recent_watched": recent_watched,
        }

    def character_network(self,
                          drama_id: str) -> Dict[str, Any]:
        """角色关系网络分析（v5.3.3 新增）

        分析短剧中角色间的共同出场频率，构建角色关系网络数据。

        Args:
            drama_id: 短剧 ID

        Returns:
            角色关系网络：节点列表 + 边列表（含共同出场次数）
        """
        conn = self._get_conn()
        did = drama_id[:64] if isinstance(drama_id, str) and drama_id else ""
        if not did:
            return {"error": "短剧 ID 不能为空"}

        # 获取所有角色
        char_rows = conn.execute(
            "SELECT id, name, role FROM drama_characters WHERE drama_id = ?",
            (did,)
        ).fetchall()

        if not char_rows:
            return {
                "drama_id": did,
                "nodes": [],
                "edges": [],
                "total_characters": 0,
            }

        characters = {r[0]: {"id": r[0], "name": r[1], "role": r[2]} for r in char_rows}

        # 获取所有场次的台词，按场次统计角色出场
        scene_chars: Dict[str, set] = {}
        line_rows = conn.execute(
            "SELECT scene_id, character_id FROM drama_lines "
            "WHERE drama_id = ? AND character_id != ''",
            (did,)
        ).fetchall()

        for r in line_rows:
            scene_id = r[0] or ""
            char_id = r[1] or ""
            if scene_id and char_id and char_id in characters:
                if scene_id not in scene_chars:
                    scene_chars[scene_id] = set()
                scene_chars[scene_id].add(char_id)

        # 构建共现矩阵
        co_occurrence: Dict[str, Dict[str, int]] = {}
        for scene_id, char_set in scene_chars.items():
            char_list = list(char_set)
            for i in range(len(char_list)):
                for j in range(i + 1, len(char_list)):
                    a, b = char_list[i], char_list[j]
                    if a not in co_occurrence:
                        co_occurrence[a] = {}
                    if b not in co_occurrence[a]:
                        co_occurrence[a][b] = 0
                    co_occurrence[a][b] += 1

        # 构建边列表
        edges = []
        seen_pairs = set()
        for a, partners in co_occurrence.items():
            for b, count in partners.items():
                pair_key = tuple(sorted([a, b]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                edges.append({
                    "source": a,
                    "source_name": characters.get(a, {}).get("name", a),
                    "target": b,
                    "target_name": characters.get(b, {}).get("name", b),
                    "weight": count,
                })

        edges.sort(key=lambda e: e["weight"], reverse=True)

        # 节点：附加出场次数和关联数
        nodes = []
        for char_id, info in characters.items():
            scene_count = sum(1 for s in scene_chars.values() if char_id in s)
            connections = sum(1 for e in edges if e["source"] == char_id or e["target"] == char_id)
            nodes.append({
                "id": char_id,
                "name": info["name"],
                "role": info["role"],
                "scene_count": scene_count,
                "connections": connections,
            })

        nodes.sort(key=lambda n: n["connections"], reverse=True)

        return {
            "drama_id": did,
            "nodes": nodes,
            "edges": edges,
            "total_characters": len(nodes),
            "total_edges": len(edges),
            "total_scenes_analyzed": len(scene_chars),
        }

    # ===== v5.3.4 新增：Agent 记忆情感分析 + 记忆衰减评分 =====

    def agent_sentiment(self,
                        agent_id: str,
                        days: int = 30) -> Dict[str, Any]:
        """Agent 记忆情感分析（v5.3.4 新增）

        基于关键词匹配分析 Agent 记忆的整体情感倾向。

        Args:
            agent_id: Agent ID
            days: 回溯天数（1-365）

        Returns:
            情感分析结果：正面/负面/中性计数、情感分布、主导情感
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        if not aid:
            return {"error": "Agent ID 不能为空"}

        days = max(1, min(365, int(days)))
        now = time.time()
        since = now - days * 86400

        # v5.3.4 安全：参数化 SQL
        rows = conn.execute(
            "SELECT content, importance FROM memories "
            "WHERE source_agent = ? AND category != 'trash' AND created_at >= ?",
            (aid, since)
        ).fetchall()

        if not rows:
            return {
                "agent_id": aid,
                "days": days,
                "total_memories": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "dominant_sentiment": "no_data",
            }

        # 情感关键词词典
        positive_words = {
            "好", "棒", "优秀", "成功", "完成", "解决", "开心", "满意", "喜欢",
            "good", "great", "excellent", "success", "happy", "love", "perfect",
            "完成", "突破", "提升", "优化", "改进", "有效", "正确", "赞同",
        }
        negative_words = {
            "坏", "差", "失败", "错误", "问题", "bug", "崩溃", "讨厌", "不满",
            "bad", "fail", "error", "broken", "crash", "hate", "wrong", "issue",
            "缺失", "丢失", "异常", "警告", "危险", "漏洞", "冲突", "阻塞",
        }

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        sentiment_by_imp: Dict[str, Dict[str, int]] = {}

        for r in rows:
            content = (r[0] or "").lower()
            imp = (r[1] or "MEDIUM").upper()

            pos_hits = sum(1 for w in positive_words if w in content)
            neg_hits = sum(1 for w in negative_words if w in content)

            if pos_hits > neg_hits:
                sentiment = "positive"
                positive_count += 1
            elif neg_hits > pos_hits:
                sentiment = "negative"
                negative_count += 1
            else:
                sentiment = "neutral"
                neutral_count += 1

            if imp not in sentiment_by_imp:
                sentiment_by_imp[imp] = {"positive": 0, "negative": 0, "neutral": 0}
            sentiment_by_imp[imp][sentiment] += 1

        total = len(rows)
        if positive_count > negative_count and positive_count > neutral_count:
            dominant = "positive"
        elif negative_count > positive_count and negative_count > neutral_count:
            dominant = "negative"
        else:
            dominant = "neutral"

        return {
            "agent_id": aid,
            "days": days,
            "total_memories": total,
            "positive": positive_count,
            "negative": negative_count,
            "neutral": neutral_count,
            "positive_ratio": round(positive_count / total, 4) if total else 0,
            "negative_ratio": round(negative_count / total, 4) if total else 0,
            "neutral_ratio": round(neutral_count / total, 4) if total else 0,
            "dominant_sentiment": dominant,
            "by_importance": sentiment_by_imp,
        }

    def memory_decay(self,
                     agent_id: str,
                     days: int = 30) -> Dict[str, Any]:
        """记忆衰减评分（v5.3.4 新增）

        基于艾宾浩斯遗忘曲线模型，评估 Agent 记忆的衰减状态。
        衰减评分 = 重要性权重 × recency_factor × retention_rate

        Args:
            agent_id: Agent ID
            days: 回溯天数（1-365）

        Returns:
            衰减分析结果：平均衰减率、高危记忆数、各衰减级别分布
        """
        conn = self._get_conn()
        aid = agent_id[:128] if isinstance(agent_id, str) else ""
        if not aid:
            return {"error": "Agent ID 不能为空"}

        days = max(1, min(365, int(days)))
        now = time.time()
        since = now - days * 86400

        # v5.3.4 安全：参数化 SQL
        rows = conn.execute(
            "SELECT id, content, importance, created_at, access_count "
            "FROM memories "
            "WHERE source_agent = ? AND category != 'trash' AND created_at >= ?",
            (aid, since)
        ).fetchall()

        if not rows:
            return {
                "agent_id": aid,
                "days": days,
                "total_memories": 0,
                "avg_retention": 0,
                "critical_decay": 0,
                "decay_distribution": {},
            }

        # 重要性权重
        imp_weights = {"LOW": 0.5, "MEDIUM": 0.7, "HIGH": 0.85, "CRITICAL": 1.0}

        total_retention = 0.0
        decay_levels = {"strong": 0, "stable": 0, "fading": 0, "critical": 0}
        critical_memories = []

        for r in rows:
            mid = r[0]
            content = (r[1] or "")[:80]
            imp = (r[2] or "MEDIUM").upper()
            created = r[3] or now
            access_count = r[4] or 0

            imp_weight = imp_weights.get(imp, 0.7)

            # 艾宾浩斯遗忘曲线：retention = e^(-t/S)
            # S = 稳定性，受重要性和访问次数影响
            days_elapsed = max(0.01, (now - created) / 86400)
            stability = imp_weight * (1 + min(access_count, 10) * 0.1) * 7  # 基础7天
            retention = __import__("math").exp(-days_elapsed / stability)

            total_retention += retention

            if retention >= 0.7:
                decay_levels["strong"] += 1
            elif retention >= 0.4:
                decay_levels["stable"] += 1
            elif retention >= 0.15:
                decay_levels["fading"] += 1
            else:
                decay_levels["critical"] += 1
                if len(critical_memories) < 20:
                    critical_memories.append({
                        "id": mid,
                        "content_preview": content,
                        "importance": imp,
                        "retention": round(retention, 4),
                        "days_elapsed": round(days_elapsed, 1),
                        "access_count": access_count,
                    })

        total = len(rows)
        avg_retention = round(total_retention / total, 4) if total else 0

        return {
            "agent_id": aid,
            "days": days,
            "total_memories": total,
            "avg_retention": avg_retention,
            "critical_decay": decay_levels["critical"],
            "decay_distribution": decay_levels,
            "critical_memories": critical_memories,
        }

    # ===== v5.3.4 新增：AI 短剧对比 + 角色成长弧线 =====

    def drama_compare(self,
                      drama_ids: List[str]) -> Dict[str, Any]:
        """短剧对比分析（v5.3.4 新增）

        对比多部短剧的评分、集数、角色数、经典台词数等维度。

        Args:
            drama_ids: 短剧 ID 列表（最多 5 部）

        Returns:
            对比分析结果
        """
        conn = self._get_conn()
        # v5.3.4 安全：数量限制 + ID 长度截断
        if not drama_ids or not isinstance(drama_ids, list):
            return {"error": "短剧 ID 列表不能为空"}
        ids = [d[:64] for d in drama_ids if isinstance(d, str) and d][:5]
        if not ids:
            return {"error": "无有效短剧 ID"}

        dramas = []
        for did in ids:
            row = conn.execute(
                "SELECT id, title, genre, total_episodes, current_episode, "
                "status, rating, metadata "
                "FROM drama_series WHERE id = ?",
                (did,)
            ).fetchone()
            if not row:
                dramas.append({"id": did, "error": "未找到"})
                continue

            # 统计角色数
            char_count = conn.execute(
                "SELECT COUNT(*) FROM drama_characters WHERE drama_id = ?",
                (did,)
            ).fetchone()[0]

            # 统计台词数和经典台词数
            line_stats = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN is_classic = 1 THEN 1 ELSE 0 END) "
                "FROM drama_lines WHERE drama_id = ?",
                (did,)
            ).fetchone()

            dramas.append({
                "id": row[0],
                "title": row[1] or "未命名",
                "genre": row[2] or "未知",
                "total_episodes": row[3] or 0,
                "current_episode": row[4] or 0,
                "status": row[5] or "planned",
                "rating": row[6] or 0.0,
                "character_count": char_count,
                "total_lines": line_stats[0] or 0,
                "classic_lines": line_stats[1] or 0,
            })

        # 计算对比维度
        valid = [d for d in dramas if "error" not in d]
        if len(valid) >= 2:
            best_rating = max(valid, key=lambda x: x["rating"])
            most_episodes = max(valid, key=lambda x: x["total_episodes"])
            most_characters = max(valid, key=lambda x: x["character_count"])
            most_classic = max(valid, key=lambda x: x["classic_lines"])
        else:
            best_rating = most_episodes = most_characters = most_classic = None

        return {
            "dramas": dramas,
            "comparison": {
                "best_rated": best_rating["title"] if best_rating else None,
                "most_episodes": most_episodes["title"] if most_episodes else None,
                "most_characters": most_characters["title"] if most_characters else None,
                "most_classic_lines": most_classic["title"] if most_classic else None,
            },
            "total_compared": len(valid),
        }

    def character_arc(self,
                      drama_id: str,
                      character_id: str) -> Dict[str, Any]:
        """角色成长弧线分析（v5.3.4 新增）

        分析角色在不同场景中的台词量变化，识别角色的成长轨迹。

        Args:
            drama_id: 短剧 ID
            character_id: 角色 ID

        Returns:
            角色成长弧线数据：按场景的台词量变化、活跃峰值、成长阶段
        """
        conn = self._get_conn()
        did = drama_id[:64] if isinstance(drama_id, str) and drama_id else ""
        cid = character_id[:64] if isinstance(character_id, str) and character_id else ""
        if not did or not cid:
            return {"error": "短剧 ID 和角色 ID 不能为空"}

        # 获取角色信息
        char_row = conn.execute(
            "SELECT id, name, role FROM drama_characters WHERE id = ? AND drama_id = ?",
            (cid, did)
        ).fetchone()
        if not char_row:
            return {"error": "角色不存在"}

        # 获取该角色在各个场景中的台词数
        scene_rows = conn.execute(
            "SELECT scene_id, COUNT(*) as line_count "
            "FROM drama_lines WHERE drama_id = ? AND character_id = ? "
            "GROUP BY scene_id ORDER BY scene_id",
            (did, cid)
        ).fetchall()

        if not scene_rows:
            return {
                "drama_id": did,
                "character_id": cid,
                "character_name": char_row[1],
                "total_scenes": 0,
                "total_lines": 0,
                "arc_points": [],
                "peak_scene": None,
                "growth_stage": "no_data",
            }

        arc_points = []
        for sr in scene_rows:
            arc_points.append({
                "scene_id": sr[0],
                "line_count": sr[1],
            })

        total_lines = sum(p["line_count"] for p in arc_points)
        total_scenes = len(arc_points)

        # 找活跃峰值场景
        peak = max(arc_points, key=lambda x: x["line_count"])

        # 成长阶段分析：将场景分为前中后三段
        third = max(1, total_scenes // 3)
        early = sum(p["line_count"] for p in arc_points[:third])
        mid = sum(p["line_count"] for p in arc_points[third:third * 2])
        late = sum(p["line_count"] for p in arc_points[third * 2:])

        if late > early * 1.2:
            growth_stage = "rising"  # 后期崛起
        elif early > late * 1.2:
            growth_stage = "falling"  # 前期活跃，后期淡出
        elif mid > early * 1.1 and mid > late * 1.1:
            growth_stage = "peak_middle"  # 中期高峰
        else:
            growth_stage = "stable"  # 稳定出场

        return {
            "drama_id": did,
            "character_id": cid,
            "character_name": char_row[1],
            "character_role": char_row[2],
            "total_scenes": total_scenes,
            "total_lines": total_lines,
            "arc_points": arc_points,
            "peak_scene": {"scene_id": peak["scene_id"], "line_count": peak["line_count"]},
            "growth_stage": growth_stage,
            "stage_distribution": {"early": early, "mid": mid, "late": late},
        }

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
                # v5.3.3 安全加固：LIKE 通配符转义
                conditions.append("content LIKE ? ESCAPE '\\'")
                params.append(f"%{_escape_like(kw)}%")
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
            pinned=bool(row["pinned"]) if "pinned" in row.keys() else False,
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
        """导出记忆为 Excel 格式（v5.1.9 新增，v5.2.9 安全加固：路径校验 + CSV 公式注入防护）

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

        # v5.2.9 安全加固：路径校验
        out = _safe_path(output_path, allowed_exts={".xlsx", ".csv"})
        out.parent.mkdir(parents=True, exist_ok=True)

        # v5.2.9 安全加固：CSV/XLSX 公式注入防护
        def _cell_safe(v, max_len=5000):
            if v is None:
                return ""
            s = str(v)[:max_len]
            if s and s[0] in ("=", "+", "-", "@"):
                return "\t" + s
            return s

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
                    _cell_safe(entry.id, 64),
                    _cell_safe(entry.content, 500),
                    _cell_safe(entry.category, 256),
                    _cell_safe(", ".join(entry.tags) if entry.tags else "", 1024),
                    _cell_safe(entry.privacy.value, 32),
                    _cell_safe(entry.importance.value, 32),
                    _cell_safe(entry.memory_type.value, 32),
                    _cell_safe(entry.layer.value, 32),
                    _cell_safe(entry.access_count, 32),
                    _cell_safe(_fmt_time(entry.created_at), 32),
                    _cell_safe(_fmt_time(entry.updated_at), 32),
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
            out_csv = Path(str(out).replace('.xlsx', '.csv'))
            with open(str(out_csv), 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "内容", "分类", "标签", "隐私等级", "重要性", "类型", "层级", "访问次数", "创建时间", "更新时间", "收藏"])
                for entry in entries:
                    writer.writerow([
                        _cell_safe(entry.id, 64),
                        _cell_safe(entry.content, 500),
                        _cell_safe(entry.category, 256),
                        _cell_safe(", ".join(entry.tags) if entry.tags else "", 1024),
                        _cell_safe(entry.privacy.value, 32),
                        _cell_safe(entry.importance.value, 32),
                        _cell_safe(entry.memory_type.value, 32),
                        _cell_safe(entry.layer.value, 32),
                        _cell_safe(entry.access_count, 32),
                        _cell_safe(entry.created_at, 32),
                        _cell_safe(entry.updated_at, 32),
                        _cell_safe(entry.starred, 8),
                    ])
            out = out_csv

        # v5.2.9 安全加固：权限收紧
        try:
            import stat
            import os
            os.chmod(out, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except (OSError, ImportError):
            pass

        return out

    def import_from_excel(self,
                          input_path: str,
                          target_category: Optional[str] = None,
                          target_layer: Optional[MemoryLayer] = None) -> Dict[str, int]:
        """从 Excel 文件导入记忆（v5.1.9 新增，v5.2.9 安全加固：路径校验 + 长度限制 + 枚举白名单）

        Args:
            input_path: Excel 文件路径
            target_category: 目标分类（覆盖文件中的分类）
            target_layer: 目标记忆层级

        Returns:
            {imported, skipped, failed}
        """
        # v5.2.9 安全加固：路径校验 + 大小限制
        path = _safe_path(input_path, must_exist=True,
                          allowed_exts={".xlsx", ".xls", ".csv"},
                          max_size=500 * 1024 * 1024)

        entries = []
        _MAX_CONTENT = 1000000
        _MAX_CAT = 256
        _MAX_TAG = 128
        _MAX_TAGS = 64
        _MAX_ROWS = 100000

        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            ws = wb.active

            headers = {}
            header_row = next(ws.iter_rows(values_only=True))
            for col_num, cell in enumerate(header_row, 1):
                h = str(cell).strip().lower() if cell is not None else ""
                if h:
                    headers[h] = col_num

            content_col = headers.get("内容", 2)
            category_col = headers.get("分类", 3)
            tags_col = headers.get("标签", 4)
            privacy_col = headers.get("隐私等级", 5)
            importance_col = headers.get("重要性", 6)
            layer_col = headers.get("层级", 8)

            row_count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                row_count += 1
                if row_count > _MAX_ROWS:
                    break
                cell_content = row[content_col - 1] if content_col - 1 < len(row) else None
                if cell_content and str(cell_content).strip():
                    content = str(cell_content).strip()[:_MAX_CONTENT]
                    cat_cell = row[category_col - 1] if category_col - 1 < len(row) else None
                    category = target_category or (
                        str(cat_cell).strip()[:_MAX_CAT] if cat_cell else "general"
                    )
                    tags_cell = row[tags_col - 1] if tags_col - 1 < len(row) else None
                    tags_str = str(tags_cell).strip() if tags_cell else ""
                    tags = [t.strip()[:_MAX_TAG] for t in tags_str.split(',') if t.strip()][:_MAX_TAGS] if tags_str else []
                    priv_cell = row[privacy_col - 1] if privacy_col - 1 < len(row) else None
                    privacy_str = str(priv_cell).strip() if priv_cell else "internal"
                    imp_cell = row[importance_col - 1] if importance_col - 1 < len(row) else None
                    importance_str = str(imp_cell).strip() if imp_cell else "medium"
                    lay_cell = row[layer_col - 1] if layer_col - 1 < len(row) else None
                    layer_str = str(lay_cell).strip() if lay_cell else "short_term"

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
                row_count = 0
                for row in reader:
                    row_count += 1
                    if row_count > _MAX_ROWS:
                        break
                    if row.get("内容") and str(row["内容"]).strip():
                        content = str(row["内容"]).strip()[:_MAX_CONTENT]
                        cat_val = str(row.get("分类", "") or "general").strip()
                        category = target_category or (cat_val[:_MAX_CAT] if cat_val else "general")
                        tags_str = str(row.get("标签", ""))
                        tags = [t.strip()[:_MAX_TAG] for t in tags_str.split(',') if t.strip()][:_MAX_TAGS] if tags_str else []
                        privacy_str = str(row.get("隐私等级", "internal")).strip()
                        importance_str = str(row.get("重要性", "medium")).strip()
                        layer_str = str(row.get("层级", "short_term")).strip()

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

        # v5.2.9 安全加固：条数限制
        if len(entries) > _MAX_ROWS:
            entries = entries[:_MAX_ROWS]

        for entry_data in entries:
            try:
                existing = None
                rows = self._get_conn().execute(
                    "SELECT id FROM memories WHERE content = ? AND category = ?",
                    (entry_data["content"][:5000], entry_data["category"][:_MAX_CAT])
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

        pre_backup_path = None
        try:
            if create_backup_before:
                pre_backup = self.create_backup()
                if pre_backup["success"]:
                    result["backup_created"] = pre_backup["path"]
                    pre_backup_path = pre_backup["path"]

            if self._conn:
                self._conn.close()
                self._conn = None

            shutil.copy2(str(backup_file), str(self.db_path))

            self._init_db()

            # PRAGMA integrity_check 校验（v5.2.7 新增：确保恢复的数据库结构完整）
            if self._conn:
                try:
                    cur = self._conn.execute("PRAGMA integrity_check")
                    integrity_row = cur.fetchone()
                    cur.close()
                except sqlite3.DatabaseError as ie:
                    result["error"] = f"数据库完整性校验异常: {ie}"
                    # 校验异常时尝试回滚到恢复前的备份
                    if pre_backup_path:
                        try:
                            self._conn.close()
                            self._conn = None
                            shutil.copy2(pre_backup_path, str(self.db_path))
                            self._init_db()
                        except (OSError, IOError):
                            pass
                    return result

                if integrity_row is None or str(integrity_row[0]).lower() != "ok":
                    integrity_msg = integrity_row[0] if integrity_row else "无结果"
                    result["error"] = f"数据库完整性校验失败: {integrity_msg}"
                    # 完整性校验失败时尝试回滚到恢复前的备份
                    if pre_backup_path:
                        try:
                            self._conn.close()
                            self._conn = None
                            shutil.copy2(pre_backup_path, str(self.db_path))
                            self._init_db()
                        except (OSError, IOError):
                            pass
                    return result

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
        """添加短剧（v5.2.1 新增，v5.3.3 安全加固：XSS 消毒）"""
        now = time.time()
        drama_id = str(uuid.uuid4())

        # v5.3.3 安全加固：XSS 消毒
        title = _sanitize_html(self._validate_str(title, "title", max_len=200))
        platform = _sanitize_html(self._validate_str(platform, "platform", max_len=100))
        rating = self._validate_float(rating, "rating", min_val=0.0, max_val=10.0)
        description = _sanitize_html(self._validate_str(description, "description", max_len=5000))
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
        # v5.3.3 安全加固：LIKE 通配符转义
        safe_query = query[:200] if isinstance(query, str) else ""
        sql = "SELECT * FROM drama_lines WHERE line_text LIKE ? ESCAPE '\\'"
        params = [f"%{_escape_like(safe_query)}%"]

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

    # ===== 记忆关联（v5.2.5 新增）=====

    def link_memories(self, source_id: str, target_id: str,
                      link_type: str = "related", note: str = "") -> Dict[str, Any]:
        """创建记忆关联（双向）"""
        if source_id == target_id:
            return {"success": False, "error": "不能关联自己"}

        # 输入校验
        link_type = link_type.strip()[:50] if link_type else "related"
        note = note.strip()[:500] if note else ""

        conn = self._get_conn()

        # 检查两条记忆是否存在
        for mid in (source_id, target_id):
            row = conn.execute("SELECT id FROM memories WHERE id = ? AND category != 'trash'", (mid,)).fetchone()
            if not row:
                return {"success": False, "error": f"记忆不存在: {mid}"}

        # 检查是否已存在关联（任一方向）
        existing = conn.execute(
            "SELECT id FROM memory_links WHERE (source_id = ? AND target_id = ?) OR (source_id = ? AND target_id = ?)",
            (source_id, target_id, target_id, source_id)
        ).fetchone()
        if existing:
            return {"success": False, "error": "关联已存在"}

        link_id = f"link_{uuid.uuid4().hex[:12]}"
        now = time.time()
        conn.execute(
            "INSERT INTO memory_links (id, source_id, target_id, link_type, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (link_id, source_id, target_id, link_type, note, now)
        )
        conn.commit()
        return {"success": True, "link_id": link_id, "source_id": source_id, "target_id": target_id,
                "link_type": link_type, "note": note}

    def list_links(self, memory_id: str) -> List[Dict[str, Any]]:
        """列出记忆的所有关联（双向）"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT ml.*, m.content as target_content, m.category as target_category
               FROM memory_links ml
               JOIN memories m ON (ml.target_id = m.id AND ml.source_id = ?)
                                  OR (ml.source_id = m.id AND ml.target_id = ?)
               WHERE ml.source_id = ? OR ml.target_id = ?
               ORDER BY ml.created_at DESC""",
            (memory_id, memory_id, memory_id, memory_id)
        ).fetchall()
        results = []
        for row in rows:
            # 确定关联的另一端
            linked_id = row["target_id"] if row["source_id"] == memory_id else row["source_id"]
            results.append({
                "link_id": row["id"],
                "linked_id": linked_id,
                "linked_content": row["target_content"],
                "linked_category": row["target_category"],
                "link_type": row["link_type"],
                "note": row["note"],
                "created_at": row["created_at"],
            })
        return results

    def unlink_memories(self, link_id: str) -> bool:
        """删除记忆关联"""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM memory_links WHERE id = ?", (link_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ===== 记忆版本历史（v5.2.7 新增）=====

    def save_version(self, memory_id: str, content: str, category: str,
                     tags, importance, actor: str = "") -> Dict[str, Any]:
        """保存记忆的历史版本（v5.2.7 新增）"""
        # 输入校验
        if not memory_id or len(memory_id) > 128:
            return {"success": False, "error": "记忆 ID 无效"}
        if not content or len(content) > 100000:
            return {"success": False, "error": "内容无效或过长"}

        conn = self._get_conn()
        try:
            # 检查记忆是否存在
            row = conn.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return {"success": False, "error": "记忆不存在"}

            # 获取当前版本号
            row = conn.execute(
                "SELECT MAX(version_number) FROM memory_versions WHERE memory_id = ?",
                (memory_id,)
            ).fetchone()
            next_version = (row[0] or 0) + 1

            version_id = f"ver_{uuid.uuid4().hex[:12]}"
            now = time.time()
            tags_str = json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else str(tags or "")

            conn.execute(
                """INSERT INTO memory_versions
                   (id, memory_id, version_number, content, category, tags, importance, actor, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (version_id, memory_id, next_version, content, category or "",
                 tags_str, str(importance or ""), actor or "", now)
            )
            conn.commit()
            return {
                "success": True,
                "version_id": version_id,
                "version_number": next_version,
                "memory_id": memory_id,
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}

    def list_versions(self, memory_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """列出记忆的所有历史版本（v5.2.7 新增）"""
        if not memory_id or len(memory_id) > 128:
            return []
        # 限制 limit 范围
        limit = max(1, min(limit, 500))

        conn = self._get_conn()
        rows = conn.execute(
            """SELECT id, version_number, content, category, tags, importance, actor, changed_at
               FROM memory_versions WHERE memory_id = ?
               ORDER BY version_number DESC LIMIT ?""",
            (memory_id, limit)
        ).fetchall()

        versions = []
        for r in rows:
            versions.append({
                "version_id": r[0],
                "version_number": r[1],
                "content": r[2],
                "content_preview": r[2][:80] + ("..." if len(r[2]) > 80 else ""),
                "category": r[3],
                "tags": json.loads(r[4]) if r[4] and r[4].startswith("[") else r[4],
                "importance": r[5],
                "actor": r[6],
                "changed_at": r[7],
            })
        return versions

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取指定版本详情（v5.2.7 新增）"""
        if not version_id or len(version_id) > 128:
            return None
        conn = self._get_conn()
        row = conn.execute(
            """SELECT id, memory_id, version_number, content, category, tags, importance, actor, changed_at
               FROM memory_versions WHERE id = ?""",
            (version_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "version_id": row[0],
            "memory_id": row[1],
            "version_number": row[2],
            "content": row[3],
            "category": row[4],
            "tags": json.loads(row[5]) if row[5] and row[5].startswith("[") else row[5],
            "importance": row[6],
            "actor": row[7],
            "changed_at": row[8],
        }

    def rollback_to_version(self, version_id: str, actor: str = "") -> Dict[str, Any]:
        """回滚记忆到指定历史版本（v5.2.7 新增）

        会先保存当前内容为新版本，再回滚到目标版本。
        """
        if not version_id or len(version_id) > 128:
            return {"success": False, "error": "版本 ID 无效"}

        conn = self._get_conn()
        try:
            # 获取目标版本
            target = conn.execute(
                "SELECT memory_id, content, category, tags, importance FROM memory_versions WHERE id = ?",
                (version_id,)
            ).fetchone()
            if not target:
                return {"success": False, "error": "版本不存在"}

            memory_id = target[0]
            content = target[1]
            category = target[2]
            tags_json = target[3]
            importance = target[4]

            # 获取当前记忆内容（保存为新版本）
            current = conn.execute(
                "SELECT content, category, tags, importance FROM memories WHERE id = ?",
                (memory_id,)
            ).fetchone()
            if not current:
                return {"success": False, "error": "记忆不存在"}

            # 保存当前状态为新版本
            save_result = self.save_version(
                memory_id, current[0], current[1],
                json.loads(current[2]) if current[2] and current[2].startswith("[") else current[2],
                current[3], actor
            )

            # 回滚：更新记忆为目标版本的内容
            conn.execute(
                """UPDATE memories SET content = ?, category = ?, tags = ?, importance = ?,
                   updated_at = ? WHERE id = ?""",
                (content, category, tags_json, importance, time.time(), memory_id)
            )
            conn.commit()

            return {
                "success": True,
                "memory_id": memory_id,
                "rolled_back_to_version": target[1] if len(target) > 1 else None,
                "saved_current_as_version": save_result.get("version_number"),
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}

    # ===== 置顶功能（v5.2.5 新增）=====

    def pin_memory(self, memory_id: str) -> bool:
        """置顶记忆"""
        return self.update_memory(entry_id=memory_id, pinned=True)

    def unpin_memory(self, memory_id: str) -> bool:
        """取消置顶"""
        return self.update_memory(entry_id=memory_id, pinned=False)

    def list_pinned(self, limit: int = 50) -> List[MemoryEntry]:
        """列出所有置顶记忆"""
        limit = max(1, min(500, int(limit)))
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE pinned = 1 AND category != 'trash' ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]
