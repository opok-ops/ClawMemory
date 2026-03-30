# ClawMemory 系统架构文档 v1.0.0

**AI Agent 终身记忆系统 - 架构规格说明**

---

## 1. 系统概述

ClawMemory 是专为 AI Agent 设计的本地化终身记忆基础设施。

| 痛点 | ClawMemory 解决方案 |
|------|-------------------|
| AI 会话失忆 | 跨会话持久化存储，无限生命周期 |
| token 成本爆炸 | 按需轻量化加载 + 智能压缩 |
| 记忆无结构化 | 多维度分类 + 标签 + 重要性分层 |
| 隐私混同 | 物理隔离四级隐私分级 |
| 调用僵化 | 语义向量 + FTS5 混合精准召回 |

---

## 2. 系统架构图（ASCII）

```
================================================================================
                         ClawMemory 系统
================================================================================

  +---------------------------------------------------------------------+
  |                         adapters/ 适配层                              |
  |  +-------------------------+    +--------------------------------+ |
  |  |   OpenClaw Adapter      |    |   Claude Code (Codex) Adapter  | |
  |  |   tool_search()         |    |   memory_search()              | |
  |  |   tool_add()           |    |   memory_add()                 | |
  |  |   tool_get()           |    |   memory_list()                | |
  |  |   tool_update()        |    |   memory_context() (MCP)       | |
  |  |   get_session_ctx()    |    |                               | |
  |  +-------------+-----------+    +---------------+--------------+ |
  +------------------+---------------------------+--------------------+
                                     |
                                     v
  +---------------------------------------------------------------------+
  |                         modules/ 功能模块层                           |
  |                                                                       |
  |  +----------------+  +----------------+  +----------------+         |
  |  | categorizer   |  | recall         |  | integrator     |         |
  |  | 分类管理模块   |  | 召回引擎模块    |  | 整合器模块      |         |
  |  |               |  |               |  |               |         |
  |  | - 层级分类树   |  | - 语义向量召回  |  | - 多片段聚合   |         |
  |  | - 自动分类建议 |  | - FTS全文召回  |  | - 时间线重建   |         |
  |  | - 动态标签提取 |  | - 时间衰减加权  |  | - 关键信息提取 |         |
  |  | - 分类统计    |  | - 会话连续性    |  | - 摘要压缩     |         |
  |  +---------------+  +---------------+  +---------------+          |
  |                              |                                      |
  |                              v                                      |
  |  +--------------------------------------------------------------+   |
  |  |  privacy 隐私引擎模块                                         |   |
  |  |  PrivacyScanResult  隐私扫描（自动识别敏感信息）              |   |
  |  |  AccessControl       访问控制列表（ACL）                       |   |
  |  |  Isolation           STRICT 级别物理隔离存储                  |   |
  |  |  ExportMasking       导出时自动脱敏                            |   |
  |  |  ComplianceReport    合规报告生成                             |   |
  |  +--------------------------------------------------------------+   |
  +---------------------------------------------------------------------+

                                     |
                                     v

  +---------------------------------------------------------------------+
  |                         core/ 核心引擎层                             |
  |                                                                       |
  |  +----------------+  +----------------+  +----------------+         |
  |  | encryption.py  |  | storage.py      |  | indexer.py     |         |
  |  |               |  |               |  |               |         |
  |  | AES-256-GCM  |  | SQLite + WAL  |  | TF-IDF向量化  |         |
  |  | PBKDF2-SHA256|  | FTS5全文索引   |  | SQLite向量库   |         |
  |  | 密钥派生+绑定 |  | 隐私分级存储   |  | 语义相似度计算 |         |
  |  | 本地密钥文件  |  | 审计日志       |  | 综合评分器     |         |
  |  +-------+--------+  +-------+--------+  +-------+--------+         |
  |          |                    |                   |                 |
  |          +--------------------+-------------------+                 |
  |                              v                                      |
  |  +--------------------------------------------------------------+   |
  |  |  query.py 查询引擎                                             |   |
  |  |  混合检索（语义 + FTS + 规则）                                 |   |
  |  |  综合评分（重要性 x 时间衰减 x 访问频率）                       |   |
  |  |  RAG Context Builder（Agent 注入）                              |   |
  |  |  Session Context（对话连续性）                                  |   |
  |  +--------------------------------------------------------------+   |
  +---------------------------------------------------------------------+

                                     |
                                     v

  +---------------------------------------------------------------------+
  |                        data/ 数据存储层                             |
  |                                                                       |
  |  +----------------+  +----------------+  +----------------+        |
  |  | store/         |  | index/         |  | backup/        |        |
  |  | memory.db      |  | vectors.db     |  | backup_*.db    |        |
  |  | (加密数据)     |  | (向量索引)      |  | (加密增量备份) |        |
  |  | strict/       |  | idf_cache/    |  |               |        |
  |  | (STRICT级)    |  |               |  |               |        |
  |  | + acl.json    |  |               |  |               |        |
  |  +----------------+  +----------------+  +----------------+       |
  |                                                                       |
  |  +----------------+  +----------------+  +----------------+         |
  |  | .key          |  | .salt         |  | .verify       |         |
  |  | (加密密钥)     |  | (密钥派生盐)   |  | (密码验证令牌) |         |
  |  +----------------+  +----------------+  +----------------+        |
  +---------------------------------------------------------------------+

================================================================================
                    cli/ 命令行工具
    init  add  search  list  get  update  delete  stats  audit
    backup  export  import  privacy-scan  compliance
================================================================================
```

---

## 3. 数据流架构

### 3.1 记忆写入流程

```
用户/Agent 输入
      |
      v
+---------------+     隐私扫描      +---------------+
|   内容验证     | -------------> | PrivacyEngine |
+---------------+                +-------+--------+
                                      | PrivacyLevel
                                      v
+---------------+     自动分类       +---------------+
|  Taxonomy    | -------------> | Categorizer  |
|  Manager     |                +-------+--------+
+---------------+                        | category + tags
                                        v
+---------------+     AES-256          +---------------+
|  Encryption  | <------------------ | content       |
|  Engine      |    加密              +-------+--------+
+-------+------+                             |
        |                                   v
        |                           +---------------+
        |                           | StorageEngine |
        |                           |   (SQLite)    |
        |                           +-------+--------+
        |                                   | WAL 写入
        |                                   v
        |                           +---------------+
        +-------------------------> | VectorIndex   |
              同步索引                 | TF-IDF 索引  |
                                      +---------------+
```

### 3.2 记忆召回流程（RAG）

```
Agent 查询 "..."
      |
      v
+---------------+    隐私过滤     +---------------+
| PrivacyEngine | <-------------- | max_privacy  |
+-------+-------+                +-------+--------+
        |                                  |
        v                                  v
+---------------+                   +---------------+
| VectorIndex   |                   | FTS5 全文索引 |
| 语义相似度     |                   | 关键词命中    |
+-------+-------+                   +-------+--------+
        |                                  |
        +---------------+------------------+
                        | merge + dedup
                        v
               +-----------------+
               | CompositeScorer|
               | 语义x重要性x时间 |
               | x频率 综合评分   |
               +--------+--------+
                        | top_k 排序
                        v
               +-----------------+
               | ContextWindow   |
               | Optimizer       |
               | 压缩到 token 上限|
               +--------+--------+
                        |
                        v
               +-----------------+
               | Agent Prompt    |
               | [相关记忆片段]    |
               +-----------------+
```

---

## 4. 核心数据模型

### 4.1 PrivacyLevel（隐私分级）

| 级别 | 值 | 存储位置 | 访问控制 |
|------|---|---------|---------|
| PUBLIC | 0 | 普通表 | 无限制 |
| INTERNAL | 1 | 普通表 | 同 Agent 会话 |
| PRIVATE | 2 | 普通表 + ACL | 需显式授权 |
| STRICT | 3 | 独立 strict/ 目录 | 物理隔离 + ACL |

### 4.2 MemoryEntry

```python
@dataclass
class MemoryEntry:
    id: str                    # UUID v4
    content: str               # AES-256-GCM 加密（EncryptedBlob base64）
    plaintext_preview: str    # 前200字符（FTS索引用，不含敏感）
    category: str              # 分类标签
    tags: List[str]           # 多标签
    privacy: PrivacyLevel      # 四级隐私
    importance: Importance     # LOW/MEDIUM/HIGH/CRITICAL
    source_session: str        # 来源会话
    source_agent: str          # 来源Agent
    created_at: float         # Unix timestamp
    updated_at: float
    accessed_at: float
    access_count: int
    is_deleted: bool           # 软删除
    metadata_json: str         # 扩展元数据
```

---

## 5. API 规格

### OpenClaw Adapter

```python
# 工具方法（Agent调用）
tool_search(query, agent_id, session_id, max_results, category)
tool_add(content, category, tags, privacy, importance, auto_categorize)
tool_get(memory_id, agent_id, session_id)
tool_list(agent_id, session_id, category, limit, offset)
tool_update(memory_id, content, category, tags, privacy, importance)
tool_delete(memory_id, agent_id, session_id, hard)
tool_audit(memory_id, actor, limit)
tool_stats()

# 会话上下文（自动注入）
get_session_memory_context(question, agent_id, session_id, max_chars)
get_conversation_context(agent_id, session_id)

# 隐私管理
grant_memory_access(memory_id, to_agent, duration_hours)
revoke_memory_access(memory_id, to_agent)
scan_privacy(text)
compliance_report()
```

### Claude Code Adapter (MCP)

```python
memory_search(query, max_results, category) -> {"found", "query_ms", "results"}
memory_add(content, category, tags, privacy, importance) -> {"id", "category", "tags"}
memory_list(category, limit) -> {"total", "memories"}
memory_get(memory_id) -> {"id", "content", "category", ...}
memory_delete(memory_id, hard) -> {"success"}
memory_stats() -> {"total", "by_privacy", "db_size_mb"}
memory_context(query, max_chars) -> str  # prompt注入
```

---

## 6. 性能设计

| 指标 | 目标 | 实现方式 |
|------|------|---------|
| 写入延迟 | < 50ms/条 | WAL模式 + 批量索引 |
| 检索延迟 P95 | <= 200ms (10万条) | TF-IDF + 内存缓存top-1000 |
| 存储效率 | ~2KB/条 | SQLite压缩 + 向量截断 |
| 索引容量 | 100万+条 | 分片索引 + 增量更新 |

---

## 7. 安全设计

| 机制 | 实现 |
|------|------|
| 加密算法 | AES-256-GCM（AEAD，认证加密） |
| 密钥派生 | PBKDF2-SHA256, 100000次迭代 |
| 密钥绑定 | 密钥 + 机器特征哈希绑定 |
| 隐私分级 | 4级物理隔离，STRICT独立目录 |
| 访问控制 | ACL访问授权列表 |
| 审计日志 | 所有操作记录（不含内容） |
| 数据脱敏 | 导出时自动识别并脱敏敏感信息 |
| 云端上传 | 架构层面完全禁用 |

---

## 8. 模块依赖

```
adapters/
  openclaw_adapter.py    <- modules.*, core.*
  claude_code_adapter.py <- modules.*, core.*

modules/
  categorizer.py         <- (无外部依赖)
  recall.py              <- core.*
  integrator.py          <- core.*
  privacy.py             <- core.*

core/
  encryption.py          <- cryptography标准库
  storage.py             <- core.encryption
  indexer.py             <- (无外部依赖，纯Python)
  query.py               <- core.{storage, indexer}

cli/main.py             <- core.*, modules.*
```
