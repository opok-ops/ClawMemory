# ClawMemory GUI - Part 1 of 2
import sys, os, json, re, sqlite3, time, uuid
from pathlib import Path
CLAWMEM = Path(__file__).parent
DBP = CLAWMEM / "data" / "store" / "memory.db"
DBP.parent.mkdir(exist_ok=True)
PM = {"PUBLIC": 0, "INTERNAL": 1, "PRIVATE": 2, "STRICT": 3}
PR = {v: k for k, v in PM.items()}
IMP = ["\u4f4e", "\u4e2d", "\u9ad8", "\u5173\u952e"]
CAT_ICONS = {"all": "\U0001f4cb", "general": "\U0001f4cc", "learning": "\U0001f4da", "work": "\U0001f4bc", "life": "\U0001f3e0", "idea": "\U0001f4a1", "fact": "\U0001f4dd", "emotion": "\U0001f495"}
CAT_LB = {"all": "\u5168\u90e8", "general": "\u901a\u7528", "learning": "\u5b66\u4e60", "work": "\u5de5\u4f5c", "life": "\u751f\u6d3b", "idea": "\u521b\u610f", "fact": "\u4e8b\u5b9e", "emotion": "\u60c5\u611f"}
PRIV_IC = {"PUBLIC": "\U0001f7e2", "INTERNAL": "\U0001f7e1", "PRIVATE": "\U0001f534", "STRICT": "\U0001f7e3"}
def scan_privacy(t):
    d = []
    if re.search(r"\u5bc6\u7801|\u8d26\u53f7", t, re.I): d.append("PASSWORD")
    if re.search(r"\u8eab\u4efd\u8bc1|\u6237\u53e3", t, re.I): d.append("ID_CARD")
    if re.search(r"1[3-9]\d{9}", t): d.append("PHONE")
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", t): d.append("EMAIL")
    if not d: return False, [], "INTERNAL"
    s = {"PASSWORD": 3, "ID_CARD": 3, "PHONE": 1, "EMAIL": 1}
    mx = max(s.get(x, 0) for x in d)
    lv = {0: "PUBLIC", 1: "PRIVATE", 2: "PRIVATE", 3: "STRICT"}
    return True, d, lv.get(mx, "INTERNAL")
def suggest_cat(t):
    t = t.lower()
    if any(x in t for x in ["\u4f1a\u8bae", "\u9879\u76ee", "task", "meeting", "project"]: return "work"
    if any(x in t for x in ["\u5b66\u4e60", "\u8bfe\u7a0b", "course", "study"]: return "learning"
    if any(x in t for x in ["\u60f3\u6cd5", "\u521b\u610f", "idea"]: return "idea"
    if any(x in t for x in ["\u5bc6\u7801", "\u8d26\u53f7", "\u5730\u5740"]: return "fact"
    if any(x in t for x in ["\u611f\u53d7", "\u5fc3\u60c5"]: return "emotion"
    return "general"
def suggest_tags(t):
    tags = [m.lower() for m in re.findall(r"[@#](\w+)", t)]
    for m in re.findall(r"https?://\S+", t): tags.append("url:" + m[:30])
    return list(dict.fromkeys(tags))[:8]
def init_db():
    c = sqlite3.connect(str(DBP)).cursor()
    c.executescript("PRAGMA journal_mode=WAL;CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,content TEXT NOT NULL,plaintext_preview TEXT,category TEXT DEFAULT 'general',tags TEXT DEFAULT '[]',privacy INTEGER DEFAULT 1,importance INTEGER DEFAULT 2,source_session TEXT DEFAULT 'gui',source_agent TEXT DEFAULT 'gui',created_at REAL,updated_at REAL,accessed_at REAL,access_count INTEGER DEFAULT 0,is_deleted INTEGER DEFAULT 0,metadata_json TEXT DEFAULT '{}';CREATE INDEX IF NOT EXISTS idx_cat ON memories(category)WHERE is_deleted=0;CREATE INDEX IF NOT EXISTS idx_priv ON memories(privacy)WHERE is_deleted=0;CREATE INDEX IF NOT EXISTS idx_updated ON memories(updated_at)WHERE is_deleted=0")
    sqlite3.connect(str(DBP)).commit()
    sqlite3.connect(str(DBP)).close()
def add_mem(content, cat, tags, priv, imp):
    mid = str(uuid.uuid4()); n = time.time(); c = sqlite3.connect(str(DBP)).cursor()
    sqlite3.connect(str(DBP)).execute("INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (mid, content, content[:200], cat, json.dumps(tags), PM[priv], imp, "gui", "gui", n, n, n)); sqlite3.connect(str(DBP)).commit(); sqlite3.connect(str(DBP)).close(); return mid
def get_mems(cat="all", search=""):
    c = sqlite3.connect(str(DBP)).cursor()
    sql = "SELECT id,content,category,tags,privacy,importance,created_at,updated_at FROM memories WHERE is_deleted=0"
    par = []
    if cat != "all": sql += " AND category=?"; par.append(cat)
    if search: sql += " AND content LIKE ?"; par.append("%"+search+"%")
    sql += " ORDER BY updated_at DESC LIMIT 200"
    rows = sqlite3.connect(str(DBP)).execute(sql, par).fetchall()
    sqlite3.connect(str(DBP)).close()
    return [{"id": r[0], "content": r[1], "category": r[2], "tags": json.loads(r[3]), "privacy": PR[r[4]], "importance": r[5], "created_at": r[6], "updated_at": r[7]} for r in rows]
def get_by_id(mid):
    c = sqlite3.connect(str(DBP)).cursor()
    r = sqlite3.connect(str(DBP)).execute("SELECT * FROM memories WHERE id=? AND is_deleted=0", (mid,)).fetchone()
    sqlite3.connect(str(DBP)).close()
    if not r: return None
    return {"id": r[0], "content": r[1], "category": r[3], "tags": json.loads(r[4]), "privacy": PR[r[5]], "importance": r[6]}
def delete_mem(mid):
    sqlite3.connect(str(DBP)).execute("UPDATE memories SET is_deleted=1,updated_at=? WHERE id=?", (time.time(), mid)); sqlite3.connect(str(DBP)).commit(); sqlite3.connect(str(DBP)).close()
def update_mem(mid, content, cat, tags, priv, imp):
    n = time.time(); sqlite3.connect(str(DBP)).execute("UPDATE memories SET content=?,category=?,tags=?,privacy=?,importance=?,updated_at=? WHERE id=?", (content, cat, json.dumps(tags), PM[priv], imp, n, mid)); sqlite3.connect(str(DBP)).commit(); r = sqlite3.connect(str(DBP)).execute("SELECT id FROM memories WHERE id=?", (mid,)).fetchone(); sqlite3.connect(str(DBP)).close()
    return r is not None
def get_stats():
    c = sqlite3.connect(str(DBP)).cursor()
    tot = sqlite3.connect(str(DBP)).execute("SELECT COUNT(*) FROM memories WHERE is_deleted=0").fetchone()[0]
    bp = {k: sqlite3.connect(str(DBP)).execute("SELECT COUNT(*) FROM memories WHERE privacy=? AND is_deleted=0", (v,)).fetchone()[0] for k, v in PR.items()}
    cats = dict(sqlite3.connect(str(DBP)).execute("SELECT category,COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY category").fetchall())
    sz = DBP.stat().st_size if DBP.exists() else 0; sqlite3.connect(str(DBP)).close()
    return {"total": tot, "by_priv": bp, "cats": cats, "size": sz}
def seed():
    if sqlite3.connect(str(DBP)).execute("SELECT COUNT(*) FROM memories").fetchone()[0] > 0: return
    for cat, cat_lb, tags, priv, imp in [
        ("\u4eca\u5929\u5b8c\u6210\u4e86 ClawMemory v1.0 \u6838\u5fc3\u67b6\u6784\u8bbe\u8ba1\uff0c\u5305\u62ec AES-256 \u52a0\u5bc6\u5f15\u64ce\u3001SQLite \u5b58\u50a8\u5f15\u64ce\u548c TF-IDF \u5411\u91cf\u7d22\u5f15\u3002", "learning", ["ai", "architecture"], "INTERNAL", 3),
        ("Q2 \u4ea7\u54c1\u8def\u7ebf\u56fe\uff1a6\u6708\u5b8c\u6210\u6838\u5fc3\u529f\u80fd\uff0c9\u6708\u652f\u6301\u591a Agent \u534f\u540c\u8bb0\u5fc6\uff0c12\u6708\u8de8\u8bbe\u5907\u540c\u6b65", "work", ["roadmap"], "INTERNAL", 3),
        ("AI Agent \u7ec8\u8eab\u8bb0\u5fc6\u662f\u8fd1\u4e24\u5e74\u6700\u6709\u4ef7\u503c\u7684\u521b\u4e1a\u65b9\u5411\u3002\u6838\u5fc3\u5783\u6b89\uff1a\u6570\u636e\u98de\u8f6e\u6548\u5e94\u3001\u9690\u79c1\u8ba1\u7b97\u57fa\u7840\u8bbe\u65bd\u3001Agent \u539f\u751f\u67b6\u6784", "idea", ["startup", "ai"], "PUBLIC", 2),
        ("ClawMemory \u652f\u6301\u56db\u7ea7\u9690\u79c1\u5206\u7ea7\uff1aPUBLIC / INTERNAL / PRIVATE / STRICT\u3002STRICT \u7ea7\u522b\u7269\u7406\u9694\u79bb\u5b58\u50a8\uff0cACL \u8bbf\u95ee\u6388\u6743", "learning", ["privacy", "security"], "INTERNAL", 2),
    ]:
        add_mem(cat, cat_lb, tags, priv, imp)
