# -*- coding: utf-8 -*-
"""调试：副露牌型的引擎/独立实现差异（针对三同刻 / 一色三节高）"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import indy                                                     # noqa: E402
from mahjong_core import (Ctx, MahjongFanCalculator, Meld, Options,  # noqa: E402
                          collect_fans, decompositions, code_of, name_of)

calc = MahjongFanCalculator()


def show(title, melds, tiles, win):
    counts = [0] * 34
    for m in melds:
        for t in m.tiles:
            counts[t] += 1
    for t in tiles:
        counts[t] += 1
    print("=" * 70)
    print(title)
    print("  副露:", [(m.kind, m.concealed, [name_of(t) for t in m.tiles])
                    for m in melds])
    print("  手牌:", [name_of(t) for t in tiles], " 和张:", name_of(win))
    for d in decompositions(tiles, melds):
        ctx = Ctx(d=d, melds=melds, concealed_counts=[0] * 34,
                  all_counts=counts, win_tile=win, opts=Options(), single_wait=False)
        eng = dict(collect_fans(ctx))
        isets = []
        for s in d.sets:
            if s.kind == "kong":
                isets.append(("k", s.tile, bool(s.concealed)))
            elif s.kind == "long":
                isets.append(("L", tuple(s.tiles), True))
            elif isinstance(s, Meld):
                isets.append(("c" if s.kind == "chi" else "p", s.tile, False))
            else:
                isets.append(("c" if s.kind == "chi" else "p", s.tile, True))
        ind = indy.ref_detect(counts, isets, d.pair, win, {
            "tsumo": False, "last_tile": False, "rob_kong": False,
            "kong_bloom": False, "last_draw": False, "last_discard": False,
            "round_wind": 27, "seat_wind": 27, "flowers": 0,
            "single_wait": False, "tag": d.tag})
        print("  分解:", isets, " 将:", name_of(d.pair) if d.pair >= 0 else "-")
        eo = {k: v for k, v in eng.items() if ind.get(k) != v}
        io = {k: v for k, v in ind.items() if eng.get(k) != v}
        print("    引擎独有:", eo, " 独立独有:", io)
        if not eo and not io:
            print("    ✅ 一致")


def main():
    # 三同刻：筒3 明杠 + 索3 碰 + 万3 碰 + 筒4 明杠 + 将 万8万8
    show("案例1 三同刻",
         [Meld("kong", (t, t, t, t), False) for t in (2,)],
         [], 0) if False else None
    t3, t3s, t3w, t4 = 2, 11, 20, 3
    show("案例1 三同刻（筒3杠 / 索3碰 / 万3碰 / 筒4杠 + 万8将）",
         [Meld("kong", (t3,) * 4, False), Meld("pong", (t3s,) * 3, False),
          Meld("pong", (t3w,) * 3, False), Meld("kong", (t4,) * 4, False)],
         [16, 16], 16)
    # 一色三节高：筒3、筒4、筒5 三个刻 + 筒6 明杠 + 索9将
    show("案例2 一色三节高（筒345碰/杠 + 索9将）",
         [Meld("pong", (2,) * 3, False), Meld("pong", (3,) * 3, False),
          Meld("pong", (4,) * 3, False), Meld("kong", (5,) * 4, True)],
         [17, 17], 17)


if __name__ == "__main__":
    main()
