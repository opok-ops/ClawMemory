#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write app_native.py with proper UTF-8 encoding"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Complete app as a single string
app_code = r'''# -*- coding: utf-8 -*-
"""
ClawMemory Native GUI - PySimpleGUI Windows Application
Connects to real ClawMemory backend.
Run: python app_native.py
"""
import sys, os, json, re, sqlite3, time, uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple

# ---- Config ----
CLAWMEMORY_DIR = Path(__file__).parent
DATA_DIR = CLAWMEMORY_DIR / "data"
STORE_DIR = DATA_DIR / "store"
DB_PATH = STORE_DIR / "memory.db"
DATA_DIR.mkdir(exist_ok=True)
STORE_DIR.mkdir(exist_ok=True)

# ---- Privacy Scanner ----
PASSWORD_RE = re.compile(r'\u5bc6\u7801|\u53e3\u4ee4|\u8d26\u53f7|\u5bc6\u7387|\u9a8c\u8bc1', re.I)
ID_RE = re.compile(r'\u8eab\u4efd\u8bc1|\u6237\u53e3|\u62a4\u7167|\u75c5\u5386', re.I)
PHONE_RE = re.compile(r'1[3-9]\d{9}')
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

def scan_privacy(text: str) -> Tuple[bool, List[str], str]:
    detected = []
    if PASSWORD_RE.search(text): detected.append("PASSWORD")
    if ID_RE.search(text): detected.append("ID_CARD")
    if PHONE_RE.search(text): detected.append("PHONE")
    if EMAIL_RE.search(text): detected.append("EMAIL")
    if not detected: return False, [], "INTERNAL"
    sev = {"PASSWORD": 3, "ID_CARD": 3, "BANK_CARD": 2, "HEALTH": 2, "PHONE": 1, "EMAIL": 1}
    mx = max(sev.get(t, 0) for t in detected)
    lvls = {0: "PUBLIC", 1: "PRIVATE", 2: "PRIVATE", 3: "STRICT"}
    return True, detected, lvls.get(mx, "INTERNAL")

def suggest_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["\u4f1a\u8bae","\u9879\u76ee","task","meeting","project","deadline"]): return "work"
    if any(k in t for k in ["\u5b66\u4e60","\u8bfe\u7a0b","\u4e66","course","study","book"]): return "learning"
    if any(k in t for k in ["\u60f3\u6cd5","\u521b\u610f","idea","think"]): return "idea"
    if any(k in t for k in ["\u5bc6\u7801","\u8d26\u53f7","\u5730\u5740","password"]): return "fact"
    if any(k in t for k in ["\u611f\u53d7","\u5fc3\u60c5","feel","happy"]): return "emotion"
    return "general"

def suggest_tags(text: str) -> List[str]:
    tags = [m.lower() for m in re.findall(r'[@#](\w+)', text)]
    for m in re.findall(r'https?://\S+', text): tags.append("url:" + m[:30])
    return list(dict.fromkeys(tags))[:8]

# ---- Database ----
PRIVACY_MAP = {"PUBLIC": 0, "INTERNAL": 1, "PRIVATE": 2, "STRICT": 3}
PRIVACY_REV = {v: k for k, v in PRIVACY_MAP.items()}

def init_db():
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.executescript("PRAGMA journal_mode=WAL;"
        "CREATE TABLE IF NOT EXISTS memories ("
        "id TEXT PRIMARY KEY, content TEXT NOT NULL, plaintext_preview TEXT,"
        "category TEXT DEFAULT 'general', tags TEXT DEFAULT '[]',"
        "privacy INTEGER DEFAULT 1, importance INTEGER DEFAULT 2,"
        "source_session TEXT DEFAULT 'gui', source_agent TEXT DEFAULT 'gui',"
        "created_at REAL, updated_at REAL, accessed_at REAL,"
        "access_count INTEGER DEFAULT 0, is_deleted INTEGER DEFAULT 0,"
        "metadata_json TEXT DEFAULT '{}');"
        "CREATE INDEX IF NOT EXISTS idx_cat ON memories(category) WHERE is_deleted=0;"
        "CREATE INDEX IF NOT EXISTS idx_priv ON memories(privacy) WHERE is_deleted=0;"
        "CREATE INDEX IF NOT EXISTS idx_updated ON memories(updated_at) WHERE is_deleted=0;")
    conn.commit(); conn.close()

def add_memory(content, category, tags, privacy, importance):
    mid = str(uuid.uuid4()); now = time.time()
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("INSERT INTO memories (id,content,plaintext_preview,category,tags,privacy,importance,"
        "source_session,source_agent,created_at,updated_at,accessed_at)"
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        mid, content, content[:200], category, json.dumps(tags, ensure_ascii=False),
        PRIVACY_MAP.get(privacy,1), importance, "gui","gui", now,now,now)
    conn.commit(); conn.close(); return mid

def get_memories(category="all", privacy="all", search=""):
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    sql = "SELECT id,content,category,tags,privacy,importance,created_at,updated_at,accessed_at,access_count FROM memories WHERE is_deleted=0"
    params = []
    if category != "all": sql += " AND category=?"; params.append(category)
    if privacy != "all": sql += " AND privacy=?"; params.append(PRIVACY_MAP.get(privacy,1))
    if search: sql += " AND (content LIKE ? OR tags LIKE ? OR category LIKE ?)"; s = "%"+search+"%"; params.extend([s,s,s])
    sql += " ORDER BY updated_at DESC LIMIT 200"
    rows = c.execute(sql, params).fetchall(); conn.close()
    return [{"id":r[0],"content":r[1],"category":r[2],"tags":json.loads(r[3]),
             "privacy":PRIVACY_REV.get(r[4],"INTERNAL"),"importance":r[5],
             "created_at":r[6],"updated_at":r[7],"accessed_at":r[8],"access_count":r[9]} for r in rows]

def get_memory_by_id(mid):
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    row = c.execute("SELECT id,content,category,tags,privacy,importance,created_at,updated_at,accessed_at,access_count FROM memories WHERE id=? AND is_deleted=0",(mid,)).fetchone()
    conn.close()
    if not row: return None
    return {"id":row[0],"content":row[1],"category":row[2],"tags":json.loads(row[3]),
             "privacy":PRIVACY_REV.get(row[4],"INTERNAL"),"importance":row[5],
             "created_at":row[6],"updated_at":row[7],"accessed_at":row[8],"access_count":row[9]}

def delete_memory(mid):
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("UPDATE memories SET is_deleted=1,updated_at=? WHERE id=?",(time.time(),mid))
    conn.commit(); conn.close()

def update_memory(mid, content, category, tags, privacy, importance):
    now = time.time()
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("UPDATE memories SET content=?,category=?,tags=?,privacy=?,importance=?,updated_at=?,plaintext_preview=? WHERE id=?",
        content, category, json.dumps(tags, ensure_ascii=False), PRIVACY_MAP.get(privacy,1), importance, now, content[:200], mid)
    conn.commit()
    affected = c.execute("SELECT COUNT(*) FROM memories WHERE id=?",(mid,)).fetchone()[0]
    conn.close(); return affected > 0

def get_stats():
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM memories WHERE is_deleted=0").fetchone()[0]
    by_priv = {k: c.execute("SELECT COUNT(*) FROM memories WHERE privacy=? AND is_deleted=0",(v,)).fetchone()[0] for k,v in PRIVACY_REV.items()}
    cats = dict(c.execute("SELECT category, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY category ORDER BY COUNT(*) DESC").fetchall())
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    conn.close(); return {"total":total,"by_privacy":by_priv,"top_categories":cats,"db_size":db_size}

def seed_demo():
    if DB_PATH.exists() and sqlite3.connect(str(DB_PATH)).execute("SELECT COUNT(*) FROM memories").fetchone()[0] > 0: return
    demos = [
        ("\u4eca\u5929\u5b8c\u6210\u4e86 ClawMemory v1.0 \u6838\u5fc3\u67b6\u6784\u8bbe\u8ba1\uff0c\u5305\u62ec AES-256 \u52a0\u5bc6\u5f15\u64ce\u3001SQLite \u5b58\u50a8\u5f15\u64ce\u548c TF-IDF \u5411\u91cf\u7d22\u5f15\u3002","learning",["ai","architecture","python"],"INTERNAL",3),
        ("Q2 \u4ea7\u54c1\u8def\u7ebf\u56fe\uff1a6\u6708\u5b8c\u6210\u6838\u5fc3\u529f\u80fd\uff0c9\u6708\u652f\u6301\u591a Agent \u534f\u540c\u8bb0\u5fc6\uff0c12\u6708\u8de8\u8bbe\u5907\u540c\u6b65\u3002","work",["roadmap","planning"],"INTERNAL",3),
        ("AI Agent \u7ec8\u8eab\u8bb0\u5fc6\u662f\u8fd1\u4e24\u5e74\u6700\u6709\u4ef7\u503c\u7684\u521b\u4e1a\u65b9\u5411\u3002\u6838\u5fc3\u5783\u6b89\uff1a\u6570\u636e\u98de\u8f6e\u6548\u5e94\u3001\u9690\u79c1\u8ba1\u7b97\u57fa\u7840\u8bbe\u65bd\u3002","idea",["startup","ai","memory"],"PUBLIC",2),
        ("\u9879\u76ee\u8fdb\u5ea6\uff1aClawMemory \u6838\u5fc3\u5f15\u64ce\u5b8c\u6210 80%\uff0c\u9884\u8ba1\u672c\u5468\u5b8c\u6210\u5168\u90e8\u6a21\u5757\u548c\u9002\u914d\u5668\u3002","work",["project","progress"],"INTERNAL",2),
        ("ClawMemory \u652f\u6301\u56db\u7ea7\u9690\u79c1\u5206\u7ea7\uff1aPUBLIC / INTERNAL / PRIVATE / STRICT\u3002STRICT \u7ea7\u522b\u7269\u7406\u9694\u79bb\u5b58\u50a8\uff0cACL \u8bbf\u95ee\u6388\u6743\u3002","learning",["privacy","security","architecture"],"INTERNAL",2),
    ]
    for content,cat,tags,priv,imp in demos: add_memory(content,cat,tags,priv,imp)

# ---- PySimpleGUI ----
import PySimpleGUI as sg
sg.theme("DarkGrey13")
sg.set_options(font=("Segoe UI",10), text_color="#e2e8f0", background_color="#0d1422",
    input_background_color="#0a1020", button_color=("#0d1422","#00d4ff"),
    element_background_color="#0d1422", border_width=1)

# Labels (all using Unicode escapes to avoid encoding issues)
CAT_ICONS = {"all":"\U0001f4cb","general":"\U0001f4cc","learning":"\U0001f4da","work":"\U0001f4bc","life":"\U0001f3e0","idea":"\U0001f4a1","fact":"\U0001f4dd","emotion":"\U0001f495"}
CAT_LABELS = {"all":"\u5168\u90e8","general":"\u901a\u7528","learning":"\u5b66\u4e60","work":"\u5de5\u4f5c","life":"\u751f\u6d3b","idea":"\u521b\u610f","fact":"\u4e8b\u5b9e","emotion":"\u60c5\u611f"}
PRIV_ICONS = {"PUBLIC":"\U0001f7e2","INTERNAL":"\U0001f7e1","PRIVATE":"\U0001f534","STRICT":"\U0001f7e3"}
IMP_LABELS = ["\u4f4e","\u4e2d","\u9ad8","\u5173\u952e"]

def time_ago(ts):
    d = time.time()-ts; m=int(d/60)
    if m<1: return "\u521a\u521a"
    if m<60: return str(m)+"\u5206\u949f\u524d"
    h=int(m/60)
    if h<24: return str(h)+"\u5c0f\u65f6\u524d"
    dd=int(h/24)
    if dd<30: return str(dd)+"\u5929\u524d"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

def cat_color(c):
    return {"learning":"#f59e0b","work":"#00d4ff","life":"#f472b6","idea":"#a855f7","fact":"#10b981","emotion":"#ef4444","general":"#64748b"}.get(c,"#00d4ff")

def make_card(mem):
    acc = cat_color(mem["category"])
    priv_icon = PRIV_ICONS.get(mem["privacy"],"\U0001f7e1")
    content_short = mem["content"][:100].replace("\n"," ").strip()
    tags_str = "  ".join("#"+t for t in mem["tags"][:4])
    time_str = time_ago(mem["updated_at"])
    imp_lbl = IMP_LABELS[mem["importance"]-1]
    cat_icon = CAT_ICONS.get(mem["category"],"\U0001f4cc")
    cat_lbl = CAT_LABELS.get(mem["category"], mem["category"])
    mid = mem["id"]
    del_key = "del:" + mid
    card_key = "card:" + mid
    col_layout = [
        [sg.Text(cat_icon+" "+cat_lbl, font=("Segoe UI",9,"bold"), text_color=acc, pad=(8,(8,0))),
         sg.Text(priv_icon+" "+mem["privacy"], font=("Segoe UI",8), text_color="#64748b",
                  pad=(0,(8,0)), expand_x=True, justification="right"),
         sg.Button("\u2715", key=del_key, button_color=("transparent","transparent"),
                  text_color="#ef4444", font=("Segoe UI",9), Size=(2,1), pad=(4,(4,0)),
                  tooltip="\u5220\u9664\u8bb0\u5fc6")],
        [sg.Text(content_short+("..." if len(mem["content"])>100 else ""),
                  text_color="#94a3b8", font=("Segoe UI",9), pad=(8,(2,0)),
                  expand_x=True, tooltip=mem["content"][:300])],
        [sg.Text(tags_str+"  \u00b7 "+time_str+"  \u00b7 "+imp_lbl+"\u91cd\u8981",
                  font=("Segoe UI",8), text_color="#475569", pad=(8,(4,8)))],
    ]
    return sg.Column(col_layout, background_color="#111a2e", pad=(0,4), expand_x=True,
                     key=card_key, metadata={"mem_id":mid})

def build_card_list(mems):
    if not mems:
        return [[sg.Text("\U0001f50d \u6682\u65e0\u8bb0\u5fc6", text_color="#334155",
                          font=("Segoe UI",11), justification="center", pad=(20,40))]]
    return [[make_card(m)] for m in mems]

def refresh(window, cat="all", search=""):
    mems = get_memories(category=cat, search=search)
    stats = get_stats()
    window["stat_text"].update("\U0001f4ca "+str(stats["total"])+" \u6761\u8bb0\u5fc6")
    window["memory_area"].update([[sg.Column(build_card_list(mems), expand_x=True,
                                              background_color="#0d1422",
                                              element_justification="left",
                                              vertical_scroll_only=True)]])
    cat_lbl = CAT_LABELS.get(cat, cat)
    window["status_text"].update("\u663e\u793a "+str(len(mems))+" \u6761 "+cat_lbl+" \u8bb0\u5fc6")

def make_stats_win():
    s = get_stats()
    sz = s["db_size"]
    sz_str = f"{sz/1024:.1f} KB" if sz < 1048576 else f"{sz/1048576:.1f} MB"
    pcols = {"PUBLIC":"#10b981","INTERNAL":"#f59e0b","PRIVATE":"#ef4444","STRICT":"#a855f7"}
    prow = [sg.Text(PRIV_ICONS.get(k,"\U0001f7e0")+" "+k+": "+str(v)+" \u6761",
                     text_color=pcols.get(k,"#94a3b8"), font=("Segoe UI",10,"bold"))
            for k,v in s.get("by_privacy",{}).items()]
    crow = [sg.Text("  "+CAT_ICONS.get(k,"\U0001f4cc")+" "+CAT_LABELS.get(k,k)+": "+str(v)+" \u6761",
                     text_color="#94a3b8")
            for k,v in list(s.get("top_categories",{}).items())[:10]]
    return sg.Window("\U0001f4ca\u7edf\u8ba1\u62a5\u544a - ClawMemory",[
        [sg.Text("\U0001f4ca ClawMemory \u7edf\u8ba1\u62a5\u544a", font=("Segoe UI",14,"bold"), text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("\u603b\u8bb0\u5fc6\u6570:  "+str(s["total"]), font=("Segoe UI",11,"bold"), text_color="#e2e8f0", pad=(0,6))],
        [sg.Text("\u6570\u636e\u5e93\u5927\u5c0f:  "+sz_str, font=("Segoe UI",10), text_color="#64748b", pad=(0,6))],
        [sg.Text("\u2014 \u9690\u79c1\u5206\u7ea7\u2014", font=("Segoe UI",9,"bold"), text_color="#334155", pad=(0,4))],
        *prow,
        [sg.Text("\u2014 \u5206\u7c7b\u2014", font=("Segoe UI",9,"bold"), text_color="#334155", pad=(0,4))],
        *crow,
        [sg.Button("\u5173\u95ed", button_color=("#1e293b","#475569"), pad=(0,(16,0)))],
    ], modal=True, finalize=True, background_color="#0d1422", size=(380,420))

def make_privacy_win():
    s = get_stats()
    strict = s["by_privacy"].get("STRICT", 0)
    comp = "\u2705 \u5408\u89c4 PASS" if strict==0 else "\u26a0\ufe0f \u9879\u5ba1\u6838 ("+str(strict)+" \u6761 STRICT)"
    ccol = "#10b981" if strict==0 else "#f59e0b"
    return sg.Window("\U0001f6e1\ufe0f \u9690\u79c1\u7ba1\u7406 - ClawMemory",[
        [sg.Text("\U0001f6e1\ufe0f \u9690\u79c1\u7ba1\u7406", font=("Segoe UI",14,"bold"), text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("\U0001f7e2 PUBLIC    \u4efb\u610f\u8bbf\u95ee", text_color="#10b981", font=("Segoe UI",9))],
        [sg.Text("\U0001f7e1 INTERNAL  \u540c\u4f1a\u8bdd\u8bbf\u95ee", text_color="#f59e0b", font=("Segoe UI",9))],
        [sg.Text("\U0001f534 PRIVATE   \u9700\u6388\u6743\u8bbf\u95ee", text_color="#ef4444", font=("Segoe UI",9))],
        [sg.Text("\U0001f7e3 STRICT    \u7269\u7406\u9694\u79bb", text_color="#a855f7", font=("Segoe UI",9))],
        [sg.Text("\u5408\u89c4\u72b6\u6001", font=("Segoe UI",10,"bold"), text_color="#94a3b8", pad=(0,(12,4))],
        [sg.Text(comp, font=("Segoe UI",11,"bold"), text_color=ccol, pad=(0,(0,4))],
        [sg.Text("\u81ea\u52a8\u9690\u79c1\u68c0\u6d4b", font=("Segoe UI",10,"bold"), text_color="#94a3b8", pad=(0,(12,4))],
        [sg.Text("\u68c0\u6d4b\u624b\u673a\u53f7/\u90ae\u7bb1 \u2192 PRIVATE", text_color="#94a3b8", font=("Segoe UI",9))],
        [sg.Text("\u68c0\u6d4b\u5bc6\u7801/\u8eab\u4efd\u8bc1\u53f7 \u2192 STRICT", text_color="#94a3b8", font=("Segoe UI",9))],
        [sg.Button("\u5173\u95ed", button_color=("#1e293b","#475569"), pad=(0,(16,0)))],
    ], modal=True, finalize=True, background_color="#0d1422", size=(360,440))

def main():
    init_db(); seed_demo()

    cats = list(CAT_LABELS.keys())
    cat_btns = {}
    for c in cats:
        cat_btns[c] = sg.Button(
            CAT_ICONS[c]+" "+CAT_LABELS[c], key="cat:"+c, font=("Segoe UI",9),
            button_color=("#1e293b","#00d4ff" if c=="all" else "#475569"),
            border_width=0, pad=(2,2), Size=(9,1))

    header_row = [
        sg.Text("\U0001f9e0 ClawMemory", font=("Segoe UI",16,"bold"), text_color="#00d4ff"),
        sg.Text("AI Agent\u7ec8\u8eab\u8bb0\u5fc6\u7cfb\u7edf", font=("Segoe UI",9), text_color="#475569", pad=((4,0),0)),
        sg.Push(),
        sg.Text(key="stat_text", font=("Segoe UI",9), text_color="#475569"),
        sg.Button("\U0001f4ca\u7edf\u8ba1", key="btn_stats", button_color=("#1e293b","#475569"), font=("Segoe UI",9), pad=(4,0)),
        sg.Button("\U0001f6e1\ufe0f\u9690\u79c1", key="btn_privacy", button_color=("#1e293b","#475569"), font=("Segoe UI",9), pad=(4,0)),
        sg.Button("\U0001f4e4\u5bfc\u51fa", key="btn_export", button_color=("#1e293b","#475569"), font=("Segoe UI",9), pad=(4,0)),
        sg.Button("+\u6dfb\u52a0", key="btn_add", button_color=("#0d1422","#00d4ff"), font=("Segoe UI",10,"bold"), pad=(8,0)),
    ]

    search_row = [
        sg.Text("\U0001f50d", font=("Segoe UI",10), text_color="#475569", pad=(8,0)),
        sg.Input(key="search", size=(40,1), background_color="#0a1020",
                 text_color="#e2e8f0", border_width=0, font=("Segoe UI",10),
                 pad=(4,0), enable_events=True, tooltip="\u641c\u7d22..."),
        sg.Button("\u2715", key="clear_search", button_color=("transparent","transparent"),
                 text_color="#475569", font=("Segoe UI",9), visible=False, tooltip="\u6e05\u9664"),
    ]

    cat_row = [[cat_btns[c] for c in cats]]

    status_row = [[sg.Text(key="status_text", font=("Segoe UI",8), text_color="#334155")]]

    layout = [
        [sg.Column([header_row], background_color="#0d1422", pad=(16,12))],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Column([cat_row], background_color="#0d1422", pad=(12,8), expand_x=True, element_justification="center")],
        [sg.Column([search_row], background_color="#0d1422", pad=(12,4), expand_x=True)],
        [sg.HorizontalSeparator(color="#0d1422")],
        [sg.Column([[sg.Text("\u6b63\u5728\u52a0\u8f7d...", text_color="#334155", font=("Segoe UI",10))]],
                  key="memory_area", expand_x=True, expand_y=True,
                  scrollable=True, vertical_scroll_only=True,
                  background_color="#0d1422", pad=(8,4))],
        [sg.HorizontalSeparator(color="#1e3a5f", pad=(0,4))],
        [sg.Column(status_row, background_color="#0d1422", pad=(16,8))],
    ]

    window = sg.Window("ClawMemory - AI Agent\u7ec8\u8eab\u8bb0\u5fc6\u7cfb\u7edf",
        layout, finalize=True, background_color="#0d1422",
        resizable=True, size=(1000,700), min_size=(700,500))

    window["search"].bind("<Return>","_enter")
    refresh(window, "all", "")

    cur_cat = "all"
    cur_search = ""

    while True:
        event, values = window.read(timeout=100)
        if event in (sg.WINDOW_CLOSED,): break

        # Category filter
        if event.startswith("cat:"):
            cat = event[4:]; cur_cat = cat
            for c in cats:
                cat_btns[c].update(button_color=("#1e293b","#00d4ff" if c==cat else "#475569"))
            refresh(window, cur_cat, cur_search)

        # Search
        if event == "search":
            q = values.get("search",""); cur_search = q
            window["clear_search"].update(visible=bool(q))
            refresh(window, cur_cat, cur_search)
        if event in ("clear_search","search_enter"):
            window["search"].update(""); cur_search = ""
            window["clear_search"].update(visible=False)
            refresh(window, cur_cat, "")

        # Add memory window
        if event == "btn_add":
            add_win = sg.Window("+\u6dfb\u52a0\u65b0\u8bb0\u5fc6 - ClawMemory", [
                [sg.Text("+\u6dfb\u52a0\u65b0\u8bb0\u5fc6", font=("Segoe UI",13,"bold"), text_color="#00d4ff")],
                [sg.HorizontalSeparator(color="#1e3a5f")],
                [sg.Text("\u5185\u5bb9", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                [sg.Multiline(key="add_content", size=(60,7), background_color="#0a1020",
                              text_color="#e2e8f0", border_width=1, focus=True, pad=(0,(0,4))],
                [sg.Text("\u5206\u7c7b", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                [sg.Combo(list(CAT_LABELS.keys()), default_value="general", key="add_cat",
                          size=(20,1), readonly=True, background_color="#0a1020", text_color="#e2e8f0")],
                [sg.Text("\u6807\u7b7e\uff08\u9017\u53f7\u5206\u9694\uff09", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                [sg.Input(key="add_tags", size=(40,1), background_color="#0a1020", text_color="#e2e8f0", border_width=1)],
                [sg.Text("\u9690\u79c1\u5206\u7ea7", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                [sg.Combo(["PUBLIC","INTERNAL","PRIVATE","STRICT"], default_value="INTERNAL",
                          key="add_privacy", size=(20,1), readonly=True,
                          background_color="#0a1020", text_color="#e2e8f0")],
                [sg.Text("\u91cd\u8981\u6027", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                [sg.Combo(IMP_LABELS, default_value="\u4e2d", key="add_imp", size=(20,1),
                          readonly=True, background_color="#0a1020", text_color="#e2e8f0")],
                [sg.Checkbox("\u3010\u63a8\u8350\u3011\u81ea\u52a8\u9690\u79c1\u68c0\u6d4b",
                             key="auto_priv", default=True, text_color="#64748b",
                             background_color="#0d1422", pad=(0,(8,0)))],
                [sg.Button("\u2705\u4fdd\u5b58\u8bb0\u5fc6", key="save_add",
                           button_color=("#0d1422","#00d4ff"), font=("Segoe UI",10,"bold"), pad=(0,(16,0))),
                 sg.Button("\u53d6\u6d88", key="cancel_add", button_color=("#1e293b","#475569"))],
            ], modal=True, finalize=True, background_color="#0d1422", size=(480,560))
            add_win["add_content"].set_focus()

            while True:
                ev2, v2 = add_win.read()
                if ev2 in (sg.WINDOW_CLOSED,"cancel_add"):
                    add_win.close(); break
                if ev2 == "save_add":
                    content = v2.get("add_content","").strip()
                    if not content: continue
                    cat_v = v2.get("add_cat","general")
                    tags_str = v2.get("add_tags","").strip()
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                    priv = v2.get("add_privacy","INTERNAL")
                    imp_idx = IMP_LABELS.index(v2.get("add_imp","\u4e2d")) + 1
                    if v2.get("auto_priv"):
                        _, _, suggested = scan_privacy(content)
                        priv = suggested
                    if not tags: tags = suggest_tags(content)
                    mid = add_memory(content, cat_v, tags, priv, imp_idx)
                    add_win.close()
                    refresh(window, cur_cat, cur_search)
                    sg.popup_auto_close("\u2705 \u8bb0\u5fc6\u5df2\u4fdd\u5b58\uff01\nID: "+mid[:8]+"...", title="\u6210\u529f", background_color="#0d1422", text_color="#10b981", auto_close_duration=2)
                    break

        # Stats window
        if event == "btn_stats":
            sw = make_stats_win(); sw.read(close=True)

        # Privacy window
        if event == "btn_privacy":
            pw = make_privacy_win(); pw.read(close=True)

        # Export
        if event == "btn_export":
            all_m = get_memories(search="")
            export = []
            for m in all_m:
                item = dict(m)
                if item["privacy"] in ("PRIVATE","STRICT"):
                    item["content"] = "\u3010\u5185\u5bb9\u5df2\u8131\u654f\u3011"
                item.pop("access_count", None); export.append(item)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = CLAWMEMORY_DIR / ("clawmemory_export_"+ts+".json")
            with open(path,"w",