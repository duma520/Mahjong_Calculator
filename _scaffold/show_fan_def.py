# -*- coding: utf-8 -*-
"""从规则 JSON 里导出指定番种的定义原文（核对用）"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"G:\Python_Code\Mahjong_Calculator\国标麻将标准规则.json"
NAMES = sys.argv[1:] or ["绿一色", "推不倒"]
j = json.load(open(P, encoding="utf-8"))
for k, items in j["番种"].items():
    for it in items:
        if it["name"] in NAMES:
            print("=== %s（%s分）不计=%s" % (it["name"], it.get("fan"),
                                            it.get("不计")))
            print("   定义:", (it.get("definition") or "").replace("\n", ""))
            print("   补充:", " / ".join(it.get("补充") or []))
