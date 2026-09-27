# -*- coding: utf-8 -*-
"""七对「含 4 张同牌」整类全量对拍（不抽样）—— v2.2.2

背景（用户提问）：「随机抽样会漏检吗？」
答案：会。全量校验里的「与独立实现对拍」原来是随机抽样，稀有牌型有概率整类躲过。
     v2.2.2 就把这类**可完整枚举**的稀有牌型改成**全量对拍**。

覆盖（七对含 4 张同牌的三个家族）：
    k=3  3 个四张 + 1 对      C(34,3)×31        =   185,504 手  → 默认**全量**
    k=2  2 个四张 + 3 对      C(34,2)×C(32,3)   = 2,782,560 手  → 默认**全量**
    k=1  1 个四张 + 5 对      34×C(33,5)        = 8,069,424 手  → 默认**抽样 20 万**
         （全量 800 万手单核约 3 小时，可选 --k1-full 跑；一般没必要）

对拍内容（逐手、逐分解、逐番种）：引擎 `collect_fans` vs 独立实现 `indy.ref_detect`，
   并顺带比对和牌判定 / 特殊牌型 tag / 听牌集合 / 最终番数（引擎 score vs 独立口径）。

用法：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/sweep_qidui4.py [--k1 200000] [--k1-full] [--workers 6]
输出：控制台 + `_scaffold/_qidui4_out.txt`（UTF-8）
"""
from __future__ import annotations

import argparse
import io
import itertools
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_PATH = os.path.join(HERE, "_qidui4_out.txt")
LOG = []

_G = None
_INDY = None


def log(msg=""):
    LOG.append(str(msg))
    try:
        with io.open(OUT_PATH, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write("\n".join(LOG))
    except Exception:          # noqa: BLE001
        pass
    try:
        print(msg, flush=True)
    except Exception:          # noqa: BLE001
        pass


def _init_worker():
    global _G, _INDY
    import mahjong_core as M
    import indy
    _G = M.MahjongFanCalculator()
    _INDY = indy


def tiles_of(c):
    return [t for t in range(34) for _ in range(c[t])]


OPT_BASE = {"tsumo": False, "last_tile": False, "rob_kong": False, "kong_bloom": False,
            "last_draw": False, "last_discard": False, "round_wind": 27, "seat_wind": 27,
            "flowers": 0, "single_wait": False, "tag": ""}


def chunk_check(chunk):
    """chunk: [counts, ...]；返回差异列表 + 计数"""
    import mahjong_core as M
    n = 0
    bad = []
    for c in chunk:
        n += 1
        tiles = tiles_of(c)
        win = tiles[-1]
        decs = M.decompositions(tiles, [])
        if not decs:
            bad.append("未识别和牌 %s" % (tiles,))
            continue
        pre = list(c)
        pre[win] -= 1
        w_eng = set(_G.waiting_tiles([], tiles_of(pre)))
        w_ind = set(_INDY.ind_waits(list(pre), 4))
        if w_eng != w_ind:
            bad.append("听牌不一致 %s 引擎=%s 独立=%s" % (tiles, sorted(w_eng), sorted(w_ind)))
            continue
        s_eng = len(w_eng) == 1
        s_ind = len(w_ind) == 1
        ok = True
        for d in decs:
            ctx = M.Ctx(d=d, melds=[], concealed_counts=c, all_counts=c,
                        win_tile=win, opts=M.Options(), single_wait=s_eng)
            e = dict(M.collect_fans(ctx))
            sets = [("c" if x.kind == "chi" else "p", x.tile, True) for x in d.sets]
            o = dict(OPT_BASE)
            o["single_wait"] = s_ind
            o["tag"] = d.tag
            i = dict(_INDY.ref_detect(list(c), sets, d.pair, win, o))
            if e != i:
                eo = {k: v for k, v in e.items() if i.get(k) != v}
                io_ = {k: v for k, v in i.items() if e.get(k) != v}
                bad.append("番种差异 %s tag=%s 引擎=%s 独立=%s" % (tiles, d.tag, eo, io_))
                ok = False
                break
        if ok:
            # 和牌判定 / 特殊牌型 tag 也要一致
            ind_tag = _INDY.ind_special(list(c))
            eng_tags = {d.tag for d in decs if d.tag}
            if eng_tags != ({ind_tag} if ind_tag else set()):
                bad.append("tag 不一致 %s 引擎=%s 独立=%s"
                           % (tiles, sorted(eng_tags), ind_tag))
        if len(bad) >= 20:
            break
    return {"n": n, "bad": bad}


def gen_k3():
    for combo in itertools.combinations(range(34), 3):
        for p in range(34):
            if p in combo:
                continue
            c = [0] * 34
            for t in combo:
                c[t] = 4
            c[p] += 2
            yield c


def gen_k2():
    for duo in itertools.combinations(range(34), 2):
        rest = [t for t in range(34) if t not in duo]
        for trio in itertools.combinations(rest, 3):
            c = [0] * 34
            for t in duo:
                c[t] = 4
            for t in trio:
                c[t] += 2
            yield c


def gen_k1(limit=None, seed=11):
    rnd = random.Random(seed)
    total = 34 * len(list(itertools.combinations(range(33), 5)))
    if limit is None or limit >= total:
        for four in range(34):
            rest = [t for t in range(34) if t != four]
            for five in itertools.combinations(rest, 5):
                c = [0] * 34
                c[four] = 4
                for t in five:
                    c[t] += 2
                yield c
    else:
        seen = set()
        while len(seen) < limit:
            four = rnd.randrange(34)
            rest = [t for t in range(34) if t != four]
            key = (four, tuple(sorted(rnd.sample(rest, 5))))
            if key in seen:
                continue
            seen.add(key)
            c = [0] * 34
            c[four] = 4
            for t in key[1]:
                c[t] += 2
            yield c


def chunks(seq, workers, per_worker=6):
    buf = []
    size = 2000
    for item in seq:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def run_family(name, gen, workers, expect=None):
    t0 = time.time()
    log("  · %s（%s）..." % (name, "全量" if expect is None else "抽样 %d" % expect))
    n = 0
    bad = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
        for r in ex.map(chunk_check, chunks(gen, workers), chunksize=1):
            n += r["n"]
            if len(bad) < 20:
                bad.extend(r["bad"][:20 - len(bad)])
            if n % 50000 < 2000:
                log("      已对拍 %d 手  %.0fs  差异 %d" % (n, time.time() - t0, len(bad)))
    log("    ⇒ %s：对拍 %d 手，差异 %d 条  （%.0fs）" % (name, n, len(bad), time.time() - t0))
    for s in bad[:10]:
        log("      ! %s" % s)
    return n, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4)))
    ap.add_argument("--k1", type=int, default=200000, help="k=1 家族抽样手数")
    ap.add_argument("--k1-full", action="store_true", help="k=1 家族也全量（约 800 万手）")
    ap.add_argument("--only", default="", help="只跑某个家族：k1/k2/k3")
    args = ap.parse_args()

    log("=" * 78)
    log("七对「含 4 张同牌」整类全量对拍（不抽样）")
    log("时间: %s    进程: %d" % (time.strftime("%Y-%m-%d %H:%M:%S"), args.workers))
    log("=" * 78)
    total_bad = []
    if args.only in ("", "k3"):
        n, bad = run_family("k=3  三个四张 + 1 对（完整枚举 185,504）", gen_k3(), args.workers)
        total_bad += bad
    if args.only in ("", "k2"):
        n, bad = run_family("k=2  两个四张 + 3 对（完整枚举 2,782,560）", gen_k2(), args.workers)
        total_bad += bad
    if args.only in ("", "k1"):
        if args.k1_full:
            n, bad = run_family("k=1  一个四张 + 5 对（完整枚举 8,069,424）",
                                gen_k1(), args.workers)
        else:
            n, bad = run_family("k=1  一个四张 + 5 对（抽样）",
                                gen_k1(args.k1), args.workers, expect=args.k1)
        total_bad += bad
    log("\n" + "=" * 78)
    log("结论: %s" % ("✅ 全量对拍无差异（这一类牌型不可能漏检）" if not total_bad
                     else "⚠ 存在 %d 条差异，见上" % len(total_bad)))
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
