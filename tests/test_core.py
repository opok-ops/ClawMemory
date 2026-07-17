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


if __name__ == "__main__":
    unittest.main(verbosity=2)
