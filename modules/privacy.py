"""
ClawMemory 隐私引擎模块
===========================
强制执行隐私分级制度：
- 隐私分级强制执行（PUBLIC / INTERNAL / PRIVATE / STRICT）
- 访问控制列表（ACL）
- 隐私扫描（自动识别敏感内容）
- 隔离存储（STRICT 级别物理隔离）
- 数据脱敏（导出时自动脱敏）
- 隐私合规报告
"""

import re
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from core import StorageEngine, MemoryEntry, PrivacyLevel


# ============================================================================
# Sensitivity Patterns
# ============================================================================
SENSITIVITY_PATTERNS = [
    # Financial
    (r"\d{16,19}", "BANK_CARD", 3),
    (r"\b\d{6}\b", "ID_NUMBER", 3),
    (r"密码[:：]\s*\S+", "PASSWORD", 4),
    (r"pass(word)?[:：]\s*\S+", "PASSWORD", 4),
    (r"卡号[:：]\s*\S+", "FINANCIAL", 3),
    # Contact
    (r"1[3-9]\d{9}", "PHONE", 2),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "EMAIL", 2),
    # Identity
    (r"身份证[:：]\s*\S+", "ID_CARD", 4),
    (r"护照[:：]\s*\S+", "PASSPORT", 4),
    # Health
    (r"病历[:：]", "HEALTH", 3),
    (r"病史[:：]", "HEALTH", 3),
    # Location
    (r"家庭地址[:：]\s*\S+", "HOME_ADDRESS", 3),
]

AUTO_PRIVACY_MAP = {
    "PASSWORD": PrivacyLevel.STRICT,
    "ID_CARD": PrivacyLevel.STRICT,
    "PASSPORT": PrivacyLevel.STRICT,
    "FINANCIAL": PrivacyLevel.PRIVATE,
    "ID_NUMBER": PrivacyLevel.PRIVATE,
    "HEALTH": PrivacyLevel.PRIVATE,
    "BANK_CARD": PrivacyLevel.PRIVATE,
    "PHONE": PrivacyLevel.INTERNAL,
    "EMAIL": PrivacyLevel.INTERNAL,
    "HOME_ADDRESS": PrivacyLevel.PRIVATE,
}


@dataclass
class PrivacyScanResult:
    """| 隐私扫描结果 |"""
    is_sensitive: bool
    detected_types: List[str]
    suggested_privacy: PrivacyLevel
    masked_preview: str  # 脱敏后的预览
    confidence: float    # 0-1

    def to_dict(self) -> Dict:
        return {
            "is_sensitive": self.is_sensitive,
            "detected_types": self.detected_types,
            "suggested_privacy": self.suggested_privacy.value,
            "masked_preview": self.masked_preview,
            "confidence": self.confidence,
        }


@dataclass
class AccessGrant:
    """| 访问授权记录 |"""
    memory_id: str
    granted_to_agent: str
    granted_by: str       # user or system
    granted_at: float
    expires_at: Optional[float]
    scope: List[str]      # ["content", "metadata"]


# ============================================================================
# Privacy Engine
# ============================================================================
class PrivacyEngine:
    """| 隐私分级执行引擎 |"""

    def __init__(
        self,
        storage: Optional[StorageEngine] = None,
        strict_storage_path: Optional[Path] = None,
    ):
        self._storage = storage or StorageEngine()
        self._strict_path = strict_storage_path or self._get_strict_path()
        self._strict_path.mkdir(parents=True, exist_ok=True)
        self._acl: Dict[str, List[AccessGrant]] = {}
        self._lock = Lock()
        self._load_acl()

    def _get_strict_path(self) -> Path:
        base = Path(__file__).parent.parent
        return base / "data" / "store" / "strict"

    def _load_acl(self):
        acl_path = self._strict_path / "acl.json"
        if acl_path.exists():
            with open(acl_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                for mem_id, grants in raw.items():
                    self._acl[mem_id] = [AccessGrant(**g) for g in grants]

    def _save_acl(self):
        acl_path = self._strict_path / "acl.json"
        serializable = {
            mem_id: [g.__dict__ for g in grants]
            for mem_id, grants in self._acl.items()
        }
        with open(acl_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------------------
    # Privacy Scanning
    # --------------------------------------------------------------------------
    def scan(self, text: str) -> PrivacyScanResult:
        """| 扫描文本中的敏感信息 |"""
        detected: List[str] = []
        highest_severity = 0

        for pattern, label, severity in SENSITIVITY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(label)
                highest_severity = max(highest_severity, severity)

        if not detected:
            return PrivacyScanResult(
                is_sensitive=False,
                detected_types=[],
                suggested_privacy=PrivacyLevel.PUBLIC,
                masked_preview=text[:200],
                confidence=0.0,
            )

        # Determine suggested privacy level
        suggested = PrivacyLevel.PUBLIC
        for dtype in detected:
            level = AUTO_PRIVACY_MAP.get(dtype, PrivacyLevel.INTERNAL)
            if level.to_int() > suggested.to_int():
                suggested = level

        # Generate masked preview
        masked = self._mask_sensitive(text)

        return PrivacyScanResult(
            is_sensitive=True,
            detected_types=detected,
            suggested_privacy=suggested,
            masked_preview=masked[:200],
            confidence=min(1.0, len(detected) * 0.3),
        )

    def _mask_sensitive(self, text: str) -> str:
        """| 脱敏处理 |"""
        masked = text
        for pattern, label, severity in SENSITIVITY_PATTERNS:
            if severity >= 3:
                if label == "PHONE":
                    masked = re.sub(r"1[3-9]\d{9}", "[手机号已脱敏]", masked)
                elif label == "EMAIL":
                    masked = re.sub(
                        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                        "[邮箱已脱敏]", masked,
                    )
                elif label in ("PASSWORD",):
                    masked = re.sub(
                        r"(密码|pass)[:：]\s*\S+",
                        r"\1: [已脱敏]", masked, flags=re.IGNORECASE,
                    )
        return masked

    # --------------------------------------------------------------------------
    # Access Control
    # --------------------------------------------------------------------------
    def check_access(
        self,
        entry: MemoryEntry,
        requester_agent: str,
        requester_session: str,
        max_privacy: PrivacyLevel = PrivacyLevel.INTERNAL,
    ) -> Tuple[bool, str]:
        """| 检查访问权限，返回 (允许, 原因) |"""
        # STRICT level: only explicitly granted agents
        if entry.privacy == PrivacyLevel.STRICT:
            grants = self._acl.get(entry.id, [])
            now = time.time()
            for grant in grants:
                if grant.granted_to_agent == requester_agent:
                    if grant.expires_at and grant.expires_at < now:
                        continue
                    return True, "explicit_grant"
            return False, "strict_no_grant"

        # PRIVATE level: own agent or explicit grant
        if entry.privacy == PrivacyLevel.PRIVATE:
            if entry.source_agent == requester_agent:
                return True, "owner"
            grants = self._acl.get(entry.id, [])
            for grant in grants:
                if grant.granted_to_agent == requester_agent:
                    return True, "explicit_grant"
            return False, "private_no_grant"

        # INTERNAL/PUBLIC: check max_privacy
        if entry.privacy.to_int() > max_privacy.to_int():
            return False, f"exceeds_max_privacy_{max_privacy.value}"

        # Same agent always has access
        if entry.source_agent == requester_agent:
            return True, "owner"

        return True, "allowed"

    def grant_access(
        self,
        memory_id: str,
        to_agent: str,
        granted_by: str = "user",
        duration_hours: Optional[float] = None,
        scope: Optional[List[str]] = None,
    ) -> bool:
        """| 授予访问权限 |"""
        with self._lock:
            grant = AccessGrant(
                memory_id=memory_id,
                granted_to_agent=to_agent,
                granted_by=granted_by,
                granted_at=time.time(),
                expires_at=time.time() + duration_hours * 3600 if duration_hours else None,
                scope=scope or ["content"],
            )
            if memory_id not in self._acl:
                self._acl[memory_id] = []
            self._acl[memory_id].append(grant)
            self._save_acl()
        return True

    def revoke_access(self, memory_id: str, to_agent: str) -> bool:
        """| 撤销访问权限 |"""
        with self._lock:
            if memory_id in self._acl:
                self._acl[memory_id] = [
                    g for g in self._acl[memory_id] if g.granted_to_agent != to_agent
                ]
                self._save_acl()
        return True

    def revoke_all_access(self, memory_id: str) -> bool:
        with self._lock:
            if memory_id in self._acl:
                del self._acl[memory_id]
                self._save_acl()
        return True

    # --------------------------------------------------------------------------
    # Privacy-Aware Export
    # --------------------------------------------------------------------------
    def export_with_privacy(
        self,
        entries: List[MemoryEntry],
        anonymize: bool = True,
    ) -> List[Dict]:
        """| 带隐私保护的导出 |"""
        exported = []
        for entry in entries:
            content = self._storage.decrypt_content(entry)
            if anonymize and entry.privacy.to_int() >= PrivacyLevel.PRIVATE.to_int():
                content = self._mask_sensitive(content)
            exported.append({
                "id": entry.id[:8] + "...",
                "category": entry.category,
                "content": content,
                "privacy": entry.privacy.value,
                "created_at": entry.created_at,
            })
        return exported

    # --------------------------------------------------------------------------
    # Compliance Report
    # --------------------------------------------------------------------------
    def generate_compliance_report(self) -> Dict:
        """| 生成隐私合规报告 |"""
        import sqlite3
        db_path = self._storage._db_path
        with self._lock:
            conn = sqlite3.connect(str(db_path))
            total = conn.execute("SELECT COUNT(*) FROM memories WHERE is_deleted=0").fetchone()[0]
            by_privacy = dict(conn.execute(
                "SELECT privacy, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY privacy"
            ).fetchall())
            private_count = sum(
                v for k, v in by_privacy.items()
                if PrivacyLevel.from_string(str(k)).to_int() >= PrivacyLevel.PRIVATE.to_int()
            )
            strict_count = by_privacy.get(PrivacyLevel.STRICT.to_int(), 0)
            acl_count = sum(len(v) for v in self._acl.values())
            conn.close()

        return {
            "report_time": time.time(),
            "total_memories": total,
            "by_privacy": {
                PrivacyLevel.from_int(k).value: v for k, v in by_privacy.items()
            },
            "private_memories": private_count,
            "strict_memories": strict_count,
            "active_grants": acl_count,
            "strict_storage_path": str(self._strict_path),
            "compliance_status": "PASS" if strict_count == 0 or acl_count > 0 else "REVIEW",
        }