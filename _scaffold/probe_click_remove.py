# -*- coding: utf-8 -*-
"""真机验证 v2.7.2「点已选的牌就取消」（真实平台 + 真实鼠标事件）

offscreen 下 QTest 也能发鼠标事件，但真实平台的窗口层级/几何不同 —— 红角标是牌按钮的
子控件，只有真实点击才能真正说明「点角标不会反过来又加一张」，所以这里再跑一遍真机。

运行：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/probe_click_remove.py
日志：_scaffold/_probe_click_out.txt
"""
import io
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PySide6.QtCore import Qt                              # noqa: E402
from PySide6.QtTest import QTest                            # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

import Mahjong_Calculator as M                             # noqa: E402
from mahjong_core import tile_of                            # noqa: E402

TMP = os.path.join(HERE, "_probe_click_settings.json")
LOG = []
PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        LOG.append("  [OK]   %s" % name)
    else:
        FAIL += 1
        LOG.append("  [FAIL] %s  %s" % (name, extra))


def wait(app, ms):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    app = QApplication(sys.argv)
    if os.path.exists(TMP):
        os.remove(TMP)
    M.settings_path = lambda: TMP
    M.QMessageBox.information = staticmethod(lambda *a, **k: None)
    M.QMessageBox.warning = staticmethod(lambda *a, **k: None)

    win = M.MahjongFanWindow()
    win.show()
    wait(app, 500)

    LOG.append("== 真机：点已选的牌取消（v2.7.2）==")
    LOG.append("平台: %s" % app.platformName())

    # ① 牌选择区红角标：点一下 = 减一张（角标在牌按钮里，最容易误变成「加一张」）
    win.on_reset()
    for _ in range(3):
        win.on_tile_clicked("W3")
    badge = win.buttons["W3"].badge
    check("角标可见且显示 3",
          badge.isVisible() and badge.text() == "3",
          "text=%s visible=%s" % (badge.text(), badge.isVisible()))
    QTest.mouseClick(badge, Qt.LeftButton)
    wait(app, 150)
    check("点红角标 → 减到 2 张（没有变成 4 张）",
          win.concealed.get(tile_of("W3")) == 2, str(win.concealed))

    # ② 立牌行点一张
    win.on_reset()
    win.on_tile_clicked("W3")
    win.on_tile_clicked("W3")
    win.on_tile_clicked("W5")
    tiles = win.row_hand.findChildren(M.ClickTile)
    check("立牌行 3 张（两张三万 + 一张五万）都是可点牌",
          len(tiles) == 3, str(len(tiles)))
    QTest.mouseClick(tiles[0], Qt.LeftButton)
    wait(app, 150)
    check("点立牌一张 → 该牌减一张",
          win.concealed.get(tile_of("W3")) == 1, str(win.concealed))

    # ③ 副露：点任意一张（含暗杠牌背）= 撤销那一组
    win.on_reset()
    win._finish_meld("angang", tile_of("W7"))
    win._finish_meld("peng", tile_of("W2"))
    win._refresh_all()
    mt = win.row_melds.findChildren(M.ClickTile)
    check("副露行 4+3 张全部可点", len(mt) == 7, str(len(mt)))
    QTest.mouseClick(mt[2], Qt.LeftButton)          # 暗杠的牌背
    wait(app, 150)
    check("点副露 → 撤销那一组（暗杠没了，碰还在）",
          len(win.melds) == 1 and win.melds[0].kind == "pong",
          str([m.kind for m in win.melds]))

    # ④ 和张：点一下 = 取消和张
    win.on_reset()
    for code in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
                 "W8", "W9", "W9", "W9", "W9"):
        win.on_tile_clicked(code)
    wt = win.row_win.findChildren(M.ClickTile)
    check("和张行可点", len(wt) == 1, str(len(wt)))
    QTest.mouseClick(wt[0], Qt.LeftButton)
    wait(app, 150)
    check("点和张 → 取消和张", win.win_tile is None, str(win.win_tile))

    # ⑤ 花牌行：点一下 = 取消那张花牌
    win.on_reset()
    win.on_flower_clicked("S1")
    win.on_flower_clicked("P2")
    ft = win.row_flowers.findChildren(M.ClickTile)
    check("花牌行两张都可点", len(ft) == 2, str(len(ft)))
    QTest.mouseClick(ft[1], Qt.LeftButton)
    wait(app, 150)
    check("点花牌行 → 只取消被点的那张", win.flowers == ["S1"], str(win.flowers))

    LOG.append("")
    LOG.append("结果: 通过 %d 项，失败 %d 项" % (PASS, FAIL))
    text = "\n".join(LOG)
    with io.open(os.path.join(HERE, "_probe_click_out.txt"), "w",
                 encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print(text)

    try:
        win.close()
    except Exception:       # noqa: BLE001
        pass
    if os.path.exists(TMP):
        try:
            os.remove(TMP)
        except OSError:
            pass
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
