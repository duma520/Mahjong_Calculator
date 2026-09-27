# -*- coding: utf-8 -*-
"""
《中国麻将竞赛规则(试行)问答》OCR 正文切分 v3。

改进点：题干在 OCR 中常被拆成"题号单独一行 + 题干下一行"，
本版用"题号必须严格递增（N == 上一题 + 1）"来锁定真正的题目起始行，
并把随后的行合并为题干，直到出现 '?' / '？' 或超过 60 字。

用法:
    python _scaffold/split_qa3.py                      # 索引
    python _scaffold/split_qa3.py --full               # 索引 + qa_full.txt
    python _scaffold/split_qa3.py --full --range 50 90 # 只要某段题号
    python _scaffold/split_qa3.py --dump 60            # 打印第 60 题的原文
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "pdf_text", "《中国麻将竞赛规则试行》问答——作者：杜维忠_orcmypdf.txt")
OUT_DIR = os.path.join(HERE, "qa_split")

BODY_START_PAGE = 15
MAX_Q_LEN = 60
NUM_ONLY = re.compile(r"^(\d{1,3})\s*[.、．,]?$")
NUM_Q = re.compile(r"^(\d{1,3})\s*[.、．,]?\s*(\S.*)$")
BLOCK = re.compile(r"^=====\s*第\s*(\d+)\s*页\s*=====$")


def load_pages():
    pages, page = {}, 0
    with open(SRC, encoding="utf-8") as f:
        for raw in f:
            ln = raw.strip().replace("\u3000", " ")
            m = BLOCK.match(ln)
            if m:
                page = int(m.group(1))
                pages.setdefault(page, [])
                continue
            if ln:
                pages.setdefault(page, []).append(ln)
    return pages


def collect(pages):
    """返回 [{num, page, q, a}]；题号允许小幅跳跃（OCR 偶尔漏掉一个题号）。"""
    questions = {}
    expect = 1
    cur = None
    for page in sorted(pages):
        if page < BODY_START_PAGE:
            continue
        for ln in pages[page]:
            m = NUM_ONLY.match(ln) or NUM_Q.match(ln)
            n = int(m.group(1)) if m else None
            if n is not None and expect <= n <= expect + 3 and n not in questions:
                cur = {"num": n, "page": page, "q": [], "a": []}
                questions[n] = cur
                expect = n + 1
                continue
            if cur is None:
                continue
            qtext = " ".join(cur["q"])
            if len(qtext) < MAX_Q_LEN and not qtext.rstrip().endswith(("?", "？")):
                cur["q"].append(ln)
            else:
                cur["a"].append(ln)
    return [questions[k] for k in sorted(questions)]


def main():
    full = "--full" in sys.argv
    lo, hi = 0, 999
    if "--range" in sys.argv:
        i = sys.argv.index("--range")
        lo, hi = int(sys.argv[i + 1]), int(sys.argv[i + 2])
    os.makedirs(OUT_DIR, exist_ok=True)
    items = collect(load_pages())

    if "--dump" in sys.argv:
        n = int(sys.argv[sys.argv.index("--dump") + 1])
        for it in items:
            if it["num"] == n:
                print("[Q%d | P%03d]\n题干: %s\n答案:\n%s"
                      % (n, it["page"], " ".join(it["q"]), " ".join(it["a"])))
                return
        print("未找到第 %d 题" % n)
        return

    items = [it for it in items if lo <= it["num"] <= hi]
    idx, body = ["题号  页   题干（'?'表示题干可能被 OCR 截断）"], []
    for it in items:
        q = " ".join(it["q"])[:80]
        idx.append("%4d  P%03d %s%s" % (it["num"], it["page"], q,
                                        "" if q.endswith(("?", "？")) else " ?"))
        body.append("\n[Q%d | P%03d] %s\n%s\n"
                    % (it["num"], it["page"], " ".join(it["q"]), " ".join(it["a"])))
    p = os.path.join(OUT_DIR, "question_index.txt")
    with open(p, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(idx))
    print("索引 -> %s （%d 题）" % (os.path.relpath(p, os.path.dirname(HERE)), len(items)))
    if full:
        p2 = os.path.join(OUT_DIR, "qa_full.txt")
        with open(p2, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(body))
        print("全文 -> %s （%d 字节）" % (os.path.relpath(p2, os.path.dirname(HERE)),
                                         os.path.getsize(p2)))


if __name__ == "__main__":
    main()
