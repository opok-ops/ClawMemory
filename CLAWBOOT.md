# CLAWBOOT.md — ClawMemory 系统初始化

## 欢迎使用 ClawMemory

你正在使用 ClawMemory —— AI Agent 终身记忆系统。
这是完全本地化的记忆基础设施，你的记忆永远属于你。

## 首次设置

系统已自动初始化：
- 存储目录：`data/store/`（加密记忆库）
- 索引目录：`data/index/`（语义检索索引）
- 备份目录：`data/backup/`（加密增量备份）

## 核心命令

```bash
# 查看帮助
python cli/main.py --help

# 添加记忆
python cli/main.py add "今天学会了用 ClawMemory" --category life

# 搜索记忆
python cli/main.py search "ClawMemory"

# 查看所有记忆
python cli/main.py list

# 导出记忆（加密）
python cli/main.py export --output memories.clawmem

# 隐私扫描
python cli/main.py audit --privacy
```

## 安全说明

- 所有记忆默认使用本地密钥加密（AES-256-GCM）
- 隐私分级：PUBLIC / INTERNAL / PRIVATE / STRICT
- 云端上传功能已被禁用
- 每次操作均有审计日志

## 架构概览

```
ClawMemory/
├── core/           # 核心引擎（存储/索引/加密/查询）
├── modules/        # 功能模块（分类/召回/整合/隐私）
├── adapters/       # Agent 适配器（OpenClaw/Claude Code）
├── cli/            # 命令行工具
├── docs/           # 文档（架构/用户手册/安全审计）
└── data/           # 加密数据存储
```

## 版本信息

当前版本：v1.0.0
发布日期：2026-03-29
许可证：MIT + 自定义隐私附加条款
