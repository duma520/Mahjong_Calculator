# -*- coding: utf-8 -*-
"""mahjong_gui.py 冒烟测试（离屏运行）

覆盖：
  1) 规则 JSON 结构与番种数量
  2) 主程序可导入、窗口可创建、标题带版本号
  3) 设置实时自动保存（防抖 → 写盘 → 新实例恢复）
  4) 窗口几何 / 最大化标志持久化
  5) 「重置」立即落盘、closeEvent 强制保存
  6) 缺失 mahjong_core 时降级不崩

运行（PowerShell 用 & 调用）：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/smoke_test.py
日志同时写入 _scaffold/_smoke_out.txt（UTF-8），避免管道丢输出。
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

LOG = []
PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        LOG.append("  [OK]   %s" % name)
    else:
        FAIL += 1
        LOG.append("  [FAIL] %s %s" % (name, extra))


def main():
    tmp = tempfile.mkdtemp(prefix="mahjong_smoke_")
    try:
        LOG.append("== 1. 规则 JSON 校验 ==")
        rules_path = os.path.join(ROOT, "国标麻将标准规则.json")
        with io.open(rules_path, encoding="utf-8") as f:
            rules = json.load(f)
        fans = rules["番种"]
        total = sum(len(v) for v in fans.values())
        check("规则文件可解析", bool(rules))
        check("番种总数为 81", total == 81, "实际 %d" % total)
        check("分值级 12 级", len(rules["番种体系"]["分值等级"]) == 12)
        check("起和分为 8", rules["番种体系"]["起和分"] == 8)
        check("不计列表均为 list", all(
            isinstance(item.get("不计", []), list)
            for group in fans.values() for item in group))
        check("问答条目已收录", len(rules["问答"]["番种定义及计分篇"]["条目"]) == 81,
              "实际 %d" % len(rules["问答"]["番种定义及计分篇"]["条目"]))

        LOG.append("== 2. 导入与创建窗口 ==")
        import mahjong_gui as M
        # 把设置/资源目录重定向到临时目录，避免污染真实设置
        M.app_dir = lambda: tmp
        M.resource_path = lambda name: os.path.join(tmp, name)

        check("模块版本号存在", bool(getattr(M, "__version__", "")))
        check("未导入 mahjong_core 时给出错误记录", M.CORE_IMPORT_ERROR is not None
              or M.MahjongFanCalculator is not None)

        from PyQt5.QtWidgets import QApplication, QMessageBox
        # 离屏下模态框会永久阻塞，全部替换掉
        M.QMessageBox = type("MB", (), {
            "about": staticmethod(lambda *a, **k: None),
            "information": staticmethod(lambda *a, **k: None),
            "warning": staticmethod(lambda *a, **k: None),
            "question": staticmethod(lambda *a, **k: None),
        })
        QMessageBox.information = staticmethod(lambda *a, **k: None)
        QMessageBox.warning = staticmethod(lambda *a, **k: None)
        QMessageBox.about = staticmethod(lambda *a, **k: None)

        app = QApplication.instance() or QApplication(sys.argv)
        w1 = M.MahjongFanCalculatorUI()
        check("窗口标题含版本号", M.__version__ in w1.windowTitle(), w1.windowTitle())
        check("设置定时器为防抖单次", w1._settings_save_timer.isSingleShot()
              and w1._settings_save_timer.interval() == 500)
        check("圈风/门风各 4 个按钮", len(w1.round_wind_group) == 4 and len(w1.seat_wind_group) == 4)
        check("花牌 8 个", all(hasattr(w1, "%s_spin" % n) for n in M.FLOWER_NAMES))

        LOG.append("== 3. 每次启动都会把 .pyc 目录以外的缺失核心降级处理 ==")
        w1.hint_label.text()  # 访问一次，确保属性存在
        check("提示标签可访问", True)

        LOG.append("== 4. 设置实时自动保存 ==")
        sp = os.path.join(tmp, M.SETTINGS_FILE)
        if os.path.exists(sp):
            os.remove(sp)
        w1.round_wind_group[1].setChecked(True)     # 圈风=南
        w1.seat_wind_group[3].setChecked(True)      # 门风=北
        w1.自摸_checkbox.setChecked(True)
        w1.春_spin.setValue(1)
        w1.竹_spin.setValue(1)
        check("控件变更后启动防抖定时器", w1._settings_save_timer.isActive())

        # 等待防抖
        import time
        deadline = time.time() + 3
        while time.time() < deadline and not os.path.exists(sp):
            app.processEvents()
            time.sleep(0.05)

        check("设置已写盘", os.path.exists(sp), sp)
        if os.path.exists(sp):
            data = json.load(io.open(sp, encoding="utf-8"))
            check("写入 round_wind=南", data.get("round_wind") == "南", str(data.get("round_wind")))
            check("写入 seat_wind=北", data.get("seat_wind") == "北", str(data.get("seat_wind")))
            check("写入 special_fans 含自摸", "自摸" in (data.get("special_fans") or []))
            check("写入 flowers.春=1", (data.get("flowers") or {}).get("春") == 1)
            check("写入 window_geometry(4元素)",
                  isinstance(data.get("window_geometry"), list)
                  and len(data.get("window_geometry")) == 4)
            check("写入 window_maximized 布尔", isinstance(data.get("window_maximized"), bool))

        LOG.append("== 5. 新实例恢复设置 ==")
        w2 = M.MahjongFanCalculatorUI()
        check("恢复圈风=南", w2.get_selected_wind(w2.round_wind_group) == "南",
              str(w2.get_selected_wind(w2.round_wind_group)))
        check("恢复门风=北", w2.get_selected_wind(w2.seat_wind_group) == "北")
        check("恢复自摸勾选", w2.自摸_checkbox.isChecked())
        check("恢复春=1", w2.春_spin.value() == 1)
        check("恢复竹=1", w2.竹_spin.value() == 1)
        w3 = M.MahjongFanCalculatorUI()
        check("加载设置期间未触发自动保存", not w3._settings_save_timer.isActive())

        LOG.append("== 6. 重置立即落盘 & closeEvent 强制保存 ==")
        calls = {"n": 0}
        raw_save = M.save_settings

        def spy_save(d):
            calls["n"] += 1
            return raw_save(d)

        M.save_settings = spy_save
        try:
            w3.on_action_clicked("重置")
            check("重置后立即保存（不走防抖）", calls["n"] >= 1, "calls=%d" % calls["n"])
            data2 = json.load(io.open(sp, encoding="utf-8"))
            check("重置已清空圈风", data2.get("round_wind") is None)
            check("重置已清空花牌", all(v == 0 for v in (data2.get("flowers") or {}).values()))

            before = calls["n"]
            w3.close()
            check("closeEvent 强制保存", calls["n"] > before, "before=%d after=%d" % (before, calls["n"]))
        finally:
            M.save_settings = raw_save

        LOG.append("== 7. 核心缺失时的降级行为 ==")
        if w1.calculator is None:
            w1.selected_tiles = ["W1"] * 14
            w1.check_winning_hand()
            check("core 缺失时 check_winning_hand 不抛异常", True)
            check("提示中带占位说明", "占位" in w1.hint_label.text(), w1.hint_label.text())
            w1.analyze_ting()
            check("core 缺失时 analyze_ting 不抛异常", True)
            w1.update_calculation()
            check("core 缺失时给出明确提示",
                  "mahjong_core" in w1.ting_result_label.text(), w1.ting_result_label.text())
        else:
            LOG.append("  [SKIP] mahjong_core 可用，跳过降级用例")

        LOG.append("== 8. 关于/来源对话框不阻塞 ==")
        w1.show_about()
        w1.show_rules_info()
        check("关于与来源对话框可打开", True)

        LOG.append("== 9. 设置文件为 UTF-8 无 BOM 且可原子替换 ==")
        with open(sp, "rb") as f:
            head = f.read(3)
        check("无 BOM", head != b"\xef\xbb\xbf")
        check("无残留 .tmp", not os.path.exists(sp + ".tmp"))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    LOG.append("")
    LOG.append("结果: 通过 %d 项，失败 %d 项" % (PASS, FAIL))
    text = "\n".join(LOG)
    with io.open(os.path.join(HERE, "_smoke_out.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print(text)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
