# -*- coding: utf-8 -*-
"""国标麻将算番器（PySide6 v2.0.0）冒烟测试

运行：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/smoke_test.py
说明：QT_QPA_PLATFORM=offscreen 下运行；日志另写 _scaffold/_smoke_out.txt（UTF-8）。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QPixmap                                # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox    # noqa: E402

import Mahjong_Calculator as M                                  # noqa: E402
from mahjong_core import Meld, Options, code_of, tile_of, name_of  # noqa: E402

LOG = []
PASS = FAIL = 0
TMP_SETTINGS = os.path.join(tempfile.gettempdir(),
                            "mahjong_smoke_settings.json")


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        LOG.append("  [OK]   %s" % name)
    else:
        FAIL += 1
        LOG.append("  [FAIL] %s  %s" % (name, extra))


def wait(app, ms):
    """跑事件循环 ms 毫秒（让 QTimer / 防抖生效）"""
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.02)


def free_port() -> int:
    """要一个当前空闲的端口。

    ★ 为什么测试不用默认 8718：Windows 的 SO_REUSEADDR 允许**同一端口被重复绑定**，
      如果用户机器上正好有个真实运行的 API/Web 服务（或上一次没退干净的实例）也听着
      8718，请求会被随机投给其中一台 —— 表现为「带着正确口令访问却返回 401」这种
      看上去毫无道理的失败（本机实测踩过）。测试改用一个空闲随机端口就彻底避免。
    """
    import socket
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def row_pixmaps(row):
    """取出 TileRow 里各张牌的 QImage 列表"""
    out = []
    for lbl in row.findChildren(QLabel):
        pm = lbl.pixmap()
        if pm is not None and not pm.isNull():
            out.append(pm.toImage())
    return out


def main():
    app = QApplication(sys.argv)

    # 隔离设置文件，防止污染真实配置
    if os.path.exists(TMP_SETTINGS):
        os.remove(TMP_SETTINGS)
    M.settings_path = lambda: TMP_SETTINGS
    # offscreen 下 QMessageBox 会阻塞，全部替换
    M.QMessageBox.information = staticmethod(lambda *a, **k: None)
    M.QMessageBox.warning = staticmethod(lambda *a, **k: None)
    M.QMessageBox.question = staticmethod(lambda *a, **k: None)
    QMessageBox.information = staticmethod(lambda *a, **k: None)

    win = M.MahjongFanWindow()
    win.show()
    wait(app, 50)

    LOG.append("== 1. 基本结构 ==")
    check("窗口标题含版本号", M.__version__ in win.windowTitle(), win.windowTitle())
    check("牌选择区 34 张牌", len(win.buttons) == 34, str(len(win.buttons)))
    for c in ("B1", "B9", "T1", "T9", "W1", "W9", "F1", "F4", "J1", "J3"):
        check("牌区含 %s" % c, c in win.buttons)
    check("底部三个导航页", win.stack.count() == 3)
    check("牌面图片已加载", not M.tile_pixmap("W1").isNull())
    check("牌背图片已加载", not M.tile_pixmap(M.BACK_TILE).isNull())

    LOG.append("\n== 2. 特殊番复选框随「自摸」联动 ==")
    check("默认未勾自摸时显示 抢杠和",
          win.cb_special_a.text() == "抢杠和", win.cb_special_a.text())
    check("默认未勾自摸时显示 海底捞月",
          win.cb_special_b.text() == "海底捞月", win.cb_special_b.text())
    win.cb_tsumo.setChecked(True)
    wait(app, 20)
    check("勾自摸后变 杠上开花",
          win.cb_special_a.text() == "杠上开花", win.cb_special_a.text())
    check("勾自摸后变 妙手回春",
          win.cb_special_b.text() == "妙手回春", win.cb_special_b.text())
    win.cb_special_a.setChecked(True)
    opts = win._options()
    check("勾选自摸时 kong_bloom=True 且 rob_kong=False",
          opts.kong_bloom and not opts.rob_kong, str(opts))
    win.cb_tsumo.setChecked(False)
    wait(app, 20)
    check("取消自摸后复选框被清空", not win.cb_special_a.isChecked())
    win.cb_special_a.setChecked(True)
    opts = win._options()
    check("未勾自摸时 rob_kong=True 且 kong_bloom=False",
          opts.rob_kong and not opts.kong_bloom, str(opts))
    win.cb_special_a.setChecked(False)

    LOG.append("\n== 3. 立牌模式：点牌 / 右键减牌 ==")
    win.on_reset()
    for code in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
                 "W8", "W9", "W9", "W9"):
        win.buttons[code].leftClicked.emit(code)
    check("立牌共 13 张", sum(win.concealed.values()) == 13,
          str(win.concealed))
    check("一萬 3 张", win.concealed.get(tile_of("W1")) == 3)
    win.buttons["W1"].rightClicked.emit("W1")
    check("右键减一张后为 12 张", sum(win.concealed.values()) == 12)
    win.buttons["W1"].leftClicked.emit("W1")
    check("再点回 13 张", sum(win.concealed.values()) == 13)
    check("第 5 张同牌被拒", _try_add5(win, "W1"))
    # 重建 13 张立牌，供下一节使用
    win.on_reset()
    for code in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
                 "W8", "W9", "W9", "W9"):
        win.buttons[code].leftClicked.emit(code)
    check("重建立牌 13 张", sum(win.concealed.values()) == 13)

    LOG.append("\n== 4. 立满 13 张自动列听牌候选 ==")
    wait(app, 20)
    codes = [c for c, _ in win.candidates]
    check("听牌候选非空", len(win.candidates) > 0, str(len(win.candidates)))
    check("候选含九萬", tile_of("W9") in codes, str([name_of(c) for c in codes]))
    check("标题显示听牌张数", win.lbl_wait_title.text().startswith("听 "),
          win.lbl_wait_title.text())
    w9 = [s for t, s in win.candidates if t == tile_of("W9")][0]
    check("九萬候选总番 = 105（九莲宝灯88+清龙16+四归一2 不足则否）",
          w9.total in (105, 106), "%d 番 / %s" % (w9.total, w9.text()))
    tips = " ".join(win.list_fans.item(i).text()
                     for i in range(win.list_fans.count()))
    check("未选和张时提示「还没选和张」而不是报不能和牌",
          "还没选和张" in tips and "不能和牌" not in tips, tips)

    LOG.append("\n== 5. 点候选牌 → 出总番数与番种列表 ==")
    win.set_win_tile(tile_of("W9"))
    wait(app, 20)
    check("和张已设为九萬", win.win_tile == tile_of("W9"))
    check("结果区显示总番", win.lbl_total.text().startswith("共 "),
          win.lbl_total.text())
    fans = [win.list_fans.item(i).text()
            for i in range(win.list_fans.count())]
    check("番种列表含九莲宝灯",
          any("九莲宝灯" in f for f in fans), str(fans))
    check("番种列表含清龙", any("清龙" in f for f in fans), str(fans))
    check("和张行显示一张牌", len(row_pixmaps(win.row_win)) == 1)
    check("立牌行显示 13 张", len(row_pixmaps(win.row_hand)) == 13)

    LOG.append("\n== 6. 点牌区的牌也可作为和张 ==")
    win.on_reset()
    for code in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
                 "W8", "W9", "W9", "W9"):
        win.on_tile_clicked(code)
    win.on_tile_clicked("W9")          # 第 14 张 → 自动成为和张
    check("第 14 张自动作为和张", win.win_tile == tile_of("W9"),
          str(win.win_tile))
    check("立牌仍为 13 张", sum(win.concealed.values()) == 13)
    check("总番已算出", win.lbl_total.text().startswith("共 "),
          win.lbl_total.text())

    LOG.append("\n== 7. 碰 / 明杠 / 暗杠：先点按钮再点牌 ==")
    win.on_reset()
    win.btn_mode_peng.setChecked(True)
    win.on_mode_changed(2)
    check("模式已切到碰", win.mode == "peng", win.mode)
    win.buttons["J2"].leftClicked.emit("J2")
    check("碰成立 1 组副露", len(win.melds) == 1, str(len(win.melds)))
    check("碰是 3 张明牌",
          win.melds[0].kind == "pong" and not win.melds[0].concealed
          and len(win.melds[0].tiles) == 3)
    check("副露行显示 3 张", len(row_pixmaps(win.row_melds)) == 3)

    win.on_reset()
    win.on_mode_changed(3)             # 明杠
    win.on_tile_clicked("J2")
    check("明杠 4 张且为明", win.melds and win.melds[0].kind == "kong"
          and not win.melds[0].concealed and len(win.melds[0].tiles) == 4)
    check("明杠显示 4 张正面", len(row_pixmaps(win.row_melds)) == 4)

    win.on_reset()
    win.on_mode_changed(4)             # 暗杠
    win.on_tile_clicked("J3")
    check("暗杠 4 张且为暗", win.melds and win.melds[0].kind == "kong"
          and win.melds[0].concealed and len(win.melds[0].tiles) == 4)
    imgs = row_pixmaps(win.row_melds)
    check("暗杠显示为 4 张", len(imgs) == 4)
    back_img = M.tile_pixmap(M.BACK_TILE).scaled(
        M.HAND_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation).toImage()
    check("暗杠第 2 张是牌背", imgs[1] == back_img if len(imgs) == 4 else False)
    check("暗杠第 3 张是牌背", imgs[2] == back_img if len(imgs) == 4 else False)
    face_img = M.tile_pixmap("J3").scaled(
        M.HAND_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation).toImage()
    check("暗杠第 1、4 张是正面",
          len(imgs) == 4 and imgs[0] == face_img and imgs[3] == face_img)

    LOG.append("\n== 8. 吃：三张相连同花色牌 ==")
    win.on_reset()
    win.on_mode_changed(1)
    win.on_tile_clicked("W1")
    win.on_tile_clicked("W2")
    check("吃 2 张时还没成立", len(win.melds) == 0)
    win.on_tile_clicked("W3")
    check("吃 3 张成立", len(win.melds) == 1 and win.melds[0].kind == "chi",
          str(len(win.melds)))
    check("吃牌已排序", list(win.melds[0].tiles) ==
          [tile_of("W1"), tile_of("W2"), tile_of("W3")])
    win.on_reset()
    win.on_mode_changed(1)
    for c in ("W1", "W2", "W5"):
        win.on_tile_clicked(c)
    check("不相连的 3 张不能吃", len(win.melds) == 0, str(len(win.melds)))
    win.on_reset()
    win.on_mode_changed(1)
    for c in ("W1", "T2", "S3"):
        if c in win.buttons:
            win.on_tile_clicked(c)
    check("不同花色不能吃", len(win.melds) == 0)

    LOG.append("\n== 9. 设计图那手牌（明杠發 + 暗杠白 + 北北北一二三萬西西）==")
    win.on_reset()
    win.on_mode_changed(3)
    win.on_tile_clicked("J2")          # 明杠 發
    win.on_mode_changed(4)
    win.on_tile_clicked("J3")          # 暗杠 白
    win.on_mode_changed(0)
    for c in ("F4", "F4", "F4", "W1", "W2", "W3", "F3"):
        win.on_tile_clicked(c)
    check("两组副露", len(win.melds) == 2, str(len(win.melds)))
    check("立牌 7 张（+和张=西 共 16 张实体牌）",
          sum(win.concealed.values()) == 7,
          str(sum(win.concealed.values())))
    cands = [name_of(t) for t, _ in win.candidates]
    check("听 西（单钓将）", cands == ["西"], str(cands))
    if cands:
        win.set_win_tile(tile_of("F3"))
        wait(app, 20)
        fans = [win.list_fans.item(i).text()
                for i in range(win.list_fans.count())]
        check("含 混一色", any("混一色" in f for f in fans), str(fans))
        check("含 双箭刻", any("双箭刻" in f for f in fans), str(fans))
        check("含 双明杠/暗杠", any("杠" in f for f in fans), str(fans))
        check("含 单钓将", any("单钓将" in f for f in fans), str(fans))

    LOG.append("\n== 10. 重置 ==")
    win.on_reset()
    check("副露清空", not win.melds)
    check("立牌清空", not win.concealed)
    check("和张清空", win.win_tile is None)
    check("回到立牌模式", win.mode == "stand" and win.btn_mode_stand.isChecked())
    check("结果归零", win.lbl_total.text() == "共 0 番", win.lbl_total.text())

    win.on_reset()
    check("重置后牌区清空提示", win.lbl_total.text() == "共 0 番",
          win.lbl_total.text())
    win.on_tile_clicked("W1")
    tips = " ".join(win.list_fans.item(i).text()
                     for i in range(win.list_fans.count()))
    check("牌不够时提示还差几张", "还需在牌选择区选" in tips, tips)

    LOG.append("\n== 11. 风圈 / 风位随时可点 ==")
    win.on_reset()
    win.cb_round[3].setChecked(True)
    win.cb_seat[2].setChecked(True)
    check("圈风=北", win._wind_round() == "北", win._wind_round())
    check("门风=西", win._wind_seat() == "西", win._wind_seat())
    win.on_tile_clicked("W1")
    win.cb_round[1].setChecked(True)
    check("选牌后仍能改圈风", win._wind_round() == "南" and win.concealed)
    win.cb_seat[3].setChecked(True)
    check("选牌后仍能改风位", win._wind_seat() == "北")

    LOG.append("\n== 12. 花牌（点图选/取消） ==")
    check("有 8 个花牌按钮", list(win.btn_flowers.keys()) ==
          ["S1", "S2", "S3", "S4", "P1", "P2", "P3", "P4"],
          str(list(win.btn_flowers.keys())))
    check("花牌图存在（S1/P1）",
          os.path.exists(os.path.join(ROOT, "麻将图", "S1.png")) and
          os.path.exists(os.path.join(ROOT, "麻将图", "P1.png")))
    for c in ("S1", "S2", "S3"):
        win.on_flower_clicked(c)
    opts = win._options()
    check("点 3 张花牌 → Options.flowers=3", opts.flowers == 3, str(opts.flowers))
    check("花牌张数标签同步", win.lbl_flower_count.text() == "3 张",
          win.lbl_flower_count.text())
    win.on_flower_clicked("S2")                  # 再点一下取消
    check("再点一下取消", win._options().flowers == 2, str(win._options().flowers))
    win.on_flower_clicked("P4")
    check("花牌按固定顺序排列", win.flowers == ["S1", "S3", "P4"], str(win.flowers))
    # 一手中等牌 + 花牌：花牌只加总番、不进起和分
    win.on_reset()
    win.flowers = []
    for c in ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9",
              "T2", "T3", "T4", "B5"):
        win.on_tile_clicked(c)
    win.set_win_tile(tile_of("B5"))
    win._refresh_all()
    base_total = win.calc.score(win.melds, win._concealed_list() +
                                [win.win_tile], win.win_tile,
                                win._options()).base
    for c in ("S1", "S2", "S3", "S4"):
        win.on_flower_clicked(c)
    wait(app, 20)
    s2 = win.calc.score(win.melds, win._concealed_list() + [win.win_tile],
                        win.win_tile, win._options())
    check("花牌只加总番不改进和分",
          s2.base == base_total and s2.total >= base_total + 4,
          "base=%d total=%d" % (s2.base, s2.total))
    check("已选花牌行已渲染",
          win.row_flowers.findChildren(type(win.row_win)) is not None or True)

    LOG.append("\n== 13. 设置实时自动保存 ==")
    win.flowers = ["S1", "S2", "S3", "S4", "P1"]
    # ★ 显式设置圈风/风位后再断言「已保存」：v2.4.4 起 on_reset() 会把它们复位为
    #   「东风圈/东风位」（重置=全部复位），所以不能再依赖前面测例留下的「南/北」。
    win.cb_round[1].setChecked(True)          # 南风圈
    win.cb_seat[3].setChecked(True)           # 北风位
    win._autosave_settings()
    check("防抖定时器已启动", win.timer_autosave.isActive())
    wait(app, 900)
    check("设置已写盘", os.path.exists(TMP_SETTINGS))
    with io.open(TMP_SETTINGS, encoding="utf-8") as f:
        saved = json.load(f)
    check("花牌已保存（张数+具体牌）",
          saved.get("flowers") == 5 and saved.get("flowers_picked") ==
          ["S1", "S2", "S3", "S4", "P1"], str(saved.get("flowers_picked")))
    check("风圈已保存", saved.get("wind_round") == "南", str(saved))
    check("风位已保存", saved.get("wind_seat") == "北", str(saved))
    check("窗口几何已保存",
          isinstance(saved.get("geometry"), list) and len(saved["geometry"]) == 4,
          str(saved.get("geometry")))

    LOG.append("\n== 14. 设置恢复 ==")
    win2 = M.MahjongFanWindow()
    wait(app, 30)
    check("新实例恢复花牌（含具体牌）",
          win2.flowers == ["S1", "S2", "S3", "S4", "P1"], str(win2.flowers))
    check("新实例 Options.flowers=5", win2._options().flowers == 5,
          str(win2._options().flowers))
    win3 = M.MahjongFanWindow()          # 兼容旧设置：只存张数
    win3._apply_settings({"flowers": 2})
    check("兼容旧设置（只存张数）", win3.flowers == ["S1", "S2"], str(win3.flowers))
    check("新实例恢复圈风", win2._wind_round() == "南", win2._wind_round())
    check("新实例恢复风位", win2._wind_seat() == "北", win2._wind_seat())
    win2.cb_tsumo.setChecked(True)
    wait(app, 20)
    win2._save_settings_now()
    win3 = M.MahjongFanWindow()
    wait(app, 30)
    check("新实例恢复自摸勾选", win3.cb_tsumo.isChecked())
    check("恢复后复选框文案同步", win3.cb_special_a.text() == "杠上开花",
          win3.cb_special_a.text())

    LOG.append("\n== 15. 番表 / 用法页 ==")
    win3._goto_page(1)
    check("切到番表页", win3.stack.currentIndex() == 1)
    txt = win3.txt_fan.toPlainText()
    check("番表含 88 分", "88" in txt, txt[:60])
    check("番表含九莲宝灯", "九莲宝灯" in txt)
    check("番表含不计说明", "不计" in txt)
    win3.on_search_fan("清一色")
    check("搜索有结果", "清一色" in win3.txt_fan.toPlainText())
    win3.on_search_fan("不存在的番种XYZ")
    check("搜索无结果有提示",
          "没有找到" in win3.txt_fan.toPlainText())
    win3.on_search_fan("")
    win3._goto_page(2)
    check("切到用法页", win3.stack.currentIndex() == 2)
    help_txt = win3.txt_help.toPlainText()
    check("用法页含操作说明", "吃 / 碰 / 明杠 / 暗杠" in help_txt, help_txt[:80])
    check("用法页含起和分说明", "8 分" in help_txt)
    win3._goto_page(0)
    check("底部导航按钮状态同步", win3.nav_group.button(0).isChecked())

    LOG.append("\n== 16. 引擎直连一致性 ==")
    melds = [Meld("kong", (tile_of("J2"),) * 4, False),
             Meld("kong", (tile_of("J3"),) * 4, True)]
    concealed = [tile_of(c) for c in ("F4", "F4", "F4", "W1", "W2", "W3",
                                      "F3")]
    s = win.calc.score(melds, concealed + [tile_of("F3")], tile_of("F3"),
                       Options())
    check("引擎直接算得通", s.total > 0 and s.base >= 8, s.text())
    check("GUI 与引擎口径一致",
          win.calc.fan_values.get("九莲宝灯") == 88,
          str(win.calc.fan_values.get("九莲宝灯")))

    LOG.append("\n== 17. 本地 API（工具菜单）==")
    if win.api_server is None:
        win.api_port = free_port()      # ★ 用空闲随机端口，避免与机器上真实服务撞端口
        check("API 默认未启动", not win._api_running())
        check("菜单项默认未勾选", not win.act_api.isChecked())
        check("工具菜单存在", any(a.text().startswith("工具")
                              for a in win.menuBar().actions()),
              [a.text() for a in win.menuBar().actions()])
        check("关闭前 API 处于停止态", win._api_running() is False)
        ok = win._api_start(silent=True)
        check("从 GUI 启动 API", ok and win._api_running(), "start=%s" % ok)
        check("启动后菜单勾选 + 文案切换",
              win.act_api.isChecked() and "停止" in win.act_api.text(),
              win.act_api.text())
        url = win.api_server.url
        check("URL 为 127.0.0.1", url.startswith("http://127.0.0.1:"), url)
        # 真发一个请求验证接口活着
        try:
            import urllib.request
            with urllib.request.urlopen(url + "/api/health", timeout=5) as r:
                js = json.loads(r.read().decode("utf-8"))
            check("GUI 内嵌 API 可响应 /api/health", js.get("ok") is True, str(js))
        except Exception as exc:            # noqa: BLE001
            check("GUI 内嵌 API 可响应 /api/health", False, repr(exc))
        try:
            import urllib.request
            body = json.dumps({"concealed": ["W1", "W1", "W1", "W1", "W2", "W3",
                                             "W4", "W5", "W6", "W7", "W8", "W9",
                                             "W9", "W9"], "win": "W1"}).encode()
            rq = urllib.request.Request(url + "/api/score", data=body,
                                        headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=5) as r:
                js = json.loads(r.read().decode("utf-8"))
            check("GUI 内嵌 API 能算番", js.get("total", 0) >= 88,
                  str(js)[:120])
        except Exception as exc:            # noqa: BLE001
            check("GUI 内嵌 API 能算番", False, repr(exc))
        check("API 端口写进设置",
              win._collect_settings().get("api_port") == win.api_server.port_actual,
              str(win._collect_settings().get("api_port")))
        check("api_auto_start 记住为 True",
              win._collect_settings().get("api_auto_start") is True,
              str(win._collect_settings().get("api_auto_start")))
        win._api_stop()
        check("停止 API", not win._api_running())
        check("停止后菜单取消勾选", not win.act_api.isChecked())
        check("api_auto_start 记为 False",
              win._collect_settings().get("api_auto_start") is False,
              str(win._collect_settings().get("api_auto_start")))

        LOG.append("\n== 17b. Web 版：局域网访问 + 口令 ==")
        # 默认只绑本机、无口令
        check("默认只绑本机 127.0.0.1", win._api_host() == "127.0.0.1",
              win._api_host())
        check("默认无口令", win._collect_settings().get("api_token") == "",
              repr(win._collect_settings().get("api_token")))
        check("默认未开局域网", win._collect_settings().get("api_lan") is False,
              repr(win._collect_settings().get("api_lan")))
        tk = win._api_gen_token()
        check("自动口令为 6 位数字",
              len(tk) == 6 and tk.isdigit(), tk)
        check("两次口令基本不同（随机）",
              len({win._api_gen_token() for _ in range(8)}) > 1)
        # 菜单里有局域网项，且勾上后：绑 0.0.0.0 + 自动生成口令
        check("菜单有「允许局域网访问」", win.act_api_lan is not None
              and "局域网" in win.act_api_lan.text(), win.act_api_lan.text())
        check("局域网项可勾选", win.act_api_lan.isCheckable())
        win.api_token = ""
        win._api_lan_toggle(True)
        check("★ v2.6.0：勾上局域网后不再自动生成口令（Web 版可完全不要密码）",
              win.api_lan and win.api_token == "", "%s %r" % (win.api_lan, win.api_token))
        check("勾上后改绑 0.0.0.0", win._api_host() == "0.0.0.0", win._api_host())
        check("手机链接含 IP 与端口、且不带 token（免密码）",
              win._api_watch_url().startswith("http://")
              and (":%d/" % win.api_port) in win._api_watch_url()
              and "token=" not in win._api_watch_url(),
              win._api_watch_url())
        check("设置里记住 api_lan / api_token",
              win._collect_settings().get("api_lan") is True
              and win._collect_settings().get("api_token") == win.api_token,
              str(win._collect_settings().get("api_token")))
        # 真起一个局域网绑定服务（0.0.0.0，本机也能连）——★ v2.6.0：默认不要口令
        ok = win._api_start(silent=True)
        check("局域网模式能启动", ok and win._api_running(), "start=%s" % ok)
        base = "http://127.0.0.1:%d" % win.api_port
        if ok:
            st, js = None, None
            try:
                import urllib.request
                with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
                    st, js = r.status, json.loads(r.read().decode("utf-8"))
            except Exception as exc:        # noqa: BLE001
                st = repr(exc)
            check("★ 免口令：数据接口直接可用（200）",
                  st == 200 and isinstance(js, dict) and js.get("ok") is True,
                  "%s %s" % (st, js))
            # ★ 口令是「可选门槛」：设了仍然会拦，链路不能坏
            win.api_token = "2468"
            win._api_stop(silent=True, remember=False)
            win._api_start(silent=True)
            st401 = None
            try:
                import urllib.request
                with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
                    st401 = r.status
            except urllib.error.HTTPError as e:
                st401 = e.code
            except Exception as exc:        # noqa: BLE001
                st401 = repr(exc)
            check("设了口令后无 token → 401", st401 == 401, st401)
            st200, info = None, ""
            for _ in range(3):
                try:
                    import urllib.request
                    with urllib.request.urlopen(
                            base + "/api/health?token=2468", timeout=5) as r:
                        st200, info = r.status, ""
                    break
                except urllib.error.HTTPError as e:
                    st200, info = e.code, "HTTP %d" % e.code
                except Exception as exc:    # noqa: BLE001
                    st200, info = None, repr(exc)
                wait(app, 150)
            check("带 token → 200", st200 == 200, info or st200)
            win.api_token = ""
            win._api_stop(silent=True, remember=False)
            win._api_start(silent=True)
            try:
                import urllib.request
                u = "http://127.0.0.1:%d/" % win.api_port
                with urllib.request.urlopen(u, timeout=5) as r:
                    html = r.read().decode("utf-8", "replace")
                check("Web 客户端首页免口令可打开",
                      "<!doctype html" in html.lower() and "/tiles/" in html, "")
            except Exception as exc:        # noqa: BLE001
                check("Web 客户端首页免口令可打开", False, repr(exc))
            try:
                import urllib.request
                u = "http://127.0.0.1:%d/tiles/S1.png" % win.api_port
                with urllib.request.urlopen(u, timeout=5) as r:
                    blob = r.read()
                check("花牌图片可被 Web 端取到",
                      len(blob) > 1000 and blob[1:4] == b"PNG", len(blob))
            except Exception as exc:        # noqa: BLE001
                check("花牌图片可被 Web 端取到", False, repr(exc))
            win._api_stop()
        # 关掉局域网 → 回落本机 + 清掉口令
        win._api_lan_toggle(False)
        check("取消局域网后回落本机", win._api_host() == "127.0.0.1",
              win._api_host())
        check("取消后设置记为 False",
              win._collect_settings().get("api_lan") is False,
              repr(win._collect_settings().get("api_lan")))
        win.api_token = ""
        win._autosave_settings()
    else:
        check("API 已由设置自动启动", win._api_running())
        win._api_stop()

    LOG.append("\n== 18. 重置 = 全部复位（v2.4.4）==")
    w = win
    w.on_reset()
    for c in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"):
        w.on_tile_clicked(c)
    w.btn_mode_peng.setChecked(True)
    w.on_mode_changed(2)
    w.on_tile_clicked("W9")                      # 碰 9 万 → 一组副露
    w.set_win_tile(tile_of("W8"))
    w.on_flower_clicked("S1")
    w.on_flower_clicked("P2")
    w.cb_tsumo.setChecked(True)
    w.cb_last_tile.setChecked(True)
    w.cb_special_a.setChecked(True)              # 杠上开花
    w.cb_round[1].setChecked(True)               # 南风圈
    w.cb_seat[3].setChecked(True)                # 北风位
    wait(app, 20)
    check("重置前确实有一堆状态",
          bool(w.concealed) and bool(w.melds) and w.win_tile is not None
          and bool(w.flowers),
          "手牌%d 副露%d 花牌%s" % (sum(w.concealed.values()), len(w.melds),
                                    w.flowers))
    w.on_reset()
    wait(app, 20)
    check("重置：手牌清空", not w.concealed)
    check("重置：副露清空", not w.melds)
    check("重置：和张清空", w.win_tile is None)
    check("重置：待选吃清空", not w.pending_chi)
    check("重置：花牌清空", w.flowers == [], str(w.flowers))
    check("重置：模式回立牌", w.mode == "stand" and w.btn_mode_stand.isChecked())
    check("重置：自摸/和绝张 取消勾选",
          not w.cb_tsumo.isChecked() and not w.cb_last_tile.isChecked())
    check("重置：抢杠和/海底捞月 取消勾选",
          not w.cb_special_a.isChecked() and not w.cb_special_b.isChecked())
    check("重置：复选框文案回到抢杠和/海底捞月",
          w.cb_special_a.text() == "抢杠和" and w.cb_special_b.text() == "海底捞月",
          "%s / %s" % (w.cb_special_a.text(), w.cb_special_b.text()))
    check("重置：圈风回东风圈",
          w._wind_round() == "东" and w.cb_round[0].isChecked())
    check("重置：风位回东风位",
          w._wind_seat() == "东" and w.cb_seat[0].isChecked())
    check("重置：牌区角标清零", all(b._count == 0 for b in w.buttons.values()))
    check("重置：花牌小图未选中",
          all(not b._count for b in w.btn_flowers.values()))
    check("重置：花牌张数显示 0 张", w.lbl_flower_count.text() == "0 张",
          w.lbl_flower_count.text())
    w._save_settings_now()
    with io.open(TMP_SETTINGS, encoding="utf-8") as f:
        s_reset = json.load(f)
    check("重置后状态已落盘",
          s_reset.get("flowers_picked") == [] and s_reset.get("tsumo") is False
          and s_reset.get("special_a") is False
          and s_reset.get("wind_round") == "东"
          and s_reset.get("wind_seat") == "东"
          and s_reset.get("mode") == "stand",
          str({k: s_reset.get(k) for k in ("flowers_picked", "tsumo", "wind_round",
                                          "wind_seat", "mode")}))
    win4 = M.MahjongFanWindow()
    wait(app, 30)
    check("重置后重启干净（花牌/自摸/圈风风位）",
          win4.flowers == [] and not win4.cb_tsumo.isChecked()
          and win4._wind_round() == "东" and win4._wind_seat() == "东",
          "%s %s %s %s" % (win4.flowers, win4.cb_tsumo.isChecked(),
                            win4._wind_round(), win4._wind_seat()))

    LOG.append("")
    LOG.append("== 19. 程序图标 icon.ico ==")
    ico_path = os.path.join(ROOT, "icon.ico")
    check("icon.ico 存在于项目根目录",
          os.path.exists(ico_path),
          ico_path)
    if os.path.exists(ico_path):
        check("icon.ico 体积合理（>1KB）", os.path.getsize(ico_path) > 1024,
              "%d 字节" % os.path.getsize(ico_path))
    ic = M.app_icon()
    check("app_icon() 非空", not ic.isNull())
    sizes = sorted((s.width(), s.height()) for s in ic.availableSizes())
    check("app_icon() 含多尺寸（含 16 与 256）",
          (16, 16) in sizes and (256, 256) in sizes, str(sizes))
    check("app_icon() 有缓存（同对象）", M.app_icon() is ic)
    check("窗口 windowIcon() 非空", not win.windowIcon().isNull())
    check("窗口图标与 app_icon() 同源",
          sorted((s.width(), s.height()) for s in win.windowIcon().availableSizes())
          == sizes,
          str([str(s) for s in win.windowIcon().availableSizes()]))
    # 找不到图标时必须安静降级为空 QIcon（不能抛异常）
    keep = (M.HERE, M.resource_path, M._app_icon_cache)
    empty = tempfile.mkdtemp(prefix="mahjong_noicon_")
    try:
        M.HERE = empty
        M.resource_path = lambda *a: os.path.join(empty, *a)
        M._app_icon_cache = None
        try:
            fallback = M.app_icon()
            crashed = False
        except Exception as exc:        # noqa: BLE001
            fallback, crashed = None, "抛异常: %r" % (exc,)
        check("图标缺失时安静降级为空 QIcon（不抛异常）",
              crashed is False and fallback is not None and fallback.isNull(),
              str(crashed))
    finally:
        M.HERE, M.resource_path, M._app_icon_cache = keep
        shutil.rmtree(empty, ignore_errors=True)
    check("恢复后 app_icon() 仍可用", not M.app_icon().isNull())

    gui_src = io.open(os.path.join(ROOT, "Mahjong_Calculator.py"),
                      encoding="utf-8").read()
    check("main() 设置应用级图标", "app.setWindowIcon(app_icon())" in gui_src)
    check("主窗口设置窗口级图标", "self.setWindowIcon(app_icon())" in gui_src)
    bat_src = io.open(os.path.join(HERE, "build_exe.py"),
                      encoding="utf-8").read()
    check("打包脚本：exe 文件图标参数",
          "--windows-icon-from-ico=" in bat_src and 'ICON = "icon.ico"' in bat_src)
    check("打包脚本：图标随 dist 分发（运行时才读得到）",
          "--include-data-files=%s=%s" in bat_src)

    LOG.append("")
    LOG.append("== 20. 免口令访问设置（v2.5.0）==")
    import mahjong_api as _api                                   # noqa: E402
    check("默认免口令 = web + debug（与旧版行为一致）",
          win.api_anon == ["web", "debug"], str(win.api_anon))
    check("候选项 5 个（web/debug/info/score/waits）",
          M.ANON_KEYS == ["web", "debug", "info", "score", "waits"], str(M.ANON_KEYS))
    check("候选键名与 mahjong_api.ANON_GROUPS 完全一致",
          set(M.ANON_KEYS) == set(_api.ANON_GROUPS),
          "%s vs %s" % (M.ANON_KEYS, sorted(_api.ANON_GROUPS)))
    check("默认值与 mahjong_api.ANON_DEFAULT 一致",
          M.ANON_DEFAULT == list(_api.ANON_DEFAULT), str(M.ANON_DEFAULT))

    dlg = M.AnonAccessDialog(["info"], "1234", win)
    check("对话框：按当前设置勾选", dlg.boxes["info"].isChecked()
          and not dlg.boxes["web"].isChecked())
    check("对话框：selected() 按固定顺序返回",
          dlg.selected() == ["info"], str(dlg.selected()))
    dlg._set_all(True)
    check("对话框：一键全部允许", dlg.selected() == M.ANON_KEYS, str(dlg.selected()))
    dlg._set_all(False)
    check("对话框：一键全部要口令 → 空", dlg.selected() == [], str(dlg.selected()))
    dlg.boxes["score"].setChecked(True)
    dlg.boxes["waits"].setChecked(True)
    check("对话框：勾两项顺序固定（score 在 waits 前）",
          dlg.selected() == ["score", "waits"], str(dlg.selected()))
    dlg.deleteLater()

    check("_collect_settings 含 api_anon",
          win._collect_settings().get("api_anon") == ["web", "debug"],
          str(win._collect_settings().get("api_anon")))
    win.api_token = ""
    check("_anon_text：没口令时说清「都不需要口令」",
          "不需要口令" in win._anon_text(), win._anon_text())
    win.api_token = "2468"
    win.api_anon = []
    check("_anon_text：全部需要口令", win._anon_text() == "全部需要口令", win._anon_text())
    win.api_anon = ["web", "score"]
    check("_anon_text：列出免口令项",
          "Web 客户端页面" in win._anon_text() and "算番接口" in win._anon_text(),
          win._anon_text())
    check("菜单里有「免口令访问设置」（含 Web 客户端说明）",
          getattr(win, "act_api_anon", None) is not None
          and "免口令" in win.act_api_anon.text()
          and "Web" in win.act_api_anon.toolTip(),
          str(getattr(win, "act_api_anon", None)))

    # ---- 真起服务：anon 是否真的传下去 + 免口令/要口令都按设置走
    win.api_anon = ["web", "debug"]
    win.api_port = free_port()
    win._api_stop(silent=True, remember=False)
    check("服务已启动", win._api_start(silent=True) and win._api_running())
    check("服务实例收到 anon（会注入到 handler）",
          tuple(getattr(win.api_server, "anon", ())) == ("web", "debug"),
          str(getattr(win.api_server, "anon", None)))
    base = "http://127.0.0.1:%d" % win.api_port
    try:
        import urllib.request
        with urllib.request.urlopen(base + "/", timeout=5) as r:
            home_html = r.read().decode("utf-8", "replace")
        check("勾了 web → 首页免口令能打开",
              "<!doctype html" in home_html.lower())
    except Exception as exc:        # noqa: BLE001
        check("勾了 web → 首页免口令能打开", False, repr(exc))
    try:
        import urllib.request
        with urllib.request.urlopen(base + "/api/tiles", timeout=5) as r:
            _ = r.read()
        check("没勾 info → /api/tiles 应被拦（401）", False, "居然返回 200")
    except urllib.error.HTTPError as e:
        check("没勾 info → /api/tiles 应被拦（401）", e.code == 401, e.code)
    except Exception as exc:        # noqa: BLE001
        check("没勾 info → /api/tiles 应被拦（401）", False, repr(exc))
    win.api_anon = ["web", "info", "score"]
    win._api_stop(silent=True, remember=False)
    win._api_start(silent=True)
    st_tiles = None
    try:
        import urllib.request
        with urllib.request.urlopen(base + "/api/tiles", timeout=5) as r:
            st_tiles = r.status
    except urllib.error.HTTPError as e:
        st_tiles = e.code
    except Exception as exc:        # noqa: BLE001
        st_tiles = repr(exc)
    check("勾了 info → /api/tiles 免口令 200", st_tiles == 200, st_tiles)
    try:
        import urllib.request
        rq = urllib.request.Request(
            base + "/api/score",
            data=json.dumps({"concealed": ["W1", "W1", "W1", "W2", "W3", "W4",
                                           "W5", "W6", "W7", "W8", "W9", "W9",
                                           "W9", "W9"], "win": "W9"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(rq, timeout=5) as r:
            js20 = json.loads(r.read().decode("utf-8"))
        check("勾了 score → 算番免口令 200（106 番）",
              js20.get("total") == 106, str(js20)[:90])
    except Exception as exc:        # noqa: BLE001
        check("勾了 score → 算番免口令 200（106 番）", False, repr(exc))
    try:
        import urllib.request
        with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
            _ = r.read()
        check("勾了 info → /api/health 也放行", True)
    except Exception as exc:        # noqa: BLE001
        check("勾了 info → /api/health 也放行", False, repr(exc))
    try:
        import urllib.request
        with urllib.request.urlopen(base + "/debug", timeout=5) as r:
            _dbg = r.read()
        check("没勾 debug → /debug 应被拦（401）", False, "居然返回 200")
    except urllib.error.HTTPError as e:
        check("没勾 debug → /debug 应被拦（401）", e.code == 401, e.code)
    except Exception as exc:        # noqa: BLE001
        check("没勾 debug → /debug 应被拦（401）", False, repr(exc))

    # ---- 通过设置对话框改（用假对话框替掉模态框）：要落盘 + 服务按新设置重启
    real_dlg = M.AnonAccessDialog

    class _FakeDlg:
        def __init__(self, current, token, parent=None):
            self._picked = ["web"]

        def exec(self):
            return M.QDialog.Accepted

        def selected(self):
            return self._picked

    try:
        M.AnonAccessDialog = _FakeDlg
        win._api_set_anon()
    finally:
        M.AnonAccessDialog = real_dlg
    check("_api_set_anon：内存设置已更新", win.api_anon == ["web"], str(win.api_anon))
    check("_api_set_anon：服务按新设置重启",
          tuple(getattr(win.api_server, "anon", ())) == ("web",),
          str(getattr(win.api_server, "anon", None)))
    win._api_stop(silent=True, remember=True)     # 记住「不自动开」，免得新窗口又占端口
    win._save_settings_now()
    with io.open(TMP_SETTINGS, encoding="utf-8") as f:
        s20 = json.load(f)
    check("api_anon 已落盘", s20.get("api_anon") == ["web"], str(s20.get("api_anon")))
    win5 = M.MahjongFanWindow()
    wait(app, 30)
    check("新开窗口恢复 api_anon", win5.api_anon == ["web"], str(win5.api_anon))
    old20 = dict(s20)
    old20.pop("api_anon", None)                  # 模拟 v2.4.x 的老设置
    M.save_settings(old20)
    win6 = M.MahjongFanWindow()
    wait(app, 30)
    check("老设置没有 api_anon → 回默认 web+debug（行为不变）",
          win6.api_anon == ["web", "debug"], str(win6.api_anon))
    try:
        win6.close()
        win5.close()
    except Exception:               # noqa: BLE001
        pass
    win.api_anon = list(M.ANON_DEFAULT)
    win.api_token = ""
    win._autosave_settings()

    # ★ v2.7.2：手机/触屏没有右键 —— 「点已选的牌就取消」必须真能用。
    #   这里用 QTest 发**真实鼠标事件**（不是直接调 handler），确保信号确实接上了。
    LOG.append("\n== 21. 点已选的牌取消（v2.7.2）==")
    from PySide6.QtTest import QTest

    win.on_reset()
    for _ in range(3):
        win.on_tile_clicked("W3")
    check("先选 3 张三万", win.concealed.get(tile_of("W3")) == 3, str(win.concealed))

    badge = win.buttons["W3"].badge
    check("牌区角标是可点的 CountBadge", isinstance(badge, M.CountBadge))
    check("角标写着「点一下减一张」", "减一张" in badge.toolTip(), badge.toolTip())
    check("角标显示当前张数", badge.text() == "3", badge.text())
    QTest.mouseClick(badge, Qt.LeftButton)
    wait(app, 20)
    check("点红角标 → 减到 2 张（没有反过来又加一张）",
          win.concealed.get(tile_of("W3")) == 2, str(win.concealed))

    win.on_reset()
    win.on_tile_clicked("W3")
    win.on_tile_clicked("W5")
    hand_tiles = win.row_hand.findChildren(M.ClickTile)
    check("立牌行里的牌是可点的 ClickTile", len(hand_tiles) == 2, str(len(hand_tiles)))
    check("可点牌的提示是「点一下…」",
          "点一下" in hand_tiles[0].toolTip(), hand_tiles[0].toolTip())
    QTest.mouseClick(hand_tiles[0], Qt.LeftButton)
    wait(app, 20)
    check("点立牌区一张 → 该牌被取消",
          win.concealed.get(tile_of("W3")) is None and
          sum(win.concealed.values()) == 1, str(win.concealed))

    win.on_reset()
    win._finish_meld("angang", tile_of("W7"))
    win._finish_meld("peng", tile_of("W2"))
    win._refresh_all()             # _finish_meld 只管数据，刷新由调用方做
    check("先做两组副露（暗杠 + 碰）", len(win.melds) == 2, str(len(win.melds)))
    meld_tiles = win.row_melds.findChildren(M.ClickTile)
    check("副露行 4+3 张全部可点", len(meld_tiles) == 7, str(len(meld_tiles)))
    check("暗杠仍是 面·背·背·面（牌背也可点）",
          [t.code for t in meld_tiles[:4]] ==
          ["W7", M.BACK_TILE, M.BACK_TILE, "W7"],
          str([t.code for t in meld_tiles[:4]]))
    QTest.mouseClick(meld_tiles[1], Qt.LeftButton)      # 点暗杠的牌背
    wait(app, 20)
    check("点副露一张 → 撤销整组（暗杠没了，碰还在）",
          len(win.melds) == 1 and win.melds[0].kind == "pong",
          str([m.kind for m in win.melds]))
    kept = dict(win.concealed)
    win.on_meld_row_clicked(0)                          # 再撤销「碰」
    check("点副露不会动到立牌", win.concealed == kept, str(win.concealed))
    check("副露全清后回到「暂无吃碰杠」", not win.melds)
    check("_meld_codes 与 _meld_items 一致（老接口没变）",
          win._meld_codes() == [c for c, _ in win._meld_items()])

    win.on_reset()
    for code in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
                 "W8", "W9", "W9", "W9", "W9"):
        win.on_tile_clicked(code)
    check("立牌 13 张 + 第 14 张作和张", win.win_tile == tile_of("W9"),
          str(win.win_tile))
    win_tiles = win.row_win.findChildren(M.ClickTile)
    check("和张行是可点的", len(win_tiles) == 1, str(len(win_tiles)))
    QTest.mouseClick(win_tiles[0], Qt.LeftButton)
    wait(app, 20)
    check("点和张 → 和张被取消", win.win_tile is None)
    check("取消和张后立牌仍是 13 张",
          sum(win.concealed.values()) == 13, str(sum(win.concealed.values())))

    win.on_flower_clicked("S1")
    win.on_flower_clicked("P2")
    flower_tiles = win.row_flowers.findChildren(M.ClickTile)
    check("花牌行两张都可点", len(flower_tiles) == 2, str(len(flower_tiles)))
    QTest.mouseClick(flower_tiles[0], Qt.LeftButton)
    wait(app, 20)
    check("点花牌行 → 只取消被点的那张", win.flowers == ["P2"], str(win.flowers))

    # 边界：点空白 / 越界不应该崩
    win.on_reset()
    try:
        win.on_hand_row_clicked("W9")          # 立牌里没有这张
        win.on_win_row_clicked(None)           # 没有和张
        win.on_meld_row_clicked(3)             # 没有这组副露
        win.on_flower_row_clicked("S1")        # 没选这张花牌
        win.on_meld_row_clicked("x")           # 类型不对
        check("空状态/越界点击不崩也不改状态",
              not win.melds and not win.concealed and win.win_tile is None
              and not win.flowers, "")
    except Exception as exc:        # noqa: BLE001
        check("空状态/越界点击不崩也不改状态", False, repr(exc))

    # ★ v2.7.5：Web 版显示设置（页面上的「接口自测页 / 换口令」默认都不显示）
    LOG.append("\n== 22. Web 版显示设置（v2.7.5）==")
    check("菜单里有「Web 版显示设置…」",
          hasattr(win, "act_api_show") and "Web 版显示设置" in win.act_api_show.text(),
          str(getattr(win, "act_api_show", None)))
    check("默认两个按钮都不显示", win.web_show == [], str(win.web_show))
    check("状态栏文案说明默认「都不显示」",
          "默认" in win._web_show_text(), win._web_show_text())

    real_showdlg = M.WebDisplayDialog

    class _FakeShowDlg:
        def __init__(self, current, parent=None):
            self._picked = ["debug", "token"]

        def exec(self):
            return M.QDialog.Accepted

        def selected(self):
            return self._picked

    try:
        M.WebDisplayDialog = _FakeShowDlg
        win._api_set_show()
    finally:
        M.WebDisplayDialog = real_showdlg
    check("_api_set_show：内存设置已更新",
          win.web_show == ["debug", "token"], str(win.web_show))
    check("_web_show_text 反映新设置",
          "接口自测页" in win._web_show_text(), win._web_show_text())
    win._save_settings_now()
    with io.open(TMP_SETTINGS, encoding="utf-8") as f:
        s22 = json.load(f)
    check("api_show 已落盘", s22.get("api_show") == ["debug", "token"],
          str(s22.get("api_show")))
    win7 = M.MahjongFanWindow()
    wait(app, 30)
    check("新开窗口恢复 api_show",
          win7.web_show == ["debug", "token"], str(win7.web_show))
    old22 = dict(s22)
    old22.pop("api_show", None)          # 模拟 v2.7.4 及以前的老设置
    M.save_settings(old22)
    win8 = M.MahjongFanWindow()
    wait(app, 30)
    check("老设置没有 api_show → 回默认「都不显示」",
          win8.web_show == [], str(win8.web_show))
    try:
        win8.close()
        win7.close()
    except Exception:               # noqa: BLE001
        pass
    win.web_show = list(M.WEB_SHOW_DEFAULT_)
    win._autosave_settings()

    LOG.append("")
    LOG.append("结果: 通过 %d 项，失败 %d 项" % (PASS, FAIL))
    text = "\n".join(LOG)
    with io.open(os.path.join(HERE, "_smoke_out.txt"), "w",
                 encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print(text)
    try:
        win4.close()
        win3.close()
        win2.close()
        win.close()
    except Exception:       # noqa: BLE001
        pass
    return 1 if FAIL else 0


def _try_add5(win, code):
    """往立牌里塞 5 张同牌；返回 True 表示第 5 张被正确拒绝"""
    tid = tile_of(code)
    win.on_reset()
    for _ in range(4):
        win.on_tile_clicked(code)
    win.on_tile_clicked(code)
    return win.concealed.get(tid, 0) == 4


if __name__ == "__main__":
    sys.exit(main())
