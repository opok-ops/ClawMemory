#!/usr/bin/env python3
# append2.py - Append event loop to app_native.py
# This adds the main() event loop + tail

TAIL = """
def main():
    init_db(); seed_demo()
    cats = list(CAT_LB.keys())
    cat_btns = {}
    for c in cats:
        cat_btns[c] = sg.Button(CI[c]+" "+LB[c], key="cat:"+c, font=("Segoe UI",9),
            button_color=("#1e293b","#00d4ff" if c=="all" else "#475569"),
            border_width=0, pad=(2,2), Size=(9,1))

    header = [
        sg.Text("🧠 ClawMemory", font=("Segoe UI",16,"bold"), text_color="#00d4ff"),
        sg.Text("AI Agent终身记忆系统", font=("Segoe UI",9), text_color="#475569", pad=((4,0),0)),
        sg.Push(),
        sg.Text(key="stat_text", font=("Segoe UI",9), text_color="#475569"),
        sg.Button("📊统计", key="btn_stats", button_color=("#1e293b","#475569"), font=("Segoe UI",9), pad=(4,0)),
        sg.Button("🛡️隐私", key="btn_privacy", button_color=("#1e293b","#475569"), font=("Segoe UI",9), pad=(4,0)),
        sg.Button("📤导出", key="btn_export", button_color=("#1e293b","#475569"), font=("Segoe UI",9), pad=(4,0)),
        sg.Button("➕添加", key="btn_add", button_color=("#0d1422","#00d4ff"), font=("Segoe UI",10,"bold"), pad=(8,0)),
    ]

    search_row = [
        sg.Text("🔍", font=("Segoe UI",10), text_color="#475569", pad=(8,0)),
        sg.Input(key="search", size=(40,1), background_color="#0a1020", text_color="#e2e8f0", border_width=0, font=("Segoe UI",10), pad=(4,0), enable_events=True, tooltip="搜索..."),
        sg.Button("✕", key="clear_search", button_color=("transparent","transparent"), text_color="#475569", font=("Segoe UI",9), visible=False, tooltip="清除"),
    ]

    layout = [
        [sg.Column([header], background_color="#0d1422", pad=(16,12))],
        [sg.HorizontalSeparator(color="#1e3a5f")],
        [sg.Column([[cat_btns[c] for c in cats]], background_color="#0d1422", pad=(12,8), expand_x=True, element_justification="center")],
        [sg.Column([search_row], background_color="#0d1422", pad=(12,4), expand_x=True)],
        [sg.HorizontalSeparator(color="#0d1422")],
        [sg.Column([[sg.Text("正在加载...", text_color="#334155", font=("Segoe UI",10))]], key="memory_area", expand_x=True, expand_y=True, scrollable=True, vertical_scroll_only=True, background_color="#0d1422", pad=(8,4))],
        [sg.HorizontalSeparator(color="#1e3a5f", pad=(0,4))],
        [sg.Column([[sg.Text(key="status_text", font=("Segoe UI",8), text_color="#334155")]], background_color="#0d1422", pad=(16,8))],
    ]

    window = sg.Window("ClawMemory - AI Agent终身记忆系统", layout, finalize=True,
        background_color="#0d1422", resizable=True, size=(1000,700), min_size=(700,500))
    window["search"].bind("<Return>","_enter")
    refresh(window, "all", "")
    cur_cat = "all"; cur_search = ""

    while True:
        event, values = window.read(timeout=100)
        if event in (sg.WINDOW_CLOSED,): break

        if event.startswith("cat:"):
            cat = event[4:]; cur_cat = cat
            for c in cats: cat_btns[c].update(button_color=("#1e293b","#00d4ff" if c==cat else "#475569"))
            refresh(window, cur_cat, cur_search)

        if event == "search":
            q = values.get("search",""); cur_search = q
            window["clear_search"].update(visible=bool(q))
            refresh(window, cur_cat, cur_search)
        if event in ("clear_search","search_enter"):
            window["search"].update(""); cur_search = ""
            window["clear_search"].update(visible=False)
            refresh(window, cur_cat, "")

        if event == "btn_add":
            aw = make_add_win(); aw["add_content"].set_focus()
            while True:
                ev2, v2 = aw.read()
                if ev2 in (sg.WINDOW_CLOSED,"cancel_add"): aw.close(); break
                if ev2 == "save_add":
                    content = v2.get("add_content","").strip()
                    if not content: continue
                    cat_v = v2.get("add_cat","general")
                    tags_str = v2.get("add_tags","").strip()
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                    priv = v2.get("add_privacy","INTERNAL")
                    imp_idx = IMP.index(v2.get("add_imp","中")) + 1
                    if v2.get("auto_priv"):
                        _, _, suggested = scan_privacy(content); priv = suggested
                    if not tags: tags = suggest_tags(content)
                    mid = add_memory(content, cat_v, tags, priv, imp_idx)
                    aw.close(); refresh(window, cur_cat, cur_search)
                    sg.popup_auto_close("✅ 记忆已保存！\nID: "+mid[:8]+"...", title="成功", background_color="#0d1422", text_color="#10b981", auto_close_duration=2); break

        if event == "btn_stats":
            sw = make_stats_win(); sw.read(close=True)

        if event == "btn_privacy":
            pw = make_privacy_win(); pw.read(close=True)

        if event == "btn_export":
            all_m = get_memories(search=""); export = []
            for m in all_m:
                item = dict(m)
                if item["privacy"] in ("PRIVATE","STRICT"): item["content"] = "【内容已脱敏】"
                item.pop("access_count", None); export.append(item)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = CLAWMEMORY_DIR / ("clawmemory_export_"+ts+".json")
            with open(path,"w",encoding="utf-8") as f: json.dump({"version":"1.0.0","exported_at":datetime.now(timezone.utc).isoformat(),"count":len(export),"memories":export},f,ensure_ascii=False,indent=2)
            sg.popup_auto_close("✅ 导出成功！\n文件: "+path.name, title="导出", background_color="#0d1422", text_color="#00d4ff", auto_close_duration=3)

        if event.startswith("del:"):
            mid = event[4:]
            ok = sg.popup_yes_no("确认删除这条记忆？", title="确认删除", background_color="#0d1422", text_color="#e2e8f0", button_color=("#1e293b","#ef4444"))
            if ok == "Yes": delete_memory(mid); refresh(window, cur_cat, cur_search); sg.popup_auto_close("🗑️ 记忆已删除", title="删除", background_color="#0d1422", text_color="#f59e0b", auto_close_duration=2)

        if event.startswith("card:"):
            mid = event[5:]; mem = get_memory_by_id(mid)
            if mem:
                imp_idx = mem["importance"] - 1
                ew = sg.Window("✏️编辑记忆 - ClawMemory", [
                    [sg.Text("✏️ 编辑记忆", font=("Segoe UI",13,"bold"), text_color="#00d4ff")],
                    [sg.HorizontalSeparator(color="#1e3a5f")],
                    [sg.Text("内容", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                    [sg.Multiline(mem["content"], key="edit_content", size=(60,6), background_color="#0a1020", text_color="#e2e8f0", border_width=1, focus=True)],
                    [sg.Text("分类", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                    [sg.Combo(list(CAT_LB.keys()), default_value=mem["category"], key="edit_cat", size=(20,1), readonly=True, background_color="#0a1020", text_color="#e2e8f0")],
                    [sg.Text("标签（逗号分隔）", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                    [sg.Input(",".join(mem["tags"]), key="edit_tags", size=(40,1), background_color="#0a1020", text_color="#e2e8f0", border_width=1)],
                    [sg.Text("隐私分级", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                    [sg.Combo(["PUBLIC","INTERNAL","PRIVATE","STRICT"], default_value=mem["privacy"], key="edit_privacy", size=(20,1), readonly=True, background_color="#0a1020", text_color="#e2e8f0")],
                    [sg.Text("重要性", font=("Segoe UI",9,"bold"), text_color="#64748b")],
                    [sg.Combo(IMP, default_value=IMP[imp_idx], key="edit_imp", size=(20,1), readonly=True, background_color="#0a1020", text_color="#e2e8f0")],
                    [sg.Button("💾保存", key="save_edit", button_color=("#0d1422","#00d4ff"), font=("Segoe UI",10,"bold"), pad=(0,(16,0))),
                     sg.Button("取消", key="cancel_edit", button_color=("#1e293b","#475569"))],
                ], modal=True, finalize=True, background_color="#0d1422", size=(540,500))
                while True:
                    ev3, v3 = ew.read()
                    if ev3 in (sg.WINDOW_CLOSED,"cancel_edit"): ew.close(); break
                    if ev3 == "save_edit":
                        content = v3.get("edit_content","").strip()
                        if not content: continue
                        cat_v = v3.get("edit_cat","general")
                        tags_str = v3.get("edit_tags","").strip()
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        priv = v3.get("edit_privacy","INTERNAL")
                        imp_idx = IMP.index(v3.get("edit_imp","中")) + 1
                        update_memory(mid, content, cat_v, tags, priv, imp_idx)
                        ew.close(); refresh(window, cur_cat, cur_search)
                        sg.popup_auto_close("✅ 记忆已更新！", title="成功", background_color="#0d1422", text_color="#10b981", auto_close_duration=2); break

    window.close()
    print("ClawMemory GUI 已关闭。记忆数据保存在:", DB_PATH)

if __name__ == "__main__": main()
"""

with open("app_native2.py", "w", encoding="utf-8") as f:
    f.write(TAIL)
print("Tail written, length:", len(TAIL))
