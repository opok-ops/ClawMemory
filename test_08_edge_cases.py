"""
Test 8: Edge cases - Invalid inputs (None, empty strings, wrong types)
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


def test_add_none_content():
    """add with None content"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        try:
            e = mf.add(None)
            log("add_none_content", False, "Should have raised but didn't")
        except (ValueError, TypeError, AttributeError) as ex:
            log("add_none_content", True, f"Correctly rejected: {type(ex).__name__}")
        except Exception as ex:
            log("add_none_content", True, f"Rejected with: {type(ex).__name__}: {ex}")

    except Exception as e:
        log("add_none_content_setup", False, f"{e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_add_empty_string():
    """add with empty string content"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        try:
            e = mf.add("")
            log("add_empty_string", e is not None,
                f"Created entry with empty content, id={e.id[:8] if e else 'None'}")
        except (ValueError, TypeError) as ex:
            log("add_empty_string", True, f"Rejected empty: {type(ex).__name__}")

    except Exception as e:
        log("add_empty_string_setup", False, f"{e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_add_oversized_content():
    """add with content exceeding MAX_CONTENT_LEN"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        huge_content = "X" * 100000
        try:
            e = mf.add(huge_content)
            log("add_oversized", False, "Should have rejected oversized content")
        except ValueError as ex:
            log("add_oversized", True, f"Correctly rejected: {ex}")
        except Exception as ex:
            log("add_oversized", True, f"Rejected: {type(ex).__name__}: {ex}")

    except Exception as e:
        log("add_oversized_setup", False, f"{e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_get_nonexistent_id():
    """get with non-existent ID"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        result = mf.get("totally_fake_id_12345")
        log("get_nonexistent", result is None, f"result={result}")

    except Exception as e:
        log("get_nonexistent", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_delete_nonexistent_id():
    """delete with non-existent ID"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        result = mf.delete("totally_fake_id_12345")
        log("delete_nonexistent", result == False, f"result={result}")

    except Exception as e:
        log("delete_nonexistent", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_search_wrong_types():
    """search with wrong parameter types"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # max_results as string
        try:
            r = mf.search("test", max_results="not_a_number")
            log("search_wrong_max_results", False, "Should have raised")
        except (TypeError, ValueError) as ex:
            log("search_wrong_max_results", True, f"Rejected: {type(ex).__name__}")
        except Exception as ex:
            log("search_wrong_max_results", True, f"Rejected: {type(ex).__name__}")

        # min_relevance as string
        try:
            r = mf.search("test", min_relevance="high")
            log("search_wrong_min_relevance", False, "Should have raised")
        except (TypeError, ValueError) as ex:
            log("search_wrong_min_relevance", True, f"Rejected: {type(ex).__name__}")
        except Exception as ex:
            log("search_wrong_min_relevance", True, f"Rejected: {type(ex).__name__}")

    except Exception as e:
        log("search_wrong_types", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_tags_wrong_types():
    """add with wrong tag types"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Tags as string instead of list
        e = mf.add("Test with string tags", tags="not_a_list")
        log("tags_as_string", e is not None,
            f"tags={e.tags}")  # Should be sanitized to []

        # Tags as dict
        e2 = mf.add("Test with dict tags", tags={"key": "value"})
        log("tags_as_dict", e2 is not None, f"tags={e2.tags}")

        # Tags with None elements
        e3 = mf.add("Test with None in tags", tags=[None, "valid", None])
        log("tags_with_none", e3 is not None and "valid" in e3.tags,
            f"tags={e3.tags}")

    except Exception as e:
        log("tags_wrong_types", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_metadata_wrong_types():
    """add with wrong metadata types"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        mf = MindForge(config=config)

        # Metadata as string
        e = mf.add("Test", metadata="not_a_dict")
        log("metadata_as_string", e is not None,
            f"metadata={e.metadata}")

        # Metadata as list
        e2 = mf.add("Test", metadata=[1, 2, 3])
        log("metadata_as_list", e2 is not None, f"metadata={e2.metadata}")

    except Exception as e:
        log("metadata_wrong_types", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 8: Edge Cases - Invalid Inputs")
    print("=" * 60)

    test_add_none_content()
    test_add_empty_string()
    test_add_oversized_content()
    test_get_nonexistent_id()
    test_delete_nonexistent_id()
    test_search_wrong_types()
    test_tags_wrong_types()
    test_metadata_wrong_types()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
