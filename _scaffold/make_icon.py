# -*- coding: utf-8 -*-
"""make_icon.py —— 生成程序图标 `icon.ico`（红中牌样式，多尺寸）

为什么要自己画而不是找一张图：
    · 项目里现成的牌面图只有 44×60（放大到 256 会糊），花牌是高分辨率但图案不适合当图标；
    · 用 `msyh.ttf`（项目里已有）画一个「红中」牌，**每个尺寸单独绘制**（不是缩放同一张），
      16/32 小尺寸下也清晰。

产物：根目录 `icon.ico`（7 张尺寸：16/24/32/48/64/128/256，每张都是 PNG 压缩条目 ——
      Qt 的 QIcon 与 Nuitka 的 --windows-icon-from-ico 都认）。

用法：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/make_icon.py
"""
import io
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "icon.ico")
FONT = os.path.join(ROOT, "msyh.ttf")
SIZES = (16, 24, 32, 48, 64, 128, 256)

# 与界面/Web 端主色一致
BLUE = (47, 127, 240, 255)      # #2f7ff0
WHITE = (255, 255, 255, 255)
RED = (214, 40, 40, 255)        # 红中
GREY = (170, 180, 195, 255)


def _font(size: int):
    try:
        from PIL import ImageFont
        return ImageFont.truetype(FONT, size)
    except Exception:       # noqa: BLE001
        from PIL import ImageFont
        print("[warn] 读不到 %s，退化为内置字体（会难看）" % FONT)
        return ImageFont.load_default()


def draw(size: int):
    """按目标尺寸**单独绘制**一张红中牌图标"""
    from PIL import Image, ImageDraw
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 外层：蓝色圆角底（任务栏上一眼能认出来）
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=max(2, int(s * 0.22)), fill=BLUE)
    # 内层：白色牌面 + 细灰边
    m = max(2, int(s * 0.11))
    ir = max(2, int(s * 0.14))
    d.rounded_rectangle([m, m, s - 1 - m, s - 1 - m], radius=ir,
                        fill=WHITE, outline=GREY, width=max(1, int(s * 0.02)))
    # 红「中」：小尺寸下稍微放大一点更醒目
    fs = int(s * (0.60 if s <= 32 else 0.56))
    f = _font(fs)
    d.text((s / 2, s / 2 + int(s * 0.015)), "中", font=f, fill=RED, anchor="mm")
    return img


def save_ico(path: str, images) -> None:
    """手写 ICO 容器（每张都是 PNG 条目，Qt / Nuitka 都支持）"""
    n = len(images)
    header = struct.pack("<HHH", 0, 1, n)
    entries = b""
    body = b""
    offset = 6 + 16 * n
    for im in images:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        blob = buf.getvalue()
        w = 0 if im.width >= 256 else im.width
        h = 0 if im.height >= 256 else im.height
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(blob), offset)
        body += blob
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(header + entries + body)


def main() -> int:
    try:
        import PIL          # noqa: F401
    except ImportError:
        print("需要 Pillow：pip install pillow")
        return 1
    imgs = [draw(s) for s in SIZES]
    save_ico(OUT, imgs)
    # 顺带导出一张 256 预览图，方便人工肉眼检查
    preview = os.path.join(HERE, "icon_preview.png")
    imgs[-1].save(preview)

    lines = ["已生成 %s（%d 字节，尺寸 %s）"
             % (OUT, os.path.getsize(OUT), "/".join(str(s) for s in SIZES)),
             "预览图 %s" % preview]
    log = os.path.join(HERE, "_icon_out.txt")
    with open(log, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 自检：Qt 能不能读（★ 必须先建 QGuiApplication，否则 Qt 会 qFatal 直接终止进程）
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QGuiApplication, QIcon
        app = QGuiApplication.instance() or QGuiApplication([])      # noqa: F841
        ic = QIcon(OUT)
        lines.append("Qt 读取: %s（可用尺寸 %s）"
                     % ("OK" if not ic.isNull() else "失败",
                        [("%dx%d" % (x.width(), x.height()))
                         for x in ic.availableSizes()]))
    except Exception as exc:        # noqa: BLE001
        lines.append("Qt 自检跳过: %r" % (exc,))

    # 终端管道有时吞输出 → 同时写日志文件
    with open(log, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
