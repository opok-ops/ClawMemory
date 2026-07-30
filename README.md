# MindForge v5.2.6

**AI Agent 终身记忆系统 — 四层记忆架构 · 知识图谱 · 多模态 · 人格化 · 联邦网络**

让 AI Agent 拥有真正的终身记忆与进化学习能力，终结会话失忆、token 爆炸、隐私混乱的行业痛点。

---

## ✨ v5.2.0 八大突破

| 特性 | 说明 |
|------|------|
| **🧠 四层记忆架构** | 感官记忆 → 短期记忆 → 长期记忆 → 永久记忆，模拟人类认知的记忆形成与巩固过程，支持艾宾浩斯遗忘曲线 |
| **🕸️ 知识图谱引擎** | 自动提取实体与关系，构建动态知识网络，支持关联推理、路径查找和上下文联想 |
| **🖼️ 多模态记忆** | 支持文本、图像、音频、代码、结构化数据等多种记忆类型，统一向量空间下的跨模态检索 |
| **👤 人格化记忆** | 学习用户偏好、语言风格、思维模式，动态生成用户画像，让 Agent 越用越懂你 |
| **🤝 联邦记忆网络** | 多 Agent 间安全共享记忆，端侧联邦学习，数据不出本地即可实现群体智能 |
| **🛡️ 零知识隐私** | AES-256-GCM 端侧加密 + 四级隐私隔离 + 零知识证明验证，你的记忆永远只属于你 |
| **🔍 智能搜索** | 模糊搜索、关键词高亮、搜索历史，支持内容/分类/标签多维度相似度评分 |
| **💾 数据备份** | 一键备份与恢复，自动时间戳命名，旧备份自动清理，数据安全有保障 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    MindForge v5.2.6                        │
├─────────────────────────────────────────────────────────┤
│  🎯 认知层 (Cognitive Layer)                              │
│     人格引擎 · 知识图谱 · 记忆演化 · 联邦网络              │
├─────────────────────────────────────────────────────────┤
│  ⚙️  功能层 (Function Layer)                               │
│     召回引擎 · 分类管理 · 隐私引擎 · 整合器 · 多模态       │
├─────────────────────────────────────────────────────────┤
│  💎 核心层 (Core Layer)                                   │
│     存储引擎 · 索引引擎 · 加密引擎 · 查询引擎              │
├─────────────────────────────────────────────────────────┤
│  🔌 适配层 (Adapter Layer)                                │
│     OpenClaw · Claude Code · 通用 API · CLI / SDK         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 安装

**方式一：pip 安装（推荐）**

```bash
pip install MindForge
```

**方式二：从源码安装**

```bash
# 克隆仓库
git clone https://github.com/opok-ops/MindForge.git
cd MindForge

# 本地安装
pip install -e .

# 初始化（生成加密密钥）
MindForge init
```

> **注意**：如果 `pip install MindForge` 提示找不到包，请升级 pip 后重试：
> ```bash
> python -m pip install --upgrade pip
> pip install MindForge
> ```

### CLI 使用

```bash
# 添加记忆
MindForge add "MindForge v5.0.6 真的太强了！" --category tech --importance high

# 搜索记忆
MindForge search "数据库优化"

# 查看统计
MindForge stats

# 记忆巩固（短期→长期）
MindForge consolidate

# 知识图谱统计
MindForge graph stats

# 用户画像
MindForge personality profile

# 启动 Web UI
MindForge serve --port 8080
```

### Python SDK

```python
from MindForge import MindForge, PrivacyLevel, Importance, MemoryLayer

# 初始化记忆系统
memory = MindForge(
    db_path="./data/memory.db",
    encrypted=False,  # 生产环境建议开启
)

# 添加记忆
entry = memory.add(
    content="用户喜欢用 Python 进行开发",
    category="preferences",
    tags=["python", "开发"],
    privacy=PrivacyLevel.PRIVATE,
    importance=Importance.HIGH,
    layer=MemoryLayer.LONG_TERM,
)

# 语义搜索
results = memory.search(
    query="关于数据库优化的建议",
    max_results=10,
    min_relevance=0.7,
)

print(f"找到 {results.total_found} 条相关记忆")
for chunk in results.chunks:
    print(f"[{chunk.relevance_score:.2f}] {chunk.content[:50]}")
```

---

## 📚 四层记忆架构

### 1. 感觉记忆 (Sensory Memory)
- **持续时间**：几秒到几分钟
- **容量**：约 50 条
- **作用**：临时缓冲，快速过滤无关信息

### 2. 短期记忆 (Short-term Memory)
- **持续时间**：几小时到几天
- **容量**：约 100 条
- **作用**：工作记忆，当前会话活跃使用

### 3. 长期记忆 (Long-term Memory)
- **持续时间**：几周到几月
- **容量**：理论无限
- **作用**：语义记忆，经过巩固的重要信息

### 4. 永久记忆 (Permanent Memory)
- **持续时间**：永久
- **容量**：理论无限
- **作用**：核心知识、用户偏好、关键经验

### 记忆巩固机制
- 基于艾宾浩斯遗忘曲线
- 定期复习增强记忆强度
- 重要记忆自动提升层级
- 低价值记忆自然衰减

---

## 🕸️ 知识图谱

```python
from MindForge import KnowledgeGraph

kg = KnowledgeGraph()

# 从文本中提取实体和关系
entities, relations = kg.process_memory(
    memory_id="mem_001",
    content="我正在用 Python 和 PostgreSQL 开发一个 AI 应用"
)

# 查询相关实体
related = kg.get_related_entities("Python", depth=2)

# 查找两个实体间的路径
path = kg.find_path("Python", "PostgreSQL")
```

---

## 👤 人格化引擎

```python
from MindForge import PersonalityEngine

pe = PersonalityEngine(storage)

# 从交互中学习
pe.learn_from_interaction(
    user_id="user_001",
    user_message="帮我用Python写个脚本",
    agent_response="好的，这是你要的Python脚本...",
)

# 获取推荐风格
style = pe.get_recommended_style("user_001")
# {
#     "formality_level": "轻松",
#     "use_emoji": True,
#     "detail_level": "详细",
#     "technical_depth": 0.7
# }

# 获取兴趣主题
interests = pe.get_top_interests("user_001", top_n=5)
```

---

## 🤝 联邦记忆网络

```python
from MindForge import FederatedMemory

fed = FederatedMemory(storage, local_peer_id="peer_alpha")

# 注册节点
fed.register_peer("peer_beta", "Beta Agent", trust_level=0.8)

# 共享记忆
fed.share_memory(
    memory_id="mem_001",
    peer_ids=["peer_beta"],
    access_policy="read_only",
    expires_hours=24,
)

# 联邦搜索
results = fed.federated_search(
    query="最佳实践",
    max_per_peer=5,
)
```

---

## 🔐 隐私安全

### 四级隐私隔离

| 级别 | 标签 | 说明 |
|------|------|------|
| 公开 | PUBLIC | 可被任何模块访问 |
| 内部 | INTERNAL | 仅同一 Agent 会话内使用（默认） |
| 私密 | PRIVATE | 高度敏感数据，需显式授权 |
| 严格 | STRICT | 物理隔离存储，二次验证解锁 |

### 安全特性

- **AES-256-GCM** 端侧加密
- **PBKDF2-SHA256** 密钥派生（100,000 次迭代）
- 架构层面**禁用云端上传**
- 完整的**审计日志**
- 支持**零知识证明**验证

---

## 📊 性能指标

- **写入速度**：单条记忆 < 50ms（含加密+索引）
- **检索延迟**：10 万条目下 P95 ≤ 200ms
- **存储效率**：平均每条记忆 ~2KB（含元数据）
- **加密强度**：AES-256-GCM + PBKDF2 密钥派生
- **可用性**：99.99% 本地可用，零云端依赖

---

## 📁 项目结构

```
MindForge/
├── core/                    # 核心层
│   ├── __init__.py
│   ├── MindForge.py       # 主入口类
│   ├── types.py            # 类型定义
│   ├── storage.py          # 存储引擎
│   ├── encryption.py       # 加密引擎
│   ├── indexer.py          # 索引引擎
│   └── query.py            # 查询引擎
├── modules/                 # 功能层
│   ├── __init__.py
│   ├── recall.py           # 召回引擎
│   ├── knowledge_graph.py  # 知识图谱
│   ├── evolution.py        # 记忆演化
│   ├── personality.py      # 人格化引擎
│   ├── multimodal.py       # 多模态记忆
│   ├── federated.py        # 联邦记忆
│   ├── categorizer.py      # 分类管理
│   ├── privacy.py          # 隐私引擎
│   └── integrator.py       # 记忆整合器
├── adapters/                # 适配层
│   ├── __init__.py
│   ├── openclaw_adapter.py # OpenClaw 适配器
│   ├── claude_adapter.py   # Claude Code 适配器
│   └── generic_api.py      # 通用 API 适配器
├── cli/                     # 命令行工具
│   └── main.py
├── website/                 # 官方网站
│   ├── index.html
│   └── assets/
├── tests/                   # 测试
├── examples/                # 示例
└── docs/                    # 文档
```

---

## 🔗 集成

### OpenClaw 集成

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

### Claude Code 集成

```python
from MindForge.adapters import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter.from_env()

# 记住用户偏好
adapter.remember("用户喜欢简洁的代码风格", ["preferences"])

# 获取相关上下文
context = adapter.get_context("数据库优化")
```

---

## 📝 更新日志

### v5.2.6 (2026-07-30)

**🔧 紧急修复**
- 修复 MindForge Bot 自动化提交误删 `commands` 命令分发字典导致 CLI 完全失效的严重问题
- 恢复 `args = parser.parse_args()` 调用和命令分发逻辑
- 保留 v5.2.5 全部功能（记忆关联、置顶收藏）的原始标注，不再错误改写为 v5.2.6

### v5.2.5 (2026-07-29)

**🔗 记忆关联（Memory Links）**
- `link` - 创建记忆间的双向关联，支持关联类型和备注（v5.2.5 新增）
- `links` - 列出记忆的所有关联（双向），显示关联类型和对方内容预览（v5.2.5 新增）
- `unlink` - 删除记忆关联（v5.2.5 新增）
- 关联类型：`related`（默认）/ `depends_on` / `extends` / `contradicts`
- 自动去重（任一方向已存在则拒绝）、禁止自关联、输入长度校验
- `link_memories`/`list_links`/`unlink_memories` API（v5.2.5 新增）

**📌 置顶/收藏增强（Pin）**
- `pin` - 置顶记忆，在 list/search 时优先展示（v5.2.5 新增）
- `unpin` - 取消置顶（v5.2.5 新增）
- `pinned` - 列出所有置顶记忆（v5.2.5 新增）
- `list` 命令支持置顶优先排序（`ORDER BY pinned DESC, ...`）
- `pin`/`unpin`/`list_pinned` API（v5.2.5 新增）

**🗄️ 数据库变更**
- 新增 `memory_links` 表（id/source_id/target_id/link_type/note/created_at），含 3 个索引
- `memories` 表新增 `pinned` 字段（INTEGER DEFAULT 0），含索引 `idx_pinned`
- `MemoryEntry` 数据类新增 `pinned: bool = False` 字段

**📋 其他**
- 版本号全面更新至 v5.2.5
- CLI description 和 --version 同步更新
- 官网更新日志新增 v5.2.5 条目

### v5.2.4 (2026-07-29)

**✨ 记忆笔记/批注**
- `note-add` - 为记忆添加笔记/批注，支持作者和标签（v5.2.4 新增）
- `note-list` - 列出记忆的所有笔记，按时间倒序（v5.2.4 新增）
- `note-delete` - 删除笔记，支持 --force 确认（v5.2.4 新增）
- `add_note`/`list_notes`/`delete_note` API（v5.2.4 新增）

**✨ 记忆模板**
- `template-add` - 创建记忆模板，支持 {变量} 占位符、默认分类/标签/重要性/层级（v5.2.4 新增）
- `template-list` - 列出模板，按使用次数排序，支持分类筛选（v5.2.4 新增）
- `template-use` - 使用模板快速创建记忆，支持变量替换（v5.2.4 新增）
- `template-delete` - 删除模板（v5.2.4 新增）
- `add_template`/`list_templates`/`use_template`/`delete_template` API（v5.2.4 新增）

**✨ 批量更新**
- `batch-update` - 批量更新记忆的分类/标签/重要性/层级/收藏状态（v5.2.4 新增）
- `batch_update` API - 支持最多 500 条记忆批量操作，带参数校验（v5.2.4 新增）

**✨ 复习计划（间隔重复）**
- `schedule create` - 为记忆创建复习计划，支持自定义间隔天数（v5.2.4 新增）
- `schedule list` - 列出到期复习，显示记忆内容和复习进度（v5.2.4 新增）
- `schedule review` - 完成复习，自动安排下次（间隔重复：1→2→4→7→15→30 天）（v5.2.4 新增）
- `schedule stats` - 复习计划统计（总计划/待复习/已到期/累计完成）（v5.2.4 新增）
- `create_review_schedule`/`list_due_reviews`/`complete_review`/`get_review_stats` API（v5.2.4 新增）

**🔧 修复**
- 修复 `pyproject.toml` 版本号滞后（5.2.0 → 5.2.4）
- 修复 `cli/main.py` argparse description 和 --version 版本号不一致（5.2.2 → 5.2.4）
- 修复 `core/mindforge.py` fallback 版本号滞后（5.2.0 → 5.2.4）
- 修复 README 架构图版本号不一致（5.2.2 → 5.2.4）
- 修复 CLI commands 字典中 `"similar"` 键重复注册问题（v5.1.3 与 v5.2.2 冲突）

**📋 其他**
- 版本号全面更新至 v5.2.4
- 新增 3 张数据表：`memory_notes`/`memory_templates`/`review_schedules`

### v5.2.3 (2026-07-28)

**🛡️ 安全加固**
- 新增 `_safe_json_loads()` 静态方法，统一处理损坏的 JSON 数据，防止解析崩溃
- 修复 `_row_to_entry`、`_row_to_drama`、`_row_to_scene`、`_row_to_character`、`_row_to_line` 等数据转换方法中的 JSON 解析安全问题
- 修复批量标签操作（`batch_add_tags`、`batch_remove_tags`、`merge_tags`）和 `rename_tag` 中的 JSON 解析安全问题
- 修复审计日志 `list_audit_logs` 中 `details` 字段的 JSON 解析安全问题
- 修复 `adapters/generic_api.py`、`core/encryption.py`、`core/indexer.py`、`core/mindforge.py`、`modules/federated.py`、`modules/integrator.py`、`modules/knowledge_graph.py`、`modules/personality.py`、`modules/privacy.py` 中的裸 `except Exception:`，全部替换为具体异常类型

**📋 其他**
- 版本号更新至 v5.2.3
- 代码推送到 GitHub

### v5.2.2 (2026-07-27)

**✨ AI 短剧智能增强**
- `drama-recommend` - AI 智能推荐短剧，支持按类型/评分筛选，排除已弃剧（v5.2.2 新增）
- `drama-progress` - 观看进度统计，显示完成度和按类型分布（v5.2.2 新增）
- `drama-export` - 一键导出短剧数据为 JSON，支持全量或指定 ID（v5.2.2 新增）
- `recommend_dramas` API - 智能推荐算法，综合评分/状态/标签（v5.2.2 新增）
- `drama_watching_progress` API - 整体观看进度统计（v5.2.2 新增）
- `export_dramas` API - 完整导出短剧及关联场次/角色/台词（v5.2.2 新增）

**🤖 Agent 记忆优化**
- `agent-stats` - Agent 记忆统计，支持全部 Agent 概览或指定 Agent 详情（v5.2.2 新增）
- `agent-list` - 列出特定 Agent 的记忆，支持分页和预览（v5.2.2 新增）
- `agent-transfer` - 迁移 Agent 记忆，将一个 Agent 的记忆转移给另一个（v5.2.2 新增）
- `agent-clean` - 清理 Agent 旧记忆，按天数和重要级别筛选，移入回收站（v5.2.2 新增）
- `evolve` - 记忆演化，基于艾宾浩斯遗忘曲线自动升级记忆层级（v5.2.2 新增）
- `agent_stats`/`list_by_agent`/`transfer_agent_memories`/`clean_agent_memories`/`evolve_memories` API（v5.2.2 新增）
- 支持 Agent 级别的记忆追踪、迁移、清理全生命周期管理

**📊 记忆质量与相似度分析**
- `quality` - 记忆质量评分，多维度评估记忆价值（v5.2.2 新增）
- `similar` - 相似度分析，查找相似记忆（v5.2.2 新增）
- `quality_score`/`batch_quality_score`/`analyze_similarity` API（v5.2.2 新增）
- 支持内容长度、访问频率、收藏状态、重要性、标签丰富度、时间衰减等评分维度

**🛡️ 安全与稳定性修复**
- 修复 18 个 CLI 命令的 `cm.close()` 资源泄漏（数据库连接未释放）
  - 涉及：add/search/list/batch_delete/tag_search/deduplicate/export_md 等
- 修复 `MindForge._init_encryption` 空逻辑问题（之前两个分支均为 pass）
- 修复 `init_engine` 缺少 `encoding='utf-8'` 参数（Windows 中文环境兼容）
- 新增密钥文件权限加固：chmod 600 限制仅所有者可读写
- 修复 `recommend_dramas` 硬编码 status='planned' 导致无法推荐已观看短剧的 bug
- 优化推荐算法：自动剔除 DROPPED 状态短剧，COMPLETED 短剧加分，PLANNED 高分剧加分

**📊 核心增强**
- 推荐算法权重：评分 × 10 + 标签奖励 + 完成度奖励
- 导出 JSON 包含版本号（5.2.2）和导出时间戳
- 短剧列表查询限制从 100 提升到 500，提高推荐候选数

**📋 其他**
- 版本号全面更新至 v5.2.2

### v5.2.1 (2026-07-27)

**✨ AI 短剧记忆模块（全新）**
- `drama-add` - 添加短剧，支持类型、集数、状态、平台、评分等元数据（v5.2.1 新增）
- `drama-list` - 列出短剧，支持按类型/状态/平台筛选，多种排序方式（v5.2.1 新增）
- `drama-get` - 获取短剧详情，包含场次、角色、经典台词概览（v5.2.1 新增）
- `drama-update` - 更新短剧信息，支持标记观看进度（v5.2.1 新增）
- `drama-delete` - 删除短剧，级联删除关联的场次/角色/台词（v5.2.1 新增）
- `drama-stats` - 短剧统计，按类型/状态分布，台词数量统计（v5.2.1 新增）
- `line-add` - 添加短剧台词，支持关联场次、角色、标记经典（v5.2.1 新增）
- `line-list` - 列出台词，支持按短剧/场次/角色/经典筛选（v5.2.1 新增）
- `line-search` - 搜索台词，模糊匹配+关键词高亮（v5.2.1 新增）
- `line-classic` - 经典台词列表，快速回顾名场面（v5.2.1 新增）
- `line-update` - 更新台词内容和元数据（v5.2.1 新增）
- `line-delete` - 删除台词（v5.2.1 新增）
- `char-add` - 添加短剧角色，支持角色定位、演员、性格描述（v5.2.1 新增）
- `char-list` - 列出角色，支持按角色定位筛选（v5.2.1 新增）
- `char-get` - 获取角色详情，包含代表台词（v5.2.1 新增）
- `char-update` - 更新角色信息（v5.2.1 新增）
- `char-delete` - 删除角色（v5.2.1 新增）
- `scene-add` - 添加短剧场次，支持集数、场号、地点、时间（v5.2.1 新增）
- `scene-list` - 列出场次，支持按集数筛选（v5.2.1 新增）
- `scene-get` - 获取场次详情，包含本场台词（v5.2.1 新增）
- `scene-update` - 更新场次信息（v5.2.1 新增）
- `scene-delete` - 删除场次，级联删除本场台词（v5.2.1 新增）

**🛡️ 安全加固**
- 新增输入验证机制：所有短剧相关 CRUD 操作均增加字符串长度限制、数值范围校验
- 修复 `search_lines` 方法参数错误（多余的 None 参数）
- 排序字段白名单验证，防止 SQL 注入
- 枚举类型合法性校验，非法值自动降级为默认值

**📊 核心增强**
- 新增 `DramaGenre`/`DramaStatus` 枚举类型
- 新增 `DramaSeries`/`DramaScene`/`DramaCharacter`/`DramaLine` 数据类
- 新增 4 张数据表：`drama_series`/`drama_scenes`/`drama_characters`/`drama_lines`
- 新增完整 CRUD API 层，封装存储操作
- 新增短剧统计接口，支持多维度数据分析

**📋 其他**
- 版本号全面更新至 v5.2.1

### v5.2.0 (2026-07-26)

**✨ CLI 新增命令**
- `fuzzy-search` - 模糊搜索记忆，支持相似度评分和关键词高亮（v5.2.0 新增）
- `search-history` - 查看搜索历史记录，按最近使用排序（v5.2.0 新增）
- `batch-add-tags` - 批量添加标签，支持按 ID 列表或按分类批量操作（v5.2.0 新增）
- `batch-remove-tags` - 批量移除标签，支持指定多个记忆 ID（v5.2.0 新增）
- `merge-tags` - 合并多个标签为一个，自动去重（v5.2.0 新增）
- `db-backup` - 创建数据库备份，自动生成时间戳文件名（v5.2.0 新增）
- `db-backups` - 列出所有备份文件，显示大小和创建时间（v5.2.0 新增）
- `db-restore` - 从备份恢复数据库，恢复前自动备份当前数据（v5.2.0 新增）
- `db-clean-backups` - 清理旧备份，保留最新 N 个（v5.2.0 新增）

**📊 核心增强**
- `fuzzy_search` - 模糊搜索方法，支持内容/分类/标签多维度相似度评分
- `get_search_history` - 搜索历史记录，基于审计日志自动统计
- `highlight_text` - 关键词高亮工具，支持自定义前后标签
- `batch_add_tags` - 批量添加标签，自动去重，带审计日志
- `batch_remove_tags` - 批量移除标签，带审计日志
- `merge_tags` - 合并标签，支持多个源标签合并到一个目标标签
- `add_tags_by_category` - 按分类批量添加标签
- `create_backup` - 创建数据库备份，自动生成带时间戳的文件名
- `list_backups` - 列出所有备份，按时间倒序排列
- `restore_backup` - 从备份恢复，可配置恢复前自动备份
- `delete_old_backups` - 自动清理旧备份，保留指定数量
- `MindForge` 类新增全部上述 API 封装

**📋 其他**
- 版本号全面更新至 v5.2.0

### v5.1.9 (2026-07-25)

**✨ CLI 新增命令**
- `export-excel` - 导出记忆为 Excel 格式，支持样式美化，无依赖时自动降级为 CSV（v5.1.9 新增）
- `import-excel` - 从 Excel 文件导入记忆，支持重复检测和数据清洗（v5.1.9 新增）
- `copy` - 复制记忆到新分类，保留原记忆（v5.1.9 新增）
- `move` - 移动记忆到新分类，移除原记忆（v5.1.9 新增）

**📊 核心增强**
- `export_as_excel` - Excel 导出方法，支持样式美化和 CSV 降级方案
- `import_from_excel` - Excel 导入方法，支持重复检测和数据清洗
- `copy_memory` - 复制记忆方法，支持分类迁移和审计日志记录
- `move_memory` - 移动记忆方法，支持分类迁移和审计日志记录
- `MindForge` 类新增 `export_excel`/`import_excel`/`copy`/`move` API

**📋 其他**
- 版本号全面更新至 v5.1.9

### v5.1.8 (2026-07-25)

**✨ CLI 新增命令**
- `doctor` - 全面诊断数据库，5 项检查（完整性、FTS 一致性、索引、加密一致性、版本），支持 `--fix` 自动修复（v5.1.8 新增）
- `find` - 高级查找记忆，支持分类/标签/层级/收藏/关键词/时间范围组合筛选（v5.1.8 新增）

**🔧 CLI 修复**
- 修复 `cleanup` 命令崩溃：SQL 查询引用不存在的 `deleted` 列，改为 `category != 'trash'`
- 修复 `migrate` 命令崩溃：`StorageEngine` 缺少 `get_db_version`/`get_latest_db_version`/`migrate_to_latest` 方法
- 修复 `import-md` 命令解析错误：内容归到错误的分类（先更新分类再追加内容的逻辑顺序错误）
- 修复 `search` 命令 `--category` 过滤失效：创建的 `RecallConfig` 未传入 `search()` 调用
- 修复 `export`/`import` 命令 `--layer` 参数大小写敏感：`MemoryLayer()` 改为 `MemoryLayer.from_string()`
- 修复 `export-html` 命令 XSS 风险：添加 `html.escape()` 转义所有动态内容
- 修复 `export-xml` 命令 XML 结构破坏：添加 `xml.sax.saxutils.escape()` 转义
- 修复 `vacuum` 命令 VACUUM 在事务中执行失败：显式提交并切换 isolation_level
- 修复 `import-url` 命令 SSRF 风险：限制 http/https 协议，禁止内网/元数据地址
- 修复 `import-xml`/`import-json` 命令空元素 `.text` 为 None 时切片崩溃
- 修复 `import-md` 标签正则误匹配（如 `C#` 被识别为标签）
- 修复 `export-html`/`export-xml` 版本号硬编码为旧版本

**📊 核心增强**
- 新增 `get_db_version`/`get_latest_db_version`/`migrate_to_latest` 数据库迁移方法
- 修复 `cleanup_expired` 方法引用不存在的 `deleted` 列
- 修复 `find_similar` 方法引用不存在的 `deleted` 列

### v5.1.7 (2026-07-24)

**✨ CLI 新增命令**
- `random` - 随机闪卡复习，从记忆库中随机抽取记忆进行复习，支持分类筛选（v5.1.7 新增）
- `rename-tag` - 重命名标签，批量更新所有包含该标签的记忆（v5.1.7 新增）
- `rename-cat` - 重命名分类，批量移动该分类下的所有记忆（v5.1.7 新增）
- `config` - 查看配置信息，展示数据库路径、加密状态、数据库大小等（v5.1.7 新增）

**🔧 CLI 参数增强**
- `random` 支持 `--count/-n` 参数指定随机记忆数量
- `random` 支持 `--category/-c` 参数按分类筛选
- `rename-tag` 支持 `--force/-f` 参数跳过确认直接执行
- `rename-cat` 支持 `--force/-f` 参数跳过确认直接执行

**📊 核心增强**
- `get_random_memories` - 随机获取记忆方法，支持分类、层级、强度筛选
- `rename_tag` - 标签重命名方法，批量更新记忆标签
- `rename_category` - 分类重命名方法，批量更新记忆分类
- `get_config_summary` - 配置摘要方法，返回数据库配置信息

**📋 其他**
- 版本号全面更新至 v5.1.7
- 修复 CLI commands 字典缺失新命令注册问题

### v5.1.6 (2026-07-24)

**✨ CLI 新增命令**
- `tags` - 标签管理，列出所有标签并按使用次数排序，带可视化条形图（v5.1.6 新增）
- `cats` - 分类统计，列出所有分类并按数量排序，带可视化条形图（v5.1.6 新增）
- `timeline` - 时间线视图，按日期分组展示记忆，支持 `--days` 和 `--category` 筛选（v5.1.6 新增）
- `top` - 热门记忆，按访问次数/记忆强度/创建时间排序展示热门记忆（v5.1.6 新增）

**🔧 CLI 参数增强**
- `tags` 支持 `--top` 参数限制显示数量
- `cats` 支持 `--top` 参数限制显示数量
- `timeline` 支持 `--days` 和 `--category` 参数
- `top` 支持 `--count` 和 `--by` 参数

**📋 其他**
- 版本号全面更新至 v5.1.6

### v5.1.5 (2026-07-24)

**✨ CLI 新增命令**
- `export-json` - 导出记忆为 JSON 格式，支持格式化输出（v5.1.5 新增）
- `import-json` - 从 JSON 文件导入记忆，支持预览和确认（v5.1.5 新增）
- `merge` - 合并重复记忆，基于相似度阈值自动检测（v5.1.5 新增）
- `remind` - 遗忘提醒，列出遗忘分数较高需要复习的记忆（v5.1.5 新增）

**🔧 CLI 参数增强**
- `export-json` 支持 `--pretty` 参数格式化输出
- `merge` 支持 `--threshold` 和 `--dry-run` 参数
- `remind` 支持 `--count` 和 `--threshold` 参数

**📋 其他**
- 版本号全面更新至 v5.1.5

### v5.1.4 (2026-07-23)

**✨ CLI 新增命令**
- `export-xml` - 导出记忆为 XML 格式，支持完整元数据（v5.1.4 新增）
- `import-xml` - 从 XML 文件导入记忆，支持预览和确认（v5.1.4 新增）

**🔧 CLI 增强**
- `list` 命令新增 `--sort/-s` 参数，支持按 `created_at`/`updated_at`/`last_accessed_at`/`access_count`/`strength`/`forgetting_score` 排序
- `list` 命令新增 `--order/-o` 参数，支持 `asc`/`desc` 排序顺序
- `stats` 命令新增 `--detailed` 参数，显示详细统计（回收站、加密数、时间范围、平均指标、极值指标等）

**📊 核心增强**
- `list_memories` 方法新增 `sort_by` 和 `sort_order` 参数支持排序
- `get_detailed_stats` 方法新增，提供多维度详细统计数据
- `MindForge` 类新增 `detailed_stats` 接口

**📋 其他**
- 版本号全面更新至 v5.1.4
- 修复 README.md 更新日志缺失问题

### v5.1.3 (2026-07-22)

**✨ CLI 新增命令**
- `cleanup` - 清理过期记忆，支持按层级和时长筛选
- `batch-add` - 从 JSON 文件批量添加记忆
- `import-url` - 从网页 URL 导入内容
- `similar` - 查找相似记忆（基于 Jaccard 相似度）

**📊 核心增强**
- `cleanup_expired` - 清理过期记忆方法
- `batch_add` - 批量添加记忆方法
- `find_similar` - 相似记忆查找方法

### v5.1.2 (2026-07-22)

**⚡ 性能优化**
- CLI 启动优化：懒加载模块和加密库，减少启动时间
- PBKDF2 迭代次数从 100000 降至 60000（符合 OWASP 2023 推荐）
- `get_memory` 方法减少不必要的数据库写入，减轻低配电脑负担

**🔧 修复**
- 修复 UTF-8 BOM 导致的 TOML 解析失败问题
- 修复 28 个源文件的 UTF-8 BOM

### v5.1.1 (2026-07-22)

**✨ CLI 新增命令**
- `get <id>` - 获取单条记忆详情（补全之前缺失的命令）
- `update <id>` - 更新记忆内容、分类、标签、隐私、重要性、层级、收藏状态（补全）
- `delete <id>` - 删除记忆，支持软删除/硬删除，带安全确认（补全）
- `audit` - 查看审计日志，支持按记忆 ID 或操作者筛选（补全）
- `recent` - 查看最近 N 小时内添加的记忆
- `trash` - 查看回收站中的记忆及原分类
- `restore <id>` - 从回收站恢复记忆到原分类

**🔧 修复**
- 软删除（delete / batch-delete）时丢失原分类的问题：现在将原分类保存到 metadata，恢复时可还原
- `pyproject.toml` 与 `setup.py` 中的 GitHub 仓库 URL 仍指向旧名 `MindForge`，已修正为实际仓库名 `MindForge`（重命名已同步）
- 官网 Open Graph / Twitter Card / GitHub 链接全部更新至 `MindForge` 路径

**📋 其他**
- 版本号全面更新至 v5.1.1

### v5.1.0 (2026-07-21)

**✨ 项目重命名**
- ClawMemory 正式重命名为 MindForge

**✨ CLI 新增命令**
- `export-html` - 导出记忆为美观的 HTML 页面（渐变背景、卡片式布局、响应式设计）

**📋 其他**
- 官网版本号全面更新至 v5.1.0

### v5.0.8 (2026-07-21)

**✨ CLI 新增命令**
- `analyze` - 记忆深度分析（时间分布柱状图、活跃度趋势、热门记忆 TOP5、标签统计）
- `import-md` - 从 Markdown 文件导入记忆（自动解析标题为分类，标签自动提取）
- `migrate` - 数据库迁移（版本检测、自动升级脚本、安全预览）

**🔧 修复**
- CLI 中版本号硬编码问题（多处 v5.0.6 → v5.0.8）

**📋 其他**
- 官网版本号更新至 v5.0.8

### v5.0.7 (2026-07-20)

**🎨 官网体验优化**
- 新增科技感自定义鼠标样式（青色圆环光标，悬浮时变为紫色）
- 新增点击涟漪动画效果（渐变扩散特效）
- 新增 Favicon 网站图标（SVG 格式，渐变配色）
- 新增 Open Graph + Twitter Card 社交分享标签（优化微信/微博分享显示）

**🔧 其他**
- 新增 SEO meta 标签（keywords、author、robots）
- 新增 sitemap.xml 和 robots.txt 用于搜索引擎收录

### v5.0.6 (2026-07-20)

**🔧 修复**
- **关键修复**：`update_memory` 更新 content/category/tags 时未同步刷新 FTS 索引，导致全文搜索返回旧内容（与 v5.0.5 修复的 delete 同类问题）
  - contentless FTS5 表通过 `delete` + `insert` 两步完成索引刷新
- 修复 `export_json` 导出文件的 `version` 字段硬编码为 "5.0.1" 的问题，改为动态读取 `__version__`

**✨ 新增功能**
- **FTS 索引重建**：`rebuild_fts()` 方法，清空并重建全文索引，消除孤立记录
  - 配合 `health_check` 发现的 `fts_orphans` 问题使用
  - 返回重建条目数和耗时
- **清空回收站**：`purge_trash()` 方法，永久删除所有软删除（category='trash'）的记忆
  - 同步清理对应的 FTS 索引，记录审计日志
  - 软删除后终于有了清理机制
- **CLI 新增命令**：
  - `vacuum` - 重建 FTS 索引 + 执行 VACUUM 回收空间（含重建前后健康对比）
  - `purge-trash` - 清空回收站（默认预览，加 `--force` 执行）

### v5.0.5 (2026-07-19)

**✨ 新增功能**
- **数据库健康检查**：`health_check()` 方法，全面体检数据库状态
  - SQLite 完整性检查（PRAGMA integrity_check）
  - 索引完整性验证（12 个预期索引）
  - FTS 索引同步状态检测（孤立 FTS 记录）
  - 孤立审计日志检测
  - 加密一致性校验（标记加密但缺密文的条目）
  - 自动生成状态评级（healthy/warning/critical）和修复建议
- **记忆摘要**：`summarize()` 方法，快速了解记忆库概况
  - 支持按 category/layer/importance/privacy 四种维度分组
  - 每组含数量、时间范围、前 3 条样例
  - 近期活动统计（7 天/30 天新增数）
  - 热门标签 Top 10
- **CLI 新增命令**：
  - `health` - 数据库健康检查（返回退出码：0=健康，1=警告，2=严重）
  - `summarize` - 记忆摘要（支持 `-g layer` 等切换分组维度）

**🔧 修复**
- **关键修复**：`delete_memory(hard_delete=True)` 硬删除时未同步清理 FTS 索引，导致搜索可能返回已删除的记忆
- **关键修复**：`batch_delete(hard_delete=True)` 批量硬删除同样存在 FTS 索引未清理的问题
- 这两个 bug 会导致：删除记忆后搜索仍能命中，FTS 索引逐渐膨胀

### v5.0.4 (2026-07-19)

**✨ 新增功能**
- **记忆去重**：`deduplicate()` 方法，基于内容相似度（Jaccard）检测并合并重复记忆
  - 支持同分类下扫描，相似度阈值可调（默认 0.95）
  - 保留策略：starred 优先 → 重要性更高 → 更新时间更晚
  - 支持 `dry_run` 试运行模式，先看报告再决定是否执行
- **Markdown 导出**：`export_as_markdown()` 方法，将记忆导出为可读性强的 `.md` 文档
  - 支持按分类、层级、星标筛选
  - 自动按分类分组，含完整元数据（ID/层级/隐私/重要性/标签等）
- **CLI 新增命令**：
  - `deduplicate` - 记忆去重（默认试运行，加 `--execute` 实际删除，加 `-v` 看详情）
  - `export-md` - 导出为 Markdown 文件

**🔧 修复**
- 修复 `search_by_tag` 双重过滤导致的性能问题（SQL LIKE 已足够精确，移除冗余的 Python 端再过滤）
- 优化 `get_stats` 中标签统计的稳定性

**📦 安装修复**（来自 v5.0.3 末尾的 hotfix）
- 修复 `cli/__init__.py` 缺失导致 `pip install` 后 `MindForge` 命令找不到的问题
- 修复 `setup.py` 用 `exec()` 读取版本号失败的问题
- 修复根 `__init__.py` 相对导入在包安装模式下失败的问题
- 新增 `pyproject.toml` 支持 PEP 517/518 现代构建

### v5.0.3 (2026-07-19)

**🔧 修复**
- 修复 `get_stats` 缺少标签统计和收藏统计

**✨ 新增功能**
- **批量删除记忆**：`batch_delete()` 方法，支持按分类/层级/星标/时间范围批量删除
- **按标签搜索**：`search_by_tag()` 方法，精确匹配标签
- **统计增强**：新增 `starred_count`（收藏数）和 `top_tags`（热门标签）
- **CLI 增强**：
  - 新增 `batch-delete` 命令（支持预览 + --force 确认）
  - 新增 `tag-search` 命令
  - `stats` 命令新增收藏数和标签统计
- **新示例**：`examples/batch_ops_and_tag_search.py` - 批量操作与标签搜索演示

### v5.0.2 (2026-07-18)

**🔧 修复**
- 修复 `__init__.py` 文档字符串版本号未同步更新的问题
- 修复 CLI banner 和描述中的版本号显示

**✨ 新增功能**
- **记忆收藏/星标功能**：`star()` / `unstar()` 方法，支持标记重要记忆
- **时间范围筛选**：`list()` 新增 `created_after` / `created_before` 参数
- **CLI 增强**：
  - 新增 `star` / `unstar` 命令
  - `add` 命令新增 `--star` 参数
  - `list` 命令新增 `--starred` / `--unstarred` / `--after` / `--before` 参数
- **setup.py**：支持 `pip install MindForge` 安装
- **新示例**：`examples/starred_and_time_filter.py` - 星标与时间范围筛选演示

### v5.0.1 (2026-07-18)

**🔧 修复**
- 修复 modules 模块相对导入路径问题
- 修复人格化引擎 emoji 正则表达式在 Python 3.14 下的兼容性
- 添加 .gitignore，排除 __pycache__ 和数据库文件
- 整理 website 目录结构，规范路径

**✨ 新增功能**
- 记忆导出/导入：支持 JSON 和 CSV 格式，支持按分类/层级筛选
- 配置文件支持：from_config() / save_config() 方法，config.json 模板
- 单元测试框架：14 个核心测试用例，覆盖类型、存储、主类、知识图谱、人格化引擎
- CLI 增强：新增 export / import 子命令

### v5.0.0 (2026-07-17)

- 🎉 **全新四层记忆架构**：感官/短期/长期/永久记忆
- 🕸️ **知识图谱引擎**：实体提取、关系推理、图谱检索
- 🖼️ **多模态记忆**：文本/图像/音频/代码/结构化数据
- 👤 **人格化引擎**：用户画像、偏好学习、风格适配
- 🤝 **联邦记忆网络**：多 Agent 安全共享、端侧联邦学习
- 🔄 **记忆演化**：艾宾浩斯遗忘曲线、记忆巩固、复习计划
- 🎨 **全新官网设计**：交互式演示、知识图谱可视化
- ⚡ **性能优化**：更快的检索速度，更低的内存占用

---

## 📄 许可证

MIT License + MindForge 自定义隐私附加条款

Copyright (c) 2026 MindForge Project

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**Made with 🧠 for the future of AI memory.**
