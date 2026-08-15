"""
Test 9: Race conditions and concurrent access
"""
import sys
import os
import tempfile
import shutil
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.types import MemoryConfig
RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_concurrent_add_search():
    """Concurrent add and search operations"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        errors = []
        lock = threading.Lock()

        def adder():
            try:
                for i in range(50):
                    mf.add(f"Concurrent add {i} unique_term_{i}", category="test")
            except Exception as ex:
                with lock:
                    errors.append(f"adder: {ex}")

        def searcher():
            try:
                for i in range(50):
                    mf.search(f"Concurrent add {i}")
                    time.sleep(0.001)
            except Exception as ex:
                with lock:
                    errors.append(f"searcher: {ex}")

        def updater():
            try:
                entries = mf.list(limit=10)
                for e in entries:
                    mf.update(e.id, content=f"Updated by updater")
            except Exception as ex:
                with lock:
                    errors.append(f"updater: {ex}")

        threads = [
            threading.Thread(target=adder),
            threading.Thread(target=searcher),
            threading.Thread(target=searcher),
            threading.Thread(target=updater),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        log("concurrent_no_errors", len(errors) == 0,
            f"errors={errors[:3]}" if errors else "4 threads OK")

    except Exception as e:
        log("concurrent_add_search", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_concurrent_delete_and_search():
    """Concurrent delete and search"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Pre-populate
        ids = []
        for i in range(100):
            e = mf.add(f"Delete test {i}", category="del_test")
            ids.append(e.id)

        errors = []
        lock = threading.Lock()

        def deleter():
            try:
                for mid in ids[:50]:
                    mf.delete(mid, hard_delete=True)
            except Exception as ex:
                with lock:
                    errors.append(f"deleter: {ex}")

        def searcher():
            try:
                for i in range(50):
                    mf.search(f"Delete test {i}")
            except Exception as ex:
                with lock:
                    errors.append(f"searcher: {ex}")

        threads = [
            threading.Thread(target=deleter),
            threading.Thread(target=searcher),
            threading.Thread(target=searcher),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        log("concurrent_delete_search", len(errors) == 0,
            f"errors={errors[:3]}" if errors else "OK")

    except Exception as e:
        log("concurrent_delete_search", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_concurrent_same_memory_update():
    """Multiple threads updating the same memory"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        e = mf.add("Original content for concurrent update test")

        errors = []
        lock = threading.Lock()

        def updater(thread_id):
            try:
                for i in range(20):
                    mf.update(e.id, content=f"Thread {thread_id} update {i}")
            except Exception as ex:
                with lock:
                    errors.append(f"updater {thread_id}: {ex}")

        threads = [threading.Thread(target=updater, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Should not crash, final content should be from one of the threads
        final = mf.get(e.id)
        log("concurrent_same_update_no_crash", len(errors) == 0,
            f"errors={errors[:3]}" if errors else "4 threads OK")
        log("concurrent_same_update_final_exists", final is not None,
            f"final content exists")

    except Exception as e:
        log("concurrent_same_update", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 9: Race Conditions and Concurrent Access")
    print("=" * 60)

    test_concurrent_add_search()
    test_concurrent_delete_and_search()
    test_concurrent_same_memory_update()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
