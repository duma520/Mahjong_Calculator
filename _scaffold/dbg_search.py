# -*- coding: utf-8 -*-
"""随机搜索：副露牌型下 引擎 / 独立实现 的差异（打印首个反例细节）"""
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import indy                                                     # noqa: E402
from mahjong_core import (Ctx, Meld, Options, collect_fans,      # noqa: E402
                          decompositions, name_of)

HAND_TYPES = {}


def build(rnd, k):
    used = [0] * 34
    melds = []
    for _ in range(k):
        kind = rnd.choice(["chi", "pong", "kong", "kong"])
        for _t in range(60):
            if kind == "chi":
                su = rnd.randrange(3)
                st = rnd.randrange(7)
                face = (su * 9 + st, su * 9 + st + 1, su * 9 + st + 2)
            else:
                t = rnd.randrange(34)
                face = (t,) * (4 if kind == "kong" else 3)
            if all(used[x] + 1 <= 4 for x in face):
                break
        else:
            return None
        for x in face:
            used[x] += 1
        melds.append(Meld(kind, face, kind == "kong" and rnd.random() < 0.5))
    shown = []
    for _ in range(4 - k):
        for _t in range(80):
            if rnd.random() < 0.6:
                su = rnd.randrange(3)
                st = rnd.randrange(7)
                face = (su * 9 + st, su * 9 + st + 1, su * 9 + st + 2)
            else:
                t = rnd.randrange(34)
                face = (t, t, t)
            if all(used[x] + 1 <= 4 for x in face):
                break
        else:
            return None
        for x in face:
            used[x] += 1
        shown.extend(face)
    for _t in range(80):
        t = rnd.randrange(34)
        if used[t] + 2 <= 4:
            used[t] += 2
            shown.extend((t, t))
            break
    else:
        return None
    return melds, shown, shown[-1]


def sets_of(d):
    out = []
    for s in d.sets:
        if s.kind == "kong":
            out.append(("k", s.tile, bool(s.concealed)))
        elif s.kind == "long":
            out.append(("L", tuple(s.tiles), True))
        elif isinstance(s, Meld):
            out.append(("c" if s.kind == "chi" else "p", s.tile, False))
        else:
            out.append(("c" if s.kind == "chi" else "p", s.tile, True))
    return out


def main():
    rnd = random.Random(12345)
    found = 0
    for n in range(20000):
        k = rnd.randrange(1, 5)
        built = build(rnd, k)
        if not built:
            continue
        melds, tiles, win = built
        counts = [0] * 34
        for m in melds:
            for t in m.tiles:
                counts[t] += 1
        for t in tiles:
            counts[t] += 1
        for d in decompositions(tiles, melds):
            ctx = Ctx(d=d, melds=melds, concealed_counts=[0] * 34,
                      all_counts=counts, win_tile=win, opts=Options(),
                      single_wait=False)
            eng = dict(collect_fans(ctx))
            ind = indy.ref_detect(counts, sets_of(d), d.pair, win, {
                "tsumo": False, "last_tile": False, "rob_kong": False,
                "kong_bloom": False, "last_draw": False, "last_discard": False,
                "round_wind": 27, "seat_wind": 27, "flowers": 0,
                "single_wait": False, "tag": d.tag})
            if dict(eng) != dict(ind):
                eo = {a: b for a, b in eng.items() if ind.get(a) != b}
                io = {a: b for a, b in ind.items() if eng.get(a) != b}
                print("-" * 70)
                print("副露:", [(m.kind, m.concealed, [name_of(t) for t in m.tiles])
                              for m in melds])
                print("手牌:", [name_of(t) for t in tiles],
                      "和张:", name_of(win))
                print("分解:", [(k2, name_of(t) if k2 != 'L' else t, c)
                              for k2, t, c in sets_of(d)], "将:",
                      name_of(d.pair) if d.pair >= 0 else "-")
                print("引擎独有:", eo, "独立独有:", io)
                found += 1
                if found >= 3:
                    return 0
    print("未发现差异")
    return 0


if __name__ == "__main__":
    sys.exit(main())
