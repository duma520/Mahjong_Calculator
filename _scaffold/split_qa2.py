# -*- coding: utf-8 -*-
"""
把《中国麻将竞赛规则(试行)问答》OCR 正文（第 15 页起）切成 问/答 结构。

用法:
    python _scaffold/split_qa2.py                 # 只输出索引（题号+题干）
    python _scaffold/split_qa2.py --full          # 另输出 qa_full.txt（含答案）
    python _scaffold/split_qa2.py --full --range 100 140   # 只输出题号区间
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "pdf_text", "《中国麻将竞赛规则试行》问答——作者：杜维忠_orcmypdf.txt")
OUT_DIR = os.path.join(HERE, "qa_split")

BODY_START_PAGE = 15          # 正文起始页（1~14 是封面与目录）
QUESTION = re.compile(r"^(\d{1,3})\s*[.、．,]?\s*(.{2,60}?[?？])$")


def load_pages():
    pages = {}
    page = 0
    with open(SRC, encoding="utf-8") as f:
        for raw in f:
            ln = raw.strip().replace("\u3000", " ")
            m = re.match(r"^=====\s*第\s*(\d+)\s*页\s*=====$", ln)
            if m:
                page = int(m.group(1))
                pages.setdefault(page, [])
                continue
            if ln:
                pages.setdefault(page, []).append(ln)
    return pages


def collect(pages):
    items = []
    cur = None
    for page in sorted(pages):
        if page < BODY_START_PAGE:
            continue
        for ln in pages[page]:
            m = QUESTION.match(ln)
            if m:
                if cur:
                    items.append(cur)
                cur = {"num": int(m.group(1)), "page": page, "q": [m.group(2)], "a": []}
            elif cur is not None:
                cur["a"].append(ln)
    if cur:
        items.append(cur)
    return items


def main():
    full = "--full" in sys.argv
    lo, hi = 0, 999
    if "--range" in sys.argv:
        i = sys.argv.index("--range")
        lo, hi = int(sys.argv[i + 1]), int(sys.argv[i + 2])

    os.makedirs(OUT_DIR, exist_ok=True)
    items = [it for it in collect(load_pages()) if lo <= it["num"] <= hi]
    items.sort(key=lambda x: x["num"])

    idx = ["题号  页   题干"]
    full_txt = []
    for it in items:
        q = " ".join(it["q"])
        idx.append("%4d  P%03d %s" % (it["num"], it["page"], q[:80]))
        full_txt.append("\n[Q%d | P%03d] %s\n%s\n"
                        % (it["num"], it["page"], q, " ".join(it["a"])))

    p = os.path.join(OUT_DIR, "question_index.txt")
    with open(p, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(idx))
    print("索引 -> %s （%d 题）" % (os.path.relpath(p, os.path.dirname(HERE)), len(items)))

    if full:
        p2 = os.path.join(OUT_DIR, "qa_full.txt")
        with open(p2, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(full_txt))
        print("全文 -> %s （%d 字节）" % (os.path.relpath(p2, os.path.dirname(HERE)),
                                         os.path.getsize(p2)))


if __name__ == "__main__":
    main()
