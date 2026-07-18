#!/usr/bin/env python3
"""
ClawMemory v5.0.2 CLI - 命令行工具
=================================

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
    consolidate         记忆巩固（短期→长期）
    evolution           记忆演化统计
    graph               知识图谱操作
    personality         人格化引擎
    multimodal          多模态记忆
    federated           联邦记忆
    serve               启动 Web UI
"""

import sys
import json
import argparse
import getpass
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    ClawMemory,
    MemoryConfig,
    PrivacyLevel,
    Importance,
    MemoryType,
    MemoryLayer,
)

from modules import (
    RecallConfig,
    KnowledgeGraph,
    MemoryEvolution,
    PersonalityEngine,
    MultimodalMemory,
    FederatedMemory,
    TaxonomyManager,
    PrivacyEngine,
    MemoryIntegrator,
)

COLORS = {
    "cyan": "\033[96m",
    "purple": "\033[95m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "pink": "\033[95m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def c(text: str, color: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def format_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / 1024 / 1024:.2f} MB"


def print_banner():
    banner = f"""
{COLORS['cyan']}╔══════════════════════════════════════════════════════╗
║        {COLORS['bold']}ClawMemory v5.0.2 - AI Agent 终身记忆系统{COLORS['reset']}{COLORS['cyan']}        ║
║      四层记忆架构 · 知识图谱 · 多模态 · 人格化      ║
╚══════════════════════════════════════════════════════╝{COLORS['reset']}
"""
    print(banner)


def cmd_init(args):
    """初始化 ClawMemory"""
    print_banner()
    print(c("ClawMemory 初始化向导", "bold"))
    print("=" * 50)

    password = getpass.getpass("请设置加密密码（用于保护记忆）：")
    if not password:
        print(c("❌ 密码不能为空", "red"))
        return 1

    password2 = getpass.getpass("请再次输入密码确认：")
    if password != password2:
        print(c("❌ 两次密码不一致", "red"))
        return 1

    if len(password) < 8:
        print(c("⚠️  警告：密码建议至少 8 位", "yellow"))

    print("\n正在生成加密密钥（PBKDF2-SHA256，100000 次迭代）...")

    try:
        config = MemoryConfig(
            db_path=args.db_path,
            key_file=args.key_file,
            encrypted=True,
        )
        cm = ClawMemory(config=config)
        cm.init_with_password(password)

        print(c("\n✅ 初始化成功！", "green"))
        print(f"   数据库路径: {args.db_path}")
        print(f"   密钥文件: {args.key_file}")
        print(c("\n   提示：请妥善保管密码，丢失后无法恢复记忆数据", "yellow"))
        return 0
    except Exception as e:
        print(c(f"❌ 初始化失败：{e}", "red"))
        return 1


def _get_memory(args) -> ClawMemory:
    config = MemoryConfig(
        db_path=args.db_path,
        key_file=args.key_file,
        encrypted=False,
    )
    return ClawMemory(config=config)


def cmd_add(args):
    """添加记忆"""
    cm = _get_memory(args)
    taxonomy = TaxonomyManager()

    content = args.content
    category = args.category
    if not category:
        category = taxonomy.suggest_category(content)
        print(f"  建议分类：{c(category, 'cyan')}")

    tags = args.tags
    if not tags:
        tags = taxonomy.suggest_tags(content)
        print(f"  建议标签：{', '.join(tags) if tags else '无'}")

    privacy = PrivacyLevel.from_string(args.privacy)
    layer = MemoryLayer.from_string(args.layer)
    memory_type = MemoryType.from_string(args.type)

    entry = cm.add(
        content=content,
        category=category,
        tags=tags,
        privacy=privacy,
        importance=Importance.from_string(args.importance),
        memory_type=memory_type,
        layer=layer,
        source_session=args.session,
        source_agent=args.agent,
        starred=getattr(args, "star", False),
    )

    print(c("\n✅ 记忆已保存", "green"))
    print(f"   ID: {entry.id}")
    print(f"   分类: {entry.category}")
    print(f"   标签: {', '.join(entry.tags) if entry.tags else '无'}")
    print(f"   层级: {c(entry.layer.value, 'purple')}")
    print(f"   隐私: {entry.privacy.value}")
    print(f"   重要性: {args.importance}")
    if entry.starred:
        print(f"   ⭐ 已收藏")
    return 0


def cmd_search(args):
    """搜索记忆"""
    cm = _get_memory(args)

    cfg = RecallConfig(
        max_results=args.limit,
        min_relevance=0.2,
        include_categories=[args.category] if args.category else None,
    )

    result = cm.search(
        query=args.query,
        max_results=args.limit,
        agent_id=args.agent,
        session_id=args.session,
    )

    print(f"\n找到 {c(result.total_found, 'cyan')} 条相关记忆"
          f"（耗时 {result.query_time_ms}ms）")
    print(f"策略：{result.strategy_used} | 预估 tokens：{result.token_estimate}")
    print(f"涉及层级：{', '.join(result.layers_used)}")

    for i, chunk in enumerate(result.chunks, 1):
        print(f"\n--- 结果 {i} [{chunk.category}] "
              f"相关度:{c(f'{chunk.relevance_score:.3f}', 'green')} "
              f"[{chunk.layer.value}] ---")
        content = chunk.content[:300]
        print(content)
        if len(chunk.content) > 300:
            print("...")

    return 0


def cmd_list(args):
    """列出记忆"""
    cm = _get_memory(args)

    starred = None
    if getattr(args, "starred", False):
        starred = True
    if getattr(args, "unstarred", False):
        starred = False

    created_after = None
    created_before = None
    if args.after:
        from datetime import datetime
        created_after = datetime.fromisoformat(args.after).timestamp()
    if args.before:
        from datetime import datetime
        created_before = datetime.fromisoformat(args.before).timestamp()

    entries = cm.list(
        category=args.category,
        layer=MemoryLayer.from_string(args.layer) if args.layer else None,
        starred=starred,
        created_after=created_after,
        created_before=created_before,
        limit=args.limit,
        offset=args.offset,
    )

    total = cm.stats()["total"]
    filter_desc = ""
    if starred is not None:
        filter_desc += " [⭐ 收藏]" if starred else " [未收藏]"
    if args.after or args.before:
        filter_desc += " [时间筛选]"
    print(f"\n记忆列表（共 {total} 条，显示 {len(entries)} 条{filter_desc}）")

    for entry in entries:
        privacy_color = {
            "PUBLIC": "green",
            "INTERNAL": "yellow",
            "PRIVATE": "red",
            "STRICT": "pink",
        }.get(entry.privacy.value, "reset")

        layer_color = {
            "sensory": "cyan",
            "short_term": "cyan",
            "long_term": "purple",
            "permanent": "green",
        }.get(entry.layer.value, "reset")

        star_mark = "⭐ " if entry.starred else ""

        print(f"\n{'='*50}")
        print(f"ID:       {entry.id[:16]}...")
        print(f"分类:     [{entry.category}]  "
              f"隐私: {c(entry.privacy.value, privacy_color)}  "
              f"层级: {c(entry.layer.value, layer_color)}  "
              f"重要性: {entry.importance.value}")
        if entry.starred:
            print(f"状态:     ⭐ 已收藏")
        print(f"标签:     {', '.join(entry.tags) if entry.tags else '无'}")
        print(f"类型:     {entry.memory_type.value}")
        print(f"创建:     {format_time(entry.created_at)}  "
              f"访问: {entry.access_count} 次")
        print(f"预览: {star_mark}{entry.preview[:80]}...")

    if total > args.limit + args.offset:
        print(f"\n... 还有 {total - args.limit - args.offset} 条"
              f"（使用 --offset {args.offset + args.limit} 查看更多）")

    return 0


def cmd_stats(args):
    """统计信息"""
    cm = _get_memory(args)
    stats = cm.stats()

    print_banner()
    print(c("ClawMemory 统计报告", "bold"))
    print("=" * 50)
    print(f"总记忆数：  {c(str(stats['total']), 'cyan')}")
    print(f"数据库大小：{format_size(stats['db_size_bytes'])}")
    print(f"数据库路径：{stats['db_path']}")

    print(f"\n按隐私分级：")
    for level, count in stats.get("by_privacy", {}).items():
        print(f"  {level}: {count}")

    print(f"\n按记忆层级：")
    for layer, count in stats.get("by_layer", {}).items():
        print(f"  {layer}: {count}")

    print(f"\n按重要性：")
    for level, count in stats.get("by_importance", {}).items():
        print(f"  {level}: {count}")

    print(f"\n分类统计（前10）：")
    for cat, count in list(stats.get("top_categories", {}).items())[:10]:
        print(f"  {cat}: {count}")

    return 0


def cmd_star(args):
    """收藏记忆"""
    cm = _get_memory(args)
    success = cm.star(args.id, actor=args.agent, session_id=args.session)
    if success:
        print(c("\n⭐ 已收藏", "green"))
    else:
        print(c("\n❌ 收藏失败：记忆不存在", "red"))
    return 0 if success else 1


def cmd_unstar(args):
    """取消收藏"""
    cm = _get_memory(args)
    success = cm.unstar(args.id, actor=args.agent, session_id=args.session)
    if success:
        print(c("\n🗑️  已取消收藏", "yellow"))
    else:
        print(c("\n❌ 取消失败：记忆不存在", "red"))
    return 0 if success else 1


def cmd_consolidate(args):
    """记忆巩固"""
    cm = _get_memory(args)
    evolution = MemoryEvolution(cm.storage)

    print(c("正在执行记忆巩固...", "cyan"))
    result = evolution.consolidate(agent_id=args.agent, session_id=args.session)

    print(c("\n✅ 记忆巩固完成", "green"))
    print(f"   处理: {result['processed']} 条")
    print(f"   提升到长期记忆: {c(str(result['promoted_to_long_term']), 'green')} 条")
    print(f"   降级到感官记忆: {c(str(result['demoted_to_sensory']), 'yellow')} 条")

    stats = evolution.get_evolution_stats()
    print(f"\n记忆层级分布：")
    print(f"  感官记忆: {stats['sensory']}")
    print(f"  短期记忆: {stats['short_term']}")
    print(f"  长期记忆: {stats['long_term']}")
    print(f"  永久记忆: {stats['permanent']}")
    print(f"  巩固率: {stats['consolidation_rate']:.1%}")

    return 0


def cmd_graph(args):
    """知识图谱操作"""
    cm = _get_memory(args)
    kg = KnowledgeGraph(storage=cm.storage)

    if args.graph_action == "stats":
        stats = kg.get_entity_stats()
        print(c("知识图谱统计", "bold"))
        print(f"  实体总数: {stats['total_entities']}")
        print(f"  关系总数: {stats['total_relations']}")
        print(f"\n  实体类型:")
        for etype, count in stats['entity_types'].items():
            print(f"    {etype}: {count}")
        print(f"\n  关系类型:")
        for rtype, count in stats['relation_types'].items():
            print(f"    {rtype}: {count}")

    elif args.graph_action == "related":
        entity = args.entity
        related = kg.get_related_entities(entity, depth=args.depth)
        print(f"\n与 '{c(entity, 'cyan')}' 相关的实体：")
        for name, rel_type, weight in related:
            print(f"  - {name}  [{rel_type}]  (权重: {weight:.2f})")

    elif args.graph_action == "extract":
        text = args.text
        entities = kg.extract_entities(text)
        print(f"\n提取到 {len(entities)} 个实体：")
        for name, etype in entities:
            print(f"  - {name} ({etype})")

    return 0


def cmd_personality(args):
    """人格化引擎"""
    cm = _get_memory(args)
    pe = PersonalityEngine(cm.storage)

    if args.personality_action == "profile":
        profile = pe.get_profile(args.user_id)
        print(c("用户画像", "bold"))
        print(f"  用户ID: {profile.user_id}")
        print(f"  交互次数: {profile.total_interactions}")
        print(f"  最后更新: {format_time(profile.last_updated)}")

        interests = pe.get_top_interests(args.user_id, 5)
        print(f"\n  兴趣主题 TOP5:")
        for topic, score in interests:
            print(f"    - {topic}: {score:.2f}")

        style = pe.get_recommended_style(args.user_id)
        print(f"\n  推荐交流风格:")
        for key, value in style.items():
            print(f"    - {key}: {value}")

    elif args.personality_action == "interests":
        interests = pe.get_top_interests(args.user_id, args.limit)
        print(f"\n用户 {args.user_id} 的兴趣 TOP {args.limit}：")
        for topic, score in interests:
            bar = "█" * int(score * 20)
            print(f"  {topic:<20} {bar} {score:.2f}")

    return 0


def cmd_backup(args):
    """备份"""
    cm = _get_memory(args)
    backup_path = cm.backup(args.output)
    print(c(f"✅ 备份已创建：{backup_path}", "green"))
    print(f"   大小：{format_size(backup_path.stat().st_size)}")
    return 0


def cmd_export(args):
    """导出记忆"""
    cm = _get_memory(args)
    layer = MemoryLayer(args.layer) if args.layer else None

    if args.format == "json":
        count = cm.export_json(
            output_path=args.output,
            category=args.category,
            layer=layer,
            include_private=args.include_private,
        )
    elif args.format == "csv":
        count = cm.export_csv(
            output_path=args.output,
            category=args.category,
            include_private=args.include_private,
        )
    else:
        print(c(f"❌ 不支持的格式：{args.format}", "red"))
        return 1

    print(c(f"✅ 导出成功！共 {count} 条记忆", "green"))
    print(f"   文件：{args.output}")
    print(f"   格式：{args.format.upper()}")
    cm.close()
    return 0


def cmd_import(args):
    """导入记忆"""
    cm = _get_memory(args)
    target_layer = MemoryLayer(args.target_layer) if args.target_layer else None

    stats = cm.import_json(
        input_path=args.input,
        skip_duplicates=not args.force,
        target_layer=target_layer,
    )

    print(c("📥 导入完成", "bold"))
    print("=" * 40)
    print(f"  成功导入：{c(str(stats['imported']), 'green')} 条")
    print(f"  跳过重复：{c(str(stats['skipped']), 'yellow')} 条")
    print(f"  导入失败：{c(str(stats['failed']), 'red')} 条")
    cm.close()
    return 0


def cmd_compliance(args):
    """合规报告"""
    cm = _get_memory(args)
    privacy_engine = PrivacyEngine(cm.storage)
    report = privacy_engine.generate_compliance_report()

    print(c("隐私合规报告", "bold"))
    print("=" * 50)
    print(f"报告时间：{format_time(report['report_time'])}")
    print(f"总记忆数：{report['total_memories']}")
    print(f"私密记忆：{report['private_memories']}")
    print(f"严格隔离：{report['strict_memories']}")
    print(f"活跃授权：{report['active_grants']}")
    print(f"合规状态：{c(report['compliance_status'], 'green' if report['compliance_status'] == 'PASS' else 'yellow')}")
    print(f"\n按隐私分级统计：")
    for level, count in report["by_privacy"].items():
        print(f"  {level}: {count}")

    return 0


def cmd_serve(args):
    """启动 Web UI"""
    print(c("启动 ClawMemory Web UI...", "cyan"))
    print(f"  地址: http://localhost:{args.port}")
    print(f"  数据库: {args.db_path}")
    print(c("\n  按 Ctrl+C 停止服务", "yellow"))

    try:
        import http.server
        import socketserver

        web_dir = Path(__file__).parent.parent / "website"
        if web_dir.exists():
            import os
            os.chdir(web_dir)

        Handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(c(f"启动失败：{e}", "red"))
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="clawmemory",
        description="ClawMemory v5.0.2 - AI Agent 终身记忆系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--db-path", default="./data/memory.db", help="数据库路径")
    parser.add_argument("--key-file", default="./data/.key", help="密钥文件路径")

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="初始化 ClawMemory")

    p_add = sub.add_parser("add", help="添加记忆")
    p_add.add_argument("content", help="记忆内容")
    p_add.add_argument("--category", "-c", help="分类")
    p_add.add_argument("--tags", "-t", nargs="+", help="标签")
    p_add.add_argument("--privacy", "-p", default="INTERNAL",
                       choices=["PUBLIC", "INTERNAL", "PRIVATE", "STRICT"], help="隐私等级")
    p_add.add_argument("--importance", "-i", default="MEDIUM",
                       choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], help="重要性")
    p_add.add_argument("--layer", "-l", default="short_term",
                       choices=["sensory", "short_term", "long_term", "permanent"], help="记忆层级")
    p_add.add_argument("--type", default="text",
                       choices=["text", "image", "audio", "code", "structured"], help="记忆类型")
    p_add.add_argument("--session", default="cli", help="会话 ID")
    p_add.add_argument("--agent", default="cli", help="Agent ID")
    p_add.add_argument("--star", action="store_true", help="添加后直接收藏")

    p_search = sub.add_parser("search", help="搜索记忆")
    p_search.add_argument("query", help="搜索查询")
    p_search.add_argument("--limit", type=int, default=10, help="最大结果数")
    p_search.add_argument("--category", "-c", help="分类筛选")
    p_search.add_argument("--agent", default="", help="Agent ID")
    p_search.add_argument("--session", default="", help="会话 ID")

    p_list = sub.add_parser("list", help="列出记忆")
    p_list.add_argument("--category", "-c", help="分类筛选")
    p_list.add_argument("--layer", "-l", help="层级筛选")
    p_list.add_argument("--starred", action="store_true", default=None,
                        help="只显示已收藏")
    p_list.add_argument("--unstarred", action="store_true", default=None,
                        help="只显示未收藏")
    p_list.add_argument("--after", help="创建时间之后 (YYYY-MM-DD 或 ISO 格式)")
    p_list.add_argument("--before", help="创建时间之前 (YYYY-MM-DD 或 ISO 格式)")
    p_list.add_argument("--limit", type=int, default=50, help="数量限制")
    p_list.add_argument("--offset", type=int, default=0, help="偏移量")

    p_stats = sub.add_parser("stats", help="统计信息")

    p_star = sub.add_parser("star", help="收藏记忆")
    p_star.add_argument("id", help="记忆 ID")
    p_star.add_argument("--agent", default="cli", help="Agent ID")
    p_star.add_argument("--session", default="cli", help="会话 ID")

    p_unstar = sub.add_parser("unstar", help="取消收藏")
    p_unstar.add_argument("id", help="记忆 ID")
    p_unstar.add_argument("--agent", default="cli", help="Agent ID")
    p_unstar.add_argument("--session", default="cli", help="会话 ID")

    p_consolidate = sub.add_parser("consolidate", help="记忆巩固")
    p_consolidate.add_argument("--agent", default="cli", help="Agent ID")
    p_consolidate.add_argument("--session", default="cli", help="会话 ID")

    p_graph = sub.add_parser("graph", help="知识图谱")
    p_graph.add_argument("graph_action", choices=["stats", "related", "extract"], help="操作")
    p_graph.add_argument("--entity", help="实体名称")
    p_graph.add_argument("--depth", type=int, default=2, help="深度")
    p_graph.add_argument("--text", help="要提取的文本")

    p_personality = sub.add_parser("personality", help="人格化")
    p_personality.add_argument("personality_action", choices=["profile", "interests"], help="操作")
    p_personality.add_argument("--user-id", default="default", help="用户 ID")
    p_personality.add_argument("--limit", type=int, default=10, help="数量限制")

    p_backup = sub.add_parser("backup", help="备份数据")
    p_backup.add_argument("--output", default="./data/backup", help="备份目录")

    p_export = sub.add_parser("export", help="导出记忆")
    p_export.add_argument("--output", "-o", default="./data/export.json", help="输出文件")
    p_export.add_argument("--format", "-f", default="json", choices=["json", "csv"], help="导出格式")
    p_export.add_argument("--category", "-c", help="按分类筛选")
    p_export.add_argument("--layer", "-l", help="按层级筛选")
    p_export.add_argument("--include-private", action="store_true", help="包含私密记忆")

    p_import = sub.add_parser("import", help="导入记忆")
    p_import.add_argument("input", help="导入文件路径")
    p_import.add_argument("--target-layer", help="目标记忆层级")
    p_import.add_argument("--force", action="store_true", help="强制导入（覆盖重复）")

    p_compliance = sub.add_parser("compliance", help="合规报告")

    p_serve = sub.add_parser("serve", help="启动 Web UI")
    p_serve.add_argument("--port", type=int, default=8080, help="端口")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "add": cmd_add,
        "search": cmd_search,
        "list": cmd_list,
        "stats": cmd_stats,
        "star": cmd_star,
        "unstar": cmd_unstar,
        "consolidate": cmd_consolidate,
        "graph": cmd_graph,
        "personality": cmd_personality,
        "backup": cmd_backup,
        "export": cmd_export,
        "import": cmd_import,
        "compliance": cmd_compliance,
        "serve": cmd_serve,
    }

    cmd = commands.get(args.command)
    if cmd:
        sys.exit(cmd(args) or 0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
