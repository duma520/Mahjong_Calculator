# -*- coding: utf-8 -*-
"""golden_fans.py —— 81 个番种的「金标准牌例」表（供 verify_all.py 使用）

每条 = (番种名, 副露, 手牌, 和张, 选项)
    副露: "" 或 "chi:B1;pong:J1;mkong:F1;akang:F2"（吃/碰/明杠/暗杠，用 ; 分隔）
    手牌: "W1x3 T2 B5x2"（xN 表示 N 张；必须满足 len = 14 - 3×副露组数）
    和张: 牌码（必须在手牌里）
    选项: "" 或 "tsumo,last_tile,kong_bloom,last_draw,last_discard,rob_kong,
          round:东,seat:西,flowers:3"

作用：证明 81 个番种**每一个都真的能被算出来**（防止判定函数恒假＝漏算），
     同时对每一例再做一次独立实现交叉校验。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mahjong_core import Meld, Options, tile_of        # noqa: E402

# 常用手牌缩写
_PONG4 = "W2x3 W3x3 W4x3 W5x3 B5x2"          # 4 刻 + 将（碰碰和）
_CHOW4 = "W1 W2 W3 T4 T5 T6 B2 B3 B4 W7 W8 W9 W5x2"   # 4 顺 + 数牌将（平和）

GOLDEN = [
    # ---------------- 88 分 ----------------
    ("大四喜", "", "F1x3 F2x3 F3x3 F4x3 J1x2", "J1", ""),
    ("大三元", "", "J1x3 J2x3 J3x3 W1x3 W9x2", "W9", ""),
    ("绿一色", "", "T2x3 T3x3 T4x3 T6x3 T8x2", "T8", ""),
    ("九莲宝灯", "", "W1x4 W2 W3 W4 W5 W6 W7 W8 W9x3", "W1", ""),
    ("四杠", "mkong:F1;mkong:F2;mkong:F3;mkong:F4", "J1x2", "J1", ""),
    ("连七对", "", "B1x2 B2x2 B3x2 B4x2 B5x2 B6x2 B7x2", "B7", ""),
    ("十三幺", "", "B1 B9 T1 T9 W1 W9 F1 F2 F3 F4 J1 J2 J3x2", "J3", ""),
    # ---------------- 64 分 ----------------
    ("清幺九", "", "B1x3 B9x3 T1x3 T9x3 W1x2", "W1", ""),
    ("小四喜", "", "F1x3 F2x3 F3x3 W5x3 F4x2", "F4", ""),
    ("小三元", "", "J1x3 J2x3 W1x3 W2x3 J3x2", "J3", ""),
    ("字一色", "", "F1x3 F2x3 J1x3 J2x3 F3x2", "F3", ""),
    ("四暗刻", "", "W1x3 T2x3 B3x3 F1x3 J1x2", "J1", ""),
    ("一色双龙会", "", "B1x2 B2x2 B3x2 B7x2 B8x2 B9x2 B5x2", "B5", ""),
    # ---------------- 48 分 ----------------
    ("一色四同顺", "", "T1x4 T2x4 T3x4 W5x2", "W5", ""),
    ("一色四节高", "", "B2x3 B3x3 B4x3 B5x3 W5x2", "W5", ""),
    # ---------------- 32 分 ----------------
    ("一色四步高", "", "B1 B2 B3 B2 B3 B4 B3 B4 B5 B4 B5 B6 W5x2", "W5", ""),
    ("三杠", "mkong:F1;akang:F2;mkong:F3", "W5x3 W9x2", "W9", ""),
    ("混幺九", "", "F1x3 B1x3 T9x3 W9x3 J1x2", "J1", ""),
    # ---------------- 24 分 ----------------
    ("七对", "", "B1x2 B2x2 B4x2 B5x2 B7x2 B8x2 J1x2", "J1", ""),
    ("七星不靠", "", "F1 F2 F3 F4 J1 J2 J3 W1 W4 W7 T2 T5 T8 B3", "B3", ""),
    ("全双刻", "", "B2x3 B4x3 B6x3 B8x3 W2x2", "W2", ""),
    ("清一色", "", "W1x3 W2x3 W3x3 W4x3 W5x2", "W5", ""),
    ("一色三同顺", "chi:B1;chi:B1", "B1 B2 B3 B4 B5 B6 B5x2", "B5", ""),
    ("一色三节高", "", "B2x3 B3x3 B4x3 W9x3 W5x2", "W5", ""),
    ("全大", "", "W7x3 W8x3 W9x3 B7x3 T9x2", "T9", ""),
    ("全中", "", "B4x3 B5x3 B6x3 T4x3 W5x2", "W5", ""),
    ("全小", "", "B1x3 B2x3 B3x3 T2x3 W1x2", "W1", ""),
    # ---------------- 16 分 ----------------
    ("清龙", "", "W1 W2 W3 W4 W5 W6 W7 W8 W9 B5x3 T9x2", "T9", ""),
    ("三色双龙会", "", "B1 B2 B3 B7 B8 B9 T1 T2 T3 T7 T8 T9 W5x2", "W5", ""),
    ("一色三步高", "", "B1 B2 B3 B2 B3 B4 B3 B4 B5 W9x3 W5x2", "W5", ""),
    ("全带五", "", "B3 B4 B5 T4 T5 T6 W5 W6 W7 B5x3 T5x2", "T5", ""),
    ("三同刻", "", "B3x3 T3x3 W3x3 W9x3 B5x2", "B5", ""),
    ("三暗刻", "pong:B9", "W1x3 T2x3 W3x3 B5x2", "B5", ""),
    # ---------------- 12 分 ----------------
    ("全不靠", "", "F1 F2 F3 J1 J2 J3 W1 W4 W7 T2 T5 T8 B3 B6", "B6", ""),
    ("组合龙", "", "W1 W4 W7 T2 T5 T8 B3 B6 B9 B2x3 W9x2", "W9", ""),
    ("大于五", "", "B6x3 B7x3 B8x3 B9x3 W7x2", "W7", ""),
    ("小于五", "", "B1x3 B2x3 B3x3 B4x3 W4x2", "W4", ""),
    ("三风刻", "", "F1x3 F2x3 F3x3 W1x3 B9x2", "B9", ""),
    # ---------------- 8 分 ----------------
    ("花龙", "", "B1 B2 B3 T4 T5 T6 W7 W8 W9 B5x3 W3x2", "W3", ""),
    ("推不倒", "", "B1x3 B2x3 B3x3 B4x3 B5x2", "B5", ""),
    ("三色三同顺", "", "B1 B2 B3 T1 T2 T3 W1 W2 W3 B5x3 W5x2", "W5", ""),
    ("三色三节高", "", "B2x3 T3x3 W4x3 B9x3 W5x2", "W5", ""),
    ("无番和", "chi:B2", "T4 T5 T6 W6 W7 W8 W2 W3 W1 F1x2", "W1", ""),
    ("妙手回春", "", _PONG4, "B5", "tsumo,last_draw"),
    ("海底捞月", "", _PONG4, "B5", "last_discard"),
    ("杠上开花", "", _PONG4, "B5", "tsumo,kong_bloom"),
    ("抢杠和", "", _PONG4, "B5", "rob_kong"),
    # ---------------- 6 分 ----------------
    ("碰碰和", "pong:W4", "F3x3 W2x3 W3x3 B5x2", "B5", ""),
    ("混一色", "", "W1x3 W2x3 W3x3 W5x3 J1x2", "J1", ""),
    ("三色三步高", "", "B1 B2 B3 T2 T3 T4 W3 W4 W5 B9x3 T9x2", "T9", ""),
    ("五门齐", "", "B1 B2 B3 T4 T5 T6 W7 W8 W9 F1x3 J1x2", "J1", ""),
    ("全求人", "chi:B1;pong:J2;mkong:F1;mkong:F2", "W9x2", "W9", ""),
    ("双暗杠", "akang:J1;akang:J2", "W1x3 W2x3 W9x2", "W9", ""),
    ("双箭刻", "", "J1x3 J2x3 W1x3 W2x3 W9x2", "W9", ""),
    # ---------------- 4 分 ----------------
    ("全带幺", "", "B1 B2 B3 T7 T8 T9 W1x3 B9x3 T1x2", "T1", ""),
    ("不求人", "", _CHOW4, "W5", "tsumo"),
    ("双明杠", "mkong:J1;mkong:J2", "W1x3 W2x3 W9x2", "W9", ""),
    ("和绝张", "", _PONG4, "B5", "last_tile"),
    # ---------------- 2 分 ----------------
    ("箭刻", "", "J1x3 W1x3 W2x3 W3x3 W9x2", "W9", ""),
    ("圈风刻", "", "F1x3 T1x3 T2x3 T3x3 J1x2", "J1", ""),
    ("门风刻", "", "F3x3 T1x3 T2x3 T3x3 J1x2", "J1", "seat:西"),
    ("门前清", "", _CHOW4, "W5", ""),
    ("平和", "", _CHOW4, "W5", ""),
    ("四归一", "", "W1x4 W2 W3 T2 T3 T4 B5 B6 B7 B9x2", "B9", ""),
    ("双同刻", "", "W3x3 T3x3 B7x3 W9x3 B5x2", "B5", ""),
    ("双暗刻", "pong:B7;pong:W9", "W1x3 T2x3 B5x2", "B5", ""),
    ("暗杠", "akang:J1", "W1x3 W2x3 W9x3 B5x2", "B5", ""),
    ("断幺", "", "W2x3 W3x3 W4x3 W6x3 B5x2", "B5", ""),
    # ---------------- 1 分 ----------------
    ("一般高", "", "W1 W2 W3 W1 W2 W3 W5x3 W9x3 B5x2", "B5", ""),
    ("喜相逢", "", "W1 W2 W3 B1 B2 B3 W5x3 W9x3 B5x2", "B5", ""),
    ("连六", "", "W1 W2 W3 W4 W5 W6 W5x3 W9x3 B5x2", "B5", ""),
    ("老少副", "", "W1 W2 W3 W7 W8 W9 W5x3 B9x3 B5x2", "B5", ""),
    ("幺九刻", "", "F3x3 W2x3 W3x3 W4x3 B5x2", "B5", ""),
    ("明杠", "mkong:J1", "W1x3 W2x3 W9x3 B5x2", "B5", ""),
    ("缺一门", "", "W1 W2 W3 W4 W5 W6 W7 W8 W9 T9x3 T5x2", "T5", ""),
    ("无字", "", "W1 W2 W3 T4 T5 T6 B7 B8 B9 W5x3 T9x2", "T9", ""),
    ("边张", "", "W1 W2 W3 W4 W5 W6 W7 W8 W9 T2 T3 T4 B5x2", "W3", ""),
    ("坎张", "", "W4 W5 W6 W1x3 W9x3 T2 T3 T4 B5x2", "W5", ""),
    ("单钓将", "", "W1x3 W2x3 W3x3 W4x3 B5x2", "B5", ""),
    ("自摸", "pong:J1", "W1x3 W2x3 W9x3 B5x2", "B5", "tsumo"),
    ("花牌", "", _PONG4, "B5", "flowers:3"),
]

WIND_CN = {"东": 27, "南": 28, "西": 29, "北": 30}


def parse_tiles(spec: str):
    """'W1x3 T2 B5x2' → [tid, ...]"""
    out = []
    for tok in (spec or "").split():
        if "x" in tok:
            code, n = tok.split("x")
            out.extend([tile_of(code)] * int(n))
        else:
            out.append(tile_of(tok))
    return out


def parse_melds(spec: str):
    """'chi:B1;pong:J1;mkong:F1;akang:F2' → [Meld, ...]"""
    out = []
    for tok in (spec or "").split(";"):
        tok = tok.strip()
        if not tok:
            continue
        kind, code = tok.split(":")
        t = tile_of(code)
        if kind == "chi":
            out.append(Meld("chi", (t, t + 1, t + 2), False))
        elif kind == "pong":
            out.append(Meld("pong", (t, t, t), False))
        elif kind == "mkong":
            out.append(Meld("kong", (t, t, t, t), False))
        elif kind == "akang":
            out.append(Meld("kong", (t, t, t, t), True))
        else:
            raise ValueError("未知副露类型 %s" % kind)
    return out


def parse_opts(spec: str) -> dict:
    kw = {"round_wind": "东", "seat_wind": "东"}
    for tok in (spec or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok in ("tsumo", "last_tile", "rob_kong", "kong_bloom",
                   "last_draw", "last_discard"):
            kw[tok] = True
        elif tok.startswith("round:"):
            kw["round_wind"] = tok.split(":", 1)[1]
        elif tok.startswith("seat:"):
            kw["seat_wind"] = tok.split(":", 1)[1]
        elif tok.startswith("flowers:"):
            kw["flowers"] = int(tok.split(":", 1)[1])
        else:
            raise ValueError("未知选项 %s" % tok)
    return kw


def parse_entry(entry):
    """→ (fan, melds, concealed, win_tid, Options)"""
    fan, meld_s, tile_s, win_s, opt_s = entry
    melds = parse_melds(meld_s)
    concealed = parse_tiles(tile_s)
    win = tile_of(win_s) if win_s else concealed[-1]
    o = Options(**parse_opts(opt_s))
    return fan, melds, concealed, win, o
