# -*- coding: utf-8 -*-
"""
把 qa_full.txt 压缩成便于阅读的 qa_compact.txt：
  - 丢掉"牌例图"产生的符号噪声行（CJK 占比过低的行）
  - 丢掉水印/页码/页眉
  - 每条答案截断到 --cap 个字符
用法:
    python _scaffold/compact_qa.py [--cap 800] [--range a b]
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "qa_split", "qa_full.txt")
DST = os.path.join(HERE, "qa_split", "qa_compact.txt")

CJK = re.compile(r"[\u4e00-\u9fff]")
NOISE = re.compile(r"文化\s*部\s*共\s*享\s*工\s*程|中国麻将.*问答|规则\s*[（(【]\s*试行\s*[)）】]?\s*问答|^\[?[EI]{2,}\]?$|^\d{1,3}$")


def clean_answer(text, cap):
    keep = []
    for tok in text.split(" "):
        if not tok or NOISE.search(tok):
            continue
        cjk = len(CJK.findall(tok))
        if cjk < 3 or cjk / max(len(tok), 1) < 0.45:   # 牌图符号行
            continue
        keep.append(tok)
    s = "，".join(keep)
    s = re.sub(r"[，,]{2,}", "，", s)
    return s[:cap] + ("……" if len(s) > cap else "")


def main():
    cap = 800
    if "--cap" in sys.argv:
        cap = int(sys.argv[sys.argv.index("--cap") + 1])
    lo, hi = 0, 999
    if "--range" in sys.argv:
        i = sys.argv.index("--range")
        lo, hi = int(sys.argv[i + 1]), int(sys.argv[i + 2])

    with open(SRC, encoding="utf-8") as f:
        raw = f.read()

    blocks = re.findall(r"\[Q(\d+) \| P(\d+)\]\s*(.*?)\n(.*?)(?=\n\[Q|\Z)", raw, re.S)
    out = []
    for num, page, q, a in blocks:
        n = int(num)
        if not (lo <= n <= hi):
            continue
        out.append("Q%-3d P%s | %s\n    %s\n" % (n, page, q.strip(), clean_answer(a.strip(), cap)))

    with open(DST, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(out))
    print("压缩 %d 条 -> %s （%d 字节）" % (len(out), os.path.relpath(DST, os.path.dirname(HERE)),
                                           os.path.getsize(DST)))


if __name__ == "__main__":
    main()
