"""
Test 2: Storage engine - thread safety, FTS5 sync, large dataset performance
"""
import sys
import os
import tempfile
import shutil
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.types import MemoryConfig, MemoryLayer
RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_thread_safety():
    """Multiple threads reading/writing simultaneously"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        errors = []
        added_ids = []
        lock = threading.Lock()

        def writer(thread_id):
            try:
                for i in range(20):
                    e = mf.add(f"Thread {thread_id} memory {i}", category=f"t{thread_id}")
                    with lock:
                        added_ids.append(e.id)
            except Exception as ex:
                with lock:
                    errors.append(f"Writer {thread_id}: {ex}")

        def reader(thread_id):
            try:
                for i in range(20):
                    mf.search(f"Thread {thread_id}")
                    time.sleep(0.001)
            except Exception as ex:
                with lock:
                    errors.append(f"Reader {thread_id}: {ex}")

        threads = []
        for t in range(4):
            threads.append(threading.Thread(target=writer, args=(t,)))
            threads.append(threading.Thread(target=reader, args=(t,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        log("thread_safety_no_errors", len(errors) == 0,
            f"errors={errors[:3]}" if errors else "8 threads OK")
        log("thread_safety_all_written", len(added_ids) == 80,
            f"expected=80, got={len(added_ids)}")

    except Exception as e:
        log("thread_safety", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fts5_sync():
    """FTS5 index syncs after updates"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Add memory
        e = mf.add("UniqueSearchTerm12345 for FTS5 testing")

        # Search immediately - should find via FTS5
        r = mf.search("UniqueSearchTerm12345")
        log("fts5_sync_after_add", r.total_found > 0, f"found={r.total_found}")

        # Update memory with new content
        mf.update(e.id, content="AnotherUniqueTerm67890 updated content")

        # Search for new term
        r2 = mf.search("AnotherUniqueTerm67890")
        log("fts5_sync_after_update", r2.total_found > 0, f"found={r2.total_found}")

    except Exception as e:
        log("fts5_sync", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_large_dataset_performance():
    """Add 1000+ memories, measure search times"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Add 1000 memories
        start = time.time()
        for i in range(1000):
            cat = ["tech", "food", "travel", "work", "life"][i % 5]
            mf.add(f"Memory item {i} about {cat} topic number {i % 50}",
                   category=cat, tags=[f"tag{i % 100}"])
        add_time = time.time() - start
        log("large_dataset_add_1000", True, f"added 1000 in {add_time:.2f}s")

        # Search performance
        search_times = []
        for q in ["tech topic", "food item", "travel memory", "work number", "life topic 42"]:
            t0 = time.time()
            r = mf.search(q, max_results=10)
            elapsed = (time.time() - t0) * 1000
            search_times.append(elapsed)

        avg_search = sum(search_times) / len(search_times)
        max_search = max(search_times)
        log("large_dataset_search_avg", avg_search < 500,
            f"avg={avg_search:.1f}ms, max={max_search:.1f}ms")
        log("large_dataset_search_max", max_search < 2000,
            f"max={max_search:.1f}ms < 2000ms")

    except Exception as e:
        log("large_dataset_performance", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 2: Storage Engine")
    print("=" * 60)

    test_thread_safety()
    test_fts5_sync()
    test_large_dataset_performance()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
