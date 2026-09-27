# -*- coding: utf-8 -*-
"""界面截图脚本（真实平台，可看到字体效果）

运行：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/shot_ui.py
输出：_scaffold/shots/ui_*.png
"""
import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
SHOTS = os.path.join(HERE, "shots")

from PySide6.QtWidgets import QApplication      # noqa: E402
import Mahjong_Calculator as M                 # noqa: E402
from mahjong_core import tile_of                # noqa: E402


def wait(app, ms):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.02)


def shot(win, name):
    app = QApplication.instance()
    wait(app, 250)
    path = os.path.join(SHOTS, name)
    win.grab().save(path, "PNG")
    print("已保存 %s" % path)


def main():
    os.makedirs(SHOTS, exist_ok=True)
    # 截图用临时设置文件，避免覆盖真实设置；每次从干净状态开始
    shot_settings = os.path.join(tempfile.gettempdir(),
                                 "mahjong_shot_settings.json")
    if os.path.exists(shot_settings):
        os.remove(shot_settings)
    M.settings_path = lambda: shot_settings
    app = QApplication(sys.argv)
    win = M.MahjongFanWindow()
    # ★ 用程序自己的默认窗口尺寸截图（v2.4.3 起 = 680×940；以前这里硬编码 1180×980，
    #   截图比真实默认外观宽很多，看不出牌池是否铺得开）
    win.resize(M.WIN_W, M.WIN_H)
    win.show()
    wait(app, 400)

    shot(win, "ui_1_empty.png")

    # 设计图 174223：一萬×3 + 二萬~八萬 + 九萬×3
    win.on_reset()
    for c in ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
              "W9", "W9", "W9"):
        win.on_tile_clicked(c)
    shot(win, "ui_2_ting.png")

    win.set_win_tile(tile_of("W9"))
    win.cb_tsumo.setChecked(True)
    win.cb_special_b.setChecked(True)     # 妙手回春
    for c in ("S1", "S2", "P1"):          # ★ 花牌（春 夏 梅）
        win.on_flower_clicked(c)
    shot(win, "ui_3_win.png")
    win._goto_page(1)
    shot(win, "ui_7_flowers_fantable.png")
    win._goto_page(0)

    # 设计图 174132：明杠發 + 暗杠白 + 北北北 + 一二三萬 + 西，和张 西
    win.on_reset()
    win.cb_tsumo.setChecked(False)
    win.on_mode_changed(3)
    win.on_tile_clicked("J2")
    win.on_mode_changed(4)
    win.on_tile_clicked("J3")
    win.on_mode_changed(0)
    for c in ("F4", "F4", "F4", "W1", "W2", "W3", "F3"):
        win.on_tile_clicked(c)
    win.set_win_tile(tile_of("F3"))
    shot(win, "ui_4_melds.png")

    win._goto_page(1)
    shot(win, "ui_5_fan_table.png")
    win._goto_page(2)
    shot(win, "ui_6_help.png")
    win.close()
    print("截图完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
