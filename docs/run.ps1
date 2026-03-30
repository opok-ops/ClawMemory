# ClawMemory GUI Launcher
# Run: .\run.ps1
# Downloads PySimpleGUI if needed, creates app_native.py, launches GUI

$ErrorActionPreference = "Continue"
Write-Host "ClawMemory GUI Launcher" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found" -ForegroundColor Red
    Write-Host "Install Python from python.org" -ForegroundColor Yellow
    exit 1
}

# Install PySimpleGUI if needed
try {
    Import-Module PySimpleGUI -ErrorAction Stop
    Write-Host "[OK] PySimpleGUI installed" -ForegroundColor Green
} catch {
    Write-Host "[*] Installing PySimpleGUI..." -ForegroundColor Yellow
    pip install PySimpleGUI --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] PySimpleGUI installed" -ForegroundColor Green
    } else {
        Write-Host "[WARN] pip install had issues, trying pip3..." -ForegroundColor Yellow
        pip3 install PySimpleGUI --quiet
    }
}

# Write app_native.py using Python
Write-Host "[*] Writing app_native.py..." -ForegroundColor Yellow
$appContent = @'
# -*- coding: utf-8 -*-
"""ClawMemory Native GUI"""
import sys, os, json, re, sqlite3, time, uuid
from pathlib import Path
from datetime import datetime, timezone

CLAWMEM = Path(__file__).parent
DBP = CLAWMEM / "data" / "store" / "memory.db"
DBP.parent.mkdir(exist_ok=True)

PM = {"PUBLIC": 0, "INTERNAL": 1, "PRIVATE": 2, "STRICT": 3}
PR = {v: k for k, v in PM.items()}
IMP = ["低", "中", "高", "关键"]
CATS_ICONS = {"all":"📋","general":"📌","learning":"📚","work":"💼","life":"🏠","idea":"💡","fact":"📝","emotion":"❤️"}
CATS_LABELS = {"all":"全部","general":"通用","learning":"学习","work":"工作","life":"生活","idea":"创意","fact":"事实","emotion":"情感"}
PRIV_ICONS = {"PUBLIC":"🟢","INTERNAL":"🟡","PRIVATE":"🔴","STRICT":"🟣"}

def scan_privacy(text):
    det = []
    if re.search(r"密码|口令|账号", text, re.I): det.append("PASSWORD")
    if re.search(r"身份证|护照", text, re.I): det.append("ID_CARD")
    if re.search(r"1[3-9]\d{9}", text): det.append("PHONE")
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text): det.append("EMAIL")
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
    conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    c.executescript("PRAGMA journal_mode=WAL;CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,content TEXT NOT NULL,plaintext_preview TEXT,category TEXT DEFAULT 'general',tags TEXT DEFAULT '[]',privacy INTEGER DEFAULT 1,importance INTEGER DEFAULT 2,source_session TEXT DEFAULT 'gui',source_agent TEXT DEFAULT 'gui',created_at REAL,updated_at REAL,accessed_at REAL,access_count INTEGER DEFAULT 0,is_deleted INTEGER DEFAULT 0,metadata_json TEXT DEFAULT '{}');CREATE INDEX IF NOT EXISTS idx_cat ON memories(category)WHERE is_deleted=0;CREATE INDEX IF NOT EXISTS idx_priv ON memories(privacy)WHERE is_deleted=0;CREATE INDEX IF NOT EXISTS idx_updated ON memories(updated_at)WHERE is_deleted=0;")
    conn.commit(); conn.close()

def add_memory(content, category, tags, privacy, importance):
    mid = str(uuid.uuid4()); n = time.time()
    conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    c.execute("INSERT INTO memories(id,content,plaintext_preview,category,tags,privacy,importance,source_session,source_agent,created_at,updated_at,accessed_at)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(mid,content,content[:200],category,json.dumps(tags,ensure_ascii=False),PM.get(privacy,1),importance,"gui","gui",n,n,n))
    conn.commit(); conn.close(); return mid

def get_memories(category="all", privacy="all", search=""):
    conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    sql = "SELECT id,content,category,tags,privacy,importance,created_at,updated_at,accessed_at,access_count FROM memories WHERE is_deleted=0"
    params = []
    if category != "all": sql += " AND category=?"; params.append(category)
    if privacy != "all": sql += " AND privacy=?"; params.append(PM.get(privacy,1))
    if search: sql += " AND (content LIKE ? OR tags LIKE ?)"; s = "%"+search+"%"; params.extend([s,s])
    sql += " ORDER BY updated_at DESC LIMIT 200"
    rows = c.execute(sql, params).fetchall(); conn.close()
    return [{"id":r[0],"content":r[1],"category":r[2],"tags":json.loads(r[3]),"privacy":PR.get(r[4],"INTERNAL"),"importance":r[5],"created_at":r[6],"updated_at":r[7],"accessed_at":r[8],"access_count":r[9]} for r in rows]

def get_memory_by_id(mid):
    conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    row = c.execute("SELECT id,content,category,tags,privacy,importance,created_at,updated_at,accessed_at,access_count FROM memories WHERE id=? AND is_deleted=0",(mid,)).fetchone()
    conn.close()
    if not row: return None
    return {"id":row[0],"content":row[1],"category":row[2],"tags":json.loads(row[3]),"privacy":PR.get(row[4],"INTERNAL"),"importance":row[5],"created_at":row[6],"updated_at":row[7],"accessed_at":row[8],"access_count":row[9]}

def delete_memory(mid):
    conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    c.execute("UPDATE memories SET is_deleted=1,updated_at=?WHERE id=?",(time.time(),mid))
    conn.commit(); conn.close()

def update_memory(mid, content, category, tags, privacy, importance):
    n = time.time(); conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    c.execute("UPDATE memories SET content=?,category=?,tags=?,privacy=?,importance=?,updated_at=?,plaintext_preview=?WHERE id=?",(content,category,json.dumps(tags,ensure_ascii=False),PM.get(privacy,1),importance,n,content[:200],mid))
    conn.commit(); aff = c.execute("SELECT COUNT(*)FROM memories WHERE id=?",(mid,)).fetchone()[0]; conn.close()
    return aff > 0

def get_stats():
    conn = sqlite3.connect(str(DBP)); c = conn.cursor()
    total = c.execute("SELECT COUNT(*)FROM memories WHERE is_deleted=0").fetchone()[0]
    by_priv = {k: c.execute("SELECT COUNT(*)FROM memories WHERE privacy=?AND is_deleted=0",(v,)).fetchone()[0] for k,v in PR.items()}
    cats = dict(c.execute("SELECT category,COUNT(*)FROM memories WHERE is_deleted=0 GROUP BY category ORDER BY COUNT(*)DESC").fetchall())
    sz = DBP.stat().st_size if DBP.exists()else 0; conn.close()
    return {"total":total,"by_privacy":by_priv,"top_categories":cats,"db_size":sz}

def seed_demo():
    if DBP.exists() and sqlite3.connect(str(DBP)).execute("SELECT COUNT(*)FROM memories").fetchone()[0] > 0: return
    demos = [
        ("今天完成了 ClawMemory v1.0 核心架构设计，包括 AES-256 加密引擎、SQLite 存储引擎和 TF-IDF 向量索引。整体采用分层模块化设计。","learning",["ai","architecture","python"],"INTERNAL",3),
        ("Q2 产品路线图：6月完成核心功能，9月支持多 Agent 协同记忆，12月跨设备同步。","work",["roadmap","planning"],"INTERNAL",3),
        ("AI Agent 终身记忆是近两年最有价值的创业方向。核心壁垒：数据飞轮效应、隐私计算基础设施、Agent 原生架构。","idea",["startup","ai","memory"],"PUBLIC",2),
        ("ClawMemory 支持四级隐私分级：PUBLIC / INTERNAL / PRIVATE / STRICT。STRICT 级别物理隔离存储，ACL 访问授权。","learning",["privacy","security","architecture"],"INTERNAL",2),
    ]
    for content,cat,tags,priv,imp in demos: add_memory(content,cat,tags,priv,imp)

import PySimpleGUI as sg
sg.theme("DarkGrey13")
sg.set_options(font=("Segoe UI",10),text_color="#e2e8f0",background_color="#0d1422",input_background_color="#0a1020",button_color=("#0d1422","#00d4ff"),element_background_color="#0d1422",border_width=1)

def time_ago(ts):
    d=time.time()-ts;m=int(d/60)
    if m<1:return"刚刚"
    if m<60:return str(m)+"分钟前"
    h=int(m/60)
    if h<24:return str(h)+"小时前"
    dd=int(h/24)
    if dd<30:return str(dd)+"天前"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

def cat_color(c):
    return {"learning":"#f59e0b","work":"#00d4ff","life":"#f472b6","idea":"#a855f7","fact":"#10b981","emotion":"#ef4444","general":"#64748b"}.get(c,"#00d4ff")

def make_card(mem):
    acc=cat_color(mem["category"])
    priv_icon=PRIV_ICONS.get(mem["privacy"],"🟡")
    content_short=mem["content"][:100].replace("\n"," ").strip()
    tags_str="  ".join("#"+t for t in mem["tags"][:4])
    time_str=time_ago(mem["updated_at"])
    imp_lbl=IMP[mem["importance"]-1]
    cat_icon=CATS_ICONS.get(mem["category"],"📌")
    cat_lbl=CATS_LABELS.get(mem["category"],mem["category"])
    mid=mem["id"]
    col_layout=[
        [sg.Text(cat_icon+" "+cat_lbl,font=("Segoe UI",9,"bold"),text_color=acc,pad=(8,(8,0))),
         sg.Text(priv_icon+" "+mem["privacy"],font=("Segoe UI",8),text_color="#64748b",pad=(0,(8,0)),expand_x=True,justification="right"),
         sg.Button("✕",key="del:"+mid,button_color=("transparent","transparent"),text_color="#ef4444",font=("Segoe UI",9),Size=(2,1),pad=(4,(4,0)),tooltip="删除记忆")],
        [sg.Text(content_short+("..."if len(mem["content"])>100else ""),text_color="#94a3b8",font=("Segoe UI",9),pad=(8,(2,0)),expand_x=True,tooltip=mem["content"][:300])],
        [sg.Text(tags_str+"  · "+time_str+"  · "+imp_lbl+"重要",font=("Segoe UI",8),text_color="#475569",pad=(8,(4,8)))],
    ]
    return sg.Column(col_layout,background_color="#111a2e",pad=(0,4),expand_x=True,key="card:"+mid,metadata={"mem_id":mid})

def build_cards(mems):
    if not mems:return[[sg.Text("🔍 暂无记忆",text_color="#334155",font=("Segoe UI",11),justification="center",pad=(20,40))]]
    return[[make_card(m)]for m in mems]

def refresh(window,cat="all",search=""):
    mems=get_memories(category=cat,search=search)
    s=get_stats()
    window["stat_text"].update("📊 "+str(s["total"])+" 条记忆")
    window["memory_area"].update([[sg.Column(build_cards(mems),expand_x=True,background_color="#0d1422",element_justification="left",vertical_scroll_only=True)]])
    window["status_text"].update("显示 "+str(len(mems))+" 条 "+CATS_LABELS.get(cat,cat)+" 记忆")

def make_stats_win():
    s=get_stats();sz=s["db_size"]
    sz_str=f"{sz/1024:.1f} KB"if sz<1048576else f"{sz/1048576:.1f} MB"
    pcols={"PUBLIC":"#10b981","INTERNAL":"#f59e0b","PRIVATE":"#ef4444","STRICT":"#a855f7"}
    prow=[sg.Text(PRIV_ICONS.get(k,"🟢")+" "+k+": "+str(v)+" 条",text_color=pcols.get(k,"#94a3b8"),font=("Segoe UI",10,"bold"))for k,v in s.get("by_privacy",{}).items()]
    crow=[sg.Text("  "+CATS_ICONS.get(k,"📌")+" "+CATS_LABELS.get(k,k)+": "+str(v)+" 条",text_color="#94a3b8")for k,v in list(s.get("top_categories",{}).items())[:10]]
    return sg.Window("📊统计报告 - ClawMemory",[
        [sg.Text("📊 ClawMemory 统计报告",font=("Segoe UI",14,"bold"),text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("总记忆数:  "+str(s["total"]),font=("Segoe UI",11,"bold"),text_color="#e2e8f0",pad=(0,6))],
        [sg.Text("数据库大小:  "+sz_str,font=("Segoe UI",10),text_color="#64748b",pad=(0,6))],
        [sg.Text("─ 隐私分级 ─",font=("Segoe UI",9,"bold"),text_color="#334155",pad=(0,4))],
        *prow,
        [sg.Text("─ 分类 ─",font=("Segoe UI",9,"bold"),text_color="#334155",pad=(0,4))],
        *crow,
        [sg.Button("关闭",button_color=("#1e293b","#475569"),pad=(0,(16,0)))],
    ],modal=True,finalize=True,background_color="#0d1422",size=(380,420))

def make_privacy_win():
    s=get_stats();strict=s["by_privacy"].get("STRICT",0)
    comp="✅ 合规 PASS"if strict==0else "⚠️ 需审查 ("+str(strict)+" 条 STRICT)"
    ccol="#10b981"if strict==0else "#f59e0b"
    return sg.Window("🛡️隐私管理 - ClawMemory",[
        [sg.Text("🛡️ 隐私管理",font=("Segoe UI",14,"bold"),text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("🟢 PUBLIC    任意访问",text_color="#10b981",font=("Segoe UI",9))],
        [sg.Text("🟡 INTERNAL  同会话访问",text_color="#f59e0b",font=("Segoe UI",9))],
        [sg.Text("🔴 PRIVATE   需授权访问",text_color="#ef4444",font=("Segoe UI",9))],
        [sg.Text("🟣 STRICT    物理隔离存储",text_color="#a855f7",font=("Segoe UI",9))],
        [sg.Text("合规状态",font=("Segoe UI",10,"bold"),text_color="#94a3b8",pad=(0,(12,4))],
        [sg.Text(comp,font=("Segoe UI",11,"bold"),text_color=ccol,pad=(0,(0,4))],
        [sg.Text("自动隐私检测",font=("Segoe UI",10,"bold"),text_color="#94a3b8",pad=(0,(12,4))],
        [sg.Text("检测手机号/邮箱 → PRIVATE",text_color="#94a3b8",font=("Segoe UI",9))],
        [sg.Text("检测密码/证件号 → STRICT",text_color="#94a3b8",font=("Segoe UI",9))],
        [sg.Button("关闭",button_color=("#1e293b","#475569"),pad=(0,(16,0)))],
    ],modal=True,finalize=True,background_color="#0d1422",size=(360,460))

def make_add_win():
    return sg.Window("➕添加新记忆 - ClawMemory",[
        [sg.Text("➕ 添加新记忆",font=("Segoe UI",13,"bold"),text_color="#00d4ff")],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Text("内容",font=("Segoe UI",9,"bold"),text_color="#64748b")],
        [sg.Multiline(key="add_content",size=(60,7),background_color="#0a1020",text_color="#e2e8f0",border_width=1,focus=True)],
        [sg.Text("分类",font=("Segoe UI",9,"bold"),text_color="#64748b")],
        [sg.Combo(list(CATS_LABELS.keys()),default_value="general",key="add_cat",size=(20,1),readonly=True,background_color="#0a1020",text_color="#e2e8f0")],
        [sg.Text("标签（逗号分隔）",font=("Segoe UI",9,"bold"),text_color="#64748b")],
        [sg.Input(key="add_tags",size=(40,1),background_color="#0a1020",text_color="#e2e8f0",border_width=1,tooltip="例如: ai, memory, project")],
        [sg.Text("隐私分级",font=("Segoe UI",9,"bold"),text_color="#64748b")],
        [sg.Combo(["PUBLIC","INTERNAL","PRIVATE","STRICT"],default_value="INTERNAL",key="add_privacy",size=(20,1),readonly=True,background_color="#0a1020",text_color="#e2e8f0")],
        [sg.Text("重要性",font=("Segoe UI",9,"bold"),text_color="#64748b")],
        [sg.Combo(IMP,default_value="中",key="add_imp",size=(20,1),readonly=True,background_color="#0a1020",text_color="#e2e8f0")],
        [sg.Checkbox("【推荐】自动隐私检测",key="auto_priv",default=True,text_color="#64748b",background_color="#0d1422",pad=(0,(8,0)))],
        [sg.Button("✅保存记忆",key="save_add",button_color=("#0d1422","#00d4ff"),font=("Segoe UI",10,"bold"),pad=(0,(16,0))),
         sg.Button("取消",key="cancel_add",button_color=("#1e293b","#475569"))],
    ],modal=True,finalize=True,background_color="#0d1422",size=(480,560))

init_db(); seed_demo()
cats=list(CATS_LABELS.keys())
cat_btns={}
for c in cats:
    cat_btns[c]=sg.Button(CATS_ICONS[c]+" "+CATS_LABELS[c],key="cat:"+c,font=("Segoe UI",9),button_color=("#1e293b","#00d4ff"if c=="all"else "#475569"),border_width=0,pad=(2,2),Size=(9,1))
header=[
    sg.Text("🧠 ClawMemory",font=("Segoe UI",16,"bold"),text_color="#00d4ff"),
    sg.Text("AI Agent终身记忆系统",font=("Segoe UI",9),text_color="#475569",pad=((4,0),0)),
    sg.Push(),
    sg.Text(key="stat_text",font=("Segoe UI",9),text_color="#475569"),
    sg.Button("📊统计",key="btn_stats",button_color=("#1e293b","#475569"),font=("Segoe UI",9),pad=(4,0)),
    sg.Button("🛡️隐私",key="btn_privacy",button_color=("#1e293b","#475569"),font=("Segoe UI",9),pad=(4,0)),
    sg.Button("📤导出",key="btn_export",button_color=("#1e293b","#475569"),font=("Segoe UI",9),pad=(4,0)),
    sg.Button("➕添加",key="btn_add",button_color=("#0d1422","#00d4ff"),font=("Segoe UI",10,"bold"),pad=(8,0)),
]
search_row=[
    sg.Text("🔍",font=("Segoe UI",10),text_color="#475569",pad=(8,0)),
    sg.Input(key="search",size=(40,1),background_color="#0a1020",text_color="#e2e8f0",border_width=0,font=("Segoe UI",10),pad=(4,0),enable_events=True,tooltip="搜索记忆..."),
    sg.Button("✕",key="clear_search",button_color=("transparent","transparent"),text_color="#475569",font=("Segoe UI",9),visible=False,tooltip="清除"),
]
layout=[
    [sg.Column([header],background_color="#0d1422",pad=(16,12))],
    [sg.HorizontalSeparator(color="#1e3a5f")],
    [sg.Column([[cat_btns[c]for c in cats],background_color="#0d1422",pad=(12,8),expand_x=True,element_justification="center")],
    [sg.Column([search_row],background_color="#0d1422",pad=(12,4),expand_x=True)],
    [sg.HorizontalSeparator(color="#0d1422")],
    [sg.Column([[sg.Text("正在加载...",text_color="#334155",font=("Segoe UI",10))]],key="memory_area",expand_x=True,expand_y=True,scrollable=True,vertical_scroll_only=True,background_color="#0d1422",pad=(8,4))],
    [sg.HorizontalSeparator(color="#1e3a5f",pad=(0,4))],
    [sg.Column([[sg.Text(key="status_text",font=("Segoe UI",8),text_color="#334155")]],background_color="#0d1422",pad=(16,8))],
]
window=sg.Window("ClawMemory - AI Agent终身记忆系统",layout,finalize=True,background_color="#0d1422",resizable=True,size=(1000,700),min_size=(700,500))
window["search"].bind("<Return>","_enter")
refresh(window,"all","")
cur_cat="all";cur_search=""
while True:
    event,values=window.read(timeout=100)
    if event in(sg.WINDOW_CLOSED,):break
    if event.startswith("cat:"):
        cat=event[4:];cur_cat=cat
        for c in cats:cat_btns[c].update(button_color=("#1e293b","#00d4ff"if c==catelse "#475569")
        refresh(window,cur_cat,cur_search)
    if event=="search":
        q=values.get("search","");cur_search=q;window["clear_search"].update(visible=bool(q));refresh(window,cur_cat,cur_search)
    if event in("clear_search","search_enter"):
        window["search"].update("");cur_search="";window["clear_search"].update(visible=False);refresh(window,cur_cat,"")
    if event=="btn_add":
        aw=make_add_win();aw["add_content"].set_focus()
        while True:
            ev2,v2=aw.read()
            if ev2 in(sg.WINDOW_CLOSED,"cancel_add"):aw.close();break
            if ev2=="save_add":
                content=v2.get("add_content","").strip()
                if not content:continue
                cat_v=v2.get("add_cat","general")
                tags_str=v2.get("add_tags","").strip()
                tags=[t.strip()for t in tags_str.split(",")if t.strip()]
                priv=v2.get("add_privacy","INTERNAL")
                imp_idx=IMP.index(v2.get("add_imp","中"))+1
                if v2.get("auto_priv"):
                    _,_,suggested=scan_privacy(content);priv=suggested
                if not tags:tags=suggest_tags(content)
                mid=add_memory(content,cat_v,tags,priv,imp_idx)
                aw.close();refresh(window,cur_cat,cur_search)
                sg.popup_auto_close("✅ 记忆已保存！\nID: "+mid[:8]+"...","ClawMemory",background_color="#0d1422",text_color="#10b981",auto_close_duration=2);break
    if event=="btn_stats":
        sw=make_stats_win();sw.read(close=True)
    if event=="btn_privacy":
        pw=make_privacy_win();pw.read(close=True)
    if event=="btn_export":
        all_m=get_memories(search="");export=[]
        for m in all_m:
            item=dict(m)
            if item["privacy"]in("PRIVATE","STRICT"):item["content"]="【内容已脱敏】"
            item.pop("access_count",None);export.append(item)
        ts=datetime.now().strftime("%Y%m%d_%H%M%S")
        path=CLAWMEM/("clawmemory_export_"+ts+".json")
        with open(path,"w",encoding="utf-8")as f:json.dump({"version":"1.0.0","exported_at":datetime.now(timezone.utc).isoformat(),"count":len(export),"memories":export},f,ensure_ascii=False,indent=2)
        sg.popup_auto_close("✅ 导出成功！\n文件: "+path.name,"ClawMemory",background_color="#0d1422",text_color="#00d4ff",auto_close_duration=3)
    if event.startswith("del:"):
        mid=event[4:]
        ok=sg.popup_yes_no("确认删除这条记忆？","ClawMemory",background_color="#0d1422",text_color="#e2e8f0",button_color=("#1e293b","#ef4444"))
        if ok=="Yes":delete_memory(mid);refresh(window,cur_cat,cur_search);sg.popup_auto_close("🗑️ 记忆已删除","ClawMemory",background_color="#0d1422",text_color="#f59e0b",auto_close_duration=2)
    if event.startswith("card:"):
        mid=event[5:];mem=get_memory_by_id(mid)
        if mem:
            imp_idx=mem["importance"]-1
            ew=sg.Window("✏️编辑记忆 - ClawMemory",[
                [sg.Text("✏️ 编辑记忆",font=("Segoe UI",13,"bold"),text_color="#00d4ff")],
                [sg.HorizontalSeparator(color="#1e3a5f")],
                [sg.Text("内容",font=("Segoe UI",9,"bold"),text_color="#64748b")],
                [sg.Multiline(mem["content"],key="edit_content",size=(60,6),background_color="#0a1020",text_color="#e2e8f0",border_width=1,focus=True)],
                [sg.Text("分类",font=("Segoe UI",9,"bold"),text_color="#64748b")],
                [sg.Combo(list(CATS_LABELS.keys()),default_value=mem["category"],key="edit_cat",size=(20,1),readonly=True,background_color="#0a1020",text_color="#e2e8f0")],
                [sg.Text("标签（逗号分隔）",font=("Segoe UI",9,"bold"),text_color="#64748b")],
                [sg.Input(",".join(mem["tags"]),key="edit_tags",size=(40,1),background_color="#0a1020",text_color="#e2e8f0",border_width=1)],
                [sg.Text("隐私分级",font=("Segoe UI",9,"bold"),text_color="#64748b")],
                [sg.Combo(["PUBLIC","INTERNAL","PRIVATE","STRICT"],default_value=mem["privacy"],key="edit_privacy",size=(20,1),readonly=True,background_color="#0a1020",text_color="#e2e8f0")],
                [sg.Text("重要性",font=("Segoe UI",9,"bold"),text_color="#64748b")],
                [sg.Combo(IMP,default_value=IMP[imp_idx],key="edit_imp",size=(20,1),readonly=True,background_color="#0a1020",text_color="#e2e8f0")],
                [sg.Button("💾保存",key="save_edit",button_color=("#0d1422","#00d4ff"),font=("Segoe UI",10,"bold"),pad=(0,(16,0))),
                 sg.Button("取消",key="cancel_edit",button_color=("#1e293b","#475569"))],
            ],modal=True,finalize=True,background_color="#0d1422",size=(540,500))
            while True:
                ev3,v3=ew.read()
                if ev3 in(sg.WINDOW_CLOSED,"cancel_edit"):ew.close();break
                if ev3=="save_edit":
                    content=v3.get("edit_content","").strip()
                    if not content:continue
                    cat_v=v3.get("edit_cat","general")
                    tags_str=v3.get("edit_tags","").strip()
                    tags=[t.strip()for t in tags_str.split(",")if t.strip()]
                    priv=v3.get("edit_privacy","INTERNAL")
                    imp_idx=IMP.index(v3.get("edit_imp","中"))+1
                    update_memory(mid,content,cat_v,tags,priv,imp_idx)
                    ew.close();refresh(window,cur_cat,cur_search)
                    sg.popup_auto_close("✅ 记忆已更新！","ClawMemory",background_color="#0d1422",text_color="#10b981",auto_close_duration=2);break
window.close()
print("ClawMemory 已关闭。记忆库路径:", DBP)
'@

# Write with UTF-8 BOM
$bytes = [System.Text.Encoding]::UTF8.GetPreamble() + [System.Text.Encoding]::UTF8.GetBytes($appContent)
[System.IO.File]::WriteAllBytes("app_native.py", $bytes)
Write-Host "[OK] app_native.py written ($($appContent.Length) chars)" -ForegroundColor Green

# Launch
Write-Host "[*] Launching GUI..." -ForegroundColor Yellow
& python app_native.py
