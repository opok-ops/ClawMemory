"""
MindForge v5.5.6 功能测试
覆盖：
- 置顶功能（pin/unpin/list_pinned/add pinned/list pinned filter）
- 批量获取记忆（batch_get）
- 记忆时间线视图（timeline）
- 搜索建议（search_suggestions）
- 添加前去重检测（check_duplicates）
- 按 ID 批量增删标签（add_tags_to_memories / remove_tags_from_memories）
- Bug 修复：fuzzy_search 空查询、rename_tag 大小写不敏感、
  batch_add 支持 expires_at/pinned、stats pinned_count
"""

import os
import time
import tempfile
import pytest

from MindForge import MindForge, __version__
from core.types import MemoryLayer, PrivacyLevel, Importance


@pytest.fixture
def mf():
    """每个测试使用独立的临时数据库"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    instance = MindForge(db_path=db_path, encrypted=False)
    yield instance
    instance.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


# ===== 版本号验证 =====

class TestVersion:
    def test_version_is_556(self):
        """版本号应为 5.5.6"""
        assert __version__ == "5.5.6"

    def test_pyproject_version(self):
        """pyproject.toml 版本号一致"""
        import re
        pyproject_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyproject.toml")
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
        m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.M)
        assert m, "pyproject.toml 中未找到 version"
        assert m.group(1) == "5.5.6"


# ===== 置顶功能 =====

class TestPinning:
    def test_pin_basic(self, mf):
        """基本置顶操作"""
        e = mf.add("测试记忆")
        assert e.pinned is False
        result = mf.pin(e.id)
        assert result is True
        # 重新获取确认
        fetched = mf.get(e.id)
        assert fetched.pinned is True

    def test_unpin(self, mf):
        """取消置顶"""
        e = mf.add("测试记忆")
        mf.pin(e.id)
        assert mf.get(e.id).pinned is True
        result = mf.unpin(e.id)
        assert result is True
        assert mf.get(e.id).pinned is False

    def test_pin_nonexistent(self, mf):
        """置顶不存在的记忆返回 False"""
        result = mf.pin("nonexistent-id")
        assert result is False

    def test_add_with_pinned(self, mf):
        """添加时直接置顶"""
        e = mf.add("置顶记忆", pinned=True)
        assert e.pinned is True
        fetched = mf.get(e.id)
        assert fetched.pinned is True

    def test_list_pinned(self, mf):
        """列出所有置顶记忆"""
        e1 = mf.add("普通记忆")
        e2 = mf.add("置顶记忆1", pinned=True)
        e3 = mf.add("置顶记忆2", pinned=True)
        pinned = mf.list_pinned(limit=10)
        assert len(pinned) == 2
        pinned_ids = {p.id for p in pinned}
        assert e2.id in pinned_ids
        assert e3.id in pinned_ids
        assert e1.id not in pinned_ids

    def test_list_pinned_empty(self, mf):
        """无置顶记忆时返回空列表"""
        mf.add("普通记忆")
        assert mf.list_pinned() == []

    def test_list_filter_pinned(self, mf):
        """list() 支持 pinned 筛选"""
        mf.add("普通1")
        mf.add("置顶1", pinned=True)
        mf.add("普通2")
        mf.add("置顶2", pinned=True)

        pinned_only = mf.list(pinned=True, limit=10)
        assert len(pinned_only) == 2
        for e in pinned_only:
            assert e.pinned is True

        unpinned = mf.list(pinned=False, limit=10)
        assert len(unpinned) == 2
        for e in unpinned:
            assert e.pinned is False

    def test_pinned_priority_in_list(self, mf):
        """置顶记忆在 list() 中优先展示"""
        e1 = mf.add("普通记忆")
        time.sleep(0.01)
        e2 = mf.add("置顶记忆", pinned=True)
        # 默认按 created_at desc，置顶应排第一
        result = mf.list(limit=10, sort_by="created_at", sort_order="desc")
        assert result[0].id == e2.id
        assert result[0].pinned is True

    def test_update_pinned(self, mf):
        """通过 update() 设置 pinned"""
        e = mf.add("测试")
        mf.update(e.id, pinned=True)
        assert mf.get(e.id).pinned is True
        mf.update(e.id, pinned=False)
        assert mf.get(e.id).pinned is False

    def test_pinned_survives_delete_restore(self, mf):
        """置顶状态在删除恢复后保持"""
        e = mf.add("置顶记忆", pinned=True)
        mf.delete(e.id, hard_delete=False)
        mf.restore(e.id)
        restored = mf.get(e.id)
        assert restored is not None
        assert restored.pinned is True


# ===== 批量获取 =====

class TestBatchGet:
    def test_batch_get_basic(self, mf):
        """基本批量获取"""
        e1 = mf.add("记忆A")
        e2 = mf.add("记忆B")
        e3 = mf.add("记忆C")

        result = mf.batch_get([e1.id, e2.id, e3.id])
        assert len(result) == 3
        assert result[0].id == e1.id
        assert result[1].id == e2.id
        assert result[2].id == e3.id

    def test_batch_get_empty(self, mf):
        """空列表返回空"""
        assert mf.batch_get([]) == []
        assert mf.batch_get(None) == []

    def test_batch_get_nonexistent(self, mf):
        """不存在的 ID 被跳过"""
        e1 = mf.add("记忆A")
        result = mf.batch_get([e1.id, "fake-id-1", "fake-id-2"])
        assert len(result) == 1
        assert result[0].id == e1.id

    def test_batch_get_preserves_order(self, mf):
        """保持输入顺序"""
        e1 = mf.add("第一个")
        e2 = mf.add("第二个")
        e3 = mf.add("第三个")
        result = mf.batch_get([e3.id, e1.id, e2.id])
        assert [r.id for r in result] == [e3.id, e1.id, e2.id]

    def test_batch_get_deduplicates(self, mf):
        """重复 ID 去重"""
        e1 = mf.add("记忆A")
        result = mf.batch_get([e1.id, e1.id, e1.id])
        assert len(result) == 1


# ===== 时间线视图 =====

class TestTimeline:
    def test_timeline_basic(self, mf):
        """基本时间线分组"""
        mf.add("今天的记忆")
        result = mf.timeline()
        assert "today" in result
        assert "yesterday" in result
        assert "this_week" in result
        assert "this_month" in result
        assert "earlier" in result
        assert len(result["today"]) >= 1

    def test_timeline_empty(self, mf):
        """空数据库时间线全为空"""
        result = mf.timeline()
        assert result["today"] == []
        assert result["yesterday"] == []
        assert result["earlier"] == []

    def test_timeline_with_category_filter(self, mf):
        """按分类筛选时间线"""
        mf.add("工作记忆", category="work")
        mf.add("生活记忆", category="life")
        result = mf.timeline(category="work")
        assert len(result["today"]) == 1
        assert result["today"][0].category == "work"

    def test_timeline_total_count(self, mf):
        """时间线总数等于记忆数"""
        for i in range(5):
            mf.add(f"记忆{i}")
        result = mf.timeline()
        total = sum(len(v) for v in result.values())
        assert total == 5


# ===== 搜索建议 =====

class TestSearchSuggestions:
    def test_suggestions_tags(self, mf):
        """标签建议"""
        mf.add("A", tags=["python", "coding"])
        mf.add("B", tags=["python", "ai"])
        mf.add("C", tags=["java", "coding"])

        result = mf.search_suggestions("py")
        assert "python" in result["tags"]

    def test_suggestions_categories(self, mf):
        """分类建议"""
        mf.add("A", category="work")
        mf.add("B", category="workout")
        mf.add("C", category="life")

        result = mf.search_suggestions("wor")
        assert "work" in result["categories"]
        assert "workout" in result["categories"]

    def test_suggestions_empty_prefix(self, mf):
        """空前缀返回空"""
        mf.add("A", tags=["python"])
        result = mf.search_suggestions("")
        assert result["tags"] == []
        assert result["categories"] == []

    def test_suggestions_none_prefix(self, mf):
        """None 前缀返回空"""
        result = mf.search_suggestions(None)
        assert result["tags"] == []
        assert result["categories"] == []

    def test_suggestions_no_match(self, mf):
        """无匹配返回空列表"""
        mf.add("A", tags=["python"])
        result = mf.search_suggestions("zzz")
        assert result["tags"] == []
        assert result["categories"] == []

    def test_suggestions_limit(self, mf):
        """限制返回数量"""
        for i in range(15):
            mf.add(f"记忆{i}", tags=[f"tag{i}"])
        result = mf.search_suggestions("tag", limit=5)
        assert len(result["tags"]) <= 5


# ===== 添加前去重检测 =====

class TestCheckDuplicates:
    def test_exact_duplicate(self, mf):
        """完全相同内容检测"""
        mf.add("这是一条测试记忆内容用于去重检测")
        result = mf.check_duplicates("这是一条测试记忆内容用于去重检测")
        assert len(result) >= 1
        assert result[0]["match_type"] == "exact"
        assert result[0]["similarity"] == 1.0

    def test_high_similarity(self, mf):
        """高度相似内容检测"""
        mf.add("Python 是一种非常流行的编程语言，广泛用于数据分析和人工智能")
        result = mf.check_duplicates(
            "Python 是一种非常流行的编程语言，广泛用于数据分析",
            similarity_threshold=0.7
        )
        assert len(result) >= 1

    def test_no_duplicate(self, mf):
        """不相似内容返回空"""
        mf.add("今天天气真好，适合出去散步")
        result = mf.check_duplicates("量子力学中的薛定谔方程")
        assert result == []

    def test_empty_content(self, mf):
        """空内容返回空"""
        mf.add("测试")
        assert mf.check_duplicates("") == []
        assert mf.check_duplicates(None) == []

    def test_category_filter(self, mf):
        """按分类筛选去重"""
        mf.add("重复内容测试", category="work")
        mf.add("重复内容测试", category="life")
        result = mf.check_duplicates("重复内容测试", category="work")
        assert len(result) == 1
        assert result[0]["entry"].category == "work"

    def test_threshold(self, mf):
        """阈值控制"""
        mf.add("完全不同的内容一")
        # 低阈值应该能匹配到部分相似
        result_low = mf.check_duplicates("完全不同的内容", similarity_threshold=0.5)
        # 高阈值可能匹配不到
        result_high = mf.check_duplicates("完全不同的内容", similarity_threshold=0.99)
        assert len(result_low) >= len(result_high)


# ===== 按 ID 批量增删标签 =====

class TestBatchTagOperations:
    def test_add_tags_basic(self, mf):
        """基本批量添加标签"""
        e1 = mf.add("A", tags=["existing"])
        e2 = mf.add("B")
        count = mf.add_tags_to_memories([e1.id, e2.id], ["new-tag"])
        assert count == 2
        assert "new-tag" in mf.get(e1.id).tags
        assert "new-tag" in mf.get(e2.id).tags

    def test_add_tags_no_duplicate(self, mf):
        """添加已有标签不重复"""
        e = mf.add("A", tags=["mytag"])
        count = mf.add_tags_to_memories([e.id], ["mytag"])
        assert count == 0  # 无变化
        assert mf.get(e.id).tags.count("mytag") == 1

    def test_add_tags_empty(self, mf):
        """空参数返回 0"""
        assert mf.add_tags_to_memories([], ["tag"]) == 0
        e = mf.add("A")
        assert mf.add_tags_to_memories([e.id], []) == 0

    def test_add_tags_nonexistent(self, mf):
        """不存在的 ID 跳过"""
        e = mf.add("A")
        count = mf.add_tags_to_memories([e.id, "fake-id"], ["tag"])
        assert count == 1

    def test_remove_tags_basic(self, mf):
        """基本批量移除标签"""
        e1 = mf.add("A", tags=["tag1", "tag2"])
        e2 = mf.add("B", tags=["tag1", "tag3"])
        count = mf.remove_tags_from_memories([e1.id, e2.id], ["tag1"])
        assert count == 2
        assert "tag1" not in mf.get(e1.id).tags
        assert "tag1" not in mf.get(e2.id).tags
        assert "tag2" in mf.get(e1.id).tags

    def test_remove_tags_case_insensitive(self, mf):
        """移除标签大小写不敏感"""
        e = mf.add("A", tags=["MyTag", "other"])
        count = mf.remove_tags_from_memories([e.id], ["mytag"])
        assert count == 1
        tags = mf.get(e.id).tags
        assert "MyTag" not in tags
        assert "other" in tags

    def test_remove_tags_empty(self, mf):
        """空参数返回 0"""
        assert mf.remove_tags_from_memories([], ["tag"]) == 0


# ===== Bug 修复测试 =====

class TestFuzzySearchFix:
    def test_fuzzy_search_none_query(self, mf):
        """fuzzy_search None 查询不崩溃"""
        mf.add("测试内容")
        result = mf.fuzzy_search(None)
        assert result == []

    def test_fuzzy_search_empty_query(self, mf):
        """fuzzy_search 空字符串不崩溃"""
        mf.add("测试内容")
        result = mf.fuzzy_search("")
        assert result == []

    def test_fuzzy_search_whitespace_query(self, mf):
        """fuzzy_search 纯空白不崩溃"""
        mf.add("测试内容")
        result = mf.fuzzy_search("   ")
        assert result == []

    def test_fuzzy_search_normal(self, mf):
        """fuzzy_search 正常工作"""
        mf.add("Python 编程教程")
        result = mf.fuzzy_search("python", limit=10)
        assert len(result) >= 1


class TestRenameTagFix:
    def test_rename_tag_case_insensitive(self, mf):
        """重命名标签大小写不敏感"""
        e = mf.add("测试", tags=["MyTag", "other"])
        count = mf.rename_tag("mytag", "RenamedTag")
        assert count == 1
        tags = mf.get(e.id).tags
        assert "RenamedTag" in tags
        assert "MyTag" not in tags

    def test_rename_tag_empty_old(self, mf):
        """空旧标签名返回 0"""
        mf.add("测试", tags=["tag"])
        assert mf.rename_tag("", "new") == 0

    def test_rename_tag_none(self, mf):
        """None 参数返回 0"""
        assert mf.rename_tag(None, "new") == 0
        assert mf.rename_tag("old", None) == 0

    def test_rename_tag_dedup_after_rename(self, mf):
        """重命名后自动去重"""
        e = mf.add("测试", tags=["TagA", "taga", "other"])
        count = mf.rename_tag("taga", "TagA")
        assert count == 1
        tags = mf.get(e.id).tags
        assert tags.count("TagA") == 1


class TestBatchAddFix:
    def test_batch_add_with_pinned(self, mf):
        """batch_add 支持 pinned"""
        count = mf.batch_add([
            {"content": "普通记忆", "category": "test"},
            {"content": "置顶记忆", "category": "test", "pinned": True},
        ])
        assert count == 2
        pinned = mf.list_pinned()
        assert len(pinned) == 1

    def test_batch_add_with_expires_at(self, mf):
        """batch_add 支持 expires_at"""
        future = time.time() + 3600
        count = mf.batch_add([
            {"content": "有过期时间", "expires_at": future},
            {"content": "永不过期"},
        ])
        assert count == 2
        # 第一条还未过期，应能获取到
        all_memories = mf.list(limit=10)
        assert len(all_memories) == 2

    def test_batch_add_with_metadata(self, mf):
        """batch_add 支持 metadata"""
        count = mf.batch_add([
            {"content": "带元数据", "metadata": {"source": "test", "priority": 1}},
        ])
        assert count == 1
        entry = mf.list(limit=1)[0]
        assert entry.metadata.get("source") == "test"


class TestStatsPinnedCount:
    def test_stats_includes_pinned_count(self, mf):
        """stats() 包含 pinned_count"""
        mf.add("普通")
        mf.add("置顶", pinned=True)
        stats = mf.stats()
        assert "pinned_count" in stats
        assert stats["pinned_count"] == 1

    def test_stats_pinned_count_excludes_trash(self, mf):
        """pinned_count 排除回收站"""
        e = mf.add("置顶", pinned=True)
        mf.delete(e.id, hard_delete=False)
        stats = mf.stats()
        assert stats["pinned_count"] == 0


# ===== v5.5.6 Bug 修复追加测试 =====

class TestCheckDuplicatesHtmlSanitize:
    """Bug 1: check_duplicates 未对输入做 HTML 消毒"""

    def test_html_content_matches_sanitized(self, mf):
        """含 HTML 标签的输入应匹配消毒后存储的内容"""
        mf.add("bold text")
        result = mf.check_duplicates("<b>bold</b> text")
        assert len(result) >= 1
        assert result[0]["similarity"] == 1.0

    def test_html_content_partial_match(self, mf):
        """HTML 消毒后部分匹配（降低阈值验证）"""
        mf.add("Python 编程教程")
        # 消毒后输入为 "Python 编程"，与存储内容高度相似
        result = mf.check_duplicates("<i>Python</i> 编程", similarity_threshold=0.5)
        assert len(result) >= 1

    def test_script_tag_sanitized(self, mf):
        """script 标签被消毒（标签移除，内容保留）"""
        mf.add("alert(1)安全内容")
        # 消毒后 <script>alert(1)</script>安全内容 → alert(1)安全内容
        result = mf.check_duplicates("<script>alert(1)</script>安全内容")
        assert len(result) >= 1
        assert result[0]["similarity"] == 1.0


class TestAddTagsCaseInsensitive:
    """Bug 2: add_tags_to_ids 大小写敏感"""

    def test_add_tags_case_insensitive_dedup(self, mf):
        """添加大小写不同的已有标签不应重复"""
        e = mf.add("测试", tags=["MyTag"])
        count = mf.add_tags_to_memories([e.id], ["mytag"])
        assert count == 0  # 已存在（大小写不敏感），无变化
        tags = mf.get(e.id).tags
        assert len(tags) == 1
        assert tags[0] == "MyTag"  # 保留原始大小写

    def test_add_tags_new_case_insensitive(self, mf):
        """添加新标签（大小写不同）正常工作"""
        e = mf.add("测试", tags=["MyTag"])
        count = mf.add_tags_to_memories([e.id], ["OTHER"])
        assert count == 1
        tags = mf.get(e.id).tags
        assert "MyTag" in tags
        assert "OTHER" in tags

    def test_add_tags_preserves_original_case(self, mf):
        """去重时保留已有标签的原始大小写"""
        e = mf.add("测试", tags=["Important"])
        mf.add_tags_to_memories([e.id], ["important"])
        tags = mf.get(e.id).tags
        assert "Important" in tags
        assert "important" not in tags


class TestBatchAddTagsOrderPreserving:
    """Bug 3: batch_add_tags 使用 set 去重不保留顺序"""

    def test_batch_add_tags_preserves_order(self, mf):
        """batch_add_tags 应保留标签顺序"""
        e = mf.add("测试", tags=["a", "b", "c"])
        # 通过 storage 层直接调用 batch_add_tags
        count = mf._storage.batch_add_tags([e.id], ["d", "e"])
        assert count == 1
        tags = mf.get(e.id).tags
        assert tags == ["a", "b", "c", "d", "e"]

    def test_batch_add_tags_no_duplicate(self, mf):
        """batch_add_tags 不重复添加已有标签"""
        e = mf.add("测试", tags=["a", "b"])
        count = mf._storage.batch_add_tags([e.id], ["b", "c"])
        assert count == 1
        tags = mf.get(e.id).tags
        assert tags == ["a", "b", "c"]

    def test_batch_add_tags_case_insensitive(self, mf):
        """batch_add_tags 大小写不敏感去重"""
        e = mf.add("测试", tags=["MyTag"])
        count = mf._storage.batch_add_tags([e.id], ["mytag", "new"])
        assert count == 1
        tags = mf.get(e.id).tags
        assert tags == ["MyTag", "new"]


class TestBulkUpdateAddTagsConsistency:
    """bulk_update_by_filter add_tags 大小写一致性"""

    def test_bulk_update_add_tags_case_insensitive(self, mf):
        """bulk_update add_tags 大小写不敏感"""
        mf.add("A", category="test", tags=["MyTag"])
        count = mf.bulk_update_by_filter(
            category="test",
            updates={"add_tags": ["mytag", "new"]}
        )
        assert count == 1
        entry = mf.list(category="test")[0]
        assert "MyTag" in entry.tags
        assert "new" in entry.tags
        assert "mytag" not in entry.tags
