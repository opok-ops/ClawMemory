#!/usr/bin/env python3
"""
MindForge v5.1.3 CLI - 命令行工具
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
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    MindForge,
    MemoryConfig,
    PrivacyLevel,
    Importance,
    MemoryType,
    MemoryLayer,
)

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
║        {COLORS['bold']}MindForge v5.1.3 - AI Agent 终身记忆系统{COLORS['reset']}{COLORS['cyan']}        ║
║      四层记忆架构 · 知识图谱 · 多模态 · 人格化      ║
╚══════════════════════════════════════════════════════╝{COLORS['reset']}
"""
    print(banner)


def cmd_init(args):
    """初始化 MindForge"""
    print_banner()
    print(c("MindForge 初始化向导", "bold"))
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

    cfg = _lazy_import("RecallConfig")(
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

    # 执行 VACUUM 回收空间
    try:
        cm.storage._get_conn().execute("VACUUM")
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
        if i + 1 < len(sections):
            header = sections[i + 1].strip()
            level = len(header) - len(header.lstrip('#'))
            title = header.lstrip('#').strip()
            current_category = title
            current_tags = re.findall(r'#(\w+)', title)
        if text:
            entries.append({
                'content': text,
                'category': current_category,
                'tags': current_tags,
            })

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
            <p>Generated by MindForge v5.1.3</p>
        </div>
    </div>
</body>
</html>"""

    cards_html = ""
    for entry in entries:
        tags_html = "".join(f'<span class="tag">#{t}</span>' for t in entry.tags) if entry.tags else ""
        cards_html += f"""
<div class="memory-card">
    <div class="card-header">
        <span class="category">{entry.category}</span>
        <span class="layer">{entry.layer.value}</span>
    </div>
    <div class="card-content">{entry.content}</div>
    <div class="card-footer">
        <div class="tags">{tags_html}</div>
        <span>{datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d %H:%M")}</span>
    </div>
</div>"""

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_content = html_template.format(count=len(entries), export_time=export_time, cards=cards_html)

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
        description="MindForge v5.1.3 - AI Agent 终身记忆系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-v", action="version", version="MindForge v5.1.3")

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

        with urllib.request.urlopen(args.url, timeout=10) as response:
            content = response.read().decode("utf-8", errors="ignore")

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


if __name__ == "__main__":
    main()
