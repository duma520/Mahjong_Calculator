# -*- coding: utf-8 -*-
"""侦察：和牌型总量 + 引擎速度（为全量校验定方案）"""
import itertools
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mahjong_core import MahjongFanCalculator, decompositions, tile_of  # noqa: E402


def all_sets():
    """全部面子：34 个刻子 + 21 个顺子"""
    out = []
    for t in range(34):
        out.append(("pong", t, (t, t, t)))
    for s in (0, 1, 2):
        for k in range(7):          # 起始数字 1..7
            a = s * 9 + k
            out.append(("chi", a, (a, a + 1, a + 2)))
    return out


def main():
    sets = all_sets()
    print("面子池: %d（刻子 34 + 顺子 21）" % len(sets))
    t0 = time.time()
    hands = set()
    combos = 0
    for combo in itertools.combinations_with_replacement(range(len(sets)), 4):
        combos += 1
        counts = {}
        ok = True
        for idx in combo:
            for t in sets[idx][2]:
                counts[t] = counts.get(t, 0) + 1
                if counts[t] > 4:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        for p in range(34):
            c2 = dict(counts)
            c2[p] = c2.get(p, 0) + 2
            if c2[p] > 4:
                continue
            hands.add(tuple(sorted(c2.items())))
    t1 = time.time()
    print("面子组合 %d 种，去重后和牌型 %d 种（%.1fs）" % (combos, len(hands), t1 - t0))

    # 验证全部能被 decompositions 认可
    bad = 0
    tiles_list = []
    for h in hands:
        tiles = []
        for t, n in h:
            tiles.extend([t] * n)
        tiles_list.append(tiles)
        if not decompositions(tiles, []):
            bad += 1
    print("其中 decompositions() 不认可的: %d" % bad)

    # 速度测试
    calc = MahjongFanCalculator()
    from mahjong_core import Options
    sample = tiles_list[:3000]
    t2 = time.time()
    for tiles in sample:
        calc.score([], tiles, tiles[-1], Options())
    t3 = time.time()
    per = (t3 - t2) / max(1, len(sample))
    print("score() 平均 %.3f ms/手" % (per * 1000))
    print("全量 %d 手预计 %.1f 分钟" % (len(hands), len(hands) * per / 60))


if __name__ == "__main__":
    main()
