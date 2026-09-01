# MindForge API 命名规范（v5.5.8）

## 现状问题

当前三层架构（Facade / Storage / Query）的命名存在四类不一致：

1. **Facade 省略 `_memory` 后缀**：`add()` vs `add_memory()`、`get()` vs `get_memory()`
2. **Storage 内部前缀不统一**：`get_memory()` / `get_stats()` 有 `get_`，`add_memory()` / `list_memories()` 没有
3. **Facade 映射规则不固定**：有时去 `get_` 前缀（`stats()` ← `get_stats()`），有时去后缀（`cleanup()` ← `cleanup_expired()`）
4. **搜索方法语义模糊**：`search()` / `fuzzy_search()` / `search_by_tag()` / `vector_search()` 职责边界不清

---

## 规范原则

### 1. 分层命名职责

| 层 | 命名风格 | 说明 |
|---|---|---|
| **Facade** (`MindForge`) | 简洁动词，省略领域后缀 | 面向最终用户，`add()`、`get()`、`search()` |
| **Storage** (`StorageEngine`) | 显式领域后缀，`_memory` 统一 | 面向内部调用，`add_memory()`、`get_memory()` |
| **Query** (`QueryEngine`) | 策略动词 + 策略后缀 | `search()`、`hybrid_search()` |
| **Index** (`IndexEngine`) | 索引操作动词 | `index_memory()`、`search()` |

### 2. CRUD 统一动词

| 操作 | Facade | Storage | 说明 |
|---|---|---|---|
| 创建 | `add()` | `add_memory()` | 不用 `create`，统一用 `add` |
| 读取 | `get()` | `get_memory()` | 单条 |
| 列表 | `list()` | `list_memories()` | 多条 |
| 更新 | `update()` | `update_memory()` | |
| 删除 | `delete()` | `delete_memory()` | 软删除进回收站 |
| 恢复 | `restore()` | `restore_memory()` | 从回收站恢复 |
| 收藏 | `star()` | `star_memory()` | |
| 置顶 | `pin()` | `pin_memory()` | |

### 3. 查询方法命名

| 方法 | 语义 | 返回 |
|---|---|---|
| `search()` | 多路融合主搜索（TF-IDF + Fuzzy + Vector） | `List[Dict]` |
| `fuzzy_search()` | 纯模糊近似匹配（子串 + SequenceMatcher） | `List[Dict]` |
| `search_by_tag()` | 标签精确过滤 | `List[MemoryEntry]` |
| `vector_search()` | 纯向量相似度（Storage 层，暂不暴露 Facade） | `List[Dict]` |

### 4. 统计 / 元数据方法

Storage 层统一用 `get_` 前缀表示"只读查询"：

```
get_stats()          → 基础统计
get_detailed_stats() → 详细统计
get_config_summary() → 配置摘要
get_search_history() → 搜索历史
get_audit_log()      → 审计日志
```

Facade 层统一去掉 `get_` 前缀：

```
stats()              ← get_stats()
detailed_stats()     ← get_detailed_stats()
config_summary()     ← get_config_summary()
search_history()     ← get_search_history()
audit_log()          ← get_audit_log()
```

### 5. Drama 子模块

Drama 方法保持现有 `_drama` 后缀风格，与 Memory 的简洁风格区分：

```
add_drama() / get_drama() / list_dramas() / update_drama() / delete_drama()
```

这是合理的领域隔离，不需要改成 `add()` 形式。

---

## 迁移计划（建议分三批）

### 第一批：低风险（Storage 层内部统一）
- `count_memories()` → 保持（无 `get_`，与 `list_memories()` 一致）
- 确认所有 `get_*` 方法都是只读查询，无副作用

### 第二批：中风险（Facade 层补别名）
- 为 Facade 层所有方法添加 `_memory` 后缀别名（deprecated），给外部调用方迁移时间
- 例：`mf.add()` 保留，新增 `mf.add_memory()` 作为别名并标记 `@deprecated`

### 第三批：高风险（MCP 层统一）
- MCP `memory_search` → 改为调用 Facade `search()`，去掉 `_memory` 后缀
- 需要确认所有 MCP 客户端兼容后再切换

---

## 检查清单

- [ ] 所有 CRUD 方法遵循上表动词
- [ ] Storage 层 `get_*` 均为只读，无副作用
- [ ] Facade 层无 `get_` 前缀
- [ ] 搜索方法语义无重叠（`search` ≠ `fuzzy_search`）
- [ ] 新增方法先查本规范再命名
