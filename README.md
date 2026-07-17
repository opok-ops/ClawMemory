# ClawMemory v5.0

**AI Agent 终身记忆系统 — 四层记忆架构 · 知识图谱 · 多模态 · 人格化 · 联邦网络**

让 AI Agent 拥有真正的终身记忆与进化学习能力，终结会话失忆、token 爆炸、隐私混乱的行业痛点。

---

## ✨ v5.0 六大突破

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
│                    ClawMemory v5.0                        │
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

```bash
# 克隆仓库
git clone https://github.com/opok-ops/ClawMemory.git
cd ClawMemory

# 初始化（生成加密密钥）
python cli/main.py init
```

### CLI 使用

```bash
# 添加记忆
python cli/main.py add "ClawMemory v5.0 真的太强了！" --category tech --importance high

# 搜索记忆
python cli/main.py search "数据库优化"

# 查看统计
python cli/main.py stats

# 记忆巩固（短期→长期）
python cli/main.py consolidate

# 知识图谱统计
python cli/main.py graph stats

# 用户画像
python cli/main.py personality profile

# 启动 Web UI
python cli/main.py serve --port 8080
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
