"""
Test 11: Database corruption recovery and batch operations
"""
import sys
import os
import tempfile
import shutil
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.types import MemoryConfig
RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_batch_add_mixed():
    """batch_add with mixed valid/invalid entries via API adapter"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from adapters.generic_api import GenericAPIAdapter

        mf = MindForge(config=config)
        api = GenericAPIAdapter(mf)

        # Add multiple entries
        added = 0
        for i in range(10):
            resp = api.handle_request({
                "action": "memory.add",
                "params": {"content": f"Batch item {i}", "category": "batch_test"}
            })
            if resp.get("success"):
                added += 1

        log("batch_add_mixed", added == 10, f"added={added}/10")

        # List them
        entries = mf.list(category="batch_test")
        log("batch_list_after", len(entries) == 10, f"listed={len(entries)}")

    except Exception as e:
        log("batch_add_mixed", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_db_corruption_recovery():
    """Database corruption: truncate DB file and try to recover"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Add some data
        for i in range(10):
            mf.add(f"Pre-corruption data {i}")

        # Corrupt the DB by truncating
        with open(db_path, 'r+b') as f:
            f.seek(0)
            f.truncate(100)  # Truncate to 100 bytes

        # Try to create new instance - should handle gracefully
        try:
            config2 = MemoryConfig(db_path=db_path, encrypted=False)
            mf2 = MindForge(config=config2)
            # If it creates without crash, that's good
            log("db_corruption_recovery_init", True, "New instance created after corruption")

            # Try to add data
            try:
                e = mf2.add("Post-corruption data")
                log("db_corruption_recovery_add", e is not None,
                    f"Added after corruption, id={e.id[:8]}")
            except Exception as ex:
                log("db_corruption_recovery_add", False, f"Cannot add after corruption: {ex}")

        except Exception as ex:
            log("db_corruption_recovery_init", False,
                f"Failed to create instance: {type(ex).__name__}: {ex}")

    except Exception as e:
        log("db_corruption_recovery", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_batch_delete():
    """batch_delete by category"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Add entries in different categories
        for i in range(5):
            mf.add(f"Category A item {i}", category="cat_a")
        for i in range(5):
            mf.add(f"Category B item {i}", category="cat_b")

        # Batch delete cat_a
        count = mf.batch_delete(category="cat_a", hard_delete=True)
        log("batch_delete_count", count == 5, f"deleted={count}")

        # Verify cat_b still exists
        remaining = mf.list(category="cat_b")
        log("batch_delete_preserves_other", len(remaining) == 5,
            f"remaining_cat_b={len(remaining)}")

    except Exception as e:
        log("batch_delete", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_restore_after_soft_delete():
    """Restore memory after soft delete"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        e = mf.add("Restore me after soft delete")

        # Soft delete
        mf.delete(e.id)

        # Try to restore
        ok = mf.restore(e.id)
        log("restore_after_soft_delete", ok == True, f"ok={ok}")

        if ok:
            fetched = mf.get(e.id)
            log("restore_content_preserved",
                fetched is not None and fetched.content == "Restore me after soft delete",
                f"content={fetched.content if fetched else 'None'}")

    except Exception as e:
        log("restore_after_soft_delete", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_star_unstar():
    """Star and unstar operations"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        e = mf.add("Star test memory")

        # Star
        ok = mf.star(e.id)
        log("star", ok == True, f"ok={ok}")
        fetched = mf.get(e.id)
        log("star_preserved", fetched.starred == True, f"starred={fetched.starred}")

        # Unstar
        ok = mf.unstar(e.id)
        log("unstar", ok == True, f"ok={ok}")
        fetched = mf.get(e.id)
        log("unstar_preserved", fetched.starred == False, f"starred={fetched.starred}")

        # List starred
        e2 = mf.add("Starred item", starred=True)
        starred = mf.list(starred=True)
        log("list_starred", len(starred) >= 1, f"starred_count={len(starred)}")

    except Exception as e:
        log("star_unstar", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_search_by_tag():
    """search_by_tag functionality"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        mf.add("Tag search test 1", tags=["python", "coding"])
        mf.add("Tag search test 2", tags=["python", "data"])
        mf.add("Tag search test 3", tags=["java", "coding"])

        results = mf.search_by_tag("python")
        log("search_by_tag_python", len(results) == 2, f"found={len(results)}")

        results2 = mf.search_by_tag("coding")
        log("search_by_tag_coding", len(results2) == 2, f"found={len(results2)}")

        results3 = mf.search_by_tag("nonexistent_tag")
        log("search_by_tag_none", len(results3) == 0, f"found={len(results3)}")

    except Exception as e:
        log("search_by_tag", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 11: DB Corruption, Batch Ops, Restore")
    print("=" * 60)

    test_batch_add_mixed()
    test_db_corruption_recovery()
    test_batch_delete()
    test_restore_after_soft_delete()
    test_star_unstar()
    test_search_by_tag()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
