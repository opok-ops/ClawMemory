"""ClawMemory v5.0 单元测试"""
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


class TestClawMemory(unittest.TestCase):
    """ClawMemory 主类测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init(self):
        from core.clawmemory import ClawMemory

        cm = ClawMemory(db_path=self.db_path, encrypted=False)
        self.assertIsNotNone(cm)
        self.assertIsNotNone(cm.storage)
        self.assertIsNotNone(cm.index)
        self.assertIsNotNone(cm.query)
        cm.close()

    def test_add_and_search(self):
        from core.clawmemory import ClawMemory

        cm = ClawMemory(db_path=self.db_path, encrypted=False)

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
        from core.clawmemory import ClawMemory
        import json

        cm = ClawMemory(db_path=self.db_path, encrypted=False)

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
        cm2 = ClawMemory(db_path=new_db, encrypted=False)
        stats = cm2.import_json(export_path)
        self.assertEqual(stats["imported"], 2)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["failed"], 0)

        results = cm2.search("导出测试", max_results=10)
        self.assertEqual(results.total_found, 2)

        cm.close()
        cm2.close()

    def test_export_csv(self):
        from core.clawmemory import ClawMemory
        import csv

        cm = ClawMemory(db_path=self.db_path, encrypted=False)

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
        from core.clawmemory import ClawMemory
        from modules.personality import PersonalityEngine

        cm = ClawMemory(db_path=self.db_path, encrypted=False)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
