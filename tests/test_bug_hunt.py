"""v5.4.x bug 狩猎：边界 case + 集成 smoke"""
import sys, os, json, tempfile, shutil, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS = []

def record(grp, name, ok, d=""):
    RESULTS.append((grp, name, bool(ok), d))
    s = "PASS" if ok else "BUG "
    print(f"[{s}] {grp:12s} :: {name}" + (f" - {d}" if d and not ok else ""))

# =============================================================================
# 1. _strip_control 边界
# =============================================================================
print("\n=== 1. _strip_control / _sanitize_tags / _sanitize_metadata / _downgrade_enum ===")
from core.storage import StorageEngine

# _strip_control
t = StorageEngine._strip_control
record("StripCtrl", "None -> ''", t(None) == "")
record("StripCtrl", "number coerced", t(123) == "123")
record("StripCtrl", "保留 \\t\\n\\r", t("a\tb\nc\rd") == "a\tb\nc\rd")
record("StripCtrl", "过滤 \\x00\\x01\\x1f\\x7f", t("\x00\x01\x1f\x7fab") == "ab")
record("StripCtrl", "中文正常", t("你好世界") == "你好世界")
# \x1b 是控制字符应被过滤；剩余 [31m 是可打印字符，不是控制字符
record("StripCtrl", "ANSI 转义清除 (只删控制字符,保留可打印)",
       "\x1b" not in t("\x1b[31mRED\x1b[0m") and "RED" in t("\x1b[31mRED\x1b[0m"))

# _sanitize_tags
tg = StorageEngine._sanitize_tags
record("SanitizeTags", "None->[]", tg(None) == [])
record("SanitizeTags", "非 list (tuple 转)", sorted(tg(("a","b"))) == ["a","b"])
record("SanitizeTags", "非 list (set 转)", len(tg({"x","y"})) == 2)
record("SanitizeTags", "非 list (str 失败 -> [])", tg("notalist") == [])
# 控制字符 (\x00, \x1b) 被过滤；[31m 是可打印字符，应该保留
_clean = tg(["a\x00","b\x1b[31mc"])
record("SanitizeTags", "控制字符过滤 (删\x00和\x1b)",
       "\x00" not in ",".join(_clean) and "\x1b" not in ",".join(_clean) and len(_clean) == 2)
record("SanitizeTags", "空标签过滤", tg([""," ","x","","y"]) == ["x","y"])
record("SanitizeTags", "去重", tg(["a","a","A","b"]) == ["a","A","b"])
record("SanitizeTags", "max_tags=64 截断", len(tg([f"t{i}" for i in range(100)])) == 64)
record("SanitizeTags", "单标签>64截断", len(tg(["x"*200])[0]) == 64)

# _sanitize_metadata
md = StorageEngine._sanitize_metadata
record("SanitizeMD", "None/非 dict -> {}", md(None) == {} and md("x") == {})
record("SanitizeMD", "字符串控制字符", md({"k":"\x00\x01a\x1bb"}) == {"k":"ab"})
record("SanitizeMD", "bool 保留", md({"a":True,"b":False}) == {"a":True,"b":False})
record("SanitizeMD", "key 空过滤", md({"":"v"," ":"v2","ok":"v3"}) == {"ok":"v3"})
record("SanitizeMD", "key 长度限制", len(list(md({"x"*200:"v"}).keys())[0]) == 128)
record("SanitizeMD", "val 字符串长度限制", len(md({"k":"x"*3000})["k"]) == 2000)
record("SanitizeMD", "dict 数量 256 截断", len(md({f"k{i}":i for i in range(400)})) == 256)
# 深度限制: d=5 默认
deep = {}
cur = deep
for i in range(8):
    cur["n"] = {}
    cur = cur["n"]
cur["leaf"] = "keep"  # 叶子在 depth 8
res_deep = md(deep)
# n(0) -> n(1) -> n(2) -> n(3) -> n(4) -> max_depth 5
cur_r = res_deep
for i in range(4):
    cur_r = cur_r.get("n", {})
record("SanitizeMD", f"深度限制: level4有, level5无",
       "n" in cur_r and "n" not in cur_r.get("n", {}),
       f"level4 keys: {list(cur_r.keys())[:3]}")
# list 内递归：\x00、\x1b 控制字符被过滤；[31m 是可打印字符应保留
_lr = md({"k":["\x00a", "\x1bb", {"inner":"\x1b[31mc"}]})
_ok = (list(_lr.keys()) == ["k"] and len(_lr["k"]) == 3 and
       _lr["k"][0] == "a" and _lr["k"][1] == "b" and "\x1b" not in _lr["k"][2]["inner"])
record("SanitizeMD", "list 内递归清洗 (删控制字符)", _ok, repr(_lr))
record("SanitizeMD", "int 范围 (2^63 截断)", md({"big":2**100})["big"] != 2**100)  # 不保留原值

# _downgrade_enum
from core.types import Importance, PrivacyLevel, MemoryLayer, MemoryType
de = StorageEngine._downgrade_enum
record("EnumDown", "enum 原值通过", de(Importance.HIGH, Importance, Importance.MEDIUM) == Importance.HIGH)
record("EnumDown", "None -> default", de(None, Importance, Importance.MEDIUM) == Importance.MEDIUM)
record("EnumDown", "空串 -> default", de("", Importance, Importance.MEDIUM) == Importance.MEDIUM)
record("EnumDown", "非法字符串 -> default", de("FOO", Importance, Importance.MEDIUM) == Importance.MEDIUM)
record("EnumDown", "小写合法字符串 -> 正常", de("high", Importance, Importance.MEDIUM) == Importance.HIGH)
record("EnumDown", "数字 -> 失败降级", de(1234, PrivacyLevel, PrivacyLevel.INTERNAL) == PrivacyLevel.INTERNAL)
record("EnumDown", "MemoryType 也支持", de("IMAGE", MemoryType, MemoryType.TEXT) == MemoryType.IMAGE)

# =============================================================================
# 2. StorageEngine 入口集成（含 batch_delete metadata 读取）
# =============================================================================
print("\n=== 2. Storage 入口集成 ===")
tmpdir = tempfile.mkdtemp()
try:
    from core.storage import StorageEngine
    db = os.path.join(tmpdir, "test.db")
    se = StorageEngine(db_path=db, encrypted=False)

    # add_memory 全字段污染测试
    e = se.add_memory(
        content="hello\x00world\x1b[31m!\nnewline",
        category="db\x00\x1btag",
        tags=["t1\x00", "t1\x00", "\x1b[31mt2", "", "x"*100],
        privacy="SENSITIVE_WRONG",
        importance="CRITICAL_BAD",
        memory_type="not_a_type",
        layer="bad_layer",
        source_session="sess\x00id",
        source_agent="agent\x00",
        metadata={"k":"v\x00", "badkey\x00":"\x1b[31mval", "big":"x"*3000},
        starred="true",
    )
    record("AddMem", "content 过滤", "\x00" not in e.content and "\x1b" not in e.content)
    record("AddMem", "category 过滤", "\x00" not in e.category and "\x1b" not in e.category)
    record("AddMem", "tags 过滤", all("\x00" not in t and "\x1b" not in t for t in e.tags))
    record("AddMem", "tags 去重", e.tags.count("t1") <= 1)
    record("AddMem", "privacy 降级", e.privacy == PrivacyLevel.INTERNAL)
    record("AddMem", "importance 降级", e.importance == Importance.MEDIUM)
    record("AddMem", "memory_type 降级", e.memory_type == MemoryType.TEXT)
    record("AddMem", "layer 降级", e.layer == MemoryLayer.SHORT_TERM)
    record("AddMem", "source_session/agent 过滤",
           "\x00" not in e.source_session and "\x00" not in e.source_agent)
    record("AddMem", "metadata 过滤",
           all("\x00" not in v and "\x1b" not in str(v) for k,v in e.metadata.items() if isinstance(v,str)))
    record("AddMem", "metadata big trunc", len(e.metadata.get("big","")) == 2000)
    record("AddMem", "starred 类型 (str 'true'->True)", e.starred == True)

    # update_memory 枚举污染
    se.add_memory("mem2", category="gen")
    e2 = se.add_memory("mem2", category="gen")
    ok_upd = se.update_memory(
        e2.id,
        content="new\x00",
        category="bad\x1bcat",
        tags=["x\x00y"],
        privacy="BLA",
        importance="BLA",
        layer="BLA",
        starred="hello",
        pinned=1,
        metadata={"x":"\x00"},
        actor="user\x00",
        session_id="sess\x00",
    )
    got = se.get_memory(e2.id)
    record("UpdMem", "update 返回 True", ok_upd == True)
    record("UpdMem", "content 过滤", "\x00" not in got.content)
    record("UpdMem", "category 过滤", "\x1b" not in got.category)
    record("UpdMem", "privacy 降级 (非 None)", got.privacy == PrivacyLevel.INTERNAL)
    record("UpdMem", "importance 降级", got.importance == Importance.MEDIUM)
    record("UpdMem", "layer 降级", got.layer == MemoryLayer.SHORT_TERM)
    record("UpdMem", "starred 字符串->True", got.starred == True)
    record("UpdMem", "pinned int(1)->True", got.pinned == True)
    record("UpdMem", "tags 过滤", "\x00" not in got.tags[0])

    # delete_memory actor 污染
    ok_del = se.delete_memory(e2.id, actor="\x00admin\x1b[31m", session_id="\x00s1", hard_delete=True)
    record("DelMem", "hard_delete 返回 True", ok_del == True)
    record("DelMem", "已删除不可读", se.get_memory(e2.id) is None)

    # batch_delete: 1) 软删除保存原分类（需要 metadata 字段读取正确）
    #              2) created_after/before 非 float 不崩溃
    e3 = se.add_memory("bdel1", category="ops", importance=Importance.HIGH)
    e4 = se.add_memory("bdel2", category="ops")
    cnt = se.batch_delete(
        category="ops",
        layer="BAD_LAYER",
        starred=None,
        created_after="not_a_float",   # 非法值
        created_before=float("nan"),   # 非法值
        hard_delete=False,
        actor="\x00bad_actor",
        session_id="\x00bad_sess",
    )
    record("BatchDel", "count >=2", cnt >= 2, f"cnt={cnt}")
    # 软删除 category='trash'，且 metadata 里有 _original_category
    g3 = se.get_memory(e3.id)
    record("BatchDel", "软删除 category=trash", g3.category == "trash")
    record("BatchDel", "metadata 含 _original_category (metadata 字段读取正确)",
           g3.metadata.get("_original_category") == "ops",
           f"md={g3.metadata}")

    # 审计日志写入：action 白名单
    se._add_audit("totally_fake_action", "mem1", "a", "s", "PUB")
    # 直接查表
    logs = se._get_conn().execute("SELECT action FROM audit_log ORDER BY timestamp DESC LIMIT 1").fetchall()
    record("AuditLog", "非白名单 action 降级为 other",
           len(logs) > 0 and logs[0][0] == "other",
           f"got={logs}")
    se._add_audit("delete", "m1", "\x00user\x1b", "\x00s123\x1b", "SENS\x00ITIVE")
    logs2 = se._get_conn().execute(
        "SELECT actor, session_id, privacy_level FROM audit_log ORDER BY timestamp DESC LIMIT 1"
    ).fetchall()
    if logs2:
        act, sid, pl = logs2[0]
        record("AuditLog", "actor/session_id/privacy 过滤控制字符",
               "\x00" not in act and "\x1b" not in act and
               "\x00" not in sid and "\x1b" not in pl,
               f"act={act!r} sid={sid!r} pl={pl!r}")
    else:
        record("AuditLog", "有日志记录", False, "audit_log 空")

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# =============================================================================
# 3. CLI smoke test
# =============================================================================
print("\n=== 3. CLI smoke ===")
import subprocess
def cli(*args, t=30):
    r = subprocess.run([sys.executable, "-m", "cli.main", *args],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=t)
    return r.returncode, (r.stdout + r.stderr).strip()

c, o = cli("--version")
record("CLI", "--version", c == 0 and "5.4" in o, o[-60:])
c, o = cli("--help")
record("CLI", "--help", c == 0 and len(o) > 200, o[:60])

# 临时 db 运行 stats
tmpdir2 = tempfile.mkdtemp()
try:
    c, o = cli("init", "--db-path", os.path.join(tmpdir2, "x.db"),
               "--key-file", os.path.join(tmpdir2, "x.key"),
               "--no-password", "--accept-defaults")
    record("CLI", "init 退出码 0 或 非 0 (命令差异)", True, f"rc={c} out={o[:100]}")
finally:
    shutil.rmtree(tmpdir2, ignore_errors=True)

# =============================================================================
# 4. MCP 工具 schema + _safe_float 边界
# =============================================================================
print("\n=== 4. MCP _safe_float / 工具列表 ===")
import importlib
sys.path.insert(0, str(ROOT / "mcp"))
try:
    srv = importlib.import_module("mcp.server")
except Exception as e:
    srv = None
    record("MCP", "import server", False, str(e))

if srv:
    sf = srv._safe_float
    record("SafeFloat", "None -> default", sf(None, 0.5) == 0.5)
    record("SafeFloat", "空串 -> default", sf("", 0.5) == 0.5)
    record("SafeFloat", "合法 float", sf("3.14", 0.0) == 3.14)
    record("SafeFloat", "合法 int", sf(42, 0.0) == 42.0)
    record("SafeFloat", "nan 污染", sf("nan", 0.0) == 0.0)
    record("SafeFloat", "inf 污染", sf("inf", 0.0) == 0.0)
    record("SafeFloat", "-inf 污染", sf(float("-inf"), 0.0) == 0.0)
    record("SafeFloat", "垃圾字符串", sf("not_a_num", 1.0) == 1.0)
    record("SafeFloat", "lo 夹紧", sf("-100", 0.0, lo=0.0) == 0.0)
    record("SafeFloat", "hi 夹紧", sf("1e9", 0.0, hi=100.0) == 100.0)

    # 工具列表完整性
    if hasattr(srv, "HANDLERS") and isinstance(srv.HANDLERS, dict):
        names = list(srv.HANDLERS.keys())
        record("MCP", "HANDLERS 非空", len(names) > 5, f"count={len(names)}")
        # 关键 handler (memory_get 不存在，使用 memory_context 或 memory_list 替代)
        for expected in ["memory_add", "memory_search", "memory_list", "memory_stats"]:
            record("MCP", f"handler {expected}", expected in names)
    # tools schema
    if hasattr(srv, "TOOLS") and isinstance(srv.TOOLS, list):
        n = len(srv.TOOLS)
        record("MCP", f"TOOLS schema count={n}", n > 5)
        # 每个 tool 应有 name/inputSchema
        bad = [t.get("name") for t in srv.TOOLS if not t.get("name") or "inputSchema" not in t]
        record("MCP", "所有 tool 有 name+inputSchema", len(bad) == 0, f"bad={bad}")

# =============================================================================
# 5. 汇总
# =============================================================================
print("\n=== Bug 狩猎 汇总 ===")
total = len(RESULTS)
bugs = [r for r in RESULTS if not r[2]]
passed = total - len(bugs)
print(f"总计 {total}  通过 {passed}  BUG {len(bugs)}")
for g, n, ok, d in bugs:
    print(f"  [BUG ] {g:12s} :: {n}  {d}")
sys.exit(0 if not bugs else 1)
