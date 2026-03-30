                    "低": 1, "中": 2, "高": 3, "关键": 4
                }.get(imp_val, 2)
                    auto_priv = vals2.get("auto_privacy", True)

                    # Auto detect privacy
                    if auto_priv:
                        _, _, suggested = scan_privacy(content)
                        priv = suggested

                    # Auto suggest category
                    if not cat or cat == "general":
                        cat = suggest_category(content)

                    # Auto suggest tags
                    if not tags:
                        tags = suggest_tags(content)

                    mid = add_memory(content, cat, tags, priv, imp)
                    add_win.close()
                    sg.popup_auto_close("✅ 记忆已保存！\nID: " + mid[:8] + "...",
                                       title="成功", background_color="#0d1422",
                                       text_color="#10b981", auto_close_duration=2)
                    refresh_memory_list(window, current_cat, current_search)
                    break

        # Stats button
        if event == "btn_stats":
            stats_win = make_stats_window()
            stats_win.read(close=True)

        # Privacy button
        if event == "btn_privacy":
            priv_win = make_privacy_window()
            priv_win.read(close=True)

        # Export button
        if event == "btn_export":
            stats = get_stats()
            all_mems = get_memories(search="")
            export_data = {
                "version": "1.0.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "count": stats["total"],
                "memories": [],
            }
            for m in all_mems:
                item = dict(m)
                if item["privacy"] in ("PRIVATE", "STRICT"):
                    item["content"] = "[内容已脱敏]"
                item.pop("access_count", None)
                export_data["memories"].append(item)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = CLAWMEMORY_DIR / ("clawmemory_export_" + ts + ".json")
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            sg.popup_auto_close("📤 导出成功！\n文件: " + export_path.name,
                               title="导出", background_color="#0d1422",
                               text_color="#00d4ff", auto_close_duration=3)

        # Memory card click - open edit window
        if event.startswith("card:"):
            mem_id = event[5:]
            mem = get_memory_by_id(mem_id)
            if mem:
                detail_win = make_edit_window(mem)
                detail_win["edit_content"].set_focus()

                while True:
                    ev2, vals2 = detail_win.read()
                    if ev2 in (sg.WINDOW_CLOSED, "cancel_edit"):
                        detail_win.close()
                        break

                    if ev2 == "save_edit":
                        content = vals2.get("edit_content", "").strip()
                        if not content:
                            continue
                        cat = vals2.get("edit_cat", "general")
                        tags_str = vals2.get("edit_tags", "").strip()
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        priv = vals2.get("edit_privacy", "INTERNAL")
                        imp_val = vals2.get("edit_imp", "中")
                        imp = {"低": 1, "中": 2, "高": 3, "关键": 4}.get(imp_val, 2)

                        update_memory(mem_id, content, cat, tags, priv, imp)
                        detail_win.close()
                        sg.popup_auto_close("✅ 记忆已更新！", title="成功",
                                           background_color="#0d1422",
                                           text_color="#10b981", auto_close_duration=2)
                        refresh_memory_list(window, current_cat, current_search)
                        break

        # Delete button
        if event.startswith("del:"):
            mem_id = event[4:]
            ok = sg.popup_yes_no("确认删除这条记忆？",
                                 title="确认删除",
                                 background_color="#0d1422",
                                 text_color="#e2e8f0",
                                 button_color=("#1e293b", "#ef4444"))
            if ok == "Yes":
                delete_memory(mem_id)
                refresh_memory_list(window, current_cat, current_search)
                sg.popup_auto_close("🗑️ 记忆已删除", title="删除",
                                   background_color="#0d1422",
                                   text_color="#f59e0b", auto_close_duration=2)

    window.close()


if __name__ == "__main__":
    main()
