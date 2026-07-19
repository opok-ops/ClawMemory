# ClawMemory v5.0.5

**AI Agent 终身记忆系统 — 四层记忆架构 · 知识图谱 · 多模态 · 人格化 · 联邦网络**

让 AI Agent 拥有真正的终身记忆与进化学习能力，终结会话失忆、token 爆炸、隐私混乱的行业痛点。

---

## ✨ v5.0.5 六大突破

| 特性 | 说明 |
|------|------|
| **🧠 四层记忆架构** | 感官记忆 → 短期记忆 → 长期记忆 → 永久记忆，模拟人类认知的记忆形成与巩固过程，支持艾宾浩斯遗忘曲线 |
| **🕸️ 知识图谱引擎** | 自动提取实体与关系，构建动态知识网络，支持关联推理、路径查找和上下文联想 |
| **🖼️ 多模态记忆** | 支持文本、图像、音频、代码、结构化数据等多种记忆类型，统一向量空间下的跨模态检索 |
| **👤 人格化记忆** | 学习用户偏好、语言风格、思维模式，动态生成用户画像，让 Agent 越用越懂你 |
| **🤝 联邦记忆网络** | 多 Agent 间安全共享记忆，端侧联邦学习，数据不出本地即可实现群体智能 |
| **🛡️ 零知识隐私** | AES-256-GCM 端侧加密 + 四级隐私隔离 + 零知识证明验证，你的记忆永远只属于你 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    ClawMemory v5.0.5                        │
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
pip install clawmemory
```

**方式二：从源码安装**

```bash
# 克隆仓库
git clone https://github.com/opok-ops/ClawMemory.git
cd ClawMemory

# 本地安装
pip install -e .

# 初始化（生成加密密钥）
clawmemory init
```

> **注意**：如果 `pip install clawmemory` 提示找不到包，请升级 pip 后重试：
> ```bash
> python -m pip install --upgrade pip
> pip install clawmemory
> ```

### CLI 使用

```bash
# 添加记忆
clawmemory add "ClawMemory v5.0.5 真的太强了！" --category tech --importance high

# 搜索记忆
clawmemory search "数据库优化"

# 查看统计
clawmemory stats

# 记忆巩固（短期→长期）
clawmemory consolidate

# 知识图谱统计
clawmemory graph stats

# 用户画像
clawmemory personality profile

# 启动 Web UI
clawmemory serve --port 8080
```

### Python SDK

```python
from clawmemory import ClawMemory, PrivacyLevel, Importance, MemoryLayer

# 初始化记忆系统
memory = ClawMemory(
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
from clawmemory import KnowledgeGraph

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
from clawmemory import PersonalityEngine

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
from clawmemory import FederatedMemory

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
ClawMemory/
├── core/                    # 核心层
│   ├── __init__.py
│   ├── clawmemory.py       # 主入口类
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
  adapter: clawmemory
  adapter_config:
    db_path: ~/.clawmemory/data/store/memory.db
    key_file: ~/.clawmemory/data/.key
    encrypted: true
    auto_consolidate: true
```

### Claude Code 集成

```python
from clawmemory.adapters import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter.from_env()

# 记住用户偏好
adapter.remember("用户喜欢简洁的代码风格", ["preferences"])

# 获取相关上下文
context = adapter.get_context("数据库优化")
```

---

## 📝 更新日志

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
- 修复 `cli/__init__.py` 缺失导致 `pip install` 后 `clawmemory` 命令找不到的问题
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
- **setup.py**：支持 `pip install clawmemory` 安装
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

MIT License + ClawMemory 自定义隐私附加条款

Copyright (c) 2026 ClawMemory Project

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**Made with 🧠 for the future of AI memory.**
