"""MindForge v5.3.9 单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import tempfile
import os


class TestCoreTypes(unittest.TestCase):
    """核心类型测试"""

    def test_enums(self):
        from core.types import PrivacyLevel, Importance, MemoryType, MemoryLayer

        self.assertEqual(PrivacyLevel.PUBLIC.value, "PUBLIC")
        self.assertEqual(PrivacyLevel.INTERNAL.value, "INTERNAL")
        self.assertEqual(PrivacyLevel.PRIVATE.value, "PRIVATE")
        self.assertEqual(PrivacyLevel.STRICT.value, "STRICT")

        self.assertEqual(Importance.LOW.value, "LOW")
        self.assertEqual(Importance.MEDIUM.value, "MEDIUM")
        self.assertEqual(Importance.HIGH.value, "HIGH")
        self.assertEqual(Importance.CRITICAL.value, "CRITICAL")

        self.assertEqual(MemoryType.TEXT.value, "text")
        self.assertEqual(MemoryType.IMAGE.value, "image")
        self.assertEqual(MemoryType.AUDIO.value, "audio")
        self.assertEqual(MemoryType.CODE.value, "code")

        self.assertEqual(MemoryLayer.SENSORY.value, "sensory")
        self.assertEqual(MemoryLayer.SHORT_TERM.value, "short_term")
        self.assertEqual(MemoryLayer.LONG_TERM.value, "long_term")
        self.assertEqual(MemoryLayer.PERMANENT.value, "permanent")

    def test_memory_config(self):
        from core.types import MemoryConfig

        config = MemoryConfig(db_path="/tmp/test.db")
        self.assertEqual(config.db_path, "/tmp/test.db")
        self.assertEqual(config.encrypted, True)
        self.assertEqual(config.default_privacy.value, "INTERNAL")
        self.assertEqual(config.default_importance.value, "MEDIUM")
        self.assertEqual(config.default_layer.value, "short_term")


class TestStorageEngine(unittest.TestCase):
    """存储引擎测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_and_get_memory(self):
        from core.storage import StorageEngine
        from core.types import MemoryLayer, PrivacyLevel, Importance, MemoryType

        storage = StorageEngine(db_path=self.db_path)

        entry = storage.add_memory(
            content="测试记忆内容",
            category="test",
            tags=["tag1", "tag2"],
            privacy=PrivacyLevel.INTERNAL,
            importance=Importance.MEDIUM,
            memory_type=MemoryType.TEXT,
            layer=MemoryLayer.SHORT_TERM,
        )

        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.content, "测试记忆内容")
        self.assertEqual(entry.category, "test")
        self.assertEqual(len(entry.tags), 2)

        retrieved = storage.get_memory(entry.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "测试记忆内容")
        self.assertEqual(retrieved.category, "test")

    def test_list_memories(self):
        from core.storage import StorageEngine
        from core.types import MemoryLayer, PrivacyLevel, Importance, MemoryType

        storage = StorageEngine(db_path=self.db_path)

        for i in range(5):
            storage.add_memory(
                content=f"记忆 {i}",
                category="test" if i % 2 == 0 else "other",
                layer=MemoryLayer.SHORT_TERM,
            )

        all_memories = storage.list_memories(limit=10)
        self.assertEqual(len(all_memories), 5)

        test_memories = storage.list_memories(category="test", limit=10)
        self.assertEqual(len(test_memories), 3)

    def test_update_memory(self):
        from core.storage import StorageEngine
        from core.types import MemoryLayer, PrivacyLevel, Importance, MemoryType

        storage = StorageEngine(db_path=self.db_path)

        entry = storage.add_memory(
            content="原始内容",
            category="test",
            layer=MemoryLayer.SHORT_TERM,
        )

        result = storage.update_memory(
            entry_id=entry.id,
            content="更新后的内容",
            category="updated",
        )

        self.assertTrue(result)

        updated = storage.get_memory(entry.id)
        self.assertEqual(updated.content, "更新后的内容")
        self.assertEqual(updated.category, "updated")

    def test_delete_memory(self):
        from core.storage import StorageEngine
        from core.types import MemoryLayer, PrivacyLevel, Importance, MemoryType

        storage = StorageEngine(db_path=self.db_path)

        entry = storage.add_memory(
            content="要删除的记忆",
            category="test",
            layer=MemoryLayer.SHORT_TERM,
        )

        result = storage.delete_memory(entry.id, hard_delete=True)
        self.assertTrue(result)

        retrieved = storage.get_memory(entry.id)
        self.assertIsNone(retrieved)

    def test_stats(self):
        from core.storage import StorageEngine
        from core.types import MemoryLayer, PrivacyLevel, Importance, MemoryType

        storage = StorageEngine(db_path=self.db_path)

        for i in range(3):
            storage.add_memory(
                content=f"记忆 {i}",
                category="test",
                layer=MemoryLayer.LONG_TERM,
            )

        stats = storage.get_stats()
        self.assertIn("total", stats)
        self.assertEqual(stats["total"], 3)


class TestMindForge(unittest.TestCase):
    """MindForge 主类测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init(self):
        from core.mindforge import MindForge

        cm = MindForge(db_path=self.db_path, encrypted=False)
        self.assertIsNotNone(cm)
        self.assertIsNotNone(cm.storage)
        self.assertIsNotNone(cm.index)
        self.assertIsNotNone(cm.query)
        cm.close()

    def test_add_and_search(self):
        from core.mindforge import MindForge

        cm = MindForge(db_path=self.db_path, encrypted=False)

        cm.add(
            content="Python 是一种高级编程语言",
            category="tech",
            tags=["python", "编程"],
        )

        cm.add(
            content="数据库优化的关键是建立合适的索引",
            category="tech",
            tags=["数据库", "优化"],
        )

        results = cm.search("Python 编程", max_results=5)
        self.assertGreater(results.total_found, 0)
        cm.close()

    def test_export_import_json(self):
        from core.mindforge import MindForge
        import json

        cm = MindForge(db_path=self.db_path, encrypted=False)

        cm.add(content="导出测试 1", category="test", tags=["export"])
        cm.add(content="导出测试 2", category="test", tags=["export"])

        export_path = os.path.join(self.tmp_dir, "export.json")
        count = cm.export_json(export_path)
        self.assertEqual(count, 2)

        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["memories"]), 2)

        new_db = os.path.join(self.tmp_dir, "new.db")
        cm2 = MindForge(db_path=new_db, encrypted=False)
        stats = cm2.import_json(export_path)
        self.assertEqual(stats["imported"], 2)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["failed"], 0)

        results = cm2.search("导出测试", max_results=10)
        self.assertEqual(results.total_found, 2)

        cm.close()
        cm2.close()

    def test_export_csv(self):
        from core.mindforge import MindForge
        import csv

        cm = MindForge(db_path=self.db_path, encrypted=False)

        cm.add(content="CSV 测试 1", category="csv_test")
        cm.add(content="CSV 测试 2", category="csv_test")

        csv_path = os.path.join(self.tmp_dir, "export.csv")
        count = cm.export_csv(csv_path)
        self.assertEqual(count, 2)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertIn("content", rows[0])
        self.assertIn("category", rows[0])

        cm.close()


class TestKnowledgeGraph(unittest.TestCase):
    """知识图谱测试"""

    def test_extract_entities(self):
        from modules.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        entities = kg.extract_entities("Python 和 PostgreSQL 是常用的开发工具")
        self.assertIsInstance(entities, list)

    def test_add_and_get_relations(self):
        from modules.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_relation("Python", "编程开发", "is_a", weight=0.9)
        kg.add_relation("PostgreSQL", "数据库", "is_a", weight=0.9)
        kg.add_relation("Python", "PostgreSQL", "uses", weight=0.7)

        related = kg.get_related_entities("Python", depth=1)
        self.assertGreater(len(related), 0)

        stats = kg.get_entity_stats()
        self.assertIn("total_entities", stats)
        self.assertIn("total_relations", stats)


class TestPersonalityEngine(unittest.TestCase):
    """人格化引擎测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_learn_and_profile(self):
        from core.mindforge import MindForge
        from modules.personality import PersonalityEngine

        cm = MindForge(db_path=self.db_path, encrypted=False)
        pe = PersonalityEngine(cm.storage)

        pe.learn_from_interaction(
            "test_user",
            "你好，请帮我写个Python脚本",
            "好的，这是一个简洁的Python脚本示例...",
        )

        profile = pe.get_profile("test_user")
        self.assertIsNotNone(profile)
        self.assertGreaterEqual(profile.total_interactions, 1)

        style = pe.get_recommended_style("test_user")
        self.assertIsInstance(style, dict)

        cm.close()


class TestFTSUpdateSync(unittest.TestCase):
    """v5.0.6: update_memory 的 FTS 索引同步测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_update_content_syncs_fts(self):
        """更新 content 后，FTS 索引应反映新内容而非旧内容"""
        from core.storage import StorageEngine
        from core.types import MemoryLayer

        storage = StorageEngine(db_path=self.db_path)
        entry = storage.add_memory(
            content="original content about python programming",
            category="tech",
            layer=MemoryLayer.SHORT_TERM,
        )

        # 更新为完全不同的内容
        storage.update_memory(entry_id=entry.id, content="updated content about database optimization")

        conn = storage._get_conn()
        # FTS 中应能搜到新内容
        rows = conn.execute(
            "SELECT rowid FROM memory_fts WHERE memory_fts MATCH 'database'"
        ).fetchall()
        self.assertGreater(len(rows), 0, "FTS 应包含更新后的新内容")

        # FTS 中不应再命中旧内容的关键词
        rows_old = conn.execute(
            "SELECT rowid FROM memory_fts WHERE memory_fts MATCH 'python'"
        ).fetchall()
        self.assertEqual(len(rows_old), 0, "FTS 不应再包含更新前的旧内容")
        storage.close()

    def test_update_category_syncs_fts(self):
        """更新 category 后，FTS 索引的 category 字段应同步"""
        from core.storage import StorageEngine
        from core.types import MemoryLayer

        storage = StorageEngine(db_path=self.db_path)
        entry = storage.add_memory(
            content="测试分类同步的内容",
            category="old_cat",
            layer=MemoryLayer.SHORT_TERM,
        )

        storage.update_memory(entry_id=entry.id, category="new_cat")

        conn = storage._get_conn()
        rows = conn.execute(
            "SELECT category FROM memory_fts WHERE memory_fts MATCH 'new_cat'"
        ).fetchall()
        self.assertGreater(len(rows), 0, "FTS 应能按新分类检索")
        storage.close()


class TestRebuildFTS(unittest.TestCase):
    """v5.0.6: rebuild_fts 测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_rebuild_fts_clears_orphans(self):
        """rebuild_fts 应消除孤立 FTS 记录"""
        from core.storage import StorageEngine
        from core.types import MemoryLayer

        storage = StorageEngine(db_path=self.db_path)
        for i in range(3):
            storage.add_memory(
                content=f"记忆内容 {i}",
                category="test",
                layer=MemoryLayer.SHORT_TERM,
            )

        # 重建前健康检查
        before = storage.health_check()
        self.assertEqual(before["fts_orphans"], 0)

        # 手动制造孤立 FTS 记录
        conn = storage._get_conn()
        conn.execute(
            "INSERT INTO memory_fts (rowid, content, category, tags) VALUES (999999, 'orphan', 'x', '[]')"
        )
        conn.commit()
        orphans = conn.execute(
            "SELECT COUNT(*) FROM memory_fts WHERE rowid NOT IN (SELECT rowid FROM memories)"
        ).fetchone()[0]
        self.assertGreater(orphans, 0, "应已制造孤立记录")

        # 重建
        result = storage.rebuild_fts()
        self.assertTrue(result["rebuilt"])
        self.assertEqual(result["indexed"], 3)

        # 重建后健康检查
        after = storage.health_check()
        self.assertEqual(after["fts_orphans"], 0, "孤立记录应被清除")
        storage.close()


class TestPurgeTrash(unittest.TestCase):
    """v5.0.6: purge_trash 测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_purge_trash_removes_soft_deleted(self):
        """purge_trash 应永久删除所有软删除的记忆"""
        from core.storage import StorageEngine
        from core.types import MemoryLayer

        storage = StorageEngine(db_path=self.db_path)

        # 添加 3 条记忆
        ids = []
        for i in range(3):
            entry = storage.add_memory(
                content=f"待删除记忆 {i}",
                category="test",
                layer=MemoryLayer.SHORT_TERM,
            )
            ids.append(entry.id)

        # 软删除 2 条
        storage.delete_memory(ids[0], hard_delete=False)
        storage.delete_memory(ids[1], hard_delete=False)

        # 回收站应有 2 条
        trash = storage.list_memories(category="trash", limit=100)
        self.assertEqual(len(trash), 2)

        # 清空回收站
        count = storage.purge_trash()
        self.assertEqual(count, 2)

        # 回收站应清空
        trash_after = storage.list_memories(category="trash", limit=100)
        self.assertEqual(len(trash_after), 0)

        # 未删除的那条应仍在
        remaining = storage.list_memories(category="test", limit=100)
        self.assertEqual(len(remaining), 1)
        storage.close()

    def test_purge_trash_empty(self):
        """回收站为空时 purge_trash 应返回 0"""
        from core.storage import StorageEngine

        storage = StorageEngine(db_path=self.db_path)
        count = storage.purge_trash()
        self.assertEqual(count, 0)
        storage.close()


class TestSearchHydration(unittest.TestCase):
    """v5.2.8 修复验证：跨进程搜索（索引水合 + 模糊补充召回）"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cross_process_search(self):
        """新进程实例中 search 应能搜到历史记忆（索引水合）"""
        from core.mindforge import MindForge

        cm1 = MindForge(db_path=self.db_path, encrypted=False)
        cm1.add("知识图谱让记忆不再孤立", category="tech", tags=["kg"])
        cm1.close()

        # 模拟新进程：全新实例，内存索引为空
        cm2 = MindForge(db_path=self.db_path, encrypted=False)
        self.assertTrue(cm2.index.needs_hydration)
        result = cm2.search("知识图谱")
        self.assertGreaterEqual(result.total_found, 1)
        cm2.close()

    def test_cjk_substring_search(self):
        """CJK 子串查询应通过模糊补充召回命中"""
        from core.mindforge import MindForge

        cm = MindForge(db_path=self.db_path, encrypted=False)
        cm.add("SQLite 是轻量级嵌入式数据库", category="tech")
        result = cm.search("数据库")
        self.assertGreaterEqual(result.total_found, 1)
        cm.close()

    def test_search_no_false_positive(self):
        """不存在的关键词应返回 0 条"""
        from core.mindforge import MindForge

        cm = MindForge(db_path=self.db_path, encrypted=False)
        cm.add("普通的一条记忆", category="test")
        result = cm.search("绝对不存在的关键词zzz")
        self.assertEqual(result.total_found, 0)
        cm.close()


class TestMultiAgentMemory(unittest.TestCase):
    """v5.2.8 新增：多 Agent 记忆空间（实验性）"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make(self):
        from core.mindforge import MindForge
        return MindForge(db_path=self.db_path, encrypted=False)

    def test_space_lifecycle(self):
        """创建空间 → 添加成员 → 共享 → 冲突解决 → 隐私护栏 → 读取 → 统计"""
        from core.types import PrivacyLevel

        cm = self._make()
        entry = cm.add("可共享的团队知识", category="team")
        private = cm.add("私密内容", category="secret", privacy=PrivacyLevel.PRIVATE)

        ma = cm.multi_agent
        r = ma.create_space("s1", owner_agent="leader")
        self.assertTrue(r["success"])

        r = ma.add_member("s1", "worker", role="editor", actor="leader")
        self.assertTrue(r["success"])

        r = ma.share_memory("s1", entry.id, actor="worker")
        self.assertTrue(r["success"])
        self.assertEqual(r["version"], 1)

        # 冲突解决：重复共享 → last-write-wins，版本递增
        r = ma.share_memory("s1", entry.id, actor="leader")
        self.assertTrue(r["success"])
        self.assertEqual(r["version"], 2)
        self.assertEqual(r["conflict_resolved"], "last-write-wins")

        # 隐私护栏：PRIVATE 禁止共享
        r = ma.share_memory("s1", private.id, actor="leader")
        self.assertFalse(r["success"])
        self.assertIn("隐私护栏", r["error"])

        # reader 可读取
        ma.add_member("s1", "guest", role="reader", actor="guest")
        r = ma.list_space_memories("s1", actor="guest")
        self.assertTrue(r["success"])
        self.assertEqual(r["count"], 1)

        # 非成员禁止读取
        r = ma.list_space_memories("s1", actor="outsider")
        self.assertFalse(r["success"])

        stats = ma.space_stats()
        self.assertEqual(stats["total_spaces"], 1)
        self.assertEqual(stats["total_shared_items"], 1)
        cm.close()

    def test_permission_enforcement(self):
        """reader 不能共享；非 owner 不能加人/删空间"""
        cm = self._make()
        entry = cm.add("知识", category="t")
        ma = cm.multi_agent
        ma.create_space("s2", owner_agent="boss")
        ma.add_member("s2", "reader1", role="reader", actor="boss")

        r = ma.share_memory("s2", entry.id, actor="reader1")
        self.assertFalse(r["success"])

        r = ma.add_member("s2", "another", role="editor", actor="reader1")
        self.assertFalse(r["success"])

        r = ma.delete_space("s2", actor="reader1")
        self.assertFalse(r["success"])

        r = ma.delete_space("s2", actor="boss")
        self.assertTrue(r["success"])
        cm.close()

    def test_duplicate_space_name_rejected(self):
        """空间名称唯一"""
        cm = self._make()
        ma = cm.multi_agent
        self.assertTrue(ma.create_space("dup", owner_agent="a")["success"])
        self.assertFalse(ma.create_space("dup", owner_agent="b")["success"])
        cm.close()


class TestIntentRouter(unittest.TestCase):
    """v5.3.9 意图分类路由测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mf_intent_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rule_matching(self):
        """规则正则匹配"""
        from modules.intent_router import IntentRouter
        router = IntentRouter()
        result = router.classify("记住：用户偏好深色主题")
        self.assertEqual(result.label, "记忆存储")
        self.assertGreater(result.confidence, 0.3)

    def test_keyword_matching(self):
        """关键词加权匹配"""
        from modules.intent_router import IntentRouter
        router = IntentRouter()
        result = router.classify("搜索一下之前的部署记录")
        self.assertEqual(result.label, "记忆检索")

    def test_force_override(self):
        """强制覆盖意图"""
        from modules.intent_router import IntentRouter
        router = IntentRouter()
        result = router.classify("随便说点什么", force_override="memory_store")
        self.assertEqual(result.intent, "memory_store")


class TestConflictDetector(unittest.TestCase):
    """v5.3.9 矛盾检测测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mf_conflict_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_antonym_detection(self):
        """反义词对检测"""
        from modules.conflict_detector import ConflictDetector
        detector = ConflictDetector()
        conflicts = detector.detect_antonym(
            "MySQL 已启用，启动成功", "MySQL 已禁用，启动失败", "id1", "id2"
        )
        self.assertIsNotNone(conflicts)
        self.assertGreaterEqual(conflicts.severity, 0.5)

    def test_empty_memories(self):
        """空记忆列表安全"""
        from modules.conflict_detector import ConflictDetector
        detector = ConflictDetector()
        result = detector.scan_memories([])
        self.assertEqual(len(result), 0)


class TestSkillExtractor(unittest.TestCase):
    """v5.3.9 技能转化测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mf_skill_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_extract_from_devops(self):
        """从 DevOps 记忆中抽取技能"""
        from modules.skill_extractor import SkillExtractor
        extractor = SkillExtractor()
        memories = [
            {"id": "1", "content": "部署步骤1 安装依赖 步骤2 初始化 步骤3 启动", "category": "devops"},
            {"id": "2", "content": "部署步骤1 检查环境 步骤2 执行部署 步骤3 验证", "category": "devops"},
        ]
        skills = extractor.extract(memories)
        self.assertIsInstance(skills, list)

    def test_empty_memories(self):
        """空记忆列表安全"""
        from modules.skill_extractor import SkillExtractor
        extractor = SkillExtractor()
        skills = extractor.extract([])
        self.assertEqual(len(skills), 0)


class TestHybridSearch(unittest.TestCase):
    """v5.3.9 混合检索增强测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mf_hybrid_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_query_expansion(self):
        """查询扩展"""
        from modules.hybrid_search import QueryExpander
        expander = QueryExpander()
        result = expander.expand("MySQL 部署")
        self.assertIsNotNone(result)
        self.assertGreater(len(result.expanded_terms), 0)

    def test_reranker(self):
        """Cross-Encoder 重排"""
        from modules.hybrid_search import CrossEncoderReranker
        reranker = CrossEncoderReranker()
        candidates = [
            {"id": "1", "content": "MySQL 部署成功", "importance": 0.8},
            {"id": "2", "content": "Python 安装教程", "importance": 0.5},
            {"id": "3", "content": "MySQL 启动失败 端口占用", "importance": 0.7},
        ]
        results = reranker.rerank("MySQL 部署启动", candidates)
        self.assertEqual(len(results), 3)
        # MySQL 相关结果应排在前面
        self.assertIn(results[0].memory_id, ["1", "3"])


class TestSessionFocus(unittest.TestCase):
    """v5.3.9 会话焦点测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="mf_focus_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_focus_summary(self):
        """焦点摘要"""
        from modules.session_focus import SessionFocus
        sf = SessionFocus()
        messages = [
            {"id": "m1", "role": "user", "content": "MySQL 怎么部署?"},
            {"id": "m2", "role": "assistant", "content": "先安装再启动"},
            {"id": "m3", "role": "user", "content": "报错了端口占用"},
        ]
        summary = sf.summarize(messages)
        self.assertIsNotNone(summary)
        self.assertGreater(len(summary.focus_keywords), 0)

    def test_empty_messages(self):
        """空消息安全"""
        from modules.session_focus import SessionFocus
        sf = SessionFocus()
        summary = sf.summarize([])
        self.assertIsNotNone(summary)


class TestFederatedACL(unittest.TestCase):
    """联邦记忆细粒度 ACL 测试（v5.4.0）"""

    def setUp(self):
        from modules.federated import FederatedMemory, AccessLevel, ACLRule
        self.fm = FederatedMemory(local_peer_id="local")
        self.fm.register_peer("alice", "Alice", trust_level=0.8)
        self.fm.register_peer("bob", "Bob", trust_level=0.4)
        self.fm.register_peer("carol", "Carol", trust_level=0.6)
        # 关闭信任兜底，让 ACL 规则成为唯一权限来源（便于隔离测试）
        self.fm.trust_read_threshold = 1.5

    def test_access_level_parse(self):
        """AccessLevel.parse 容错"""
        from modules.federated import AccessLevel
        self.assertEqual(AccessLevel.parse("read"), AccessLevel.READ)
        self.assertEqual(AccessLevel.parse("WRITE"), AccessLevel.WRITE)
        self.assertEqual(AccessLevel.parse("rw"), AccessLevel.WRITE)
        self.assertEqual(AccessLevel.parse("admin"), AccessLevel.ADMIN)
        self.assertEqual(AccessLevel.parse(2), AccessLevel.WRITE)
        self.assertEqual(AccessLevel.parse("invalid"), AccessLevel.NONE)
        self.assertEqual(AccessLevel.parse(None), AccessLevel.NONE)

    def test_grant_and_check(self):
        """授予规则后能通过 check_access"""
        from modules.federated import AccessLevel
        self.fm.grant(
            principal="alice",
            level=AccessLevel.WRITE,
            namespace="team/*",
            tags=["python"],
            granted_by="local",
        )
        # alice 在 team/api 命名空间 + python 标签下应有 WRITE
        level = self.fm.check_access("alice", "write",
                                     namespace="team/api",
                                     tags=["python", "ops"])
        self.assertEqual(level, AccessLevel.WRITE)
        # bob 未授权 → NONE
        level = self.fm.check_access("bob", "write",
                                     namespace="team/api",
                                     tags=["python"])
        self.assertEqual(level, AccessLevel.NONE)
        # bob 信任度 0.4 < 0.5 阈值，连 READ 都没有
        level = self.fm.check_access("bob", "read",
                                     namespace="team/api",
                                     tags=["python"])
        self.assertEqual(level, AccessLevel.NONE)

    def test_namespace_wildcard(self):
        """namespace 通配匹配"""
        from modules.federated import AccessLevel
        self.fm.grant(principal="carol", level=AccessLevel.READ,
                      namespace="docs/*", granted_by="local")
        # docs/api 命中
        self.assertTrue(self.fm.can_read("carol", namespace="docs/api"))
        # docs/api/v2 命中
        self.assertTrue(self.fm.can_read("carol", namespace="docs/api/v2"))
        # team/api 不命中
        self.assertFalse(self.fm.can_read("carol", namespace="team/api"))
        # 不可写
        self.assertFalse(self.fm.can_write("carol", namespace="docs/api"))

    def test_local_peer_always_admin(self):
        """本地 peer 永远是 ADMIN"""
        from modules.federated import AccessLevel
        level = self.fm.check_access("local", "admin")
        self.assertEqual(level, AccessLevel.ADMIN)

    def test_revoke_acl(self):
        """撤销 ACL 规则"""
        from modules.federated import AccessLevel
        self.fm.grant(principal="alice", level=AccessLevel.WRITE,
                      memory_id="mem_001", granted_by="local")
        self.assertTrue(self.fm.can_write("alice", memory_id="mem_001"))
        # 撤销
        removed = self.fm.revoke_acl("alice", memory_id="mem_001")
        self.assertEqual(removed, 1)
        self.assertFalse(self.fm.can_write("alice", memory_id="mem_001"))

    def test_acl_dedup(self):
        """同 principal + 同资源维度 = 更新而非追加"""
        from modules.federated import AccessLevel
        self.fm.grant(principal="alice", level=AccessLevel.READ,
                      namespace="team/*", granted_by="local")
        before = len(self.fm.acl_rules)
        # 再授予一次同维度但 level 不同
        self.fm.grant(principal="alice", level=AccessLevel.WRITE,
                      namespace="team/*", granted_by="local")
        after = len(self.fm.acl_rules)
        self.assertEqual(before, after)  # 规则数不增加
        # level 应被更新为 WRITE
        self.assertTrue(self.fm.can_write("alice", namespace="team/api"))

    def test_acl_expiry(self):
        """过期规则不生效"""
        import time as _time
        from modules.federated import AccessLevel
        # 用 bob（信任度 0.4 < 0.5 阈值）避免信任兜底干扰
        self.fm.grant(principal="bob", level=AccessLevel.READ,
                      memory_id="mem_002",
                      expires_at=_time.time() - 1,  # 已过期
                      granted_by="local")
        self.assertFalse(self.fm.can_read("bob", memory_id="mem_002"))

    def test_share_memory_writes_acl(self):
        """share_memory 自动写入 ACL 规则"""
        from modules.federated import AccessLevel
        # 模拟一个不依赖 storage 的场景
        self.fm.storage = None  # _verify_memory_exists 返回 True
        self.fm.share_memory(
            memory_id="mem_003",
            peer_ids=["alice"],
            level=AccessLevel.WRITE,
            namespace="team/api",
            tags=["python"],
        )
        self.assertTrue(self.fm.can_write("alice", memory_id="mem_003",
                                          namespace="team/api",
                                          tags=["python"]))

    def test_provenance_chain(self):
        """溯源链追加"""
        prov = self.fm.track_provenance("mem_004", created_by="alice")
        self.assertEqual(prov.version, 1)
        self.assertEqual(prov.created_by, "alice")
        # 修改一次
        prov2 = self.fm.record_modification("mem_004", actor="bob", reason="update content")
        self.assertEqual(prov2.version, 2)
        self.assertEqual(prov2.last_modified_by, "bob")
        # 链上应该有 2 条记录
        chain = self.fm.audit_trail("mem_004")
        self.assertEqual(len(chain), 2)
        # 反向查询
        created = self.fm.find_by_creator("alice")
        self.assertIn("mem_004", created)


class TestConsensusEngine(unittest.TestCase):
    """共享记忆冲突解决测试（v5.4.0）"""

    def setUp(self):
        from modules.consensus import ConsensusEngine, ReplicaState
        self.engine = ConsensusEngine(strategy="lww")

    def test_lww_higher_version_wins(self):
        """高 version 胜"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0, content="old")
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         last_modified_at=1000.0, content="new")
        result = self.engine.merge_replicas([a, b])
        self.assertEqual(result.winner.peer_id, "bob")
        self.assertEqual(result.merged_content, "new")
        self.assertEqual(len(result.losers), 1)
        self.assertEqual(result.losers[0].peer_id, "alice")

    def test_lww_same_version_newer_timestamp_wins(self):
        """同 version 时新时间戳胜"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=2,
                         last_modified_at=1000.0, content="old")
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         last_modified_at=2000.0, content="new")
        result = self.engine.merge_replicas([a, b])
        self.assertEqual(result.winner.peer_id, "bob")

    def test_lww_importance_override(self):
        """高重要度副本不被低重要度的新时间戳覆盖"""
        from modules.consensus import ReplicaState
        # CRITICAL 旧副本 vs LOW 新副本
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0, content="critical fact",
                         importance="CRITICAL")
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         last_modified_at=2000.0, content="casual note",
                         importance="LOW")
        result = self.engine.merge_replicas([a, b])
        # CRITICAL 胜，因为 LOW 与 CRITICAL rank 差 > 1
        self.assertEqual(result.winner.peer_id, "alice")
        self.assertEqual(result.merged_content, "critical fact")

    def test_tags_union_merge(self):
        """tags 并集合并"""
        from modules.consensus import ReplicaState, ConsensusEngine
        engine = ConsensusEngine(strategy="crdt", tag_merge="union")
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0, tags=["python", "ops"])
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         last_modified_at=2000.0, tags=["python", "db"])
        result = engine.merge_replicas([a, b])
        # 并集
        self.assertEqual(set(result.merged_tags), {"python", "ops", "db"})

    def test_metadata_field_conflict_detected(self):
        """metadata 字段冲突被标记"""
        from modules.consensus import ReplicaState, ConsensusEngine
        engine = ConsensusEngine(strategy="crdt")
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0,
                         metadata={"owner": "alice", "env": "prod"})
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         last_modified_at=2000.0,
                         metadata={"owner": "bob", "env": "prod"})
        result = engine.merge_replicas([a, b])
        self.assertIn("metadata.owner", result.conflict_fields)
        self.assertNotIn("metadata.env", result.conflict_fields)
        # 冲突字段保留各副本值
        self.assertIn("_conflict_owner", result.merged_metadata)

    def test_single_replica_no_conflict(self):
        """单一副本无冲突"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0, content="solo")
        result = self.engine.merge_replicas([a])
        self.assertEqual(result.winner, a)
        self.assertEqual(result.losers, [])
        self.assertEqual(result.conflict_fields, [])

    def test_empty_replicas(self):
        """空副本列表安全返回"""
        result = self.engine.merge_replicas([])
        self.assertIsNone(result.winner)
        self.assertEqual(result.merged_content, "")

    def test_inconsistent_memory_id_rejected(self):
        """不同 memory_id 不能合并"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1)
        b = ReplicaState(memory_id="m2", peer_id="bob", version=1)
        with self.assertRaises(ValueError):
            self.engine.merge_replicas([a, b])

    def test_version_chain_appended(self):
        """合并后 version_chain 追加败方记录"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0, content="old",
                         modified_by="alice")
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         last_modified_at=2000.0, content="new",
                         modified_by="bob")
        result = self.engine.merge_replicas([a, b])
        # 链上至少有 2 条（loser + winner）
        self.assertGreaterEqual(len(result.version_chain_appended), 2)
        # 第一条是 loser alice，reason=merge_loser
        loser_entry = next(e for e in result.version_chain_appended
                           if e.get("reason") == "merge_loser")
        self.assertEqual(loser_entry["peer_id"], "alice")
        self.assertEqual(loser_entry["lost_to"], "bob")

    def test_merge_with_existing(self):
        """增量合并：existing vs incoming"""
        from modules.consensus import ReplicaState
        existing = ReplicaState(memory_id="m1", peer_id="alice", version=2,
                                last_modified_at=1000.0, content="current")
        incoming = ReplicaState(memory_id="m1", peer_id="bob", version=3,
                                last_modified_at=2000.0, content="newer")
        result = self.engine.merge_with_existing(existing, incoming)
        self.assertEqual(result.winner.peer_id, "bob")

    def test_detect_conflicts_dry_run(self):
        """冲突检测 dry-run"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         content="foo", category="ops",
                         importance="HIGH", tags=["python"],
                         metadata={"env": "prod"})
        b = ReplicaState(memory_id="m1", peer_id="bob", version=2,
                         content="bar", category="dev",
                         importance="LOW", tags=["db"],
                         metadata={"env": "staging"})
        conflicts = self.engine.detect_conflicts([a, b])
        self.assertIn("content", conflicts)
        self.assertIn("category", conflicts)
        self.assertIn("importance", conflicts)
        self.assertIn("tags", conflicts)
        self.assertIn("metadata.env", conflicts)

    def test_deterministic_merge(self):
        """相同输入产生相同输出（确定性）"""
        from modules.consensus import ReplicaState
        a = ReplicaState(memory_id="m1", peer_id="alice", version=1,
                         last_modified_at=1000.0, content="a")
        b = ReplicaState(memory_id="m1", peer_id="bob", version=1,
                         last_modified_at=1000.0, content="b")
        r1 = self.engine.merge_replicas([a, b])
        r2 = self.engine.merge_replicas([a, b])
        self.assertEqual(r1.winner.peer_id, r2.winner.peer_id)
        self.assertEqual(r1.merged_content, r2.merged_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
