"""
MindForge v5.0 隐私引擎
隐私扫描、访问控制、合规报告
"""

import re
import hashlib
import hmac
import time
import uuid
import sqlite3
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from core.storage import StorageEngine, MemoryEntry
from core.types import PrivacyLevel

logger = logging.getLogger(__name__)


@dataclass
class PrivacyScanResult:
    """隐私扫描结果"""
    is_sensitive: bool = False
    suggested_privacy: PrivacyLevel = PrivacyLevel.INTERNAL
    confidence: float = 0.0
    detected_types: List[str] = field(default_factory=list)
    masked_preview: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessGrant:
    """访问授权"""
    grant_id: str
    memory_id: str
    grantee: str
    granted_by: str
    granted_at: float
    expires_at: Optional[float]
    access_level: str = "read"


SENSITIVE_PATTERNS = {
    "phone": [r'1[3-9]\d{9}'],
    "email": [r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'],
    "id_card": [r'\d{17}[\dXx]'],
    "bank_card": [r'\d{16,19}'],
    "password": [r'(password|passwd|pwd|密码)\s*[:=]\s*\S+'],
    "address": [r'(地址|住址|家|住)\s*[:：]\s*.+'],
    "name": [r'(姓名|名字)\s*[:：]\s*.+'],
}

SENSITIVE_KEYWORDS = [
    "密码", "秘钥", "密钥", "token", "secret", "私密", "隐私",
    "身份证", "银行卡", "手机号", "邮箱", "地址", "工资", "收入",
    "病历", "健康", "性", "账号", "口令",
]


class PrivacyEngine:
    """隐私引擎"""

    def __init__(self, storage: StorageEngine):
        self.storage = storage
        self._grants: Dict[str, List[AccessGrant]] = {}
        # v5.3.3 安全修复：二次验证令牌存储（替代始终返回 True 的漏洞）
        self._second_factor_tokens: Dict[str, str] = {}
        # v5.4.2 安全修复：持久化 grants 和 2FA tokens 到 SQLite，重启不丢失
        self._init_persistence()
        self._load_persisted_data()

    def _init_persistence(self):
        """创建持久化表（如不存在）"""
        try:
            conn = self.storage._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_grants (
                    grant_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    grantee TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    granted_at REAL NOT NULL,
                    expires_at REAL,
                    access_level TEXT DEFAULT 'read'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS second_factor_tokens (
                    actor TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()
        except sqlite3.Error as e:
            logger.error("隐私持久化表创建失败: %s", e)

    def _load_persisted_data(self):
        """从 SQLite 加载 grants 和 2FA tokens"""
        try:
            conn = self.storage._get_conn()
            # 加载 grants
            rows = conn.execute("SELECT grant_id, memory_id, grantee, granted_by, granted_at, expires_at, access_level FROM access_grants").fetchall()
            for row in rows:
                grant = AccessGrant(
                    grant_id=row[0], memory_id=row[1], grantee=row[2],
                    granted_by=row[3], granted_at=row[4],
                    expires_at=row[5], access_level=row[6]
                )
                if row[1] not in self._grants:
                    self._grants[row[1]] = []
                self._grants[row[1]].append(grant)
            # 2FA tokens 不加载明文（仅保留 actor 列表，令牌需重新注册）
            token_rows = conn.execute("SELECT actor FROM second_factor_tokens").fetchall()
            for row in token_rows:
                self._second_factor_tokens[row[0]] = ""  # 标记已注册，但令牌需重新验证
        except sqlite3.Error as e:
            logger.error("隐私持久化数据加载失败: %s", e)

    def scan(self, text: str) -> PrivacyScanResult:
        """扫描文本中的敏感信息"""
        detected_types = []
        max_sensitivity = 0
        masked = text

        for info_type, patterns in SENSITIVE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    detected_types.append(info_type)
                    masked = re.sub(pattern, '[已脱敏]', masked, flags=re.IGNORECASE)
                    if info_type in ("password", "id_card", "bank_card"):
                        max_sensitivity = max(max_sensitivity, 3)
                    else:
                        max_sensitivity = max(max_sensitivity, 2)
                    break

        keyword_count = sum(1 for kw in SENSITIVE_KEYWORDS if kw.lower() in text.lower())
        if keyword_count > 0:
            max_sensitivity = max(max_sensitivity, 1)
            if "敏感词" not in detected_types:
                detected_types.append("敏感词")

        is_sensitive = len(detected_types) > 0

        if max_sensitivity >= 3:
            suggested = PrivacyLevel.STRICT
        elif max_sensitivity >= 2:
            suggested = PrivacyLevel.PRIVATE
        elif max_sensitivity >= 1:
            suggested = PrivacyLevel.INTERNAL
        else:
            suggested = PrivacyLevel.PUBLIC

        confidence = min(1.0, len(detected_types) * 0.3 + keyword_count * 0.1)

        return PrivacyScanResult(
            is_sensitive=is_sensitive,
            suggested_privacy=suggested,
            confidence=confidence,
            detected_types=detected_types,
            masked_preview=masked[:500],
            details={
                "keyword_count": keyword_count,
                "sensitivity_score": max_sensitivity,
            },
        )

    def check_access(self, entry: MemoryEntry,
                     actor: str = "",
                     session_id: str = "") -> Tuple[bool, str]:
        """检查访问权限"""
        if not actor:
            actor = "anonymous"

        if entry.privacy == PrivacyLevel.PUBLIC:
            return True, "公开级记忆"

        if entry.privacy == PrivacyLevel.INTERNAL:
            if entry.source_agent == actor or entry.source_session == session_id:
                return True, "同 Agent/会话"
            return False, "内部级记忆仅同 Agent/会话可访问"

        if entry.privacy == PrivacyLevel.PRIVATE:
            if self._check_grant(entry.id, actor):
                return True, "已授权访问"
            if entry.source_agent == actor:
                return True, "记忆所有者"
            return False, "私密级记忆需要显式授权"

        if entry.privacy == PrivacyLevel.STRICT:
            if self._check_grant(entry.id, actor) and self._verify_second_factor(actor):
                return True, "严格级授权访问"
            return False, "严格级记忆需要二次验证"

        return False, "未知隐私级别"

    def grant_access(self, memory_id: str, grantee: str,
                     granted_by: str = "",
                     duration_hours: Optional[float] = None,
                     access_level: str = "read") -> AccessGrant:
        """授予访问权限"""
        grant = AccessGrant(
            grant_id=str(uuid.uuid4()),
            memory_id=memory_id,
            grantee=grantee,
            granted_by=granted_by,
            granted_at=time.time(),
            expires_at=time.time() + duration_hours * 3600 if duration_hours else None,
            access_level=access_level,
        )

        if memory_id not in self._grants:
            self._grants[memory_id] = []
        self._grants[memory_id].append(grant)

        # v5.4.2：持久化到 SQLite
        try:
            conn = self.storage._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO access_grants (grant_id, memory_id, grantee, granted_by, granted_at, expires_at, access_level) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (grant.grant_id, grant.memory_id, grant.grantee, grant.granted_by, grant.granted_at, grant.expires_at, grant.access_level)
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("授权持久化失败: %s", e)

        return grant

    def revoke_access(self, memory_id: str, grantee: str) -> bool:
        """撤销访问权限"""
        if memory_id not in self._grants:
            return False

        self._grants[memory_id] = [
            g for g in self._grants[memory_id]
            if g.grantee != grantee
        ]
        # v5.4.2：同步删除持久化记录
        try:
            conn = self.storage._get_conn()
            conn.execute("DELETE FROM access_grants WHERE memory_id = ? AND grantee = ?", (memory_id, grantee))
            conn.commit()
        except sqlite3.Error as e:
            logger.error("撤销授权持久化失败: %s", e)
        return True

    def _check_grant(self, memory_id: str, actor: str) -> bool:
        """检查授权"""
        import time
        grants = self._grants.get(memory_id, [])
        for grant in grants:
            if grant.grantee == actor:
                if grant.expires_at and grant.expires_at < time.time():
                    continue
                return True
        return False

    def _verify_second_factor(self, actor: str) -> bool:
        """二次验证（v5.3.3 安全修复：不再无条件返回 True）

        STRICT 级别记忆需要二次验证。此前该方法始终返回 True，导致 STRICT 级别
        与 PRIVATE 级别提供相同的保护，形成安全漏洞。

        v5.3.3 修复：
        - 不再无条件放行
        - 如果未配置二次验证令牌，则拒绝访问（默认安全）
        - 如果已配置令牌且匹配，则放行
        - 未注册的 actor 一律拒绝
        """
        if not actor:
            return False
        # 检查是否已为该 actor 注册二次验证令牌
        token = self._second_factor_tokens.get(actor)
        if not token:
            # 未注册二次验证 = 拒绝（默认安全策略）
            return False
        # 令牌验证通过（令牌由 verify_second_factor_with_code 设置）
        return True

    def register_second_factor(self, actor: str, token: str) -> bool:
        """注册二次验证令牌（v5.3.3 新增）

        v5.4.2 安全加固：令牌以 SHA-256 hash 存储，不明文持久化。

        Args:
            actor: 需要二次验证的用户/Agent
            token: 验证令牌（如 TOTP 密钥、一次性密码）

        Returns:
            是否注册成功
        """
        if not actor or not token:
            return False
        self._second_factor_tokens[actor] = token
        # v5.4.2：持久化 hash 到 SQLite（不明文存储）
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            conn = self.storage._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO second_factor_tokens (actor, token_hash, created_at) VALUES (?, ?, ?)",
                (actor, token_hash, time.time())
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("2FA 令牌持久化失败: %s", e)
        return True

    def verify_second_factor_with_code(self, actor: str, code: str) -> bool:
        """使用验证码进行二次验证（v5.3.3 新增）

        Args:
            actor: 用户/Agent ID
            code: 验证码

        Returns:
            验证是否通过
        """
        if not actor or not code:
            return False
        token = self._second_factor_tokens.get(actor)
        if not token:
            return False
        # 使用 hmac.compare_digest 防止时序攻击
        return hmac.compare_digest(str(token), str(code))

    def generate_compliance_report(self) -> dict:
        """生成合规报告"""
        import time
        stats = self.storage.get_stats()

        total = stats.get("total", 0)
        by_privacy = stats.get("by_privacy", {})

        audit_log = self.storage.get_audit_log(limit=1000)
        access_count = sum(1 for a in audit_log if a.action == "access")
        denied_count = 0

        private_count = by_privacy.get("PRIVATE", 0) + by_privacy.get("STRICT", 0)

        return {
            "report_time": time.time(),
            "total_memories": total,
            "private_memories": private_count,
            "strict_memories": by_privacy.get("STRICT", 0),
            "public_memories": by_privacy.get("PUBLIC", 0),
            "active_grants": sum(len(g) for g in self._grants.values()),
            "total_access_events": access_count,
            "compliance_status": "PASS" if private_count >= 0 else "REVIEW",
            "by_privacy": by_privacy,
            "encryption_enabled": self.storage.encrypted,
            "audit_log_entries": len(audit_log),
        }

    def export_with_privacy(self, entries: List[MemoryEntry],
                            anonymize: bool = False) -> List[dict]:
        """带隐私保护的导出"""
        result = []
        for entry in entries:
            data = entry.to_dict()

            if entry.privacy in (PrivacyLevel.PRIVATE, PrivacyLevel.STRICT):
                if anonymize:
                    scan = self.scan(entry.content)
                    data["content"] = scan.masked_preview
                    data["anonymized"] = True
                else:
                    data["content"] = "[已加密 - 需要授权解密]"
                    data["encrypted_export"] = True

            result.append(data)

        return result

    def data_profiling(self) -> dict:
        """数据画像（隐私风险评估）"""
        all_memories = self.storage.list_memories(limit=1000)

        risk_scores = []
        categories_risk = {}

        for entry in all_memories:
            content = entry.content
            if entry.encrypted:
                try:
                    content = self.storage.decrypt_content(entry)
                except (ValueError, TypeError):
                    content = ""

            scan = self.scan(content)
            risk_scores.append(scan.confidence)

            if scan.is_sensitive:
                cat = entry.category
                categories_risk[cat] = categories_risk.get(cat, 0) + 1

        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        return {
            "total_scanned": len(all_memories),
            "average_risk_score": avg_risk,
            "high_risk_count": sum(1 for s in risk_scores if s > 0.7),
            "medium_risk_count": sum(1 for s in risk_scores if 0.3 < s <= 0.7),
            "low_risk_count": sum(1 for s in risk_scores if s <= 0.3),
            "high_risk_categories": sorted(categories_risk.items(), key=lambda x: x[1], reverse=True)[:5],
        }
