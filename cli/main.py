#!/usr/bin/env python3
"""
MindForge v5.2.0 CLI - 命令行工具
=================================

Usage:
    python cli/main.py <command> [options]

Commands:
    init                初始化 MindForge（生成加密密钥）
    add <content>       添加记忆
    search <query>      搜索记忆
    list                列出所有记忆
    get <id>            获取单条记忆（v5.1.1 补全）
    update <id>         更新记忆（v5.1.1 补全）
    delete <id>         删除记忆（v5.1.1 补全）
    stats               统计信息
    audit               审计日志（v5.1.1 补全）
    recent              最近添加的记忆（v5.1.1 新增）
    trash               查看回收站（v5.1.1 新增）
    restore <id>        从回收站恢复记忆（v5.1.1 新增）
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
import html
import time
from pathlib import Path
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    MindForge,
    MemoryConfig,
    PrivacyLevel,
    Importance,
    MemoryType,
    MemoryLayer,
)

try:
    from __init__ import __version__
except ImportError:
    __version__ = "5.2.1"

# 懒加载 modules：仅在对应命令执行时才导入，大幅加速 CLI 启动
_modules_cache = {}

def _lazy_import(name):
    if name not in _modules_cache:
        if name == "TaxonomyManager":
            from modules.categorizer import TaxonomyManager
            _modules_cache[name] = TaxonomyManager
        elif name == "RecallConfig":
            from modules.recall import RecallConfig
            _modules_cache[name] = RecallConfig
        elif name == "KnowledgeGraph":
            from modules.knowledge_graph import KnowledgeGraph
            _modules_cache[name] = KnowledgeGraph
        elif name == "MemoryEvolution":
            from modules.evolution import MemoryEvolution
            _modules_cache[name] = MemoryEvolution
        elif name == "PersonalityEngine":
            from modules.personality import PersonalityEngine
            _modules_cache[name] = PersonalityEngine
        elif name == "MultimodalMemory":
            from modules.multimodal import MultimodalMemory
            _modules_cache[name] = MultimodalMemory
        elif name == "FederatedMemory":
            from modules.federated import FederatedMemory
            _modules_cache[name] = FederatedMemory
        elif name == "PrivacyEngine":
            from modules.privacy import PrivacyEngine
            _modules_cache[name] = PrivacyEngine
        elif name == "MemoryIntegrator":
            from modules.integrator import MemoryIntegrator
            _modules_cache[name] = MemoryIntegrator
    return _modules_cache[name]

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
║        {COLORS['bold']}MindForge v5.2.1 - AI Agent 终身记忆系统{COLORS['reset']}{COLORS['cyan']}        ║
║      四层记忆架构 · 知识图谱 · 多模态 · 人格化      ║
╚══════════════════════════════════════════════════════╝{COLORS['reset']}
"""
    print(banner)


def cmd_init(args):
    """初始化 MindForge"""
    print_banner()
    print(c("MindForge v5.2.1 初始化向导", "bold"))
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
        cm = MindForge(config=config)
        cm.init_with_password(password)

        print(c("\n✅ 初始化成功！", "green"))
        print(f"   数据库路径: {args.db_path}")
        print(f"   密钥文件: {args.key_file}")
        print(c("\n   提示：请妥善保管密码，丢失后无法恢复记忆数据", "yellow"))
        return 0
    except Exception as e:
        print(c(f"❌ 初始化失败：{e}", "red"))
        return 1


def _get_memory(args) -> MindForge:
    config = MemoryConfig(
        db_path=args.db_path,
        key_file=args.key_file,
        encrypted=False,
    )
    return MindForge(config=config)


def cmd_add(args):
    """添加记忆"""
    cm = _get_memory(args)
    taxonomy = _lazy_import("TaxonomyManager")()

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

    result = cm.search(
        query=args.query,
        max_results=args.limit,
        min_relevance=0.2,
        categories=[args.category] if args.category else None,
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


def cmd_get(args):
    """获取单条记忆（v5.1.1 补全）"""
    cm = _get_memory(args)
    entry = cm.get(args.id, actor=args.agent, session_id=args.session)

    if not entry:
        print(c("❌ 记忆不存在或无权访问", "red"))
        return 1

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

    print(c("\n📄 记忆详情", "bold"))
    print("=" * 50)
    print(f"ID:       {entry.id}")
    print(f"分类:     [{entry.category}]")
    print(f"隐私:     {c(entry.privacy.value, privacy_color)}")
    print(f"层级:     {c(entry.layer.value, layer_color)}")
    print(f"重要性:   {entry.importance.value}")
    print(f"类型:     {entry.memory_type.value}")
    print(f"标签:     {', '.join(entry.tags) if entry.tags else '无'}")
    print(f"创建:     {format_time(entry.created_at)}")
    print(f"更新:     {format_time(entry.updated_at)}")
    print(f"访问:     {entry.access_count} 次")
    print(f"状态:     {star_mark + '已收藏' if entry.starred else '未收藏'}")
    print(f"\n内容:\n{entry.content}")

    if entry.metadata:
        print(f"\n元数据: {json.dumps(entry.metadata, ensure_ascii=False, indent=2)}")

    cm.close()
    return 0


def cmd_update(args):
    """更新记忆（v5.1.1 补全）"""
    cm = _get_memory(args)

    privacy = PrivacyLevel.from_string(args.privacy) if args.privacy else None
    layer = MemoryLayer.from_string(args.layer) if args.layer else None
    importance = Importance.from_string(args.importance) if args.importance else None

    starred = None
    if args.star:
        starred = True
    elif args.unstar:
        starred = False

    # 至少要更新一个字段
    if not any([args.content, args.category, args.tags, args.privacy,
                args.importance, args.layer, starred is not None]):
        print(c("⚠️  请至少指定一个要更新的字段", "yellow"))
        return 1

    success = cm.update(
        memory_id=args.id,
        content=args.content,
        category=args.category,
        tags=args.tags,
        privacy=privacy,
        importance=importance,
        layer=layer,
        starred=starred,
        actor=args.agent,
        session_id=args.session,
    )

    if success:
        print(c("\n✅ 记忆已更新", "green"))
    else:
        print(c("\n❌ 更新失败：记忆不存在", "red"))

    cm.close()
    return 0 if success else 1


def cmd_delete(args):
    """删除记忆（v5.1.1 补全）"""
    cm = _get_memory(args)

    entry = cm.get(args.id, actor=args.agent, session_id=args.session)
    if not entry:
        print(c("❌ 记忆不存在", "red"))
        return 1

    if not args.force:
        print(c(f"\n⚠️  将删除记忆：", "yellow"))
        print(f"   [{entry.category}] {entry.preview[:60]}...")
        print(c(f"\n确认删除？加 --force 执行（软删除，可在回收站恢复）", "yellow"))
        print(c(f"彻底删除请加 --hard", "yellow"))
        return 1

    success = cm.delete(
        args.id,
        actor=args.agent,
        session_id=args.session,
        hard_delete=args.hard,
    )

    if success:
        action = "彻底删除" if args.hard else "移到回收站"
        print(c(f"\n🗑️  已{action}", "green"))
    else:
        print(c("\n❌ 删除失败", "red"))

    cm.close()
    return 0 if success else 1


def cmd_audit(args):
    """审计日志（v5.1.1 补全）"""
    cm = _get_memory(args)

    logs = cm.audit_log(
        memory_id=args.id,
        actor=args.actor,
        limit=args.limit,
    )

    print(c("\n📋 审计日志", "bold"))
    print("=" * 50)
    print(f"共 {c(str(len(logs)), 'cyan')} 条记录")

    for log in logs:
        ts = format_time(log.timestamp)
        action = log.action or "unknown"
        mid = log.memory_id or "-"
        actor = log.actor or "-"
        detail = ""
        if log.details:
            if isinstance(log.details, dict):
                detail = log.details.get("message", "")
                if not detail:
                    detail = json.dumps(log.details, ensure_ascii=False)
            else:
                detail = str(log.details)
        print(f"\n[{ts}] {c(action.upper(), 'purple')}")
        print(f"   记忆ID: {mid[:16]}... | 操作者: {actor}")
        if detail:
            print(f"   详情: {detail}")

    cm.close()
    return 0


def cmd_recent(args):
    """最近添加的记忆（v5.1.1 新增）"""
    cm = _get_memory(args)

    now = datetime.now().timestamp()
    since = now - args.hours * 3600

    entries = cm.list(
        created_after=since,
        limit=args.limit,
        offset=args.offset,
    )

    print(f"\n最近 {c(str(args.hours), 'cyan')} 小时内添加的记忆"
          f"（共 {c(str(len(entries)), 'cyan')} 条）")

    for entry in entries:
        star_mark = "⭐ " if entry.starred else ""
        print(f"\n--- [{entry.category}] {star_mark}{entry.preview[:60]} ---")
        print(f"  层级: {entry.layer.value} | 重要性: {entry.importance.value}")
        print(f"  标签: {', '.join(entry.tags) if entry.tags else '无'}")
        print(f"  创建: {format_time(entry.created_at)}")

    cm.close()
    return 0


def cmd_trash(args):
    """查看回收站（v5.1.1 新增）"""
    cm = _get_memory(args)
    entries = cm.list(category="trash", limit=args.limit, offset=args.offset)

    print(f"\n🗑️  回收站（共 {c(str(len(entries)), 'cyan')} 条）")

    for entry in entries:
        original = entry.metadata.get("_original_category", "unknown")
        print(f"\n--- 原分类: [{original}] {entry.preview[:60]} ---")
        print(f"  ID: {entry.id}")
        print(f"  删除时间: {format_time(entry.updated_at)}")
        print(f"  标签: {', '.join(entry.tags) if entry.tags else '无'}")

    if not entries:
        print(c("回收站为空", "yellow"))

    cm.close()
    return 0


def cmd_restore(args):
    """从回收站恢复记忆（v5.1.1 新增）"""
    cm = _get_memory(args)

    success = cm.restore(
        args.id,
        actor=args.agent,
        session_id=args.session,
    )

    if success:
        print(c("\n♻️  记忆已恢复", "green"))
    else:
        print(c("\n❌ 恢复失败：记忆不存在或不在回收站", "red"))

    cm.close()
    return 0 if success else 1


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
        sort_by=args.sort,
        sort_order=args.order,
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

    if args.detailed:
        stats = cm.detailed_stats()
        print_banner()
        print(c("MindForge 详细统计报告", "bold"))
        print("=" * 50)
        print(f"总记忆数：        {c(str(stats.get('total', 0)), 'cyan')}")
        print(f"回收站：          {c(str(stats.get('trash', 0)), 'yellow')}")
        print(f"⭐ 收藏数：       {c(str(stats.get('starred', 0)), 'yellow')}")
        print(f"加密记忆数：      {c(str(stats.get('encrypted', 0)), 'purple')}")

        if stats.get("first_created"):
            print(f"\n创建时间范围：")
            print(f"  最早： {format_time(stats['first_created'])}")
            print(f"  最近： {format_time(stats['last_created'])}")

        print(f"\n📊 平均指标：")
        print(f"  平均访问次数：   {stats.get('avg_access_count', 0)}")
        print(f"  平均记忆强度：   {stats.get('avg_strength', 0)}")
        print(f"  平均遗忘分数：   {stats.get('avg_forgetting_score', 0)}")

        print(f"\n🔝 极值指标：")
        print(f"  最高访问次数：   {stats.get('max_access_count', 0)}")
        print(f"  最低记忆强度：   {stats.get('min_strength', 0)}")

        print(f"\n📂 按分类：")
        for cat, count in stats.get("by_category", {}).items():
            print(f"  {cat}: {count}")

        print(f"\n🧠 按层级：")
        for lay, count in stats.get("by_layer", {}).items():
            print(f"  {lay}: {count}")

        print(f"\n🔐 按隐私：")
        for pri, count in stats.get("by_privacy", {}).items():
            print(f"  {pri}: {count}")

        print(f"\n⭐ 按重要性：")
        for imp, count in stats.get("by_importance", {}).items():
            print(f"  {imp}: {count}")

        print(f"\n📋 审计记录数：   {stats.get('audit_records', 0)}")
    else:
        stats = cm.stats()
        print_banner()
        print(c("MindForge 统计报告", "bold"))
        print("=" * 50)
        print(f"总记忆数：  {c(str(stats['total']), 'cyan')}")
        print(f"⭐ 收藏数： {c(str(stats.get('starred_count', 0)), 'yellow')}")
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

        top_tags = stats.get("top_tags", {})
        if top_tags:
            print(f"\n标签统计（前10）：")
            for tag, count in list(top_tags.items())[:10]:
                print(f"  #{tag}: {count}")

    cm.close()
    return 0


def cmd_batch_delete(args):
    """批量删除记忆"""
    cm = _get_memory(args)

    created_after = None
    created_before = None
    if args.after:
        from datetime import datetime
        created_after = datetime.fromisoformat(args.after).timestamp()
    if args.before:
        from datetime import datetime
        created_before = datetime.fromisoformat(args.before).timestamp()

    starred = None
    if getattr(args, "starred", False):
        starred = True
    if getattr(args, "unstarred", False):
        starred = False

    if not args.force:
        preview = cm.list(
            category=args.category,
            layer=MemoryLayer.from_string(args.layer) if args.layer else None,
            starred=starred,
            created_after=created_after,
            created_before=created_before,
            limit=10,
        )
        print(c(f"\n⚠️  将删除 {len(preview)} 条记忆（预览前10条）：", "yellow"))
        for entry in preview:
            print(f"   - [{entry.category}] {entry.preview[:60]}...")
        print(c("\n确认删除？加 --force 执行", "yellow"))
        return 1

    count = cm.batch_delete(
        category=args.category,
        layer=MemoryLayer.from_string(args.layer) if args.layer else None,
        starred=starred,
        created_after=created_after,
        created_before=created_before,
        hard_delete=args.hard,
        actor=args.agent,
        session_id=args.session,
    )

    action = "彻底删除" if args.hard else "移到回收站"
    print(c(f"\n🗑️  已{action} {count} 条记忆", "green"))
    return 0


def cmd_tag_search(args):
    """按标签搜索记忆"""
    cm = _get_memory(args)
    entries = cm.search_by_tag(
        tag=args.tag,
        category=args.category,
        layer=MemoryLayer.from_string(args.layer) if args.layer else None,
        limit=args.limit,
        offset=args.offset,
    )

    print(f"\n找到 {c(str(len(entries)), 'cyan')} 条带标签 #{args.tag} 的记忆")

    for entry in entries:
        star_mark = "⭐ " if entry.starred else ""
        print(f"\n--- [{entry.category}] "
              f"{star_mark}{entry.preview[:60]} ---")
        print(f"  标签: {', '.join(entry.tags)}")
        print(f"  层级: {entry.layer.value} | 重要性: {entry.importance.value}")
        print(f"  创建: {format_time(entry.created_at)}")

    return 0


def cmd_deduplicate(args):
    """记忆去重（v5.0.4 新增）"""
    cm = _get_memory(args)

    actually_delete = args.execute

    print(c("正在扫描重复记忆...", "cyan"))
    if not actually_delete:
        result = cm.deduplicate(
            category=args.category,
            similarity_threshold=args.threshold,
            dry_run=True,
            actor=args.agent,
            session_id=args.session,
        )
        print(c(f"\n🔍 试运行结果（未实际删除）：", "yellow"))
    else:
        result = cm.deduplicate(
            category=args.category,
            similarity_threshold=args.threshold,
            dry_run=False,
            actor=args.agent,
            session_id=args.session,
        )
        print(c(f"\n🗑️  去重完成：", "green"))

    print(f"   发现重复组：{c(str(result['duplicates_found']), 'cyan')}")
    if not actually_delete:
        print(f"   将删除：    {c(str(result['would_remove']), 'yellow')} 条")
    else:
        print(f"   实际删除：  {c(str(result['removed']), 'green')} 条")

    if result["details"] and args.verbose:
        print(c("\n--- 详情 ---", "purple"))
        for i, d in enumerate(result["details"], 1):
            print(f"\n[{i}] 分类: {d['category']} | 相似度: {d['similarity']}")
            print(f"    保留: {d['keeper_preview'][:60]}")
            print(f"    删除: {d['loser_preview'][:60]}")

    if not actually_delete and result["would_remove"] > 0:
        print(c("\n确认无误后，加 --execute 执行实际删除", "yellow"))

    return 0


def cmd_export_md(args):
    """导出为 Markdown（v5.0.4 新增）"""
    cm = _get_memory(args)

    path = cm.export_as_markdown(
        output_path=args.output,
        category=args.category,
        layer=MemoryLayer.from_string(args.layer) if args.layer else None,
        starred_only=args.starred,
    )

    size = path.stat().st_size
    print(c("\n✅ Markdown 导出成功", "green"))
    print(f"   文件路径: {path}")
    print(f"   文件大小: {format_size(size)}")
    return 0


def cmd_health(args):
    """数据库健康检查（v5.0.5 新增）"""
    cm = _get_memory(args)
    print_banner()
    print(c("🩺 MindForge 健康检查", "bold"))
    print("=" * 50)

    result = cm.health_check()

    status = result["status"]
    status_color = {
        "healthy": "green",
        "warning": "yellow",
        "critical": "red",
    }.get(status, "reset")
    status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "🚨"}.get(status, "❓")

    print(f"\n总体状态：{status_icon} {c(status.upper(), status_color)}")
    print(f"完整性检查：{c(result['integrity_check'], 'green' if result['integrity_check'] == 'ok' else 'red')}")
    print(f"总记忆数：  {c(str(result['total_memories']), 'cyan')}")
    print(f"数据库大小：{format_size(result['db_size_bytes'])}")

    idx = result["indexes"]
    print(f"\n📊 索引状态：")
    print(f"   预期 {idx['expected']} 个，找到 {c(str(idx['found']), 'green' if idx['found'] == idx['expected'] else 'red')} 个")
    if idx["missing"]:
        print(f"   缺失：{', '.join(idx['missing'])}")

    print(f"\n📋 数据一致性：")
    print(f"   孤立 FTS 记录：    {c(str(result['fts_orphans']), 'yellow' if result['fts_orphans'] else 'green')}")
    print(f"   孤立审计日志：    {c(str(result['audit_orphans']), 'yellow' if result['audit_orphans'] else 'green')}")
    print(f"   加密不一致条目：  {c(str(result['encrypted_inconsistent']), 'red' if result['encrypted_inconsistent'] else 'green')}")

    print(f"\n💡 建议：")
    for rec in result["recommendations"]:
        print(f"   • {rec}")

    return 0 if status == "healthy" else (1 if status == "warning" else 2)


def cmd_summarize(args):
    """记忆摘要（v5.0.5 新增）"""
    cm = _get_memory(args)
    print_banner()
    print(c("📊 MindForge 记忆摘要", "bold"))
    print("=" * 50)

    result = cm.summarize(
        category=args.category,
        group_by=args.group_by,
    )

    print(f"\n总记忆数：{c(str(result['total']), 'cyan')}")

    print(f"\n📅 近期活动：")
    print(f"   最近 7 天： {c(str(result['recent_activity']['last_7d']), 'cyan')} 条")
    print(f"   最近 30 天：{c(str(result['recent_activity']['last_30d']), 'cyan')} 条")

    print(f"\n📂 按 {c(args.group_by, 'purple')} 分组：")
    for key, info in result["grouped"].items():
        print(f"\n  ▸ {c(key, 'cyan')} ({info['count']} 条)")
        print(f"    时间范围: {info['oldest'] or '-'} ~ {info['latest'] or '-'}")
        if info["samples"]:
            print(f"    样例：")
            for s in info["samples"][:2]:
                print(f"      • {s[:60]}{'...' if len(s) >= 60 else ''}")

    if result["top_tags"]:
        print(f"\n🏷️  热门标签：")
        for tag, count in result["top_tags"][:5]:
            print(f"   #{tag}: {count}")

    return 0


def cmd_vacuum(args):
    """重建 FTS 索引 + 数据库优化（v5.0.6 新增）"""
    cm = _get_memory(args)
    print_banner()
    print(c("🧹 MindForge FTS 索引重建", "bold"))
    print("=" * 50)

    # 重建前健康状态
    before = cm.health_check()
    print(f"\n重建前：孤立 FTS 记录 = {c(str(before['fts_orphans']), 'yellow' if before['fts_orphans'] else 'green')}")

    print(c("\n正在重建 FTS 索引...", "cyan"))
    result = cm.rebuild_fts()

    # 执行 VACUUM 回收空间（需在非事务模式下执行）
    try:
        conn = cm.storage._get_conn()
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.isolation_level = ""
        vacuum_ok = True
    except Exception:
        vacuum_ok = False

    # 重建后健康状态
    after = cm.health_check()
    print(c("\n✅ 重建完成", "green"))
    print(f"   已索引条目：{c(str(result['indexed']), 'cyan')}")
    print(f"   耗时：{result['duration_ms']} ms")
    print(f"   VACUUM：{'✅ 已执行' if vacuum_ok else '⚠️ 跳过'}")
    print(f"\n重建后：孤立 FTS 记录 = {c(str(after['fts_orphans']), 'green' if after['fts_orphans'] == 0 else 'yellow')}")
    print(f"总体状态：{after['status']}")
    cm.close()
    return 0


def cmd_purge_trash(args):
    """清空回收站（v5.0.6 新增）"""
    cm = _get_memory(args)

    # 先统计回收站数量
    trash_items = cm.list(category="trash", limit=100000)

    if not trash_items:
        print(c("回收站为空，无需清理", "yellow"))
        cm.close()
        return 0

    if not args.force:
        print(c(f"\n⚠️  回收站中有 {len(trash_items)} 条记忆将被永久删除", "yellow"))
        print(c("预览（前 10 条）：", "cyan"))
        for entry in trash_items[:10]:
            print(f"   - [{entry.category}] {entry.preview[:60]}")
        print(c("\n确认永久删除？加 --force 执行（此操作不可恢复）", "yellow"))
        cm.close()
        return 1

    count = cm.purge_trash(actor=args.agent, session_id=args.session)
    print(c(f"\n🗑️  已永久删除 {count} 条回收站记忆", "green"))
    cm.close()
    return 0


def cmd_analyze(args):
    """记忆深度分析（v5.0.8 新增）"""
    cm = _get_memory(args)
    print_banner()
    print(c("📊 MindForge 深度分析报告", "bold"))
    print("=" * 50)

    stats = cm.stats()

    print(f"\n📈 总体概览：")
    print(f"   总记忆数：        {c(str(stats['total']), 'cyan')}")
    print(f"   ⭐ 收藏数：       {c(str(stats.get('starred_count', 0)), 'yellow')}")
    print(f"   数据库大小：      {format_size(stats['db_size_bytes'])}")

    print(f"\n📅 创建时间分布（最近 7 天）：")
    recent_counts = {}
    now = datetime.now().timestamp()
    day = 24 * 3600
    for i in range(7):
        start = now - (i + 1) * day
        end = now - i * day
        cnt = len(cm.list(created_after=start, created_before=end, limit=99999))
        date_str = datetime.fromtimestamp(end).strftime("%m-%d")
        recent_counts[date_str] = cnt

    max_count = max(recent_counts.values()) if recent_counts else 1
    for date_str in reversed(list(recent_counts.keys())):
        cnt = recent_counts[date_str]
        bar = "█" * int(cnt / max_count * 20) if max_count > 0 else ""
        print(f"   {date_str}: {bar} {c(str(cnt), 'cyan')} 条")

    print(f"\n🔥 活跃度分析：")
    total_access = sum(e.access_count for e in cm.list(limit=99999))
    avg_access = total_access / stats['total'] if stats['total'] > 0 else 0
    print(f"   总访问次数：      {c(str(total_access), 'purple')}")
    print(f"   平均访问次数：    {avg_access:.2f}")

    hot_entries = sorted(cm.list(limit=100), key=lambda e: e.access_count, reverse=True)[:5]
    if hot_entries:
        print(f"\n   🔥 热门记忆 TOP5：")
        for i, e in enumerate(hot_entries, 1):
            print(f"      {i}. [{e.category}] {e.preview[:40]}... ({e.access_count} 次访问)")

    print(f"\n🏷️ 标签分析：")
    top_tags = stats.get("top_tags", {})
    if top_tags:
        tag_list = sorted(top_tags.items(), key=lambda x: x[1], reverse=True)[:10]
        for tag, count in tag_list:
            print(f"   #{tag}: {c(str(count), 'pink')}")

    return 0


def cmd_import_md(args):
    """从 Markdown 导入记忆（v5.0.8 新增）"""
    cm = _get_memory(args)

    input_path = Path(args.input)
    if not input_path.exists():
        print(c(f"❌ 文件不存在：{input_path}", "red"))
        return 1

    try:
        content = input_path.read_text(encoding='utf-8')
    except Exception as e:
        print(c(f"❌ 读取文件失败：{e}", "red"))
        return 1

    import re
    entries = []
    current_category = "default"
    current_tags = []

    sections = re.split(r'(#{1,2}\s+.+)', content)
    for i in range(0, len(sections), 2):
        text = sections[i].strip()
        if text:
            entries.append({
                'content': text,
                'category': current_category,
                'tags': current_tags,
            })
        if i + 1 < len(sections):
            header = sections[i + 1].strip()
            title = header.lstrip('#').strip()
            current_category = title
            current_tags = re.findall(r'(?:^|\s)#([a-zA-Z]\w*)', title)

    if not entries:
        print(c("⚠️  未找到可导入的内容", "yellow"))
        return 0

    if not args.force:
        print(c(f"\n🔍 将导入 {len(entries)} 条记忆：", "cyan"))
        for e in entries[:5]:
            print(f"   - [{e['category']}] {e['content'][:60]}...")
        if len(entries) > 5:
            print(f"   ... 还有 {len(entries) - 5} 条")
        print(c("\n确认导入？加 --force 执行", "yellow"))
        return 1

    imported = 0
    skipped = 0
    for entry in entries:
        try:
            cm.add(
                content=entry['content'],
                category=entry['category'],
                tags=entry['tags'],
                layer=MemoryLayer.from_string(args.layer) if args.layer else MemoryLayer.short_term,
            )
            imported += 1
        except Exception:
            skipped += 1

    print(c(f"\n✅ Markdown 导入完成", "green"))
    print(f"   成功导入：{c(str(imported), 'green')} 条")
    print(f"   导入失败：{c(str(skipped), 'yellow')} 条")
    cm.close()
    return 0


def cmd_migrate(args):
    """数据库迁移（v5.0.8 新增）"""
    cm = _get_memory(args)
    print_banner()
    print(c("🔄 MindForge 数据库迁移", "bold"))
    print("=" * 50)

    current_version = cm.storage.get_db_version()
    latest_version = cm.storage.get_latest_db_version()

    print(f"\n当前版本：{c(str(current_version), 'cyan')}")
    print(f"最新版本：{c(str(latest_version), 'green')}")

    if current_version >= latest_version:
        print(c("\n✅ 数据库已是最新版本，无需迁移", "green"))
        return 0

    if not args.force:
        print(c(f"\n⚠️  将执行从 v{current_version} 到 v{latest_version} 的迁移", "yellow"))
        print(c("确认迁移？加 --force 执行", "yellow"))
        return 1

    try:
        result = cm.storage.migrate_to_latest()
        print(c(f"\n✅ 迁移完成！", "green"))
        print(f"   迁移脚本：{result['scripts_applied']} 个")
        print(f"   耗时：{result['duration_ms']} ms")
        print(f"   当前版本：{result['final_version']}")
    except Exception as e:
        print(c(f"\n❌ 迁移失败：{e}", "red"))
        return 1

    return 0


def cmd_export_html(args):
    """导出记忆为 HTML（v5.0.9 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有可导出的记忆", "yellow"))
        return 0

    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MindForge 导出 - {count} 条记忆</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #00d4ff; font-size: 2rem; margin-bottom: 10px; }}
        .header p {{ color: #888; font-size: 0.9rem; }}
        .memory-card {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid rgba(0,212,255,0.1); }}
        .memory-card:hover {{ border-color: rgba(0,212,255,0.3); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .category {{ background: linear-gradient(135deg, #00d4ff, #7b2cbf); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; }}
        .layer {{ font-size: 0.7rem; color: #aaa; }}
        .card-content {{ color: #e0e0e0; line-height: 1.6; margin-bottom: 10px; }}
        .card-footer {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #666; }}
        .tags {{ display: flex; gap: 6px; }}
        .tag {{ background: rgba(123,44,191,0.3); color: #c792ea; padding: 2px 8px; border-radius: 10px; }}
        .footer {{ text-align: center; margin-top: 40px; color: #555; font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 MindForge 记忆导出</h1>
            <p>共 {count} 条记忆 · 导出时间：{export_time}</p>
        </div>
        {cards}
        <div class="footer">
            <p>Generated by MindForge v{__version__}</p>
        </div>
    </div>
</body>
</html>"""

    cards_html = ""
    for entry in entries:
        tags_html = "".join(f'<span class="tag">#{html.escape(str(t))}</span>' for t in entry.tags) if entry.tags else ""
        cards_html += f"""
<div class="memory-card">
    <div class="card-header">
        <span class="category">{html.escape(str(entry.category))}</span>
        <span class="layer">{html.escape(entry.layer.value)}</span>
    </div>
    <div class="card-content">{html.escape(entry.content)}</div>
    <div class="card-footer">
        <div class="tags">{tags_html}</div>
        <span>{format_time(entry.created_at)}</span>
    </div>
</div>"""

    export_time = format_time(time.time())
    html_content = html_template.format(count=len(entries), export_time=export_time, cards=cards_html, __version__=__version__)

    output_path = Path(args.output) if args.output else Path("memory_export.html")
    output_path.write_text(html_content, encoding='utf-8')

    print(c(f"✅ HTML 导出完成！", "green"))
    print(f"   文件：{output_path}")
    print(f"   记忆数：{len(entries)}")
    cm.close()
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
    evolution = _lazy_import("MemoryEvolution")(cm.storage)

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
    kg = _lazy_import("KnowledgeGraph")(storage=cm.storage)

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
    pe = _lazy_import("PersonalityEngine")(cm.storage)

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
    layer = MemoryLayer.from_string(args.layer) if args.layer else None

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
    target_layer = MemoryLayer.from_string(args.target_layer) if args.target_layer else None

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
    privacy_engine = _lazy_import("PrivacyEngine")(cm.storage)
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
    print(c("启动 MindForge Web UI...", "cyan"))
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
        prog="mindforge",
        description="MindForge v5.2.1 - AI Agent 终身记忆系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-v", action="version", version="MindForge v5.2.1")

    parser.add_argument("--db-path", default="./data/memory.db", help="数据库路径")
    parser.add_argument("--key-file", default="./data/.key", help="密钥文件路径")

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="初始化 MindForge")

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
    p_list.add_argument("--sort", "-s", default="created_at",
                        choices=["created_at", "updated_at", "last_accessed_at", "access_count", "strength", "forgetting_score"],
                        help="排序字段（v5.1.4 新增）")
    p_list.add_argument("--order", "-o", default="desc",
                        choices=["asc", "desc"],
                        help="排序顺序（v5.1.4 新增）")

    p_get = sub.add_parser("get", help="获取单条记忆（v5.1.1 补全）")
    p_get.add_argument("id", help="记忆 ID")
    p_get.add_argument("--agent", default="cli", help="Agent ID")
    p_get.add_argument("--session", default="cli", help="会话 ID")

    p_update = sub.add_parser("update", help="更新记忆（v5.1.1 补全）")
    p_update.add_argument("id", help="记忆 ID")
    p_update.add_argument("--content", help="新的记忆内容")
    p_update.add_argument("--category", "-c", help="新的分类")
    p_update.add_argument("--tags", "-t", nargs="+", help="新的标签")
    p_update.add_argument("--privacy", "-p",
                          choices=["PUBLIC", "INTERNAL", "PRIVATE", "STRICT"], help="隐私等级")
    p_update.add_argument("--importance", "-i",
                          choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], help="重要性")
    p_update.add_argument("--layer", "-l",
                          choices=["sensory", "short_term", "long_term", "permanent"],
                          help="记忆层级")
    p_update.add_argument("--star", action="store_true", help="设为收藏")
    p_update.add_argument("--unstar", action="store_true", help="取消收藏")
    p_update.add_argument("--agent", default="cli", help="Agent ID")
    p_update.add_argument("--session", default="cli", help="会话 ID")

    p_delete = sub.add_parser("delete", help="删除记忆（v5.1.1 补全）")
    p_delete.add_argument("id", help="记忆 ID")
    p_delete.add_argument("--hard", action="store_true", help="彻底删除（不可恢复）")
    p_delete.add_argument("--force", action="store_true", help="确认删除")
    p_delete.add_argument("--agent", default="cli", help="Agent ID")
    p_delete.add_argument("--session", default="cli", help="会话 ID")

    p_audit = sub.add_parser("audit", help="查看审计日志（v5.1.1 补全）")
    p_audit.add_argument("--id", help="限定记忆 ID")
    p_audit.add_argument("--actor", help="限定操作者")
    p_audit.add_argument("--limit", type=int, default=100, help="数量限制")

    p_recent = sub.add_parser("recent", help="最近添加的记忆（v5.1.1 新增）")
    p_recent.add_argument("--hours", type=int, default=24, help="最近 N 小时，默认 24")
    p_recent.add_argument("--limit", type=int, default=20, help="数量限制")
    p_recent.add_argument("--offset", type=int, default=0, help="偏移量")

    p_trash = sub.add_parser("trash", help="查看回收站（v5.1.1 新增）")
    p_trash.add_argument("--limit", type=int, default=50, help="数量限制")
    p_trash.add_argument("--offset", type=int, default=0, help="偏移量")

    p_restore = sub.add_parser("restore", help="从回收站恢复记忆（v5.1.1 新增）")
    p_restore.add_argument("id", help="记忆 ID")
    p_restore.add_argument("--agent", default="cli", help="Agent ID")
    p_restore.add_argument("--session", default="cli", help="会话 ID")

    p_stats = sub.add_parser("stats", help="统计信息")
    p_stats.add_argument("--detailed", action="store_true", help="显示详细统计（v5.1.4 新增）")

    p_star = sub.add_parser("star", help="收藏记忆")
    p_star.add_argument("id", help="记忆 ID")
    p_star.add_argument("--agent", default="cli", help="Agent ID")
    p_star.add_argument("--session", default="cli", help="会话 ID")

    p_unstar = sub.add_parser("unstar", help="取消收藏")
    p_unstar.add_argument("id", help="记忆 ID")
    p_unstar.add_argument("--agent", default="cli", help="Agent ID")
    p_unstar.add_argument("--session", default="cli", help="会话 ID")

    p_batch_delete = sub.add_parser("batch-delete", help="批量删除记忆")
    p_batch_delete.add_argument("--category", "-c", help="按分类删除")
    p_batch_delete.add_argument("--layer", "-l", help="按层级删除")
    p_batch_delete.add_argument("--starred", action="store_true", default=None,
                                help="只删除已收藏的")
    p_batch_delete.add_argument("--unstarred", action="store_true", default=None,
                                help="只删除未收藏的")
    p_batch_delete.add_argument("--after", help="删除此时间之后的")
    p_batch_delete.add_argument("--before", help="删除此时间之前的")
    p_batch_delete.add_argument("--hard", action="store_true", help="彻底删除（不可恢复）")
    p_batch_delete.add_argument("--force", action="store_true", help="确认删除（不加则只预览）")
    p_batch_delete.add_argument("--agent", default="cli", help="Agent ID")
    p_batch_delete.add_argument("--session", default="cli", help="会话 ID")

    p_tag_search = sub.add_parser("tag-search", help="按标签搜索记忆")
    p_tag_search.add_argument("tag", help="标签名称")
    p_tag_search.add_argument("--category", "-c", help="分类筛选")
    p_tag_search.add_argument("--layer", "-l", help="层级筛选")
    p_tag_search.add_argument("--limit", type=int, default=50, help="数量限制")
    p_tag_search.add_argument("--offset", type=int, default=0, help="偏移量")

    p_dedup = sub.add_parser("deduplicate", help="记忆去重（v5.0.4 新增）")
    p_dedup.add_argument("--category", "-c", help="限定分类")
    p_dedup.add_argument("--threshold", type=float, default=0.95,
                         help="相似度阈值 (0-1)，默认 0.95")
    p_dedup.add_argument("--execute", action="store_true",
                         help="实际执行删除（不加则默认试运行）")
    p_dedup.add_argument("--verbose", "-v", action="store_true",
                         help="显示详细信息")
    p_dedup.add_argument("--agent", default="cli", help="Agent ID")
    p_dedup.add_argument("--session", default="cli", help="会话 ID")

    p_export_md = sub.add_parser("export-md", help="导出为 Markdown（v5.0.4 新增）")
    p_export_md.add_argument("--output", "-o", default="./data/memory.md",
                             help="输出文件路径")
    p_export_md.add_argument("--category", "-c", help="按分类筛选")
    p_export_md.add_argument("--layer", "-l", help="按层级筛选")
    p_export_md.add_argument("--starred", action="store_true",
                             help="仅导出收藏的记忆")

    p_health = sub.add_parser("health", help="数据库健康检查（v5.0.5 新增）")

    p_summarize = sub.add_parser("summarize", help="记忆摘要（v5.0.5 新增）")
    p_summarize.add_argument("--category", "-c", help="限定分类")
    p_summarize.add_argument("--group-by", "-g", default="category",
                             choices=["category", "layer", "importance", "privacy"],
                             help="分组维度（默认 category）")

    p_vacuum = sub.add_parser("vacuum", help="重建 FTS 索引 + 数据库优化（v5.0.6 新增）")

    p_purge_trash = sub.add_parser("purge-trash", help="清空回收站（v5.0.6 新增）")
    p_purge_trash.add_argument("--force", action="store_true",
                               help="确认永久删除（不加则只预览）")
    p_purge_trash.add_argument("--agent", default="cli", help="Agent ID")
    p_purge_trash.add_argument("--session", default="cli", help="会话 ID")

    p_analyze = sub.add_parser("analyze", help="记忆深度分析（v5.0.8 新增）")

    p_import_md = sub.add_parser("import-md", help="从 Markdown 导入记忆（v5.0.8 新增）")
    p_import_md.add_argument("input", help="Markdown 文件路径")
    p_import_md.add_argument("--layer", "-l", default="short_term",
                             choices=["sensory", "short_term", "long_term", "permanent"],
                             help="目标记忆层级")
    p_import_md.add_argument("--force", action="store_true",
                             help="确认导入（不加则只预览）")

    p_migrate = sub.add_parser("migrate", help="数据库迁移（v5.0.8 新增）")
    p_migrate.add_argument("--force", action="store_true",
                           help="确认迁移（不加则只预览）")

    p_export_html = sub.add_parser("export-html", help="导出记忆为 HTML（v5.0.9 新增）")
    p_export_html.add_argument("--output", "-o", default="memory_export.html",
                               help="输出文件路径")

    p_export_xml = sub.add_parser("export-xml", help="导出记忆为 XML（v5.1.4 新增）")
    p_export_xml.add_argument("--output", "-o", default="./data/memory_export.xml",
                              help="输出文件路径")

    p_import_xml = sub.add_parser("import-xml", help="从 XML 导入记忆（v5.1.4 新增）")
    p_import_xml.add_argument("input", help="XML 文件路径")
    p_import_xml.add_argument("--force", action="store_true", help="强制导入（覆盖重复）")

    p_export_json = sub.add_parser("export-json", help="导出记忆为 JSON（v5.1.5 新增）")
    p_export_json.add_argument("--output", "-o", default="./data/memory_export.json",
                               help="输出文件路径")
    p_export_json.add_argument("--pretty", action="store_true", help="格式化输出")

    p_import_json = sub.add_parser("import-json", help="从 JSON 导入记忆（v5.1.5 新增）")
    p_import_json.add_argument("input", help="JSON 文件路径")
    p_import_json.add_argument("--force", action="store_true", help="强制导入（覆盖重复）")

    p_merge = sub.add_parser("merge", help="合并重复记忆（v5.1.5 新增）")
    p_merge.add_argument("--threshold", type=float, default=0.8, help="相似度阈值")
    p_merge.add_argument("--dry-run", action="store_true", help="仅预览，不执行")

    p_remind = sub.add_parser("remind", help="遗忘提醒（v5.1.5 新增）")
    p_remind.add_argument("--count", type=int, default=10, help="提醒数量")
    p_remind.add_argument("--threshold", type=float, default=0.5, help="遗忘分数阈值")

    p_tags = sub.add_parser("tags", help="标签管理（v5.1.6 新增）")
    p_tags.add_argument("--list", action="store_true", help="列出所有标签")
    p_tags.add_argument("--top", type=int, default=20, help="显示前 N 个标签")

    p_cats = sub.add_parser("cats", help="分类统计（v5.1.6 新增）")
    p_cats.add_argument("--top", type=int, default=20, help="显示前 N 个分类")

    p_timeline = sub.add_parser("timeline", help="时间线视图（v5.1.6 新增）")
    p_timeline.add_argument("--days", type=int, default=30, help="查看最近 N 天")
    p_timeline.add_argument("--category", help="按分类筛选")

    p_top = sub.add_parser("top", help="热门记忆（v5.1.6 新增）")
    p_top.add_argument("--count", type=int, default=10, help="显示数量")
    p_top.add_argument("--by", default="access_count", choices=["access_count", "strength", "created_at"],
                       help="排序依据")

    p_random = sub.add_parser("random", help="随机闪卡复习（v5.1.7 新增）")
    p_random.add_argument("--count", "-n", type=int, default=1, help="随机记忆数量")
    p_random.add_argument("--category", "-c", help="按分类筛选")

    p_rename_tag = sub.add_parser("rename-tag", help="重命名标签（v5.1.7 新增）")
    p_rename_tag.add_argument("old", help="旧标签名")
    p_rename_tag.add_argument("new", help="新标签名")
    p_rename_tag.add_argument("--force", "-f", action="store_true", help="强制确认")

    p_rename_cat = sub.add_parser("rename-cat", help="重命名分类（v5.1.7 新增）")
    p_rename_cat.add_argument("old", help="旧分类名")
    p_rename_cat.add_argument("new", help="新分类名")
    p_rename_cat.add_argument("--force", "-f", action="store_true", help="强制确认")

    p_config = sub.add_parser("config", help="查看配置（v5.1.7 新增）")

    p_doctor = sub.add_parser("doctor", help="全面诊断数据库（v5.1.8 新增）")
    p_doctor.add_argument("--fix", action="store_true", help="自动修复可修复的问题")

    p_find = sub.add_parser("find", help="高级查找记忆（v5.1.8 新增）")
    p_find.add_argument("--category", "-c", help="按分类筛选")
    p_find.add_argument("--layer", "-l", help="按层级筛选")
    p_find.add_argument("--tags", nargs="+", help="按标签筛选（支持多个）")
    p_find.add_argument("--keyword", "-k", help="关键词搜索")
    p_find.add_argument("--starred", action="store_true", help="仅收藏")
    p_find.add_argument("--after", type=float, help="起始时间戳")
    p_find.add_argument("--before", type=float, help="截止时间戳")
    p_find.add_argument("--limit", "-n", type=int, help="结果数量限制")

    p_export_excel = sub.add_parser("export-excel", help="导出记忆为 Excel（v5.1.9 新增）")
    p_export_excel.add_argument("--output", "-o", default="./data/memory_export.xlsx",
                                help="输出文件路径")
    p_export_excel.add_argument("--category", "-c", help="按分类筛选")
    p_export_excel.add_argument("--layer", "-l", help="按层级筛选")
    p_export_excel.add_argument("--starred", action="store_true", help="仅导出收藏的记忆")

    p_import_excel = sub.add_parser("import-excel", help="从 Excel 导入记忆（v5.1.9 新增）")
    p_import_excel.add_argument("input", help="Excel 文件路径")
    p_import_excel.add_argument("--category", "-c", help="目标分类（覆盖文件中的分类）")
    p_import_excel.add_argument("--layer", "-l", default="short_term",
                                choices=["sensory", "short_term", "long_term", "permanent"],
                                help="目标记忆层级")
    p_import_excel.add_argument("--force", action="store_true", help="强制导入（覆盖重复）")

    p_copy = sub.add_parser("copy", help="复制记忆到新分类（v5.1.9 新增）")
    p_copy.add_argument("id", help="记忆 ID")
    p_copy.add_argument("category", help="目标分类")
    p_copy.add_argument("--agent", default="cli", help="Agent ID")
    p_copy.add_argument("--session", default="cli", help="会话 ID")

    p_move = sub.add_parser("move", help="移动记忆到新分类（v5.1.9 新增）")
    p_move.add_argument("id", help="记忆 ID")
    p_move.add_argument("category", help="目标分类")
    p_move.add_argument("--agent", default="cli", help="Agent ID")
    p_move.add_argument("--session", default="cli", help="会话 ID")

    # ===== v5.2.0 新增命令 =====

    p_fuzzy_search = sub.add_parser("fuzzy-search", help="模糊搜索记忆（v5.2.0 新增）")
    p_fuzzy_search.add_argument("query", help="搜索关键词")
    p_fuzzy_search.add_argument("--category", "-c", help="按分类筛选")
    p_fuzzy_search.add_argument("--layer", "-l", help="按层级筛选")
    p_fuzzy_search.add_argument("--limit", "-n", type=int, default=20, help="结果数量限制")
    p_fuzzy_search.add_argument("--threshold", "-t", type=float, default=0.3, help="相似度阈值")
    p_fuzzy_search.add_argument("--highlight", action="store_true", help="高亮显示匹配词")

    p_search_history = sub.add_parser("search-history", help="查看搜索历史（v5.2.0 新增）")
    p_search_history.add_argument("--limit", "-n", type=int, default=20, help="显示数量")

    p_batch_add_tags = sub.add_parser("batch-add-tags", help="批量添加标签（v5.2.0 新增）")
    p_batch_add_tags.add_argument("--ids", help="记忆 ID 列表，逗号分隔")
    p_batch_add_tags.add_argument("--tags", required=True, help="标签列表，逗号分隔")
    p_batch_add_tags.add_argument("--category", "-c", help="按分类批量添加（替代 --ids）")
    p_batch_add_tags.add_argument("--agent", default="cli", help="Agent ID")
    p_batch_add_tags.add_argument("--session", default="cli", help="会话 ID")

    p_batch_remove_tags = sub.add_parser("batch-remove-tags", help="批量移除标签（v5.2.0 新增）")
    p_batch_remove_tags.add_argument("--ids", help="记忆 ID 列表，逗号分隔")
    p_batch_remove_tags.add_argument("--tags", required=True, help="标签列表，逗号分隔")
    p_batch_remove_tags.add_argument("--agent", default="cli", help="Agent ID")
    p_batch_remove_tags.add_argument("--session", default="cli", help="会话 ID")

    p_merge_tags = sub.add_parser("merge-tags", help="合并标签（v5.2.0 新增）")
    p_merge_tags.add_argument("--source", required=True, help="源标签列表，逗号分隔")
    p_merge_tags.add_argument("--target", required=True, help="目标标签名")
    p_merge_tags.add_argument("--force", action="store_true", help="跳过确认")
    p_merge_tags.add_argument("--agent", default="cli", help="Agent ID")
    p_merge_tags.add_argument("--session", default="cli", help="会话 ID")

    p_db_backup = sub.add_parser("db-backup", help="创建数据库备份（v5.2.0 新增）")
    p_db_backup.add_argument("--dir", default="./data/backups", help="备份目录")

    p_db_backups = sub.add_parser("db-backups", help="列出备份文件（v5.2.0 新增）")
    p_db_backups.add_argument("--dir", default="./data/backups", help="备份目录")

    p_db_restore = sub.add_parser("db-restore", help="从备份恢复（v5.2.0 新增）")
    p_db_restore.add_argument("backup", help="备份文件路径")
    p_db_restore.add_argument("--no-pre-backup", action="store_true", help="恢复前不先备份当前数据")
    p_db_restore.add_argument("--force", action="store_true", help="跳过确认")

    p_db_clean_backups = sub.add_parser("db-clean-backups", help="清理旧备份（v5.2.0 新增）")
    p_db_clean_backups.add_argument("--dir", default="./data/backups", help="备份目录")
    p_db_clean_backups.add_argument("--keep", type=int, default=10, help="保留数量")
    p_db_clean_backups.add_argument("--force", action="store_true", help="跳过确认")

    # ===== AI 短剧记忆模块（v5.2.1 新增）=====

    p_drama_add = sub.add_parser("drama-add", help="添加短剧（v5.2.1 新增）")
    p_drama_add.add_argument("title", help="短剧标题")
    p_drama_add.add_argument("--genre", "-g", default="other",
                             choices=["romance", "suspense", "comedy", "action", "horror", "scifi", "fantasy", "drama", "other"],
                             help="短剧类型")
    p_drama_add.add_argument("--episodes", "-e", type=int, default=0, help="总集数")
    p_drama_add.add_argument("--status", "-s", default="planned",
                             choices=["watching", "completed", "planned", "dropped"],
                             help="观看状态")
    p_drama_add.add_argument("--platform", default="", help="播放平台")
    p_drama_add.add_argument("--rating", type=float, default=0.0, help="评分 (0-10)")
    p_drama_add.add_argument("--description", "-d", default="", help="简介")
    p_drama_add.add_argument("--tags", "-t", nargs="+", help="标签")
    p_drama_add.add_argument("--cover", default="", help="封面 URL")

    p_drama_list = sub.add_parser("drama-list", help="列出短剧（v5.2.1 新增）")
    p_drama_list.add_argument("--genre", "-g", help="按类型筛选")
    p_drama_list.add_argument("--status", "-s", help="按状态筛选")
    p_drama_list.add_argument("--platform", help="按平台筛选")
    p_drama_list.add_argument("--min-rating", type=float, default=0.0, help="最低评分")
    p_drama_list.add_argument("--limit", type=int, default=50, help="数量限制")
    p_drama_list.add_argument("--offset", type=int, default=0, help="偏移量")
    p_drama_list.add_argument("--sort", default="updated_at",
                              choices=["created_at", "updated_at", "rating", "last_watched_at", "title"],
                              help="排序字段")
    p_drama_list.add_argument("--order", default="desc", choices=["asc", "desc"], help="排序顺序")

    p_drama_get = sub.add_parser("drama-get", help="获取短剧详情（v5.2.1 新增）")
    p_drama_get.add_argument("id", help="短剧 ID")

    p_drama_update = sub.add_parser("drama-update", help="更新短剧（v5.2.1 新增）")
    p_drama_update.add_argument("id", help="短剧 ID")
    p_drama_update.add_argument("--title", help="新标题")
    p_drama_update.add_argument("--genre", "-g",
                                choices=["romance", "suspense", "comedy", "action", "horror", "scifi", "fantasy", "drama", "other"],
                                help="新类型")
    p_drama_update.add_argument("--episodes", "-e", type=int, help="总集数")
    p_drama_update.add_argument("--current", type=int, help="当前看到第几集")
    p_drama_update.add_argument("--status", "-s",
                                choices=["watching", "completed", "planned", "dropped"],
                                help="观看状态")
    p_drama_update.add_argument("--platform", help="播放平台")
    p_drama_update.add_argument("--rating", type=float, help="评分")
    p_drama_update.add_argument("--description", "-d", help="简介")
    p_drama_update.add_argument("--tags", "-t", nargs="+", help="标签")
    p_drama_update.add_argument("--cover", help="封面 URL")
    p_drama_update.add_argument("--watched", action="store_true", help="标记为刚看过（更新观看时间）")

    p_drama_delete = sub.add_parser("drama-delete", help="删除短剧（v5.2.1 新增）")
    p_drama_delete.add_argument("id", help="短剧 ID")
    p_drama_delete.add_argument("--force", action="store_true", help="确认删除")

    p_drama_stats = sub.add_parser("drama-stats", help="短剧统计（v5.2.1 新增）")

    # 台词相关
    p_line_add = sub.add_parser("line-add", help="添加短剧台词（v5.2.1 新增）")
    p_line_add.add_argument("drama_id", help="短剧 ID")
    p_line_add.add_argument("line", help="台词内容")
    p_line_add.add_argument("--character", "-c", default="", help="角色名")
    p_line_add.add_argument("--char-id", default="", help="角色 ID")
    p_line_add.add_argument("--scene-id", default="", help="场次 ID")
    p_line_add.add_argument("--context", default="", help="上下文")
    p_line_add.add_argument("--episode", "-e", type=int, default=0, help="集数")
    p_line_add.add_argument("--timestamp", default="", help="时间戳")
    p_line_add.add_argument("--classic", action="store_true", help="标记为经典台词")
    p_line_add.add_argument("--tags", "-t", nargs="+", help="标签")

    p_line_list = sub.add_parser("line-list", help="列出短剧台词（v5.2.1 新增）")
    p_line_list.add_argument("--drama-id", help="短剧 ID")
    p_line_list.add_argument("--scene-id", help="场次 ID")
    p_line_list.add_argument("--char-id", help="角色 ID")
    p_line_list.add_argument("--classic", action="store_true", default=None, help="仅经典台词")
    p_line_list.add_argument("--episode", type=int, help="集数")
    p_line_list.add_argument("--limit", type=int, default=100, help="数量限制")
    p_line_list.add_argument("--offset", type=int, default=0, help="偏移量")

    p_line_search = sub.add_parser("line-search", help="搜索台词（v5.2.1 新增）")
    p_line_search.add_argument("query", help="搜索关键词")
    p_line_search.add_argument("--drama-id", help="限定短剧 ID")
    p_line_search.add_argument("--classic-only", action="store_true", help="仅搜索经典台词")
    p_line_search.add_argument("--limit", type=int, default=20, help="数量限制")

    p_line_classic = sub.add_parser("line-classic", help="经典台词（v5.2.1 新增）")
    p_line_classic.add_argument("--drama-id", help="限定短剧 ID")
    p_line_classic.add_argument("--limit", type=int, default=20, help="数量限制")

    p_line_update = sub.add_parser("line-update", help="更新台词（v5.2.1 新增）")
    p_line_update.add_argument("id", help="台词 ID")
    p_line_update.add_argument("--line", help="新台词内容")
    p_line_update.add_argument("--character", help="新角色名")
    p_line_update.add_argument("--context", help="新上下文")
    p_line_update.add_argument("--classic", action="store_true", default=None, help="标记为经典")
    p_line_update.add_argument("--tags", "-t", nargs="+", help="新标签")

    p_line_delete = sub.add_parser("line-delete", help="删除台词（v5.2.1 新增）")
    p_line_delete.add_argument("id", help="台词 ID")
    p_line_delete.add_argument("--force", action="store_true", help="确认删除")

    # 角色相关
    p_char_add = sub.add_parser("char-add", help="添加短剧角色（v5.2.1 新增）")
    p_char_add.add_argument("drama_id", help="短剧 ID")
    p_char_add.add_argument("name", help="角色名")
    p_char_add.add_argument("--role", default="supporting",
                            choices=["lead", "supporting", "guest", "villain", "mentor"],
                            help="角色定位")
    p_char_add.add_argument("--actor", default="", help="演员名")
    p_char_add.add_argument("--description", "-d", default="", help="角色描述")
    p_char_add.add_argument("--personality", "-p", default="", help="性格特点")
    p_char_add.add_argument("--avatar", default="", help="头像 URL")
    p_char_add.add_argument("--tags", "-t", nargs="+", help="标签")

    p_char_list = sub.add_parser("char-list", help="列出短剧角色（v5.2.1 新增）")
    p_char_list.add_argument("--drama-id", help="短剧 ID")
    p_char_list.add_argument("--role", help="按角色定位筛选")
    p_char_list.add_argument("--limit", type=int, default=100, help="数量限制")
    p_char_list.add_argument("--offset", type=int, default=0, help="偏移量")

    p_char_get = sub.add_parser("char-get", help="获取角色详情（v5.2.1 新增）")
    p_char_get.add_argument("id", help="角色 ID")

    p_char_update = sub.add_parser("char-update", help="更新角色（v5.2.1 新增）")
    p_char_update.add_argument("id", help="角色 ID")
    p_char_update.add_argument("--name", help="新角色名")
    p_char_update.add_argument("--role",
                               choices=["lead", "supporting", "guest", "villain", "mentor"],
                               help="新角色定位")
    p_char_update.add_argument("--actor", help="新演员名")
    p_char_update.add_argument("--description", "-d", help="新描述")
    p_char_update.add_argument("--personality", "-p", help="新性格")
    p_char_update.add_argument("--avatar", help="新头像 URL")
    p_char_update.add_argument("--tags", "-t", nargs="+", help="新标签")

    p_char_delete = sub.add_parser("char-delete", help="删除角色（v5.2.1 新增）")
    p_char_delete.add_argument("id", help="角色 ID")
    p_char_delete.add_argument("--force", action="store_true", help="确认删除")

    # 场次相关
    p_scene_add = sub.add_parser("scene-add", help="添加短剧场次（v5.2.1 新增）")
    p_scene_add.add_argument("drama_id", help="短剧 ID")
    p_scene_add.add_argument("episode", type=int, help="集数")
    p_scene_add.add_argument("scene_number", type=int, help="场次号")
    p_scene_add.add_argument("title", help="场次标题")
    p_scene_add.add_argument("--content", "-c", default="", help="场次内容")
    p_scene_add.add_argument("--location", "-l", default="", help="地点")
    p_scene_add.add_argument("--time", default="", help="时间（日/夜）")
    p_scene_add.add_argument("--tags", "-t", nargs="+", help="标签")

    p_scene_list = sub.add_parser("scene-list", help="列出短剧场次（v5.2.1 新增）")
    p_scene_list.add_argument("--drama-id", help="短剧 ID")
    p_scene_list.add_argument("--episode", type=int, help="按集数筛选")
    p_scene_list.add_argument("--limit", type=int, default=100, help="数量限制")
    p_scene_list.add_argument("--offset", type=int, default=0, help="偏移量")

    p_scene_get = sub.add_parser("scene-get", help="获取场次详情（v5.2.1 新增）")
    p_scene_get.add_argument("id", help="场次 ID")

    p_scene_update = sub.add_parser("scene-update", help="更新场次（v5.2.1 新增）")
    p_scene_update.add_argument("id", help="场次 ID")
    p_scene_update.add_argument("--title", help="新标题")
    p_scene_update.add_argument("--content", "-c", help="新内容")
    p_scene_update.add_argument("--location", "-l", help="新地点")
    p_scene_update.add_argument("--time", help="新时间")
    p_scene_update.add_argument("--tags", "-t", nargs="+", help="新标签")

    p_scene_delete = sub.add_parser("scene-delete", help="删除场次（v5.2.1 新增）")
    p_scene_delete.add_argument("id", help="场次 ID")
    p_scene_delete.add_argument("--force", action="store_true", help="确认删除")

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

    p_cleanup = sub.add_parser("cleanup", help="清理过期记忆（v5.1.3 新增）")
    p_cleanup.add_argument("--hours", type=int, default=24, help="超过 N 小时的记忆将被清理，默认 24")
    p_cleanup.add_argument("--layer", "-l", default="sensory",
                           choices=["sensory", "short_term", "long_term", "permanent"],
                           help="要清理的记忆层级，默认 sensory")

    p_batch_add = sub.add_parser("batch-add", help="从文件批量添加记忆（v5.1.3 新增）")
    p_batch_add.add_argument("input", help="输入 JSON 文件路径")

    p_import_url = sub.add_parser("import-url", help="从 URL 导入网页内容（v5.1.3 新增）")
    p_import_url.add_argument("url", help="要导入的网页 URL")
    p_import_url.add_argument("--category", "-c", default="web", help="分类")
    p_import_url.add_argument("--tags", "-t", nargs="+", help="标签")
    p_import_url.add_argument("--layer", "-l", default="short_term",
                              choices=["sensory", "short_term", "long_term", "permanent"],
                              help="记忆层级")

    p_similar = sub.add_parser("similar", help="查找相似记忆（v5.1.3 新增）")
    p_similar.add_argument("content", help="参考内容")
    p_similar.add_argument("--limit", type=int, default=5, help="返回数量限制")
    p_similar.add_argument("--threshold", type=float, default=0.3,
                           help="相似度阈值 (0-1)，默认 0.3")

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
        "star": cmd_star,
        "unstar": cmd_unstar,
        "batch-delete": cmd_batch_delete,
        "tag-search": cmd_tag_search,
        "deduplicate": cmd_deduplicate,
        "export-md": cmd_export_md,
        "health": cmd_health,
        "summarize": cmd_summarize,
        "vacuum": cmd_vacuum,
        "purge-trash": cmd_purge_trash,
        "analyze": cmd_analyze,
        "import-md": cmd_import_md,
        "migrate": cmd_migrate,
        "export-html": cmd_export_html,
        "export-xml": cmd_export_xml,
        "import-xml": cmd_import_xml,
        "export-json": cmd_export_json,
        "import-json": cmd_import_json,
        "merge": cmd_merge,
        "remind": cmd_remind,
        "tags": cmd_tags,
        "cats": cmd_cats,
        "timeline": cmd_timeline,
        "top": cmd_top,
        "random": cmd_random,
        "rename-tag": cmd_rename_tag,
        "rename-cat": cmd_rename_cat,
        "config": cmd_config,
        "doctor": cmd_doctor,
        "find": cmd_find,
        "audit": cmd_audit,
        "recent": cmd_recent,
        "trash": cmd_trash,
        "restore": cmd_restore,
        "consolidate": cmd_consolidate,
        "graph": cmd_graph,
        "personality": cmd_personality,
        "backup": cmd_backup,
        "export": cmd_export,
        "import": cmd_import,
        "compliance": cmd_compliance,
        "serve": cmd_serve,
        "cleanup": cmd_cleanup,
        "batch-add": cmd_batch_add,
        "import-url": cmd_import_url,
        "similar": cmd_similar,
        "export-excel": cmd_export_excel,
        "import-excel": cmd_import_excel,
        "copy": cmd_copy,
        "move": cmd_move,
        "fuzzy-search": cmd_fuzzy_search,
        "search-history": cmd_search_history,
        "batch-add-tags": cmd_batch_add_tags,
        "batch-remove-tags": cmd_batch_remove_tags,
        "merge-tags": cmd_merge_tags,
        "db-backup": cmd_db_backup,
        "db-backups": cmd_db_backups,
        "db-restore": cmd_db_restore,
        "db-clean-backups": cmd_db_clean_backups,
        # AI 短剧记忆模块（v5.2.1 新增）
        "drama-add": cmd_drama_add,
        "drama-list": cmd_drama_list,
        "drama-get": cmd_drama_get,
        "drama-update": cmd_drama_update,
        "drama-delete": cmd_drama_delete,
        "drama-stats": cmd_drama_stats,
        "line-add": cmd_line_add,
        "line-list": cmd_line_list,
        "line-search": cmd_line_search,
        "line-classic": cmd_line_classic,
        "line-update": cmd_line_update,
        "line-delete": cmd_line_delete,
        "char-add": cmd_char_add,
        "char-list": cmd_char_list,
        "char-get": cmd_char_get,
        "char-update": cmd_char_update,
        "char-delete": cmd_char_delete,
        "scene-add": cmd_scene_add,
        "scene-list": cmd_scene_list,
        "scene-get": cmd_scene_get,
        "scene-update": cmd_scene_update,
        "scene-delete": cmd_scene_delete,
    }

    cmd = commands.get(args.command)
    if cmd:
        sys.exit(cmd(args) or 0)
    else:
        parser.print_help()
        sys.exit(1)


def cmd_cleanup(args):
    """清理过期记忆（v5.1.3 新增）"""
    cm = _get_memory(args)

    count = cm.cleanup(max_age_hours=args.hours, layer=args.layer)

    print(c(f"\n✅ 清理完成", "green"))
    print(f"   清理了 {count} 条过期记忆（层级: {args.layer}, 超过 {args.hours} 小时）")

    cm.close()
    return 0


def cmd_batch_add(args):
    """从文件批量添加记忆（v5.1.3 新增）"""
    cm = _get_memory(args)
    input_path = Path(args.input)

    if not input_path.exists():
        print(c(f"\n❌ 文件不存在: {input_path}", "red"))
        return 1

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(c(f"\n❌ JSON 解析失败", "red"))
        return 1

    entries = data.get("memories", data)
    if not isinstance(entries, list):
        print(c(f"\n❌ 数据格式错误：必须是 memories 列表", "red"))
        return 1

    count = cm.batch_add(entries)
    print(c(f"\n✅ 批量添加完成", "green"))
    print(f"   成功添加 {count} 条记忆（共 {len(entries)} 条）")

    cm.close()
    return 0


def cmd_import_url(args):
    """从 URL 导入网页内容（v5.1.3 新增）"""
    cm = _get_memory(args)

    try:
        import urllib.request
        import re
        from urllib.parse import urlparse

        parsed = urlparse(args.url)
        if parsed.scheme not in ("http", "https"):
            print(c("❌ 仅支持 http/https 协议", "red"))
            cm.close()
            return 1
        if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or \
           parsed.hostname.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                                        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                                        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                                        "172.30.", "172.31.", "192.168.", "169.254.")):
            print(c("❌ 不支持访问内网/元数据地址", "red"))
            cm.close()
            return 1

        with urllib.request.urlopen(args.url, timeout=10) as response:
            content = response.read(5 * 1024 * 1024).decode("utf-8", errors="ignore")

        title_match = re.search(r"<title>([^<]+)</title>", content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "网页内容"

        text_content = re.sub(r"<[^>]+>", "\n", content)
        text_content = re.sub(r"\s+", " ", text_content).strip()[:5000]

        entry = cm.add(
            content=text_content,
            category=args.category or "web",
            tags=args.tags or ["url", "imported"],
            layer=MemoryLayer.from_string(args.layer),
        )

        print(c(f"\n✅ URL 导入完成", "green"))
        print(f"   标题: {title}")
        print(f"   内容: {text_content[:100]}...")
        print(f"   ID: {entry.id[:16]}...")

    except Exception as e:
        print(c(f"\n❌ 导入失败: {e}", "red"))
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_similar(args):
    """查找相似记忆（v5.1.3 新增）"""
    cm = _get_memory(args)

    results = cm.find_similar(
        content=args.content,
        limit=args.limit,
        threshold=args.threshold,
    )

    if not results:
        print(c("\n⚠️  未找到相似记忆", "yellow"))
        cm.close()
        return 0

    print(c(f"\n找到 {len(results)} 条相似记忆:", "cyan"))
    for i, entry in enumerate(results, 1):
        print(f"\n{i}. ID: {entry.id[:16]}...")
        print(f"   分类: {entry.category}")
        print(f"   内容: {entry.content[:150]}...")

    cm.close()
    return 0


def cmd_export_xml(args):
    """导出记忆为 XML（v5.1.4 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有可导出的记忆", "yellow"))
        return 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<mindforge>
    <version>{version}</version>
    <export_time>{export_time}</export_time>
    <total>{total}</total>
    <memories>
{memories}
    </memories>
</mindforge>"""

    memories_xml = ""
    for entry in entries:
        tags_xml = "".join(f"<tag>{xml_escape(str(t))}</tag>" for t in entry.tags) if entry.tags else ""
        memories_xml += f"""        <memory>
            <id>{xml_escape(str(entry.id))}</id>
            <content>{xml_escape(entry.content)}</content>
            <category>{xml_escape(str(entry.category))}</category>
            <tags>{tags_xml}</tags>
            <privacy>{entry.privacy.value}</privacy>
            <importance>{entry.importance.value}</importance>
            <memory_type>{entry.memory_type.value}</memory_type>
            <layer>{entry.layer.value}</layer>
            <access_count>{entry.access_count}</access_count>
            <created_at>{entry.created_at}</created_at>
            <updated_at>{entry.updated_at}</updated_at>
            <starred>{'true' if entry.starred else 'false'}</starred>
        </memory>
"""

    export_time = format_time(time.time())
    final_xml = xml_content.format(version=__version__, export_time=export_time, total=len(entries), memories=memories_xml)

    output_path.write_text(final_xml, encoding='utf-8')

    print(c(f"\n✅ XML 导出完成！", "green"))
    print(f"   文件：{output_path}")
    print(f"   记忆数：{len(entries)}")
    cm.close()
    return 0


def cmd_import_xml(args):
    """从 XML 导入记忆（v5.1.4 新增）"""
    cm = _get_memory(args)
    input_path = Path(args.input)

    if not input_path.exists():
        print(c(f"\n❌ 文件不存在: {input_path}", "red"))
        return 1

    try:
        content = input_path.read_text(encoding='utf-8')
    except Exception as e:
        print(c(f"\n❌ 读取文件失败: {e}", "red"))
        return 1

    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
    except Exception as e:
        print(c(f"\n❌ XML 解析失败: {e}", "red"))
        return 1

    memories = root.findall('memories/memory')
    if not memories:
        print(c("⚠️  未找到可导入的记忆", "yellow"))
        cm.close()
        return 0

    if not args.force:
        print(c(f"\n🔍 将导入 {len(memories)} 条记忆：", "cyan"))
        for mem in memories[:5]:
            content_elem = mem.find('content')
            content_preview = (content_elem.text or "")[:60] if content_elem is not None else ""
            cat_elem = mem.find('category')
            category = cat_elem.text or "general" if cat_elem is not None else "general"
            print(f"   - [{category}] {content_preview}...")
        if len(memories) > 5:
            print(f"   ... 还有 {len(memories) - 5} 条")
        print(c("\n确认导入？加 --force 执行", "yellow"))
        cm.close()
        return 1

    imported = 0
    skipped = 0
    for mem in memories:
        try:
            content_elem = mem.find('content')
            content_text = (content_elem.text or "") if content_elem is not None else ""
            cat_elem = mem.find('category')
            category = (cat_elem.text or "general") if cat_elem is not None else "general"

            tags = []
            tag_elements = mem.findall('tags/tag')
            for tag_elem in tag_elements:
                if tag_elem.text:
                    tags.append(tag_elem.text)

            privacy_str = mem.find('privacy').text if mem.find('privacy') is not None else "internal"
            importance_str = mem.find('importance').text if mem.find('importance') is not None else "medium"
            layer_str = mem.find('layer').text if mem.find('layer') is not None else "short_term"

            cm.add(
                content=content_text,
                category=category,
                tags=tags,
                privacy=PrivacyLevel.from_string(privacy_str),
                importance=Importance.from_string(importance_str),
                layer=MemoryLayer.from_string(layer_str),
            )
            imported += 1
        except Exception:
            skipped += 1

    print(c(f"\n✅ XML 导入完成", "green"))
    print(f"   成功导入：{c(str(imported), 'green')} 条")
    print(f"   导入失败：{c(str(skipped), 'yellow')} 条")
    cm.close()
    return 0


def cmd_export_json(args):
    """导出记忆为 JSON（v5.1.5 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有可导出的记忆", "yellow"))
        return 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_data = {
        "version": "5.1.5",
        "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(entries),
        "memories": []
    }

    for entry in entries:
        mem_dict = {
            "id": entry.id,
            "content": entry.content,
            "category": entry.category,
            "tags": entry.tags,
            "privacy": entry.privacy.value,
            "importance": entry.importance.value,
            "memory_type": entry.memory_type.value,
            "layer": entry.layer.value,
            "access_count": entry.access_count,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "starred": entry.starred,
            "strength": entry.strength,
            "forgetting_score": entry.forgetting_score,
        }
        export_data["memories"].append(mem_dict)

    indent = 2 if args.pretty else None
    output_path.write_text(json.dumps(export_data, ensure_ascii=False, indent=indent), encoding='utf-8')

    print(c(f"\n✅ JSON 导出完成！", "green"))
    print(f"   文件：{output_path}")
    print(f"   记忆数：{len(entries)}")
    cm.close()
    return 0


def cmd_import_json(args):
    """从 JSON 导入记忆（v5.1.5 新增）"""
    cm = _get_memory(args)
    input_path = Path(args.input)

    if not input_path.exists():
        print(c(f"\n❌ 文件不存在: {input_path}", "red"))
        return 1

    try:
        content = input_path.read_text(encoding='utf-8')
        data = json.loads(content)
    except Exception as e:
        print(c(f"\n❌ JSON 解析失败: {e}", "red"))
        return 1

    memories = data.get("memories", [])
    if not memories:
        print(c("⚠️  未找到可导入的记忆", "yellow"))
        cm.close()
        return 0

    if not args.force:
        print(c(f"\n🔍 将导入 {len(memories)} 条记忆：", "cyan"))
        for mem in memories[:5]:
            content_preview = (mem.get("content") or "")[:60]
            category = mem.get("category") or "general"
            print(f"   - [{category}] {content_preview}...")
        if len(memories) > 5:
            print(f"   ... 还有 {len(memories) - 5} 条")
        print(c("\n确认导入？加 --force 执行", "yellow"))
        cm.close()
        return 1

    imported = 0
    skipped = 0
    for mem in memories:
        try:
            cm.add(
                content=mem.get("content", ""),
                category=mem.get("category", "general"),
                tags=mem.get("tags", []),
                privacy=PrivacyLevel.from_string(mem.get("privacy", "internal")),
                importance=Importance.from_string(mem.get("importance", "medium")),
                layer=MemoryLayer.from_string(mem.get("layer", "short_term")),
            )
            imported += 1
        except Exception:
            skipped += 1

    print(c(f"\n✅ JSON 导入完成", "green"))
    print(f"   成功导入：{c(str(imported), 'green')} 条")
    print(f"   导入失败：{c(str(skipped), 'yellow')} 条")
    cm.close()
    return 0


def cmd_merge(args):
    """合并重复记忆（v5.1.5 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if len(entries) < 2:
        print(c("⚠️  记忆数量不足，无法合并", "yellow"))
        cm.close()
        return 0

    from difflib import SequenceMatcher

    duplicates = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            ratio = SequenceMatcher(None, entries[i].content, entries[j].content).ratio()
            if ratio >= args.threshold:
                duplicates.append({
                    "source": entries[i],
                    "target": entries[j],
                    "similarity": round(ratio, 2)
                })

    if not duplicates:
        print(c("✅ 未找到重复记忆", "green"))
        cm.close()
        return 0

    print(c(f"\n🔍 找到 {len(duplicates)} 组重复记忆（相似度 >= {args.threshold}）:", "cyan"))
    for idx, dup in enumerate(duplicates, 1):
        print(f"\n{idx}. 相似度: {dup['similarity']}")
        print(f"   源记忆: {dup['source'].content[:80]}...")
        print(f"   目标:   {dup['target'].content[:80]}...")

    if args.dry_run:
        print(c("\n⚠️  预览模式，未执行合并", "yellow"))
        cm.close()
        return 0

    merged = 0
    skipped = 0
    for dup in duplicates:
        try:
            cm.delete(dup["target"].id)
            merged += 1
        except Exception:
            skipped += 1

    print(c(f"\n✅ 合并完成", "green"))
    print(f"   已合并：{c(str(merged), 'green')} 组")
    print(f"   合并失败：{c(str(skipped), 'yellow')} 组")
    cm.close()
    return 0


def cmd_remind(args):
    """遗忘提醒（v5.1.5 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有记忆", "yellow"))
        cm.close()
        return 0

    need_remind = sorted(
        [e for e in entries if e.forgetting_score >= args.threshold],
        key=lambda x: x.forgetting_score,
        reverse=True
    )[:args.count]

    if not need_remind:
        print(c("✅ 所有记忆状态良好，无需提醒", "green"))
        cm.close()
        return 0

    print(c(f"\n📢 需要复习的记忆（遗忘分数 >= {args.threshold}）:", "yellow"))
    for idx, entry in enumerate(need_remind, 1):
        print(f"\n{idx}. [{entry.category}] 遗忘分数: {c(f'{entry.forgetting_score:.2f}', 'red')}")
        print(f"   访问次数: {entry.access_count} | 强度: {entry.strength:.2f}")
        print(f"   内容: {entry.content[:120]}...")

    cm.close()
    return 0


def cmd_tags(args):
    """标签管理（v5.1.6 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有记忆", "yellow"))
        cm.close()
        return 0

    tag_counts = {}
    for entry in entries:
        for tag in entry.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        print(c("⚠️  没有找到标签", "yellow"))
        cm.close()
        return 0

    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:args.top]

    print(c(f"\n🏷️  标签统计（共 {len(tag_counts)} 个，显示前 {len(sorted_tags)}）:", "cyan"))
    max_len = max(len(t) for t, _ in sorted_tags) if sorted_tags else 0
    for idx, (tag, count) in enumerate(sorted_tags, 1):
        bar = "█" * min(count, 20)
        print(f"{idx:2}. #{tag:<{max_len}} {c(str(count), 'yellow'):>4} {bar}")

    cm.close()
    return 0


def cmd_cats(args):
    """分类统计（v5.1.6 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有记忆", "yellow"))
        cm.close()
        return 0

    cat_counts = {}
    for entry in entries:
        cat_counts[entry.category] = cat_counts.get(entry.category, 0) + 1

    sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:args.top]

    print(c(f"\n📂 分类统计（共 {len(cat_counts)} 个，显示前 {len(sorted_cats)}）:", "cyan"))
    max_len = max(len(cn) for cn, _ in sorted_cats) if sorted_cats else 0
    for idx, (cat, count) in enumerate(sorted_cats, 1):
        bar = "█" * min(count, 20)
        print(f"{idx:2}. {cat:<{max_len}} {c(str(count), 'yellow'):>4} {bar}")

    cm.close()
    return 0


def cmd_timeline(args):
    """时间线视图（v5.1.6 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有记忆", "yellow"))
        cm.close()
        return 0

    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=args.days)
    cutoff_ts = cutoff.timestamp()

    filtered = [e for e in entries if e.created_at >= cutoff_ts]
    if args.category:
        filtered = [e for e in filtered if e.category == args.category]

    if not filtered:
        print(c(f"⚠️  最近 {args.days} 天没有记忆", "yellow"))
        cm.close()
        return 0

    by_date = {}
    for entry in filtered:
        date_str = datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d")
        if date_str not in by_date:
            by_date[date_str] = []
        by_date[date_str].append(entry)

    print(c(f"\n📅 时间线视图（最近 {args.days} 天，共 {len(filtered)} 条）:", "cyan"))
    if args.category:
        print(f"   分类筛选: {args.category}")

    for date_str in sorted(by_date.keys(), reverse=True):
        entries_day = by_date[date_str]
        print(f"\n{date_str} ({len(entries_day)} 条)")
        for entry in entries_day:
            prefix = "⭐" if entry.starred else "  "
            print(f"  {prefix} [{entry.category}] {entry.content[:80]}...")

    cm.close()
    return 0


def cmd_top(args):
    """热门记忆（v5.1.6 新增）"""
    cm = _get_memory(args)
    entries = cm.list(limit=99999)

    if not entries:
        print(c("⚠️  没有记忆", "yellow"))
        cm.close()
        return 0

    sort_key = {
        "access_count": lambda x: x.access_count,
        "strength": lambda x: x.strength,
        "created_at": lambda x: x.created_at,
    }.get(args.by, lambda x: x.access_count)

    top_entries = sorted(entries, key=sort_key, reverse=True)[:args.count]

    by_label = {"access_count": "访问次数", "strength": "记忆强度", "created_at": "创建时间"}
    label = by_label.get(args.by, "访问次数")

    print(c(f"\n🔥 热门记忆（按 {label} 排序，前 {args.count} 条）:", "cyan"))
    for idx, entry in enumerate(top_entries, 1):
        val = sort_key(entry)
        if args.by == "created_at":
            from datetime import datetime
            val_str = datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M")
        else:
            val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
        prefix = "⭐" if entry.starred else "  "
        print(f"\n{idx}. {prefix} [{entry.category}] {label}: {c(val_str, 'yellow')}")
        print(f"   {entry.content[:100]}...")

    cm.close()
    return 0


def cmd_random(args):
    """随机闪卡复习（v5.1.7 新增）"""
    cm = _get_memory(args)
    entries = cm.random(count=args.count, category=getattr(args, 'category', None))

    if not entries:
        print(c("⚠️  没有找到记忆", "yellow"))
        cm.close()
        return 0

    print(c(f"\n🎲 随机记忆闪卡（共 {len(entries)} 张）:", "cyan"))
    for idx, entry in enumerate(entries, 1):
        from datetime import datetime
        created = datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d")
        starred = "⭐" if entry.starred else "  "
        print(f"\n{'='*50}")
        print(f"  第 {idx} 张  {starred}  [{entry.category}] 强度: {entry.strength:.2f}")
        print(f"  创建: {created}  访问: {entry.access_count}次")
        print(f"{'='*50}")
        print(f"\n  {entry.content}")
        if entry.tags:
            print(f"\n  🏷️  标签: {', '.join(entry.tags)}")

    cm.close()
    return 0


def cmd_rename_tag(args):
    """重命名标签（v5.1.7 新增）"""
    cm = _get_memory(args)

    if not args.force:
        print(c(f"\n将标签 '{args.old}' 重命名为 '{args.new}'", "yellow"))
        print(c("此操作将更新所有包含该标签的记忆。", "yellow"))
        confirm = input("\n确认继续？(y/N): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            cm.close()
            return 0

    count = cm.rename_tag(args.old, args.new)
    print(c(f"\n✅ 标签重命名成功，影响 {count} 条记忆", "green"))

    cm.close()
    return 0


def cmd_rename_cat(args):
    """重命名分类（v5.1.7 新增）"""
    cm = _get_memory(args)

    if not args.force:
        print(c(f"\n将分类 '{args.old}' 重命名为 '{args.new}'", "yellow"))
        print(c("此操作将移动所有该分类下的记忆。", "yellow"))
        confirm = input("\n确认继续？(y/N): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            cm.close()
            return 0

    count = cm.rename_category(args.old, args.new)
    print(c(f"\n✅ 分类重命名成功，影响 {count} 条记忆", "green"))

    cm.close()
    return 0


def cmd_config(args):
    """查看配置（v5.1.7 新增）"""
    cm = _get_memory(args)
    cfg = cm.config_summary()

    print(c("\n⚙️  MindForge 配置信息:", "cyan"))
    print(f"  数据库路径: {cfg['db_path']}")
    print(f"  加密状态: {'开启 🔐' if cfg['encrypted'] else '未加密'}")
    print(f"  数据库大小: {cfg['db_size_mb']} MB")
    print(f"  版本: v{__version__}")

    stats = cm.stats()
    print(f"\n📊 记忆统计:")
    print(f"  总记忆数: {stats['total']}")
    print(f"  分类数: {len(stats.get('top_categories', {}))}")
    print(f"  收藏数: {stats.get('starred_count', 0)}")

    cm.close()
    return 0


def cmd_doctor(args):
    """全面诊断数据库（v5.1.8 新增）"""
    cm = _get_memory(args)
    print_banner()
    print(c("🔧 MindForge 全面诊断", "bold"))
    print("=" * 50)

    issues = []
    fixes_applied = 0

    # 1. 完整性检查
    print(c("\n[1/5] 数据库完整性...", "cyan"))
    health = cm.health_check()
    if health["integrity_check"] == "ok":
        print("  ✅ 完整性校验通过")
    else:
        print(f"  🚨 完整性校验失败: {health['integrity_check']}")
        issues.append("数据库完整性校验失败，可能存在损坏")

    # 2. FTS 孤立记录
    print(c("\n[2/5] FTS 索引一致性...", "cyan"))
    if health["fts_orphans"] == 0:
        print("  ✅ FTS 索引无孤立记录")
    else:
        print(f"  ⚠️  发现 {health['fts_orphans']} 条孤立 FTS 记录")
        if args.fix:
            cm.rebuild_fts()
            print("  ✅ 已重建 FTS 索引")
            fixes_applied += 1
        else:
            issues.append("存在孤立 FTS 记录，建议运行 vacuum 命令")

    # 3. 索引检查
    print(c("\n[3/5] 数据库索引...", "cyan"))
    idx = health["indexes"]
    if idx["found"] == idx["expected"]:
        print(f"  ✅ 索引完整 ({idx['found']}/{idx['expected']})")
    else:
        print(f"  ⚠️  索引缺失: {idx['found']}/{idx['expected']}")
        if idx["missing"]:
            print(f"     缺失: {', '.join(idx['missing'])}")
        issues.append("存在缺失索引，可能影响查询性能")

    # 4. 加密一致性
    print(c("\n[4/5] 加密一致性...", "cyan"))
    if health["encrypted_inconsistent"] == 0:
        print("  ✅ 加密状态一致")
    else:
        print(f"  🚨 {health['encrypted_inconsistent']} 条记忆加密状态异常")
        issues.append("存在加密不一致的记忆")

    # 5. 数据库版本
    print(c("\n[5/5] 数据库版本...", "cyan"))
    try:
        current_ver = cm.storage.get_db_version()
        latest_ver = cm.storage.get_latest_db_version()
        if current_ver >= latest_ver:
            print(f"  ✅ 版本最新 (v{current_ver})")
        else:
            print(f"  ⚠️  版本落后: v{current_ver} -> v{latest_ver}")
            if args.fix:
                cm.storage.migrate_to_latest()
                print("  ✅ 已迁移到最新版本")
                fixes_applied += 1
            else:
                issues.append(f"数据库版本落后，建议运行 migrate --force")
    except Exception as e:
        print(f"  ⚠️  无法获取版本: {e}")

    # 汇总
    print(c("\n" + "=" * 50, "reset"))
    if not issues:
        print(c("🎉 诊断完成，未发现问题！", "green"))
    else:
        print(c(f"⚠️  发现 {len(issues)} 个问题:", "yellow"))
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        if args.fix:
            print(c(f"\n✅ 已自动修复 {fixes_applied} 个问题", "green"))
        else:
            print(c("\n💡 加 --fix 参数自动修复可修复的问题", "cyan"))

    cm.close()
    return 0 if not issues else 1


def cmd_find(args):
    """高级查找记忆（v5.1.8 新增）
    支持按分类、标签、层级、收藏、时间范围组合筛选
    """
    cm = _get_memory(args)

    entries = cm.list(limit=99999)
    results = []

    for entry in entries:
        if args.category and entry.category != args.category:
            continue
        if args.layer and entry.layer.value != args.layer:
            continue
        if args.starred and not entry.starred:
            continue
        if args.tags:
            entry_tags = set(entry.tags) if entry.tags else set()
            if not set(args.tags).issubset(entry_tags):
                continue
        if args.keyword and args.keyword.lower() not in entry.content.lower():
            continue
        if args.after and entry.created_at < args.after:
            continue
        if args.before and entry.created_at > args.before:
            continue
        results.append(entry)

    results.sort(key=lambda e: e.created_at, reverse=True)
    total = len(results)
    if args.limit:
        results = results[:args.limit]

    print(c(f"\n🔍 高级查找结果", "bold"))
    print(f"   匹配 {c(str(total), 'cyan')} 条记忆" + (f"（显示前 {len(results)} 条）" if args.limit and total > args.limit else ""))

    for entry in results:
        star = "⭐ " if entry.starred else ""
        print(f"\n{star}[{c(entry.id[:12], 'dim')}] {c(entry.category, 'green')} "
              f"[{entry.layer.value}]")
        print(f"   {entry.content[:200]}")
        if entry.tags:
            print(f"   标签: {', '.join('#' + t for t in entry.tags)}")
        print(f"   创建: {format_time(entry.created_at)} | 访问: {entry.access_count}")

    cm.close()
    return 0


def cmd_export_excel(args):
    """导出记忆为 Excel（v5.1.9 新增）"""
    cm = _get_memory(args)

    layer = MemoryLayer.from_string(args.layer) if args.layer else None

    path = cm.export_excel(
        output_path=args.output,
        category=args.category,
        layer=layer,
        starred_only=getattr(args, 'starred', False),
    )

    size = path.stat().st_size
    print(c(f"\n✅ Excel 导出成功", "green"))
    print(f"   文件路径: {path}")
    print(f"   文件大小: {format_size(size)}")
    cm.close()
    return 0


def cmd_import_excel(args):
    """从 Excel 导入记忆（v5.1.9 新增）"""
    cm = _get_memory(args)
    input_path = Path(args.input)

    if not input_path.exists():
        print(c(f"\n❌ 文件不存在: {input_path}", "red"))
        return 1

    layer = MemoryLayer.from_string(args.layer) if args.layer else None

    stats = cm.import_excel(
        input_path=str(input_path),
        target_category=args.category,
        target_layer=layer,
    )

    print(c(f"\n✅ Excel 导入完成", "green"))
    print(f"   成功导入：{c(str(stats['imported']), 'green')} 条")
    print(f"   跳过重复：{c(str(stats['skipped']), 'yellow')} 条")
    print(f"   导入失败：{c(str(stats['failed']), 'red')} 条")
    cm.close()
    return 0


def cmd_copy(args):
    """复制记忆到新分类（v5.1.9 新增）"""
    cm = _get_memory(args)

    entry = cm.get(args.id)
    if not entry:
        print(c("❌ 记忆不存在", "red"))
        return 1

    print(c(f"\n将记忆复制到新分类 '{args.category}'", "yellow"))
    print(f"   原记忆: [{entry.category}] {entry.preview[:60]}...")

    success = cm.copy(
        memory_id=args.id,
        new_category=args.category,
        actor=args.agent,
        session_id=args.session,
    )

    if success:
        print(c("\n✅ 复制成功", "green"))
    else:
        print(c("\n❌ 复制失败", "red"))

    cm.close()
    return 0 if success else 1


def cmd_move(args):
    """移动记忆到新分类（v5.1.9 新增）"""
    cm = _get_memory(args)

    entry = cm.get(args.id)
    if not entry:
        print(c("❌ 记忆不存在", "red"))
        return 1

    if entry.category == "trash":
        print(c("❌ 无法移动回收站中的记忆，请先恢复", "red"))
        return 1

    print(c(f"\n将记忆从 '{entry.category}' 移动到 '{args.category}'", "yellow"))
    print(f"   记忆: {entry.preview[:60]}...")

    success = cm.move(
        memory_id=args.id,
        new_category=args.category,
        actor=args.agent,
        session_id=args.session,
    )

    if success:
        print(c("\n✅ 移动成功", "green"))
    else:
        print(c("\n❌ 移动失败", "red"))

    cm.close()
    return 0 if success else 1


def cmd_fuzzy_search(args):
    """模糊搜索记忆（v5.2.0 新增）"""
    cm = _get_memory(args)

    layer = MemoryLayer.from_string(args.layer) if args.layer else None

    results = cm.fuzzy_search(
        query=args.query,
        category=args.category,
        layer=layer,
        limit=args.limit,
        threshold=args.threshold,
    )

    print(c(f"\n🔍 模糊搜索: \"{args.query}\"", "bold"))
    print(c(f"   找到 {len(results)} 条结果（阈值 {args.threshold}）\n", "dim"))

    if not results:
        print(c("   没有找到匹配的记忆", "yellow"))
        cm.close()
        return 0

    for i, result in enumerate(results, 1):
        entry = result["entry"]
        score = result["score"]

        content = entry.preview
        if args.highlight:
            content = cm.highlight(content, args.query, c("", "yellow"), c("", "reset"))

        print(f" {i}. [{entry.id[:12]}] {content[:80]}...")
        print(f"    分类: {entry.category} | 标签: {', '.join(entry.tags) if entry.tags else '无'}")
        print(f"    相关度: {score:.2f} | 访问: {entry.access_count}次 | 强度: {entry.strength:.2f}")
        print()

    cm.close()
    return 0


def cmd_search_history(args):
    """查看搜索历史（v5.2.0 新增）"""
    cm = _get_memory(args)

    history = cm.search_history(limit=args.limit)

    print(c(f"\n📜 搜索历史（最近 {len(history)} 条）\n", "bold"))

    if not history:
        print(c("   暂无搜索历史", "yellow"))
        cm.close()
        return 0

    for i, item in enumerate(history, 1):
        from datetime import datetime
        last_used = datetime.fromtimestamp(item["last_used"]).strftime("%Y-%m-%d %H:%M")
        print(f" {i}. \"{item['query']}\"  ({item['count']}次, 最近: {last_used})")

    print()
    cm.close()
    return 0


def cmd_batch_add_tags(args):
    """批量添加标签（v5.2.0 新增）"""
    cm = _get_memory(args)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    if args.category:
        count = cm.add_tags_by_category(
            category=args.category,
            tags=tags,
            actor=args.agent,
            session_id=args.session,
        )
        print(c(f"\n✅ 已为分类 '{args.category}' 的 {count} 条记忆添加标签: {', '.join(tags)}", "green"))
    elif args.ids:
        entry_ids = [i.strip() for i in args.ids.split(",") if i.strip()]
        count = cm.batch_add_tags(
            entry_ids=entry_ids,
            tags=tags,
            actor=args.agent,
            session_id=args.session,
        )
        print(c(f"\n✅ 已为 {count} 条记忆添加标签: {', '.join(tags)}", "green"))
    else:
        print(c("❌ 请指定 --ids 或 --category 参数", "red"))
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_batch_remove_tags(args):
    """批量移除标签（v5.2.0 新增）"""
    cm = _get_memory(args)

    if not args.ids:
        print(c("❌ 请指定 --ids 参数（记忆 ID 列表，逗号分隔）", "red"))
        cm.close()
        return 1

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    entry_ids = [i.strip() for i in args.ids.split(",") if i.strip()]

    count = cm.batch_remove_tags(
        entry_ids=entry_ids,
        tags=tags,
        actor=args.agent,
        session_id=args.session,
    )

    print(c(f"\n✅ 已从 {count} 条记忆中移除标签: {', '.join(tags)}", "green"))
    cm.close()
    return 0


def cmd_merge_tags(args):
    """合并标签（v5.2.0 新增）"""
    cm = _get_memory(args)

    source_tags = [t.strip() for t in args.source.split(",") if t.strip()]

    print(c(f"\n合并标签确认:", "yellow"))
    print(f"   源标签: {', '.join(source_tags)}")
    print(f"   目标标签: {args.target}")

    if not args.force:
        answer = input("\n确认合并？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    count = cm.merge_tags(
        source_tags=source_tags,
        target_tag=args.target,
        actor=args.agent,
        session_id=args.session,
    )

    print(c(f"\n✅ 合并完成，{count} 条记忆受影响", "green"))
    cm.close()
    return 0


def cmd_db_backup(args):
    """创建数据库备份（v5.2.0 新增）"""
    cm = _get_memory(args)

    print(c("\n💾 创建数据库备份...", "yellow"))

    result = cm.create_backup(backup_dir=args.dir)

    if result["success"]:
        print(c(f"\n✅ 备份成功", "green"))
        print(f"   文件: {result['filename']}")
        print(f"   路径: {result['path']}")
        print(f"   大小: {result['size_mb']} MB")
        print(f"   时间: {result['timestamp']}")
    else:
        print(c(f"\n❌ 备份失败: {result.get('error', '未知错误')}", "red"))
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_db_backups(args):
    """列出备份文件（v5.2.0 新增）"""
    cm = _get_memory(args)

    backups = cm.list_backups(backup_dir=args.dir)

    print(c(f"\n📦 备份列表（共 {len(backups)} 个）\n", "bold"))

    if not backups:
        print(c("   暂无备份", "yellow"))
        cm.close()
        return 0

    for i, backup in enumerate(backups, 1):
        from datetime import datetime
        created = datetime.fromtimestamp(backup["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        print(f" {i}. {backup['filename']}")
        print(f"    大小: {backup['size_mb']} MB | 创建时间: {created}")

    print()
    cm.close()
    return 0


def cmd_db_restore(args):
    """从备份恢复（v5.2.0 新增）"""
    cm = _get_memory(args)

    print(c(f"\n⚠️  恢复备份警告:", "yellow"))
    print(f"   备份文件: {args.backup}")
    print(f"   恢复前自动备份: {'否' if args.no_pre_backup else '是'}")
    print(c("\n   此操作将覆盖当前数据库！", "red"))

    if not args.force:
        answer = input("\n确认恢复？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    result = cm.restore_backup(
        backup_path=args.backup,
        create_backup_before=not args.no_pre_backup,
    )

    if result["success"]:
        print(c("\n✅ 恢复成功", "green"))
        if result.get("backup_created"):
            print(f"   恢复前备份: {result['backup_created']}")
    else:
        print(c(f"\n❌ 恢复失败: {result.get('error', '未知错误')}", "red"))
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_db_clean_backups(args):
    """清理旧备份（v5.2.0 新增）"""
    cm = _get_memory(args)

    backups = cm.list_backups(backup_dir=args.dir)
    will_delete = max(0, len(backups) - args.keep)

    print(c(f"\n🧹 清理旧备份", "yellow"))
    print(f"   当前备份数: {len(backups)}")
    print(f"   保留数量: {args.keep}")
    print(f"   将删除: {will_delete} 个")

    if not args.force and will_delete > 0:
        answer = input("\n确认删除？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    deleted = cm.delete_old_backups(
        backup_dir=args.dir,
        keep_count=args.keep,
    )

    print(c(f"\n✅ 已删除 {deleted} 个旧备份", "green"))
    cm.close()
    return 0


# ===== AI 短剧记忆模块（v5.2.1 新增）=====

def cmd_drama_add(args):
    """添加短剧（v5.2.1 新增）"""
    cm = _get_memory(args)
    drama = cm.add_drama(
        title=args.title,
        genre=args.genre,
        total_episodes=args.episodes,
        status=args.status,
        platform=args.platform,
        rating=args.rating,
        description=args.description,
        tags=args.tags,
        cover_url=args.cover,
    )
    print(c(f"\n✅ 短剧已添加", "green"))
    print(f"   ID: {drama.id}")
    print(f"   标题: {drama.title}")
    print(f"   类型: {drama.genre.value}")
    print(f"   集数: {drama.total_episodes}")
    print(f"   状态: {drama.status.value}")
    cm.close()
    return 0


def cmd_drama_list(args):
    """列出短剧（v5.2.1 新增）"""
    cm = _get_memory(args)
    dramas = cm.list_dramas(
        genre=args.genre,
        status=args.status,
        platform=args.platform,
        min_rating=args.min_rating,
        limit=args.limit,
        offset=args.offset,
        sort_by=args.sort,
        sort_order=args.order,
    )
    print(f"\n找到 {c(str(len(dramas)), 'cyan')} 部短剧")
    for i, d in enumerate(dramas, 1):
        status_color = {
            "watching": "green", "completed": "cyan",
            "planned": "yellow", "dropped": "red"
        }.get(d.status.value, "reset")
        progress = f"{d.current_episode}/{d.total_episodes}" if d.total_episodes else f"{d.current_episode}/?"
        star = "⭐" if d.rating >= 8 else ""
        print(f"\n{i}. {star} {c(d.title, 'bold')} [{c(d.status.value, status_color)}]")
        print(f"   类型: {d.genre.value} | 进度: {progress} | 评分: {d.rating}")
        if d.platform:
            print(f"   平台: {d.platform}")
        if d.description:
            print(f"   简介: {d.description[:80]}...")
    cm.close()
    return 0


def cmd_drama_get(args):
    """获取短剧详情（v5.2.1 新增）"""
    cm = _get_memory(args)
    drama = cm.get_drama(args.id)
    if not drama:
        print(c("❌ 短剧不存在", "red"))
        cm.close()
        return 1

    print(c(f"\n📺 短剧详情", "bold"))
    print("=" * 50)
    print(f"标题:   {drama.title}")
    print(f"ID:     {drama.id}")
    print(f"类型:   {drama.genre.value}")
    print(f"状态:   {drama.status.value}")
    print(f"集数:   {drama.current_episode}/{drama.total_episodes}")
    print(f"评分:   {drama.rating}")
    if drama.platform:
        print(f"平台:   {drama.platform}")
    if drama.tags:
        print(f"标签:   {', '.join(drama.tags)}")
    if drama.description:
        print(f"简介:   {drama.description}")
    if drama.last_watched_at:
        from datetime import datetime
        print(f"上次观看: {datetime.fromtimestamp(drama.last_watched_at).strftime('%Y-%m-%d %H:%M')}")

    scenes = cm.list_scenes(drama_id=drama.id, limit=5)
    if scenes:
        print(f"\n场次:   共 {len(scenes)} 场（显示前5场）")
        for s in scenes[:5]:
            print(f"   EP{s.episode}-{s.scene_number}: {s.title}")

    chars = cm.list_characters(drama_id=drama.id, limit=5)
    if chars:
        print(f"\n角色:   共 {len(chars)} 个（显示前5个）")
        for ch in chars[:5]:
            print(f"   {ch.name} ({ch.role})")

    lines = cm.classic_lines(drama_id=drama.id, limit=3)
    if lines:
        print(f"\n经典台词:")
        for l in lines[:3]:
            char = l.character_name or "未知"
            print(f'   "{l.line_text[:80]}" — {char}')

    cm.close()
    return 0


def cmd_drama_update(args):
    """更新短剧（v5.2.1 新增）"""
    cm = _get_memory(args)
    success = cm.update_drama(
        drama_id=args.id,
        title=args.title,
        genre=args.genre,
        total_episodes=args.episodes,
        current_episode=args.current,
        status=args.status,
        platform=args.platform,
        rating=args.rating,
        description=args.description,
        tags=args.tags,
        cover_url=args.cover,
        mark_watched=args.watched,
    )
    if success:
        print(c("\n✅ 短剧已更新", "green"))
    else:
        print(c("\n❌ 更新失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_drama_delete(args):
    """删除短剧（v5.2.1 新增）"""
    cm = _get_memory(args)
    drama = cm.get_drama(args.id)
    if not drama:
        print(c("❌ 短剧不存在", "red"))
        cm.close()
        return 1

    if not args.force:
        print(c(f"\n⚠️  将删除短剧：{drama.title}", "yellow"))
        print(c("   同时删除所有场次、角色、台词", "yellow"))
        answer = input("\n确认删除？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    success = cm.delete_drama(args.id)
    if success:
        print(c("\n🗑️  短剧已删除", "green"))
    else:
        print(c("\n❌ 删除失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_drama_stats(args):
    """短剧统计（v5.2.1 新增）"""
    cm = _get_memory(args)
    stats = cm.drama_stats()
    print(c(f"\n📊 短剧统计", "bold"))
    print("=" * 40)
    print(f"短剧总数:   {stats['total']}")
    print(f"在看:       {stats['watching']}")
    print(f"已看完:     {stats['completed']}")
    print(f"台词总数:   {stats['total_lines']}")
    print(f"经典台词:   {stats['classic_lines']}")
    if stats['by_genre']:
        print(f"\n按类型:")
        for genre, cnt in stats['by_genre'].items():
            print(f"  {genre}: {cnt}")
    if stats['by_status']:
        print(f"\n按状态:")
        for status, cnt in stats['by_status'].items():
            print(f"  {status}: {cnt}")
    cm.close()
    return 0


def cmd_line_add(args):
    """添加短剧台词（v5.2.1 新增）"""
    cm = _get_memory(args)
    line = cm.add_line(
        drama_id=args.drama_id,
        line_text=args.line,
        scene_id=args.scene_id,
        character_id=args.char_id,
        character_name=args.character,
        context=args.context,
        episode=args.episode,
        timestamp=args.timestamp,
        is_classic=args.classic,
        tags=args.tags,
    )
    print(c(f"\n✅ 台词已添加", "green"))
    print(f"   ID: {line.id}")
    char = line.character_name or "未知"
    print(f'   "{line.line_text}" — {char}')
    if line.is_classic:
        print(f"   ⭐ 经典台词")
    cm.close()
    return 0


def cmd_line_list(args):
    """列出短剧台词（v5.2.1 新增）"""
    cm = _get_memory(args)
    lines = cm.list_lines(
        drama_id=args.drama_id,
        scene_id=args.scene_id,
        character_id=args.char_id,
        is_classic=args.classic,
        episode=args.episode,
        limit=args.limit,
        offset=args.offset,
    )
    label = "经典台词" if args.classic else "台词"
    print(f"\n找到 {c(str(len(lines)), 'cyan')} 条{label}")
    for i, l in enumerate(lines, 1):
        char = l.character_name or "未知"
        classic = "⭐" if l.is_classic else "  "
        ep = f"EP{l.episode}" if l.episode else ""
        print(f"\n{i}. {classic} {ep} {char}:")
        print(f'   "{l.line_text}"')
        if l.context:
            print(f"   背景: {l.context[:60]}")
    cm.close()
    return 0


def cmd_line_search(args):
    """搜索台词（v5.2.1 新增）"""
    cm = _get_memory(args)
    lines = cm.search_lines(
        query=args.query,
        drama_id=args.drama_id,
        is_classic_only=args.classic_only,
        limit=args.limit,
    )
    print(f"\n找到 {c(str(len(lines)), 'cyan')} 条匹配台词")
    for i, l in enumerate(lines, 1):
        char = l.character_name or "未知"
        classic = "⭐" if l.is_classic else "  "
        highlighted = cm.highlight(l.line_text, args.query)
        print(f"\n{i}. {classic} {char}:")
        print(f'   "{highlighted}"')
    cm.close()
    return 0


def cmd_line_classic(args):
    """经典台词（v5.2.1 新增）"""
    cm = _get_memory(args)
    lines = cm.classic_lines(
        drama_id=args.drama_id,
        limit=args.limit,
    )
    print(c(f"\n⭐ 经典台词（共 {len(lines)} 条）", "yellow"))
    for i, l in enumerate(lines, 1):
        char = l.character_name or "未知"
        print(f'\n{i}. "{l.line_text}"')
        print(f"   —— {char}")
    cm.close()
    return 0


def cmd_line_update(args):
    """更新台词（v5.2.1 新增）"""
    cm = _get_memory(args)
    success = cm.update_line(
        line_id=args.id,
        line_text=args.line,
        character_name=args.character,
        context=args.context,
        is_classic=args.classic,
        tags=args.tags,
    )
    if success:
        print(c("\n✅ 台词已更新", "green"))
    else:
        print(c("\n❌ 更新失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_line_delete(args):
    """删除台词（v5.2.1 新增）"""
    cm = _get_memory(args)
    line = cm.get_line(args.id)
    if not line:
        print(c("❌ 台词不存在", "red"))
        cm.close()
        return 1

    if not args.force:
        print(c(f'\n⚠️  将删除台词："{line.line_text[:50]}..."', "yellow"))
        answer = input("\n确认删除？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    success = cm.delete_line(args.id)
    if success:
        print(c("\n🗑️  台词已删除", "green"))
    else:
        print(c("\n❌ 删除失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_char_add(args):
    """添加短剧角色（v5.2.1 新增）"""
    cm = _get_memory(args)
    char = cm.add_character(
        drama_id=args.drama_id,
        name=args.name,
        role=args.role,
        actor=args.actor,
        description=args.description,
        personality=args.personality,
        avatar_url=args.avatar,
        tags=args.tags,
    )
    print(c(f"\n✅ 角色已添加", "green"))
    print(f"   ID: {char.id}")
    print(f"   姓名: {char.name}")
    print(f"   定位: {char.role}")
    if char.actor:
        print(f"   演员: {char.actor}")
    cm.close()
    return 0


def cmd_char_list(args):
    """列出短剧角色（v5.2.1 新增）"""
    cm = _get_memory(args)
    chars = cm.list_characters(
        drama_id=args.drama_id,
        role=args.role,
        limit=args.limit,
        offset=args.offset,
    )
    print(f"\n找到 {c(str(len(chars)), 'cyan')} 个角色")
    for i, ch in enumerate(chars, 1):
        role_color = {"lead": "yellow", "supporting": "cyan", "villain": "red"}.get(ch.role, "reset")
        actor = f" ({ch.actor})" if ch.actor else ""
        print(f"\n{i}. {ch.name} [{c(ch.role, role_color)}]{actor}")
        if ch.personality:
            print(f"   性格: {ch.personality[:60]}")
        if ch.description:
            print(f"   描述: {ch.description[:60]}")
    cm.close()
    return 0


def cmd_char_get(args):
    """获取角色详情（v5.2.1 新增）"""
    cm = _get_memory(args)
    char = cm.get_character(args.id)
    if not char:
        print(c("❌ 角色不存在", "red"))
        cm.close()
        return 1

    print(c(f"\n👤 角色详情", "bold"))
    print("=" * 40)
    print(f"姓名:   {char.name}")
    print(f"ID:     {char.id}")
    print(f"定位:   {char.role}")
    if char.actor:
        print(f"演员:   {char.actor}")
    if char.personality:
        print(f"性格:   {char.personality}")
    if char.description:
        print(f"描述:   {char.description}")
    if char.tags:
        print(f"标签:   {', '.join(char.tags)}")

    lines = cm.list_lines(character_id=char.id, limit=5)
    if lines:
        print(f"\n代表台词（最近5条）:")
        for l in lines[:5]:
            print(f'   "{l.line_text[:60]}"')

    cm.close()
    return 0


def cmd_char_update(args):
    """更新角色（v5.2.1 新增）"""
    cm = _get_memory(args)
    success = cm.update_character(
        char_id=args.id,
        name=args.name,
        role=args.role,
        actor=args.actor,
        description=args.description,
        personality=args.personality,
        avatar_url=args.avatar,
        tags=args.tags,
    )
    if success:
        print(c("\n✅ 角色已更新", "green"))
    else:
        print(c("\n❌ 更新失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_char_delete(args):
    """删除角色（v5.2.1 新增）"""
    cm = _get_memory(args)
    char = cm.get_character(args.id)
    if not char:
        print(c("❌ 角色不存在", "red"))
        cm.close()
        return 1

    if not args.force:
        print(c(f"\n⚠️  将删除角色：{char.name}", "yellow"))
        answer = input("\n确认删除？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    success = cm.delete_character(args.id)
    if success:
        print(c("\n🗑️  角色已删除", "green"))
    else:
        print(c("\n❌ 删除失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_scene_add(args):
    """添加短剧场次（v5.2.1 新增）"""
    cm = _get_memory(args)
    scene = cm.add_scene(
        drama_id=args.drama_id,
        episode=args.episode,
        scene_number=args.scene_number,
        title=args.title,
        content=args.content,
        location=args.location,
        time_of_day=args.time,
        tags=args.tags,
    )
    print(c(f"\n✅ 场次已添加", "green"))
    print(f"   ID: {scene.id}")
    print(f"   EP{scene.episode} - 场{scene.scene_number}: {scene.title}")
    if scene.location:
        print(f"   地点: {scene.location}")
    cm.close()
    return 0


def cmd_scene_list(args):
    """列出短剧场次（v5.2.1 新增）"""
    cm = _get_memory(args)
    scenes = cm.list_scenes(
        drama_id=args.drama_id,
        episode=args.episode,
        limit=args.limit,
        offset=args.offset,
    )
    print(f"\n找到 {c(str(len(scenes)), 'cyan')} 个场次")
    for i, s in enumerate(scenes, 1):
        location = f"[{s.location}]" if s.location else ""
        time_str = f" ({s.time_of_day})" if s.time_of_day else ""
        print(f"\n{i}. EP{s.episode}-{s.scene_number}: {s.title} {location}{time_str}")
        if s.content:
            print(f"   {s.content[:80]}...")
    cm.close()
    return 0


def cmd_scene_get(args):
    """获取场次详情（v5.2.1 新增）"""
    cm = _get_memory(args)
    scene = cm.get_scene(args.id)
    if not scene:
        print(c("❌ 场次不存在", "red"))
        cm.close()
        return 1

    print(c(f"\n🎬 场次详情", "bold"))
    print("=" * 40)
    print(f"标题:   EP{scene.episode} - 场{scene.scene_number}: {scene.title}")
    print(f"ID:     {scene.id}")
    if scene.location:
        print(f"地点:   {scene.location}")
    if scene.time_of_day:
        print(f"时间:   {scene.time_of_day}")
    if scene.tags:
        print(f"标签:   {', '.join(scene.tags)}")
    if scene.content:
        print(f"\n内容:\n{scene.content}")

    lines = cm.list_lines(scene_id=scene.id, limit=10)
    if lines:
        print(f"\n本场台词（{len(lines)} 条）:")
        for l in lines:
            char = l.character_name or "未知"
            print(f'   {char}: "{l.line_text[:60]}"')

    cm.close()
    return 0


def cmd_scene_update(args):
    """更新场次（v5.2.1 新增）"""
    cm = _get_memory(args)
    success = cm.update_scene(
        scene_id=args.id,
        title=args.title,
        content=args.content,
        location=args.location,
        time_of_day=args.time,
        tags=args.tags,
    )
    if success:
        print(c("\n✅ 场次已更新", "green"))
    else:
        print(c("\n❌ 更新失败", "red"))
    cm.close()
    return 0 if success else 1


def cmd_scene_delete(args):
    """删除场次（v5.2.1 新增）"""
    cm = _get_memory(args)
    scene = cm.get_scene(args.id)
    if not scene:
        print(c("❌ 场次不存在", "red"))
        cm.close()
        return 1

    if not args.force:
        print(c(f"\n⚠️  将删除场次：{scene.title}", "yellow"))
        print(c("   同时删除本场所有台词", "yellow"))
        answer = input("\n确认删除？(y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print(c("已取消", "yellow"))
            cm.close()
            return 0

    success = cm.delete_scene(args.id)
    if success:
        print(c("\n🗑️  场次已删除", "green"))
    else:
        print(c("\n❌ 删除失败", "red"))
    cm.close()
    return 0 if success else 1


if __name__ == "__main__":
    main()
