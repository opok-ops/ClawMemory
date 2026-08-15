"""
Test 4: Query engine - fuzzy search, CJK handling, cross-process search
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


def test_fuzzy_search_accuracy():
    """Fuzzy search should find approximate matches"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        mf.add("Python programming language tutorial")
        mf.add("JavaScript frontend development")
        mf.add("Machine learning with TensorFlow")
        mf.add("Database design with PostgreSQL")
        mf.add("Cloud deployment on AWS")

        # Fuzzy: "pythn" should find "Python"
        r = mf.search("pythn", min_relevance=0.1)
        found_python = any("Python" in c.content or "python" in c.content.lower()
                          for c in r.chunks)
        log("fuzzy_typo", found_python, f"found_python={found_python}, total={r.total_found}")

        # Fuzzy: "machne lerning" should find "Machine learning"
        r2 = mf.search("machne lerning", min_relevance=0.1)
        found_ml = any("Machine" in c.content or "machine" in c.content.lower()
                       for c in r2.chunks)
        log("fuzzy_multiple_typos", found_ml, f"found_ml={found_ml}, total={r2.total_found}")

    except Exception as e:
        log("fuzzy_search_accuracy", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cjk_handling():
    """CJK substring handling in search"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        mf.add("\u4eca\u5929\u5f00\u4f1a\u8ba8\u8bba\u4e86Q3\u8ba1\u5212")
        mf.add("\u660e\u5929\u53bb\u5317\u4eac\u51fa\u5dee")
        mf.add("\u9879\u76ee\u8fdb\u5ea6\u6b63\u5e38\u63a8\u8fdb\u4e2d")
        mf.add("\u5ba2\u6237\u53cd\u9988\u4ea7\u54c1\u95ee\u9898")
        mf.add("\u5468\u672b\u56e2\u5efa\u6d3b\u52a8\u5b89\u6392")

        # Search Chinese substring
        r = mf.search("\u5f00\u4f1a", min_relevance=0.1)
        log("cjk_substring", r.total_found > 0, f"found={r.total_found}")

        # Search partial Chinese
        r2 = mf.search("\u5317\u4eac", min_relevance=0.1)
        log("cjk_partial", r2.total_found > 0, f"found={r2.total_found}")

        # Search mixed CJK + English
        r3 = mf.search("Q3\u8ba1\u5212", min_relevance=0.1)
        log("cjk_mixed_english", r3.total_found > 0, f"found={r3.total_found}")

    except Exception as e:
        log("cjk_handling", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cross_process_search():
    """Search in a new MindForge instance should find data written by previous instance"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")

        # Instance 1: write data
        config1 = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf1 = MindForge(config=config1)
        mf1.add("CrossProcessSearchTerm unique data here")
        del mf1

        # Instance 2: read data (simulates new process)
        config2 = MemoryConfig(db_path=db_path, encrypted=False)
        mf2 = MindForge(config=config2)
        r = mf2.search("CrossProcessSearchTerm")
        log("cross_process_search", r.total_found > 0,
            f"found={r.total_found}")

    except Exception as e:
        log("cross_process_search", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_search_with_embedding_disabled():
    """Search with use_embedding=False should still work"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        mf.add("Embedding disabled test content about algorithms")

        r = mf.search("algorithms", use_embedding=False)
        log("search_no_embedding", r.total_found > 0,
            f"found={r.total_found}, strategy={r.strategy_used}")

    except Exception as e:
        log("search_no_embedding", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 4: Query Engine")
    print("=" * 60)

    test_fuzzy_search_accuracy()
    test_cjk_handling()
    test_cross_process_search()
    test_search_with_embedding_disabled()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
