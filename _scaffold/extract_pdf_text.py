# -*- coding: utf-8 -*-
"""
从 中国国标麻将标准PDF 目录下的 PDF 提取全文。

用法:
    python _scaffold/extract_pdf_text.py            # 提取全部 PDF -> _scaffold/pdf_text/*.txt
    python _scaffold/extract_pdf_text.py --stat     # 只统计每页字符数，判断哪个 PDF 带文本层

说明:
    - 目录里同名 PDF 有多个版本（原版 / ocrmypdf 版 / 抽页版），
      ocrmypdf 版通常带 OCR 文本层，因此本脚本对每个 PDF 都输出统计数据，
      便于挑选"文本最全"的那一份作为唯一数据源。
    - 输出文件为 UTF-8(无 BOM) + CRLF，与项目其它文件保持一致。
"""
import os
import sys
import json
import argparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PDF_DIR = os.path.join(ROOT, "中国国标麻将标准PDF")
OUT_DIR = os.path.join(HERE, "pdf_text")


def iter_pdfs():
    for name in sorted(os.listdir(PDF_DIR)):
        if name.lower().endswith(".pdf"):
            yield name, os.path.join(PDF_DIR, name)


def page_text(page):
    """优先 get_text('text')，为空时退回 'blocks' 拼接。"""
    txt = page.get_text("text") or ""
    if not txt.strip():
        blocks = page.get_text("blocks") or []
        txt = "\n".join(b[4] for b in blocks if len(b) > 4 and isinstance(b[4], str))
    return txt


def extract_one(path, want_text=True):
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc):
        pages.append(page_text(page))
    doc.close()
    body = "\n\n".join(
        "===== 第 %d 页 =====\n%s" % (i + 1, t.strip()) for i, t in enumerate(pages)
    )
    return pages, body


def clean(text):
    """轻度清洗：去掉纯空白行、统一全角空格、去掉页眉页码噪声里的多余空格。"""
    lines = []
    for raw in text.splitlines():
        line = raw.replace("\u3000", " ").strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stat", action="store_true", help="只统计，不写文件")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    stats = []
    for name, path in iter_pdfs():
        try:
            pages, body = extract_one(path)
        except Exception as e:  # noqa: BLE001
            print("[FAIL] %s -> %r" % (name, e))
            continue
        chars = sum(len(p.strip()) for p in pages)
        empty = sum(1 for p in pages if not p.strip())
        stats.append({
            "file": name,
            "pages": len(pages),
            "chars": chars,
            "empty_pages": empty,
            "avg": round(chars / len(pages), 1) if pages else 0,
        })
        print("[OK] %-58s 页=%4d 字数=%7d 空页=%3d 均=%6.1f"
              % (name[:58], len(pages), chars, empty,
                 chars / len(pages) if pages else 0))
        if not args.stat and chars > 0:
            safe = name.replace(".pdf", "").replace(" ", "_")
            dst = os.path.join(args.out, safe + ".txt")
            with open(dst, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(clean(body))
            print("     -> %s" % os.path.relpath(dst, ROOT))

    with open(os.path.join(args.out, "_stat.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("\n统计已写入 %s" % os.path.relpath(os.path.join(args.out, "_stat.json"), ROOT))


if __name__ == "__main__":
    main()
