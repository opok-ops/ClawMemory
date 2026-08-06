"""
MindForge v5.4.0 共享记忆冲突解决
=================================
联邦场景下，同一记忆可能被多个 peer 并发修改，产生冲突副本。
本模块实现两种解决策略：

  A. Last-Write-Wins（LWW）：
     - 基于 (version, last_modified_at, peer_id) 三元组字典序比较
     - 高 version 胜；同 version 比 modified_at；同时间比 peer_id（确定性兜底）
     - 保留败方为历史版本，写入 version_chain（不丢失数据）

  B. Version-Chain 合并（CRDT-lite）：
     - 把所有副本视为同一条记忆的版本链
     - 字段级合并：content 取 LWW 胜方；tags 取并集；metadata 字段级合并
     - 冲突字段标记 `conflict=true`，交上层人工裁决

设计原则：
  - 无外部依赖，纯 Python 标准库
  - 确定性：相同输入 → 相同输出
  - 可追溯：每次合并都写入 version_chain，保留败方记录
  - 可逆：败方版本保留在链上，可随时回滚
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class ReplicaState:
    """一份记忆副本的完整状态（用于冲突检测）

    一个 ReplicaState = 同一 memory_id 在某 peer 上的快照。
    """
    memory_id: str
    peer_id: str
    version: int = 1
    last_modified_at: float = 0.0
    content: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    importance: str = "MEDIUM"
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 修改签发者（created_by 或 last_modifier）
    modified_by: str = ""

    def lww_key(self) -> Tuple[int, float, str]:
        """LWW 比较键：version DESC, modified_at DESC, peer_id ASC

        返回的元组越大表示越新。
        peer_id 用升序作为 tie-breaker，保证多个相同时间戳的副本有确定性的胜者。
        """
        return (self.version, self.last_modified_at, self.peer_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "peer_id": self.peer_id,
            "version": self.version,
            "last_modified_at": self.last_modified_at,
            "content": self.content[:200],
            "category": self.category,
            "tags": list(self.tags),
            "importance": self.importance,
            "metadata": dict(self.metadata),
            "modified_by": self.modified_by,
        }


@dataclass
class MergeResult:
    """合并结果"""
    memory_id: str
    winner: Optional[ReplicaState] = None            # LWW 胜方
    losers: List[ReplicaState] = field(default_factory=list)  # 败方（保留为历史版本）
    merged_content: str = ""
    merged_tags: List[str] = field(default_factory=list)
    merged_metadata: Dict[str, Any] = field(default_factory=dict)
    conflict_fields: List[str] = field(default_factory=list)  # 字段级冲突标记
    strategy: str = "lww"   # lww / crdt_merge
    merged_at: float = field(default_factory=time.time)
    version_chain_appended: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "winner_peer": self.winner.peer_id if self.winner else None,
            "winner_version": self.winner.version if self.winner else 0,
            "losers": [{"peer": l.peer_id, "version": l.version} for l in self.losers],
            "merged_content": self.merged_content[:200],
            "merged_tags": list(self.merged_tags),
            "conflict_fields": list(self.conflict_fields),
            "strategy": self.strategy,
            "merged_at": self.merged_at,
            "version_chain_appended": list(self.version_chain_appended),
        }


# ---------------------------------------------------------------------------
# 冲突检测 + 合并引擎
# ---------------------------------------------------------------------------

class ConsensusEngine:
    """LWW + 版本链合并引擎

    使用方式：
        engine = ConsensusEngine()
        result = engine.merge_replicas([replica_a, replica_b, replica_c])
        if result.winner:
            apply_to_storage(result)
    """

    def __init__(self,
                 strategy: str = "lww",
                 prefer_higher_importance: bool = True,
                 tag_merge: str = "union",
                 content_merge_on_conflict: str = "winner"):
        """
        Args:
            strategy: 'lww' 或 'crdt'（crdt=字段级合并）
            prefer_higher_importance: content 冲突时，importance 更高者胜
            tag_merge: 'union' / 'winner' / 'intersection'
            content_merge_on_conflict: 'winner' / 'concat' / 'manual'
        """
        if strategy not in ("lww", "crdt"):
            raise ValueError(f"unknown strategy: {strategy}")
        self.strategy = strategy
        self.prefer_higher_importance = prefer_higher_importance
        self.tag_merge = tag_merge
        self.content_merge_on_conflict = content_merge_on_conflict

    # -- helpers -----------------------------------------------------------

    _IMPORTANCE_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

    @classmethod
    def _rank(cls, imp: str) -> int:
        return cls._IMPORTANCE_RANK.get((imp or "").upper(), 2)

    @staticmethod
    def _is_same_memory(replicas: List[ReplicaState]) -> bool:
        if not replicas:
            return True
        first = replicas[0].memory_id
        return all(r.memory_id == first for r in replicas)

    # -- LWW ---------------------------------------------------------------

    def pick_lww_winner(self, replicas: List[ReplicaState]) -> Tuple[Optional[ReplicaState], List[ReplicaState]]:
        """LWW 选主：返回 (winner, losers)"""
        if not replicas:
            return None, []
        if len(replicas) == 1:
            return replicas[0], []

        # 先按 importance 优先级过滤：如果存在 CRITICAL 而其他是 LOW，且 prefer_higher_importance=True
        # 则只从 CRITICAL 中选（视为「权威副本」）
        candidates = list(replicas)
        if self.prefer_higher_importance:
            max_rank = max(self._rank(r.importance) for r in candidates)
            # 只保留 rank 差 ≤ 1 的副本（避免低重要度副本因时间戳新而覆盖关键事实）
            high = [r for r in candidates if self._rank(r.importance) >= max_rank - 1]
            if len(high) < len(candidates):
                # 把低重要度的直接判为 loser
                low = [r for r in candidates if self._rank(r.importance) < max_rank - 1]
                candidates = high
                initial_losers = low
            else:
                initial_losers = []
        else:
            initial_losers = []

        # 在 candidates 内按 LWW key 选最大
        winner = max(candidates, key=lambda r: r.lww_key())
        losers = [r for r in replicas if r is not winner]
        return winner, losers

    # -- CRDT 字段级合并 ---------------------------------------------------

    def _merge_tags(self, replicas: List[ReplicaState],
                    winner: Optional[ReplicaState]) -> List[str]:
        if self.tag_merge == "winner":
            return list(winner.tags) if winner else []
        if self.tag_merge == "intersection":
            if not replicas:
                return []
            sets = [set(r.tags) for r in replicas]
            inter = sets[0]
            for s in sets[1:]:
                inter &= s
            return sorted(inter)
        # union（默认）
        out: List[str] = []
        seen: set = set()
        for r in replicas:
            for t in r.tags:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
        return out

    def _merge_metadata(self, replicas: List[ReplicaState],
                        winner: Optional[ReplicaState]) -> Tuple[Dict[str, Any], List[str]]:
        """字段级合并 metadata，返回 (merged, conflict_fields)"""
        if not winner:
            return {}, []
        merged: Dict[str, Any] = dict(winner.metadata)
        conflicts: List[str] = []

        # 收集所有副本中相同 key 的不同 value
        all_keys: set = set()
        for r in replicas:
            all_keys.update(r.metadata.keys())

        for k in all_keys:
            values_by_peer: Dict[str, Any] = {}
            for r in replicas:
                if k in r.metadata:
                    values_by_peer[r.peer_id] = r.metadata[k]
            unique_vals = set()
            for v in values_by_peer.values():
                # 不可哈希的转 str
                try:
                    unique_vals.add(v)
                except TypeError:
                    unique_vals.add(str(v))
            if len(unique_vals) > 1:
                conflicts.append(f"metadata.{k}")
                # 取 LWW 胜方的值（已在 merged 中），但保留所有副本的值用于 audit
                merged[f"_conflict_{k}"] = values_by_peer
            # 否则保留 winner 的值
        return merged, conflicts

    def _merge_content(self, replicas: List[ReplicaState],
                       winner: Optional[ReplicaState],
                       losers: List[ReplicaState]) -> Tuple[str, List[str]]:
        """合并 content 字段"""
        if not winner:
            return "", []
        if not losers:
            return winner.content, []

        # 检查是否有 content 冲突
        winner_content = winner.content or ""
        conflict = False
        for l in losers:
            if (l.content or "") != winner_content:
                conflict = True
                break

        if not conflict:
            return winner_content, []

        # 有冲突，按策略处理
        if self.content_merge_on_conflict == "concat":
            # 拼接所有副本的 content（去重保序）
            seen: set = set()
            parts: List[str] = []
            for r in [winner] + losers:
                c = (r.content or "").strip()
                if c and c not in seen:
                    seen.add(c)
                    parts.append(f"[{r.peer_id}@v{r.version}]\n{c}")
            return "\n\n---\n\n".join(parts), ["content"]
        elif self.content_merge_on_conflict == "manual":
            # 不合并，标记冲突，等人工裁决
            return winner_content, ["content"]
        # winner（默认）
        return winner_content, ["content"]

    # -- 主入口 ------------------------------------------------------------

    def merge_replicas(self, replicas: List[ReplicaState]) -> MergeResult:
        """合并一组副本，返回 MergeResult"""
        if not replicas:
            return MergeResult(memory_id="", strategy=self.strategy)
        if not self._is_same_memory(replicas):
            raise ValueError("所有副本必须属于同一 memory_id")
        memory_id = replicas[0].memory_id

        # 单一副本：直接返回
        if len(replicas) == 1:
            r = replicas[0]
            return MergeResult(
                memory_id=memory_id,
                winner=r,
                losers=[],
                merged_content=r.content,
                merged_tags=list(r.tags),
                merged_metadata=dict(r.metadata),
                conflict_fields=[],
                strategy=self.strategy,
                version_chain_appended=[{
                    "by": r.modified_by or r.peer_id,
                    "at": r.last_modified_at,
                    "version": r.version,
                    "reason": "single_replica_no_merge",
                }],
            )

        # LWW 选主
        winner, losers = self.pick_lww_winner(replicas)

        # 字段级合并
        merged_tags = self._merge_tags(replicas, winner)
        merged_metadata, meta_conflicts = self._merge_metadata(replicas, winner)
        merged_content, content_conflicts = self._merge_content(replicas, winner, losers)

        conflict_fields = content_conflicts + meta_conflicts
        # category 冲突
        if winner and any(l.category != winner.category for l in losers):
            conflict_fields.append("category")
        # importance 冲突
        if winner and any(l.importance != winner.importance for l in losers):
            conflict_fields.append("importance")

        # 追加 version_chain 记录
        chain_entries: List[Dict[str, Any]] = []
        for l in losers:
            chain_entries.append({
                "by": l.modified_by or l.peer_id,
                "at": l.last_modified_at,
                "version": l.version,
                "peer_id": l.peer_id,
                "reason": "merge_loser" if l is not winner else "merge_winner",
                "lost_to": winner.peer_id if winner else None,
            })
        if winner:
            chain_entries.append({
                "by": winner.modified_by or winner.peer_id,
                "at": time.time(),
                "version": winner.version + 1,
                "peer_id": winner.peer_id,
                "reason": "merge_winner" + ("_with_conflicts" if conflict_fields else ""),
            })

        return MergeResult(
            memory_id=memory_id,
            winner=winner,
            losers=losers,
            merged_content=merged_content,
            merged_tags=merged_tags,
            merged_metadata=merged_metadata,
            conflict_fields=conflict_fields,
            strategy=self.strategy,
            version_chain_appended=chain_entries,
        )

    # -- 增量更新 ----------------------------------------------------------

    def merge_with_existing(self,
                             existing: Optional[ReplicaState],
                             incoming: ReplicaState) -> MergeResult:
        """把一份新到的副本合并到当前状态

        - 如果 existing 为 None：incoming 直接成为 winner
        - 如果 incoming 的 version ≤ existing 的 version：incoming 成为 loser
        - 如果 incoming 的 version > existing 的 version：incoming 成为 winner
        """
        if existing is None:
            return self.merge_replicas([incoming])
        # 同 memory_id 校验
        if existing.memory_id != incoming.memory_id:
            raise ValueError("memory_id 不一致，不能合并")
        return self.merge_replicas([existing, incoming])

    # -- 批量同步 ----------------------------------------------------------

    def detect_conflicts(self, replicas: List[ReplicaState]) -> List[str]:
        """检测一组副本中的冲突字段（dry-run，不合并）"""
        if len(replicas) < 2:
            return []
        conflicts: List[str] = []
        # content
        contents = {(r.content or "") for r in replicas}
        if len(contents) > 1:
            conflicts.append("content")
        # category
        cats = {r.category for r in replicas}
        if len(cats) > 1:
            conflicts.append("category")
        # importance
        imps = {r.importance for r in replicas}
        if len(imps) > 1:
            conflicts.append("importance")
        # tags（顺序无关，只看集合差异）
        tag_sets = [frozenset(r.tags) for r in replicas]
        if len(set(tag_sets)) > 1:
            conflicts.append("tags")
        # metadata keys
        all_keys: set = set()
        for r in replicas:
            all_keys.update(r.metadata.keys())
        for k in all_keys:
            vals = set()
            for r in replicas:
                if k in r.metadata:
                    try:
                        vals.add(r.metadata[k])
                    except TypeError:
                        vals.add(str(r.metadata[k]))
            if len(vals) > 1:
                conflicts.append(f"metadata.{k}")
        return conflicts


__all__ = [
    "ConsensusEngine",
    "ReplicaState",
    "MergeResult",
]
