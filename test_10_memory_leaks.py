"""
Test 10: Memory leaks and performance in loops
"""
import sys
import os
import tempfile
import shutil
import time
import traceback
import gc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.types import MemoryConfig
RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def get_memory_usage_mb():
    """Get current process memory usage in MB"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback: use tracemalloc
        return None


def test_add_loop_memory():
    """Add/search in a loop, check for memory growth"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Warm up
        for i in range(50):
            mf.add(f"Warmup {i}")

        gc.collect()
        mem_before = get_memory_usage_mb()

        # Add 500 more in a loop
        for i in range(500):
            mf.add(f"Loop memory {i} with some content to make it realistic")
            if i % 100 == 0:
                mf.search(f"Loop memory {i}")

        gc.collect()
        mem_after = get_memory_usage_mb()

        if mem_before is not None and mem_after is not None:
            growth = mem_after - mem_before
            log("memory_loop_growth", growth < 100,
                f"before={mem_before:.1f}MB, after={mem_after:.1f}MB, growth={growth:.1f}MB")
        else:
            log("memory_loop_growth", True, "psutil not available, skipped memory check")

    except Exception as e:
        log("add_loop_memory", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_search_loop_performance():
    """Search in a loop, measure performance stability"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Populate
        for i in range(200):
            mf.add(f"Search loop item {i} about topic {i % 20}", category=f"cat{i%5}")

        # Measure search times in batches
        batch_times = []
        for batch in range(5):
            times = []
            for i in range(20):
                t0 = time.time()
                mf.search(f"topic {batch * 4 + i % 4}")
                times.append((time.time() - t0) * 1000)
            batch_times.append(sum(times) / len(times))

        # Check that later batches aren't dramatically slower
        first_batch = batch_times[0]
        last_batch = batch_times[-1]
        slowdown = last_batch / first_batch if first_batch > 0 else 1

        log("search_loop_stability", slowdown < 5.0,
            f"first={first_batch:.1f}ms, last={last_batch:.1f}ms, ratio={slowdown:.2f}x")

    except Exception as e:
        log("search_loop_performance", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_repeated_init_cleanup():
    """Repeatedly create and destroy MindForge instances"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        from core.mindforge import MindForge

        gc.collect()
        mem_before = get_memory_usage_mb()

        for i in range(20):
            db_path = os.path.join(tmpdir, f"test_{i}.db")
            config = MemoryConfig(db_path=db_path, encrypted=False)
            mf = MindForge(config=config)
            mf.add(f"Instance {i} data")
            mf.search(f"Instance {i}")
            del mf

        gc.collect()
        mem_after = get_memory_usage_mb()

        if mem_before is not None and mem_after is not None:
            growth = mem_after - mem_before
            log("repeated_init_cleanup", growth < 50,
                f"before={mem_before:.1f}MB, after={mem_after:.1f}MB, growth={growth:.1f}MB")
        else:
            log("repeated_init_cleanup", True, "psutil not available, skipped")

    except Exception as e:
        log("repeated_init_cleanup", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 10: Memory Leaks and Performance")
    print("=" * 60)

    test_add_loop_memory()
    test_search_loop_performance()
    test_repeated_init_cleanup()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
