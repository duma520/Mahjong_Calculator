# -*- coding: utf-8 -*-
"""indy.py —— 算番「第二套独立实现」（**只用于交叉校验，不参与打包分发**）

设计原则：与 `mahjong_core` **不共用任何判定逻辑**，只共用「牌张编号 0~33」这一数据接口约定。
    * 花色/点数用自己的函数（i_suit / i_num，字牌另分风 3 / 箭 4）
    * 牌型分解是自己写的递归（ind_decomps）
    * 81 个番种逐条按《规则》定义**另写一遍**（ref_detect）
    * 「不计」闭包也是自己写的（ref_final）

用途：把两套实现放在**同一个分解、同一手牌、同一选项**下比对：
    * 一边算出的番种集合 / 番数，另一边也必须一样
    * 出现差异 ⇒ 至少一套算错（多算 / 少算 / 漏算），逐条人工确认

本文件不 import mahjong_core。
"""

# ------------------------------------------------------------------ 牌张编码

def i_suit(t: int) -> int:
    """0 筒 / 1 索 / 2 万 / 3 风 / 4 箭"""
    if t < 27:
        return t // 9
    return 3 if t < 31 else 4


def i_num(t: int) -> int:
    """序数牌 1~9；字牌 1~7（东南西北中发白）"""
    if t < 27:
        return t % 9 + 1
    return t - 26


def i_is_number(t: int) -> bool:
    return t < 27


def i_is_terminal(t: int) -> bool:
    """序数牌的 一 / 九"""
    return t < 27 and i_num(t) in (1, 9)


def i_is_yao(t: int) -> bool:
    """幺九牌：一、九 与 字牌"""
    return t >= 27 or i_num(t) in (1, 9)


H_WINDS = (27, 28, 29, 30)
H_DRAGONS = (31, 32, 33)

# 绿一色：二三四六八索 + 发（规则原文「由索的二、三、四、六、八及发组成的和牌」）
GREEN_TILES = {10, 11, 12, 14, 16, 32}
# 推不倒：一二三四五八九筒、二四五六八九索、白板（规则原文）
PUSHABLE = {0, 1, 2, 3, 4, 7, 8, 10, 12, 13, 14, 16, 17, 33}
# 十三幺的 13 张
THIRTEEN = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]


def i_counts(tiles) -> list:
    c = [0] * 34
    for t in tiles:
        c[t] += 1
    return c


def i_tiles(c) -> list:
    return [t for t in range(34) for _ in range(c[t])]


# ------------------------------------------------------------------ 牌型分解

def ind_sets(c, need):
    """把计数 c 拆成 need 个「面子」（不含将），返回全部拆法（每种是排序后的元组）"""
    out = []

    def rec(cc, packs, n):
        if n == 0:
            if not any(cc):
                out.append(tuple(sorted(packs)))
            return
        # 取最小的一张牌做「第一组」
        first = -1
        for i in range(34):
            if cc[i]:
                first = i
                break
        if first < 0:
            return
        if cc[first] >= 3:
            cc[first] -= 3
            rec(cc, packs + (('p', first),), n - 1)
            cc[first] += 3
        if i_is_number(first) and i_num(first) <= 7 and cc[first + 1] and cc[first + 2]:
            cc[first] -= 1
            cc[first + 1] -= 1
            cc[first + 2] -= 1
            rec(cc, packs + (('c', first),), n - 1)
            cc[first] += 1
            cc[first + 1] += 1
            cc[first + 2] += 1

    rec(list(c), (), need)
    return out


def ind_decomps(c, need_sets):
    """返回 {(面子元组, 将牌)} 的集合（含组合龙：用 'L' 伪面子表示）"""
    res = set()
    n = sum(c)
    if need_sets < 0 or n != need_sets * 3 + 2:
        return res
    for p in range(34):
        if c[p] >= 2:
            cc = list(c)
            cc[p] -= 2
            for packs in ind_sets(cc, need_sets):
                res.add((packs, p))
    if need_sets == 4:                       # 组合龙：9 张龙牌占 3 组 + 1 面子 + 将
        for pat in LONG_PAT:
            if all(c[t] >= 1 for t in pat):
                cc = list(c)
                for t in pat:
                    cc[t] -= 1
                groups = (('L', tuple(sorted(pat[0:3]))),
                          ('L', tuple(sorted(pat[3:6]))),
                          ('L', tuple(sorted(pat[6:9]))))
                for p in range(34):
                    if cc[p] >= 2:
                        c2 = list(cc)
                        c2[p] -= 2
                        for packs in ind_sets(c2, 1):
                            res.add((tuple(sorted(groups + packs)), p))
    return res


def ind_win(c) -> bool:
    """14 张是否和牌（含特殊牌型）"""
    if ind_decomps(c, 4):
        return True
    return ind_special(c) is not None


def ind_special(c):
    """七对 / 连七对 / 十三幺 / 全不靠 / 七星不靠 的独立判定（14 张）"""
    if sum(c) != 14:
        return None
    # 十三幺
    if all(c[t] >= 1 for t in THIRTEEN) and sum(c[t] for t in THIRTEEN) == 14:
        return "十三幺"
    # 七对（★ 国标口径：4 张相同的牌算两对）
    if all(v in (0, 2, 4) for v in c) and sum(v // 2 for v in c) == 7:
        kinds = [t for t in range(34) if c[t] == 2]
        if len(kinds) == 7 and i_is_number(kinds[0]) and \
                i_suit(kinds[0]) == i_suit(kinds[6]) and kinds[6] == kinds[0] + 6:
            return "连七对"
        return "七对"
    # 全不靠 / 七星不靠
    used = [t for t in range(34) if c[t]]
    if len(used) == 14 and all(c[t] == 1 for t in used):
        honors = [t for t in used if t >= 27]
        nums = [t for t in used if t < 27]
        for cols in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
            if all((i_num(t) - 1) % 3 == cols[i_suit(t)] for t in nums):
                if len(honors) == 7:
                    return "七星不靠"
                return "全不靠"
    return None


def ind_waits(c13, need_sets) -> set:
    """13 张（或 13-3m 张）的听牌张集合"""
    out = set()
    for t in range(34):
        if c13[t] >= 4:
            continue
        c13[t] += 1
        ok = bool(ind_decomps(c13, need_sets)) or ind_special(c13) is not None
        c13[t] -= 1
        if ok:
            out.add(t)
    return out


# 组合龙：三种花色分别取「隔三」的三组，且不能错位
LONG_PAT = []
for _p in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
    LONG_PAT.append(tuple(sorted(
        _p[k] * 9 + (k + off) for k in range(3) for off in (0, 3, 6))))
LONG_PAT = sorted(set(LONG_PAT))


def ind_long_dragon(c):
    """若 c 里含组合龙的 9 张，返回 (剩余计数, 龙牌组)"""
    if sum(c) < 9:
        return None
    for pat in LONG_PAT:
        if all(c[t] >= 1 for t in pat):
            cc = list(c)
            for t in pat:
                cc[t] -= 1
            return cc, pat
    return None


# ------------------------------------------------------------------ 番种判定


def ref_detect(c, sets, pair, win, opts):
    """独立实现：给定**同一个分解**，算出命中的番种（未做「不计」处理）

    c    : 34 长度计数（含副露牌）
    sets : [(kind, tile, concealed)]  kind ∈ 'c'(顺) 'p'(刻) 'k'(杠) 'L'(组合龙一组)
           concealed=True 表示暗的（暗刻 / 暗杠 / 手中顺子）
    pair : 将牌 tile（-1 表示无，如七对）
    win  : 和张 tile
    opts : dict(tsumo,last_tile,rob_kong,kong_bloom,last_draw,last_discard,
                round_wind,seat_wind,flowers,single_wait)
    """
    f = {}

    def put(n, v=1):
        f[n] = v

    chows = [s[1] for s in sets if s[0] == 'c']
    pongs = [s[1] for s in sets if s[0] == 'p']
    kongs = [s for s in sets if s[0] == 'k']
    longs = [s for s in sets if s[0] == 'L']
    allsets = sets
    n_sets = len(allsets)

    def chi_start(t):
        return t

    def in_chi(t):
        return any(s[0] == 'c' and s[1] <= t <= s[1] + 2 for s in sets)

    # ---- 特殊牌型 ----
    tag = opts.get("tag") or ""
    if tag == "十三幺":
        put("十三幺", 88)
    elif tag == "连七对":
        put("连七对", 88)
    elif tag == "七对":
        put("七对", 24)
    elif tag == "七星不靠":
        put("七星不靠", 24)
    elif tag == "全不靠":
        put("全不靠", 12)
    if longs:
        put("组合龙", 12)

    suits = {i_suit(t) for t in range(34) if c[t]}
    numsuits = {s for s in suits if s <= 2}
    has_honor = any(c[t] for t in range(27, 34))
    all_yao = all(i_is_yao(t) for t in range(34) if c[t])
    all_pong = n_sets == 4 and all(s[0] in ('p', 'k') for s in sets)
    all_chi = n_sets == 4 and all(s[0] == 'c' for s in sets)

    def conc_pongs():
        """暗刻（含暗杠）；点炮补成的那副刻子算明刻"""
        out = []
        for s in sets:
            if s[0] == 'k':
                if s[2]:
                    out.append(s[1])
            elif s[0] == 'p' and s[2]:
                if not (not opts["tsumo"] and s[1] == win):
                    out.append(s[1])
        return out

    # ---- 88 分 ----
    if n_sets == 4 and all(s[0] in ('p', 'k') for s in sets) and \
            all(any(s[1] == w for s in sets) for w in H_WINDS):
        put("大四喜", 88)
    if all(any(s[0] in ('p', 'k') and s[1] == d for s in sets) for d in H_DRAGONS):
        put("大三元", 88)
    if all(t in GREEN_TILES for t in range(34) if c[t]):
        put("绿一色", 88)
    # 九莲宝灯：门前、一色、1112345678999 型
    if not any(s[2] is False for s in sets) and len(numsuits) == 1 and not has_honor:
        su = next(iter(numsuits))
        cc = [c[su * 9 + k] for k in range(9)]
        if cc[0] >= 3 and cc[8] >= 3 and all(cc[k] >= 1 for k in range(1, 8)) and \
                sum(cc) == 14:
            put("九莲宝灯", 88)
    if len(kongs) >= 4:
        put("四杠", 88)

    # ---- 64 分 ----
    # ★ 七对里「事实上存在清幺九」，按《问答》71 牌例 2 应另加计（其余牌型要求四副刻子）
    _qidui = tag in ("七对", "连七对")
    if (_qidui or all_pong) and not has_honor and \
            all(i_is_terminal(t) for t in range(34) if c[t]):
        put("清幺九", 64)
    if n_sets == 4 and sum(1 for w in H_WINDS if any(s[0] in ('p', 'k') and s[1] == w
                                                     for s in sets)) == 3 and \
            pair in H_WINDS:
        put("小四喜", 64)
    if sum(1 for d in H_DRAGONS if any(s[0] in ('p', 'k') and s[1] == d
                                       for s in sets)) == 2 and pair in H_DRAGONS:
        put("小三元", 64)
    if has_honor and not numsuits:
        put("字一色", 64)
    if len(conc_pongs()) == 4 and n_sets == 4:
        put("四暗刻", 64)
    if len(numsuits) == 1 and not has_honor and pair >= 0 and i_is_number(pair) and \
            i_num(pair) == 5:
        su = next(iter(numsuits))
        starts = sorted(s[1] - su * 9 + 1 for s in sets if s[0] == 'c')
        if starts.count(1) >= 2 and starts.count(7) >= 2 and len(sets) == 4:
            put("一色双龙会", 64)

    # ---- 48 分 ----
    if n_sets == 4 and any(chows.count(x) >= 4 for x in set(chows)):
        put("一色四同顺", 48)
    _g = {}
    for s in sets:
        if s[0] in ('p', 'k') and i_is_number(s[1]):
            _g.setdefault(i_suit(s[1]), []).append(i_num(s[1]))
    for su, nums in _g.items():
        u = sorted(set(nums))
        if len(u) == 4 and u[3] - u[0] == 3 and len(sets) == 4:
            put("一色四节高", 48)

    # ---- 32 分 ----
    for su in range(3):
        starts = sorted({s[1] for s in sets if s[0] == 'c' and i_suit(s[1]) == su})
        for step in (1, 2):
            for a in starts:
                if all(a + step * k in starts for k in range(4)):
                    put("一色四步高", 32)
    if len(kongs) == 3:
        put("三杠", 32)
    # ★ 七对里「事实上存在混幺九」，按《问答》71 牌例 6 应另加计（其余牌型要求四副刻子）
    if (_qidui or all_pong) and has_honor and all_yao:
        put("混幺九", 32)

    # ---- 24 分 ----
    if all_pong and not has_honor and \
            all(i_num(t) % 2 == 0 for t in range(34) if c[t]):
        put("全双刻", 24)
    if len(numsuits) == 1 and not has_honor:
        put("清一色", 24)
    if any(chows.count(x) >= 3 for x in set(chows)):
        put("一色三同顺", 24)
    for su, nums in _g.items():
        u = sorted(set(nums))
        if any(u[k + 2] - u[k] == 2 for k in range(len(u) - 2)):
            put("一色三节高", 24)
    if not has_honor and all(i_num(t) >= 7 for t in range(34) if c[t]):
        put("全大", 24)
    if not has_honor and all(4 <= i_num(t) <= 6 for t in range(34) if c[t]):
        put("全中", 24)
    if not has_honor and all(i_num(t) <= 3 for t in range(34) if c[t]):
        put("全小", 24)

    # ---- 16 分 ----
    for su in range(3):
        starts = {s[1] for s in sets if s[0] == 'c' and i_suit(s[1]) == su}
        if all(su * 9 + k in starts for k in (0, 3, 6)) and \
                any(i_suit(s[1]) == su and i_num(s[1]) == 1 for s in sets if s[0] == 'c') \
                and any(i_suit(s[1]) == su and i_num(s[1]) == 4 for s in sets if s[0] == 'c') \
                and any(i_suit(s[1]) == su and i_num(s[1]) == 7 for s in sets if s[0] == 'c'):
            put("清龙", 16)
    if pair >= 0 and i_is_number(pair) and i_num(pair) == 5 and len(sets) == 4:
        su_pair = i_suit(pair)
        others = [s for s in range(3) if s != su_pair]
        ok = True
        for su in others:
            starts = {s[1] for s in sets if s[0] == 'c' and i_suit(s[1]) == su}
            if not (su * 9 in starts and su * 9 + 6 in starts):
                ok = False
        if ok:
            put("三色双龙会", 16)
    for su in range(3):
        starts = sorted({s[1] - su * 9 + 1 for s in sets
                         if s[0] == 'c' and i_suit(s[1]) == su})
        for step in (1, 2):
            for a in starts:
                if all(a + step * k in starts for k in range(3)):
                    put("一色三步高", 16)
    _five = True
    for s in sets:
        if s[0] == 'c':
            if not (i_num(s[1]) <= 5 <= i_num(s[1]) + 2):
                _five = False
        elif s[0] == 'L':
            if not any(i_is_number(t) and i_num(t) == 5 for t in s[1]):
                _five = False
        else:
            if not (i_is_number(s[1]) and i_num(s[1]) == 5):
                _five = False
    if _five and pair >= 0 and i_is_number(pair) and i_num(pair) == 5:
        put("全带五", 16)
    _t = {}
    for t in pongs + [s[1] for s in kongs] + [s[1] for s in sets if s[0] == 'p']:
        if i_is_number(t):
            _t.setdefault(i_num(t), set()).add(i_suit(t))
    if any(len(v) >= 3 for v in _t.values()):
        put("三同刻", 16)
    if len(conc_pongs()) >= 3:
        put("三暗刻", 16)

    # ---- 12 分 ----
    if not has_honor and all(i_num(t) >= 6 for t in range(34) if c[t]) and \
            any(i_num(t) == 6 for t in range(34) if c[t]):
        put("大于五", 12)
    if not has_honor and all(i_num(t) <= 4 for t in range(34) if c[t]) and \
            any(i_num(t) == 4 for t in range(34) if c[t]):
        put("小于五", 12)
    if sum(1 for w in H_WINDS if any(s[0] in ('p', 'k') and s[1] == w
                                     for s in sets)) >= 3:
        put("三风刻", 12)

    # ---- 8 分 ----
    _hua = False
    _ci = [s for s in sets if s[0] == 'c']
    for _perm in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
        if all(any(i_suit(s[1]) == _perm[k] and i_num(s[1]) == 1 + 3 * k
                   for s in _ci) for k in range(3)):
            _hua = True
            break
    if _hua:
        put("花龙", 8)
    if all(t in PUSHABLE for t in range(34) if c[t]):
        put("推不倒", 8)
    for n in range(1, 8):
        ss = {i_suit(s[1]) for s in sets if s[0] == 'c' and i_num(s[1]) == n}
        if len(ss) >= 3:
            put("三色三同顺", 8)
            break
    _t2 = {}
    for t in pongs + [s[1] for s in kongs]:
        if i_is_number(t):
            _t2.setdefault(i_num(t), set()).add(i_suit(t))
    for n in range(1, 8):
        if all(n + k in _t2 for k in range(3)):
            if any(all(_perm[k] in _t2[n + k] for k in range(3))
                   for _perm in ((0, 1, 2), (0, 2, 1), (1, 0, 2),
                                 (1, 2, 0), (2, 0, 1), (2, 1, 0))):
                put("三色三节高", 8)
                break
    if opts["last_draw"]:
        put("妙手回春", 8)
    if opts["last_discard"]:
        put("海底捞月", 8)
    if opts["kong_bloom"]:
        put("杠上开花", 8)
    if opts["rob_kong"]:
        put("抢杠和", 8)

    # ---- 6 分 ----
    if all_pong:
        put("碰碰和", 6)
    if len(numsuits) == 1 and has_honor:
        put("混一色", 6)
    for n in range(1, 7):
        hits = []
        for k in range(3):
            ss = [s for s in sets if s[0] == 'c' and i_num(s[1]) == n + k]
            if ss:
                hits.append({i_suit(s[1]) for s in ss})
        if len(hits) == 3:
            for x in hits[0]:
                for y in hits[1]:
                    for z in hits[2]:
                        if len({x, y, z}) == 3:
                            put("三色三步高", 6)
                            break
    if len(numsuits) == 3 and any(c[t] for t in H_WINDS) and any(c[t] for t in H_DRAGONS):
        put("五门齐", 6)
    if n_sets == 4 and all(s[2] is False for s in sets) and not opts["tsumo"] and \
            opts.get("single_wait"):
        put("全求人", 6)
    if sum(1 for s in kongs if s[2]) == 2 and len(kongs) == 2:
        put("双暗杠", 6)
    if sum(1 for d in H_DRAGONS if any(s[0] in ('p', 'k') and s[1] == d
                                       for s in sets)) >= 2:
        put("双箭刻", 6)

    # ---- 4 分 ----
    _dai = pair >= 0 and i_is_yao(pair)
    if _dai:
        for s in sets:
            if s[0] == 'L':
                if not any(i_is_yao(t) for t in s[1]):
                    _dai = False
            elif not any(i_is_yao(t if s[0] == 'c' else s[1])
                         for t in ((s[1], s[1] + 1, s[1] + 2) if s[0] == 'c'
                                   else (s[1],))):
                _dai = False
    if _dai:
        put("全带幺", 4)
    if not any(s[2] is False for s in sets) and opts["tsumo"]:
        put("不求人", 4)
    if sum(1 for s in kongs if not s[2]) == 2 and len(kongs) == 2:
        put("双明杠", 4)
    if opts["last_tile"]:
        put("和绝张", 4)

    # ---- 2 分 ----
    _dk = [d for d in H_DRAGONS if any(s[0] in ('p', 'k') and s[1] == d for s in sets)]
    if len(_dk) == 1:
        put("箭刻", 2)
    if any(s[0] in ('p', 'k') and s[1] == opts["round_wind"] for s in sets):
        put("圈风刻", 2)
    if any(s[0] in ('p', 'k') and s[1] == opts["seat_wind"] for s in sets):
        put("门风刻", 2)
    if not any(s[2] is False for s in sets) and not opts["tsumo"]:
        put("门前清", 2)
    if all_chi and pair >= 0 and i_is_number(pair):
        put("平和", 2)
    _kongtiles = {s[1] for s in kongs}
    # ★ 特殊牌型（七对/连七对/十三幺/全不靠…）中的四归一属「必然并存」，按《问答》Q71 不计
    _si = 0 if tag else sum(1 for t in range(34) if c[t] == 4 and t not in _kongtiles)
    if _si:
        put("四归一", 2 * _si)
    _st = {}
    for t in [s[1] for s in sets if s[0] == 'p'] + [s[1] for s in kongs]:
        if i_is_number(t):
            _st.setdefault(i_num(t), set()).add(i_suit(t))
    _nst = sum(len(v) - 1 for v in _st.values() if len(v) >= 2)
    if _nst and not any(len(v) >= 3 for v in _st.values()):
        put("双同刻", 2 * _nst)
    if len(conc_pongs()) == 2:
        put("双暗刻", 2)
    if sum(1 for s in kongs if s[2]) == 1 and len(kongs) == 1:
        put("暗杠", 2)
    if not has_honor and all(i_num(t) not in (1, 9) for t in range(34) if c[t]):
        put("断幺", 2)

    # ---- 1 分 ----
    _bg = {}
    for s in sets:
        if s[0] == 'c':
            k = (i_suit(s[1]), i_num(s[1]))
            _bg[k] = _bg.get(k, 0) + 1
    _nbg = sum(v - 1 for v in _bg.values() if v >= 2)
    if _nbg:
        put("一般高", _nbg)
    _xf = {}
    for s in sets:
        if s[0] == 'c':
            _xf.setdefault(i_num(s[1]), set()).add(i_suit(s[1]))
    _nxf = sum(len(v) - 1 for v in _xf.values() if len(v) >= 2)
    if _nxf:
        put("喜相逢", _nxf)
    _nll = 0
    for su in range(3):
        st = {i_num(s[1]) for s in sets if s[0] == 'c' and i_suit(s[1]) == su}
        _nll += sum(1 for i in (1, 2, 3, 4) if i in st and i + 3 in st)
    if _nll:
        put("连六", _nll)
    _nlsf = sum(1 for su in range(3)
                if any(s[0] == 'c' and i_suit(s[1]) == su and i_num(s[1]) == 1
                       for s in sets)
                and any(s[0] == 'c' and i_suit(s[1]) == su and i_num(s[1]) == 7
                        for s in sets))
    if _nlsf:
        put("老少副", _nlsf)
    # 幺九刻（扣除被箭刻/圈门风刻/三风刻/混幺九/字一色/九莲宝灯覆盖的刻子）
    cov = set(H_DRAGONS)
    if any(s[0] in ('p', 'k') and s[1] == opts["round_wind"] for s in sets):
        cov.add(opts["round_wind"])
    if any(s[0] in ('p', 'k') and s[1] == opts["seat_wind"] for s in sets):
        cov.add(opts["seat_wind"])
    if sum(1 for w in H_WINDS if any(s[0] in ('p', 'k') and s[1] == w
                                     for s in sets)) >= 3 or \
            (has_honor and not numsuits):
        cov |= set(H_WINDS)
    if all_pong and has_honor and all_yao:
        cov |= {t for t in range(34) if c[t]}
    if "九莲宝灯" in f:
        su = next(iter(numsuits))
        cov |= {su * 9, su * 9 + 8}
    _nyao = sum(1 for s in sets
                if s[0] in ('p', 'k') and i_is_yao(s[1]) and s[1] not in cov)
    if _nyao:
        put("幺九刻", _nyao)
    if len(kongs) == 1 and not kongs[0][2]:
        put("明杠", 1)
    elif len(kongs) == 2 and sum(1 for s in kongs if s[2]) == 1:
        put("双明杠", 4)
        put("暗杠", 2)
    elif len(kongs) == 3:
        # 三杠（32 分）另加计：1 暗杠 +2；双暗杠 +6（《问答》第 41 条）
        _ck = sum(1 for s in kongs if s[2])
        if _ck == 1:
            put("暗杠", 2)
        elif _ck == 2:
            put("双暗杠", 6)
    if len(numsuits) == 2:
        put("缺一门", 1)
    if not has_honor:
        put("无字", 1)
    if opts.get("single_wait"):
        if pair == win and c[win] >= 2:
            _shape = None
            for s in sets:
                if s[0] == 'c' and s[1] <= win <= s[1] + 2:
                    _shape = "坎张" if i_num(win) == i_num(s[1]) + 1 else (
                        "边张" if (i_num(s[1]) == 1 and i_num(win) == 3) or
                        (i_num(s[1]) == 7 and i_num(win) == 7) else None)
                    break
            put(_shape or "单钓将", 1)
        else:
            for s in sets:
                if s[0] == 'c' and s[1] <= win <= s[1] + 2:
                    if i_num(win) == i_num(s[1]) + 1:
                        put("坎张", 1)
                    elif (i_num(s[1]) == 1 and i_num(win) == 3) or \
                            (i_num(s[1]) == 7 and i_num(win) == 7):
                        put("边张", 1)
                    break
    if opts["tsumo"]:
        put("自摸", 1)

    return f


def ref_final(fans, excl_table):
    """独立实现的「不计」闭包（高分优先反复剔除），不做任何额外保护策略"""
    out = dict(fans)
    changed = True
    while changed:
        changed = False
        for x in sorted(out, key=lambda n: -out[n]):
            if x not in out:
                continue
            for y in excl_table.get(x, ()):
                if y in out:
                    del out[y]
                    changed = True
    return out


def ref_score(c, sets, pair, win, opts, excl_table):
    """给出一手牌的最终番种字典（独立实现口径）"""
    raw = ref_detect(c, sets, pair, win, opts)
    fin = ref_final(raw, excl_table)
    if not fin:
        fin = {"无番和": 8}
    return raw, fin
