# ClawMemory v1.2.0

**AI Agent 终身记忆系统 — 本地化·结构化·隐私优先**

> 让 AI Agent 拥有真正的终身记忆，终结会话失忆、token 爆炸、隐私混乱的行业痛点。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **无限全生命周期** | 跨越所有会话的记忆存储，无条目上限 |
| **多维度结构化管理** | 分类标签 + 重要性分级 + 时间线组织 |
| **100% 本地加密** | AES-256-GCM 本地加密，离线优先 |
| **10 万级检索 ≤200ms** | 语义向量索引 + SQLite FTS5 全文检索 |
| **按需轻量化加载** | 热/温/冷分层，只加载相关记忆碎片 |
| **隐私分级物理隔离** | PUBLIC/INTERNAL/PRIVATE/STRICT 四级隔离 |
| **Agent 自主精准调用** | RAG 召回引擎，Agent 自动获取相关记忆 |
| **模块化可扩展** | 核心模块化设计，支持插件扩展 |

## 架构概览

`
┌─────────────────────────────────────────────────────┐
│                    ClawMemory                        │
├─────────────────────────────────────────────────────┤
│  adapters/    OpenClaw · ClaudeCode · 通用API适配器  │
│  modules/     分类管理 · 召回引擎 · 整合器 · 隐私引擎 │
│  core/        存储引擎 · 索引引擎 · 加密引擎 · 查询引擎│
│  cli/         命令行工具 · Web UI (可选)             │
│  data/        store/ · index/ · backup/             │
└─────────────────────────────────────────────────────┘
`

## 快速开始

### 安装

`ash
# 克隆或解压到本地目录
cd ClawMemory

# 初始化（生成加密密钥，首次运行自动执行）
python cli/main.py init

# 添加第一条记忆
python cli/main.py add "今天开始使用 ClawMemory" --category life --importance high

# 搜索记忆
python cli/main.py search "ClawMemory"

# 查看所有记忆
python cli/main.py list --category life
`

### OpenClaw 集成

`ash
# 在 OpenClaw 中启用 ClawMemory
openclaw config set memory.adapter clawmemory
openclaw config set memory.encrypted true
`

### Claude Code 集成

`ash
# 设置环境变量
export CLAWMEMORY_DB_PATH=~/.clawmemory/data/store/memory.db
export CLAWMEMORY_KEY_FILE=~/.clawmemory/data/.key
`

## 隐私分级说明

| 级别 | 标签 | 说明 | 调用限制 |
|------|------|------|---------|
| 公开 | PUBLIC | 可被任何模块访问 | 无限制 |
| 内部 | INTERNAL | 仅 Agent 内部使用 | 同 Agent 会话 |
| 私密 | PRIVATE | 高度敏感数据 | 需显式授权 |
| 严格 | STRICT | 极高敏感度 | 物理隔离存储 |

## 性能指标

- **写入速度**：单条记忆 < 50ms（含加密+索引）
- **检索延迟**：10 万条目下 P95 ≤ 200ms
- **存储效率**：平均每条记忆 ~2KB（含元数据）
- **加密强度**：AES-256-GCM + PBKDF2 密钥派生
- **可用性**：99.99% 本地可用，零云端依赖

## 禁止事项

- 🚫 云端数据上传（已从架构层面禁用）
- 🚫 越权调取隐私分级记忆
- 🚫 未经授权修改/删除记忆
- 🚫 全量记忆投喂给 AI
- 🚫 纯对话日志无结构存储

## 许可证

MIT License + ClawMemory 自定义隐私附加条款
Copyright (c) 2026 ClawMemory Project