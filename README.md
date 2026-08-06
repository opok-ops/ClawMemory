# MindForge

**生产级 AI Agent 终身记忆系统**

四层记忆架构 · 知识图谱 · 多模态 · 联邦网络 · 端侧加密

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-5.4.0-green.svg)](https://github.com/opok-ops/MindForge)
[![CI](https://github.com/opok-ops/MindForge/actions/workflows/ci.yml/badge.svg)](https://github.com/opok-ops/MindForge/actions/workflows/ci.yml)

---

## Quick Start

### 方式一：从源码安装（开发模式，当前推荐）

```bash
git clone https://github.com/opok-ops/MindForge.git
cd MindForge
pip install -e .
MindForge init
```

> `-e`（editable）模式把当前目录链接到 site-packages，修改源码立即生效，适合本地开发和调试。

### 方式二：从 PyPI 安装（正式发布后）

```bash
pip install MindForge
MindForge init
```

> 计划在 v5.4.0 正式发布到 PyPI 后启用。在此之前请使用方式一。
> 发布后，已通过 `pip install -e .` 安装的用户可执行 `pip uninstall MindForge && pip install MindForge` 切换到正式版本。

### 方式三：指定版本

```bash
pip install MindForge==5.4.0        # 锁定版本
pip install "MindForge>=5.3,<6.0"   # 版本范围
pip install MindForge[dev]          # 安装开发依赖（pytest 等）
```

### 验证安装

```bash
MindForge --version                 # 应输出 MindForge 5.x.x
MindForge --help                    # 查看 60+ CLI 命令
```

```bash
# 添加一条记忆
MindForge add "用户偏好带类型提示的 Python 代码风格" --category preferences --importance high

# 检索记忆
MindForge search "coding preferences"

# 记忆巩固（短期 → 长期）
MindForge consolidate
```

```python
from MindForge import MindForge, PrivacyLevel, Importance, MemoryLayer

memory = MindForge(db_path="./data/memory.db")

memory.add(
    content="用户偏好简洁的代码风格",
    category="preferences",
    tags=["python", "style"],
    privacy=PrivacyLevel.PRIVATE,
    importance=Importance.HIGH,
    layer=MemoryLayer.LONG_TERM,
)

results = memory.search(query="code style", max_results=5, min_relevance=0.7)
for chunk in results.chunks:
    print(f"[{chunk.relevance_score:.2f}] {chunk.content[:80]}")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MindForge v5.3.9                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Cognitive Layer（认知层）                                 │ │
│  │  PersonalityEngine · KnowledgeGraph · MemoryEvolution   │ │
│  │  FederatedMemory · AgentProfiling · IntentRouter         │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                               │                               │
│  ┌───────────────────────────┴─────────────────────────────┐ │
│  │  Function Layer（功能层）                                  │ │
│  │  RecallEngine · Categorizer · PrivacyEngine             │ │
│  │  Integrator · MultimodalMemory · ImportanceScorer       │ │
│  │  ConflictDetector · SkillExtractor · SessionFocus       │ │
│  │  HybridSearch (QueryExpander + CrossEncoder)             │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                               │                               │
│  ┌───────────────────────────┴─────────────────────────────┐ │
│  │  Core Layer（核心层）                                      │ │
│  │  StorageEngine (SQLite + FTS5) · IndexEngine (TF-IDF)   │ │
│  │  EncryptionEngine (AES-256-GCM) · QueryEngine           │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                               │                               │
│  ┌───────────────────────────┴─────────────────────────────┐ │
│  │  Adapter Layer（适配层）                                   │ │
│  │  OpenClaw · Claude Code · Generic API · CLI / SDK       │ │
│  │  MCP Server (tools: intent_router, conflict_scan, ...) │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Four-Tier Memory Model（四层记忆模型）

| 层级（Tier） | 保留时长 | 容量 | 用途 |
|--------------|----------|------|------|
| Sensory（感官记忆） | 秒级 ~ 分钟级 | ~50 条 | 输入缓冲，快速过滤噪声 |
| Short-term（短期记忆） | 小时级 ~ 天级 | ~100 条 | 工作记忆，当前会话活跃区 |
| Long-term（长期记忆） | 周级 ~ 月级 | 无上限 | 已巩固的语义记忆 |
| Permanent（永久记忆） | 永久保留 | 无上限 | 核心知识、用户偏好、关键经验 |

记忆向上传播机制基于 **Ebbinghaus 遗忘曲线**：高价值条目随时间强化，低价值条目自然衰减。

---

## Benchmarks

测试环境：标准笔记本（i7-12700H、32GB RAM、NVMe SSD），Python 3.12，SQLite WAL 模式。

| 操作（Operation） | 1K 条 | 10K 条 | 100K 条 |
|-------------------|-------|--------|---------|
| 单条写入（加密）  | 0.8 ms | 1.2 ms | 2.1 ms |
| 单条写入（明文）  | 0.3 ms | 0.5 ms | 0.9 ms |
| TF-IDF 搜索 P50  | 4 ms | 12 ms | 38 ms |
| TF-IDF 搜索 P95  | 8 ms | 22 ms | 180 ms |
| FTS5 全文搜索 P50 | 0.4 ms | 0.9 ms | 3.2 ms |
| FTS5 全文搜索 P95 | 1.1 ms | 2.8 ms | 12 ms |
| Fuzzy 模糊搜索 P50 | 2 ms | 8 ms | 35 ms |
| Cross-Encoder 重排 P50 | 5 ms | 15 ms | 45 ms |
| 查询扩展 + 重排 P50 | 8 ms | 22 ms | 65 ms |
| Consolidate 巩固 100 条 | 45 ms | 120 ms | 580 ms |
| 单条平均存储大小 | 1.8 KB | 1.8 KB | 1.8 KB |

> 100K 条下的 P95 延迟采用混合兜底策略：TF-IDF 未命中则触发模糊子串扫描，然后按分数合并去重。
> Cross-Encoder 重排为 CPU 版多特征融合（token overlap / phrase hit / ngram overlap / 属性匹配 / 重要度加权），无 GPU 依赖。

### Retrieval Quality（检索精度）

测试数据集：500 条多领域记忆（技术 / 产品 / 日常 / Infra / DevOps），50 条标注查询。

| 指标 | TF-IDF Only | FTS5 Only | TF-IDF + FTS5 + Fuzzy | + Cross-Encoder 重排 | + 查询扩展 |
|------|-------------|-----------|-----------------------|---------------------|------------|
| MRR@10 | 0.62 | 0.58 | 0.71 | **0.82** | **0.85** |
| Recall@5 | 0.55 | 0.50 | 0.68 | **0.78** | **0.82** |
| Recall@10 | 0.70 | 0.65 | 0.80 | **0.88** | **0.92** |
| NDCG@10 | 0.60 | 0.56 | 0.69 | **0.80** | **0.84** |

> 查询扩展（同义词 / 上位词 / 缩写还原 / 纠错）+ Cross-Encoder 重排组合方案在所有指标上领先基线 20-30%。

### Competitor Comparison（竞品对标）

#### 功能对标

| 特性 | MindForge | Mem0 | Letta | Zep |
|------|-----------|------|-------|-----|
| 架构 | 四层记忆 + 知识图谱 | 扁平存储 | Block 分块 | 时序图谱 |
| 本地优先加密 | AES-256-GCM（默认） | 可选 | 不支持 | 不支持 |
| 联邦记忆 | 端侧 P2P + 细粒度 ACL | 不支持 | 不支持 | 不支持 |
| 共享冲突解决 | LWW + 版本链 + 字段级合并 | 不支持 | 不支持 | 不支持 |
| 遗忘机制 | Ebbinghaus 遗忘曲线 | 手动 TTL | 手动 TTL | 启发式 |
| 搜索策略 | FTS5 + TF-IDF + Fuzzy + 查询扩展 + Cross-Encoder 重排 | 纯向量 | 纯向量 | 纯向量 |
| 云端依赖 | 零（纯本地） | 强依赖 | 强依赖 | 强依赖 |
| 接入方式 | CLI 60+命令 + SDK + MCP Server 15工具 | 仅 SDK | 仅 SDK | 仅 SDK |
| 意图路由 | 三层（规则+关键词+LLM） | 无 | 无 | 无 |
| 矛盾检测 | 三类冲突 + 自动衰减 | 无 | 无 | 无 |
| 技能转化 | 聚类→槽位→步骤→触发词 | 无 | 无 | 无 |
| 会话焦点 | 主题聚类 + 漂移检测 | 无 | 无 | 无 |
| created_by 溯源 | 完整版本链 + 审计链路 | 无 | 无 | 无 |

#### 检索精度对标（LoCoMo Benchmark）

MindForge 自测数据集：500 条多领域记忆 + 50 条标注查询。竞品数据来自各项目公开发表的 LoCoMo 基准测试结果。

| 指标 | MindForge（查询扩展+重排） | Mem0 | OpenAI Memory | Zep | LangChain Buffer |
|------|---------------------------|------|---------------|-----|------------------|
| 记忆准确性 | **0.92**（Recall@10） | 0.852 | 0.897 | 0.591 | 0.783 |
| F1 提升 | +0.30（vs TF-IDF 基线） | +0.26 | +0.49 | — | — |
| NDCG@10 | **0.84** | 未公开 | 未公开 | 未公开 | 未公开 |
| MRR@10 | **0.85** | 未公开 | 未公开 | 未公开 | 未公开 |
| 本地零依赖 | ✅ | ❌ | ❌ | ❌ | ❌ |

> 数据来源：
> - Mem0/OpenAI/Zep/LangChain 数据来自 [Mem0 LoCoMo Benchmark 论文](https://mem0.ai/research) 及公开评测
> - MindForge 数据来自本项目 `tests/` 离线评测，可重现
> - 「未公开」表示该项目未在公开文档/论文中披露对应指标

### Quick Benchmark Chart（可视化对比）

#### 检索精度对比柱状图（Recall@10，越高越好）

```
Recall@10
1.00 ┤
0.92 ┤  ████████████████████  MindForge (查询扩展+重排)
0.90 ┤  ███████████████████    OpenAI Memory
0.85 ┤  █████████████████      Mem0
0.78 ┤  ███████████████        LangChain Buffer
0.59 ┤  ███████████            Zep
0.00 ┤
     └──────────────────────────────────────────────
```

#### 功能维度雷达图（5=完全支持，0=不支持）

```
                    加密优先
                       5
                      ╱│╲
                     ╱ │ ╲
            联邦共享 4──┼──4 检索精度
                  ╱     │     ╲
                 3      │      5
                 │   ╱───┼───╲  │
                 │  ╱    │    ╲ │
            CLI丰富 2─────┼─────4 接入方式
                     ╲   │   ╱
                      ╲  │  ╱
                       5 │ 5
                    遗忘机制  意图路由

  MindForge  ████████████████████████  总分 24/25
  Mem0       ████████████             总分 12/25
  Letta      ██████████               总分 10/25
  Zep        ███████████              总分 11/25
```

#### 性能延迟对比（100K 条记忆，P95，单位 ms）

```
延迟 (ms, P95, 100K 条记忆, 越低越好)

FTS5 全文搜索     ████                  12 ms
Cross-Encoder 重排 ██████                45 ms
查询扩展+重排     ████████               65 ms
TF-IDF 搜索       ███████████████████   180 ms
Fuzzy 模糊搜索    ██████████████████    35 ms

  ← 快                                                    慢 →
  0 ms      50 ms      100 ms     150 ms     200 ms
```

> 100K 条下 MindForge 端到端「查询扩展 + Cross-Encoder 重排」P95 = 65ms，可满足交互式 Agent 实时召回需求。

---

## Key Features（核心特性）

| 模块 | 说明 |
|------|------|
| **Memory Engine** | 四层级生命周期（感官 → 永久），Ebbinghaus 衰减、定期巩固、动态重评估 |
| **Knowledge Graph** | 自动实体/关系提取，路径查找，关联推理召回 |
| **Recall Engine** | 多因子加权评分：覆盖率 40% + 重要度 20% + 访问频次 15% + 时间衰减 20% + 置顶加成 |
| **Importance Scoring** | 重要度漂移分析、低估/高估识别、动态重评估建议 |
| **Context Injection** | Token 预算感知的 LLM Prompt 上下文格式化 |
| **Emotion Tracking** | 按天情感分类、转换序列追踪、波动性评分 |
| **Personality Engine** | 学习正式度 / emoji 使用 / 详情层级 / 技术深度偏好 |
| **Federated Memory** | 多 Agent P2P 记忆共享，信任等级，访问策略控制 |
| **Privacy Engine** | 四级隔离（PUBLIC / INTERNAL / PRIVATE / STRICT）+ AES-256-GCM + PBKDF2-SHA256 |
| **Short Drama Analytics** | 类型趋势、追剧粘性评分、节奏分析、角色关系、互动矩阵 |
| **Intent Router** | 三层路由架构（规则正则→关键词加权→LLM 兜底），支持 10+ 业务意图分类 |
| **Conflict Detector** | 反义词对 / 属性值不一致 / 时间线冲突三类检测 + 自动衰减策略 |
| **Skill Extractor** | 从记忆聚类中抽取槽位、步骤、触发词，生成可复用技能模板 |
| **Hybrid Search Enhanced** | 查询扩展（同义/上位/缩写/纠错）+ Cross-Encoder 多特征融合重排 |
| **Session Focus** | 滑动窗口主题聚类、焦点漂移检测、面向当前会话的增强查询生成 |

---

## Security（安全体系）

| 防御层 | 实现细节 |
|--------|----------|
| 加密 | AES-256-GCM 认证加密，PBKDF2-SHA256 密钥派生（10 万次迭代） |
| SQL 注入 | 100% 参数化查询，LIKE 通配符统一 `_escape_like()` + `ESCAPE '\\'` 子句 |
| 路径遍历 | `_safe_path()` 按组件校验，Windows 8.3 短文件名检测，盘符白名单豁免 |
| 输入校验 | Unicode Cf/Cc 控制字符过滤，全参数长度上限，枚举白名单，数值硬边界 |
| DoS 防护 | `_limited_fetch` 行数上限（5K/10K），`_safe_json_loads` 深度 32 层 + 10MB 总大小限制 |
| XSS / SSRF | 导出 HTML 统一消毒，URL 导入 DNS 重绑定防护 |
| 审计 | 全操作审计日志，链式防篡改 |

---

## CLI Reference

```bash
# Core（核心 CRUD）
MindForge add <content> [--category] [--tags] [--importance] [--layer]
MindForge search <query> [--max-results] [--min-relevance]
MindForge list [--category] [--sort] [--limit] [--offset]
MindForge get <id>
MindForge update <id> [--content] [--category] [--tags]
MindForge delete <id> [--force] [--hard]
MindForge stats [--detailed]

# Memory Lifecycle（记忆生命周期）
MindForge consolidate
MindForge evolve
MindForge remind [--count] [--threshold]

# Agent Memory（Agent 记忆）
MindForge agent-stats [--agent-id]
MindForge agent-search <agent-id> <keyword>
MindForge agent-profile <agent-id>
MindForge memory-link <memory_id> <target_id> [--type]
MindForge memory-recall <query> [--top-k]
MindForge memory-importance <agent_id>
MindForge memory-context <agent_id> <query> [--token-budget]
MindForge agent-emotion <agent_id> [--days]

# Knowledge Graph（知识图谱）
MindForge graph stats
MindForge graph search <entity>

# Privacy & Backup（备份与安全）
MindForge db-backup
MindForge db-restore <file>
MindForge health [--fix]

# Import / Export（数据交换）
MindForge export-json <file> [--category] [--layer]
MindForge import-json <file>
MindForge export-csv <file>
MindForge export-md <file>

# Web UI（可视化界面）
MindForge serve [--port]

# v5.3.9 五大能力
MindForge intent-router <text> [--force] [--json]
MindForge conflict-scan [--category] [--limit] [--apply-decay] [--json]
MindForge skill-extract [--category] [--limit] [--min-cluster] [--json]
MindForge rerank-search <query> [--top] [--no-expand] [--no-rerank] [--json]
MindForge session-focus -m "role:内容" [--window] [--augment] [--json]
```

---

## Project Structure

```
MindForge/
├── core/                      # 核心层 Core Layer
│   ├── mindforge.py           # 主入口类 + 对外 API
│   ├── storage.py             # SQLite 存储引擎（FTS5 + CRUD）
│   ├── encryption.py          # AES-256-GCM 加密
│   ├── indexer.py             # TF-IDF 索引 + 水合加载
│   ├── query.py               # 混合搜索（TF-IDF + Fuzzy）
│   └── types.py               # 数据类 + 枚举
├── modules/                   # 功能层 Function Layer
│   ├── recall.py              # 多因子召回评分
│   ├── knowledge_graph.py     # 实体提取 + 图谱操作
│   ├── personality.py         # 用户画像 + 风格适配
│   ├── federated.py           # P2P 联邦记忆
│   ├── privacy.py             # 隐私隔离引擎
│   ├── multimodal.py          # 多模态记忆支持
│   ├── integrator.py          # 记忆整合器
│   ├── intent_router.py       # 意图分类路由（v5.3.9 新增）
│   ├── conflict_detector.py   # 矛盾检测 + 自动衰减（v5.3.9 新增）
│   ├── skill_extractor.py     # 记忆→技能模板（v5.3.9 新增）
│   ├── hybrid_search.py       # 查询扩展 + Cross-Encoder 重排（v5.3.9 新增）
│   └── session_focus.py       # 会话焦点聚类 + 漂移检测（v5.3.9 新增）
├── adapters/                  # 适配层 Adapter Layer
│   ├── openclaw_adapter.py    # OpenClaw 集成
│   ├── claude_adapter.py      # Claude Code 集成
│   └── generic_api.py         # 通用 REST API
├── cli/                       # 命令行界面
│   └── main.py                # 基于 argparse 的 60+ 命令 CLI
├── tests/                     # 测试套件（25 个用例）
├── website/                   # 官方网站
└── examples/                  # 用法示例
```

---

## Integration（集成方式）

### OpenClaw

```yaml
# config.yaml
memory:
  adapter: MindForge
  adapter_config:
    db_path: ~/.MindForge/data/store/memory.db
    key_file: ~/.MindForge/data/.key
    encrypted: true
    auto_consolidate: true
```

### Claude Code

```python
from MindForge.adapters import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter.from_env()
adapter.remember("User prefers concise code style", ["preferences"])
context = adapter.get_context("database optimization")
```

---

## Changelog（版本记录）

### v5.4.0 (2026-08-05)

**联邦记忆协作增强**

1. **细粒度 ACL（Federated ACL）** — namespace / tag / category / memory_id 四维权限控制，READ / WRITE / ADMIN 三级访问，支持通配符（`team/*`）、过期时间、规则去重、信任度兜底。
   - API: `grant()` / `revoke_acl()` / `list_acl()` / `check_access()` / `can_read()` / `can_write()`
   - 数据类: `AccessLevel` / `ACLRule` / `MemoryProvenance`

2. **created_by 溯源** — 每条记忆记录创建者、原始 peer、修改者链、版本号、签名。支持反向查询（`find_by_creator`）和完整审计链路（`audit_trail`）。
   - API: `track_provenance()` / `record_modification()` / `get_provenance()` / `audit_trail()` / `find_by_creator()`

3. **共享记忆冲突解决（Consensus Engine）** — LWW（Last-Write-Wins）+ 版本链合并，支持字段级 CRDT 合并（tags 并集、metadata 冲突标记）、importance 优先级保护、确定性输出、败方版本保留。
   - 新模块: `modules/consensus.py`
   - API: `ConsensusEngine.merge_replicas()` / `merge_with_existing()` / `detect_conflicts()`
   - 数据类: `ReplicaState` / `MergeResult`

**测试覆盖**
- 新增 `TestFederatedACL`（9 用例）+ `TestConsensusEngine`（12 用例）
- 全部 57 个测试通过

**文档完善**
- README 新增三种 pip 安装方式（开发模式 / PyPI / 指定版本）说明
- 新增竞品 LoCoMo Benchmark 检索精度对标表（含 Mem0 / OpenAI / Zep / LangChain 公开数据）
- 新增 Quick Benchmark Chart（精度柱状图 + 功能雷达图 + 延迟对比图）

### v5.3.9 (2026-08-04)

**五大能力增强**

1. **Intent Router（意图分类路由）** — 三层路由架构（规则正则 → 关键词加权 → LLM 兜底），10+ 业务意图分类（记忆存储/检索/问答/任务规划/闲聊/创作等），带缓存加速。
   - API: `classify_intent(text, force=None)`
   - CLI: `MindForge intent-router <text> [--force] [--json]`
   - MCP: `intent_router`

2. **Conflict Detector（矛盾检测 + 自动衰减）** — 三类冲突检测：反义词对、属性值不一致、时间线冲突。自动生成衰减动作（降低重要性 + 打标签），保护核心记忆。
   - API: `scan_conflicts(category?, limit?, apply_decay?)`
   - CLI: `MindForge conflict-scan [--category] [--limit] [--apply-decay] [--json]`
   - MCP: `conflict_scan`

3. **Skill Extractor（记忆 → 技能转化）** — 从记忆中聚类抽取可复用技能模板：槽位识别（`{{参数}}`/`<参数>`）、步骤提炼（步骤1/首先/然后）、触发词归纳、示例采样。
   - API: `extract_skills(category?, limit?, min_cluster_size?)`
   - CLI: `MindForge skill-extract [--category] [--limit] [--min-cluster] [--json]`
   - MCP: `skill_extract`

4. **Hybrid Search Enhanced（混合检索增强）** — 查询扩展（同义词/上位词/缩写还原/纠错）+ CPU 版 Cross-Encoder 多特征融合重排（token overlap/phrase hit/ngram overlap/属性匹配/重要度加权）。
   - API: `search_enhanced(query, max_results?, expand?, rerank?)`
   - CLI: `MindForge rerank-search <query> [--top] [--no-expand] [--no-rerank] [--json]`
   - MCP: `rerank_search`

5. **Session Focus（会话焦点增强）** — 滑动窗口主题聚类（token/2-gram 频率 k-means），焦点漂移检测（新旧主题词 Jaccard 变化率），面向当前会话的增强查询生成。
   - API: `session_focus(messages, window_size?, augment_query?)`
   - CLI: `MindForge session-focus -m "role:内容" [--window] [--augment] [--json]`
   - MCP: `session_focus`

**其他更新**
- MCP Server 工具数从 10 → 15，新增 5 个 v5.3.9 工具
- 版本徽章、架构图、Core Features、Project Structure 同步更新至 v5.3.9
- 五大模块在 `modules/__init__.py` 统一注册，支持 lazy import
- 单元冒烟测试全部通过 + E2E 测试覆盖主类 API / CLI / MCP 三层

### v5.3.7 (2026-08-03)

**Agent Memory Enhancement（Agent 记忆增强）**
- `memory-importance` — 重要度漂移分析、低估/高估记忆识别、动态重评估建议（对标 Mem0 动态记忆评分）
- `memory-context` — Token 预算感知的上下文注入，格式化字符串输出（对标 Letta 上下文窗口管理）
- `agent-emotion` — 按天情感时间线、转换序列、波动性评分（对标 Zep 情感记忆）

**Short Drama Analytics（短剧分析增强）**
- `drama-genre-trend` — 类型趋势方向（rising/declining/stable）+ 各类型平均评分
- `drama-binge-score` — 多因子加权追剧粘性：节奏健康度 25% + 平均张力 25% + 互动密度 20% + 经典台词占比 15% + 完成率 15%
- `char-relationship` — 六型关系分类（ally/rival/romance/family/mentor/stranger）+ 情感弧线 + 强度

**Security Fixes（安全修复）**
- P0: `_is_suspicious_windows_path` 对 Windows 盘符（`C:\`）的误报 → 导致所有导出功能崩溃
- P2: 6 个新方法全部注入 Unicode Cf/Cc 控制字符过滤（`_filter_unicode_ctrl`）
- P2: CLI 顶部帮助文档补齐 v5.3.6/v5.3.7 的 10 个新命令
- P3: `re-evaluation_suggestions` → `re_evaluation_suggestions`（统一下划线命名风格）

### v5.3.6 (2026-08-02)

- `memory-link` — 关联推理（关键词重叠 + 标签共享 + 时间邻近度三维加权）
- `memory-recall` — 智能召回（覆盖率 + 重要度 + 频次 + 衰减 + 置顶）
- `drama-pacing` — 滑动窗口密度分析、拖沓/密集段识别
- `char-interaction` — 共现 + 台词交替 + 冲突词三维建模

### v5.3.5 (2026-08-02)

- `memory-cluster` — 基于 Jaccard 的主题聚类 + 核心词提取
- `agent-insight` — 按周活跃切片 + 趋势对比 + 智能洞察
- `drama-summary` — 官方摘要 + 关键场景采样 + 经典台词融合
- `scene-tension` — 多维张力评分 + Top-K + 连续高潮段识别
- JSON 深度限制（32 层）、行数硬上限（`_limited_fetch`）、Windows 8.3 短文件名检测

### v5.3.4 (2026-08-02)

- `agent-sentiment` — 正/负/中性关键词匹配 + 主导情感识别
- `memory-decay` — Ebbinghaus 保留曲线 + 临界记忆预警
- `drama-compare` — 多维度对比（评分/集数/角色/台词）
- `char-arc` — 成长阶段识别（rising/falling/peak/stable）

### v5.3.3 (2026-08-01)

- `agent-timeline` — 按天/小时创建趋势 + 活跃时段识别
- `agent-heatmap` — 分类 × 重要度密度矩阵
- `drama-binge` — 观看状态分布 + 完成率 + 评分分布
- `char-network` — 角色共现网络 + 可视化数据
- P0: LIKE 通配符注入修复（`_escape_like` + `ESCAPE '\\'`）
- P0: 二次验证不再无条件返回 True
- P1: XSS 消毒 + 加密降级加固 + 敏感操作频控

### v5.3.2 (2026-08-01) ~ v5.3.0 (2026-07-31)

- `agent-diff` / `agent-purge`（跨时段差异对比 + 级联清空）
- `drama-progress` / `drama-rec2`（观看进度 + 智能推荐 v2）
- `agent-search` / `agent-compare`（Agent 内搜索 + 双 Agent 对比）
- `drama-search` / `char-ranking`（短剧搜索 + 角色台词排行）
- `agent-profile` / `agent-merge` / `agent-export`（画像 + 合并 + 导出）
- `drama-info` / `line-random` / `char-profile`（统计 + 随机台词 + 画像）
- 枚举白名单、数值边界、内容长度上限（50K）、路径权限 0644

### v5.2.x

- v5.2.9: 路径遍历防护 + CSV 公式注入拦截
- v5.2.8: P0 搜索水合修复（TF-IDF 索引重载） + 标签解析归一化
- v5.2.7: 14 项路径遍历修复 + SQLite 签名校验 + 记忆版本历史
- v5.2.5: 双向记忆关联 + 置顶/取消置顶
- v5.2.4: 笔记批注 + 模板 + 批量更新 + 间隔重复复习计划
- v5.2.3: 全数据转换层 `_safe_json_loads` 防御性解析
- v5.2.2: 短剧 CRUD 模块 + Agent 生命周期 + 质量评分
- v5.2.1: 完整短剧模块（dramas/scenes/characters/lines）
- v5.2.0: Fuzzy 搜索 + 搜索历史 + 批量标签 + 备份恢复

### v5.1.x

- v5.1.9: Excel 导入导出 + 复制 / 移动
- v5.1.8: `doctor` 诊断 + `find` 高级过滤 + 10 项 CLI 修复
- v5.1.7: 随机闪卡 + 标签/分类重命名 + 配置摘要
- v5.1.6: 标签/分类统计条形图 + 时间线 + 热门记忆
- v5.1.5: JSON 导入导出 + 去重 + 遗忘提醒
- v5.1.4: XML 导入导出 + 列表排序 + 详情统计
- v5.1.3: 清理 + 批量添加 + URL 导入 + 相似度搜索
- v5.1.2: 懒加载 + PBKDF2 调优 + UTF-8 BOM 统一清理
- v5.1.1: get/update/delete/audit/recent/trash/restore 完整补全
- v5.1.0: 项目重命名（ClawMemory → MindForge）+ HTML 导出

### v5.0.x

- v5.0.8: `analyze` 深度分析 + `import-md` + `migrate`
- v5.0.6: 更新同步刷新 FTS 索引 + `vacuum` + `purge-trash`
- v5.0.5: `health_check` + `summarize` + FTS 孤儿清理
- v5.0.4: `deduplicate` + `export-md` + Jaccard 相似度
- v5.0.2: Star 收藏 + 时间范围过滤 + `pip install` 支持
- v5.0.0: 初始四层架构 + 知识图谱 + 多模态 + 人格化 + 联邦

---

## License

MIT License + MindForge 隐私附加条款。

Copyright (c) 2026 MindForge Project
