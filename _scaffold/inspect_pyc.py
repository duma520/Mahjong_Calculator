# -*- coding: utf-8 -*-
"""
反查 __pycache__/mahjong_core.cpython-310.pyc —— 源码 mahjong_core.py 已丢失，
用本脚本把 .pyc 里的模块级名字、类、方法、常量与关键字节码打印出来，
以便后续据此重建 mahjong_core.py。

用法:
    python _scaffold/inspect_pyc.py
"""
import dis
import marshal
import os
import sys
import types

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PYC = os.path.join(ROOT, "__pycache__", "mahjong_core.cpython-310.pyc")


def load_code(path):
    with open(path, "rb") as f:
        f.read(16)                    # PEP 552 header (magic + flags + mtime + size)
        return marshal.load(f)


def brief_const(c):
    if isinstance(c, types.CodeType):
        return "<code %s>" % c.co_name
    s = repr(c)
    return s if len(s) <= 160 else s[:160] + "..."


def walk(code, indent=0):
    pad = "  " * indent
    print("%s=== code: %s  (args=%s, vars=%s, flags=%#x) ==="
          % (pad, code.co_name, code.co_varnames[:code.co_argcount], code.co_varnames, code.co_flags))
    consts = [brief_const(c) for c in code.co_consts if not isinstance(c, types.CodeType)]
    if consts:
        print("%s  consts: %s" % (pad, ", ".join(consts)))
    print("%s  names : %s" % (pad, ", ".join(code.co_names)))
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            walk(c, indent + 1)


def main():
    if not os.path.exists(PYC):
        sys.stdout.write("找不到 %s\n" % PYC)
        return
    # 结果同时写入 _scaffold/pyc_dump.txt（UTF-8），避免 PowerShell 重定向写成 UTF-16
    dump = os.path.join(HERE, "pyc_dump.txt")
    buf = []

    def out(*args, **kw):
        s = " ".join(str(a) for a in args)
        buf.append(s)
        sys.stdout.write(s + "\n")

    global print
    real_print = sys.stdout.write

    def _p(*args, **kw):
        out(*args)

    print = _p
    try:
        code = load_code(PYC)
        print("# 文件: %s (%d 字节)" % (os.path.relpath(PYC, ROOT), os.path.getsize(PYC)))
        print("# 顶层名字: " + ", ".join(code.co_names))
        print()
        walk(code)
        print("\n\n########## 顶层字节码 ##########")
        dis.dis(code)
    finally:
        print = _p  # 保持同一实现即可
    with open(dump, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(buf))
    real_print("\n完整报告已写入 %s\n" % os.path.relpath(dump, ROOT))



if __name__ == "__main__":
    main()
