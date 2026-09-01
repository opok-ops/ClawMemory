> **归档说明（v5.5.8）**：这是 v5.2.8（2026-07-30）的历史发布公告，已归档至
> `docs/archive/`。当前版本为 **v5.5.8**，请以 [CHANGELOG.md](../../CHANGELOG.md)
> 与 README 的版本记录为准。

# MindForge v5.2.8 更新公告

## 发布摘要
- **版本号**：v5.2.8
- **发布日期**：2026-07-30
- **项目状态**：稳定版 (Stable) + 实验性预览

MindForge v5.2.8 现已正式发布。本次更新包含**一项 P0 级核心修复**（`search` 命令跨进程失效）、两项稳定性修复，并首次带来**多 Agent 记忆空间**的实验性预览——这是通往 v6.0.0 的第一块基石。

---

## 🔍 核心修复：search 跨进程失效（P0）

`search` 是最常用的核心命令，但自 TF-IDF 索引引入以来一直存在一个隐蔽的严重问题：索引完全存储在进程内存中，CLI 每次运行都是全新进程，导致**跨进程搜索永远返回 0 结果**。

- `IndexEngine` 新增 `hydrate()` 水合能力，搜索前自动从 SQLite 加载全部可索引文档
- 新增模糊搜索补充召回：TF-IDF 词表滞后（新记忆未入词表）或 CJK 中文子串未命中时自动兜底
- 合并策略按 id 取高分，保证补充召回结果不被零分项截断
- 新增 3 个回归测试，防止该问题重演

## 🏷️ 标签解析统一（P1）

修复 `add --tags a,b` 逗号分隔被错误存为单个标签 `"a,b"` 的问题。现在空格分隔与逗号分隔可自由混用，单点归一化覆盖全部 15 个使用 `--tags` 的命令。

## 🤝 联邦模块修复（P2）

修复 `modules/federated.py` 中 `except sqlite3.OperationalError` 引用未导入模块导致的 NameError 隐患。

---

## 🌐 多 Agent 记忆空间（实验性 — v6.0.0 全量推送预览）

> ⚠️ **EXPERIMENTAL**：本功能为 v6.0.0 前瞻预览，API 在正式发布前可能变化。官网已同步标注"开发中"。

多个 AI Agent 在同一本地库内协作时，需要受控的共享机制——而不是互相能看见对方的全部记忆。多 Agent 记忆空间为此而生：

- **记忆空间（Space）**：命名的共享容器，归属某个 owner Agent
- **三级角色权限**：`owner` / `editor` / `reader`，broadcast 策略下仅 owner 可写
- **隐私护栏**：`PRIVATE` / `STRICT` 级别记忆**永远禁止**进入共享空间
- **冲突解决**：重复共享同一条记忆 = last-write-wins，条目版本号自动递增
- **审计追踪**：所有空间变更操作写入审计日志，随主库一起备份

### 新增 CLI 命令（7 个，均标注实验性）

```bash
mindforge space-create team-ai --agent leader          # 创建空间
mindforge space-add-member team-ai worker --role editor --agent leader
mindforge space-join team-ai --agent guest             # reader 自助加入
mindforge space-share team-ai <memory_id> --agent worker
mindforge space-memories team-space --agent guest      # 成员可读
mindforge space-list --mine --agent worker
mindforge space-stats                                  # 全局统计
```

### Python SDK

```python
from MindForge import MindForge

cm = MindForge(db_path="./data/memory.db", encrypted=False)
ma = cm.multi_agent  # EXPERIMENTAL

ma.create_space("team-ai", owner_agent="leader")
ma.add_member("team-ai", "worker", role="editor", actor="leader")
ma.share_memory("team-ai", memory_id, actor="worker")
```

**v6.0.0 路线图**：owner 转移、空间级加密、跨库空间同步、与联邦记忆网络打通。

---

## 📤 其他新命令

- `export-csv` — 导出记忆为 CSV（含路径安全校验，默认排除 PRIVATE/STRICT 记忆）
- `diff <memory_id>` — 对比记忆版本差异（unified diff 格式，配合 v5.2.7 版本历史使用）

## 🧪 测试

新增 6 个测试用例（搜索水合 ×3 + 多 Agent 空间 ×3），**全部 25 个测试通过**。

---

## 升级指南

### 方式一：通过源码更新（推荐）
```bash
git pull origin master
```

### 方式二：通过本地安装
```bash
pip install -e .
```

数据库自动迁移：首次运行时自动创建 `agent_spaces` / `agent_space_members` / `agent_space_items` 三张新表，不影响既有数据。

---

## 项目链接
- **GitHub 仓库**：[https://github.com/opok-ops/MindForge](https://github.com/opok-ops/MindForge)
- **官方文档**：[https://opok-ops.github.io/MindForge/](https://opok-ops.github.io/MindForge/)

感谢所有贡献者和用户对 MindForge 项目的支持。v6.0.0，敬请期待多 Agent 协作的完整形态。
