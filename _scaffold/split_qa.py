# -*- coding: utf-8 -*-
"""
把《中国麻将竞赛规则(试行)问答》的 OCR 文本切成"篇 / 问 / 答"结构，
并输出一个轻量索引（question_index.txt），便于人工整理到 JSON。

用法:
    python _scaffold/split_qa.py            # 输出索引
    python _scaffold/split_qa.py --full     # 输出索引 + 每题全文（qa_full.txt）
"""
import os
import re
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "pdf_text", "《中国麻将竞赛规则试行》问答——作者：杜维忠_orcmypdf.txt")
OUT_DIR = os.path.join(HERE, "qa_split")

# OCR 噪声行：文化部水印、页码、书名页眉
NOISE = re.compile(
    r"^(文化\s*部\s*共\s*享\s*工\s*程\s*专\s*用"
    r"|国《中国[床麻]将竞赛.*"
    r"|规则[【(（]试行[】)）]?\s*问答.*"
    r"|第\s*\d+\s*页\s*$"
    r"|\d{1,6})$"
)

# 篇标题（占一行）
SECTION = re.compile(r"^[一-龥（）()、\s]{2,20}篇\s*$")

# 问题标题形如 "12.怎样理解……?" 或 "1.《规则》产生的历史背景是什么?"
QUESTION = re.compile(r"^(\d{1,3})\s*[.、．,]\s*(.{4,})\??$")


def load_lines():
    with open(SRC, encoding="utf-8") as f:
        raw = f.read()
    out = []
    page = 0
    for ln in raw.splitlines():
        ln = ln.strip().replace("\u3000", " ")
        m = re.match(r"^=====\s*第\s*(\d+)\s*页\s*=====$", ln)
        if m:
            page = int(m.group(1))
            continue
        if not ln or NOISE.match(ln):
            continue
        out.append((page, ln))
    return out


def split_sections(lines):
    """按"XX篇"切段。"""
    sections = []
    cur = {"title": "（前文）", "items": []}
    for page, ln in lines:
        if SECTION.match(ln) and len(ln) <= 20:
            sections.append(cur)
            cur = {"title": ln, "items": []}
        else:
            cur["items"].append((page, ln))
    sections.append(cur)
    return [s for s in sections if s["items"]]


def main():
    full = "--full" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = load_lines()
    sections = split_sections(lines)

    idx_lines = []
    full_lines = []
    total_q = 0
    for sec in sections:
        idx_lines.append("\n########## %s ##########" % sec["title"])
        full_lines.append("\n########## %s ##########" % sec["title"])
        buf_num, buf_txt, buf_page = None, [], None
        qs = []

        def flush():
            if buf_num is not None:
                qs.append((buf_num, buf_page, " ".join(buf_txt)))

        for page, ln in sec["items"]:
            m = QUESTION.match(ln)
            if m and (len(ln) <= 40 or ln.rstrip().endswith(("?", "？"))):
                flush()
                buf_num, buf_txt, buf_page = int(m.group(1)), [ln], page
            else:
                if buf_num is not None:
                    buf_txt.append(ln)
        flush()

        for num, page, txt in qs:
            total_q += 1
            idx_lines.append("P%03d Q%-3d %s" % (page, num, txt[:70]))
            full_lines.append("\n[P%03d Q%d] %s\n" % (page, num, txt))
        idx_lines.append("  -> 本篇 %d 问" % len(qs))

    idx = os.path.join(OUT_DIR, "question_index.txt")
    with open(idx, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(idx_lines))
    print("索引 -> %s （共 %d 问，%d 篇）" % (os.path.relpath(idx, os.path.dirname(HERE)),
                                              total_q, len(sections)))
    if full:
        dst = os.path.join(OUT_DIR, "qa_full.txt")
        with open(dst, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(full_lines))
        print("全文 -> %s" % os.path.relpath(dst, os.path.dirname(HERE)))


if __name__ == "__main__":
    main()
