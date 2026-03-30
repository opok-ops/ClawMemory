# ClawMemory 用户手册 v1.0.0

## 目录

1. 快速开始
2. CLI 命令详解
3. 隐私分级使用指南
4. OpenClaw 集成
5. Claude Code 集成
6. 分类与标签系统
7. 常见问题

---

## 1. 快速开始

### 1.1 安装

```bash
cd ClawMemory
```

### 1.2 初始化（首次必须执行）

```bash
python cli/main.py init
```

系统会要求设置加密密码。**请务必记住，丢失将无法恢复记忆。**

### 1.3 添加记忆

```bash
python cli/main.py add "今天开始使用 ClawMemory！" --category life --importance high
```

### 1.4 搜索记忆

```bash
python cli/main.py search "ClawMemory"
```

### 1.5 查看所有记忆

```bash
python cli/main.py list --limit 20
```

---

## 2. CLI 命令详解

| 命令 | 说明 |
|------|------|
| `init` | 初始化系统，生成加密密钥 |
| `add <内容>` | 添加记忆 |
| `search <查询>` | 搜索记忆 |
| `list` | 列出所有记忆 |
| `get <ID>` | 获取单条记忆 |
| `update <ID>` | 更新记忆 |
| `delete <ID>` | 删除记忆 |
| `stats` | 统计信息 |
| `audit` | 审计日志 |
| `backup` | 备份数据 |
| `export <文件>` | 导出记忆（自动脱敏） |
| `import <文件>` | 导入记忆 |
| `privacy-scan <文本>` | 隐私扫描 |
| `compliance` | 合规报告 |

### add 命令选项

```
-c, --category     分类（自动建议）
-t, --tags         标签（多个）
-p, --privacy      隐私等级：PUBLIC/INTERNAL/PRIVATE/STRICT
-i, --importance   重要性：LOW/MEDIUM/HIGH/CRITICAL
--auto-privacy     自动检测隐私等级
```

### search 命令选项

```
-l, --limit        最大结果数（默认10）
--category         限定分类
```

---

## 3. 隐私分级使用指南

### 四级隐私

**PUBLIC（公开）**
- 任何模块、任何Agent都可以访问
- 适用：公开信息、一般知识分享

**INTERNAL（内部）**
- 仅限同一Agent会话内访问
- 适用：工作记录、项目进展

**PRIVATE（私密）**
- 需要显式授权才能被其他Agent访问
- 适用：个人偏好、私人信息

**STRICT（严格隔离）**
- 物理隔离存储，需单独授权
- 适用：密码、证件号、财务信息

### 自动隐私检测

使用 `--auto-privacy` 标志，系统会自动识别敏感信息：

```
检测到手机号 -> 建议 PRIVATE
检测到密码/证件号 -> 建议 STRICT
```

---

## 4. OpenClaw 集成

在OpenClaw的Agent system prompt中添加：

```
你有一个外部记忆系统ClawMemory。

使用指南：
- 重要事实和决定 -> 使用 memory_add 保存
- 需要回忆过去信息 -> 使用 memory_search 搜索

隐私分级：
- PUBLIC: 可共享的信息
- INTERNAL: 仅供我使用（默认）
- PRIVATE: 敏感信息，需授权访问
- STRICT: 极高敏感度，物理隔离
```

可用工具：memory_search / memory_add / memory_get / memory_list / memory_update / memory_delete / memory_audit / memory_stats

---

## 5. Claude Code 集成

### MCP 服务器模式

```bash
python adapters/claude_code_adapter.py
```

### Claude Desktop 配置

在 claude_desktop_config.json 中添加：

```json
{
  "mcpServers": {
    "clawmemory": {
      "command": "python",
      "args": ["path/to/ClawMemory/adapters/claude_code_adapter.py"]
    }
  }
}
```

### 环境变量

```bash
export CLAWMEMORY_DB_PATH=~/.clawmemory/data/store/memory.db
export CLAWMEMORY_KEY_FILE=~/.clawmemory/data/.key
```

---

## 6. 分类与标签系统

### 内置分类

| 分类 | 图标 | 说明 |
|------|------|------|
| life | 住宅 | 生活日常 |
| work | 公文包 | 工作相关 |
| learning | 书本 | 学习和知识 |
| idea | 灯泡 | 创意想法 |
| fact | 笔记 | 事实记录 |
| emotion | 红心 | 情感感受 |
| general | 图钉 | 通用分类 |

### 自动标签

系统自动从内容中提取：
- @提及 -> 转换为标签
- #话题 -> 保留为标签
- 日期 -> date:YYYY-MM-DD 标签
- URL -> url:xxx 标签

---

## 7. 常见问题

**Q: 忘记了加密密码怎么办？**
无法恢复。密码是本地生成的，不存在恢复机制。建议在安全的地方备份密码提示。

**Q: 记忆数据存在哪里？**
所有数据存储在本地 data/ 目录。云端上传已在架构层面完全禁用。

**Q: 如何迁移到新电脑？**
1. 导出记忆：python cli/main.py export backup.json
2. 复制整个ClawMemory目录到新电脑
3. 重新初始化：python cli/main.py init（使用相同或新密码）
4. 导入：python cli/main.py import backup.json

**Q: 可以多设备同步吗？**
ClawMemory不提供云端同步。可使用加密云盘（Cryptomator）或Syncthing进行本地同步。

**Q: token消耗太高怎么办？**
使用ContextWindowOptimizer压缩记忆，自动分配token预算。
