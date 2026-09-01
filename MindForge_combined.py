#!/usr/bin/env python3
"""
MindForge - 智能记忆管理系统
带 AI 短剧创作功能的完整记忆管理 CLI

核心能力：
- 分层记忆存储（工作记忆 / 情景记忆 / 语义记忆 / 程序记忆）
- FTS5 全文检索 + 向量语义检索混合召回
- 遗忘曲线与记忆巩固（spaced repetition）
- 记忆快照、去重、健康检查
- Agent 增强：记忆画像、情感追踪、影响力图谱、冲突检测
- AI 短剧创作：短剧/场次/角色/台词管理，节奏分析，角色关系网，剧情伏笔追踪
"""

import argparse
import json
import os
import sys
import time
import uuid
import hashlib
import sqlite3
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# 配置与常量
# ============================================================

VERSION = "5.5.8"
DEFAULT_DB_PATH = os.path.expanduser("~/.mindforge/memory.db")
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.mindforge/config.json")

# 记忆层级
MEMORY_LAYERS = ["working", "episodic", "semantic", "procedural"]

# 遗忘曲线参数（Ebbinghaus 简化模型）
FORGETTING_CURVE = {
    "working": {"half_life_hours": 1.0, "retention_threshold": 0.3},
    "episodic": {"half_life_hours": 24.0, "retention_threshold": 0.2},
    "semantic": {"half_life_hours": 720.0, "retention_threshold": 0.1},
    "procedural": {"half_life_hours": 1440.0, "retention_threshold": 0.05},
}

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mindforge")


# ============================================================
# 数据模型
# ============================================================

@dataclass
class MemoryEntry:
    """单条记忆条目"""
    id: str = ""
    content: str = ""
    layer: str = "episodic"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    last_accessed: str = ""
    strength: float = 1.0  # 记忆强度 0-1
    importance: float = 0.5  # 重要性 0-1
    source: str = "manual"  # manual / agent / import / api
    encrypted: bool = False


@dataclass
class MemorySnapshot:
    """记忆快照"""
    id: str = ""
    name: str = ""
    description: str = ""
    created_at: str = ""
    entry_count: int = 0
    total_size_bytes: int = 0
    layer_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class Drama:
    """AI 短剧"""
    id: str = ""
    title: str = ""
    genre: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    total_scenes: int = 0
    total_lines: int = 0
    status: str = "draft"  # draft / writing / completed / archived
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DramaScene:
    """短剧场次"""
    id: str = ""
    drama_id: str = ""
    scene_number: int = 0
    title: str = ""
    location: str = ""
    time_of_day: str = ""
    summary: str = ""
    created_at: str = ""
    line_count: int = 0
    emotional_tone: str = "neutral"
    pacing: str = "medium"  # slow / medium / fast


@dataclass
class DramaCharacter:
    """短剧角色"""
    id: str = ""
    drama_id: str = ""
    name: str = ""
    role_type: str = "supporting"  # protagonist / antagonist / supporting / minor
    description: str = ""
    personality_traits: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)  # character_id -> relationship
    total_lines: int = 0
    first_appearance_scene: int = 0
    last_appearance_scene: int = 0


@dataclass
class DramaLine:
    """短剧台词"""
    id: str = ""
    drama_id: str = ""
    scene_id: str = ""
    character_id: str = ""
    character_name: str = ""
    line_number: int = 0
    content: str = ""
    emotion: str = "neutral"
    action: str = ""  # 舞台动作说明
    created_at: str = ""


@dataclass
class Foreshadowing:
    """剧情伏笔"""
    id: str = ""
    drama_id: str = ""
    description: str = ""
    planted_scene: int = 0
    resolved_scene: Optional[int] = None
    status: str = "active"  # active / resolved / abandoned
    importance: float = 0.5
    related_characters: List[str] = field(default_factory=list)
    notes: str = ""


# ============================================================
# 加密模块
# ============================================================

class EncryptionManager:
    """记忆内容加密管理"""

    def __init__(self, password: Optional[str] = None):
        self._password = password
        self._enabled = password is not None and len(password) > 0
        self._key: Optional[bytes] = None
        if self._enabled:
            self._derive_key()

    def _derive_key(self):
        """从密码派生加密密钥"""
        if not self._password:
            return
        # 使用 PBKDF2 派生密钥
        salt = b"mindforge_encryption_salt_v1"
        self._key = hashlib.pbkdf2_hmac(
            "sha256", self._password.encode("utf-8"), salt, 100000, dklen=32
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def encrypt(self, plaintext: str) -> str:
        """加密文本"""
        if not self._enabled or not self._key:
            return plaintext
        try:
            from cryptography.fernet import Fernet
            import base64

            # Fernet 需要 32 字节 url-safe base64 编码的 key
            fernet_key = base64.urlsafe_b64encode(self._key)
            f = Fernet(fernet_key)
            encrypted = f.encrypt(plaintext.encode("utf-8"))
            return f"ENC:{encrypted.decode('utf-8')}"
        except ImportError:
            logger.warning("cryptography 未安装，加密不可用")
            return plaintext
        except Exception as e:
            logger.error(f"加密失败: {e}")
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """解密文本"""
        if not ciphertext or not ciphertext.startswith("ENC:"):
            return ciphertext
        if not self._enabled or not self._key:
            logger.error("尝试解密但加密未启用")
            return ciphertext
        try:
            from cryptography.fernet import Fernet
            import base64

            fernet_key = base64.urlsafe_b64encode(self._key)
            f = Fernet(fernet_key)
            encrypted_data = ciphertext[4:].encode("utf-8")
            decrypted = f.decrypt(encrypted_data)
            return decrypted.decode("utf-8")
        except ImportError:
            logger.warning("cryptography 未安装，解密不可用")
            return ciphertext
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return ciphertext


# ============================================================
# 嵌入模型（轻量本地实现）
# ============================================================

class LocalEmbeddingProvider:
    """本地轻量嵌入模型（基于词袋 + TF-IDF 的简化实现）"""

    def __init__(self, dim: int = 128):
        self.dim = dim
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._doc_count = 0

    def _tokenize(self, text: str) -> List[str]:
        """简单分词（中英文混合）"""
        text = text.lower()
        tokens = []
        current = []
        for ch in text:
            if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
                current.append(ch)
            else:
                if current:
                    tokens.append(''.join(current))
                    current = []
        if current:
            tokens.append(''.join(current))
        # 中文单字也作为 token
        final_tokens = []
        for t in tokens:
            if any('\u4e00' <= c <= '\u9fff' for c in t) and len(t) > 1:
                final_tokens.extend(list(t))
            final_tokens.append(t)
        return final_tokens

    def embed(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        tokens = self._tokenize(text)
        vec = [0.0] * self.dim
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0
        # L2 归一化
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        return dot


# ============================================================
# 网络文件系统检测
# ============================================================

def _is_network_fs(path: str) -> bool:
    """检测路径是否位于网络文件系统上

    网络文件系统上 SQLite WAL 模式不可靠，可能导致 SIGBUS。
    检测范围：NFS、CIFS/SMB、SSHFS、9p、FUSE（含 fuseblk）等。
    """
    network_fs_types = {
        "nfs", "nfs4", "cifs", "smb", "smbfs",
        "sshfs", "9p", "9p2000.l",
        "fuse", "fuseblk", "fuse.sshfs", "fuse.gocryptfs",
        "fuse.rclone", "fuse.mergerfs", "fuse.ecryptfs",
    }
    try:
        import subprocess
        result = subprocess.run(
            ["stat", "-f", "-c", "%T", path],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            fs_type = result.stdout.strip().lower()
            if fs_type in network_fs_types:
                return True
            # FUSE 前缀整体纳入
            if fs_type.startswith("fuse"):
                return True
    except Exception:
        pass
    return False


# ============================================================
# 核心记忆存储
# ============================================================

class MemoryCore:
    """MindForge 核心记忆存储引擎"""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        password: Optional[str] = None,
        embedding_dim: int = 128,
    ):
        self.db_path = db_path
        self.encryption = EncryptionManager(password)
        self.embedding = LocalEmbeddingProvider(dim=embedding_dim)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # 检测网络文件系统，决定是否启用 WAL
        use_wal = not _is_network_fs(self.db_path)
        journal_mode = "WAL" if use_wal else "DELETE"

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(f"PRAGMA journal_mode={journal_mode}")
        self._conn.execute("PRAGMA foreign_keys=ON")

        if not use_wal:
            logger.info(
                f"检测到网络文件系统或 FUSE 挂载，SQLite 使用 DELETE 模式而非 WAL（路径: {self.db_path}）"
            )

        self._create_tables()

    def _create_tables(self):
        """创建数据库表"""
        assert self._conn is not None
        cursor = self._conn.cursor()

        # 记忆主表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                layer TEXT NOT NULL DEFAULT 'episodic',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                embedding TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                strength REAL DEFAULT 1.0,
                importance REAL DEFAULT 0.5,
                source TEXT DEFAULT 'manual',
                encrypted INTEGER DEFAULT 0,
                content_hash TEXT
            )
        """)

        # FTS5 全文索引
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                tags,
                content_rowid,
                tokenize='unicode61'
            )
        """)

        # 记忆快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                entry_count INTEGER DEFAULT 0,
                total_size_bytes INTEGER DEFAULT 0,
                layer_distribution TEXT DEFAULT '{}'
            )
        """)

        # 短剧表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dramas (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                genre TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                total_scenes INTEGER DEFAULT 0,
                total_lines INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                metadata TEXT DEFAULT '{}'
            )
        """)

        # 短剧场次表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drama_scenes (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                scene_number INTEGER NOT NULL,
                title TEXT DEFAULT '',
                location TEXT DEFAULT '',
                time_of_day TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                line_count INTEGER DEFAULT 0,
                emotional_tone TEXT DEFAULT 'neutral',
                pacing TEXT DEFAULT 'medium',
                FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
            )
        """)

        # 短剧角色表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drama_characters (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role_type TEXT DEFAULT 'supporting',
                description TEXT DEFAULT '',
                personality_traits TEXT DEFAULT '[]',
                relationships TEXT DEFAULT '{}',
                total_lines INTEGER DEFAULT 0,
                first_appearance_scene INTEGER DEFAULT 0,
                last_appearance_scene INTEGER DEFAULT 0,
                FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
            )
        """)

        # 短剧台词表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drama_lines (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                scene_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                character_name TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                emotion TEXT DEFAULT 'neutral',
                action TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
                FOREIGN KEY (scene_id) REFERENCES drama_scenes(id) ON DELETE CASCADE
            )
        """)

        # 剧情伏笔表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS foreshadowings (
                id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                description TEXT NOT NULL,
                planted_scene INTEGER DEFAULT 0,
                resolved_scene INTEGER,
                status TEXT DEFAULT 'active',
                importance REAL DEFAULT 0.5,
                related_characters TEXT DEFAULT '[]',
                notes TEXT DEFAULT '',
                FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_layer ON memories(layer)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_strength ON memories(strength)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_drama ON drama_scenes(drama_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_scene ON drama_lines(scene_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_character ON drama_lines(character_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_foreshadow_drama ON foreshadowings(drama_id)")

        self._conn.commit()

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _gen_id(self) -> str:
        return str(uuid.uuid4())

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ----------------------------------------------------------
    # 记忆增删改查
    # ----------------------------------------------------------

    def add(
        self,
        content: str,
        layer: str = "episodic",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        source: str = "manual",
    ) -> MemoryEntry:
        """添加一条记忆"""
        assert self._conn is not None
        now = self._now()
        entry_id = self._gen_id()
        tags = tags or []
        metadata = metadata or {}

        # 生成嵌入向量
        embedding_vec = self.embedding.embed(content)
        embedding_json = json.dumps(embedding_vec)

        # 加密处理
        stored_content = content
        encrypted_flag = 0
        if self.encryption.enabled:
            stored_content = self.encryption.encrypt(content)
            encrypted_flag = 1

        content_hash = self._content_hash(content)

        entry = MemoryEntry(
            id=entry_id,
            content=content,  # 返回对象保留明文 content 用于回显
            layer=layer,
            tags=tags,
            metadata=metadata,
            created_at=now,
            updated_at=now,
            last_accessed=now,
            strength=1.0,
            importance=importance,
            source=source,
            encrypted=bool(encrypted_flag),
        )

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO memories
            (id, content, layer, tags, metadata, embedding, created_at, updated_at,
             access_count, last_accessed, strength, importance, source, encrypted, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, stored_content, layer, json.dumps(tags), json.dumps(metadata),
            embedding_json, now, now, 0, now, 1.0, importance, source, encrypted_flag, content_hash
        ))

        # 更新 FTS 索引
        cursor.execute("""
            INSERT INTO memories_fts (rowid, content, tags, content_rowid)
            VALUES (?, ?, ?, ?)
        """, (cursor.lastrowid, content, " ".join(tags), cursor.lastrowid))

        self._conn.commit()
        return entry

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取单条记忆"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_entry(row)

    def delete(self, memory_id: str) -> bool:
        """删除一条记忆"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        # 获取 rowid 用于 FTS 删除
        cursor.execute("SELECT rowid FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            return False
        rowid = row["rowid"]

        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        cursor.execute("DELETE FROM memories_fts WHERE rowid = ?", (rowid,))
        self._conn.commit()
        return True

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: Optional[float] = None,
        layer: Optional[str] = None,
    ) -> Optional[MemoryEntry]:
        """更新记忆"""
        assert self._conn is not None
        entry = self.get(memory_id)
        if not entry:
            return None

        now = self._now()
        updates = []
        params = []

        if content is not None:
            stored = self.encryption.encrypt(content) if self.encryption.enabled else content
            updates.append("content = ?")
            params.append(stored)
            updates.append("content_hash = ?")
            params.append(self._content_hash(content))
            # 更新嵌入
            emb = self.embedding.embed(content)
            updates.append("embedding = ?")
            params.append(json.dumps(emb))
            entry.content = content

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
            entry.tags = tags

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
            entry.metadata = metadata

        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)
            entry.importance = importance

        if layer is not None:
            updates.append("layer = ?")
            params.append(layer)
            entry.layer = layer

        updates.append("updated_at = ?")
        params.append(now)
        params.append(memory_id)

        cursor = self._conn.cursor()
        cursor.execute(
            f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
            params
        )
        self._conn.commit()
        entry.updated_at = now
        return entry

    def list(
        self,
        layer: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> List[MemoryEntry]:
        """列出记忆"""
        assert self._conn is not None
        query = "SELECT * FROM memories WHERE 1=1"
        params = []

        if layer:
            query += " AND layer = ?"
            params.append(layer)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

        order_dir = "DESC" if descending else "ASC"
        query += f" ORDER BY {order_by} {order_dir} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search(
        self,
        query: str,
        limit: int = 20,
        layer: Optional[str] = None,
        min_score: float = 0.1,
    ) -> List[Tuple[MemoryEntry, float]]:
        """混合检索：FTS 全文 + 向量语义"""
        assert self._conn is not None
        results: Dict[str, Tuple[MemoryEntry, float]] = {}

        # 1. FTS 全文检索
        try:
            cursor = self._conn.cursor()
            fts_query = f"SELECT m.*, bm25(memories_fts) as score FROM memories_fts JOIN memories m ON memories_fts.rowid = m.rowid WHERE memories_fts MATCH ? ORDER BY score LIMIT ?"
            cursor.execute(fts_query, (query, limit * 2))
            rows = cursor.fetchall()
            for row in rows:
                entry = self._row_to_entry(row)
                # bm25 分数越小越相关，转换为 0-1 相似度
                score = max(0.0, 1.0 / (1.0 + abs(row["score"]) / 10.0))
                if score >= min_score:
                    results[entry.id] = (entry, score)
        except Exception as e:
            logger.debug(f"FTS 检索异常: {e}")

        # 2. 向量语义检索
        try:
            query_emb = self.embedding.embed(query)
            all_entries = self.list(limit=500, order_by="created_at")
            for entry in all_entries:
                if layer and entry.layer != layer:
                    continue
                if entry.embedding:
                    sim = self.embedding.cosine_similarity(query_emb, entry.embedding)
                    if sim >= min_score:
                        if entry.id in results:
                            # 混合分数：取加权平均
                            _, fts_score = results[entry.id]
                            combined = 0.6 * fts_score + 0.4 * sim
                            results[entry.id] = (entry, combined)
                        else:
                            results[entry.id] = (entry, sim * 0.8)  # 纯语义检索略降权
        except Exception as e:
            logger.debug(f"向量检索异常: {e}")

        # 按分数排序
        sorted_results = sorted(results.values(), key=lambda x: x[1], reverse=True)
        return sorted_results[:limit]

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """将数据库行转换为 MemoryEntry"""
        content = row["content"]
        encrypted = bool(row["encrypted"])
        if encrypted and self.encryption.enabled:
            content = self.encryption.decrypt(content)

        embedding = None
        if row["embedding"]:
            try:
                embedding = json.loads(row["embedding"])
            except Exception:
                pass

        return MemoryEntry(
            id=row["id"],
            content=content,
            layer=row["layer"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=embedding,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"] or "",
            strength=row["strength"],
            importance=row["importance"],
            source=row["source"],
            encrypted=encrypted,
        )

    # ----------------------------------------------------------
    # 记忆统计与健康检查
    # ----------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """获取记忆库统计信息"""
        assert self._conn is not None
        cursor = self._conn.cursor()

        stats: Dict[str, Any] = {"total_entries": 0, "by_layer": {}, "by_source": {}, "total_tags": 0}

        cursor.execute("SELECT COUNT(*) as cnt FROM memories")
        stats["total_entries"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT layer, COUNT(*) as cnt FROM memories GROUP BY layer")
        for row in cursor.fetchall():
            stats["by_layer"][row["layer"]] = row["cnt"]

        cursor.execute("SELECT source, COUNT(*) as cnt FROM memories GROUP BY source")
        for row in cursor.fetchall():
            stats["by_source"][row["source"]] = row["cnt"]

        # 统计标签
        cursor.execute("SELECT tags FROM memories")
        all_tags = set()
        for row in cursor.fetchall():
            try:
                tags = json.loads(row["tags"])
                all_tags.update(tags)
            except Exception:
                pass
        stats["total_tags"] = len(all_tags)

        # 加密状态
        stats["encryption_enabled"] = self.encryption.enabled

        # 数据库大小
        try:
            stats["db_size_bytes"] = os.path.getsize(self.db_path)
        except Exception:
            stats["db_size_bytes"] = 0

        return stats

    def health_check(self) -> Dict[str, Any]:
        """记忆库健康检查"""
        assert self._conn is not None
        results: Dict[str, Any] = {"status": "healthy", "issues": [], "warnings": []}

        cursor = self._conn.cursor()

        # 1. 检查数据库完整性
        try:
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            if integrity != "ok":
                results["issues"].append(f"数据库完整性异常: {integrity}")
                results["status"] = "unhealthy"
        except Exception as e:
            results["issues"].append(f"完整性检查失败: {e}")
            results["status"] = "unhealthy"

        # 2. 检查孤儿 FTS 条目
        try:
            cursor.execute("SELECT COUNT(*) as cnt FROM memories_fts WHERE rowid NOT IN (SELECT rowid FROM memories)")
            orphan_count = cursor.fetchone()["cnt"]
            if orphan_count > 0:
                results["warnings"].append(f"发现 {orphan_count} 条孤儿 FTS 索引条目")
        except Exception:
            pass

        # 3. 检查重复内容
        try:
            cursor.execute("SELECT content_hash, COUNT(*) as cnt FROM memories GROUP BY content_hash HAVING cnt > 1")
            duplicates = cursor.fetchall()
            if duplicates:
                total_dup = sum(d["cnt"] - 1 for d in duplicates)
                results["warnings"].append(f"发现 {len(duplicates)} 组重复内容，共 {total_dup} 条冗余")
        except Exception:
            pass

        # 4. 检查弱记忆（strength 过低）
        try:
            cursor.execute("SELECT COUNT(*) as cnt FROM memories WHERE strength < 0.1")
            weak_count = cursor.fetchone()["cnt"]
            if weak_count > 0:
                results["warnings"].append(f"{weak_count} 条记忆强度低于 0.1，可能即将遗忘")
        except Exception:
            pass

        # 5. 检查 WAL 模式
        try:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            results["journal_mode"] = mode
            if _is_network_fs(self.db_path) and mode == "wal":
                results["issues"].append("网络文件系统上启用了 WAL 模式，可能导致数据损坏")
                results["status"] = "unhealthy"
        except Exception:
            pass

        if results["issues"]:
            results["status"] = "unhealthy"
        elif results["warnings"]:
            results["status"] = "degraded"

        return results

    # ----------------------------------------------------------
    # 记忆去重
    # ----------------------------------------------------------

    def deduplicate(self, threshold: float = 0.95) -> Dict[str, Any]:
        """记忆去重：基于内容哈希和语义相似度"""
        assert self._conn is not None
        results = {"removed": 0, "duplicates_found": 0, "details": []}

        cursor = self._conn.cursor()

        # 1. 精确去重（相同 content_hash）
        cursor.execute("""
            SELECT content_hash, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
            FROM memories
            GROUP BY content_hash
            HAVING cnt > 1
        """)
        exact_dups = cursor.fetchall()

        for row in exact_dups:
            ids = row["ids"].split(",")
            # 保留最早创建的，删除其余
            entries = [self.get(mid) for mid in ids]
            entries.sort(key=lambda e: e.created_at if e else "")
            keep_id = entries[0].id if entries[0] else ids[0]

            for mid in ids:
                if mid != keep_id:
                    if self.delete(mid):
                        results["removed"] += 1
                        results["details"].append({"id": mid, "reason": "exact_duplicate"})
            results["duplicates_found"] += row["cnt"] - 1

        # 2. 语义去重（高相似度）
        all_entries = self.list(limit=1000, order_by="created_at")
        removed_ids = set(d["id"] for d in results["details"])

        for i, entry1 in enumerate(all_entries):
            if entry1.id in removed_ids:
                continue
            for entry2 in all_entries[i + 1:]:
                if entry2.id in removed_ids:
                    continue
                if entry1.embedding and entry2.embedding:
                    sim = self.embedding.cosine_similarity(entry1.embedding, entry2.embedding)
                    if sim >= threshold:
                        # 保留重要性更高的，或更新的
                        keep = entry1 if entry1.importance >= entry2.importance else entry2
                        remove = entry2 if keep.id == entry1.id else entry1
                        if self.delete(remove.id):
                            results["removed"] += 1
                            results["duplicates_found"] += 1
                            removed_ids.add(remove.id)
                            results["details"].append({
                                "id": remove.id,
                                "reason": f"semantic_duplicate(sim={sim:.3f})",
                                "kept_id": keep.id,
                            })

        return results

    # ----------------------------------------------------------
    # 记忆快照
    # ----------------------------------------------------------

    def create_snapshot(self, name: str, description: str = "") -> MemorySnapshot:
        """创建记忆快照"""
        assert self._conn is not None
        now = self._now()
        snap_id = self._gen_id()

        stats = self.stats()
        layer_dist = stats.get("by_layer", {})
        total_size = stats.get("db_size_bytes", 0)

        snapshot = MemorySnapshot(
            id=snap_id,
            name=name,
            description=description,
            created_at=now,
            entry_count=stats["total_entries"],
            total_size_bytes=total_size,
            layer_distribution=layer_dist,
        )

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO snapshots (id, name, description, created_at, entry_count, total_size_bytes, layer_distribution)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (snap_id, name, description, now, snapshot.entry_count, total_size, json.dumps(layer_dist)))
        self._conn.commit()
        return snapshot

    def list_snapshots(self) -> List[MemorySnapshot]:
        """列出所有快照"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM snapshots ORDER BY created_at DESC")
        rows = cursor.fetchall()
        snapshots = []
        for row in rows:
            snapshots.append(MemorySnapshot(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                entry_count=row["entry_count"],
                total_size_bytes=row["total_size_bytes"],
                layer_distribution=json.loads(row["layer_distribution"]) if row["layer_distribution"] else {},
            ))
        return snapshots

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ----------------------------------------------------------
    # 遗忘曲线与巩固
    # ----------------------------------------------------------

    def apply_forgetting(self) -> Dict[str, Any]:
        """应用遗忘曲线，更新记忆强度"""
        assert self._conn is not None
        results = {"updated": 0, "weakened": 0, "forgotten": 0}

        cursor = self._conn.cursor()
        cursor.execute("SELECT id, layer, strength, created_at, last_accessed, access_count FROM memories")
        rows = cursor.fetchall()

        now = datetime.utcnow()

        for row in rows:
            layer = row["layer"]
            params = FORGETTING_CURVE.get(layer, FORGETTING_CURVE["episodic"])
            half_life = params["half_life_hours"]

            # 计算时间衰减
            last_access = row["last_accessed"] or row["created_at"]
            try:
                last_dt = datetime.fromisoformat(last_access.replace("Z", "+00:00").replace("+00:00", ""))
                hours_passed = (now - last_dt).total_seconds() / 3600
            except Exception:
                hours_passed = 0

            # 指数衰减：strength *= 0.5^(t/half_life)
            decay_factor = 0.5 ** (hours_passed / half_life) if half_life > 0 else 1.0

            # 访问次数增强记忆
            access_boost = min(1.0, row["access_count"] * 0.05)

            old_strength = row["strength"]
            new_strength = min(1.0, old_strength * decay_factor + access_boost * 0.3)
            new_strength = max(0.0, new_strength)

            if new_strength < old_strength * 0.9:
                results["weakened"] += 1
            if new_strength < params["retention_threshold"]:
                results["forgotten"] += 1

            cursor.execute(
                "UPDATE memories SET strength = ?, updated_at = ? WHERE id = ?",
                (new_strength, self._now(), row["id"])
            )
            results["updated"] += 1

        self._conn.commit()
        return results

    def consolidate(self, memory_id: str) -> Optional[MemoryEntry]:
        """巩固记忆（提升强度和重要性）"""
        entry = self.get(memory_id)
        if not entry:
            return None

        new_strength = min(1.0, entry.strength + 0.3)
        new_importance = min(1.0, entry.importance + 0.1)

        return self.update(memory_id, importance=new_importance)

    def recall_recent(self, hours: int = 24, limit: int = 50) -> List[MemoryEntry]:
        """回忆最近 N 小时的记忆"""
        assert self._conn is not None
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM memories WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
            (cutoff, limit)
        )
        rows = cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_context(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """获取与查询相关的记忆上下文"""
        results = self.search(query, limit=limit)
        return [entry for entry, _ in results]

    # ----------------------------------------------------------
    # Agent 增强功能
    # ----------------------------------------------------------

    def get_memory_profile(self) -> Dict[str, Any]:
        """生成记忆画像：总结记忆库的特征和偏好"""
        stats = self.stats()
        recent = self.recall_recent(hours=168, limit=100)  # 最近 7 天

        profile: Dict[str, Any] = {
            "total_memories": stats["total_entries"],
            "dominant_layer": max(stats["by_layer"], key=stats["by_layer"].get) if stats["by_layer"] else "unknown",
            "encryption_enabled": stats.get("encryption_enabled", False),
            "recent_activity": len(recent),
            "top_tags": [],
            "common_sources": [],
        }

        # 统计热门标签
        tag_counts: Dict[str, int] = {}
        for entry in recent:
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        profile["top_tags"] = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # 统计来源分布
        source_counts: Dict[str, int] = {}
        all_entries = self.list(limit=500)
        for entry in all_entries:
            source_counts[entry.source] = source_counts.get(entry.source, 0) + 1
        profile["common_sources"] = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)

        return profile

    def get_emotional_timeline(self, days: int = 30) -> List[Dict[str, Any]]:
        """提取情感时间线（从 metadata 中分析情感倾向）"""
        recent = self.recall_recent(hours=days * 24, limit=500)
        timeline = []

        for entry in recent:
            emotion = entry.metadata.get("emotion", "neutral")
            sentiment = entry.metadata.get("sentiment", 0.0)
            timeline.append({
                "id": entry.id,
                "date": entry.created_at,
                "emotion": emotion,
                "sentiment": sentiment,
                "layer": entry.layer,
                "preview": entry.content[:100] if entry.content else "",
            })

        return timeline

    def get_influence_graph(self, depth: int = 2) -> Dict[str, Any]:
        """构建记忆影响力图谱（基于标签和元数据关联）"""
        all_entries = self.list(limit=200, order_by="importance", descending=True)

        nodes = []
        edges = []
        node_ids = set()

        # 以高重要性记忆为核心节点
        core_entries = [e for e in all_entries if e.importance >= 0.7][:20]

        for entry in core_entries:
            if entry.id not in node_ids:
                nodes.append({
                    "id": entry.id,
                    "label": entry.content[:50] if entry.content else "",
                    "importance": entry.importance,
                    "layer": entry.layer,
                    "tags": entry.tags,
                })
                node_ids.add(entry.id)

        # 基于共享标签建立边
        for i, e1 in enumerate(core_entries):
            for e2 in core_entries[i + 1:]:
                shared_tags = set(e1.tags) & set(e2.tags)
                if shared_tags:
                    edges.append({
                        "source": e1.id,
                        "target": e2.id,
                        "weight": len(shared_tags),
                        "shared_tags": list(shared_tags),
                    })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "avg_degree": (2 * len(edges) / len(nodes)) if nodes else 0,
            },
        }

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """检测记忆间的冲突（矛盾信息）"""
        all_entries = self.list(limit=500, order_by="created_at")
        conflicts = []

        # 基于关键词对立检测简单冲突
        contradiction_pairs = [
            ("是", "不是"), ("可以", "不可以"), ("能", "不能"),
            ("会", "不会"), ("有", "没有"), ("对", "错"),
            ("真", "假"), ("成功", "失败"), ("喜欢", "讨厌"),
        ]

        for i, e1 in enumerate(all_entries):
            for e2 in all_entries[i + 1:]:
                if e1.layer != e2.layer:
                    continue
                # 检查是否包含对立关键词
                for pos, neg in contradiction_pairs:
                    e1_has_pos = pos in e1.content and neg not in e1.content
                    e1_has_neg = neg in e1.content and pos not in e1.content
                    e2_has_pos = pos in e2.content and neg not in e2.content
                    e2_has_neg = neg in e2.content and pos not in e2.content

                    if (e1_has_pos and e2_has_neg) or (e1_has_neg and e2_has_pos):
                        # 检查是否有共享标签或相似主题
                        shared_tags = set(e1.tags) & set(e2.tags)
                        if shared_tags or e1.embedding and e2.embedding:
                            sim = 0.0
                            if e1.embedding and e2.embedding:
                                sim = self.embedding.cosine_similarity(e1.embedding, e2.embedding)
                            if shared_tags or sim > 0.5:
                                conflicts.append({
                                    "type": "contradiction",
                                    "memory1": {"id": e1.id, "preview": e1.content[:100]},
                                    "memory2": {"id": e2.id, "preview": e2.content[:100]},
                                    "contradiction_keywords": [pos, neg],
                                    "shared_tags": list(shared_tags),
                                    "semantic_similarity": round(sim, 3),
                                    "severity": "high" if sim > 0.7 else "medium",
                                })
                                break

        return conflicts

    def get_conflict_stats(self) -> Dict[str, Any]:
        """获取冲突统计"""
        stats = {
            "total_conflicts": 0,
            "by_type": {},
            "by_severity": {},
            "active": 0,
            "resolved": 0,
        }
        # === 代码截断，后续逻辑待补充 ===
        return stats


# ============================================================
# AI 短剧管理器
# ============================================================

class DramaManager:
    """AI 短剧创作管理器"""

    def __init__(self, core: MemoryCore):
        self.core = core
        self._conn = core._conn

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _gen_id(self) -> str:
        return str(uuid.uuid4())

    # ----------------------------------------------------------
    # 短剧管理
    # ----------------------------------------------------------

    def create_drama(self, title: str, genre: str = "", description: str = "") -> Drama:
        """创建新短剧"""
        assert self._conn is not None
        now = self._now()
        drama_id = self._gen_id()

        drama = Drama(
            id=drama_id,
            title=title,
            genre=genre,
            description=description,
            created_at=now,
            updated_at=now,
            status="draft",
        )

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO dramas (id, title, genre, description, created_at, updated_at, total_scenes, total_lines, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'draft', '{}')
        """, (drama_id, title, genre, description, now, now))
        self._conn.commit()
        return drama

    def get_drama(self, drama_id: str) -> Optional[Drama]:
        """获取短剧详情"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM dramas WHERE id = ?", (drama_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return Drama(
            id=row["id"],
            title=row["title"],
            genre=row["genre"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            total_scenes=row["total_scenes"],
            total_lines=row["total_lines"],
            status=row["status"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def list_dramas(self, status: Optional[str] = None, limit: int = 50) -> List[Drama]:
        """列出短剧"""
        assert self._conn is not None
        query = "SELECT * FROM dramas"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [Drama(
            id=r["id"], title=r["title"], genre=r["genre"],
            description=r["description"], created_at=r["created_at"],
            updated_at=r["updated_at"], total_scenes=r["total_scenes"],
            total_lines=r["total_lines"], status=r["status"],
            metadata=json.loads(r["metadata"]) if r["metadata"] else {},
        ) for r in rows]

    def update_drama(self, drama_id: str, **kwargs) -> Optional[Drama]:
        """更新短剧信息"""
        assert self._conn is not None
        allowed = {"title", "genre", "description", "status", "metadata"}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in allowed:
                if key == "metadata":
                    value = json.dumps(value)
                updates.append(f"{key} = ?")
                params.append(value)
        if not updates:
            return self.get_drama(drama_id)
        updates.append("updated_at = ?")
        params.append(self._now())
        params.append(drama_id)

        cursor = self._conn.cursor()
        cursor.execute(f"UPDATE dramas SET {', '.join(updates)} WHERE id = ?", params)
        self._conn.commit()
        return self.get_drama(drama_id)

    def delete_drama(self, drama_id: str) -> bool:
        """删除短剧（级联删除场次、角色、台词、伏笔）"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM dramas WHERE id = ?", (drama_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ----------------------------------------------------------
    # 场次管理
    # ----------------------------------------------------------

    def add_scene(
        self, drama_id: str, title: str = "", location: str = "",
        time_of_day: str = "", summary: str = "", emotional_tone: str = "neutral",
        pacing: str = "medium",
    ) -> Optional[DramaScene]:
        """添加场次"""
        assert self._conn is not None
        drama = self.get_drama(drama_id)
        if not drama:
            return None

        now = self._now()
        scene_id = self._gen_id()
        scene_number = drama.total_scenes + 1

        scene = DramaScene(
            id=scene_id,
            drama_id=drama_id,
            scene_number=scene_number,
            title=title,
            location=location,
            time_of_day=time_of_day,
            summary=summary,
            created_at=now,
            emotional_tone=emotional_tone,
            pacing=pacing,
        )

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO drama_scenes (id, drama_id, scene_number, title, location, time_of_day, summary, created_at, line_count, emotional_tone, pacing)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (scene_id, drama_id, scene_number, title, location, time_of_day, summary, now, emotional_tone, pacing))

        # 更新短剧场次计数
        cursor.execute("UPDATE dramas SET total_scenes = total_scenes + 1, updated_at = ? WHERE id = ?", (now, drama_id))
        self._conn.commit()
        return scene

    def list_scenes(self, drama_id: str) -> List[DramaScene]:
        """列出短剧所有场次"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM drama_scenes WHERE drama_id = ? ORDER BY scene_number", (drama_id,))
        rows = cursor.fetchall()
        return [DramaScene(
            id=r["id"], drama_id=r["drama_id"], scene_number=r["scene_number"],
            title=r["title"], location=r["location"], time_of_day=r["time_of_day"],
            summary=r["summary"], created_at=r["created_at"], line_count=r["line_count"],
            emotional_tone=r["emotional_tone"], pacing=r["pacing"],
        ) for r in rows]

    # ----------------------------------------------------------
    # 角色管理
    # ----------------------------------------------------------

    def add_character(
        self, drama_id: str, name: str, role_type: str = "supporting",
        description: str = "", personality_traits: Optional[List[str]] = None,
    ) -> Optional[DramaCharacter]:
        """添加角色"""
        assert self._conn is not None
        drama = self.get_drama(drama_id)
        if not drama:
            return None

        char_id = self._gen_id()
        character = DramaCharacter(
            id=char_id,
            drama_id=drama_id,
            name=name,
            role_type=role_type,
            description=description,
            personality_traits=personality_traits or [],
        )

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO drama_characters (id, drama_id, name, role_type, description, personality_traits, relationships, total_lines, first_appearance_scene, last_appearance_scene)
            VALUES (?, ?, ?, ?, ?, ?, '{}', 0, 0, 0)
        """, (char_id, drama_id, name, role_type, description, json.dumps(personality_traits or [])))
        self._conn.commit()
        return character

    def list_characters(self, drama_id: str) -> List[DramaCharacter]:
        """列出短剧所有角色"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM drama_characters WHERE drama_id = ? ORDER BY role_type, name", (drama_id,))
        rows = cursor.fetchall()
        return [DramaCharacter(
            id=r["id"], drama_id=r["drama_id"], name=r["name"],
            role_type=r["role_type"], description=r["description"],
            personality_traits=json.loads(r["personality_traits"]) if r["personality_traits"] else [],
            relationships=json.loads(r["relationships"]) if r["relationships"] else {},
            total_lines=r["total_lines"],
            first_appearance_scene=r["first_appearance_scene"],
            last_appearance_scene=r["last_appearance_scene"],
        ) for r in rows]

    # ----------------------------------------------------------
    # 台词管理
    # ----------------------------------------------------------

    def add_line(
        self, drama_id: str, scene_id: str, character_id: str,
        content: str, emotion: str = "neutral", action: str = "",
    ) -> Optional[DramaLine]:
        """添加台词"""
        assert self._conn is not None
        # 验证存在性
        drama = self.get_drama(drama_id)
        if not drama:
            return None

        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM drama_scenes WHERE id = ?", (scene_id,))
        scene = cursor.fetchone()
        if not scene:
            return None

        cursor.execute("SELECT * FROM drama_characters WHERE id = ?", (character_id,))
        char = cursor.fetchone()
        if not char:
            return None

        now = self._now()
        line_id = self._gen_id()

        # 获取当前场次最大行号
        cursor.execute("SELECT COALESCE(MAX(line_number), 0) as max_line FROM drama_lines WHERE scene_id = ?", (scene_id,))
        line_number = cursor.fetchone()["max_line"] + 1

        line = DramaLine(
            id=line_id,
            drama_id=drama_id,
            scene_id=scene_id,
            character_id=character_id,
            character_name=char["name"],
            line_number=line_number,
            content=content,
            emotion=emotion,
            action=action,
            created_at=now,
        )

        cursor.execute("""
            INSERT INTO drama_lines (id, drama_id, scene_id, character_id, character_name, line_number, content, emotion, action, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (line_id, drama_id, scene_id, character_id, char["name"], line_number, content, emotion, action, now))

        # 更新计数
        cursor.execute("UPDATE drama_scenes SET line_count = line_count + 1 WHERE id = ?", (scene_id,))
        cursor.execute("UPDATE dramas SET total_lines = total_lines + 1, updated_at = ? WHERE id = ?", (now, drama_id))
        cursor.execute("UPDATE drama_characters SET total_lines = total_lines + 1 WHERE id = ?", (character_id,))

        # 更新角色出场场次
        cursor.execute("SELECT scene_number FROM drama_scenes WHERE id = ?", (scene_id,))
        scene_num = cursor.fetchone()["scene_number"]
        cursor.execute("""
            UPDATE drama_characters
            SET first_appearance_scene = CASE WHEN first_appearance_scene = 0 THEN ? ELSE first_appearance_scene END,
                last_appearance_scene = ?
            WHERE id = ?
        """, (scene_num, scene_num, character_id))

        self._conn.commit()
        return line

    def list_lines(self, drama_id: str, scene_id: Optional[str] = None) -> List[DramaLine]:
        """列出台词"""
        assert self._conn is not None
        query = "SELECT * FROM drama_lines WHERE drama_id = ?"
        params = [drama_id]
        if scene_id:
            query += " AND scene_id = ?"
            params.append(scene_id)
        query += " ORDER BY scene_id, line_number"

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [DramaLine(
            id=r["id"], drama_id=r["drama_id"], scene_id=r["scene_id"],
            character_id=r["character_id"], character_name=r["character_name"],
            line_number=r["line_number"], content=r["content"],
            emotion=r["emotion"], action=r["action"], created_at=r["created_at"],
        ) for r in rows]

    # ----------------------------------------------------------
    # 伏笔管理
    # ----------------------------------------------------------

    def add_foreshadowing(
        self, drama_id: str, description: str, planted_scene: int = 0,
        importance: float = 0.5, related_characters: Optional[List[str]] = None,
        notes: str = "",
    ) -> Optional[Foreshadowing]:
        """添加剧情伏笔"""
        assert self._conn is not None
        drama = self.get_drama(drama_id)
        if not drama:
            return None

        foreshadow_id = self._gen_id()
        foreshadowing = Foreshadowing(
            id=foreshadow_id,
            drama_id=drama_id,
            description=description,
            planted_scene=planted_scene,
            importance=importance,
            related_characters=related_characters or [],
            notes=notes,
        )

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO foreshadowings (id, drama_id, description, planted_scene, resolved_scene, status, importance, related_characters, notes)
            VALUES (?, ?, ?, ?, NULL, 'active', ?, ?, ?)
        """, (foreshadow_id, drama_id, description, planted_scene, importance, json.dumps(related_characters or []), notes))
        self._conn.commit()
        return foreshadowing

    def resolve_foreshadowing(self, foreshadow_id: str, resolved_scene: int) -> bool:
        """标记伏笔已回收"""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE foreshadowings SET status = 'resolved', resolved_scene = ? WHERE id = ?",
            (resolved_scene, foreshadow_id)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_foreshadowings(self, drama_id: str, status: Optional[str] = None) -> List[Foreshadowing]:
        """列出伏笔"""
        assert self._conn is not None
        query = "SELECT * FROM foreshadowings WHERE drama_id = ?"
        params = [drama_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY planted_scene"

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [Foreshadowing(
            id=r["id"], drama_id=r["drama_id"], description=r["description"],
            planted_scene=r["planted_scene"], resolved_scene=r["resolved_scene"],
            status=r["status"], importance=r["importance"],
            related_characters=json.loads(r["related_characters"]) if r["related_characters"] else [],
            notes=r["notes"],
        ) for r in rows]

    # ----------------------------------------------------------
    # 节奏分析
    # ----------------------------------------------------------

    def analyze_pacing(self, drama_id: str) -> Dict[str, Any]:
        """分析短剧节奏"""
        scenes = self.list_scenes(drama_id)
        if not scenes:
            return {"error": "没有场次数据"}

        pacing_stats = {
            "total_scenes": len(scenes),
            "pacing_distribution": {},
            "emotion_distribution": {},
            "avg_lines_per_scene": 0,
            "scene_summary": [],
        }

        total_lines = 0
        for scene in scenes:
            pacing_stats["pacing_distribution"][scene.pacing] = pacing_stats["pacing_distribution"].get(scene.pacing, 0) + 1
            pacing_stats["emotion_distribution"][scene.emotional_tone] = pacing_stats["emotion_distribution"].get(scene.emotional_tone, 0) + 1
            total_lines += scene.line_count
            pacing_stats["scene_summary"].append({
                "scene_number": scene.scene_number,
                "title": scene.title,
                "pacing": scene.pacing,
                "emotion": scene.emotional_tone,
                "lines": scene.line_count,
            })

        pacing_stats["avg_lines_per_scene"] = round(total_lines / len(scenes), 1) if scenes else 0
        return pacing_stats

    # ----------------------------------------------------------
    # 角色关系网
    # ----------------------------------------------------------

    def get_relationship_graph(self, drama_id: str) -> Dict[str, Any]:
        """构建角色关系网"""
        characters = self.list_characters(drama_id)
        if not characters:
            return {"nodes": [], "edges": [], "stats": {}}

        nodes = []
        edges = []

        for char in characters:
            nodes.append({
                "id": char.id,
                "name": char.name,
                "role_type": char.role_type,
                "total_lines": char.total_lines,
                "traits": char.personality_traits,
            })

            # 添加关系边
            for target_id, relation in char.relationships.items():
                edges.append({
                    "source": char.id,
                    "target": target_id,
                    "relationship": relation,
                })

        # 基于共现场次推断关系
        lines = self.list_lines(drama_id)
        scene_chars: Dict[str, set] = {}
        for line in lines:
            if line.scene_id not in scene_chars:
                scene_chars[line.scene_id] = set()
            scene_chars[line.scene_id].add(line.character_id)

        co_occurrence: Dict[Tuple[str, str], int] = {}
        for char_ids in scene_chars.values():
            char_list = list(char_ids)
            for i in range(len(char_list)):
                for j in range(i + 1, len(char_list)):
                    pair = tuple(sorted([char_list[i], char_list[j]]))
                    co_occurrence[pair] = co_occurrence.get(pair, 0) + 1

        inferred_edges = []
        for (c1, c2), count in co_occurrence.items():
            if count >= 2:
                inferred_edges.append({
                    "source": c1,
                    "target": c2,
                    "relationship": f"co_occurrence({count} scenes)",
                    "inferred": True,
                })

        edges.extend(inferred_edges)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "character_count": len(nodes),
                "relationship_count": len(edges),
                "inferred_count": len(inferred_edges),
            },
        }

    # ----------------------------------------------------------
    # 剧本导出
    # ----------------------------------------------------------

    def export_script(self, drama_id: str, format: str = "text") -> str:
        """导出剧本"""
        drama = self.get_drama(drama_id)
        if not drama:
            return "短剧不存在"

        scenes = self.list_scenes(drama_id)
        characters = self.list_characters(drama_id)
        char_map = {c.id: c.name for c in characters}

        if format == "json":
            script_data = {
                "title": drama.title,
                "genre": drama.genre,
                "description": drama.description,
                "scenes": [],
            }
            for scene in scenes:
                lines = self.list_lines(drama_id, scene.id)
                script_data["scenes"].append({
                    "scene_number": scene.scene_number,
                    "title": scene.title,
                    "location": scene.location,
                    "time_of_day": scene.time_of_day,
                    "summary": scene.summary,
                    "lines": [{
                        "character": l.character_name,
                        "content": l.content,
                        "emotion": l.emotion,
                        "action": l.action,
                    } for l in lines],
                })
            return json.dumps(script_data, ensure_ascii=False, indent=2)

        # 纯文本格式
        lines_out = []
        lines_out.append(f"{'=' * 60}")
        lines_out.append(f"  {drama.title}")
        if drama.genre:
            lines_out.append(f"  类型：{drama.genre}")
        if drama.description:
            lines_out.append(f"  {drama.description}")
        lines_out.append(f"{'=' * 60}")
        lines_out.append("")

        for scene in scenes:
            lines_out.append(f"--- 第 {scene.scene_number} 场 {scene.title} ---")
            if scene.location:
                lines_out.append(f"地点：{scene.location}")
            if scene.time_of_day:
                lines_out.append(f"时间：{scene.time_of_day}")
            if scene.summary:
                lines_out.append(f"概要：{scene.summary}")
            lines_out.append("")

            scene_lines = self.list_lines(drama_id, scene.id)
            for line in scene_lines:
                if line.action:
                    lines_out.append(f"  （{line.action}）")
                emotion_tag = f"[{line.emotion}]" if line.emotion != "neutral" else ""
                lines_out.append(f"  {line.character_name}{emotion_tag}：{line.content}")
            lines_out.append("")

        return "\n".join(lines_out)


# ============================================================
# CLI 命令处理
# ============================================================

_json_mode = False


def print_banner():
    """打印程序横幅"""
    if _json_mode:
        return
    banner = f"""
╔══════════════════════════════════════════════════════════╗
║                    MindForge v{VERSION:<39}║
║              智能记忆管理系统 × AI 短剧创作               ║
╚══════════════════════════════════════════════════════════╝
"""
    print(banner)


def output_json(data: Any):
    """输出 JSON"""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def cmd_add(args, core: MemoryCore):
    """添加记忆"""
    entry = core.add(
        content=args.content,
        layer=args.layer,
        tags=args.tags.split(",") if args.tags else [],
        importance=args.importance,
        source=args.source or "manual",
    )
    if _json_mode:
        output_json(asdict(entry))
    else:
        print(f"✓ 记忆已添加")
        print(f"  ID: {entry.id}")
        print(f"  层级: {entry.layer}")
        print(f"  内容: {entry.content[:100]}..." if len(entry.content) > 100 else f"  内容: {entry.content}")
        if entry.tags:
            print(f"  标签: {', '.join(entry.tags)}")
        if entry.encrypted:
            print(f"  加密: 已启用")


def cmd_delete(args, core: MemoryCore):
    """删除记忆"""
    success = core.delete(args.id)
    if _json_mode:
        output_json({"deleted": success, "id": args.id})
    else:
        if success:
            print(f"✓ 记忆 {args.id} 已删除")
        else:
            print(f"✗ 记忆 {args.id} 不存在")


def cmd_search(args, core: MemoryCore):
    """搜索记忆"""
    results = core.search(args.query, limit=args.limit, layer=args.layer)
    if _json_mode:
        output_json([{
            "id": e.id,
            "content": e.content,
            "layer": e.layer,
            "tags": e.tags,
            "score": round(s, 4),
            "importance": e.importance,
        } for e, s in results])
    else:
        if not results:
            print("未找到匹配的记忆")
            return
        print(f"找到 {len(results)} 条匹配记忆：")
        for i, (entry, score) in enumerate(results, 1):
            print(f"\n  [{i}] 相似度: {score:.3f} | 层级: {entry.layer} | 重要性: {entry.importance}")
            print(f"      ID: {entry.id}")
            print(f"      内容: {entry.content[:120]}..." if len(entry.content) > 120 else f"      内容: {entry.content}")


def cmd_stats(args, core: MemoryCore):
    """显示统计信息"""
    stats = core.stats()
    if _json_mode:
        output_json(stats)
    else:
        print("=== 记忆库统计 ===")
        print(f"总记忆数: {stats['total_entries']}")
        print(f"标签总数: {stats['total_tags']}")
        print(f"加密: {'启用' if stats.get('encryption_enabled') else '未启用'}")
        print(f"数据库大小: {stats.get('db_size_bytes', 0) / 1024:.1f} KB")
        print("\n按层级分布:")
        for layer, count in stats.get('by_layer', {}).items():
            print(f"  {layer}: {count}")
        print("\n按来源分布:")
        for source, count in stats.get('by_source', {}).items():
            print(f"  {source}: {count}")


def cmd_health(args, core: MemoryCore):
    """健康检查"""
    results = core.health_check()
    if _json_mode:
        output_json(results)
    else:
        status_icon = "✓" if results["status"] == "healthy" else ("⚠" if results["status"] == "degraded" else "✗")
        print(f"{status_icon} 健康状态: {results['status']}")
        if results.get("journal_mode"):
            print(f"  日志模式: {results['journal_mode']}")
        if results["issues"]:
            print("\n问题:")
            for issue in results["issues"]:
                print(f"  ✗ {issue}")
        if results["warnings"]:
            print("\n警告:")
            for warning in results["warnings"]:
                print(f"  ⚠ {warning}")
        if not results["issues"] and not results["warnings"]:
            print("  一切正常")


def cmd_dedup(args, core: MemoryCore):
    """去重"""
    results = core.deduplicate(threshold=args.threshold)
    if _json_mode:
        output_json(results)
    else:
        print(f"去重完成：移除 {results['removed']} 条，发现 {results['duplicates_found']} 组重复")
        for detail in results.get("details", []):
            print(f"  - {detail['id']}: {detail['reason']}")


def cmd_snapshot(args, core: MemoryCore):
    """快照管理"""
    if args.action == "create":
        snap = core.create_snapshot(args.name, args.description or "")
        if _json_mode:
            output_json(asdict(snap))
        else:
            print(f"✓ 快照已创建: {snap.name} ({snap.entry_count} 条记忆)")
    elif args.action == "list":
        snapshots = core.list_snapshots()
        if _json_mode:
            output_json([asdict(s) for s in snapshots])
        else:
            if not snapshots:
                print("暂无快照")
            for snap in snapshots:
                print(f"  {snap.name} | {snap.created_at} | {snap.entry_count} 条 | {snap.total_size_bytes / 1024:.1f} KB")
    elif args.action == "delete":
        success = core.delete_snapshot(args.snapshot_id)
        if _json_mode:
            output_json({"deleted": success, "id": args.snapshot_id})
        else:
            print(f"{'✓' if success else '✗'} 快照 {args.snapshot_id} {'已删除' if success else '不存在'}")


def cmd_agent_insight(args, core: MemoryCore):
    """Agent 增强分析"""
    insights: Dict[str, Any] = {}

    if args.type in ("all", "profile"):
        insights["profile"] = core.get_memory_profile()
    if args.type in ("all", "emotions"):
        insights["emotional_timeline"] = core.get_emotional_timeline(days=args.days)
    if args.type in ("all", "influence"):
        insights["influence_graph"] = core.get_influence_graph(depth=args.depth)
    if args.type in ("all", "conflicts"):
        conflicts = core.detect_conflicts()
        insights["conflicts"] = conflicts
        insights["conflict_count"] = len(conflicts)

    if _json_mode:
        output_json(insights)
    else:
        print("=== Agent 洞察 ===")
        if "profile" in insights:
            p = insights["profile"]
            print(f"\n[记忆画像]")
            print(f"  总记忆: {p['total_memories']}")
            print(f"  主导层级: {p['dominant_layer']}")
            print(f"  近7天活跃: {p['recent_activity']} 条")
            if p["top_tags"]:
                print(f"  热门标签: {', '.join(t for t, _ in p['top_tags'][:5])}")
        if "conflict_count" in insights:
            print(f"\n[冲突检测]")
            print(f"  发现 {insights['conflict_count']} 处潜在冲突")
            for c in insights.get("conflicts", [])[:5]:
                print(f"  - [{c['severity']}] {c['memory1']['preview'][:50]}... vs {c['memory2']['preview'][:50]}...")


def cmd_drama(args, core: MemoryCore):
    """短剧管理"""
    drama_mgr = DramaManager(core)

    if args.action == "create":
        drama = drama_mgr.create_drama(args.title, args.genre or "", args.description or "")
        if _json_mode:
            output_json(asdict(drama))
        else:
            print(f"✓ 短剧已创建: {drama.title} (ID: {drama.id})")

    elif args.action == "list":
        dramas = drama_mgr.list_dramas(status=args.status, limit=args.limit)
        if _json_mode:
            output_json([asdict(d) for d in dramas])
        else:
            if not dramas:
                print("暂无短剧")
            for d in dramas:
                print(f"  {d.title} | {d.status} | {d.total_scenes}场 | {d.total_lines}台词 | {d.updated_at}")

    elif args.action == "delete":
        success = drama_mgr.delete_drama(args.drama_id)
        if _json_mode:
            output_json({"deleted": success, "id": args.drama_id})
        else:
            print(f"{'✓' if success else '✗'} 短剧 {'已删除' if success else '不存在'}")

    elif args.action == "export":
        script = drama_mgr.export_script(args.drama_id, format=args.format)
        if _json_mode and args.format == "json":
            print(script)
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(script)
            print(f"✓ 剧本已导出到: {args.output}")
        else:
            print(script)

    elif args.action == "analyze":
        pacing = drama_mgr.analyze_pacing(args.drama_id)
        relationships = drama_mgr.get_relationship_graph(args.drama_id)
        foreshadowings = drama_mgr.list_foreshadowings(args.drama_id)
        analysis = {
            "pacing": pacing,
            "relationships": relationships,
            "foreshadowings": [asdict(f) for f in foreshadowings],
            "active_foreshadowings": len([f for f in foreshadowings if f.status == "active"]),
        }
        if _json_mode:
            output_json(analysis)
        else:
            print("=== 短剧分析 ===")
            if "error" not in pacing:
                print(f"\n[节奏分析]")
                print(f"  总场次: {pacing['total_scenes']}")
                print(f"  场均台词: {pacing['avg_lines_per_scene']}")
                print(f"  节奏分布: {pacing['pacing_distribution']}")
            print(f"\n[角色关系]")
            print(f"  角色数: {relationships['stats']['character_count']}")
            print(f"  关系数: {relationships['stats']['relationship_count']}")
            print(f"\n[伏笔追踪]")
            print(f"  总伏笔: {len(foreshadowings)}")
            print(f"  未回收: {analysis['active_foreshadowings']}")


def cmd_scene(args, core: MemoryCore):
    """场次管理"""
    drama_mgr = DramaManager(core)
    if args.action == "add":
        scene = drama_mgr.add_scene(
            args.drama_id, title=args.title or "", location=args.location or "",
            time_of_day=args.time or "", summary=args.summary or "",
            emotional_tone=args.emotion or "neutral", pacing=args.pacing or "medium",
        )
        if _json_mode:
            output_json(asdict(scene) if scene else {"error": "创建失败"})
        else:
            if scene:
                print(f"✓ 场次已添加: 第{scene.scene_number}场 {scene.title}")
            else:
                print("✗ 场次添加失败")
    elif args.action == "list":
        scenes = drama_mgr.list_scenes(args.drama_id)
        if _json_mode:
            output_json([asdict(s) for s in scenes])
        else:
            for s in scenes:
                print(f"  第{s.scene_number}场 | {s.title} | {s.location} | {s.pacing} | {s.line_count}台词")


def cmd_character(args, core: MemoryCore):
    """角色管理"""
    drama_mgr = DramaManager(core)
    if args.action == "add":
        char = drama_mgr.add_character(
            args.drama_id, name=args.name, role_type=args.role or "supporting",
            description=args.description or "",
            personality_traits=args.traits.split(",") if args.traits else [],
        )
        if _json_mode:
            output_json(asdict(char) if char else {"error": "创建失败"})
        else:
            if char:
                print(f"✓ 角色已添加: {char.name} ({char.role_type})")
            else:
                print("✗ 角色添加失败")
    elif args.action == "list":
        chars = drama_mgr.list_characters(args.drama_id)
        if _json_mode:
            output_json([asdict(c) for c in chars])
        else:
            for c in chars:
                print(f"  {c.name} | {c.role_type} | {c.total_lines}台词 | 出场: {c.first_appearance_scene}-{c.last_appearance_scene}")


def cmd_line(args, core: MemoryCore):
    """台词管理"""
    drama_mgr = DramaManager(core)
    if args.action == "add":
        line = drama_mgr.add_line(
            args.drama_id, args.scene_id, args.character_id,
            content=args.content, emotion=args.emotion or "neutral", action=args.action or "",
        )
        if _json_mode:
            output_json(asdict(line) if line else {"error": "添加失败"})
        else:
            if line:
                print(f"✓ 台词已添加: {line.character_name}: {line.content[:50]}")
            else:
                print("✗ 台词添加失败")
    elif args.action == "list":
        lines = drama_mgr.list_lines(args.drama_id, args.scene_id)
        if _json_mode:
            output_json([asdict(l) for l in lines])
        else:
            for l in lines:
                action_str = f"（{l.action}）" if l.action else ""
                print(f"  {l.character_name}: {l.content} {action_str}")


def cmd_foreshadowing(args, core: MemoryCore):
    """伏笔管理"""
    drama_mgr = DramaManager(core)
    if args.action == "add":
        f = drama_mgr.add_foreshadowing(
            args.drama_id, description=args.description,
            planted_scene=args.planted_scene or 0,
            importance=args.importance or 0.5,
            related_characters=args.characters.split(",") if args.characters else [],
            notes=args.notes or "",
        )
        if _json_mode:
            output_json(asdict(f) if f else {"error": "添加失败"})
        else:
            if f:
                print(f"✓ 伏笔已添加: {f.description[:50]}")
            else:
                print("✗ 伏笔添加失败")
    elif args.action == "resolve":
        success = drama_mgr.resolve_foreshadowing(args.foreshadow_id, args.resolved_scene)
        if _json_mode:
            output_json({"resolved": success, "id": args.foreshadow_id})
        else:
            print(f"{'✓' if success else '✗'} 伏笔 {'已回收' if success else '不存在'}")
    elif args.action == "list":
        fs = drama_mgr.list_foreshadowings(args.drama_id, status=args.status)
        if _json_mode:
            output_json([asdict(f) for f in fs])
        else:
            for f in fs:
                status_str = f"→ 第{f.resolved_scene}场回收" if f.resolved_scene else "(未回收)"
                print(f"  [{f.status}] 第{f.planted_scene}场埋下 {status_str}: {f.description[:60]}")


def cmd_forget(args, core: MemoryCore):
    """应用遗忘曲线"""
    results = core.apply_forgetting()
    if _json_mode:
        output_json(results)
    else:
        print(f"遗忘曲线已应用：更新 {results['updated']} 条，弱化 {results['weakened']} 条，遗忘 {results['forgotten']} 条")


def cmd_recall(args, core: MemoryCore):
    """回忆最近记忆"""
    entries = core.recall_recent(hours=args.hours, limit=args.limit)
    if _json_mode:
        output_json([asdict(e) for e in entries])
    else:
        print(f"最近 {args.hours} 小时的记忆（共 {len(entries)} 条）：")
        for e in entries:
            print(f"  [{e.layer}] {e.created_at}: {e.content[:80]}")


def cmd_consolidate(args, core: MemoryCore):
    """巩固记忆"""
    entry = core.consolidate(args.id)
    if _json_mode:
        output_json(asdict(entry) if entry else {"error": "记忆不存在"})
    else:
        if entry:
            print(f"✓ 记忆已巩固: {entry.id} (强度: {entry.strength:.2f}, 重要性: {entry.importance:.2f})")
        else:
            print("✗ 记忆不存在")


# ============================================================
# 主入口
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="mindforge",
        description="MindForge - 智能记忆管理系统 × AI 短剧创作",
    )
    parser.add_argument("--version", action="version", version=f"MindForge {VERSION}")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="数据库路径")
    parser.add_argument("--password", default=None, help="加密密码")
    parser.add_argument("--json", action="store_true", help="JSON 输出模式")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # --- 记忆管理 ---
    add_parser = subparsers.add_parser("add", help="添加记忆")
    add_parser.add_argument("content", help="记忆内容")
    add_parser.add_argument("--layer", choices=MEMORY_LAYERS, default="episodic")
    add_parser.add_argument("--tags", default=None, help="逗号分隔的标签")
    add_parser.add_argument("--importance", type=float, default=0.5)
    add_parser.add_argument("--source", default=None)

    del_parser = subparsers.add_parser("delete", help="删除记忆")
    del_parser.add_argument("id", help="记忆 ID")

    search_parser = subparsers.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", help="搜索查询")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--layer", default=None)

    subparsers.add_parser("stats", help="显示统计信息")
    subparsers.add_parser("health", help="健康检查")

    dedup_parser = subparsers.add_parser("dedup", help="记忆去重")
    dedup_parser.add_argument("--threshold", type=float, default=0.95)

    snap_parser = subparsers.add_parser("snapshot", help="快照管理")
    snap_parser.add_argument("action", choices=["create", "list", "delete"])
    snap_parser.add_argument("--name", default="snapshot")
    snap_parser.add_argument("--description", default=None)
    snap_parser.add_argument("--snapshot-id", default=None)

    # --- Agent 增强 ---
    agent_parser = subparsers.add_parser("agent-insight", help="Agent 增强分析")
    agent_parser.add_argument("--type", choices=["all", "profile", "emotions", "influence", "conflicts"], default="all")
    agent_parser.add_argument("--days", type=int, default=30)
    agent_parser.add_argument("--depth", type=int, default=2)

    # --- 遗忘与巩固 ---
    subparsers.add_parser("forget", help="应用遗忘曲线")

    recall_parser = subparsers.add_parser("recall", help="回忆最近记忆")
    recall_parser.add_argument("--hours", type=int, default=24)
    recall_parser.add_argument("--limit", type=int, default=50)

    cons_parser = subparsers.add_parser("consolidate", help="巩固记忆")
    cons_parser.add_argument("id", help="记忆 ID")

    # --- 短剧管理 ---
    drama_parser = subparsers.add_parser("drama", help="短剧管理")
    drama_parser.add_argument("action", choices=["create", "list", "delete", "export", "analyze"])
    drama_parser.add_argument("--title", default=None)
    drama_parser.add_argument("--genre", default=None)
    drama_parser.add_argument("--description", default=None)
    drama_parser.add_argument("--drama-id", default=None)
    drama_parser.add_argument("--status", default=None)
    drama_parser.add_argument("--limit", type=int, default=50)
    drama_parser.add_argument("--format", choices=["text", "json"], default="text")
    drama_parser.add_argument("--output", default=None)

    scene_parser = subparsers.add_parser("scene", help="场次管理")
    scene_parser.add_argument("action", choices=["add", "list"])
    scene_parser.add_argument("--drama-id", required=True)
    scene_parser.add_argument("--title", default=None)
    scene_parser.add_argument("--location", default=None)
    scene_parser.add_argument("--time", default=None)
    scene_parser.add_argument("--summary", default=None)
    scene_parser.add_argument("--emotion", default=None)
    scene_parser.add_argument("--pacing", default=None)

    char_parser = subparsers.add_parser("character", help="角色管理")
    char_parser.add_argument("action", choices=["add", "list"])
    char_parser.add_argument("--drama-id", required=True)
    char_parser.add_argument("--name", default=None)
    char_parser.add_argument("--role", default=None)
    char_parser.add_argument("--description", default=None)
    char_parser.add_argument("--traits", default=None)

    line_parser = subparsers.add_parser("line", help="台词管理")
    line_parser.add_argument("action", choices=["add", "list"])
    line_parser.add_argument("--drama-id", required=True)
    line_parser.add_argument("--scene-id", default=None)
    line_parser.add_argument("--character-id", default=None)
    line_parser.add_argument("--content", default=None)
    line_parser.add_argument("--emotion", default=None)
    line_parser.add_argument("--action", default=None)

    foreshadow_parser = subparsers.add_parser("foreshadowing", help="伏笔管理")
    foreshadow_parser.add_argument("action", choices=["add", "resolve", "list"])
    foreshadow_parser.add_argument("--drama-id", required=True)
    foreshadow_parser.add_argument("--description", default=None)
    foreshadow_parser.add_argument("--planted-scene", type=int, default=None)
    foreshadow_parser.add_argument("--importance", type=float, default=None)
    foreshadow_parser.add_argument("--characters", default=None)
    foreshadow_parser.add_argument("--notes", default=None)
    foreshadow_parser.add_argument("--foreshadow-id", default=None)
    foreshadow_parser.add_argument("--resolved-scene", type=int, default=None)
    foreshadow_parser.add_argument("--status", default=None)

    return parser


def main():
    """主入口函数"""
    global _json_mode

    parser = build_parser()
    args = parser.parse_args()

    _json_mode = args.json

    if not args.command:
        parser.print_help()
        return

    # 初始化核心
    try:
        core = MemoryCore(db_path=args.db, password=args.password)
    except Exception as e:
        if _json_mode:
            output_json({"error": str(e), "type": "initialization_error"})
        else:
            print(f"初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 命令分发
    cmd_map = {
        "add": cmd_add,
        "delete": cmd_delete,
        "search": cmd_search,
        "stats": cmd_stats,
        "health": cmd_health,
        "dedup": cmd_dedup,
        "snapshot": cmd_snapshot,
        "agent-insight": cmd_agent_insight,
        "drama": cmd_drama,
        "scene": cmd_scene,
        "character": cmd_character,
        "line": cmd_line,
        "foreshadowing": cmd_foreshadowing,
        "forget": cmd_forget,
        "recall": cmd_recall,
        "consolidate": cmd_consolidate,
    }

    handler = cmd_map.get(args.command)
    if handler:
        try:
            if not _json_mode:
                print_banner()
            handler(args, core)
        except Exception as e:
            if _json_mode:
                output_json({"error": str(e), "command": args.command})
            else:
                print(f"命令执行失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
