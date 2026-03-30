#!/usr/bin/env python3
# Write app_native.py in multiple parts, then concatenate
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Part 1: imports + config
p1 = '''# -*- coding: utf-8 -*-
"""
ClawMemory Native GUI - PySimpleGUI Windows Application
Connects to real ClawMemory backend with local encrypted storage.
Run: python app_native.py
"""
import sys, os, json, re, sqlite3, time, uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple

CLAWMEMORY_DIR = Path(__file__).parent
DB_PATH = CLAWMEMORY_DIR / "data" / "store" / "memory.db"
DB_PATH.parent.mkdir(exist_ok=True)

PRIVACY_MAP = {"PUBLIC": 0, "INTERNAL": 1, "PRIVATE": 2, "STRICT": 3}
PRIVACY_REV = {v: k for k, v in PRIVACY_MAP.items()}
IMP_LABELS = ["低", "中", "高", "关键"]
CAT_ICONS = {"all":"📋","general":"📌","learning":"📚","work":"💼","life":"🏠","idea":"💡","fact":"📝","emotion":"❤️"}
CAT_LABELS = {"all":"全部","general":"通用","learning":"学习","work":"工作","life":"生活","idea":"创意","fact":"事实","emotion":"情感"}
PRIV_ICONS = {"PUBLIC":"🟢","INTERNAL":"🟡","PRIVATE":"🔴","STRICT":"🟣"}

def scan_privacy(text):
    pw_re = re.compile(r"密码|口令|账号|口今|密码之关缝关键", re.I)
    id_re = re.compile(r"身份证|户日", re.I)
    ph_re = re.compile(r"1[3-9]\d{9}")
    em_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    det = []
    if pw_re.search(text): det.append("PASSWORD")
    if id_re.search(text): det.append("ID_CARD")
    if ph_re.search(text): det.append("PHONE")
    if em_re.search(text): det.append("EMAIL")
    if not det: return False, [], "INTERNAL"
    sev = {"PASSWORD": 3, "ID_CARD": 3, "PHONE": 1, "EMAIL": 1}
    mx = max(sev.get(t, 0) for t in det)
    lvls = {0: "PUBLIC", 1: "PRIVATE", 2: "PRIVATE", 3: "STRICT"}
    return True, det, lvls.get(mx, "INTERNAL")

def suggest_category(text):
    t = text.lower()
    if any(k in t for k in ["会议","项目","task","meeting","project"]): return "work"
    if any(k in t for k in ["学习","课程","书","course","study"]): return "learning"
    if any(k in t for k in ["想法","创意","idea","think"]): return "idea"
    if any(k in t for k in ["密码","账号","地址","password"]): return "fact"
    if any(k in t for k in ["感受","心情","feel","happy"]): return "emotion"
    return "general"

def suggest_tags(text):
    tags = [m.lower() for m in re.findall(r"[@#](\w+)", text)]
    for m in re.findall(r"https?://\S+", text): tags.append("url:" + m[:30])
    return list(dict.fromkeys(tags))[:8]

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
    affected = c.execute("SELECT COUNT(*) FROM memories WHERE id=?",(mid,)).fetchone()[0]; conn.close()
    return affected > 0

def get_stats():
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM memories WHERE is_deleted=0").fetchone()[0]
    by_priv = {k: c.execute("SELECT COUNT(*) FROM memories WHERE privacy=? AND is_deleted=0",(v,)).fetchone()[0] for k,v in PRIVACY_REV.items()}
    cats = dict(c.execute("SELECT category, COUNT(*) FROM memories WHERE is_deleted=0 GROUP BY category ORDER BY COUNT(*) DESC").fetchall())
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    conn.close()
    return {"total":total,"by_privacy":by_priv,"top_categories":cats,"db_size":db_size}

def seed_demo():
    if DB_PATH.exists() and sqlite3.connect(str(DB_PATH)).execute("SELECT COUNT(*) FROM memories").fetchone()[0] > 0: return
    demos = [
        ("今天完成了 ClawMemory v1.0 核心架构设计，包括 AES-256 加密引擎、SQLite 存储引擎和 TF-IDF 向量索引。整体采用分层模块化设计。", "learning", ["ai","architecture","python"], "INTERNAL", 3),
        ("Q2 产品路线图：6月完成核心功能，9月支持多 Agent 协同记忆，12月跨设备同步。技术风险：向量检索在百万级条目下的性能优化。", "work", ["roadmap","planning"], "INTERNAL", 3),
        ("AI Agent 终身记忆是近两年最有价值的创业方向。核心壁垒：数据飞轮效应、隐私计算基础设施、Agent 原生架构。", "idea", ["startup","ai","memory"], "PUBLIC", 2),
        ("项目进度：ClawMemory 核心引擎完成 80%，预计本周完成全部模块和适配器。下周开始测试 OpenClaw 集成。", "work", ["project","progress"], "INTERNAL", 2),
        ("ClawMemory 支持四级隐私分级：PUBLIC / INTERNAL / PRIVATE / STRICT。STRICT 级别物理隔离存储，ACL 访问授权。", "learning", ["privacy","security","architecture"], "INTERNAL", 2),
    ]
    for content,cat,tags,priv,imp in demos: add_memory(content,cat,tags,priv,imp)

import PySimpleGUI as sg
sg.theme("DarkGrey13")
sg.set_options(font=("Segoe UI",10), text_color="#e2e8f0", background_color="#0d1422",
    input_background_color="#0a1020", button_color=("#0d1422","#00d4ff"),
    element_background_color="#0d1422", border_width=1)

def time_ago(ts):
    d = time.time()-ts; m=int(d/60)
    if m<1: return "刚刚"
    if m<60: return str(m)+"分钟前"
    h=int(m/60)
    if h<24: return str(h)+"小时前"
    dd=int(h/24)
    if dd<30: return str(dd)+"天前"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

def cat_color(c):
    return {"learning":"#f59e0b","work":"#00d4ff","life":"#f472b6","idea":"#a855f7","fact":"#10b981","emotion":"#ef4444","general":"#64748b"}.get(c,"#00d4ff")

def make_card(mem):
    acc = cat_color(mem["category"])
    priv_icon = PRIV_ICONS.get(mem["privacy"],"🟡")
    content_short = mem["content"][:100].replace("\n"," ").strip()
    tags_str = "  ".join("#"+t for t in mem["tags"][:4])
    time_str = time_ago(mem["updated_at"])
    imp_lbl = IMP_LABELS[mem["importance"]-1]
    cat_icon = CAT_ICONS.get(mem["category"],"📌")
    cat_lbl = CAT_LABELS.get(mem["category"], mem["category"])
    mid = mem["id"]
    col_layout = [
        [sg.Text(cat_icon+" "+cat_lbl, font=("Segoe UI",9,"bold"), text_color=acc, pad=(8,(8,0))),
         sg.Text(priv_icon+" "+mem["privacy"], font=("Segoe UI",8), text_color="#64748b", pad=(0,(8,0)), expand_x=True, justification="right"),
         sg.Button("✕", key="del:"+mid, button_color=("transparent","transparent"), text_color="#ef4444", font=("Segoe UI",9), Size=(2,1), pad=(4,(4,0)), tooltip="删除记忆")],
        [sg.Text(content_short+("..." if len(mem["content"])>100 else ""), text_color="#94a3b8", font=("Segoe UI",9), pad=(8,(2,0)), expand_x=True, tooltip=mem["content"][:300])],
        [sg.Text(tags_str+"  · "+time_str+"  · "+imp_lbl+"重要", font=("Segoe UI",8), text_color="#475569", pad=(8,(4,8)))],
    ]
    return sg.Column(col_layout, background_color="#111a2e", pad=(0,4), expand_x=True, key="card:"+mid, metadata={"mem_id":mid})

def build_card_list(mems):
    if not mems: return [[sg.Text("🔍 暂无记忆", text_color="#334155", font=("Segoe UI",11), justification="center", pad=(20,40))]]
    return [[make_card(m)] for m in mems]

def refresh(window, cat="all", search=""):
    mems = get_memories(category=cat, search=search)
    stats = get_stats()
    window["stat_text"].update("📊 "+str(stats["total"])+" 条记忆")
    window["memory_area"].update([[sg.Column(build_card_list(mems), expand_x=True, background_color="#0d1422", element_justification="left", vertical_scroll_only=True)]])
    cat_lbl = CAT_LABELS.get(cat, cat)
    window["status_text"].update("显示 "+str(len(mems))+" 条 "+cat_lbl+" 记忆")

def make_stats_win():
    s = get_stats()
    sz = s["db_size"]
    sz_str = f"{sz/1024:.1f} KB" if sz < 1048576 else f"{sz/1048576:.1f} MB"
    pcols = {"PUBLIC":"#10b981","INTERNAL":"#f59e0b","PRIVATE":"#ef4444","STRICT":"#a855f7"}
    prow = [sg.Text(PRIV_ICONS.get(k,"🟢")+" "+k+": "+str(v)+" 条", text_color=pcols.get(k,"#94a3b8"), font=("Segoe UI",10,"bold")) for k,v in s.get("by_privacy",{}).items()]
    crow = [sg.Text("  "+CAT_ICONS.get(k,"📌")+" "+CAT_LABELS.get(k,k)+": "+str(v)+" 条", text_color="#94a3b8") for k,v in list(s.get("top_categories",{}).items())[:10]]
    return sg.Window("📊统计报告 - ClawMemory",[
        [sg.Text("📊 ClawMemory 统计报告", font=("Segoe UI",14,"bold"), text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("总记忆数:  "+str(s["total"]), font=("Segoe UI",11,"bold"), text_color="#e2e8f0", pad=(0,6))],
        [sg.Text("数据库大小:  "+sz_str, font=("Segoe UI",10), text_color="#64748b", pad=(0,6))],
        [sg.Text("─ 隐私分级分布 ─", font=("Segoe UI",9,"bold"), text_color="#334155", pad=(0,4))],*prow,
        [sg.Text("─ 分类统计 ─", font=("Segoe UI",9,"bold"), text_color="#334155", pad=(0,4))],*crow,
        [sg.Button("关闭", button_color=("#1e293b","#475569"), pad=(0,(16,0)))],
    ], modal=True, finalize=True, background_color="#0d1422", size=(380,420))

def make_privacy_win():
    s = get_stats()
    strict = s["by_privacy"].get("STRICT", 0)
    comp = "✅ 合规 PASS" if strict==0 else "⚠️ 需审查 ("+str(strict)+" 条 STRICT)"
    ccol = "#10b981" if strict==0 else "#f59e0b"
    return sg.Window("🛡️隐私管理 - ClawMemory",[
        [sg.Text("🛡️ 隐私管理", font=("Segoe UI",14,"bold"), text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("🟢 PUBLIC    任意访问", text_color="#10b981", font=("Segoe UI",9))],
        [sg.Text("🟡 INTERNAL  同会话访问", text_color="#f59e0b", font=("Segoe UI",9))],
        [sg.Text("🔴 PRIVATE   需授权访问", text_color="#ef4444", font=("Segoe UI",9))],
        [sg.Text("🟣 STRICT    物理隔离存储", text_color="#a855f7", font=("Segoe UI",9))],
        [sg.Text("合规状态", font=("Segoe UI",10,"bold"), text_color="#94a3b8", pad=(0,(12,4))],
        [sg.Text(comp, font=("Segoe UI",11,"bold"), text_color=ccol, pad=(0,(0,4))],
        [sg.Text("自动隐私检测", font=("Segoe UI",10,"bold"), text_color="#94a3b8", pad=(0,(12,4))],
        [sg.Text("检测手机号/邮箱 → PRIVATE", text_color="#94a3b8", font=("Segoe UI",9))],
        [sg.Text("检测密码/证件号 → STRICT", text_color="#94a3b8", font=("Segoe UI",9))],
        [sg.Text("导出脱敏", font=("Segoe UI",10,"bold"), text_color="#94a3b8", pad=(0,(12,4))],
        [sg.Text("PRIVATE/STRICT 内容导出时自动脱敏", text_color="#94a3b8", font=("Segoe UI",9))],
        [sg.Button("关闭", button_color=("#1e293b","#475569"), pad=(0,(16,0)))],
    ], modal=True, finalize=True, background_color="#0d1422", size=(360,440))
'''

with open('app_native.py', 'w', encoding='utf-8') as f:
    f.write(p1)
print("Part 1 written:", len(p1), "chars")
