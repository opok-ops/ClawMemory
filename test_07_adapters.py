"""
Test 7: Adapters - GenericAPI and ClaudeCodeAdapter
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


def test_generic_api_add():
    """GenericAPI: add memory via API"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from adapters.generic_api import GenericAPIAdapter

        mf = MindForge(config=config)
        api = GenericAPIAdapter(mf)

        # Add via API
        resp = api.handle_request({
            "action": "memory.add",
            "params": {"content": "API test memory", "category": "test", "tags": ["api"]}
        })
        log("api_add_success", resp.get("success") == True,
            f"success={resp.get('success')}")
        log("api_add_has_id", "id" in resp.get("data", {}),
            f"has_id={'id' in resp.get('data', {})}")

    except Exception as e:
        log("generic_api_add", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_generic_api_get():
    """GenericAPI: get memory via API"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from adapters.generic_api import GenericAPIAdapter

        mf = MindForge(config=config)
        api = GenericAPIAdapter(mf)

        # Add first
        add_resp = api.handle_request({
            "action": "memory.add",
            "params": {"content": "Get test memory"}
        })
        mem_id = add_resp["data"]["id"]

        # Get
        get_resp = api.handle_request({
            "action": "memory.get",
            "params": {"id": mem_id}
        })
        log("api_get_success", get_resp.get("success") == True,
            f"success={get_resp.get('success')}")
        log("api_get_content", get_resp.get("data", {}).get("content") == "Get test memory",
            f"content={get_resp.get('data', {}).get('content')}")

    except Exception as e:
        log("generic_api_get", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_generic_api_search():
    """GenericAPI: search via API"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from adapters.generic_api import GenericAPIAdapter

        mf = MindForge(config=config)
        api = GenericAPIAdapter(mf)

        api.handle_request({
            "action": "memory.add",
            "params": {"content": "Searchable unique content about databases"}
        })

        resp = api.handle_request({
            "action": "memory.search",
            "params": {"query": "databases", "limit": 5}
        })
        log("api_search_success", resp.get("success") == True,
            f"success={resp.get('success')}")
        log("api_search_found", resp.get("data", {}).get("total", 0) > 0,
            f"total={resp.get('data', {}).get('total', 0)}")

    except Exception as e:
        log("generic_api_search", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_generic_api_unknown_action():
    """GenericAPI: unknown action returns error"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from adapters.generic_api import GenericAPIAdapter

        mf = MindForge(config=config)
        api = GenericAPIAdapter(mf)

        resp = api.handle_request({
            "action": "unknown.action",
            "params": {}
        })
        log("api_unknown_action", resp.get("success") == False,
            f"success={resp.get('success')}")

    except Exception as e:
        log("generic_api_unknown", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_claude_adapter_basic():
    """ClaudeCodeAdapter: initialization and basic operations"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_")
    try:
        db_path = os.path.join(tmpdir, "test.db")
        config = MemoryConfig(db_path=db_path, encrypted=False)
        from core.mindforge import MindForge
        from adapters.claude_adapter import ClaudeCodeAdapter

        mf = MindForge(config=config)
        adapter = ClaudeCodeAdapter(mf)

        # Remember
        mem_id = adapter.remember("Claude adapter test memory", tags=["claude", "test"])
        log("claude_remember", mem_id is not None and len(mem_id) > 0,
            f"id={mem_id[:8] if mem_id else 'None'}")

        # Recall
        results = adapter.recall("Claude adapter test")
        log("claude_recall", isinstance(results, list),
            f"results={len(results)}")

        # Get context
        context = adapter.get_context("test task")
        log("claude_context", isinstance(context, str) and len(context) > 0,
            f"len={len(context)}")

        # Forget
        ok = adapter.forget(mem_id)
        log("claude_forget", ok == True, f"ok={ok}")

    except Exception as e:
        log("claude_adapter", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 7: Adapters")
    print("=" * 60)

    test_generic_api_add()
    test_generic_api_get()
    test_generic_api_search()
    test_generic_api_unknown_action()
    test_claude_adapter_basic()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
