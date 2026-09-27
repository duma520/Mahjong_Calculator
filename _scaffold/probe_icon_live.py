# -*- coding: utf-8 -*-
"""probe_icon_live.py —— 真机验证「窗口图标真的交给了 Windows」

offscreen 下只能验证 QIcon 非空；这里用**真实平台**开窗，
再用 Win32 的 WM_GETICON / GWL_HICON 看窗口是否真的挂上了图标句柄
（任务栏、Alt+Tab、标题栏左上角都取这个句柄）。

用法：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/probe_icon_live.py
"""
import ctypes
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.pop("QT_QPA_PLATFORM", None)          # ★ 真实平台，不用 offscreen
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication          # noqa: E402
import Mahjong_Calculator as M                       # noqa: E402

LOG = []


def say(*a):
    line = " ".join(str(x) for x in a)
    LOG.append(line)
    print(line)


def main() -> int:
    M.settings_path = lambda: os.path.join(HERE, "_probe_icon_settings.json")
    app = QApplication(sys.argv)
    app.setWindowIcon(M.app_icon())

    ic = M.app_icon()
    say("app_icon(): isNull=%s sizes=%s" % (
        ic.isNull(), sorted((s.width(), s.height()) for s in ic.availableSizes())))
    pm32 = ic.pixmap(32, 32)
    say("pixmap(32x32): isNull=%s size=%s" % (pm32.isNull(), pm32.size()))
    img = pm32.toImage()
    # 是否真的画了东西（不是全透明）
    solid = 0
    for y in range(0, img.height(), 4):
        for x in range(0, img.width(), 4):
            if img.pixelColor(x, y).alpha() > 0:
                solid += 1
    say("pixmap(32x32) 非透明采样点: %d" % solid)

    win = M.MahjongFanWindow()
    win.show()
    for _ in range(50):
        app.processEvents()
        time.sleep(0.02)

    say("win.windowIcon(): isNull=%s sizes=%s" % (
        win.windowIcon().isNull(),
        sorted((s.width(), s.height()) for s in win.windowIcon().availableSizes())))

    try:
        hwnd = int(win.winId())
        u = ctypes.windll.user32
        WM_GETICON, ICON_SMALL, ICON_BIG = 0x007F, 0, 1
        big = u.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0)
        small = u.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0)
        cls_big = u.GetClassLongPtrW(hwnd, -14)      # GWL_HICON
        cls_small = u.GetClassLongPtrW(hwnd, -34)    # GWL_HICONSM
        say("hwnd=%s  WM_GETICON big=%s small=%s  class HICON=%s HICONSM=%s"
            % (hwnd, big, small, cls_big, cls_small))
        say("结论: %s" % ("系统已挂上图标 ✓"
                          if (big or small or cls_big or cls_small)
                          else "系统层看不到图标 ✗（任务栏会是默认图标）"))
    except Exception as exc:                         # noqa: BLE001
        say("Win32 检查跳过: %r" % (exc,))

    win.close()
    with open(os.path.join(HERE, "_probe_icon_out.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
