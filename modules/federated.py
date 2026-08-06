"""
MindForge v5.4.0 联邦记忆网络
多 Agent 间安全共享记忆，端侧联邦学习

v5.4.0 新增：
  - 细粒度 ACL：namespace / tag / category 级读写权限控制
  - created_by 溯源：每条记忆记录创建者、来源 peer、版本链
  - 共享策略：read / write / admin 三级，支持通配符匹配
"""

import json
import hashlib
import hmac
import re
import sqlite3  # v5.2.8 修复：_verify_memory_exists 的 except 子句引用了未导入的 sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class PeerStatus(Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class AccessLevel(Enum):
    """细粒度访问级别（v5.4.0 新增）

    优先级：NONE < READ < WRITE < ADMIN
    """
    NONE = 0   # 无权限
    READ = 1   # 可读（搜索 / get / list）
    WRITE = 2  # 可写（update / append / tag）
    ADMIN = 3  # 可管理（删除 / 共享给第三方 / 撤销）

    @classmethod
    def parse(cls, value: Any) -> "AccessLevel":
        """容错解析，非法值降级到 NONE"""
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            for m in cls:
                if m.value == value:
                    return m
            return cls.NONE
        if isinstance(value, str):
            v = value.strip().upper()
            return {
                "NONE": cls.NONE, "READ": cls.READ, "R": cls.READ,
                "WRITE": cls.WRITE, "W": cls.WRITE, "RW": cls.WRITE,
                "ADMIN": cls.ADMIN, "A": cls.ADMIN,
            }.get(v, cls.NONE)
        return cls.NONE


@dataclass
class FederatedPeer:
    """联邦节点"""
    peer_id: str
    name: str
    status: PeerStatus = PeerStatus.OFFLINE
    trust_level: float = 0.5
    public_key: str = ""
    last_seen: float = 0.0
    shared_categories: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "name": self.name,
            "status": self.status.value,
            "trust_level": self.trust_level,
            "last_seen": self.last_seen,
            "shared_categories": self.shared_categories,
            "metadata": self.metadata,
        }


@dataclass
class MemoryProvenance:
    """记忆溯源信息（v5.4.0 新增）

    记录一条记忆的「创建者 → 修改者链」，用于：
      - 审计：谁创建了这条记忆、谁修改过
      - 冲突解决：LWW 时按 (created_by, updated_at, version) 比较
      - 撤回：发现污染记忆时按溯源链路反向清理
    """
    created_by: str = ""               # 创建者 peer_id
    created_at: float = 0.0
    origin_peer: str = ""              # 记忆原始归属节点（联邦入站时 ≠ created_by）
    last_modified_by: str = ""
    last_modified_at: float = 0.0
    version: int = 1                   # 单调递增版本号
    version_chain: List[Dict[str, Any]] = field(default_factory=list)  # [{by, at, version, reason}]
    signature: str = ""                # 创建时签名（HMAC）

    def bump(self, actor: str, reason: str = "") -> int:
        """追加一次修改记录，返回新版本号"""
        self.version += 1
        self.last_modified_by = actor
        self.last_modified_at = time.time()
        self.version_chain.append({
            "by": actor,
            "at": self.last_modified_at,
            "version": self.version,
            "reason": (reason or "")[:200],
        })
        # 限制链长度，避免无限增长
        if len(self.version_chain) > 50:
            self.version_chain = self.version_chain[-50:]
        return self.version

    def to_dict(self) -> dict:
        return {
            "created_by": self.created_by,
            "created_at": self.created_at,
            "origin_peer": self.origin_peer,
            "last_modified_by": self.last_modified_by,
            "last_modified_at": self.last_modified_at,
            "version": self.version,
            "version_chain": self.version_chain[-10:],
            "signature": self.signature[:32] + "…" if len(self.signature) > 32 else self.signature,
        }


@dataclass
class ACLRule:
    """细粒度 ACL 规则（v5.4.0 新增）

    一条规则形如：
        principal=peer_alice, namespace="team/*", tags=["python", "ops"], level=WRITE

    匹配优先级（具体到抽象）：
        1. 显式 memory_id
        2. namespace 通配（"team/*" 匹配 "team/api"、"team/api/v1"）
        3. tag 命中（任一 tag 命中即生效）
        4. category 精确匹配
        5. 全局默认（principal="*"）
    """
    principal: str                          # peer_id 或 "*"（通配）
    level: AccessLevel = AccessLevel.READ
    memory_id: Optional[str] = None         # 针对单条记忆
    namespace: Optional[str] = None          # 支持 "team/*" 通配
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    granted_by: str = ""                    # 谁授予的（溯源）
    granted_at: float = 0.0
    expires_at: Optional[float] = None      # 过期时间，None=永久
    note: str = ""

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or time.time()) >= self.expires_at

    @staticmethod
    def ns_match(pattern: str, ns: str) -> bool:
        """namespace 通配匹配：'team/*' 匹配 'team/api'"""
        if not pattern:
            return False
        if pattern == "*":
            return True
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            return ns == prefix or ns.startswith(prefix + "/")
        return pattern == ns

    def matches(self, memory_id: str, namespace: str,
                category: str, tags: List[str]) -> bool:
        if self.is_expired():
            return False
        if self.memory_id and self.memory_id != memory_id:
            return False
        if self.namespace and not self.ns_match(self.namespace, namespace):
            return False
        if self.category and self.category != category:
            return False
        if self.tags:
            if not any(t in tags for t in self.tags):
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "principal": self.principal,
            "level": self.level.name,
            "memory_id": self.memory_id,
            "namespace": self.namespace,
            "category": self.category,
            "tags": list(self.tags),
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "note": self.note,
        }


@dataclass
class SharedMemory:
    """共享记忆"""
    memory_id: str
    original_peer: str
    shared_with: List[str] = field(default_factory=list)
    access_count: Dict[str, int] = field(default_factory=dict)
    shared_at: float = 0.0
    expires_at: Optional[float] = None
    access_policy: str = "read_only"   # 旧字段保留向后兼容
    provenance: Optional[MemoryProvenance] = None  # v5.4.0 溯源


class FederatedMemory:
    """联邦记忆管理器"""

    def __init__(self, storage=None, local_peer_id: str = ""):
        self.storage = storage
        self.local_peer_id = local_peer_id or str(uuid.uuid4())
        self.peers: Dict[str, FederatedPeer] = {}
        self.shared_memories: Dict[str, SharedMemory] = {}
        self._incoming_queue: List[Dict] = []
        self._outgoing_queue: List[Dict] = []
        # v5.4.0 新增：细粒度 ACL + 溯源
        self.acl_rules: List[ACLRule] = []
        self.provenance: Dict[str, MemoryProvenance] = {}  # memory_id -> Provenance
        # 默认策略：未匹配任何 ACL 规则时的兜底级别
        self.default_access: AccessLevel = AccessLevel.NONE
        # 全局只读豁免名单（信任度 ≥ 此值的 peer 默认获得 READ）
        self.trust_read_threshold: float = 0.5

    def register_peer(self, peer_id: str, name: str,
                      trust_level: float = 0.5,
                      shared_categories: Optional[List[str]] = None) -> FederatedPeer:
        """注册联邦节点"""
        peer = FederatedPeer(
            peer_id=peer_id,
            name=name,
            trust_level=trust_level,
            shared_categories=shared_categories or [],
            last_seen=time.time(),
        )
        self.peers[peer_id] = peer
        return peer

    def remove_peer(self, peer_id: str) -> bool:
        """移除节点"""
        if peer_id in self.peers:
            del self.peers[peer_id]
            return True
        return False

    def update_trust_level(self, peer_id: str, new_level: float) -> bool:
        """更新信任级别"""
        if peer_id in self.peers:
            self.peers[peer_id].trust_level = max(0.0, min(1.0, new_level))
            self.peers[peer_id].last_seen = time.time()
            return True
        return False

    def share_memory(self, memory_id: str,
                     peer_ids: List[str],
                     access_policy: str = "read_only",
                     expires_hours: Optional[float] = None,
                     namespace: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     category: Optional[str] = None,
                     level: Optional[AccessLevel] = None) -> Optional[SharedMemory]:
        """共享记忆给其他节点（v5.4.0 增强：同时写入 ACL 规则）

        Args:
            memory_id: 要共享的记忆 ID
            peer_ids: 接收方 peer_id 列表
            access_policy: 旧字段（read_only / read_write），向下兼容
            expires_hours: 过期小时数
            namespace: 命名空间（如 "team/api"），用于 ACL 通配匹配
            tags: 标签列表，ACL 规则可按 tag 授权
            category: 分类
            level: v5.4.0 细粒度权限（READ/WRITE/ADMIN），优先于 access_policy
        """
        if not self._verify_memory_exists(memory_id):
            return None

        # 解析最终 level：优先 level 参数，其次 access_policy 字符串
        if level is None:
            level = (AccessLevel.WRITE
                     if access_policy in ("read_write", "write", "rw")
                     else AccessLevel.READ)

        for pid in peer_ids:
            if pid not in self.peers:
                continue
            if self.peers[pid].trust_level < 0.3:
                continue

        now = time.time()
        shared = SharedMemory(
            memory_id=memory_id,
            original_peer=self.local_peer_id,
            shared_with=list(peer_ids),
            shared_at=now,
            expires_at=now + expires_hours * 3600 if expires_hours else None,
            access_policy=access_policy,
        )

        self.shared_memories[memory_id] = shared

        # v5.4.0：为每个 peer 写入细粒度 ACL 规则
        for pid in peer_ids:
            self.grant(
                principal=pid,
                level=level,
                memory_id=memory_id,
                namespace=namespace,
                category=category,
                tags=tags or [],
                granted_by=self.local_peer_id,
                expires_at=shared.expires_at,
                note=f"share_memory via FederatedMemory",
            )

        for pid in peer_ids:
            self._outgoing_queue.append({
                "type": "memory_share",
                "from": self.local_peer_id,
                "to": pid,
                "memory_id": memory_id,
                "access_policy": access_policy,
                "level": level.name,
                "namespace": namespace,
                "tags": tags or [],
                "category": category,
                "timestamp": now,
            })

        return shared

    def revoke_share(self, memory_id: str, peer_ids: Optional[List[str]] = None) -> bool:
        """撤销共享（同步清理 ACL 规则）"""
        if memory_id not in self.shared_memories:
            return False

        shared = self.shared_memories[memory_id]

        if peer_ids:
            shared.shared_with = [pid for pid in shared.shared_with if pid not in peer_ids]
            # 删除针对这些 peer 的 ACL 规则
            self.acl_rules = [
                r for r in self.acl_rules
                if not (r.memory_id == memory_id and r.principal in (peer_ids or []))
            ]
            if not shared.shared_with:
                del self.shared_memories[memory_id]
        else:
            del self.shared_memories[memory_id]
            # 删除该 memory_id 的所有 ACL 规则
            self.acl_rules = [r for r in self.acl_rules if r.memory_id != memory_id]

        return True

    # =====================================================================
    # v5.4.0 细粒度 ACL API
    # =====================================================================

    def grant(self,
              principal: str,
              level: AccessLevel,
              memory_id: Optional[str] = None,
              namespace: Optional[str] = None,
              category: Optional[str] = None,
              tags: Optional[List[str]] = None,
              granted_by: str = "",
              expires_at: Optional[float] = None,
              note: str = "") -> ACLRule:
        """授予一条 ACL 规则

        若已存在相同 (principal, memory_id, namespace, category, tags) 的规则，
        则更新其 level（避免重复规则堆积）。
        """
        if not principal or not isinstance(principal, str):
            raise ValueError("principal 不能为空")
        if principal != "*" and principal not in self.peers:
            # 允许给未注册 peer 授权，但记录警告到 note
            note = (note + " | warn:principal_not_registered").strip(" |")

        level = AccessLevel.parse(level)
        tags = list(tags or [])[:20]  # 限制 tag 数量

        # 去重：同 principal + 同资源维度 = 更新而非追加
        for r in self.acl_rules:
            if (r.principal == principal
                    and r.memory_id == memory_id
                    and r.namespace == namespace
                    and r.category == category
                    and tuple(sorted(r.tags)) == tuple(sorted(tags))):
                r.level = level
                r.granted_by = granted_by or r.granted_by
                r.granted_at = time.time()
                r.expires_at = expires_at
                if note:
                    r.note = note
                return r

        rule = ACLRule(
            principal=principal,
            level=level,
            memory_id=memory_id,
            namespace=namespace,
            category=category,
            tags=tags,
            granted_by=granted_by or self.local_peer_id,
            granted_at=time.time(),
            expires_at=expires_at,
            note=note,
        )
        self.acl_rules.append(rule)
        return rule

    def revoke_acl(self,
                   principal: str,
                   memory_id: Optional[str] = None,
                   namespace: Optional[str] = None,
                   category: Optional[str] = None) -> int:
        """撤销 ACL 规则，返回被移除的规则数

        撤销范围由参数决定：传 memory_id 只撤销该记忆的规则；
        传 namespace 撤销整个命名空间；不传则撤销该 principal 的所有规则。
        """
        before = len(self.acl_rules)
        self.acl_rules = [
            r for r in self.acl_rules
            if not (
                r.principal == principal
                and (memory_id is None or r.memory_id == memory_id)
                and (namespace is None or r.namespace == namespace)
                and (category is None or r.category == category)
            )
        ]
        return before - len(self.acl_rules)

    def list_acl(self,
                 principal: Optional[str] = None,
                 memory_id: Optional[str] = None,
                 namespace: Optional[str] = None) -> List[ACLRule]:
        """查询 ACL 规则"""
        out = []
        for r in self.acl_rules:
            if r.is_expired():
                continue
            if principal and r.principal != principal:
                continue
            if memory_id and r.memory_id != memory_id:
                continue
            if namespace and not ACLRule.ns_match(namespace, r.namespace or ""):
                continue
            out.append(r)
        return out

    def check_access(self,
                     principal: str,
                     action: str,
                     memory_id: str = "",
                     namespace: str = "",
                     category: str = "",
                     tags: Optional[List[str]] = None) -> AccessLevel:
        """检查 peer 对某资源的访问权限

        Args:
            principal: 发起请求的 peer_id
            action: read / write / admin / delete
            memory_id / namespace / category / tags: 资源定位

        Returns:
            实际授予的 AccessLevel；NONE 表示拒绝
        """
        required = {
            "read": AccessLevel.READ,
            "write": AccessLevel.WRITE,
            "admin": AccessLevel.ADMIN,
            "delete": AccessLevel.ADMIN,
            "share": AccessLevel.ADMIN,
        }.get(action.lower(), AccessLevel.READ)

        tags = tags or []
        granted = AccessLevel.NONE

        # 1) 显式规则：按优先级匹配（memory_id > namespace > tags > category > 通配）
        # 收集所有命中的规则
        matched: List[ACLRule] = []
        for r in self.acl_rules:
            if r.is_expired():
                continue
            # principal 匹配（支持 "*" 通配）
            if r.principal != "*" and r.principal != principal:
                continue
            if not r.matches(memory_id, namespace, category, tags):
                continue
            matched.append(r)

        # 排序：memory_id 优先 > namespace > category > tags > principal=*
        def _specificity(r: ACLRule) -> Tuple[int, int, int, int]:
            return (
                1 if r.memory_id else 0,
                1 if r.namespace else 0,
                1 if r.category else 0,
                len(r.tags),
            )
        matched.sort(key=_specificity, reverse=True)

        # 取最具体的命中规则的 level；同级别则取最大
        for r in matched:
            if r.level.value > granted.value:
                granted = r.level

        # 2) 兜底：未命中规则时，信任度 ≥ 阈值的 peer 给 READ
        if granted == AccessLevel.NONE:
            peer = self.peers.get(principal)
            if peer and peer.trust_level >= self.trust_read_threshold:
                granted = AccessLevel.READ

        # 3) 默认策略
        if granted == AccessLevel.NONE:
            granted = self.default_access

        # 4) 本地 peer 永远是 ADMIN
        if principal == self.local_peer_id:
            granted = AccessLevel.ADMIN

        return granted if granted.value >= required.value else AccessLevel.NONE

    def can_read(self, principal: str, memory_id: str = "",
                 namespace: str = "", category: str = "",
                 tags: Optional[List[str]] = None) -> bool:
        return self.check_access(principal, "read", memory_id,
                                 namespace, category, tags).value >= AccessLevel.READ.value

    def can_write(self, principal: str, memory_id: str = "",
                  namespace: str = "", category: str = "",
                  tags: Optional[List[str]] = None) -> bool:
        return self.check_access(principal, "write", memory_id,
                                 namespace, category, tags).value >= AccessLevel.WRITE.value

    # =====================================================================
    # v5.4.0 溯源 API
    # =====================================================================

    def track_provenance(self, memory_id: str,
                         created_by: str = "",
                         origin_peer: str = "",
                         signature: str = "") -> MemoryProvenance:
        """为一条记忆初始化溯源记录"""
        now = time.time()
        prov = MemoryProvenance(
            created_by=created_by or self.local_peer_id,
            created_at=now,
            origin_peer=origin_peer or created_by or self.local_peer_id,
            last_modified_by=created_by or self.local_peer_id,
            last_modified_at=now,
            version=1,
            version_chain=[{
                "by": created_by or self.local_peer_id,
                "at": now,
                "version": 1,
                "reason": "create",
            }],
            signature=signature,
        )
        self.provenance[memory_id] = prov
        return prov

    def record_modification(self, memory_id: str,
                            actor: str,
                            reason: str = "") -> Optional[MemoryProvenance]:
        """记录一次修改到溯源链"""
        prov = self.provenance.get(memory_id)
        if prov is None:
            prov = MemoryProvenance(
                created_by=actor,
                created_at=time.time(),
                origin_peer=actor,
            )
            self.provenance[memory_id] = prov
        prov.bump(actor, reason)
        return prov

    def get_provenance(self, memory_id: str) -> Optional[MemoryProvenance]:
        return self.provenance.get(memory_id)

    def audit_trail(self, memory_id: str) -> List[Dict[str, Any]]:
        """返回某条记忆的完整修改链（用于审计）"""
        prov = self.provenance.get(memory_id)
        if not prov:
            return []
        return list(prov.version_chain)

    def find_by_creator(self, created_by: str) -> List[str]:
        """查询某 peer 创建的所有记忆 ID（溯源反向查询）"""
        return [mid for mid, p in self.provenance.items() if p.created_by == created_by]

    def receive_memory(self, from_peer: str,
                       memory_data: Dict,
                       signature: str = "") -> bool:
        """接收来自其他节点的记忆"""
        if from_peer not in self.peers:
            return False

        peer = self.peers[from_peer]
        if peer.trust_level < 0.2:
            return False

        if not self._verify_signature(memory_data, signature, from_peer):
            return False

        self._incoming_queue.append({
            "from": from_peer,
            "data": memory_data,
            "received_at": time.time(),
        })

        return True

    def accept_incoming(self, memory_index: int = -1) -> Optional[str]:
        """接受传入的记忆（v5.4.0：自动建立溯源 + ACL）"""
        if not self._incoming_queue:
            return None

        item = self._incoming_queue.pop(memory_index)

        if self.storage:
            try:
                entry = self.storage.add_memory(
                    content=item["data"].get("content", ""),
                    category=item["data"].get("category", "federated"),
                    tags=item["data"].get("tags", []) + [f"from:{item['from']}"],
                    source_agent=f"federated:{item['from']}",
                    metadata={
                        "federated_origin": item["from"],
                        "received_at": item["received_at"],
                        "federated_signature": item.get("signature", ""),
                    }
                )
                # v5.4.0：建立溯源链 + 授予 origin peer READ 权限
                self.track_provenance(
                    memory_id=entry.id,
                    created_by=item["from"],
                    origin_peer=item["from"],
                    signature=item.get("signature", ""),
                )
                # 接收方对来自 origin 的记忆默认获得 ADMIN（自己已落库）
                # 同时授予 origin peer 一条 READ 规则，便于后续 audit
                self.grant(
                    principal=item["from"],
                    level=AccessLevel.READ,
                    memory_id=entry.id,
                    granted_by=self.local_peer_id,
                    note="auto-grant on federated receive",
                )
                return entry.id
            except (ValueError, TypeError):
                return None

        return None

    def federated_search(self, query: str,
                         peer_ids: Optional[List[str]] = None,
                         max_per_peer: int = 5) -> Dict[str, List[Dict]]:
        """联邦搜索（跨节点）"""
        results = {}

        search_peers = peer_ids or list(self.peers.keys())

        for pid in search_peers:
            if pid not in self.peers:
                continue
            peer = self.peers[pid]
            if peer.status == PeerStatus.OFFLINE:
                continue
            if peer.trust_level < 0.3:
                continue

            self._outgoing_queue.append({
                "type": "search_request",
                "from": self.local_peer_id,
                "to": pid,
                "query": query,
                "max_results": max_per_peer,
                "timestamp": time.time(),
            })

            results[pid] = []

        return results

    def get_shared_memories(self, peer_id: Optional[str] = None) -> List[SharedMemory]:
        """获取共享记忆列表"""
        if peer_id:
            return [
                s for s in self.shared_memories.values()
                if peer_id in s.shared_with
            ]
        return list(self.shared_memories.values())

    def get_peers(self, status: Optional[PeerStatus] = None) -> List[FederatedPeer]:
        """获取节点列表"""
        peers = list(self.peers.values())
        if status:
            peers = [p for p in peers if p.status == status]
        return peers

    def get_queue_sizes(self) -> Dict[str, int]:
        """获取队列大小"""
        return {
            "incoming": len(self._incoming_queue),
            "outgoing": len(self._outgoing_queue),
        }

    def _verify_memory_exists(self, memory_id: str) -> bool:
        """验证记忆存在"""
        if not self.storage:
            return True
        try:
            entry = self.storage.get_memory(memory_id)
            return entry is not None
        except sqlite3.OperationalError:
            return False

    def _verify_signature(self, data: Dict, signature: str, peer_id: str) -> bool:
        """验证签名（简化版）"""
        if not signature:
            return peer_id in self.peers
        return True

    def compute_federated_stats(self) -> Dict:
        """计算联邦统计（v5.4.0：加入 ACL 和溯源统计）"""
        # 按 level 统计 ACL 规则数
        level_counts: Dict[str, int] = {"NONE": 0, "READ": 0, "WRITE": 0, "ADMIN": 0}
        active_rules = 0
        for r in self.acl_rules:
            if r.is_expired():
                continue
            active_rules += 1
            level_counts[r.level.name] = level_counts.get(r.level.name, 0) + 1

        # 按 namespace 分桶
        ns_counts: Dict[str, int] = {}
        for r in self.acl_rules:
            if r.is_expired():
                continue
            ns = r.namespace or "(default)"
            ns_counts[ns] = ns_counts.get(ns, 0) + 1

        return {
            "local_peer_id": self.local_peer_id,
            "total_peers": len(self.peers),
            "online_peers": sum(1 for p in self.peers.values() if p.status == PeerStatus.ONLINE),
            "trusted_peers": sum(1 for p in self.peers.values() if p.trust_level >= 0.7),
            "shared_memories": len(self.shared_memories),
            "incoming_queue": len(self._incoming_queue),
            "outgoing_queue": len(self._outgoing_queue),
            "avg_trust_level": (
                sum(p.trust_level for p in self.peers.values()) / len(self.peers)
                if self.peers else 0
            ),
            # v5.4.0 新增
            "acl_rules_total": len(self.acl_rules),
            "acl_rules_active": active_rules,
            "acl_by_level": level_counts,
            "acl_by_namespace": dict(sorted(ns_counts.items(), key=lambda x: -x[1])[:10]),
            "provenance_tracked": len(self.provenance),
            "default_access": self.default_access.name,
        }


__all__ = [
    "FederatedMemory",
    "FederatedPeer",
    "PeerStatus",
    "AccessLevel",
    "ACLRule",
    "MemoryProvenance",
    "SharedMemory",
]
