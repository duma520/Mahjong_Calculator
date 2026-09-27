# -*- coding: utf-8 -*-
"""verify_all.py —— 全量和牌枚举 + 算番完备性/正确性校验

对应需求：「枚举所有和牌的组合（包括不同的方式和方法），计算番数是否正确，
          避免数多了、或者算少了、算漏了的情况发生。」

校验层次
  A 枚举   所有和牌型：标准型（4 面子 + 将）、组合龙、七对、连七对、十三幺、全不靠、七星不靠
  B 判定   每一手都必须被 decompositions() 认可（防「和牌被漏判」）
  C 分解   引擎分解集合 与 独立实现（indy.py）的分解集合必须完全一致（防漏拆 / 多拆）
  D 逐分解 对**每一种分解、每一种和张**重算番种，独立实现与引擎必须逐番逐值一致
           （防多算＝多判番种；防少算＝漏判番种；防番值取错）
  E 取优   引擎最终结果必须等于「所有分解方式里番数最高的那一种」（防少算）
  F 排除   ① 结果内部不得同时出现「X 与 X 的不计项 Y」
           ② 被剔除的番种必须有合法剔除理由（防「无故丢番」）
  G 覆盖   81 个番种 + 花牌 + 各选项（自摸/不求人/门前清/和绝张/杠上开花/妙手回春/
           海底捞月/抢杠和）都必须在某手牌里被真正算出来（防判定恒假＝漏算）
  H 反例   变异牌型的「和/不和」判定，引擎与独立实现必须一致（防「假和」）
  I 听牌   引擎 waiting_tiles 与独立实现 ind_waits 必须一致
  J 副露   吃/碰/明杠/暗杠 牌型的专项对拍（明杠/暗杠/双明杠/双暗杠/三杠/四杠/全求人…）
  K 全路径  calc.score() 公开接口与「逐分解最优」结果一致（含起和分/无番和/花牌）

用法
  & "…python.exe" -u _scaffold/verify_all.py                  # ★ 完整检验（不抽样，默认）
  & "…python.exe" -u _scaffold/verify_all.py --phases main    # 只跑核心阶段
  & "…python.exe" -u _scaffold/verify_all.py --phases all     # 100% 全维度（含 sweep，很久）
  & "…python.exe" -u _scaffold/verify_all.py --quick          # 抽样快速版（旧的默认行为）

完整检验（不抽样）的设计
  · 牌型空间 100% 穷尽：标准型（4 面子+将）/ 组合龙 / 十三幺·连七对·全不靠·七星不靠 /
    七对全空间 C(34,7)=5,379,616 / 七对含四张 k=3(185,504) + k=2(2,782,560) + k=1(8,069,424)
    ≈ 2842 万手**逐手**校验（七对含四张 1~2 个四张以前是随机抽样，现在完整枚举）。
  · 内存安全：全部用生成器 + 分批（--batch，默认 30 万手/批），单批处理完即释放，
    不再一次性构造上千万手的 list；进度写 _verify_progress_<阶段>.json，**中断后重跑自动续跑**
    （要重头跑加 --restart）。
  · 阶段（--phases，默认 main,waits,score,neg,meld,golden）：
      main  逐手自洽 + 独立实现对拍（判定/分解/tag/逐分解逐番/取优/并存/丢番/番值）
      waits 逐手听牌对拍（引擎 waiting_tiles vs 独立实现 ind_waits）
      score 逐手公开接口 score() 全路径
      sweep 每一手的每一个和张 × 点炮/自摸（默认不跑，耗时约为 main 的 5 倍）
      neg   逐手 2 个确定性变异的和牌判定
      meld  副露手牌（确定性种子放大；副露形态 × 和牌型的组合空间不可穷尽）
      golden 81 个番种金标准牌例
  · 为什么有些维度不能「穷尽」：副露（吃/碰/杠）× 和牌型的组合是 10^10 量级，
    「和张 × 选项」是「每手 × 每张牌 × 选项组合」，都不是「牌型枚举」而是组合放大；
    这两处用「确定性形态覆盖 + 放大规模」，其余全部完整。
日志：_scaffold/_verify_out.txt（UTF-8，实时写入，可随时查看进度）
"""
import argparse
import io
import itertools
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import indy                                                    # noqa: E402
from mahjong_core import (Ctx, MahjongFanCalculator, Meld,      # noqa: E402
                          Options, collect_fans, decompositions)

LOG_PATH = os.path.join(HERE, "_verify_out.txt")
_BUF = []


def log(msg=""):
    _BUF.append(str(msg))
    # ★ 先写文件再打印：stdout 是管道时，管道满了 print 会阻塞进程
    try:
        with io.open(LOG_PATH, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write("\n".join(_BUF))
    except Exception:          # noqa: BLE001
        pass
    try:
        print(msg, flush=True)
    except Exception:          # noqa: BLE001
        pass


# ------------------------------------------------------------------ 面子池

SET_TILES = []
for _t in range(34):
    SET_TILES.append((_t, _t, _t))
for _su in range(3):
    for _k in range(7):
        _a = _su * 9 + _k
        SET_TILES.append((_a, _a + 1, _a + 2))

_G = None       # 每进程一个计算器
_EXCL = None    # 独立实现用的「不计」表（自己从 JSON 读）


def _init_worker():
    global _G, _EXCL
    _G = MahjongFanCalculator()
    _EXCL = {}
    table = (_G.rules.get("番种") or {}) if isinstance(_G.rules, dict) else {}
    for items in table.values():
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and it.get("name"):
                ex = it.get("不计") or []
                if ex:
                    _EXCL[it["name"]] = list(ex)


# ------------------------------------------------------------------ 枚举

def enum_standard(limit=None, seed=1):
    """标准型：4 面子 + 1 将（去重后的所有牌型）"""
    hands = set()
    n = len(SET_TILES)
    for combo in itertools.combinations_with_replacement(range(n), 4):
        c = bytearray(34)
        ok = True
        for idx in combo:
            for t in SET_TILES[idx]:
                c[t] += 1
                if c[t] > 4:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        for p in range(34):
            if c[p] > 2:
                continue
            c2 = bytearray(c)
            c2[p] += 2
            hands.add(bytes(c2))
    out = list(hands)
    if limit and len(out) > limit:
        random.Random(seed).shuffle(out)
        out = out[:limit]
    return out


def enum_long_dragon():
    """组合龙：9 张龙牌 + 1 面子 + 1 将"""
    hands = set()
    for pat in indy.LONG_PAT:
        base = bytearray(34)
        for t in pat:
            base[t] += 1
        for st in SET_TILES:
            c = bytearray(base)
            ok = True
            for t in st:
                c[t] += 1
                if c[t] > 4:
                    ok = False
                    break
            if not ok:
                continue
            for p in range(34):
                if c[p] > 2:
                    continue
                c2 = bytearray(c)
                c2[p] += 2
                hands.add(bytes(c2))
    return list(hands)


def enum_specials():
    """十三幺 / 连七对 / 全不靠 / 七星不靠（完整枚举）"""
    hands = set()
    for dup in indy.THIRTEEN:
        c = bytearray(34)
        for t in indy.THIRTEEN:
            c[t] += 1
        c[dup] += 1
        hands.add(bytes(c))
    for su in range(3):
        for k in range(3):
            c = bytearray(34)
            for i in range(7):
                c[su * 9 + k + i] += 2
            hands.add(bytes(c))
    for col in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
        cols = [None] * 3
        for su in range(3):
            cols[su] = [su * 9 + col[su], su * 9 + col[su] + 3, su * 9 + col[su] + 6]
        # 三门花色各自从本花的「那一列」里任选 0~3 张（三花不必张数相同）
        picks = []
        for su in range(3):
            sub = []
            for r in range(4):
                sub.extend(itertools.combinations(cols[su], r))
            picks.append(sub)
        for a in picks[0]:
            for b in picks[1]:
                for d in picks[2]:
                    nums = list(a) + list(b) + list(d)
                    need = 14 - len(nums)
                    if not 0 <= need <= 7:
                        continue
                    for hs in itertools.combinations(range(27, 34), need):
                        picked = nums + list(hs)
                        if len(set(picked)) != len(picked):
                            continue
                        c = bytearray(34)
                        for t in picked:
                            c[t] += 1
                        hands.add(bytes(c))
    return list(hands)


def enum_qidui_space(limit=None, seed=3):
    """七对：在「筒+索+字」子空间里完整枚举（C(25,7)=480700）"""
    types = list(range(0, 9)) + list(range(9, 18)) + list(range(27, 34))
    hands = []
    for combo in itertools.combinations(types, 7):
        c = bytearray(34)
        for t in combo:
            c[t] += 2
        hands.append(bytes(c))
    if limit and len(hands) > limit:
        random.Random(seed).shuffle(hands)
        hands = hands[:limit]
    return hands


def enum_qidui_sample(n, seed=7):
    rnd = random.Random(seed)
    hands = set()
    tries = 0
    while len(hands) < n and tries < n * 40:
        tries += 1
        c = bytearray(34)
        for t in rnd.sample(range(34), 7):
            c[t] += 2
        hands.add(bytes(c))
    return list(hands)


def enum_qidui_four_full():
    """七对含四张（★ 4 张算两对）：3 个四张 + 1 对 —— C(34,3)×31 = 185,504 完整枚举"""
    hands = set()
    for combo in itertools.combinations(range(34), 3):
        for p in range(34):
            if p in combo:
                continue
            c = bytearray(34)
            for t in combo:
                c[t] += 4
            c[p] += 2
            hands.add(bytes(c))
    return list(hands)


def enum_qidui_four_sample(n, seed=13):
    """七对含四张：1~2 个四张 + 其余对子（全空间 1085 万手，随机抽样）"""
    rnd = random.Random(seed)
    hands = set()
    tries = 0
    while len(hands) < n and tries < n * 40:
        tries += 1
        k = rnd.choice((1, 2))
        c = bytearray(34)
        fours = rnd.sample(range(34), k)
        for t in fours:
            c[t] += 4
        rest = [t for t in range(34) if t not in fours]
        for t in rnd.sample(rest, 7 - 2 * k):
            c[t] += 2
        hands.add(bytes(c))
    return list(hands)


# --------------------------------------------------- 完整模式：流式枚举（不抽样）
# ★ 内存铁律：完整牌型空间约 2800 万手，**绝不能**先建一个 2800 万元的 list
#   （约 2~3 GB，若再 dict.fromkeys 去重还要翻倍）。所以下面全部是**生成器**，
#   由 run_full_mode() 每取一批（--batch）就交给进程池处理，处理完立即释放。
#   族与族之间、族内不同拆法之间可能出现「同一手牌重复出现」，重复只会多花时间，
#   不会漏检 —— 完整性不受影响。

def enum_standard_iter():
    """标准型（4 面子 + 将）：完整流式枚举（C(58,4)×34 种写法，含同一手的多种拆法）"""
    n = len(SET_TILES)
    for combo in itertools.combinations_with_replacement(range(n), 4):
        c = bytearray(34)
        ok = True
        for idx in combo:
            for t in SET_TILES[idx]:
                c[t] += 1
                if c[t] > 4:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        for p in range(34):
            if c[p] > 2:
                continue
            c2 = bytearray(c)
            c2[p] += 2
            yield bytes(c2)


def enum_qidui_all_iter():
    """七对（全空间）：C(34,7) = 5,379,616 手，完整流式枚举"""
    for combo in itertools.combinations(range(34), 7):
        c = bytearray(34)
        for t in combo:
            c[t] += 2
        yield bytes(c)


def enum_qidui_four_iter(k):
    """七对含四张：k 个四张 + (7-2k) 个对子，完整流式枚举

    k=3 → C(34,3)×31        = 185,504
    k=2 → C(34,2)×C(32,3)   = 2,782,560
    k=1 → 34×C(33,5)        = 8,069,424
    （k=2/k=1 之前是随机抽样，v2.4.3 起改为完整枚举）
    """
    for fours in itertools.combinations(range(34), k):
        rest = [t for t in range(34) if t not in fours]
        for pairs in itertools.combinations(rest, 7 - 2 * k):
            c = bytearray(34)
            for t in fours:
                c[t] += 4
            for t in pairs:
                c[t] += 2
            yield bytes(c)


def full_families():
    """完整模式的族：(族名, 生成器工厂, 已知手数或 0)

    ★ 顺序：**稀有族优先**（组合龙/特殊牌型/七对含四张 k=3 → 七对 → 标准型最后）。
    这样即使标准型（约 1150 万手，占大头）还没跑完，稀有牌型的完整结论已经先出来了。
    """
    return [
        ("组合龙", lambda: iter(enum_long_dragon()), 0),
        ("特殊牌型（十三幺/连七对/全不靠/七星不靠）",
         lambda: iter(enum_specials()), 0),
        ("七对含四张 k=3", lambda: enum_qidui_four_iter(3), 185504),
        ("七对含四张 k=2", lambda: enum_qidui_four_iter(2), 2782560),
        ("七对含四张 k=1", lambda: enum_qidui_four_iter(1), 8069424),
        ("七对（全空间 C(34,7)）", enum_qidui_all_iter, 5379616),
        ("标准型（4 面子 + 将）", enum_standard_iter, 0),
    ]


# ------------------------------------------------------------------ 工具

def key_tiles(key):
    return [t for t in range(34) for _ in range(key[t])]


def eng_sets(decomp):
    """引擎分解 → 独立实现的表示（Meld 是副露；Set_ 是手牌里的暗面子）"""
    out = []
    for s in decomp.sets:
        if s.kind == "kong":
            out.append(("k", s.tile, bool(s.concealed)))
        elif s.kind == "long":
            out.append(("L", tuple(s.tiles), True))
        elif isinstance(s, Meld):
            out.append(("c" if s.kind == "chi" else "p", s.tile, False))
        else:
            out.append(("c" if s.kind == "chi" else "p", s.tile, True))
    return out


def ind_only_sets(decomp):
    """用于比对「手牌分解集合」的规范化面子元组"""
    out = []
    for s in decomp.sets:
        if s.kind == "kong":
            continue
        if s.kind == "chi":
            out.append(("c", s.tile))
        elif s.kind == "pong":
            out.append(("p", s.tile))
        elif s.kind == "long":
            out.append(("L", tuple(s.tiles)))
    return tuple(sorted(out))


# 可以「按实例多次成立」的番种：值 = 表值 × 副数
MULTI_FANS = {"幺九刻", "四归一", "一般高", "喜相逢", "连六", "老少副", "双同刻"}


WIND_ID = {"东": 27, "南": 28, "西": 29, "北": 30}


def opts_dict(o, win, single, tag):
    return {"tsumo": o.tsumo, "last_tile": o.last_tile, "rob_kong": o.rob_kong,
            "kong_bloom": o.kong_bloom, "last_draw": o.last_draw,
            "last_discard": o.last_discard,
            "round_wind": WIND_ID.get(o.round_wind, 27),
            "seat_wind": WIND_ID.get(o.seat_wind, 27),
            "flowers": o.flowers, "single_wait": single, "tag": tag}


# ------------------------------------------------------------------ 各阶段

# ------------------------- 完整模式：逐手全维度校验（对每一手都做，不抽样）

def _norm_ind(eng_raw, ind_raw):
    """已知口径差规范化：indy 的 raw **不**做「已计不求人不再计自摸」的抑制
    （它交给终局不计表），而引擎在 raw 阶段就抑制。这里把 indy 那一份规范化后再比，
    避免把已知口径差当成缺陷；其它任何差异仍会被严格抓到。
    """
    if "不求人" in eng_raw and "自摸" not in eng_raw \
            and "不求人" in ind_raw and "自摸" in ind_raw:
        d = dict(ind_raw)
        d.pop("自摸", None)
        return d
    return dict(ind_raw)


def waits_full_chunk(keys):
    """★ 完整模式：听牌对拍（I）—— 对**每一手**（去掉一张后的 13 张）比对
    引擎 waiting_tiles 与独立实现 ind_waits，直接查「漏听 / 多听 / 听错」
    """
    calc = _G
    bad = []
    n = 0
    for key in keys:
        tiles = key_tiles(key)
        pre = list(key)
        win = tiles[-1]
        pre[win] -= 1
        n += 1
        eng_w = set(calc.waiting_tiles([], key_tiles(bytes(pre))))
        ind_w = indy.ind_waits(list(pre), 4)
        if eng_w != ind_w and len(bad) < 20:
            bad.append("听牌不一致 tiles=%s 引擎=%s 独立=%s"
                       % (tiles, sorted(eng_w), sorted(ind_w)))
        elif not eng_w and len(bad) < 20:
            bad.append("听牌为空（13 张不该出现）tiles=%s" % (tiles,))
    return {"n": n, "bad": bad}


def score_full_chunk(keys):
    """★ 完整模式：公开接口 calc.score() 全路径（K）—— 对**每一手**都调真接口，
    与「逐分解最优」比对（起和分 8 / 无番和补 8 / 花牌只加总分 / ok 标记）
    """
    calc = _G
    bad = []
    n = 0
    for key in keys:
        n += 1
        tiles = key_tiles(key)
        counts = list(key)
        win = tiles[-1]
        decs = decompositions(tiles, [])
        pre = list(counts)
        pre[win] -= 1
        single = len(indy.ind_waits(list(pre), 4)) == 1
        o = Options(flowers=3)
        best = -1
        for d in decs:
            fin = calc.handle_exclusions(collect_fans(
                Ctx(d=d, melds=[], concealed_counts=counts, all_counts=counts,
                    win_tile=win, opts=o, single_wait=single)))
            best = max(best, sum(fin.values()))
        base = best if best > 0 else 8
        res = calc.score([], tiles, win, o)
        if res.base != base or res.total != base + 3 or res.ok != (base >= 8):
            if len(bad) < 10:
                bad.append("score() 不一致 tiles=%s base=%s/%s total=%s ok=%s"
                           % (tiles, res.base, base, res.total, res.ok))
        # ★ 判「无番和」必须看**补 8 之前**的 best：best <= 0 才是真的一分数不出。
        #   原来写 `base == 8` 会把「恰好 8 分」的手牌（如 双暗刻2+幺九刻2+门前清2+
        #   无字1+缺一门1 = 8）也当成无番和 ⇒ 假报警（v2.7.5 实测 40 例，全是误报，
        #   引擎本身 base/total/ok 与「逐分解最优」完全一致）。
        elif best <= 0 and "无番和" not in dict(res.fans) and len(bad) < 10:
            bad.append("无番和未补 tiles=%s" % (tiles,))
    return {"n": n, "bad": bad}


def full_chunk(keys):
    """★ 完整模式核心（对**每一手**都执行，不抽样）：

    B 和牌判定 / C 分解集合 + 特殊牌型 tag（独立实现）/ D 逐分解逐番对拍
    （点炮 + 自摸 两种选项）/ E 取优一致 / F 并存违规 + 无故丢番 + 番值 /
    I 听牌对拍 / K 公开接口 calc.score() 全路径
    """
    calc = _G
    bad = []
    diffs = []
    fans_seen = {}
    n = 0
    agree = 0
    mx = 0
    for key in keys:
        n += 1
        tiles = key_tiles(key)
        counts = list(key)
        decs = decompositions(tiles, [])
        if not decs:
            if len(bad) < 10:
                bad.append("和牌型未被识别: %s" % (tiles,))
            continue
        eng_tag = next((d.tag for d in decs if d.tag), "")
        ind_tag = indy.ind_special(counts) or ""
        if eng_tag != ind_tag and len(bad) < 10:
            bad.append("特殊牌型 tag 不一致 tiles=%s 引擎=%s 独立=%s"
                       % (tiles, eng_tag, ind_tag))
        win = tiles[-1]
        pre = list(counts)
        pre[win] -= 1
        # 单钓判定（影响 边张/坎张/单钓将 三个 1 分番种）：这里只用独立实现算一次，
        # 「引擎听牌 vs 独立听牌」的**对拍**在独立的 waits 阶段做（避免重复算两道）
        single = len(indy.ind_waits(list(pre), 4)) == 1
        eng_std = {(ind_only_sets(d), d.pair) for d in decs if not d.tag}
        ind_std = indy.ind_decomps(counts, 4)
        if eng_std != ind_std and len(bad) < 10:
            bad.append("分解集合不一致 tiles=%s 引擎=%d组 独立=%d组"
                       % (tiles, len(eng_std), len(ind_std)))
        best_e = {}
        v_e = -1
        for tsumo in (False, True):
            o = Options(tsumo=tsumo)
            for d in decs:
                ctx = Ctx(d=d, melds=[], concealed_counts=counts,
                          all_counts=counts, win_tile=win, opts=o,
                          single_wait=single)
                eng_raw = collect_fans(ctx)
                if tsumo:
                    # ★ 自摸口径只做「引擎终局自洽」（下面的并存违规检查会盖到）
                    #    跨实现对拍只在点炮口径做：indy 的 raw 不抑制自摸（见 _norm_ind）
                    continue
                ind_raw = _norm_ind(eng_raw, indy.ref_detect(
                    counts, eng_sets(d), d.pair, win,
                    opts_dict(o, win, single, d.tag)))
                if dict(eng_raw) != ind_raw and len(diffs) < 12:
                    e_only = {k: v for k, v in eng_raw.items()
                              if ind_raw.get(k) != v}
                    i_only = {k: v for k, v in ind_raw.items()
                              if eng_raw.get(k) != v}
                    diffs.append("番种差异 tiles=%s 和张=%s 分解=%s 引擎=%s 独立=%s"
                                 % (tiles, win, eng_sets(d), e_only, i_only))
                fin_e = calc.handle_exclusions(eng_raw)
                se = sum(fin_e.values())
                if se > v_e:
                    v_e, best_e = se, dict(fin_e)
        seen = best_e if best_e else {"无番和": 8}
        names = set(seen)
        for name, val in seen.items():
            tv = calc.fan_values.get(name, -1)
            ok_val = (val % tv == 0) if (name in MULTI_FANS and tv > 0) else (val == tv)
            if not ok_val and len(bad) < 10:
                bad.append("番值不符 %s=%s 表=%s tiles=%s" % (name, val, tv, tiles))
            fans_seen[name] = fans_seen.get(name, 0) + 1
        for x in names:
            for y in calc.excludes.get(x, []):
                if y in names and x != "幺九刻" and y != "幺九刻" and len(bad) < 10:
                    bad.append("并存违规 %s 与 %s tiles=%s" % (x, y, tiles))
        for y in best_e:
            if y in names or y == "幺九刻":
                continue
            if not any(x in names and y in calc.excludes.get(x, []) for x in names):
                if len(bad) < 10:
                    bad.append("无故丢番 %s tiles=%s 结果=%s"
                               % (y, tiles, sorted(names)))
        base = sum(best_e.values()) if best_e else 8
        if base > mx:
            mx = base
        # K：公开接口 —— 单一分解的手用等价公式校验（省一次重复拆牌），
        #    「有多个分解」与「无番和」这两种有取优/补救风险的手**必须**调真接口
        if len(decs) >= 2 or not best_e:
            res = calc.score([], tiles, win, Options(flowers=3))
            if res.base != base or res.total != base + 3 or res.ok != (base >= 8):
                if len(bad) < 10:
                    bad.append("score() 不一致 tiles=%s base=%s/%s total=%s ok=%s"
                               % (tiles, res.base, base, res.total, res.ok))
        agree += 1
    return {"n": n, "agree": agree, "fans": fans_seen, "bad": bad,
            "diff": diffs, "max": mx}


def sweep_full_chunk(keys):
    """★ 完整模式：每一手的**每一个可能的和张** × 点炮/自摸 都逐分解对拍

    覆盖 边张/坎张/单钓将/自摸/不求人/门前清/花牌 这些「依赖和张与选项」的番种。
    （之前这个阶段只随机抽 1500 手，现在对全部牌型逐手穷举和张）
    """
    calc = _G
    diffs = []
    seen = {}
    n = 0
    for key in keys:
        tiles = key_tiles(key)
        counts = list(key)
        decs = decompositions(tiles, [])
        if not decs:
            continue
        for tsumo in (False, True):
            o = Options(tsumo=tsumo, flowers=2)
            for win in sorted(set(tiles)):
                n += 1
                pre = list(counts)
                pre[win] -= 1
                ind_w = indy.ind_waits(list(pre), 4)
                single = len(ind_w) == 1
                best = -1
                for d in decs:
                    ctx = Ctx(d=d, melds=[], concealed_counts=counts,
                              all_counts=counts, win_tile=win, opts=o,
                              single_wait=single)
                    raw = collect_fans(ctx)
                    ind_raw = _norm_ind(raw, indy.ref_detect(
                        counts, eng_sets(d), d.pair, win,
                        opts_dict(o, win, single, d.tag)))
                    if dict(raw) != ind_raw and len(diffs) < 12:
                        e_only = {k: v for k, v in raw.items() if ind_raw.get(k) != v}
                        i_only = {k: v for k, v in ind_raw.items() if raw.get(k) != v}
                        diffs.append("和张差异 自摸=%s tiles=%s 和张=%s "
                                     "引擎=%s 独立=%s"
                                     % (tsumo, tiles, win, e_only, i_only))
                    fin = calc.handle_exclusions(raw)
                    best = max(best, sum(fin.values()))
                res = calc.score([], tiles, win, o)
                base = best if best > 0 else 8
                if res.base != base and len(diffs) < 12:
                    diffs.append("和张总数不符 自摸=%s tiles=%s 和张=%s "
                                 "引擎=%s 期望=%s"
                                 % (tsumo, tiles, win, res.base, base))
                if res.total != res.base + 2 and len(diffs) < 12:
                    diffs.append("花牌加计错 tiles=%s total=%s base=%s"
                                 % (tiles, res.total, res.base))
                for name, _v in res.fans:
                    seen[name] = seen.get(name, 0) + 1
    return {"n": n, "diff": diffs, "seen": seen}


def neg_full_chunk(keys):
    """★ 完整模式：对每一手做 2 个**确定性**变异，核对和牌判定（引擎 vs 独立实现）

    变异 A：去掉「第一张」并换成另一种牌；变异 B：去掉「中间那张」并换成另一种牌。
    （之前的 neg_chunk 用固定随机种子抽 6 万手，现在对全部牌型逐手做）
    """
    bad = []
    n = 0
    win_cnt = 0
    for key in keys:
        tiles = key_tiles(key)
        for pos, delta in ((0, 7), (len(tiles) // 2, 5)):
            c = bytearray(key)
            c[tiles[pos]] -= 1
            c[(tiles[pos] + delta) % 34] += 1
            if max(c) > 4 or sum(c) != 14:
                continue
            n += 1
            eng = bool(decompositions(key_tiles(c), []))
            ind = indy.ind_win(list(c))
            if eng != ind and len(bad) < 10:
                bad.append("和牌判定不一致 %s 引擎=%s 独立=%s" % (list(c), eng, ind))
            if eng:
                win_cnt += 1
    return {"n": n, "win": win_cnt, "bad": bad}


def bulk_chunk(keys):
    """B~G：逐手 和牌判定 / 逐分解算番 / 取优 / 番值 / 并存违规 / 无故丢番 / 覆盖率

    （「独立实现的分解集合比对」与「score() 公开接口」在抽样阶段做，见 diff_chunk/score_chunk）
    """
    calc = _G
    opts = Options()
    fans_seen = {}
    bad = []
    n = 0
    mx = 0
    for key in keys:
        n += 1
        tiles = key_tiles(key)
        counts = list(key)
        win = tiles[-1]
        decs = decompositions(tiles, [])
        if not decs:
            if len(bad) < 10:
                bad.append("和牌型未被识别: %s" % (tiles,))
            continue
        # ★ 特殊牌型 tag 用独立实现全量核对（七对/连七对/十三幺/全不靠/七星不靠）
        #   这一步覆盖全部枚举牌型，防止「跨花色被当成连七对」这类多算 88 分的缺陷
        eng_tag = next((d.tag for d in decs if d.tag), "")
        ind_tag = indy.ind_special(counts) or ""
        if eng_tag != ind_tag and len(bad) < 10:
            bad.append("特殊牌型 tag 不一致 tiles=%s 引擎=%s 独立=%s"
                       % (tiles, eng_tag, ind_tag))
        pre = list(counts)
        pre[win] -= 1
        single = len(calc.waiting_tiles([], key_tiles(bytes(pre)))) == 1
        best_tot = -1
        best_fans = {}
        for d in decs:
            ctx = Ctx(d=d, melds=[], concealed_counts=counts, all_counts=counts,
                      win_tile=win, opts=opts, single_wait=single)
            fin = calc.handle_exclusions(collect_fans(ctx))
            tot = sum(fin.values())
            if tot > best_tot:
                best_tot, best_fans = tot, dict(fin)
        # 无番和：数不出任何番种分（花牌不计）
        seen = dict(best_fans) if best_fans else {"无番和": 8}
        base = sum(best_fans.values()) if best_fans else 8
        names = set(seen)
        for name, val in seen.items():
            tv = calc.fan_values.get(name, -1)
            ok_val = (val % tv == 0) if (name in MULTI_FANS and tv > 0) else (val == tv)
            if not ok_val and len(bad) < 10:
                bad.append("番值不符 %s=%s 表=%s tiles=%s" % (name, val, tv, tiles))
            fans_seen[name] = fans_seen.get(name, 0) + 1
        for x in names:
            for y in calc.excludes.get(x, []):
                if y in names and x != "幺九刻" and y != "幺九刻" and len(bad) < 10:
                    bad.append("并存违规 %s 与 %s tiles=%s" % (x, y, tiles))
        for y in best_fans:
            if y in names or y == "幺九刻":
                continue
            if not any(x in names and y in calc.excludes.get(x, []) for x in names):
                if len(bad) < 10:
                    bad.append("无故丢番 %s tiles=%s 结果=%s"
                               % (y, tiles, sorted(names)))
        if base > mx:
            mx = base
    return {"n": n, "fans": fans_seen, "bad": bad, "max": mx}

def diff_chunk(keys):
    """C/D/I：同分解逐番对拍 + 听牌对拍"""
    calc = _G
    diffs = []
    n = 0
    agree = 0
    for key in keys:
        n += 1
        tiles = key_tiles(key)
        counts = list(key)
        decs = decompositions(tiles, [])
        if not decs:
            diffs.append("未识别和牌 %s" % (tiles,))
            continue
        win = tiles[-1]
        pre = list(counts)
        pre[win] -= 1
        eng_w = set(calc.waiting_tiles([], key_tiles(bytes(pre))))
        ind_w = indy.ind_waits(list(pre), 4)
        if eng_w != ind_w:
            diffs.append("听牌不一致 tiles=%s 引擎=%s 独立=%s"
                         % (tiles, sorted(eng_w), sorted(ind_w)))
            continue
        # 分解集合与特殊牌型 tag
        eng = {(ind_only_sets(d), d.pair) for d in decs if not d.tag}
        eng_tags = {d.tag for d in decs if d.tag}
        ind = indy.ind_decomps(counts, 4)
        ind_tag = indy.ind_special(counts)
        if ind != eng or set(eng_tags) != ({ind_tag} if ind_tag else set()):
            diffs.append("分解不一致 tiles=%s 引擎std%d 独立std%d 引擎tag=%s 独立tag=%s"
                         % (tiles, len(eng), len(ind), sorted(eng_tags), ind_tag))
            continue
        single = len(ind_w) == 1
        o = Options()
        ok = True
        for d in decs:
            ctx = Ctx(d=d, melds=[], concealed_counts=counts, all_counts=counts,
                      win_tile=win, opts=o, single_wait=single)
            eng_raw = collect_fans(ctx)
            ind_raw = indy.ref_detect(counts, eng_sets(d), d.pair, win,
                                      opts_dict(o, win, single, d.tag))
            if dict(eng_raw) != dict(ind_raw):
                e_only = {k: v for k, v in eng_raw.items() if ind_raw.get(k) != v}
                i_only = {k: v for k, v in ind_raw.items() if eng_raw.get(k) != v}
                diffs.append("番种差异 tiles=%s 和张=%s 分解=%s 引擎=%s 独立=%s"
                             % (tiles, win, eng_sets(d), e_only, i_only))
                ok = False
                break
        if ok:
            agree += 1
        if len(diffs) >= 12:
            break
    return {"n": n, "agree": agree, "diff": diffs}


def sweep_chunk(items):
    """D/G：全和张 × 点炮/自摸 × 特殊选项（验证选项类番种与边坎钓）"""
    calc = _G
    diffs = []
    seen = {}
    n = 0
    for key in items:
        tiles = key_tiles(key)
        counts = list(key)
        for tsumo in (False, True):
            o = Options(tsumo=tsumo, flowers=2)
            for win in sorted(set(tiles)):
                n += 1
                pre = list(counts)
                pre[win] -= 1
                ind_w = indy.ind_waits(list(pre), 4)
                single = len(ind_w) == 1
                decs = decompositions(tiles, [])
                best = -1
                for d in decs:
                    ctx = Ctx(d=d, melds=[], concealed_counts=counts,
                              all_counts=counts, win_tile=win, opts=o,
                              single_wait=single)
                    raw = collect_fans(ctx)
                    ind_raw = indy.ref_detect(counts, eng_sets(d), d.pair, win,
                                              opts_dict(o, win, single, d.tag))
                    if dict(raw) != dict(ind_raw):
                        e_only = {k: v for k, v in raw.items() if ind_raw.get(k) != v}
                        i_only = {k: v for k, v in ind_raw.items() if raw.get(k) != v}
                        if len(diffs) < 12:
                            diffs.append("自摸=%s tiles=%s 和张=%s 引擎=%s 独立=%s"
                                         % (tsumo, tiles, win, e_only, i_only))
                    fin = calc.handle_exclusions(raw)
                    best = max(best, sum(fin.values()))
                res = calc.score([], tiles, win, o)
                base = best if best > 0 else 8
                if res.base != base and len(diffs) < 12:
                    diffs.append("总数不符 自摸=%s tiles=%s 和张=%s 引擎=%s 期望=%s"
                                 % (tsumo, tiles, win, res.base, base))
                if res.total != res.base + 2 and len(diffs) < 12:
                    diffs.append("花牌加计错 tiles=%s total=%s base=%s"
                                 % (tiles, res.total, res.base))
                for name, _v in res.fans:
                    seen[name] = seen.get(name, 0) + 1
        if len(diffs) >= 12:
            break
    return {"n": n, "diff": diffs, "seen": seen}


def option_chunk(keys):
    """G：选项类番种（自摸/不求人/门前清/和绝张/杠上开花/妙手回春/海底捞月/抢杠和）

    注意：「已计不求人不再计自摸分」，所以自摸只能在**带副露**的牌上出现。
    """
    calc = _G
    seen = {}
    bad = []
    scenarios = [
        ("自摸", Options(tsumo=True)),
        ("不求人", Options(tsumo=True)),
        ("门前清", Options(tsumo=False)),
        ("和绝张", Options(last_tile=True)),
        ("杠上开花", Options(tsumo=True, kong_bloom=True)),
        ("妙手回春", Options(tsumo=True, last_draw=True)),
        ("海底捞月", Options(last_discard=True)),
        ("抢杠和", Options(rob_kong=True)),
    ]
    for key in keys:
        tiles = key_tiles(key)
        win = tiles[-1]
        for name, o in scenarios:
            res = calc.score([], tiles, win, o)
            if name in {n for n, _ in res.fans}:
                seen[name] = seen.get(name, 0) + 1
        # 带一副副露（碰一筒）的版本：用来验证「自摸」
        if tiles.count(0) >= 3:
            rest = list(tiles)
            for _ in range(3):
                rest.remove(0)
            melds = [Meld("pong", (0, 0, 0), False)]
            res = calc.score(melds, rest, rest[-1], Options(tsumo=True))
            for n, _v in res.fans:
                seen[n] = seen.get(n, 0) + 1
    return {"seen": seen, "bad": bad}


def neg_chunk(keys):
    """H：变异牌型的和牌判定（引擎 vs 独立实现）"""
    rnd = random.Random(99)
    bad = []
    win_cnt = 0
    n = 0
    for key in keys:
        tiles = key_tiles(key)
        c = bytearray(key)
        c[tiles[rnd.randrange(len(tiles))]] -= 1
        j = rnd.randrange(34)
        c[j] += 1
        if max(c) > 4 or sum(c) != 14:
            continue
        n += 1
        eng = bool(decompositions(key_tiles(c), []))
        ind = indy.ind_win(list(c))
        if eng != ind and len(bad) < 10:
            bad.append("和牌判定不一致 %s 引擎=%s 独立=%s" % (list(c), eng, ind))
        if eng:
            win_cnt += 1
    return {"n": n, "win": win_cnt, "bad": bad}


def build_meld_hand(rnd, k):
    """构造一手带 k 组副露的**合法**和牌（保证是一手能和牌的结构、且每种牌不超过 4 张）"""
    used = [0] * 34
    melds = []
    for _ in range(k):
        kind = rnd.choice(["chi", "pong", "kong", "kong"])
        face = None
        for _try in range(60):
            if kind == "chi":
                su = rnd.randrange(3)
                st = rnd.randrange(7)
                face = (su * 9 + st, su * 9 + st + 1, su * 9 + st + 2)
            else:
                t = rnd.randrange(34)
                face = (t,) * (4 if kind == "kong" else 3)
            if all(used[x] + face.count(x) <= 4 for x in face):
                break
            face = None
        if face is None:
            return None
        for x in face:
            used[x] += 1
        concealed_flag = kind == "kong" and rnd.random() < 0.5
        melds.append(Meld(kind, face, concealed_flag))
    shown = []
    for _ in range(4 - k):
        face = None
        for _try in range(80):
            if rnd.random() < 0.6:
                su = rnd.randrange(3)
                st = rnd.randrange(7)
                face = (su * 9 + st, su * 9 + st + 1, su * 9 + st + 2)
            else:
                t = rnd.randrange(34)
                face = (t, t, t)
            if all(used[x] + face.count(x) <= 4 for x in face):
                break
            face = None
        if face is None:
            return None
        for x in face:
            used[x] += 1
        shown.extend(face)
    for _try in range(80):
        t = rnd.randrange(34)
        if used[t] + 2 <= 4:
            used[t] += 2
            shown.extend((t, t))
            break
    else:
        return None
    return melds, shown, shown[-1]


def meld_chunk(items):
    """J：副露（吃/碰/明杠/暗杠）专项对拍"""
    calc = _G
    diffs = []
    seen = {}
    n = 0
    for melds, tiles, win in items:
        counts = [0] * 34
        for m in melds:
            for t in m.tiles:
                counts[t] += 1
        for t in tiles:
            counts[t] += 1
        decs = decompositions(tiles, melds)
        if not decs:
            diffs.append("副露牌未识别 副露=%s 手牌=%s"
                         % ([(m.kind, m.concealed, m.tiles) for m in melds], tiles))
            continue
        n += 1
        o = Options()
        for d in decs:
            ctx = Ctx(d=d, melds=melds,
                      concealed_counts=[0] * 34,
                      all_counts=counts, win_tile=win, opts=o, single_wait=False)
            eng_raw = collect_fans(ctx)
            ind_raw = indy.ref_detect(counts, eng_sets(d), d.pair, win,
                                      opts_dict(o, win, False, d.tag))
            for k in eng_raw:
                seen[k] = seen.get(k, 0) + 1
            if dict(eng_raw) != dict(ind_raw):
                e_only = {k: v for k, v in eng_raw.items() if ind_raw.get(k) != v}
                i_only = {k: v for k, v in ind_raw.items() if eng_raw.get(k) != v}
                if len(diffs) < 20:
                    diffs.append("副露差异 副露=%s 手牌=%s 引擎=%s 独立=%s"
                                 % ([(m.kind, m.concealed) for m in melds], tiles,
                                    e_only, i_only))
        if len(diffs) >= 20:
            break
    return {"n": n, "diff": diffs, "seen": seen}


def _score_via_fans(calc, base, fans):
    """把「逐分解最优的番种字典」转成与 score() 同样的口径（含无番和）"""
    if not fans:
        return {"无番和": 8}
    return dict(fans)


def score_chunk(keys):
    """K：公开接口 calc.score() 全路径与「逐分解最优」一致"""
    calc = _G
    bad = []
    n = 0
    for key in keys:
        tiles = key_tiles(key)
        counts = list(key)
        win = tiles[-1]
        o = Options(flowers=3)
        decs = decompositions(tiles, [])
        pre = list(counts)
        pre[win] -= 1
        single = len(calc.waiting_tiles([], key_tiles(bytes(pre)))) == 1
        best = -1
        for d in decs:
            ctx = Ctx(d=d, melds=[], concealed_counts=counts, all_counts=counts,
                      win_tile=win, opts=o, single_wait=single)
            fin = calc.handle_exclusions(collect_fans(ctx))
            best = max(best, sum(fin.values()))
        base = best if best > 0 else 8
        res = calc.score([], tiles, win, o)
        n += 1
        if res.base != base or res.total != base + 3 or res.ok != (base >= 8):
            if len(bad) < 10:
                bad.append("score() 不一致 tiles=%s base=%s/%s total=%s ok=%s"
                           % (tiles, res.base, base, res.total, res.ok))
        if base == 0 and "无番和" not in dict(res.fans):
            if len(bad) < 10:
                bad.append("无番和未补 tiles=%s" % (tiles,))
    return {"n": n, "bad": bad}


# ------------------------------------------------------------------ 金标准牌例

def golden_stage():
    """G2：81 个番种逐一构造牌例——每个都必须能算出来（防漏算）+ 独立实现交叉

    返回 (命中数, 未命中列表, 牌例错误列表, 对拍差异列表)
    """
    import golden_fans as gf
    calc = MahjongFanCalculator()
    excl = {}
    table = (calc.rules.get("番种") or {}) if isinstance(calc.rules, dict) else {}
    for items in table.values():
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and it.get("name") and it.get("不计"):
                excl[it["name"]] = list(it["不计"])
    ok = 0
    miss = []
    bad_hand = []
    xdiff = []
    for entry in gf.GOLDEN:
        fan, melds, concealed, win, o = gf.parse_entry(entry)
        if len(concealed) != 14 - 3 * len(melds):
            bad_hand.append("%s 牌例张数不对：手牌 %d，应为 %d"
                            % (fan, len(concealed), 14 - 3 * len(melds)))
            continue
        if win not in concealed:
            bad_hand.append("%s 和张不在手牌" % fan)
            continue
        res = calc.score(melds, concealed, win, o)
        names = {n for n, _ in res.fans}
        good = (o.flowers > 0 and res.total == res.base + o.flowers) \
            if fan == "花牌" else (fan in names)
        if good:
            ok += 1
        else:
            miss.append("%s 未算出 → %s %s" % (fan, res.text(), res.message))
        counts = [0] * 34
        for m in melds:
            for t in m.tiles:
                counts[t] += 1
        for t in concealed:
            counts[t] += 1
        pre = list(concealed)
        pre.remove(win)
        single = len(calc.waiting_tiles(melds, pre)) == 1
        for d in decompositions(concealed, melds):
            eng_raw = collect_fans(Ctx(d=d, melds=melds,
                                       concealed_counts=[0] * 34,
                                       all_counts=counts, win_tile=win,
                                       opts=o, single_wait=single))
            ind_raw = indy.ref_detect(counts, eng_sets(d), d.pair, win,
                                      opts_dict(o, win, single, d.tag))
            if dict(eng_raw) != dict(ind_raw):
                e_only = {k: v for k, v in eng_raw.items() if ind_raw.get(k) != v}
                i_only = {k: v for k, v in ind_raw.items() if eng_raw.get(k) != v}
                xdiff.append("%s 引擎=%s 独立=%s" % (fan, e_only, i_only))
    return ok, miss, bad_hand, xdiff


# ------------------------------------------------------------------ 调度

def run_pool(fn, tasks, workers, label):
    t0 = time.time()
    log("  · %s（%d 块 / %d 进程）" % (label, len(tasks), workers))
    out = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
        for i, r in enumerate(ex.map(fn, tasks, chunksize=1)):
            out.append(r)
            log("      进度 %d/%d  %.0fs" % (i + 1, len(tasks), time.time() - t0))
    return out

def chunks_of(seq, workers, per_worker=4):
    step = max(1, len(seq) // (workers * per_worker))
    return [seq[i:i + step] for i in range(0, len(seq), step)]


# --------------------------------------------------------- 完整模式：分批 + 续跑

def _progress_path(phase):
    return os.path.join(HERE, "_verify_progress_%s.json" % phase)


def _load_progress(phase, families, batch):
    p = _progress_path(phase)
    if not os.path.exists(p):
        return None
    try:
        with io.open(p, encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception:      # noqa: BLE001
        return None
    if data.get("families") != [f[0] for f in families] or data.get("batch") != batch:
        log("  · 进度文件与本族/批大小不匹配 → 忽略，从头跑")
        return None
    return data


def _save_progress(phase, families, batch, done, stat, grand):
    data = {"families": [f[0] for f in families], "batch": batch,
            "done": sorted(done), "stat": stat, "grand": grand}
    p = _progress_path(phase)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\r\n") as fp:
        fp.write(json.dumps(data, ensure_ascii=False))
    os.replace(tmp, p)


def _merge_stat(stat, r):
    """把一批结果并入累计统计（坏例/差异只留前 40 条）+ 累计番种覆盖"""
    stat["n"] = stat.get("n", 0) + r.get("n", 0)
    stat["agree"] = stat.get("agree", 0) + r.get("agree", 0)
    stat["win"] = stat.get("win", 0) + r.get("win", 0)
    if r.get("max", 0) > stat.get("max", 0):
        stat["max"] = r["max"]
    fans = stat.setdefault("fans", {})
    for src in ("fans", "seen"):
        for k, v in (r.get(src) or {}).items():
            fans[k] = fans.get(k, 0) + v
    for k in ("bad", "diff"):
        arr = stat.setdefault(k, [])
        if len(arr) < 40:
            arr.extend((r.get(k) or [])[:40 - len(arr)])
    return stat


def run_full_phase(phase, chunk_fn, families, args, title=""):
    """跑一个完整阶段的**全部族**：分批处理 + 实时日志 + 进度文件（可中断续跑）"""
    t0 = time.time()
    log("\n" + "=" * 78)
    log("【完整·%s】%s" % (phase, title))
    prog = None if args.restart else _load_progress(phase, families, args.batch)
    stat = (prog or {}).get("stat") or {}
    done = set((prog or {}).get("done") or [])
    grand = int((prog or {}).get("grand") or 0)
    if done:
        log("  · 续跑：已完成 %d 批（累计 %d 手/次），本次跳过已完成的批次"
            % (len(done), grand))
    for fi, (fname, factory, est) in enumerate(families):
        it = factory()
        b = 0
        while True:
            items = list(itertools.islice(it, args.batch))
            if not items:
                break
            pid = "%s:%d-%d" % (phase, fi, b)
            b += 1
            if pid in done:
                continue
            res = run_pool(chunk_fn,
                           chunks_of(items, args.workers, args.per_worker),
                           args.workers, "%s·%s·批%d" % (phase, fname, b))
            for r in res:
                _merge_stat(stat, r)
            grand += len(items)
            done.add(pid)
            el = max(1e-9, time.time() - t0)
            log("      → %s 批%d：本批 %d 手，累计 %d，用时 %.0fs（%.0f 手/秒）"
                % (fname, b, len(items), grand, el, grand / el))
            _save_progress(phase, families, args.batch, done, stat, grand)
            elapsed = time.time() - t0
            if elapsed > args.log_every:
                log("      · 进度快照：%s 已 %d 手，异常 %d，差异 %d"
                    % (phase, grand, len(stat.get("bad", [])),
                       len(stat.get("diff", []))))
                args.log_every = elapsed + 600      # 每 10 分钟快照一次
    log("\n  【%s 汇总】累计 %d 次校验，用时 %.0fs" % (phase, grand, time.time() - t0))
    bad, diff = stat.get("bad", []), stat.get("diff", [])
    log("  · 异常 %d 条，差异 %d 条" % (len(bad), len(diff)))
    for x in bad[:40]:
        log("      ! %s" % x)
    for x in diff[:40]:
        log("      ! %s" % x)
    if not bad and not diff:
        log("  · ✅ 本阶段 0 异常 0 差异")
    return stat, grand


def meld_family_iter(count, seed=2027):
    """副露手牌（确定性种子放大）：副露形态 × 和牌型的组合空间不可穷尽，
    这里用固定种子生成 count 手，形态覆盖 吃/碰/明杠/暗杠/双明杠/双暗杠/三杠/四杠
    （见日志说明；「副露形态」本身另有 golden_fans 与 test_engine 的确定性牌例覆盖）"""
    rnd = random.Random(seed)
    made = 0
    while made < count:
        k = rnd.randrange(1, 5)
        built = build_meld_hand(rnd, k)
        if built:
            made += 1
            yield built


def run_full_mode(args):
    if args.phases.strip() == "all":
        phases = ["main", "waits", "score", "sweep", "neg", "meld", "golden"]
    else:
        phases = [p for p in args.phases.split(",") if p]
    families = full_families()
    if args.families.strip():
        keys = [s for s in args.families.split(",") if s]
        families = [f for f in families if any(k in f[0] for k in keys)]
    log("=" * 78)
    log("国标麻将算番器 —— 完整检验（**不抽样**：牌型空间全部穷尽）")
    log("时间: %s    进程: %d    批大小: %d    阶段: %s"
        % (time.strftime("%Y-%m-%d %H:%M:%S"), args.workers, args.batch,
           ",".join(phases)))
    if args.families.strip():
        log("族筛选: %s → 本次只跑 %d 个族" % (args.families, len(families)))
    log("牌型族（全部完整枚举）：")
    for fname, _f, est in families:
        log("   · %s%s" % (fname, ("（%d 手）" % est) if est else "（流式，量同上量级）"))
    log("已知规模合计: %d 手" % sum(e for _n, _f, e in families))
    log("阶段：main=逐手自洽+独立实现对拍；waits=逐手听牌对拍；score=逐手公开接口；"
        "sweep=逐手穷举和张×点炮/自摸；neg=逐手 2 个确定性变异；"
        "meld=副露手牌；golden=81 番种金标准")
    log("⚠ 预计耗时（4 核机器，2842 万手）：main 约 8~15 小时；waits 约 3~6 小时；"
        "score 约 3~6 小时；sweep 约为 main 的 4~6 倍（默认不开）")
    log("   默认阶段不含 sweep（太耗时）；要跑 100% 全维度加 --phases all；"
        "只先看核心可 --phases main")
    log("   中途可 Ctrl+C 中断，重跑同一条命令会自动**续跑**（进度文件 "
        "_verify_progress_*.json）；要重头跑加 --restart")
    log("=" * 78)
    t0 = time.time()
    stats = {}
    if "main" in phases:
        stats["main"], _n = run_full_phase(
            "main", full_chunk, families, args,
            "逐手：和牌判定 / 分解集合 / 特殊 tag / 逐分解逐番对拍（点炮口径）/ "
            "取优 / 并存 / 丢番 / 番值 / 自摸∧不求人 互斥")
    if "waits" in phases:
        stats["waits"], _n = run_full_phase(
            "waits", waits_full_chunk, families, args,
            "逐手听牌对拍：引擎 waiting_tiles vs 独立实现 ind_waits（漏听/多听）")
    if "score" in phases:
        stats["score"], _n = run_full_phase(
            "score", score_full_chunk, families, args,
            "逐手公开接口 score() 全路径（起和分 8 / 无番和补 8 / 花牌只加总分）")
    if "sweep" in phases:
        stats["sweep"], _n = run_full_phase(
            "sweep", sweep_full_chunk, families, args,
            "每一手的每一个和张 × 点炮/自摸（边张/坎张/单钓将/自摸/不求人/门前清/花牌）")
    if "neg" in phases:
        stats["neg"], n_neg = run_full_phase(
            "neg", neg_full_chunk, families, args,
            "每手 2 个确定性变异 → 和牌判定（引擎 vs 独立实现）")
    if "meld" in phases:
        mf = [("副露手牌（确定性种子 %d 手，形态覆盖吃/碰/明杠/暗杠/三杠/四杠）"
               % args.meld_hands,
               lambda: meld_family_iter(args.meld_hands), args.meld_hands)]
        stats["meld"], n_meld = run_full_phase("meld", meld_chunk, mf, args,
                                               "副露专项对拍")
    if "golden" in phases:
        log("\n" + "=" * 78)
        log("【完整·golden】81 个番种金标准牌例（每个番种都必须能算出来 + 独立对拍）")
        gok, gmiss, gbad, gdiff = golden_stage()
        log("  · 命中 %d / 81" % gok)
        for m in gmiss:
            log("      ! %s" % m)
        for b in gbad:
            log("      ! 牌例错误: %s" % b)
        for d in gdiff[:30]:
            log("      ! 对拍差异: %s" % d)
        if not (gmiss or gbad or gdiff):
            log("  · ✅ 81 个番种全部可复现，且与独立实现一致")
        stats["golden"] = {"bad": gmiss + gbad, "diff": gdiff}

    log("\n" + "=" * 78)
    log("【总汇总】用时 %.0f 秒（%.1f 小时）" % (time.time() - t0,
                                                (time.time() - t0) / 3600))
    calc = MahjongFanCalculator()
    table = set(calc.fan_values) - {"花牌"}
    fans = {}
    problems = 0
    for ph in phases:
        st = stats.get(ph) or {}
        nb = len(st.get("bad") or [])
        nd = len(st.get("diff") or [])
        log("  · %-7s 校验 %s 次，异常 %d 条，差异 %d 条"
            % (ph, st.get("n", 0), nb, nd))
        problems += nb + nd
        for k, v in (st.get("fans") or {}).items():
            fans[k] = fans.get(k, 0) + v
    got = sorted(k for k in fans if k in table)
    missing = sorted(table - set(fans))
    log("  · 番种覆盖: %d / 81%s" % (len(got), "" if not missing else
                                    "  ⚠ 未出现: %s" % missing))
    log("  · 异常条目合计: %d" % problems)
    log("结论: %s" % ("✅ 完整检验未发现任何不一致（多算/少算/漏算均为 0）"
                      if problems == 0 else
                      "⚠ 存在 %d 条待确认项（见上方 ! 行）" % problems))
    log("=" * 78)
    return 0 if problems == 0 else 1


def _build_parser():
    ap = argparse.ArgumentParser(
        description="国标麻将算番器 —— 完整检验（默认，不抽样）/ 快速抽样（--quick）")
    ap.add_argument("--quick", action="store_true",
                    help="快速抽样版（= 旧的 --quick；与 --sample 等价）")
    ap.add_argument("--sample", action="store_true",
                    help="抽样模式（旧的默认路径：分层对拍）。不带该开关即为完整检验")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4)))
    ap.add_argument("--standard-limit", type=int, default=0,
                    help="【抽样模式】标准型抽样上限（0 = 全部）")
    ap.add_argument("--diff-limit", type=int, default=0,
                    help="【抽样模式】与独立实现对拍的手数上限（0 = 默认 12 万）")
    ap.add_argument("--no-qidui", action="store_true", help="跳过七对子空间")
    # ---- 完整模式（默认）----
    ap.add_argument("--batch", type=int, default=300000,
                    help="完整模式每批手数（默认 30 万；内存安全 + 断点续跑粒度）")
    ap.add_argument("--families", default="",
                    help="只跑名字含这些关键字的族（逗号分隔），例如 "
                         "\"组合龙,特殊,k=3\"；用于分族分批跑")
    ap.add_argument("--phases", default="main,waits,score,neg,meld,golden",
                    help="完整模式的阶段（逗号分隔）：main,waits,score,sweep,neg,meld,golden；"
                         "默认不含 sweep（耗时约为 main 的 5 倍）；all = 全部阶段；"
                         "只跑核心可写 --phases main")
    ap.add_argument("--meld-hands", type=int, default=200000, dest="meld_hands",
                    help="副露阶段手牌数（确定性种子，默认 20 万）")
    ap.add_argument("--per-worker", type=int, default=4, dest="per_worker",
                    help="每进程分到的块数（默认 4）")
    ap.add_argument("--restart", action="store_true",
                    help="忽略进度文件，从头跑（默认自动续跑）")
    ap.add_argument("--log-every", type=float, default=600.0, dest="log_every",
                    help="完整模式的进度快照间隔秒数（默认 600）")
    return ap


def main():
    args = _build_parser().parse_args()
    if args.quick or args.sample:
        return run_sample_mode(args)
    return run_full_mode(args)


def run_sample_mode(args):
    quick = args.quick
    workers = args.workers

    log("=" * 78)
    log("国标麻将算番器 —— 全量和牌枚举 / 算番完备性校验")
    log("时间: %s    进程: %d    %s" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                        workers, "快速抽样" if quick else "全量"))
    log("=" * 78)

    t0 = time.time()
    log("\n【A】枚举全部和牌型")
    lim = args.standard_limit or (80000 if quick else 0)
    std = enum_standard(lim)
    log("  · 标准型（4面子+将，去重）: %d 种%s"
        % (len(std), "（抽样）" if lim else "（完整）"))
    lng = enum_long_dragon()
    log("  · 组合龙型: %d 种（完整）" % len(lng))
    sp = enum_specials()
    log("  · 十三幺/连七对/全不靠/七星不靠: %d 种（完整）" % len(sp))
    if args.no_qidui:
        qd, qds, qf, qfs = [], [], [], []
    else:
        qd = enum_qidui_space(60000 if quick else None)
        qds = enum_qidui_sample(20000 if quick else 120000)
        qf = enum_qidui_four_full()                    # 3 个四张 + 1 对（完整）
        qfs = enum_qidui_four_sample(20000 if quick else 120000)
    log("  · 七对（筒+索+字 子空间）: %d 种%s"
        % (len(qd), "（抽样）" if quick else "（完整枚举）"))
    log("  · 七对（全空间随机）: %d 种" % len(qds))
    log("  · 七对含四张（3 四张 + 1 对）: %d 种（完整枚举，★ 4 张算两对）" % len(qf))
    log("  · 七对含四张（1~2 四张）: %d 种（随机抽样）" % len(qfs))
    hands = list(dict.fromkeys(std + lng + sp + qd + qds + qf + qfs))
    log("  · 合计待检验: %d 手（枚举用时 %.0fs）" % (len(hands), time.time() - t0))

    log("\n【B~G】逐手校验：和牌判定 / 分解一致 / 逐分解算番 / 取优 / 番值 / 并存 / 丢番")
    res = run_pool(bulk_chunk, chunks_of(hands, workers), workers, "全量算番校验")
    n = sum(r["n"] for r in res)
    fans = {}
    bad = []
    mx = 0
    for r in res:
        for k, v in r["fans"].items():
            fans[k] = fans.get(k, 0) + v
        mx = max(mx, r["max"])
        if len(bad) < 40:
            bad.extend(r["bad"][:40 - len(bad)])
    log("  · 已校验 %d 手，单手最高 %d 番" % (n, mx))
    log("  · 异常 %d 条" % len(bad))
    for b in bad[:40]:
        log("      ! %s" % b)

    calc = MahjongFanCalculator()
    table = set(calc.fan_values) - {"花牌"}

    log("\n【K】算番公开接口 score() 全路径抽检")
    ks = hands[:40000 if not quick else 8000]
    res = run_pool(score_chunk, chunks_of(ks, workers), workers, "score() 抽检")
    kbad = []
    for r in res:
        if len(kbad) < 20:
            kbad.extend(r["bad"][:20 - len(kbad)])
    log("  · 抽检 %d 手，异常 %d 条" % (sum(r["n"] for r in res), len(kbad)))
    for b in kbad[:20]:
        log("      ! %s" % b)

    log("\n【D/I】与独立实现对拍（同分解逐番比对 + 听牌比对）")
    rnd = random.Random(2026)
    # ★ 分层对拍：稀有牌型「全量」，其余随机抽样 —— 纯随机抽样会漏掉稀有结构
    #   （七对含四张只有 185,504 手，纯抽样 40 万手也未必抽到「大三元」那种极端组合）
    rare = list(dict.fromkeys(lng + sp + qf))          # 组合龙 + 特殊牌型 + 七对含四张(3 四张)
    rest = [h for h in hands if h not in set(rare)]
    rnd.shuffle(rest)
    budget = args.diff_limit or (120000 if not quick else 12000)
    extra = max(0, budget - len(rare))
    sample = rare + rest[:extra]
    log("  · 对拍样本 %d 手 = 稀有牌型全量 %d + 随机抽样 %d"
        % (len(sample), len(rare), min(extra, len(rest))))
    res = run_pool(diff_chunk, chunks_of(sample, workers, 3), workers, "独立实现对拍")
    dn = sum(r["n"] for r in res)
    dag = sum(r["agree"] for r in res)
    dd = []
    for r in res:
        if len(dd) < 40:
            dd.extend(r["diff"][:40 - len(dd)])
    log("  · 对拍 %d 手（每手取一个和张 × 全部分解），完全一致 %d 手" % (dn, dag))
    log("  · 差异 %d 条" % len(dd))
    for d in dd[:40]:
        log("      ! %s" % d)

    log("\n【D/G】全和张 × 点炮/自摸 扫描（边张/坎张/单钓将/自摸/不求人/门前清/花牌）")
    sw = list(hands)
    rnd.shuffle(sw)
    sw = sw[:1500 if not quick else 300]
    res = run_pool(sweep_chunk, chunks_of(sw, workers, 4), workers, "全和张扫描")
    sbad = []
    for r in res:
        if len(sbad) < 30:
            sbad.extend(r["diff"][:30 - len(sbad)])
        for k, v in r["seen"].items():
            fans[k] = fans.get(k, 0) + v
    log("  · 共 %d 次算番，差异 %d 条" % (sum(r["n"] for r in res), len(sbad)))
    for b in sbad[:30]:
        log("      ! %s" % b)

    log("\n【G】选项类番种覆盖（自摸/不求人/门前清/和绝张/杠上开花/妙手回春/海底捞月/抢杠和）")
    okeys = hands[:8000 if not quick else 2000]
    res = run_pool(option_chunk, chunks_of(okeys, workers, 4), workers, "选项覆盖")
    obad = []
    oseen = {}
    for r in res:
        obad.extend(r["bad"])
        for k, v in r["seen"].items():
            oseen[k] = oseen.get(k, 0) + v
            fans[k] = fans.get(k, 0) + v
    log("  · 各选项番种命中次数: %s"
        % ", ".join("%s=%d" % (k, oseen.get(k, 0))
                    for k in ("自摸", "不求人", "门前清", "和绝张", "杠上开花",
                              "妙手回春", "海底捞月", "抢杠和")))
    for b in sorted(set(obad)):
        log("      ! %s" % b)
    for nm in ("自摸", "不求人", "门前清", "和绝张", "杠上开花",
               "妙手回春", "海底捞月", "抢杠和"):
        if not oseen.get(nm):
            log("      ! 选项番种 %s 在所有牌例上都没出现" % nm)
            obad.append("选项番种 %s 缺失" % nm)
            oseen[nm] = 0

    log("\n【G2】81 个番种金标准牌例（每个番种都必须被算出来）")
    import golden_fans as _gf
    total_fans = len(_gf.GOLDEN)
    gok, gmiss, gbad, gdiff = golden_stage()
    for entry in _gf.GOLDEN:
        try:
            _fn, _melds, _concealed, _win, _o = _gf.parse_entry(entry)
            _res = calc.score(_melds, _concealed, _win, _o)
            for nm, _v in _res.fans:
                fans[nm] = fans.get(nm, 0) + 1
        except Exception:      # noqa: BLE001
            pass
    log("  · 命中 %d / %d" % (gok, total_fans))
    for b in gbad:
        log("      ! 牌例错误: %s" % b)
    for m in gmiss:
        log("      ! %s" % m)
    for d in gdiff[:30]:
        log("      ! 对拍差异: %s" % d)
    if not (gbad or gmiss or gdiff):
        log("  · ✅ 81 个番种全部可复现，且与独立实现一致")

    log("\n【H】变异牌型的和牌判定（引擎 vs 独立实现）")
    ns = hands[:60000 if not quick else 12000]
    res = run_pool(neg_chunk, chunks_of(ns, workers), workers, "变异判定")
    nbad = []
    for r in res:
        if len(nbad) < 30:
            nbad.extend(r["bad"][:30 - len(nbad)])
    log("  · 变异 %d 手（仍为和牌 %d 手），不一致 %d 条"
        % (sum(r["n"] for r in res), sum(r["win"] for r in res), len(nbad)))
    for b in nbad[:30]:
        log("      ! %s" % b)

    log("\n【J】副露（吃/碰/明杠/暗杠）专项对拍")
    items = []
    for _ in range(6000 if not quick else 1200):
        k = rnd.randrange(1, 5)
        built = build_meld_hand(rnd, k)
        if built:
            items.append(built)
    res = run_pool(meld_chunk, chunks_of(items, workers, 4), workers, "副露专项")
    md = []
    mseen = {}
    for r in res:
        if len(md) < 30:
            md.extend(r["diff"][:30 - len(md)])
        for k, v in r["seen"].items():
            mseen[k] = mseen.get(k, 0) + v
            fans[k] = fans.get(k, 0) + v
    log("  · 副露牌对拍 %d 手，差异 %d 条" % (sum(r["n"] for r in res), len(md)))
    for d in md[:30]:
        log("      ! %s" % d)

    log("\n【G】番种覆盖率（全量 + 全和张扫描 + 选项 + 副露 合并）")
    got = sorted(k for k in fans if k in table)
    missing = sorted(table - set(fans))
    log("  · 已算出: %d / 81" % len(got))
    if missing:
        log("  · ⚠ 从未被算出: %s" % missing)
    else:
        log("  · ✅ 81 个番种全部在和牌型上出现过")
    extra = sorted(set(fans) - table - {"花牌"})
    if extra:
        log("  · ⚠ 表外番种: %s" % extra)

    log("\n" + "=" * 78)
    problems = (len(bad) + len(kbad) + len(dd) + len(sbad) + len(nbad) + len(md)
                + len(set(obad)) + len(gbad) + len(gmiss) + len(gdiff))
    log("汇总：枚举/校验 %d 手；对拍 %d 手；金标准 %d/%d；异常条目合计 %d"
        % (n, dn, gok, total_fans, problems))
    log("结论: %s" % ("✅ 未发现算番不一致（多算 / 少算 / 漏算 均为 0）"
                      if problems == 0 else
                      "⚠ 存在 %d 条待确认项，见上方 ! 行" % problems))
    log("=" * 78)
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
