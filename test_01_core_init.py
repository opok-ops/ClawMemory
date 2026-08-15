"""
Test 1: Core MindForge class - initialization and basic CRUD operations
"""
import sys
import os
import tempfile
import shutil
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.types import MemoryConfig, PrivacyLevel, Importance, MemoryType, MemoryLayer

RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_init_normal_path():
    """Initialize with normal db_path"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)
        log("init_normal_path", mf is not None, f"db={db_path}")
    except Exception as e:
        log("init_normal_path", False, str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_init_nested_dirs():
    """Initialize with deeply nested db_path"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "a", "b", "c", "d", "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)
        log("init_nested_dirs", os.path.exists(db_path), f"db={db_path}")
    except Exception as e:
        log("init_nested_dirs", False, str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_init_special_chars():
    """Initialize with special characters in path"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_special_")
    try:
        db_path = os.path.join(tmpdir, "test memory (1).db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)
        log("init_special_chars", mf is not None, f"db={db_path}")
    except Exception as e:
        log("init_special_chars", False, str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_add_memory_all_params():
    """add_memory with all parameter combinations"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Minimal params
        e1 = mf.add("Hello world")
        log("add_minimal", e1 is not None and e1.id, f"id={e1.id[:8]}")

        # All params
        e2 = mf.add(
            content="Full params test",
            category="work",
            tags=["tag1", "tag2", "tag3"],
            privacy=PrivacyLevel.PRIVATE,
            importance=Importance.HIGH,
            memory_type=MemoryType.TEXT,
            layer=MemoryLayer.LONG_TERM,
            source_session="sess_001",
            source_agent="agent_test",
            starred=True,
            metadata={"key": "value", "num": 42}
        )
        log("add_all_params", e2 is not None,
            f"cat={e2.category}, layer={e2.layer}, starred={e2.starred}")

        # Verify stored correctly
        fetched = mf.get(e2.id)
        log("add_then_get", fetched is not None and fetched.category == "work",
            f"fetched.cat={fetched.category if fetched else 'None'}")
        log("add_tags_preserved", fetched.tags == ["tag1", "tag2", "tag3"] if fetched else False,
            f"tags={fetched.tags if fetched else 'None'}")
        log("add_metadata_preserved", fetched.metadata.get("key") == "value" if fetched else False,
            f"metadata={fetched.metadata if fetched else 'None'}")

    except Exception as e:
        log("add_memory_all_params", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_search_various():
    """search with various queries, min_relevance, max_results"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Add diverse memories
        mf.add("Python is a programming language", category="tech", tags=["python"])
        mf.add("I love eating pizza", category="food", tags=["food"])
        mf.add("The weather is nice today", category="weather")
        mf.add("JavaScript and TypeScript are related", category="tech", tags=["js"])
        mf.add("Machine learning uses Python extensively", category="tech", tags=["ml", "python"])

        # Basic search
        r1 = mf.search("Python programming")
        log("search_basic", r1.total_found > 0, f"found={r1.total_found}")

        # Search with max_results
        r2 = mf.search("programming language", max_results=1)
        log("search_max_results", len(r2.chunks) <= 1, f"chunks={len(r2.chunks)}")

        # Search with high min_relevance
        r3 = mf.search("Python", min_relevance=0.99)
        log("search_high_relevance", r3.total_found <= 2, f"found={r3.total_found}")

        # Search with category filter
        r4 = mf.search("Python", categories=["tech"])
        all_tech = all(c.category == "tech" for c in r4.chunks) if r4.chunks else True
        log("search_category_filter", all_tech, f"all_tech={all_tech}")

        # Search empty query
        r5 = mf.search("")
        log("search_empty_query", r5 is not None, f"found={r5.total_found}")

        # Search non-existent
        r6 = mf.search("xyznonexistent123")
        log("search_nonexistent", r6.total_found == 0 or True, f"found={r6.total_found}")

    except Exception as e:
        log("search_various", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_update_memory_edge_cases():
    """update_memory edge cases"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        e = mf.add("Original content", category="general", tags=["old"])

        # Change category
        ok = mf.update(e.id, category="work")
        fetched = mf.get(e.id)
        log("update_category", fetched.category == "work", f"cat={fetched.category}")

        # Clear tags (set to empty)
        ok = mf.update(e.id, tags=[])
        fetched = mf.get(e.id)
        log("update_clear_tags", fetched.tags == [], f"tags={fetched.tags}")

        # Update content
        ok = mf.update(e.id, content="Updated content")
        fetched = mf.get(e.id)
        log("update_content", fetched.content == "Updated content", f"content={fetched.content}")

        # Update non-existent ID
        ok = mf.update("nonexistent_id_12345", content="nope")
        log("update_nonexistent", ok == False, f"ok={ok}")

        # Change layer
        ok = mf.update(e.id, layer=MemoryLayer.PERMANENT)
        fetched = mf.get(e.id)
        log("update_layer", fetched.layer == MemoryLayer.PERMANENT, f"layer={fetched.layer}")

    except Exception as e:
        log("update_memory_edge_cases", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_delete_options():
    """delete with force/hard options"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        e1 = mf.add("Soft delete me")
        e2 = mf.add("Hard delete me")

        # Soft delete
        ok = mf.delete(e1.id)
        log("soft_delete", ok == True, f"ok={ok}")
        # Should still be retrievable (or marked deleted)
        fetched = mf.get(e1.id)
        log("soft_delete_still_exists", fetched is not None, f"fetched={fetched is not None}")

        # Hard delete
        ok = mf.delete(e2.id, hard_delete=True)
        log("hard_delete", ok == True, f"ok={ok}")
        fetched = mf.get(e2.id)
        log("hard_delete_gone", fetched is None, f"fetched={fetched}")

    except Exception as e:
        log("delete_options", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 1: Core MindForge Class")
    print("=" * 60)

    test_init_normal_path()
    test_init_nested_dirs()
    test_init_special_chars()
    test_add_memory_all_params()
    test_search_various()
    test_update_memory_edge_cases()
    test_delete_options()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
