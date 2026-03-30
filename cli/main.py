"""
ClawMemory CLI - 命令行工具
===========================
Usage:
    python cli/main.py <command> [options]

Commands:
    init                初始化 ClawMemory（生成加密密钥）
    add <content>       添加记忆
    search <query>      搜索记忆
    list                列出所有记忆
    get <id>            获取单条记忆
    update <id>         更新记忆
    delete <id>         删除记忆
    stats               统计信息
    audit               审计日志
    backup              备份数据
    export <file>       导出记忆
    import <file>       导入记忆
    privacy-scan <text> 隐私扫描
    compliance          合规报告
    serve               启动 Web UI（可选）

Examples:
    python cli/main.py init
    python cli/main.py add ""今天学会了 ClawMemory"" --category life --importance high
    python cli/main.py search ""ClawMemory 使用方法""
    python cli/main.py list --category work --limit 20
    python cli/main.py stats
    python cli/main.py audit --actor openclaw
    python cli/main.py backup
    python cli/main.py export memories_backup.clawmem --password xxx
"""

import sys
import json
import argparse
import getpass
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    init_engine, get_engine,
    StorageEngine, QueryEngine, IndexManager,
    PrivacyLevel, Importance, MemoryEntry,
)
from modules import (
    RecallEngine, RecallConfig,
    PrivacyEngine, PrivacyScanResult,
    TaxonomyManager,
)


# ============================================================================
# Formatters
# ============================================================================
def format_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

def format_size(bytes: int) -> str:
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    else:
        return f"{bytes / 1024 / 1024:.2f} MB"

def format_privacy(p: PrivacyLevel) -> str:
    colors = {"PUBLIC": "\033[92m", "INTERNAL": "\033[93m",
              "PRIVATE": "\033[91m", "STRICT": "\033[95m"}
    RESET = "\033[0m"
    return f"""{colors.get(p.value, "")}{p.value}{RESET}"""

def format_entry(entry: MemoryEntry, show_content: bool = False) -> str:
    privacy_color = {"PUBLIC": "\033[92m", "INTERNAL": "\033[93m",
                     "PRIVATE": "\033[91m", "STRICT": "\033[95m"}
    RESET = "\033[0m"
    c = privacy_color.get(entry.privacy.value, "")
    lines = [
        f"\n{'='*60}",
        f"ID:       {entry.id}",
        f"分类:     [{entry.category}]  隐私: {c}{entry.privacy.value}{RESET}  重要性: {entry.importance.name}",
        f"标签:     {', '.join(entry.tags) if entry.tags else '无'}",
        f"会话:     {entry.source_session}  |  Agent: {entry.source_agent}",
        f"创建:     {format_time(entry.created_at)}  |  更新: {format_time(entry.updated_at)}",
        f"访问:     {entry.access_count} 次",
    ]
    if show_content:
        lines.append(f"内容:\n{entry.plaintext_preview}")
    else:
        lines.append(f"预览: {entry.plaintext_preview[:100]}...")
    return "\n".join(lines)


# ============================================================================
# CLI Commands
# ============================================================================
def cmd_init(args):
    """| 初始化 ClawMemory |"""
    print("=" * 60)
    print("ClawMemory 初始化向导")
    print("=" * 60)

    password = getpass.getpass("请设置加密密码（用于保护记忆）：")
    if not password:
        print("密码不能为空。")
        return 1

    password2 = getpass.getpass("请再次输入密码确认：")
    if password != password2:
        print("两次密码不一致。")
        return 1

    if len(password) < 8:
        print("警告：密码建议至少 8 位。")

    print("\n正在生成加密密钥（PBKDF2-SHA256，100000 次迭代）...")
    try:
        init_engine(password)
        print("\n✅ 初始化成功！")
        print("   密钥文件已保存在 data/ 目录")
        print("   首次添加记忆时会自动创建数据库。")
        return 0
    except Exception as e:
        print(f"❌ 初始化失败：{e}")
        return 1


def _ensure_init() -> Optional[StorageEngine]:
    try:
        storage = StorageEngine()
        return storage
    except Exception as e:
        print(f"❌ 无法初始化存储引擎：{e}")
        print("请先运行：python cli/main.py init")
        return None


def cmd_add(args):
    """| 添加记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    taxonomy = TaxonomyManager()
    privacy_engine = PrivacyEngine(storage)
    index = IndexManager()
    recall = RecallEngine(storage=storage, index=index)

    content = args.content

    # Auto-categorize
    category = args.category
    if not category:
        category = taxonomy.suggest_category(content)
        print(f"  建议分类：{category}")

    # Auto-tag
    tags = args.tags
    if not tags:
        tags = taxonomy.suggest_tags(content)
        print(f"  建议标签：{', '.join(tags) if tags else '无'}")

    # Privacy
    privacy = PrivacyLevel.from_string(args.privacy)
    if args.auto_privacy:
        scan = privacy_engine.scan(content)
        if scan.suggested_privacy.to_int() > privacy.to_int():
            privacy = scan.suggested_privacy
            print(f"  ⚠️  隐私升级：自动调整为 {privacy.value}（检测到敏感信息：{', '.join(scan.detected_types)}）")

    # Add
    entry = storage.add_memory(
        content=content,
        category=category,
        tags=tags,
        privacy=privacy,
        importance=Importance.from_string(args.importance),
        source_session=args.session,
        source_agent=args.agent,
    )

    # Index
    index.index_memory(
        entry.id, content,
        metadata={"category": category, "tags": tags, "importance": entry.importance.value},
    )

    print(f"\n✅ 记忆已保存")
    print(f"   ID: {entry.id}")
    print(f"   分类: {category}")
    print(f"   标签: {', '.join(tags) if tags else '无'}")
    print(f"   隐私: {privacy.value}")
    print(f"   重要性: {args.importance}")
    return 0


def cmd_search(args):
    """| 搜索记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    index = IndexManager()
    recall = RecallEngine(storage=storage, index=index)

    cfg = RecallConfig(
        max_results=args.limit,
        include_categories=[args.category] if args.category else None,
    )
    result = recall.recall(
        query=args.query,
        agent_id=args.agent,
        session_id=args.session,
        config=cfg,
    )

    print(f"\n找到 {result.total_found} 条相关记忆（耗时 {result.query_time_ms}ms）")
    print(f"策略：{result.strategy_used} | 预估 tokens：{result.token_estimate}")

    for i, chunk in enumerate(result.chunks, 1):
        print(f"\n--- 结果 {i} [{chunk.category}] 相关度:{chunk.relevance_score:.3f} ---")
        print(chunk.content[:300])
        if chunk.content[300:]:
            print("...")

    return 0


def cmd_list(args):
    """| 列出记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    privacy_engine = PrivacyEngine(storage)

    entries = storage.list_memories(
        category=args.category,
        limit=args.limit,
        offset=args.offset,
    )

    # Filter by access
    accessible = [
        e for e in entries
        if privacy_engine.check_access(e, args.agent, args.session)[0]
    ]

    total = storage.count_memories(args.category)
    print(f"\n记忆列表（共 {total} 条，显示 {len(accessible)} 条）")

    for entry in accessible:
        tags_str = ", ".join(entry.tags[:3]) if entry.tags else "无"
        print(format_entry(entry))

    if total > args.limit + args.offset:
        print(f"\n... 还有 {total - args.limit - args.offset} 条（使用 --offset {args.offset + args.limit} 查看更多）")
    return 0


def cmd_get(args):
    """| 获取单条记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    privacy_engine = PrivacyEngine(storage)
    entry = storage.get_memory(args.id, args.agent, args.session)
    if not entry:
        print(f"未找到记忆 ID: {args.id}")
        return 1

    allowed, reason = privacy_engine.check_access(entry, args.agent, args.session)
    if not allowed:
        print(f"访问被拒绝：{reason}")
        return 1

    content = storage.decrypt_content(entry)
    print(format_entry(entry, show_content=True))
    print(f"\n完整内容：\n{content}")
    return 0


def cmd_update(args):
    """| 更新记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1
    index = IndexManager()

    privacy = PrivacyLevel.from_string(args.privacy) if args.privacy else None
    importance = Importance.from_string(args.importance) if args.importance else None

    success = storage.update_memory(
        entry_id=args.id,
        content=args.content,
        category=args.category,
        tags=args.tags,
        privacy=privacy,
        importance=importance,
        actor=args.agent,
        session_id=args.session,
    )

    if success:
        if args.content:
            index.index_memory(args.id, args.content, metadata={})
        print(f"✅ 记忆已更新: {args.id}")
    else:
        print(f"❌ 更新失败：记忆不存在")
    return 0 if success else 1


def cmd_delete(args):
    """| 删除记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1
    index = IndexManager()

    if not args.confirm:
        print(f"确认删除记忆 {args.id}？（使用 --confirm 确认）")
        return 1

    success = storage.delete_memory(args.id, args.agent, args.session, args.hard)
    if success:
        index.remove_memory(args.id)
        print(f"✅ 记忆已{'永久' if args.hard else '软'}删除: {args.id}")
    else:
        print(f"❌ 删除失败：记忆不存在")
    return 0 if success else 1


def cmd_stats(args):
    """| 统计信息 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    stats = storage.get_stats()
    print(f"\n{'='*50}")
    print(f"ClawMemory 统计报告")
    print(f"{'='*50}")
    print(f"总记忆数：  {stats['total']}")
    print(f"数据库大小：{format_size(stats['db_size_bytes'])}")
    print(f"数据库路径：{stats['db_path']}")
    print(f"\n按隐私分级：")
    for level, count in stats["by_privacy"].items():
        print(f"  {level}: {count}")
    print(f"\n按重要性：")
    for level, count in stats["by_importance"].items():
        print(f"  {level}: {count}")
    print(f"\n分类统计（前10）：")
    for cat, count in list(stats["top_categories"].items())[:10]:
        print(f"  {cat}: {count}")
    return 0


def cmd_audit(args):
    """| 审计日志 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    records = storage.get_audit_log(
        memory_id=args.memory_id,
        actor=args.actor,
        limit=args.limit,
    )

    print(f"\n审计日志（共 {len(records)} 条）")
    for r in records:
        print(f"  [{format_time(r.timestamp)}] {r.action} | {r.actor} | memory={r.memory_id[:8]}... | privacy={r.privacy_level}")
    return 0


def cmd_backup(args):
    """| 备份数据 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    backup_dir = Path(__file__).parent.parent / "data" / "backup"
    backup_path = storage.backup(backup_dir)
    print(f"✅ 备份已创建：{backup_path}")
    print(f"   大小：{format_size(backup_path.stat().st_size)}")
    return 0


def cmd_export(args):
    """| 导出记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    privacy_engine = PrivacyEngine(storage)
    entries = storage.list_memories(limit=10000)

    exported = privacy_engine.export_with_privacy(entries, anonymize=True)
    output = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(exported),
        "memories": exported,
    }

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 已导出 {len(exported)} 条记忆到 {output_path}")
    print(f"   私密内容已自动脱敏")
    return 0


def cmd_import(args):
    """| 导入记忆 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    import_path = Path(args.file)
    if not import_path.exists():
        print(f"文件不存在：{args.file}")
        return 1

    with open(import_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    memories = data.get("memories", [])
    print(f"准备导入 {len(memories)} 条记忆...")

    index = IndexManager()
    imported = 0
    for mem in memories:
        try:
            entry = storage.add_memory(
                content=mem.get("content", mem.get("plaintext_preview", "")),
                category=mem.get("category", "general"),
                tags=mem.get("tags", []),
                privacy=PrivacyLevel.from_string(mem.get("privacy", "INTERNAL")),
                importance=Importance.from_string(mem.get("importance", "MEDIUM")),
            )
            index.index_memory(entry.id, entry.plaintext_preview, metadata={})
            imported += 1
        except Exception as e:
            print(f"  跳过 1 条（导入失败：{e}）")

    print(f"✅ 成功导入 {imported}/{len(memories)} 条记忆")
    return 0


def cmd_privacy_scan(args):
    """| 隐私扫描 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    privacy_engine = PrivacyEngine(storage)
    result = privacy_engine.scan(args.text)

    print(f"\n隐私扫描结果：")
    print(f"  是否敏感：{'是' if result.is_sensitive else '否'}")
    print(f"  建议隐私等级：{result.suggested_privacy.value}")
    print(f"  置信度：{result.confidence:.1%}")
    if result.detected_types:
        print(f"  检测到敏感类型：{', '.join(result.detected_types)}")
    print(f"\n脱敏预览：")
    print(result.masked_preview[:500])
    return 0


def cmd_compliance(args):
    """| 合规报告 |"""
    storage = _ensure_init()
    if not storage:
        return 1

    privacy_engine = PrivacyEngine(storage)
    report = privacy_engine.generate_compliance_report()

    print(f"\n{'='*50}")
    print(f"ClawMemory 隐私合规报告")
    print(f"{'='*50}")
    print(f"报告时间：{format_time(report['report_time'])}")
    print(f"总记忆数：{report['total_memories']}")
    print(f"私密记忆：{report['private_memories']}")
    print(f"严格隔离：{report['strict_memories']}")
    print(f"活跃授权：{report['active_grants']}")
    print(f"合规状态：{report['compliance_status']}")
    print(f"\n按隐私分级统计：")
    for level, count in report["by_privacy"].items():
        print(f"  {level}: {count}")
    return 0


# ============================================================================
# Main Entry
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        prog="clawmemory",
        description="ClawMemory CLI - AI 终身记忆系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="初始化 ClawMemory")

    # add
    p_add = sub.add_parser("add", help="添加记忆")
    p_add.add_argument("content", help="记忆内容")
    p_add.add_argument("--category", "-c", help="分类")
    p_add.add_argument("--tags", "-t", nargs="+", help="标签")
    p_add.add_argument("--privacy", "-p", default="INTERNAL", choices=["PUBLIC", "INTERNAL", "PRIVATE", "STRICT"], help="隐私等级")
    p_add.add_argument("--importance", "-i", default="MEDIUM", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], help="重要性")
    p_add.add_argument("--auto-privacy", action="store_true", help="自动检测隐私等级")
    p_add.add_argument("--session", default="cli", help="会话 ID")
    p_add.add_argument("--agent", default="cli", help="Agent ID")

    # search
    p_search = sub.add_parser("search", help="搜索记忆")
    p_search.add_argument("query", help="搜索查询")
    p_search.add_argument("--limit", "-l", type=int, default=10, help="最大结果数")
    p_search.add_argument("--category", help="限定分类")
    p_search.add_argument("--session", default="cli", help="会话 ID")
    p_search.add_argument("--agent", default="cli", help="Agent ID")

    # list
    p_list = sub.add_parser("list", help="列出记忆")
    p_list.add_argument("--category", help="限定分类")
    p_list.add_argument("--limit", "-l", type=int, default=20, help="最大结果数")
    p_list.add_argument("--offset", type=int, default=0, help="偏移量")
    p_list.add_argument("--session", default="cli", help="会话 ID")
    p_list.add_argument("--agent", default="cli", help="Agent ID")

    # get
    p_get = sub.add_parser("get", help="获取单条记忆")
    p_get.add_argument("id", help="记忆 ID")
    p_get.add_argument("--session", default="cli", help="会话 ID")
    p_get.add_argument("--agent", default="cli", help="Agent ID")

    # update
    p_upd = sub.add_parser("update", help="更新记忆")
    p_upd.add_argument("id", help="记忆 ID")
    p_upd.add_argument("--content", help="新内容")
    p_upd.add_argument("--category", "-c", help="新分类")
    p_upd.add_argument("--tags", "-t", nargs="+", help="新标签")
    p_upd.add_argument("--privacy", "-p", choices=["PUBLIC", "INTERNAL", "PRIVATE", "STRICT"])
    p_upd.add_argument("--importance", "-i", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    p_upd.add_argument("--session", default="cli", help="会话 ID")
    p_upd.add_argument("--agent", default="cli", help="Agent ID")

    # delete
    p_del = sub.add_parser("delete", help="删除记忆")
    p_del.add_argument("id", help="记忆 ID")
    p_del.add_argument("--confirm", action="store_true", help="确认删除")
    p_del.add_argument("--hard", action="store_true", help="永久删除")
    p_del.add_argument("--session", default="cli", help="会话 ID")
    p_del.add_argument("--agent", default="cli", help="Agent ID")

    # stats
    sub.add_parser("stats", help="统计信息")

    # audit
    p_audit = sub.add_parser("audit", help="审计日志")
    p_audit.add_argument("--memory-id", help="记忆 ID")
    p_audit.add_argument("--actor", help="操作者")
    p_audit.add_argument("--limit", "-l", type=int, default=50)

    # backup
    sub.add_parser("backup", help="备份数据")

    # export
    p_exp = sub.add_parser("export", help="导出记忆")
    p_exp.add_argument("output", help="输出文件路径")

    # import
    p_imp = sub.add_parser("import", help="导入记忆")
    p_imp.add_argument("file", help="导入文件路径")

    # privacy-scan
    p_priv = sub.add_parser("privacy-scan", help="隐私扫描")
    p_priv.add_argument("text", help="要扫描的文本")

    # compliance
    sub.add_parser("compliance", help="合规报告")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "add": cmd_add,
        "search": cmd_search,
        "list": cmd_list,
        "get": cmd_get,
        "update": cmd_update,
        "delete": cmd_delete,
        "stats": cmd_stats,
        "audit": cmd_audit,
        "backup": cmd_backup,
        "export": cmd_export,
        "import": cmd_import,
        "privacy-scan": cmd_privacy_scan,
        "compliance": cmd_compliance,
    }

    cmd = commands.get(args.command)
    if cmd:
        return cmd(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())