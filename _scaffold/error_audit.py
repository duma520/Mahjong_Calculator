# -*- coding: utf-8 -*-
"""国标麻将算番器 —— 「所有可能发生的错误」全枚举 + 故障注入验证（v2.2.0）

用户要求：枚举**所有可能发生的错误**，验证会不会发生类似的错误，
         算番是否正确，避免算多了 / 算少了 / 算漏了。

本脚本做三件事：

一、**错误类别目录**（CATEGORIES）：把「算番器可能出错的地方」按出错机制穷举成 **25 类**
    （数量以 `len(CATEGORIES)` 为准），每类都给出：出错机制 / 规则依据 / 检测手段。
二、**检测器**（D1~D10）：互相独立、可复用的一组检查。关键设计：
    · 断言口径用**注入前快照**（PRISTINE）和**第二套独立实现**（indy.py），
      不用被检查对象自身的实现做断言，否则注入的缺陷会被自己「掩盖」。
    · 既检查**过程**（每个分解的番种、番值、并存、丢番），也检查**结果**
      （score() 的 base/total/ok/无番和、听牌集合）。
    · 还检查**数据**（番值表 / 不计表 与《规则》JSON 的一致性 + 必然并存表完整性）。
三、**故障注入**（INJECTIONS）：对每一类错误，往引擎里注入一个**真实缺陷**
    （其中 6 个就是本项目历史上真出现过的缺陷），再跑全部检测器：
    · 被检出 ⇒ 该类错误「不可能悄悄发生」（给出是哪个检测器抓到的 + 例证牌型）
    · 未被检出 ⇒ **校验盲区**，必须补检测（脚本以非零退出码报错）

用法：& "D:/Program Files/Python310/python.exe" -u _scaffold/error_audit.py
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mahjong_core as M                                     # noqa: E402
import indy                                                  # noqa: E402
from mahjong_core import (Meld, Options, Set_, Ctx,           # noqa: E402
                          decompositions, collect_fans, counts_of,
                          num_of, suit_of, is_suit, tile_of, code_of)

OUT_PATH = os.path.join(HERE, "_audit_out.txt")
LOG = []


def log(msg=""):
    LOG.append(str(msg))
    try:                       # ★ 先写文件再打印（stdout 是管道时 print 会阻塞）
        with io.open(OUT_PATH, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write("\n".join(LOG))
    except Exception:          # noqa: BLE001
        pass
    try:
        print(msg, flush=True)
    except Exception:          # noqa: BLE001
        pass


# ==================================================================== 快照 / 参照

RULES_PATH = os.path.join(ROOT, M.MahjongFanCalculator.RULES_FILE)


def new_calc():
    return M.MahjongFanCalculator(rules_path=RULES_PATH)


CALC = new_calc()

# ---- 注入前的「干净」实现快照：所有断言的参照物都从这里取，绝不用被注入的对象
PRISTINE = {
    "decompositions": M.decompositions,
    "waiting_tiles": M.MahjongFanCalculator.waiting_tiles,
    "score": M.MahjongFanCalculator.score,
    "handle_exclusions": M.MahjongFanCalculator.handle_exclusions,
    "load_rules": M.MahjongFanCalculator._load_rules,
    "collect_fans": M.collect_fans,
    "LONG_PATTERNS": list(M.LONG_PATTERNS),
    "EXTRA_EXCLUDES": {k: list(v) for k, v in M.EXTRA_EXCLUDES.items()},
    "EXCLUDE_KEEP": set(M.EXCLUDE_KEEP),
    "EXCLUDE_DROP": set(M.EXCLUDE_DROP),
    "is_bu_kao": M._is_bu_kao,
    "special_win_quick": M._special_win_quick,
}
FAN_FUNCS = {n: getattr(M, n) for n in dir(M)
             if (n.startswith("fan_") or n.startswith("_count_")) and callable(getattr(M, n))}

# ---- 规则数据（独立数据源：直接读 JSON，不经过引擎）
with io.open(RULES_PATH, encoding="utf-8") as _fp:
    RULES = json.load(_fp)


def _json_fan_values():
    out = {}
    for items in (RULES.get("番种") or {}).values():
        for it in items:
            if isinstance(it, dict) and it.get("name"):
                out[it["name"]] = int(it.get("fan") or 0)
    return out


def _json_excludes():
    out = {}
    for items in (RULES.get("番种") or {}).values():
        for it in items:
            if isinstance(it, dict) and it.get("name"):
                out[it["name"]] = list(it.get("不计") or [])
    return out


JSON_FAN = _json_fan_values()
JSON_EXCL = _json_excludes()

# 判定「不计」用的参照表 = 《规则》JSON 的「不计」 ∪ 注入前快照的《问答》补充项
ORACLE_EXCL = {}
for _src in (JSON_EXCL, PRISTINE["EXTRA_EXCLUDES"]):
    for _k, _v in _src.items():
        ORACLE_EXCL.setdefault(_k, [])
        ORACLE_EXCL[_k] = list(dict.fromkeys(ORACLE_EXCL[_k] + list(_v)))

WIND_ID = {"东": 27, "南": 28, "西": 29, "北": 30}


def opts_dict(o, single, tag):
    return {"tsumo": o.tsumo, "last_tile": o.last_tile, "rob_kong": o.rob_kong,
            "kong_bloom": o.kong_bloom, "last_draw": o.last_draw,
            "last_discard": o.last_discard,
            "round_wind": WIND_ID.get(o.round_wind, 27),
            "seat_wind": WIND_ID.get(o.seat_wind, 27),
            "flowers": o.flowers, "single_wait": single, "tag": tag}


def eng_full_rep(d):
    """引擎分解 → 独立实现的表示（Meld 是副露；Set_ 是暗面子）"""
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


def eng_norm_rep(d):
    """只反映「暗手部分」的分解（副露由两边共同拥有，不参与比对）"""
    out = []
    for s in d.sets:
        if isinstance(s, Meld) or s.kind == "kong":
            continue
        if s.kind in ("chi", "pong"):
            out.append(("c" if s.kind == "chi" else "p", s.tile))
        elif s.kind == "long":
            out.append(("L", tuple(s.tiles)))
    return tuple(sorted(out))


def ind_final2(fans, excl):
    """独立实现「不计」闭包 + 引擎口径的两条保护（幺九刻按实例、三杠另计双暗杠）"""
    out = dict(fans)
    changed = True
    while changed:
        changed = False
        for x in sorted(out, key=lambda n: -out[n]):
            if x not in out:
                continue
            for y in excl.get(x, ()):
                if y not in out or y in PRISTINE["EXCLUDE_KEEP"]:
                    continue
                if (x, y) in PRISTINE["EXCLUDE_DROP"]:
                    continue
                del out[y]
                changed = True
    return out


# ==================================================================== 手牌池

def H(melds=None, concealed=None, win=None, opts=None):
    if isinstance(win, (list, tuple)):
        win = win[0] if win else None
    return {"melds": list(melds or []), "concealed": list(concealed or []),
            "win": win, "opts": opts or Options()}


def T(*codes):
    return sorted(tile_of(c) for c in codes)


def M_(kind, codes, concealed=False):
    return Meld(kind, tuple(T(*codes)), concealed)


def rand_hand(rnd, meld_prob=0.0, kong_prob=0.0):
    """随机生成一手合法和牌（4 面子 + 将），可把若干面子变成副露/杠"""
    while True:
        cnt = [0] * 34
        packs = []
        ok = True
        for _ in range(4):
            pick = None
            for _try in range(80):
                if rnd.random() < 0.45:
                    s = rnd.randrange(3) * 9 + rnd.randrange(7)
                    need = (s, s + 1, s + 2)
                    kind = "chi"
                else:
                    t = rnd.randrange(34)
                    need = (t, t, t)
                    kind = "pong"
                want = list(need) + ([need[0]] if rnd.random() < kong_prob and kind == "pong" else [])
                if all(cnt[x] + want.count(x) <= 4 for x in set(want)):
                    pick = (kind, need, len(want) == 4)
                    break
            if pick is None:
                ok = False
                break
            kind, need, kong = pick
            for x in need:
                cnt[x] += 1
            if kong:
                cnt[need[0]] += 1
            packs.append((kind, need, kong))
        if not ok:
            continue
        cands = [t for t in range(34) if cnt[t] <= 2]
        if not cands:
            continue
        p = rnd.choice(cands)
        cnt[p] += 2
        melds, concealed = [], []
        for kind, need, kong in packs:
            if kong:
                melds.append(Meld("kong", tuple([need[0]] * 4), rnd.random() < 0.5))
            elif rnd.random() < meld_prob:
                melds.append(Meld(kind, tuple(need), False))
            else:
                concealed.extend(need)
        concealed.extend([p, p])
        return H(melds, concealed, concealed[-1], Options(tsumo=rnd.random() < 0.5))


OPTION_SETS = [
    dict(),
    dict(tsumo=True),
    dict(last_tile=True),
    dict(rob_kong=True),
    dict(kong_bloom=True),
    dict(last_draw=True),
    dict(last_discard=True),
    dict(tsumo=True, round_wind="南", seat_wind="西", flowers=2),
]


def build_pool(extra_hands=None, small=False):
    """★ 断言用牌池（大池：基线用；小池：每类注入用，只要「能抓到」的手牌够就行）

    组成：81 番种金标准 + 定向反例 + 随机和牌 + 选项组合 + 副露/杠 + 听牌用例
    """
    import golden_fans as gf
    pool = []
    for entry in gf.GOLDEN:
        fan, melds, concealed, win, o = gf.parse_entry(entry)
        pool.append(H(melds, concealed, win, o))
    rnd = random.Random(20260824)
    n_base = 60 if small else 140
    base = [rand_hand(rnd) for _ in range(n_base)]
    opt_sets = OPTION_SETS[1:4] if small else OPTION_SETS[1:]
    for k, h in enumerate(base):
        pool.append(h)
        for od in opt_sets:
            pool.append(H(h["melds"], h["concealed"], h["win"],
                          Options(**{**dict(tsumo=False, last_tile=False, rob_kong=False,
                                            kong_bloom=False, last_draw=False,
                                            last_discard=False, round_wind="东",
                                            seat_wind="东", flowers=0), **od})))
        if k % 5 == 0:
            pre = list(h["concealed"])
            pre.remove(h["win"])
            pool.append(H(h["melds"], pre, None))       # 听牌用例
    for _ in range(30 if small else 120):                # 副露 / 杠
        pool.append(rand_hand(rnd, meld_prob=0.75, kong_prob=0.25))
    for _ in range(15 if small else 40):                 # 纯随机 13 张（听牌反例）
        deck = [t for t in range(34) for _ in range(4)]
        rnd.shuffle(deck)
        pool.append(H([], sorted(deck[:13]), None))
    if extra_hands:
        pool.extend(extra_hands)
    return pool


# ==================================================================== 检测器

def det_rules_data():
    """D1：番值表 / 番种数 / 花牌分 / 不计表 与《规则》JSON 的一致性"""
    p = []
    calc = new_calc()
    if len(JSON_FAN) != 81:
        p.append("《规则》JSON 番种数 %d != 81" % len(JSON_FAN))
    for n, v in sorted(JSON_FAN.items()):
        if n not in calc.fan_values:
            p.append("引擎番值表缺番种 %s" % n)
        elif calc.fan_values[n] != v:
            p.append("番值不符 %s 引擎=%s 规则=%s" % (n, calc.fan_values[n], v))
    if calc.fan_values.get("花牌") != 1:
        p.append("花牌分值应为 1，实际 %s" % calc.fan_values.get("花牌"))
    if not calc.fan_table():
        p.append("fan_table() 为空（番表页会空白）")
    for n, exs in JSON_EXCL.items():
        for e in exs:
            if e not in calc.excludes.get(n, []):
                p.append("不计表缺失 %s 不计 %s" % (n, e))
    return p


def det_excl_consistency():
    """D1b：不计表 vs 参照表（多余项会少算 / 缺失项会多算）"""
    p = []
    calc = new_calc()
    for n in sorted(set(ORACLE_EXCL) | set(calc.excludes)):
        have = set(calc.excludes.get(n, []))
        want = set(ORACLE_EXCL.get(n, []))
        for y in sorted(want - have):
            p.append("不计表缺失：%s 应不计 %s（会多算）" % (n, y))
        for y in sorted(have - want):
            p.append("不计表多余：%s 多出了不计 %s（会少算）" % (n, y))
    return p


def det_golden():
    """D8：81 个番种金标准牌例 —— 每个都必须被算出来，且与独立实现一致"""
    import golden_fans as gf
    p = []
    for entry in gf.GOLDEN:
        fan, melds, concealed, win, o = gf.parse_entry(entry)
        if len(concealed) != 14 - 3 * len(melds) or win not in concealed:
            p.append("金标准牌例本身不合法：%s" % fan)
            continue
        res = CALC.score(melds, concealed, win, o)
        names = {n for n, _ in res.fans}
        if fan != "花牌" and fan not in names:
            p.append("金标准未算出 %s → %s" % (fan, res.text()))
    return p


def check_hand(h):
    """逐手检查：D2/D2b/D3/D4/D5/D6/D6b/D7/D9，返回 {检测器: [问题]}"""
    res = defaultdict(list)
    melds, concealed, win, o = h["melds"], h["concealed"], h["win"], h["opts"]
    need = 4 - len(melds)

    if h["win"] is not None and len(concealed) != 14 - 3 * len(melds):
        res["D9 结构不变量"].append("手牌张数错：%d（应 %d）" % (len(concealed), 14 - 3 * len(melds)))
    c_all = [0] * 34
    for t in concealed:
        c_all[t] += 1
    for m in melds:
        for t in m.tiles:
            c_all[t] += 1
    if any(v > 4 for v in c_all):
        res["D9 结构不变量"].append("某张牌超过 4 张：%s" % [i for i, v in enumerate(c_all) if v > 4])
    if win is None:
        w_eng = set(CALC.waiting_tiles(melds, concealed))
        w_ind = set(indy.ind_waits(counts_of(concealed), need))
        if w_eng != w_ind:
            res["D2b 听牌判定"].append("听牌不一致(13张) 手牌=%s 引擎=%s 独立=%s"
                                       % (sorted(concealed), sorted(w_eng), sorted(w_ind)))
        return res
    if win not in concealed:
        res["D9 结构不变量"].append("和张不在手牌：%s" % (sorted(concealed),))
        return res

    # ---------------- 分解 / 和牌判定
    decs = M.decompositions(concealed, melds)
    ind_can = bool(indy.ind_decomps(counts_of(concealed), need)) or \
        (need == 4 and indy.ind_special(c_all) is not None)
    if bool(decs) != ind_can:
        res["D2 和牌判定"].append("和牌判定不一致 %s 引擎=%s 独立=%s"
                                  % (sorted(concealed), bool(decs), ind_can))
    if not decs:
        return res

    # ---------------- D3 分解集合
    eng_norm = {(eng_norm_rep(d), d.pair) for d in decs if not d.tag}
    ind_norm = indy.ind_decomps(counts_of(concealed), need)
    if eng_norm != ind_norm:
        res["D3 分解集合"].append("分解集合不一致 手牌=%s 引擎%d 独立%d"
                                  % (sorted(concealed), len(eng_norm), len(ind_norm)))
    eng_tags = {d.tag for d in decs if d.tag}
    ind_tag = indy.ind_special(c_all) if need == 4 else None
    if eng_tags != ({ind_tag} if ind_tag else set()):
        res["D4 特殊牌型tag"].append("特殊牌型不一致 手牌=%s 引擎=%s 独立=%s"
                                     % (sorted(concealed), sorted(eng_tags), ind_tag))

    # ---------------- D9 结构不变量
    for d in decs:
        for s in d.sets:
            if s.kind == "chi":
                t = s.tile
                if not (is_suit(t) and num_of(t) <= 7 and s.tiles == (t, t + 1, t + 2)
                        and suit_of(t) == suit_of(t + 2)):
                    res["D9 结构不变量"].append("非法顺子 %s" % (s.tiles,))
            if s.kind in ("chi", "pong") and s.kind == "pong" and s.tiles != (s.tile,) * 3:
                res["D9 结构不变量"].append("非法刻子 %s" % (s.tiles,))
        if d.tag and melds:
            res["D9 结构不变量"].append("有副露却给出特殊牌型 %s" % d.tag)
        if d.tag and len(concealed) != 14:
            res["D9 结构不变量"].append("非 14 张却给出特殊牌型 %s" % d.tag)

    # ---------------- D2b 听牌
    pre = list(concealed)
    pre.remove(win)
    w_eng = set(CALC.waiting_tiles(melds, pre))
    w_ind = set(indy.ind_waits(counts_of(pre), need))
    if w_eng != w_ind:
        res["D2b 听牌判定"].append("听牌不一致 手牌=%s 引擎=%s 独立=%s"
                                   % (sorted(pre), sorted(w_eng), sorted(w_ind)))
    single_eng = len(w_eng) == 1
    single_ind = len(w_ind) == 1

    # ---------------- D5 逐分解番种对拍（同一分解，引擎 vs 独立）
    for d in decs:
        ctx = Ctx(d=d, melds=melds, concealed_counts=counts_of(concealed),
                  all_counts=c_all, win_tile=win, opts=o, single_wait=single_eng)
        eng_raw = M.collect_fans(ctx)
        ind_raw = indy.ref_detect(c_all, eng_full_rep(d), d.pair, win,
                                  opts_dict(o, single_ind, d.tag))
        if dict(eng_raw) != dict(ind_raw):
            e_only = {k: v for k, v in eng_raw.items() if ind_raw.get(k) != v}
            i_only = {k: v for k, v in ind_raw.items() if eng_raw.get(k) != v}
            res["D5 逐分解番种"].append(
                "番种差异 手牌=%s 张=%s 分解=%s 引擎=%s 独立=%s"
                % (sorted(concealed), code_of(win), eng_full_rep(d), e_only, i_only))

    # ---------------- D6 取优 / 口径（引擎内部一致性）
    best_in = -1
    for d in PRISTINE["decompositions"](concealed, melds):
        ctx = Ctx(d=d, melds=melds, concealed_counts=counts_of(concealed),
                  all_counts=c_all, win_tile=win, opts=o, single_wait=single_eng)
        fin = CALC.handle_exclusions(PRISTINE["collect_fans"](ctx))
        best_in = max(best_in, sum(fin.values()))
    base_in = best_in if best_in > 0 else 8
    sc = CALC.score(melds, concealed, win, o)
    flowers = max(0, int(o.flowers or 0))
    if sc.base != base_in:
        res["D6 取优"].append("未取最高分解 手牌=%s 引擎=%s 逐分解最高=%s"
                              % (sorted(concealed), sc.base, base_in))
    if sc.total != sc.base + flowers:
        res["D7 起和/花牌口径"].append("花牌未另计 手牌=%s base=%s total=%s 花=%s"
                                      % (sorted(concealed), sc.base, sc.total, flowers))
    if best_in == 0 and "无番和" not in dict(sc.fans):
        res["D7 起和/花牌口径"].append("无番和未补 手牌=%s" % (sorted(concealed),))
    if sc.ok != (sc.base >= 8):
        res["D7 起和/花牌口径"].append("起和判定错 手牌=%s base=%s ok=%s"
                                      % (sorted(concealed), sc.base, sc.ok))

    # ---------------- D6b 终局番数对拍（独立实现口径）
    best_ind = 0
    for d in PRISTINE["decompositions"](concealed, melds):
        raw = indy.ref_detect(c_all, eng_full_rep(d), d.pair, win,
                              opts_dict(o, single_ind, d.tag))
        best_ind = max(best_ind, sum(ind_final2(raw, ORACLE_EXCL).values()))
    base_ind = best_ind if best_ind > 0 else 8
    if sc.base != base_ind:
        res["D6b 终局番数(独立)"].append("终局番数不一致 手牌=%s 引擎=%s 独立=%s"
                                        % (sorted(concealed), sc.base, base_ind))
    return res


def run_detectors(pool, deep=True):
    global CALC
    CALC = new_calc()
    probs = defaultdict(list)
    for name, fn in (("D1 规则数据一致性", det_rules_data),
                     ("D1b 不计表 vs 参照表", det_excl_consistency),
                     ("D8 81 番种金标准", det_golden)):
        try:
            probs[name].extend(fn())
        except Exception as exc:                       # noqa: BLE001
            probs[name].append("检测器异常：%r" % (exc,))
    if deep:
        for h in pool:
            try:
                for k, v in check_hand(h).items():
                    probs[k].extend(v)
            except Exception as exc:                   # noqa: BLE001
                probs["!! 运行异常"].append("手牌=%s → %r" % (h["concealed"], exc))
    return probs


def det_api_boundary():
    """D10：对外接口的输入校验（张数 / 超过 4 张 / 和张不在手牌 / 花牌口径）"""
    p = []
    calc = new_calc()
    five = T("W1", "W1", "W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W9")
    if "4 张" not in calc.score([], five, five[0], Options()).message:
        p.append("超过 4 张未拦截：%s" % calc.score([], five, five[0], Options()).message)
    short = T("W1", "W2", "W3")
    if "不足" not in calc.score([], short, short[0], Options()).message:
        p.append("张数不足未提示")
    if "不等" in calc.score([], short, short[0], Options()).message:
        p.append("张数不足提示文案异常")
    # 合法 14 张（九莲宝灯），和张不在手牌
    nine = T("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
             "W9", "W9", "W9", "W1")
    if "和张不在手牌" not in calc.score([], nine, tile_of("T5"), Options()).message:
        p.append("和张不在手牌未提示")
    a = calc.score([], nine, nine[-1], Options(flowers=0))
    b = calc.score([], nine, nine[-1], Options(flowers=4))
    if not a.ok:
        p.append("九莲宝灯应达起和标准：base=%s msg=%s" % (a.base, a.message))
    if b.total != a.total + 4 or b.base != a.base:
        p.append("花牌口径错：base %s→%s total %s→%s"
                 % (a.base, b.base, a.total, b.total))
    if a.ok != (a.base >= 8):
        p.append("起和判定与 base 不一致")
    return p


# ==================================================================== 错误类别目录

CATEGORIES = [
    ("C01", "花色边界算术", "牌号跨花色连续编号（筒0-8/索9-17/万18-26），用「差几」做判断时漏判花色",
     "D4 特殊牌型tag / D3 分解集合", "E01 连七对只比较牌号差 6"),
    ("C02", "花色过滤缺失", "顺子/刻子/同顺类判定只比数字不比花色，跨花色也成立",
     "D2 和牌判定 / D3 / D5", "E02 顺子不查花色；E03 三色三同顺不查花色"),
    ("C03", "可选择性未穷举", "「三种花色各一副」这类条件用并集近似，选不出合法组合也算",
     "D5 逐分解番种", "E04 三色三节高用花色并集"),
    ("C04", "组合取法被截断", "多重花色/多种排列的合法取法只实现了一部分",
     "D2 / D3", "E05 组合龙只保留一种花色排列"),
    ("C05", "分解完备性", "分解递归的边界条件漏掉整类牌型（副露数、将牌、张数）",
     "D2 和牌判定 / D3", "E06 4 副露 + 将不可分（历史真缺陷）"),
    ("C06", "特殊牌型判定", "七对/连七对/十三幺/全不靠/七星不靠 的成立条件过宽或过严",
     "D4 / D3", "E23 全不靠不校验 147/258/369 列；E24 十三幺过宽；E29 七对必须允许 4 张同牌"),
    ("C06b", "杠与七对互斥", "已报明杠/暗杠的 4 张同牌不得再当两对（杠属副露，七对必须门前无副露）",
     "D9 结构不变量 / D3 / D4", "E27 带副露（含杠）时注入七对 tag"),
    ("C07", "听牌判定", "听牌集合算错 → 单听口径错 → 边张/坎张/单钓将 多算或少算",
     "D2b 听牌判定 / D5", "E18 听牌返回空；E19 快速判定丢七对"),
    ("C08", "快速判定与完整判定不一致", "waiting_tiles 用布尔快速算法，可能漏七对/组合龙/特殊牌型",
     "D2b / D5", "E19 快速判定丢七对"),
    ("C09", "取优（就高不就低）", "多个分解方式时不取最高番，或只算第一个分解",
     "D6 取优", "E11 只算第一个分解"),
    ("C10", "多重番种计数", "可多次成立的番种（四归一/一般高/喜相逢/连六/老少副/双同刻/幺九刻）只算一次",
     "D5 逐分解番种", "E12 计数上限压到 1"),
    ("C11", "番值表错", "分值表数字与《规则》不符、缺番种、多番种",
     "D1 规则数据一致性", "E09 清一色 24→12；E10 缺「推不倒」"),
    ("C12", "「不计」表错", "必然并存的番种该剔没剔（多算）或不剔却剔（少算）",
     "D1b 不计表 vs 参照表 / D6b", "E08a 丢「连七对不计清一色」；E08b 多一条不计"),
    ("C13", "幺九刻保护", "幺九刻被整项删除（应按实例扣除被覆盖的刻子）",
     "D6b 终局对拍", "E13 清空 EXCLUDE_KEEP"),
    ("C14", "必然并存反向保护", "《问答》要求另计的组合（三杠 + 双暗杠）被误删",
     "D6b 终局对拍", "E14 清空 EXCLUDE_DROP"),
    ("C15", "起和分口径", "起和 8 分判定错、花牌计入起和分",
     "D7 起和/花牌口径 / D10", "E15 ok 恒真；E16 花牌并进 base"),
    ("C16", "无番和兜底", "数不出番种时应记「无番和」8 分，兜底丢失会变成 0 分",
     "D7", "E17 去掉无番和兜底"),
    ("C17", "副露口径", "明刻/暗刻/杠/点炮补成的刻子 区分错 → 三暗刻/四暗刻/门前清类番种错",
     "D5 逐分解番种", "E20 明刻当暗刻"),
    ("C18", "杠的计分", "明杠1/暗杠2/双明杠4/一明一暗6/双暗杠6/三杠32/四杠88 及必然并存",
     "D5 / D8", "E21 双明杠判定失效"),
    ("C19", "风位/圈风", "圈风刻、门风刻 用错风位（东/南/西/北 与门风）",
     "D6b 终局对拍", "E22 门风恒按东算"),
    ("C20", "选项类番种", "自摸/和绝张/杠上开花/妙手回春/海底捞月/抢杠和 的触发与互斥",
     "D5 / D8", "E15（自摸类）由选项组合池覆盖"),
    ("C21", "结构不变量", "顺子同花色相连、刻子 3 张同牌、tag 只能无副露 14 张",
     "D9 结构不变量", "E26 注入跨花色顺子；E27 注入带副露的 tag"),
    ("C22", "输入校验", "张数不足 / 某张超过 4 张 / 和张不在手牌 未拦截",
     "D10 接口边界", "不可注入（定向用例直检）"),
    ("C23", "参照实现自身出错", "第二套实现对拍基准错了 ⇒ 对拍结论失效（必须验证对拍灵敏度）",
     "D5（对参照实现注入）", "E28 让参照实现凭空加「自摸」"),
    ("C24", "结果与过程不一致", "score() 的结果与「逐分解最优」不一致（口径分叉）",
     "D6 / D6b", "E11"),
    ("C25", "口径回归防护", "已裁定的口径被改回旧口径（如七对又变成「7 个不同对子」）",
     "D4 / D6b / 口径审计", "E29 七对退回旧口径"),
]


# ==================================================================== 故障注入

def _patch(**kw):
    """把 M / indy 上的属性换成缺陷版本，返回还原函数"""
    saved = {}
    for mod, name, value in kw["sets"]:
        saved[(id(mod), name)] = (mod, name, getattr(mod, name))
        setattr(mod, name, value)
    def restore():
        for mod, name, old in saved.values():
            setattr(mod, name, old)
    return restore


def HW(codes, melds=None, opts=None):
    """完整一手和牌（14-3m 张，和张取最后一张）"""
    tiles = sorted(tile_of(c) for c in codes)
    return H(melds, tiles, tiles[-1], opts)


def _extra_lian_qi_cross():
    return [HW(["B6", "B6", "B7", "B7", "B8", "B8", "B9", "B9",
                "T1", "T1", "T2", "T2", "T3", "T3"]),
            HW(["T7", "T7", "T8", "T8", "T9", "T9", "W1", "W1",
                "W2", "W2", "W3", "W3", "W4", "W4"])]


def _extra_cross_suit_chi():
    return [HW(["B9", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8",
                "W1", "W2", "W3", "W5", "W5"])]


def _extra_san_se_3tong_shun():
    return [HW(["B1", "B2", "B3", "B1", "B2", "B3", "W1", "W2", "W3",
                "T4", "T5", "T6", "W5", "W5"])]


def _extra_san_se_3jie_gao():
    return [HW(["B1", "B1", "B1", "B2", "B2", "B2", "T3", "T3", "T3",
                "W3", "W3", "W3", "W5", "W5"])]


def _extra_long_dragon():
    """组合龙手牌：9 张龙牌 + 1 个顺子 + 将（花色排列取列表最后一个）"""
    pat = list(PRISTINE["LONG_PATTERNS"][-1])
    free = [t for t in range(34) if t not in pat]
    s = None
    for cand in range(0, 27):
        if cand % 9 <= 6 and cand + 1 in free and cand + 2 in free:
            s = cand
            break
    pair = next(t for t in free if t not in (s, s + 1, s + 2))
    tiles = sorted(pat + [s, s + 1, s + 2, pair, pair])
    return [H([], tiles, tiles[-1])]


def _extra_4melds():
    melds = [Meld("pong", tuple(T("W1", "W1", "W1")), False),
             Meld("pong", tuple(T("W2", "W2", "W2")), False),
             Meld("chi", tuple(T("T3", "T4", "T5")), False),
             Meld("kong", tuple(T("B7",) * 4), False)]
    return [H(melds, T("W9", "W9"), T("W9"))]


def _extra_lian_qi():
    return [HW(["B3", "B3", "B4", "B4", "B5", "B5", "B6", "B6",
                "B7", "B7", "B8", "B8", "B9", "B9"])]


def _extra_multi_fans():
    """同时含 2 个喜相逢 + 2 个一般高（多重番种计数用）"""
    return [HW(["B1", "B2", "B3", "B1", "B2", "B3",
                "T1", "T2", "T3", "T1", "T2", "T3", "W5", "W5"])]


def _extra_ping_he_xi_xiang():
    """平和 + 喜相逢（校验「不计」表多一条时能否发现）"""
    return [HW(["B1", "B2", "B3", "T1", "T2", "T3",
                "B4", "B5", "B6", "T7", "T8", "T9", "W5", "W5"])]


def _extra_bu_kao_bad_column():
    # 14 张互不相同、字牌合法，但数牌「列」错位（1 与 8 同列）⇒ 不是全不靠
    return [HW(["B1", "B4", "B8", "T2", "T5", "T8",
                "W3", "W6", "W9", "F1", "F2", "F3", "F4", "J1"])]


def _extra_shisan_yao_near():
    return [HW(["W1", "W9", "T1", "T9", "B1", "B9", "F1", "F2", "F3",
                "F4", "J1", "J2", "T5", "T5"])]


def _extra_long_dragon_wrong_rest():
    """含组合龙 9 张，但余下 5 张不是「1 面子 + 将」（不是和牌）"""
    pat = list(PRISTINE["LONG_PATTERNS"][0])
    free = [t for t in range(34) if t not in pat]
    bad = [t for t in free if t % 9 in (0, 3, 8)][:3]          # 不成顺/不成刻
    pair = next(t for t in free if t not in bad)
    return [HW(["%s" % code_of(t) for t in sorted(pat + bad + [pair, pair])])]


def _extra_qidui_wait():
    # 听七对：6 对 + 1 单张
    return [H([], T("B2", "B2", "B3", "B3", "B4", "B4", "B5", "B5",
                    "B6", "B6", "T7", "T7", "J1"),
               None)]


def _extra_qidui_four():
    """七对含 4 张同牌（国标口径：4 张算两对）"""
    return [HW(["W1", "W1", "W1", "W1", "W2", "W2", "W3", "W3",
                "W4", "W4", "W5", "W5", "W6", "W6"]),
            HW(["W1", "W1", "W1", "W1", "W2", "W2", "W2", "W2",
                "W3", "W3", "W4", "W4", "W5", "W5"]),
            HW(["F1", "F1", "F1", "F1", "F2", "F2", "F3", "F3",
                "F4", "F4", "J1", "J1", "J2", "J2"])]


def _extra_men_feng():
    return [HW(["F3", "F3", "F3", "B1", "B2", "B3", "B4", "B5", "B6",
                "T7", "T8", "T9", "B9", "B9"], opts=Options(seat_wind="西"))]


def _extra_kong_hands():
    """杠：一明一暗 / 明杠+碰 / 三杠（2 暗 1 明，用于验证「三杠 + 双暗杠」必然并存）"""
    return [H([Meld("kong", tuple(T("B7",) * 4), False),
               Meld("pong", tuple(T("W3", "W3", "W3")), False)],
              T("T1", "T2", "T3", "T6", "T7", "T8", "W5", "W5"), T("W5")),
            H([Meld("kong", tuple(T("B7",) * 4), False),
               Meld("kong", tuple(T("W3",) * 4), True)],
              T("T1", "T2", "T3", "T6", "T7", "T8", "W5", "W5"), T("W5")),
            H([Meld("kong", tuple(T("B7",) * 4), True),
               Meld("kong", tuple(T("W3",) * 4), True),
               Meld("kong", tuple(T("T5",) * 4), False)],
              T("T1", "T2", "T3", "W9", "W9"), T("W9"))]


def _extra_meld_ankou():
    return [H([Meld("pong", tuple(T("W1", "W1", "W1")), False)],
              T("B2", "B2", "B2", "T3", "T3", "T3", "W5", "W5", "W5",
                "B9", "B9"), T("B9"))]


def _extra_kong_pair_hands():
    """★ 4 张已报杠（副露）时不得再当两对用于七对"""
    return [H([Meld("kong", tuple(T("W1",) * 4), True)],          # 暗杠
              T("W2", "W2", "W3", "W3", "W4", "W4", "W5", "W5",
                "W6", "W6", "W7"), T("W7")),
            H([Meld("kong", tuple(T("W1",) * 4), False)],          # 明杠
              T("W2", "W2", "W3", "W3", "W4", "W4", "W5", "W5",
                "W6", "W6", "W7"), T("W7")),
            H([Meld("kong", tuple(T("W1",) * 4), True),
               Meld("chi", tuple(T("T7", "T8", "T9")), False)],
              T("B1", "B2", "B3", "B4", "B5", "B6", "B9", "B9"), T("B9"))]


def _make_injections():
    """每个注入 = 一个「真实可能发生的缺陷」，注入后必须被检测器抓到"""
    inj = []

    # ---- E01 连七对：只比较牌号差 6（花色边界）—— 历史真缺陷
    def e01():
        orig = M.decompositions
        def bug(concealed, melds):
            out = orig(concealed, melds)
            c = counts_of(concealed)
            kinds = [i for i in range(34) if c[i] == 2]
            if len(kinds) == 7 and kinds[-1] - kinds[0] == 6:
                for d in out:
                    if d.tag == "七对":
                        d.tag, d.lian_qi = "连七对", True
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E01", "C01", "连七对只比较牌号差 6（跨花色误判 88 分）", e01,
                _extra_lian_qi_cross()))

    # ---- E02 顺子跨花色（不查花色）
    def e02():
        def bug_walk(c, out, need):
            if need == 0:
                if sum(c) == 0:
                    out.append(([], -1))
                return
            def walk(c2, start, sets, n):
                if n == 0:
                    if sum(c2) == 0:
                        out.append((list(sets), -1))
                    return
                i = start
                while i < 34 and c2[i] == 0:
                    i += 1
                if i >= 34:
                    return
                if c2[i] >= 3:
                    c2[i] -= 3
                    sets.append(Set_("pong", (i, i, i), True))
                    walk(c2, i, sets, n - 1)
                    sets.pop()
                    c2[i] += 3
                if i + 2 < 34 and c2[i + 1] and c2[i + 2]:      # ← 缺陷：不查花色
                    c2[i] -= 1
                    c2[i + 1] -= 1
                    c2[i + 2] -= 1
                    sets.append(Set_("chi", (i, i + 1, i + 2), True))
                    walk(c2, i, sets, n - 1)
                    sets.pop()
                    c2[i] += 1
                    c2[i + 1] += 1
                    c2[i + 2] += 1
            walk(list(c), 0, [], need)
        def bug_split(c, need):
            if need == 0:
                return not any(c)
            i = 0
            while i < 34 and not c[i]:
                i += 1
            if i >= 34:
                return False
            if c[i] >= 3:
                c[i] -= 3
                ok = bug_split(c, need - 1)
                c[i] += 3
                if ok:
                    return True
            if i + 2 < 34 and c[i + 1] and c[i + 2]:
                c[i] -= 1
                c[i + 1] -= 1
                c[i + 2] -= 1
                ok = bug_split(c, need - 1)
                c[i] += 1
                c[i + 1] += 1
                c[i + 2] += 1
                if ok:
                    return True
            return False
        return _patch(sets=[(M, "walk_collect", bug_walk), (M, "_split_ok", bug_split)])
    inj.append(("E02", "C02", "顺子不查花色（跨花色也成顺）", e02,
                _extra_cross_suit_chi()))

    # ---- E03 三色三同顺不查花色 —— 历史真缺陷
    def e03():
        def bug(ctx):
            for n in range(1, 8):
                if sum(1 for s in ctx.sets if s.kind == "chi"
                       and num_of(s.tile) == n) >= 3:
                    return True
            return False
        return _patch(sets=[(M, "fan_san_se_san_tong_shun", bug)])
    inj.append(("E03", "C02", "三色三同顺只数同数字顺子，不查花色", e03,
                _extra_san_se_3tong_shun()))

    # ---- E04 三色三节高用「花色并集 ≥ 3」 —— 历史真缺陷
    def e04():
        def bug(ctx):
            per = ctx.triplet_nums()
            for start in range(1, 8):
                if not all(start + k in per for k in range(3)):
                    continue
                suits = set()
                for k in range(3):
                    suits |= set(per[start + k])
                if len(suits) >= 3:
                    return True
            return False
        return _patch(sets=[(M, "fan_san_se_san_jie_gao", bug)])
    inj.append(("E04", "C03", "三色三节高用花色并集代替可选择性", e04,
                _extra_san_se_3jie_gao()))

    # ---- E05 组合龙只保留一种花色排列
    def e05():
        return _patch(sets=[(M, "LONG_PATTERNS", list(PRISTINE["LONG_PATTERNS"][:1]))])
    inj.append(("E05", "C04", "组合龙只实现一种花色排列", e05,
                _extra_long_dragon()))

    # ---- E06 4 副露牌型不可分 —— 历史真缺陷
    def e06():
        orig = M.decompositions
        def bug(concealed, melds):
            if 4 - len(melds) == 0:
                return []
            return orig(concealed, melds)
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E06", "C05", "4 副露 + 将（need==0）不可分解", e06, _extra_4melds()))

    # ---- E08a 不计表丢项（连七对不计清一色/七对）
    def e08a():
        tbl = {k: list(v) for k, v in M.EXTRA_EXCLUDES.items()}
        tbl.pop("连七对", None)
        return _patch(sets=[(M, "EXTRA_EXCLUDES", tbl)])
    inj.append(("E08a", "C12", "不计表丢「连七对不计七对/清一色」", e08a, _extra_lian_qi()))

    # ---- E08b 不计表多一条（清一色 不计 喜相逢）
    def e08b():
        tbl = {k: list(v) for k, v in M.EXTRA_EXCLUDES.items()}
        tbl["平和"] = list(tbl.get("平和", [])) + ["喜相逢"]
        return _patch(sets=[(M, "EXTRA_EXCLUDES", tbl)])
    inj.append(("E08b", "C12", "不计表多出「平和不计喜相逢」（少算）", e08b,
                _extra_ping_he_xi_xiang()))

    # ---- E09 番值被改（清一色 24 → 12）
    def e09():
        orig = PRISTINE["load_rules"]
        def bug(self):
            orig(self)
            self.fan_values["清一色"] = 12
        return _patch(sets=[(M.MahjongFanCalculator, "_load_rules", bug)])
    inj.append(("E09", "C11", "番值表被改（清一色 24→12）", e09, _extra_ping_he_xi_xiang()))

    # ---- E10 番值表缺番种
    def e10():
        orig = PRISTINE["load_rules"]
        def bug(self):
            orig(self)
            self.fan_values.pop("推不倒", None)
        return _patch(sets=[(M.MahjongFanCalculator, "_load_rules", bug)])
    inj.append(("E10", "C11", "番值表缺「推不倒」", e10, []))

    # ---- E11 取优失效：score() 只看第一个分解
    def e11():
        orig = PRISTINE["score"]
        def bug(self, melds, concealed, win=None, opts=None):
            decs = PRISTINE["decompositions"](list(concealed), list(melds))
            if len(decs) > 1:
                keep = M.decompositions
                M.decompositions = lambda c, m: decs[:1]
                try:
                    return orig(self, melds, concealed, win, opts)
                finally:
                    M.decompositions = keep
            return orig(self, melds, concealed, win, opts)
        return _patch(sets=[(M.MahjongFanCalculator, "score", bug)])
    inj.append(("E11", "C09", "不取最高分解，只算第一个分解", e11,
                _extra_san_se_3jie_gao() + _extra_san_se_3tong_shun()))

    # ---- E12 多重番种只算 1 次
    def e12():
        sets_ = []
        for name in ("_count_yi_ban_gao", "_count_xi_xiang_feng", "_count_lian_liu",
                     "_count_lao_shao_fu", "_count_shuang_tong_ke", "_count_si_gui_yi"):
            orig = getattr(M, name)
            sets_.append((M, name, (lambda o: (lambda ctx: 1 if o(ctx) else 0))(orig)))
        return _patch(sets=sets_)
    inj.append(("E12", "C10", "多重番种计数被压到 1（四归一/一般高/连六…）", e12,
                _extra_multi_fans()))

    # ---- E13 幺九刻保护丢失
    def e13():
        return _patch(sets=[(M, "EXCLUDE_KEEP", set())])
    inj.append(("E13", "C13", "EXCLUDE_KEEP 丢失（幺九刻被整项删除）", e13,
                [HW(["B1", "B1", "B1", "B9", "B9", "B9", "F1", "F1", "F1",
                     "T9", "T9", "T9", "W5", "W5"])]))

    # ---- E14 EXCLUDE_DROP 丢失（三杠 + 双暗杠）
    def e14():
        return _patch(sets=[(M, "EXCLUDE_DROP", set())])
    inj.append(("E14", "C14", "EXCLUDE_DROP 丢失（三杠不同时计双暗杠）", e14, _extra_kong_hands()))

    # ---- E15 起和判定失效（ok 恒真）
    def e15():
        orig = PRISTINE["score"]
        def bug(self, melds, concealed, win=None, opts=None):
            r = orig(self, melds, concealed, win, opts)
            r.ok = True
            return r
        return _patch(sets=[(M.MahjongFanCalculator, "score", bug)])
    inj.append(("E15", "C15", "起和判定恒真（不足 8 分也报和）", e15, []))

    # ---- E16 花牌并进起和分
    def e16():
        orig = PRISTINE["score"]
        def bug(self, melds, concealed, win=None, opts=None):
            r = orig(self, melds, concealed, win, opts)
            r.base += max(0, int((opts.flowers if opts else 0) or 0))
            return r
        return _patch(sets=[(M.MahjongFanCalculator, "score", bug)])
    inj.append(("E16", "C15", "花牌计入起和分", e16, []))

    # ---- E17 无番和兜底丢失
    def e17():
        orig = PRISTINE["score"]
        def bug(self, melds, concealed, win=None, opts=None):
            r = orig(self, melds, concealed, win, opts)
            rest = [f for f in r.fans if f[0] != "无番和"]
            if not rest:                      # 只靠「无番和」兜底才算得出分 → 去掉
                r.fans, r.base, r.total = [], 0, 0
            return r
        return _patch(sets=[(M.MahjongFanCalculator, "score", bug)])
    inj.append(("E17", "C16", "去掉「无番和」兜底", e17, []))

    # ---- E18 听牌判定失效
    def e18():
        return _patch(sets=[(M.MahjongFanCalculator, "waiting_tiles",
                             lambda self, melds, concealed: [])])
    inj.append(("E18", "C07", "听牌判定返回空（边/坎/钓 全失）", e18,
                [H([], T("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                        "W7", "W8", "W9", "W9", "W9"), None),
                 H([], T("B7", "B8", "B9", "T2", "T3", "T4", "W5", "W6", "W7",
                         "B4", "B5", "B6", "T9"), None)]))

    # ---- E19 快速和牌判定丢七对
    def e19():
        return _patch(sets=[(M, "_special_win_quick", lambda c: False)])
    inj.append(("E19", "C08", "快速听牌判定丢七对/特殊牌型", e19, _extra_qidui_wait()))

    # ---- E20 副露口径：明刻当暗刻
    def e20():
        orig = M.decompositions
        def bug(concealed, melds):
            out = orig(concealed, melds)
            for d in out:
                for s in d.sets:
                    if getattr(s, "kind", "") in ("pong", "kong"):
                        object.__setattr__(s, "concealed", True)   # Meld/Set_ 是 frozen
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E20", "C17", "明刻被当成暗刻（三暗刻/四暗刻多算）", e20, _extra_meld_ankou()))

    # ---- E21 双明杠判定失效
    def e21():
        return _patch(sets=[(M, "fan_shuang_ming_gang", lambda ctx: False)])
    inj.append(("E21", "C18", "双明杠判定失效（一明一暗少算）", e21, _extra_kong_hands()))

    # ---- E22 门风恒按东算
    def e22():
        import dataclasses
        orig = PRISTINE["score"]
        def bug(self, melds, concealed, win=None, opts=None):
            o2 = dataclasses.replace(opts, seat_wind="东") if opts else None
            return orig(self, melds, concealed, win, o2)
        return _patch(sets=[(M.MahjongFanCalculator, "score", bug)])
    inj.append(("E22", "C19", "门风刻恒按东风算", e22, _extra_men_feng()))

    # ---- E23 全不靠不校验 147/258/369 列
    def e23():
        def bug(counts):
            used = [i for i in range(34) if counts[i]]
            if len(used) != 14 or any(counts[i] != 1 for i in used):
                return False
            return all(i < 27 or i >= 27 for i in used)
        return _patch(sets=[(M, "_is_bu_kao", bug)])
    inj.append(("E23", "C06", "全不靠不校验花色列（148 组合也算）", e23,
                _extra_bu_kao_bad_column()))

    # ---- E24 十三幺过宽（只要集齐 12 种）
    def e24():
        orig = M.decompositions
        need13 = [0, 8, 9, 17, 18, 26] + list(M.HONOR_IDS)
        def bug(concealed, melds):
            out = orig(concealed, melds)
            c = counts_of(concealed)
            if sum(c) == 14 and sum(1 for t in need13 if c[t] >= 1) >= 12:
                if not any(d.tag == "十三幺" for d in out):
                    out.append(M.Decomp(sets=[], pair=-1, tag="十三幺"))
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E24", "C06", "十三幺过宽（集齐 12 种即算）", e24, _extra_shisan_yao_near()))

    # ---- E25 组合龙忽略余牌合法性
    def e25():
        orig = M.decompositions
        def bug(concealed, melds):
            out = orig(concealed, melds)
            c = counts_of(concealed)
            if sum(c) == 14:
                for pat in PRISTINE["LONG_PATTERNS"]:
                    if all(c[t] >= 1 for t in pat) and not any(
                            d.long_dragon for d in out):
                        out.append(M.Decomp(sets=[], pair=-1, long_dragon=True))
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E25", "C06", "组合龙忽略余牌是否成面子（过宽）", e25,
                _extra_long_dragon_wrong_rest()))

    # ---- E26 结构不变量：注入跨花色顺子
    def e26():
        orig = M.decompositions
        def bug(concealed, melds):
            out = orig(concealed, melds)
            for d in out:
                if d.sets and not d.tag:
                    d.sets = list(d.sets) + [Set_("chi", (8, 9, 10), True)]
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E26", "C21", "分解里出现跨花色「顺子」（8,9,10）", e26, []))

    # ---- E27 有副露却给出特殊牌型 tag
    def e27():
        orig = M.decompositions
        def bug(concealed, melds):
            out = orig(concealed, melds)
            if melds:
                out.append(M.Decomp(sets=[], pair=-1, tag="七对"))
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E27", "C21", "有副露（含杠）却给出「七对」tag", e27,
                _extra_4melds() + _extra_kong_pair_hands()))

    # ---- E28 参照实现本身出错（验证对拍灵敏度）
    def e28():
        orig = indy.ref_detect
        def bug(c, sets, pair, win, opts):
            out = dict(orig(c, sets, pair, win, opts))
            out["自摸"] = 1
            return out
        return _patch(sets=[(indy, "ref_detect", bug)])
    inj.append(("E28", "C23", "参照实现凭空多算「自摸」（对拍灵敏度）", e28, []))

    # ---- E29 七对退回「7 个不同对子」的旧口径（4 张不算两对）
    def e29():
        orig = M.decompositions
        def bug(concealed, melds):
            out = orig(concealed, melds)
            if any(v == 4 for v in counts_of(concealed)):
                out = [d for d in out if not d.tag]      # 旧口径：含四张就不是七对
            return out
        M.decompositions = bug
        return lambda: setattr(M, "decompositions", orig)
    inj.append(("E29", "C25", "七对退回旧口径（4 张同牌不算两对）", e29,
                _extra_qidui_four()))

    return inj


# ==================================================================== 口径审计

def qidui_four_scope():
    """「七对能否含 4 张同牌」两种口径各覆盖多少手牌（影响面）"""
    from math import comb
    one4 = 34 * comb(33, 5)                 # 1 个 4 张 + 5 个对子
    two4 = comb(34, 2) * comb(32, 3)        # 2 个 4 张 + 3 个对子
    three4 = comb(34, 3) * comb(31, 1)      # 3 个 4 张 + 1 个对子
    return one4, two4, three4, one4 + two4 + three4


def audit_interpretations():
    """口径审计：「七对能否含 4 张相同的牌」——已裁定**按国标口径（4 张算两对）**"""
    p = []
    a, b, c, tot = qidui_four_scope()
    p.append("七对含 4 张相同的牌：**已按国标口径实现**（4 张相同的牌算两对）——"
             "`1111 22 33 44 55 66` 即七对；共影响 %d 手牌"
             "（1 个四张 %d + 2 个四张 %d + 3 个四张 %d）" % (tot, a, b, c))
    p.append("对应防护：① 注入 E29「退回 7 个不同对子的旧口径」必须被 D4/D6b 抓到；"
             "② `verify_all.py` 已把这三类牌型纳入枚举（3 个四张完整 185,504 手 + 1~2 个四张抽样 12 万手）；"
             "③ `test_engine.py` 新增含四张的七对回归用例")
    p.append("注意：含 4 张同牌时「四归一」属必然并存，按《问答》Q71 不计（已由不计表保证）")
    return p


# ==================================================================== 主流程

def main():
    t0 = time.time()
    log("=" * 78)
    log("国标麻将算番器 —— 错误类别全枚举 + 故障注入验证")
    log("时间: %s    检测器: D1/D1b/D2/D2b/D3/D4/D5/D6/D6b/D7/D8/D9/D10    "
        "错误类别: %d 类" % (time.strftime("%Y-%m-%d %H:%M:%S"), len(CATEGORIES)))
    log("=" * 78)

    inj = _make_injections()
    extra = []
    for _i, _c, _m, _fn, _hs in inj:
        extra.extend(_hs)
    extra.extend(_extra_meld_ankou())
    extra.extend(_extra_kong_pair_hands())
    big_pool = build_pool(extra)
    small_pool = build_pool(extra, small=True)
    log("\n【0】断言用牌池：大池 %d 手（基线用）/ 小池 %d 手（逐类注入用）"
        " —— 金标准 81 + 随机和牌 + 选项组合 + 副露·杠 + 听牌 + 定向反例"
        % (len(big_pool), len(small_pool)))

    log("\n【1】基线（未注入）：跑全部检测器")
    base = run_detectors(big_pool)
    nbase = sum(len(v) for v in base.values())
    for k in sorted(base):
        log("  · %-22s 问题 %d 条" % (k, len(base[k])))
    if nbase:
        log("  ⚠ 基线不干净：")
        for k in sorted(base):
            for s in base[k][:5]:
                log("      [%s] %s" % (k, s))
    else:
        log("  ✅ 基线全部检测器无问题（干净起点）")

    log("\n【2】故障注入：逐类注入真实缺陷，检查能否被检测器抓到")
    rows = []
    blind = []
    base_sig = {(k, s) for k, v in base.items() for s in v}   # 基线已有问题不算「检出」
    for cid, cat, mech, apply_fn, hands in inj:
        restore = None
        try:
            restore = apply_fn()
            probs = run_detectors(small_pool)
        except Exception as exc:                       # noqa: BLE001
            probs = {"注入后运行异常": [repr(exc)]}
        finally:
            if restore:
                restore()
        hit = {k: [s for s in v if (k, s) not in base_sig]
               for k, v in probs.items()}
        hit = {k: v for k, v in hit.items() if v}
        rows.append((cid, cat, mech, hit, hands))
        if hit:
            who = "、".join(sorted(hit))
            sample = ""
            for k in sorted(hit):
                if hit[k] and not sample:
                    sample = hit[k][0]
            log("  %-5s %-8s 检出 ✅  %s" % (cid, cat, who))
            log("         缺陷：%s" % mech)
            log("         例证：%s" % sample[:150])
        else:
            blind.append((cid, mech))
            log("  %-5s %-8s ★盲区★ 没有任何检测器发现：%s" % (cid, cat, mech))

    log("\n【3】口径不确定项审计（不是 bug，但必须量化影响）")
    for s in audit_interpretations():
        log("  · %s" % s)

    log("\n【4】不可注入类的定向直检（D10 接口边界）")
    api = det_api_boundary()
    if api:
        for s in api:
            log("      ! %s" % s)
    else:
        log("  ✅ 张数不足 / 超过 4 张 / 和张不在手牌 / 花牌与起和口径 全部正确")

    log("\n" + "=" * 78)
    log("【汇总】")
    log("  · 错误类别           : %d 类" % len(CATEGORIES))
    log("  · 故障注入           : %d 个（历史真缺陷 6 个：E01/E03/E04/E06 + 绿一色/一色双龙会）"
        % len(rows))
    log("  · 被检测器抓到        : %d 个" % (len(rows) - len(blind)))
    log("  · 基线问题            : %d 条" % nbase)
    log("  · 校验盲区            : %d 个 %s" % (len(blind), [b[0] for b in blind]))
    det_used = sorted({k for _a, _b, _c, hit, _d in rows for k in hit})
    log("  · 实际发挥作用的检测器 : %s" % "、".join(det_used))
    if blind or nbase:
        log("结论： ⚠ 存在待处理项（见上）")
    else:
        log("结论： ✅ %d 类错误全部「能被检出」——任何一类真缺陷都不会悄悄溜过去"
            % len(CATEGORIES))
    log("用时 %.0fs，详细日志见 _scaffold\\_audit_out.txt" % (time.time() - t0))
    log("=" * 78)
    return 1 if (blind or nbase) else 0


if __name__ == "__main__":
    sys.exit(main())
