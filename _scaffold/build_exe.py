# -*- coding: utf-8 -*-
"""Nuitka 打包脚本（由根目录 `0_nuitka_pyside6_clang_auto.bat` 调用）

为什么用 Python 而不是把参数全写在 bat 里：
    bat 必须保持**纯 ASCII**（cmd 按字节解析，中文注释/中文路径容易错位），
    而本项目的数据文件叫《国标麻将标准规则.json》、牌面图目录叫《麻将图》，
    用 Python 传参就不会有编码问题。

产物：`build_output\\Mahjong_Calculator.dist\\`（exe + DLL + `麻将图\\` + 规则 JSON），
      **整个 dist 目录一起分发**。

★ v2.7.3：英文名 / 文件名 / exe 名 / 产物目录统一叫 `Mahjong_Calculator`
   主程序 `Mahjong_Calculator.py` → Nuitka 自动产出 `Mahjong_Calculator.exe`；
   **不再把 exe 重命名成中文**（中文名只用于界面显示）。

用法（一般在 bat 里双击调用）：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/build_exe.py
    set EM_SKIP_BUILD=1   # 只做自检，不真正编译
"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = "Mahjong_Calculator.py"
OUT_DIR = "build_output"
# Nuitka 先生成 xxx.dist，编译完再改名成 FINAL_DIR（与英文名完全统一的目录名）
DIST_NAME = "Mahjong_Calculator.dist"
FINAL_DIR = "Mahjong_Calculator"
ICON = "icon.ico"
TILE_DIR = "麻将图"
RULES_JSON = "国标麻将标准规则.json"
EXE_NAME = "Mahjong_Calculator.exe"
# ★ v2.7.3：不再重命名 exe（曾经会改成「国标麻将算番器.exe」）——
#   英文名 / 文件名 / exe / 产物目录统一用 Mahjong_Calculator；中文名只在界面里显示。
EXE_RENAME = ""
# 编译前要检查是否在运行的 exe（含历史名字，它们同样占用 dist 里的文件）
RUNNING_NAMES = (EXE_NAME, "国标麻将算番器.exe", "mahjong_gui.exe")


def _running_exe() -> str:
    """编译前检查目标 exe 是否在运行（占用会导致链接阶段报错）；返回命中的名字"""
    for name in RUNNING_NAMES:
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + name],
                                 capture_output=True, text=True, timeout=20).stdout
        except Exception:       # noqa: BLE001
            continue
        if name.lower() in (out or "").lower():
            return name
    return ""


def build_args() -> list:
    args = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        # ★ v2.6.0：改成 attach —— 双击时照旧是纯 GUI（不弹黑窗），
        #   但被 cmd/subprocess 调用时能挂到父控制台，`--hand ... --json` 的输出才看得见。
        #   （disable 会让 exe 完全丢弃 stdout，命令行算番就没法用了）
        "--windows-console-mode=attach",
        "--follow-imports",
        "--jobs=4",
        "--clang",
        "--remove-output",
        "--output-dir=" + OUT_DIR,
        "--assume-yes-for-downloads",
    ]
    if os.path.exists(os.path.join(ROOT, ICON)):
        args.append("--windows-icon-from-ico=" + ICON)
        args.append("--include-data-files=%s=%s" % (ICON, ICON))
    else:
        print("[warn] 未找到 %s，跳过图标设置" % ICON)

    # 规则数据表
    if os.path.exists(os.path.join(ROOT, RULES_JSON)):
        args.append("--include-data-files=%s=%s" % (RULES_JSON, RULES_JSON))
    else:
        print("[warn] 未找到 %s（算番会退化为内置表）" % RULES_JSON)

    # 牌面图片（整个 麻将图 目录）
    tile_root = os.path.join(ROOT, TILE_DIR)
    n_tiles = 0
    if os.path.isdir(tile_root):
        for name in sorted(os.listdir(tile_root)):
            if name.lower().endswith(".png"):
                rel = "%s/%s" % (TILE_DIR, name)
                args.append("--include-data-files=%s=%s" % (rel, rel))
                n_tiles += 1
    else:
        print("[warn] 未找到牌面图目录 %s" % TILE_DIR)

    args.append(ENTRY)
    print("[info] 牌面图 %d 张；规则表 %s" % (n_tiles, RULES_JSON))
    return args


def main() -> int:
    os.chdir(ROOT)
    print("工作目录: %s" % ROOT)
    args = build_args()

    # 干跑自检放最前面（只看参数对不对，不碰文件，运行时开着 exe 也没关系）
    if os.environ.get("EM_SKIP_BUILD") == "1":
        print("[dry-run] " + " ".join('"%s"' % a if " " in a else a for a in args))
        return 0

    busy = _running_exe()
    if busy:
        print("[error] %s 正在运行，请先关闭再编译" % busy)
        return 2

    rc = subprocess.call(args)
    if rc != 0:
        print("[error] Nuitka 退出码 %d" % rc)
        return rc

    dist = os.path.join(ROOT, OUT_DIR, DIST_NAME)
    src_exe = os.path.join(dist, EXE_NAME)
    if EXE_RENAME and os.path.exists(src_exe):
        try:
            dst_exe = os.path.join(dist, EXE_RENAME)
            if os.path.exists(dst_exe):
                os.remove(dst_exe)
            shutil.move(src_exe, dst_exe)
            print("[info] 已重命名为 %s" % EXE_RENAME)
        except Exception as exc:        # noqa: BLE001
            print("[warn] 重命名失败（不影响使用）: %r" % (exc,))
    # ★ v2.7.3：把 Nuitka 的 `Mahjong_Calculator.dist` 改成最终目录 `Mahjong_Calculator`
    #   （英文名 / 文件名 / exe / 产物目录完全统一，不带 .dist 后缀）
    #   目标已存在时**改名保留**（不直接删 —— 用户上次的产物可能是要发出去的版本）
    final = os.path.join(ROOT, OUT_DIR, FINAL_DIR)
    if os.path.isdir(dist):
        try:
            if os.path.isdir(final):
                stamp = time.strftime("%Y%m%d_%H%M%S")
                os.rename(final, "%s_旧编译_%s" % (final, stamp))
                print("[info] 旧产物目录已保留为 %s_旧编译_%s" % (FINAL_DIR, stamp))
            os.rename(dist, final)
            dist = final
            print("[info] 产物目录已改为 %s（不带 .dist）" % FINAL_DIR)
        except Exception as exc:        # noqa: BLE001
            print("[warn] 目录改名失败（dist 目录也能用）: %r" % (exc,))
    print("[done] 产物目录: %s（整个目录一起分发）" % dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
