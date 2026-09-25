# -*- coding: utf-8 -*-
"""国标麻将（《中国麻将竞赛规则》1998）算番核心引擎 —— 重建版

本模块原源码曾丢失（只剩 __pycache__ 里的 .pyc），现按 `国标麻将标准规则.json`
（依据 1998 年国家体育总局审定《中国麻将竞赛规则(试行)》＋杜维忠《问答》整理）
重新实现，保持旧 .pyc 反查出的公开接口：

    MahjongFanCalculator()
    calc.calculate_fan(tiles, hand_config) -> Dict[str, int]
    calc.is_winning_hand(tiles) -> bool
    calc.get_possible_winning_tiles(tiles) -> List[Tuple[str, Dict[str, int]]]

并新增带副露/和张/特殊番种的新接口（GUI 使用）：

    calc.score(melds, concealed, win_tile, opts) -> Score
    calc.winning_tiles(melds, concealed, opts) -> List[Tuple[int, Score]]

牌张编码（与 GUI、tiles 目录一致）：
    0..8   B1..B9   筒（一筒~九筒）
    9..17  T1..T9   索（一索~九索）
    18..26 W1..W9   万（一万~九万）
    27..30 F1..F4   风（东、南、西、北）
    31..33 J1..J3   箭（中、发、白）

设计要点：
    * 副露（吃/碰/明杠/暗杠）由 `Meld` 表达；暗杠不影响门前清。
    * 暗手牌用「枚举全部分解」的方式匹配（顺子/刻子/将），并额外处理
      七对、十三幺、全不靠、七星不靠、组合龙 这些非标准牌型。
    * 每个分解都算一遍番种，取「就高不就低」的最高总番。
    * 番种的「不计」排除表直接读规则 JSON 的 `不计` 字段。
"""
from __future__ import annotations

import itertools
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------- 牌编码

CN_NUM = "一二三四五六七八九"
SUIT_CN = {0: "筒", 1: "索", 2: "万"}
HONOR_CN = {27: "东", 28: "南", 29: "西", 30: "北", 31: "中", 32: "发", 33: "白"}

TILE_CODES: Tuple[str, ...] = tuple(
    ["B%d" % i for i in range(1, 10)]
    + ["T%d" % i for i in range(1, 10)]
    + ["W%d" % i for i in range(1, 10)]
    + ["F%d" % i for i in range(1, 5)]
    + ["J%d" % i for i in range(1, 4)]
)

HONOR_IDS = tuple(range(27, 34))
WIND_IDS = (27, 28, 29, 30)
DRAGON_IDS = (31, 32, 33)

# 花牌（春、夏、秋、冬、梅、兰、竹、菊）在 UI 上用计数表达
FLOWER_NAMES = ("春", "夏", "秋", "冬", "梅", "兰", "竹", "菊")

# 特殊牌面集合
# 绿一色：二三四六八『索』+ 发（规则原文：由 23468 条及发字中的任何牌组成）
GREEN_TILES = {10, 11, 12, 14, 16, 32}         # 索2,3,4,6,8 + 发
PUSHABLE_TILES = {                       # 推不倒：1234589筒、245689条、白板
    0, 1, 2, 3, 4, 7, 8,                   # 1,2,3,4,5,8,9 筒
    10, 12, 13, 14, 16, 17,                # 2,4,5,6,8,9 索
    33,                                    # 白板
}
# 全不靠 / 组合龙的 16 张候选牌（147、258、369 三种花色 + 7 种字牌）
BU_KAO_TILES = {
    0, 3, 6,        # 1,4,7 筒
    1, 4, 7,        # 2,5,8 筒
    2, 5, 8,        # 3,6,9 筒
    9, 12, 15,      # 1,4,7 索
    10, 13, 16,     # 2,5,8 索
    11, 14, 17,     # 3,6,9 索
    18, 21, 24,     # 1,4,7 万
    19, 22, 25,     # 2,5,8 万
    20, 23, 26,     # 3,6,9 万
}
ALL_HONORS = set(HONOR_IDS)

# 组合龙的三种「同花色隔三」三张组（每种花色 3 个组合）
LONG_GROUPS = [
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (9, 12, 15), (10, 13, 16), (11, 14, 17),
    (18, 21, 24), (19, 22, 25), (20, 23, 26),
]


def suit_of(tid: int) -> int:
    """0=筒 1=索 2=万 3=风 4=箭"""
    if tid < 27:
        return tid // 9
    return 3 if tid < 31 else 4


def num_of(tid: int) -> int:
    """数牌返回 1~9；风返回 1~4（东南西北）；箭返回 1~3（中发白）"""
    if tid < 27:
        return tid % 9 + 1
    if tid < 31:
        return tid - 26
    return tid - 30


def is_suit(tid: int) -> bool:
    return tid < 27


def is_honor(tid: int) -> bool:
    return tid >= 27


def code_of(tid: int) -> str:
    return TILE_CODES[tid]


def tile_of(code: str) -> int:
    return TILE_CODES.index(code)


def name_of(tid: int) -> str:
    if tid < 27:
        return CN_NUM[num_of(tid) - 1] + SUIT_CN[suit_of(tid)]
    return HONOR_CN[tid]


def names_of(tiles: Iterable[int]) -> str:
    return " ".join(name_of(t) for t in tiles)


def counts_of(tiles: Iterable[int]) -> List[int]:
    c = [0] * 34
    for t in tiles:
        c[t] += 1
    return c


def is_terminal_or_honor(tid: int) -> bool:
    """幺九牌：数牌的一、九 或 字牌"""
    if is_honor(tid):
        return True
    return num_of(tid) in (1, 9)


# ---------------------------------------------------------------- 数据结构


@dataclass(frozen=True)
class Meld:
    """一个副露面子。

    kind      : 'chi'（吃，3 张顺子）/ 'pong'（碰，3 张相同）/ 'kong'（杠，4 张）
    tiles     : 牌 id 元组（chi 已排序；pong/kong 为相同牌）
    concealed : True = 暗杠（暗杠不影响门前清）
    added     : True = 补杠（碰后加杠），仍计明杠
    """

    kind: str
    tiles: Tuple[int, ...]
    concealed: bool = False
    added: bool = False

    @property
    def is_kong(self) -> bool:
        return self.kind == "kong"

    @property
    def is_triplet(self) -> bool:
        return self.kind in ("pong", "kong")

    @property
    def is_exposed(self) -> bool:
        """是否属于「亮明」的面子（影响门前清/不求人）"""
        return not (self.kind == "kong" and self.concealed)

    @property
    def tile(self) -> int:
        return self.tiles[0]


@dataclass(frozen=True)
class Set_:
    """分解出的一个面子（含副露与暗手面子）"""

    kind: str            # 'chi' | 'pong' | 'kong'
    tiles: Tuple[int, ...]
    concealed: bool      # 是否为暗（抓在手中的刻子 / 暗顺 / 暗杠）

    @property
    def is_kong(self) -> bool:
        return self.kind == "kong"

    @property
    def is_exposed(self) -> bool:
        """暗杠仍算「暗」，不影响门前清"""
        return not self.concealed

    @property
    def is_triplet(self) -> bool:
        return self.kind in ("pong", "kong")

    @property
    def tile(self) -> int:
        return self.tiles[0]


@dataclass
class Score:
    """一次算番的结果"""

    fans: List[Tuple[str, int]] = field(default_factory=list)   # 番种（降序）
    total: int = 0          # 总番（含花牌）
    base: int = 0           # 起和分口径（不含花牌）
    flowers: int = 0
    ok: bool = False        # base >= 8
    message: str = ""
    pattern: str = ""       # 命中的牌型说明（如「七对」「组合龙+…」）

    @property
    def fan_map(self) -> Dict[str, int]:
        return {n: v for n, v in self.fans}

    def text(self) -> str:
        if not self.fans:
            return "无番种"
        return "、".join("%s%d番" % (n, v) for n, v in self.fans)


@dataclass
class Options:
    """算番选项"""

    tsumo: bool = False              # 自摸
    last_tile: bool = False          # 和绝张
    rob_kong: bool = False           # 抢杠和
    kong_bloom: bool = False         # 杠上开花
    last_draw: bool = False          # 妙手回春（自摸牌墙最后一张）
    last_discard: bool = False       # 海底捞月（和打出的最后一张）
    round_wind: str = "东"           # 圈风
    seat_wind: str = "东"            # 门风
    flowers: int = 0                 # 花牌张数

    def to_dict(self) -> Dict[str, object]:
        return {
            "tsumo": self.tsumo, "last_tile": self.last_tile,
            "rob_kong": self.rob_kong, "kong_bloom": self.kong_bloom,
            "last_draw": self.last_draw, "last_discard": self.last_discard,
            "round_wind": self.round_wind, "seat_wind": self.seat_wind,
            "flowers": self.flowers,
        }


WIND_NAME_TO_ID = {"东": 27, "南": 28, "西": 29, "北": 30}


# ---------------------------------------------------------------- 规则表

DEFAULT_FAN_TABLE: Dict[int, List[str]] = {
    88: ["大四喜", "大三元", "绿一色", "九莲宝灯", "四杠", "连七对", "十三幺"],
    64: ["清幺九", "小四喜", "小三元", "字一色", "四暗刻", "一色双龙会"],
    48: ["一色四同顺", "一色四节高"],
    32: ["一色四步高", "三杠", "混幺九"],
    24: ["七对", "七星不靠", "全双刻", "清一色", "一色三同顺", "一色三节高",
         "全大", "全中", "全小"],
    16: ["清龙", "三色双龙会", "一色三步高", "全带五", "三同刻", "三暗刻"],
    12: ["全不靠", "组合龙", "大于五", "小于五", "三风刻"],
    8: ["花龙", "推不倒", "三色三同顺", "三色三节高", "无番和",
        "妙手回春", "海底捞月", "杠上开花", "抢杠和"],
    6: ["碰碰和", "混一色", "三色三步高", "五门齐", "全求人", "双暗杠", "双箭刻"],
    4: ["全带幺", "不求人", "双明杠", "和绝张"],
    2: ["箭刻", "圈风刻", "门风刻", "门前清", "平和", "四归一", "双同刻",
        "双暗刻", "暗杠", "断幺"],
    1: ["一般高", "喜相逢", "连六", "老少副", "幺九刻", "明杠", "缺一门",
        "无字", "边张", "坎张", "单钓将", "自摸"],
}
FLOWER_FAN = ("花牌", 1)

# 兜底排除表（规则 JSON 缺失时使用）—— 只列最关键的必然并存关系
DEFAULT_EXCLUDES: Dict[str, List[str]] = {
    "无番和": [],
}


def fan_value_map(table: Dict[int, List[str]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for value, names in table.items():
        for n in names:
            out[n] = value
    out["花牌"] = 1
    return out


# ---------------------------------------------------------------- 分解算法


@dataclass
class Decomp:
    """一种牌型分解结果"""

    sets: List[Set_] = field(default_factory=list)  # 4 个面子（含副露）
    pair: int = -1                                   # 将牌 tid（七对/十三幺等为 -1）
    tag: str = ""                                    # '' | '七对' | '连七对' | '十三幺' | '全不靠' | '七星不靠'
    long_dragon: bool = False                        # 是否含组合龙
    lian_qi: bool = False                            # 连七对


def walk_collect(c: List[int], out: List[Tuple[List[Set_], int]], need: int) -> None:
    """枚举 need 个面子的全部拆法（不含将）"""
    if need == 0:
        if sum(c) == 0:
            out.append(([], -1))
        return

    def walk(c2: List[int], start: int, sets: List[Set_], n: int) -> None:
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
        if is_suit(i) and num_of(i) <= 7 and c2[i + 1] and c2[i + 2]:
            c2[i] -= 1; c2[i + 1] -= 1; c2[i + 2] -= 1
            sets.append(Set_("chi", (i, i + 1, i + 2), True))
            walk(c2, i, sets, n - 1)
            sets.pop()
            c2[i] += 1; c2[i + 1] += 1; c2[i + 2] += 1

    walk(list(c), 0, [], need)


def _standard_splits(counts: List[int], need_sets: int) -> List[Tuple[List[Set_], int]]:
    """把 counts 拆成 need_sets 个面子 + 1 个将，返回 (面子列表, 将牌) 的全部可能"""
    out: List[Tuple[List[Set_], int]] = []
    if need_sets < 0 or sum(counts) != need_sets * 3 + 2:
        return out
    for p in range(34):
        if counts[p] < 2:
            continue
        c = list(counts)
        c[p] -= 2
        tmp: List[Tuple[List[Set_], int]] = []
        walk_collect(c, tmp, need_sets)
        for sets_, _ in tmp:
            out.append((sets_, p))
    return out


def _long_dragon_patterns() -> List[Tuple[int, ...]]:
    """组合龙 9 张牌的 6 种合法取法（花色与「147/258/369」的对应关系不能错位）"""
    pats = []
    for perm in itertools.permutations((0, 1, 2)):   # 三个花色分给 147 / 258 / 369
        pat = tuple(
            perm.index(k) * 9 + (0 + k) + off
            for k in range(3)
            for off in (0, 3, 6)
        )
        # perm[k] = 花色 k 对应的「第几组」；上面写法保证第 k 组落在 perm[k] 花色上
        pats.append(pat)
    seen, uniq = set(), []
    for p in pats:
        key = tuple(sorted(p))
        if key not in seen:
            seen.add(key)
            uniq.append(key)
    return uniq


LONG_PATTERNS = _long_dragon_patterns()


def decompositions(concealed: Sequence[int], melds: Sequence[Meld]) -> List[Decomp]:
    """枚举暗手牌的全部分解方式"""
    counts = counts_of(concealed)
    m = len(melds)
    need = 4 - m
    res: List[Decomp] = []

    if need >= 0 and sum(counts) == need * 3 + 2:
        for sets, pair in _standard_splits(counts, need):
            res.append(Decomp(sets=list(melds) + sets, pair=pair))

    # 组合龙（占 3 个「面子」，这 9 张牌本身不成顺子）
    if need >= 3 and sum(counts) == need * 3 + 2:
        for pat in LONG_PATTERNS:
            if all(counts[t] >= 1 for t in pat):
                c = list(counts)
                for t in pat:
                    c[t] -= 1
                long_sets = [Set_("long", tuple(sorted(pat[0:3])), True),
                             Set_("long", tuple(sorted(pat[3:6])), True),
                             Set_("long", tuple(sorted(pat[6:9])), True)]
                for sets, pair in _standard_splits(c, need - 3):
                    res.append(Decomp(sets=list(melds) + long_sets + sets,
                                      pair=pair, long_dragon=True))

    # 特殊牌型：只有门前（无副露）才可能
    # ★ 注意：七对必须是「门前无副露」，而明杠/暗杠都是副露（进 melds）
    #   ⇒ 己报枉的 4 张同牌**不能**再当两对用于七对（会自动落到 m != 0 分支以外）
    if m == 0 and sum(counts) == 14:
        # 七对：由 7 个对子组成
        # ★ 国标口径：4 张相同的牌算作两对，故 1111 22 33 44 55 66 也是七对
        #   （对子数 = Σ 张数/2 = 7，而不是「7 个不同对子」）
        if all(c in (0, 2, 4) for c in counts) and \
                sum(c // 2 for c in counts) == 7:
            kinds = [i for i in range(34) if counts[i] == 2]
            # ★ 连七对必须是「同一花色 + 序数连续」的 7 个对子
            #   （只比 tid 差值会把跨花色的七对误判成连七对，从而多算 88 分）
            lian = (len(kinds) == 7
                    and is_suit(kinds[0])
                    and suit_of(kinds[-1]) == suit_of(kinds[0])
                    and num_of(kinds[-1]) - num_of(kinds[0]) == 6)
            res.append(Decomp(sets=[], pair=-1,
                              tag="连七对" if lian else "七对", lian_qi=lian))
        # 十三幺
        need13 = [0, 8, 9, 17, 18, 26] + list(HONOR_IDS)
        if all(counts[t] >= 1 for t in need13) and \
                all(counts[t] <= 2 for t in need13) and \
                sum(counts[t] for t in need13) == 14:
            res.append(Decomp(sets=[], pair=-1, tag="十三幺"))
        # 全不靠 / 七星不靠
        if _is_bu_kao(counts):
            seven = all(counts[i] == 1 for i in ALL_HONORS)
            res.append(Decomp(sets=[], pair=-1,
                              tag="七星不靠" if seven else "全不靠"))
    return res


def _is_bu_kao(counts: List[int]) -> bool:
    """全不靠/七星不靠：14 张牌互不相同，三门花色各落在 147/258/369 中不同的「列」上"""
    used = [i for i in range(34) if counts[i]]
    if len(used) != 14 or any(counts[i] != 1 for i in used):
        return False
    numbered = [i for i in used if is_suit(i)]
    honors = [i for i in used if is_honor(i)]
    if any(i not in ALL_HONORS for i in honors):
        return False
    for cols in itertools.permutations((0, 1, 2)):    # 花色 k 使用第 cols[k] 列
        if all((num_of(t) - 1) % 3 == cols[suit_of(t)] for t in numbered):
            return True
    return False


# ---------------------------------------------------------------- 快速和牌判定
# 只用来回答「是/否能和」，不做对象构造，比 decompositions() 快一个数量级
# （waiting_tiles 每手要跑 34 次，全量校验与界面实时重算都吃这个开销）

THIRTEEN_IDS = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)


def _split_ok(c: List[int], need: int) -> bool:
    """c 能否拆成 need 个面子（会被就地修改，调用方负责还原）"""
    if need == 0:
        return not any(c)
    i = 0
    while i < 34 and not c[i]:
        i += 1
    if i >= 34:
        return False
    if c[i] >= 3:
        c[i] -= 3
        ok = _split_ok(c, need - 1)
        c[i] += 3
        if ok:
            return True
    if is_suit(i) and num_of(i) <= 7 and c[i + 1] and c[i + 2]:
        c[i] -= 1
        c[i + 1] -= 1
        c[i + 2] -= 1
        ok = _split_ok(c, need - 1)
        c[i] += 1
        c[i + 1] += 1
        c[i + 2] += 1
        if ok:
            return True
    return False


def _shape_win(counts: List[int], need: int) -> bool:
    """标准型：need 个面子 + 1 个将"""
    if sum(counts) != need * 3 + 2:
        return False
    for p in range(34):
        if counts[p] >= 2:
            c = list(counts)
            c[p] -= 2
            if _split_ok(c, need):
                return True
    return False


def _special_win_quick(counts: List[int]) -> bool:
    """无副露时：七对 / 十三幺 / 全不靠 / 七星不靠

    七对按国标口径：4 张相同的牌算两对，故只要「每个牌张数∈{0,2,4} 且对子数=7」即可。
    """
    if sum(counts) != 14:
        return False
    if all(v in (0, 2, 4) for v in counts) and \
            sum(v // 2 for v in counts) == 7:
        return True
    if all(counts[t] >= 1 for t in THIRTEEN_IDS) and \
            sum(counts[t] for t in THIRTEEN_IDS) == 14:
        return True
    return _is_bu_kao(counts)


def _long_dragon_win(counts: List[int]) -> bool:
    """无副露时：组合龙 9 张 + 1 个面子 + 1 个将"""
    if sum(counts) != 14:
        return False
    for pat in LONG_PATTERNS:
        if all(counts[t] >= 1 for t in pat):
            c = list(counts)
            for t in pat:
                c[t] -= 1
            if _shape_win(c, 1):
                return True
    return False


# ---------------------------------------------------------------- 判定上下文


@dataclass
class Ctx:
    d: Decomp
    melds: List[Meld]
    concealed_counts: List[int]
    all_counts: List[int]
    win_tile: int
    opts: Options
    single_wait: bool = False

    # ---- 便捷属性 ----
    @property
    def sets(self) -> List[Set_]:
        return self.d.sets

    @property
    def pair(self) -> int:
        return self.d.pair

    @property
    def tag(self) -> str:
        return self.d.tag

    @property
    def special(self) -> bool:
        return bool(self.d.tag)

    @property
    def tiles(self) -> List[int]:
        return [i for i in range(34) for _ in range(self.all_counts[i])]

    @property
    def suits_present(self) -> Set[int]:
        return {suit_of(i) for i in range(34) if self.all_counts[i]}

    @property
    def has_honor(self) -> bool:
        return any(self.all_counts[i] for i in HONOR_IDS)

    @property
    def melds_all(self) -> List[Meld]:
        return self.melds

    def n_sets(self, kind: str) -> int:
        return sum(1 for s in self.sets if s.kind == kind)

    @property
    def triplet_tiles(self) -> List[int]:
        return [s.tile for s in self.sets if s.is_triplet]

    @property
    def chi_starts(self) -> List[Tuple[int, int]]:
        """(花色/起始 tid) 列表"""
        return [s.tile for s in self.sets if s.kind == "chi"]

    @property
    def kong_count(self) -> int:
        return sum(1 for s in self.sets if s.is_kong)

    @property
    def exposed_kongs(self) -> int:
        return sum(1 for s in self.sets if s.is_kong and not s.concealed)

    @property
    def concealed_kongs(self) -> int:
        return sum(1 for s in self.sets if s.is_kong and s.concealed)

    @property
    def concealed_triplets(self) -> int:
        """暗刻个数（暗杠计入）；点炮补成的刻子按明刻处理"""
        n = 0
        for s in self.sets:
            if not s.is_triplet or not s.concealed:
                continue
            if not s.is_kong and not self.opts.tsumo and s.tile == self.win_tile:
                continue
            n += 1
        return n

    @property
    def no_exposed(self) -> bool:
        """没有吃、碰、明杠（暗杠不影响）"""
        return all(not s.is_exposed for s in self.sets)

    @property
    def all_sets_exposed(self) -> bool:
        return all(s.is_exposed for s in self.sets) and len(self.sets) == 4

    @property
    def all_sets_triplets(self) -> bool:
        return len(self.sets) == 4 and all(s.is_triplet for s in self.sets)

    @property
    def all_sets_chow(self) -> bool:
        return len(self.sets) == 4 and all(s.kind == "chi" for s in self.sets)

    @property
    def nums(self) -> List[int]:
        return [num_of(t) for t in self.tiles]

    @property
    def suit_nums(self) -> Dict[int, List[int]]:
        d: Dict[int, List[int]] = {}
        for i in range(34):
            if self.all_counts[i]:
                d.setdefault(suit_of(i), []).append(num_of(i))
        return d

    def round_wind_id(self) -> int:
        return WIND_NAME_TO_ID.get(self.opts.round_wind, 27)

    def seat_wind_id(self) -> int:
        return WIND_NAME_TO_ID.get(self.opts.seat_wind, 27)

    # ---------- 顺子/刻子分组辅助 ----------

    def chow_groups(self) -> Dict[Tuple[int, int], int]:
        """{(花色, 起始数字): 副数}"""
        g: Dict[Tuple[int, int], int] = {}
        for s in self.sets:
            if s.kind == "chi":
                g[(suit_of(s.tile), num_of(s.tile))] = \
                    g.get((suit_of(s.tile), num_of(s.tile)), 0) + 1
        return g

    def triplet_nums(self) -> Dict[int, List[int]]:
        """{数字: [花色…]}"""
        g: Dict[int, List[int]] = {}
        for s in self.sets:
            if s.is_triplet and is_suit(s.tile):
                g.setdefault(num_of(s.tile), []).append(suit_of(s.tile))
        return g


# ---------------------------------------------------------------- 番种判定


def _all_tiles_in(ctx: Ctx, allow: Set[int]) -> bool:
    return all((i in allow) for i in range(34) if ctx.all_counts[i])


def _same_suit(ctx: Ctx) -> Optional[int]:
    """清一色用：只有一种序数牌花色、且没有字牌"""
    if ctx.has_honor:
        return None
    s = {suit_of(i) for i in range(34) if ctx.all_counts[i]}
    return s.pop() if len(s) == 1 else None


def _one_number_suit(ctx: Ctx) -> Optional[int]:
    """混一色用：只有一种序数牌花色（允许有字牌）"""
    s = {suit_of(i) for i in range(34) if ctx.all_counts[i] and is_suit(i)}
    return s.pop() if len(s) == 1 else None


def _nums_within(ctx: Ctx, lo: int, hi: int) -> bool:
    return all(lo <= num_of(i) <= hi for i in range(34) if ctx.all_counts[i])


def _step_series(nums: Sequence[int], count: int, steps: Tuple[int, ...]) -> bool:
    """判断 nums 中是否存在 count 个数值，公差落在 steps 上（用于三/四步高）"""
    s = sorted(set(nums))
    for start in s:
        for step in steps:
            if all(start + step * k in s for k in range(count)):
                return True
    return False


def fan_da_si_xi(ctx: Ctx) -> bool:
    return ctx.all_sets_triplets and all(
        ctx.all_counts[w] >= 3 for w in WIND_IDS)


def fan_da_san_yuan(ctx: Ctx) -> bool:
    # ★ 大三元要求「箭牌的三副刻子」：七对等特殊牌型里没有刻子
    #   （4 张相同的牌算两对，不是刻子/杠），所以不能计大三元。
    if ctx.special:
        return False
    return all(ctx.all_counts[d] >= 3 for d in DRAGON_IDS)


def fan_lv_yi_se(ctx: Ctx) -> bool:
    return _all_tiles_in(ctx, GREEN_TILES)


def fan_jiu_lian(ctx: Ctx) -> bool:
    if ctx.melds or ctx.special:
        return False
    suit = _same_suit(ctx)
    if suit is None:
        return False
    c = [ctx.all_counts[suit * 9 + k] for k in range(9)]
    return (c[0] >= 3 and c[8] >= 3 and all(c[k] >= 1 for k in range(1, 8))
            and sum(c) >= 14)


def fan_qing_yao_jiu(ctx: Ctx) -> bool:
    # ★ 七对（含 4 张同牌）里「事实上存在清幺九」，《问答》71 牌例 2 明确允许另加计 64 分；
    #   其余牌型仍要求四副刻子。
    if ctx.has_honor:
        return False
    if not (ctx.tag in ("七对", "连七对") or ctx.all_sets_triplets):
        return False
    return all(num_of(i) in (1, 9) for i in range(34) if ctx.all_counts[i])


def fan_xiao_si_xi(ctx: Ctx) -> bool:
    winds3 = sum(1 for w in WIND_IDS if ctx.all_counts[w] >= 3)
    return winds3 >= 3 and ctx.pair in WIND_IDS


def fan_xiao_san_yuan(ctx: Ctx) -> bool:
    d3 = sum(1 for d in DRAGON_IDS if ctx.all_counts[d] >= 3)
    return d3 >= 2 and ctx.pair in DRAGON_IDS


def fan_zi_yi_se(ctx: Ctx) -> bool:
    return _all_tiles_in(ctx, ALL_HONORS)


def fan_si_an_ke(ctx: Ctx) -> bool:
    return ctx.all_sets_triplets and ctx.concealed_triplets == 4


def fan_san_an_ke(ctx: Ctx) -> bool:
    return ctx.concealed_triplets >= 3


def fan_shuang_an_ke(ctx: Ctx) -> bool:
    return ctx.concealed_triplets == 2


def fan_yi_se_shuang_long(ctx: Ctx) -> bool:
    """一色双龙会：同花色 123、123、789、789 加 5 作将"""
    suit = _same_suit(ctx)
    if suit is None or ctx.pair < 0:
        return False
    if not is_suit(ctx.pair) or suit_of(ctx.pair) != suit or num_of(ctx.pair) != 5:
        return False
    if len(ctx.sets) != 4:
        return False
    for k in (1, 7):
        n = sum(1 for s in ctx.sets
                if s.kind == "chi" and suit_of(s.tile) == suit
                and num_of(s.tile) == k)
        if n < 2:
            return False
    return True


def fan_yi_se_si_tong_shun(ctx: Ctx) -> bool:
    return any(v >= 4 for v in ctx.chow_groups().values())


def fan_yi_se_san_tong_shun(ctx: Ctx) -> bool:
    return any(v >= 3 for v in ctx.chow_groups().values())


def _step_ke(ctx: Ctx, count: int) -> bool:
    """同花色 count 个依次递增一位数的刻子"""
    for suit in (0, 1, 2):
        nums = sorted(num_of(s.tile) for s in ctx.sets
                      if s.is_triplet and is_suit(s.tile) and suit_of(s.tile) == suit)
        if len(nums) >= count:
            for i in range(len(nums) - count + 1):
                if nums[i + count - 1] - nums[i] == count - 1:
                    return True
            # 含重复数字的情况：先按集合处理
            u = sorted(set(nums))
            if len(u) >= count:
                for i in range(len(u) - count + 1):
                    if u[i + count - 1] - u[i] == count - 1:
                        return True
    return False


def fan_yi_se_si_jie_gao(ctx: Ctx) -> bool:
    return _step_ke(ctx, 4)


def fan_yi_se_san_jie_gao(ctx: Ctx) -> bool:
    return _step_ke(ctx, 3)


def _step_shun(ctx: Ctx, count: int, steps) -> bool:
    """同花色 count 个顺子，起始数字公差落在 steps"""
    for suit in (0, 1, 2):
        nums = sorted(num_of(s.tile) for s in ctx.sets
                      if s.kind == "chi" and suit_of(s.tile) == suit)
        if len(nums) >= count and _step_series(nums, count, steps):
            return True
    return False


def fan_yi_se_si_bu_gao(ctx: Ctx) -> bool:
    return _step_shun(ctx, 4, (1, 2))


def fan_yi_se_san_bu_gao(ctx: Ctx) -> bool:
    return _step_shun(ctx, 3, (1, 2))


def fan_hun_yao_jiu(ctx: Ctx) -> bool:
    # ★ 七对里「事实上存在混幺九」，《问答》71 牌例 6 明确允许另加计 32 分
    if not (ctx.tag in ("七对", "连七对") or ctx.all_sets_triplets):
        return False
    if not any(ctx.all_counts[i] for i in HONOR_IDS):
        return False
    return all(is_terminal_or_honor(i) for i in range(34) if ctx.all_counts[i])


def fan_quan_shuang_ke(ctx: Ctx) -> bool:
    if not ctx.all_sets_triplets or ctx.has_honor:
        return False
    return all(num_of(i) in (2, 4, 6, 8) for i in range(34) if ctx.all_counts[i])


def fan_qing_yi_se(ctx: Ctx) -> bool:
    return _same_suit(ctx) is not None


def fan_quan_da(ctx: Ctx) -> bool:
    return not ctx.has_honor and _nums_within(ctx, 7, 9)


def fan_quan_zhong(ctx: Ctx) -> bool:
    return not ctx.has_honor and _nums_within(ctx, 4, 6)


def fan_quan_xiao(ctx: Ctx) -> bool:
    return not ctx.has_honor and _nums_within(ctx, 1, 3)


def fan_qing_long(ctx: Ctx) -> bool:
    """同花色 1~9 相连（123+456+789）"""
    for suit in (0, 1, 2):
        st = {num_of(s.tile) for s in ctx.sets
              if s.kind == "chi" and suit_of(s.tile) == suit}
        if {1, 4, 7} <= st:
            return True
    return False


def fan_hua_long(ctx: Ctx) -> bool:
    """花龙：三种花色分别有 123 / 456 / 789（花色与起始数字构成双射）"""
    chows = {(suit_of(s.tile), num_of(s.tile)) for s in ctx.sets if s.kind == "chi"}
    for perm in itertools.permutations((1, 4, 7)):
        if all((suit, perm[suit]) in chows for suit in (0, 1, 2)):
            return True
    return False


def fan_san_se_shuang_long(ctx: Ctx) -> bool:
    if ctx.pair < 0 or not is_suit(ctx.pair) or num_of(ctx.pair) != 5:
        return False
    pair_suit = suit_of(ctx.pair)
    others = [s for s in (0, 1, 2) if s != pair_suit]
    if len(others) != 2:
        return False
    chows = {(suit_of(s.tile), num_of(s.tile)) for s in ctx.sets if s.kind == "chi"}
    return all((su, n) in chows for su in others for n in (1, 7))


def fan_quan_dai_wu(ctx: Ctx) -> bool:
    if ctx.pair < 0 or num_of(ctx.pair) != 5 or not is_suit(ctx.pair):
        return False
    for s in ctx.sets:
        if s.kind == "chi":
            if not (num_of(s.tile) <= 5 <= num_of(s.tile) + 2):
                return False
        else:
            if num_of(s.tile) != 5 or not is_suit(s.tile):
                return False
    return True


def fan_san_tong_ke(ctx: Ctx) -> bool:
    return any(len(v) >= 3 for v in ctx.triplet_nums().values())


def fan_san_feng_ke(ctx: Ctx) -> bool:
    return sum(1 for w in WIND_IDS if any(
        s.is_triplet and s.tile == w for s in ctx.sets)) >= 3


def fan_tui_bu_dao(ctx: Ctx) -> bool:
    return _all_tiles_in(ctx, PUSHABLE_TILES)


def fan_san_se_san_tong_shun(ctx: Ctx) -> bool:
    """三色三同顺：三种花色的同一数字顺子各一副"""
    for n in range(1, 8):
        suits = {suit_of(s.tile) for s in ctx.sets
                 if s.kind == "chi" and num_of(s.tile) == n}
        if len(suits) >= 3:
            return True
    return False


def fan_san_se_san_jie_gao(ctx: Ctx) -> bool:
    """三色三节高：三种花色各一副刻子，数字依次递增一位"""
    per = ctx.triplet_nums()
    for start in range(1, 8):
        if not all(start + k in per and per[start + k] for k in range(3)):
            continue
        # 必须能选出 3 种互不相同的花色（不能用「并集≥3」代替）
        for perm in itertools.permutations((0, 1, 2)):
            if all(perm[k] in per[start + k] for k in range(3)):
                return True
    return False


def fan_san_se_san_bu_gao(ctx: Ctx) -> bool:
    for start in range(1, 8):
        if all(any(s.kind == "chi" and num_of(s.tile) == start + k for s in ctx.sets)
               for k in range(3)):
            suits = [set(suit_of(s2.tile) for s2 in ctx.sets
                         if s2.kind == "chi" and num_of(s2.tile) == start + k)
                     for k in range(3)]
            pool = {frozenset(x) for x in itertools.product(*suits)}
            for c in pool:
                if len(set(c)) == 3:
                    return True
    return False


def fan_peng_peng_he(ctx: Ctx) -> bool:
    return ctx.all_sets_triplets


def fan_hun_yi_se(ctx: Ctx) -> bool:
    return _one_number_suit(ctx) is not None and ctx.has_honor


def fan_wu_men_qi(ctx: Ctx) -> bool:
    s = ctx.suits_present
    return {0, 1, 2} <= s and 3 in s and 4 in s


def fan_quan_qiu_ren(ctx: Ctx) -> bool:
    return ctx.all_sets_exposed and not ctx.opts.tsumo and ctx.single_wait


def fan_shuang_an_gang(ctx: Ctx) -> bool:
    return ctx.concealed_kongs == 2 and ctx.kong_count == 2


def fan_shuang_jian_ke(ctx: Ctx) -> bool:
    return sum(1 for d in DRAGON_IDS if any(
        s.is_triplet and s.tile == d for s in ctx.sets)) >= 2


def fan_quan_dai_yao(ctx: Ctx) -> bool:
    if ctx.special or ctx.pair < 0 or not is_terminal_or_honor(ctx.pair):
        return False
    for s in ctx.sets:
        if not any(is_terminal_or_honor(t) for t in s.tiles):
            return False
    return True


def fan_bu_qiu_ren(ctx: Ctx) -> bool:
    return ctx.no_exposed and ctx.opts.tsumo


def fan_shuang_ming_gang(ctx: Ctx) -> bool:
    return ctx.exposed_kongs == 2 and ctx.kong_count == 2


def fan_jian_ke(ctx: Ctx) -> bool:
    return any(s.is_triplet and s.tile in DRAGON_IDS for s in ctx.sets)


def fan_quan_feng_ke(ctx: Ctx) -> bool:
    return any(s.is_triplet and s.tile == ctx.round_wind_id() for s in ctx.sets)


def fan_men_feng_ke(ctx: Ctx) -> bool:
    return any(s.is_triplet and s.tile == ctx.seat_wind_id() for s in ctx.sets)


def fan_men_qian_qing(ctx: Ctx) -> bool:
    return ctx.no_exposed and not ctx.opts.tsumo


def fan_ping_he(ctx: Ctx) -> bool:
    return ctx.all_sets_chow and ctx.pair >= 0 and is_suit(ctx.pair)


def fan_si_gui_yi(ctx: Ctx) -> bool:
    return _count_si_gui_yi(ctx) > 0


def _count_si_gui_yi(ctx: Ctx) -> int:
    """四归一副数：某张牌共 4 张且未作杠"""
    if ctx.special:
        return 0
    kong_tiles = {s.tile for s in ctx.sets if s.is_kong}
    n = 0
    for i in range(34):
        if ctx.all_counts[i] == 4 and i not in kong_tiles:
            n += 1
    return n


def _count_yi_ban_gao(ctx: Ctx) -> int:
    """一般高副数：同花色同起始的顺子两两组合（套算一次原则 → n-1）"""
    if ctx.special:
        return 0
    n = 0
    for v in ctx.chow_groups().values():
        if v >= 2:
            n += v - 1
    return n


def _count_xi_xiang_feng(ctx: Ctx) -> int:
    """喜相逢副数：不同花色、相同起始数字的顺子两两组合"""
    if ctx.special:
        return 0
    by_start: Dict[int, Set[int]] = {}
    for s in ctx.sets:
        if s.kind == "chi":
            by_start.setdefault(num_of(s.tile), set()).add(suit_of(s.tile))
    return sum(len(v) - 1 for v in by_start.values() if len(v) >= 2)


def _count_lian_liu(ctx: Ctx) -> int:
    """连六副数：同花色 6 张相连（两个相隔 3 的顺子）"""
    if ctx.special:
        return 0
    n = 0
    for suit in (0, 1, 2):
        starts = {num_of(s.tile) for s in ctx.sets
                  if s.kind == "chi" and suit_of(s.tile) == suit}
        n += sum(1 for i in (1, 2, 3, 4) if i in starts and i + 3 in starts)
    return n


def _count_lao_shao_fu(ctx: Ctx) -> int:
    """老少副副数：同花色 123 + 789"""
    if ctx.special:
        return 0
    n = 0
    for suit in (0, 1, 2):
        starts = {num_of(s.tile) for s in ctx.sets
                  if s.kind == "chi" and suit_of(s.tile) == suit}
        if 1 in starts and 7 in starts:
            n += 1
    return n


def _yao_jiu_covered(ctx: Ctx) -> Set[int]:
    """被更高番种「必然并存」覆盖、不再另计幺九刻的牌张"""
    cov: Set[int] = set(DRAGON_IDS)                       # 箭刻 / 双箭刻 / 三元
    if any(s.is_triplet and s.tile == ctx.round_wind_id() for s in ctx.sets):
        cov.add(ctx.round_wind_id())                      # 圈风刻
    if any(s.is_triplet and s.tile == ctx.seat_wind_id() for s in ctx.sets):
        cov.add(ctx.seat_wind_id())                       # 门风刻
    wind3 = sum(1 for w in WIND_IDS
                if any(s.is_triplet and s.tile == w for s in ctx.sets))
    if wind3 >= 3 or _all_tiles_in(ctx, ALL_HONORS):
        cov |= set(WIND_IDS)                              # 三风刻 / 四喜 / 字一色
    if fan_hun_yao_jiu(ctx):
        cov |= {i for i in range(34) if ctx.all_counts[i]}   # 混幺九：必然并存
    if fan_jiu_lian(ctx):
        suit = _same_suit(ctx)
        if suit is not None:
            cov |= {suit * 9, suit * 9 + 8}               # 九莲宝灯
    return cov


def _count_yao_jiu_ke(ctx: Ctx, excluded_ids: Set[int]) -> int:
    """幺九刻副数（逐个实例计：1/9 与字牌的刻子各 1 分）"""
    if ctx.special:
        return 0
    n = 0
    for s in ctx.sets:
        if s.is_triplet and is_terminal_or_honor(s.tile) and s.tile not in excluded_ids:
            n += 1
    return n


def _count_shuang_tong_ke(ctx: Ctx) -> int:
    """双同刻副数：同数字、不同花色的刻子组合"""
    if ctx.special:
        return 0
    return sum(len(set(v)) - 1 for v in ctx.triplet_nums().values() if len(set(v)) >= 2)


def wait_shape(ctx: Ctx) -> Optional[str]:
    """判断和张是以什么方式成和的：'边张' / '坎张' / '单钓将' / None

    《规则》补充：1233 和 3、7789 和 7 均算边张，4556 和 5 算坎张，
    所以先看顺子、再看将牌（对倒听牌不算坎张，已在 single_wait 处限制）。
    """
    if ctx.special:
        return None
    for s in ctx.sets:
        if s.kind == "chi" and ctx.win_tile in s.tiles:
            start, win = num_of(s.tile), num_of(ctx.win_tile)
            if win == start + 1:
                return "坎张"
            if start == 1 and win == 3:
                return "边张"
            if start == 7 and win == 7:
                return "边张"
            break
    if ctx.pair == ctx.win_tile and ctx.all_counts[ctx.win_tile] >= 2:
        return "单钓将"
    return None


# ---------------------------------------------------------------- 番种汇总

# 《问答》补充的「不计」项（规则 JSON 的 `不计` 字段之外的必然并存 / 官方答复）
# 注意：凡「必然并存」的番种都不再重复计分；但像「幺九刻 / 四归一 / 一般高」这类
# 可多次成立的番种，不在这里整项删除（改由计数函数按实例处理）。
EXTRA_EXCLUDES: Dict[str, List[str]] = {
    "四暗刻": ["不求人", "三暗刻", "双暗刻"],
    "三暗刻": ["双暗刻"],
    "四杠": ["三杠", "双明杠", "双暗杠", "明杠", "暗杠"],
    "十三幺": ["全带幺", "单钓将", "门前清"],
    "连七对": ["七对", "清一色", "不求人", "门前清", "单钓将", "一般高", "连六", "无字"],
    "七对": ["四归一"],
    "九莲宝灯": ["幺九刻", "无字"],
    "清幺九": ["双同刻", "三同刻", "全带幺"],
    "字一色": ["幺九刻", "混幺九", "全带幺"],
    "混幺九": ["全带幺"],
    "一色四同顺": ["一色三节高", "连六", "喜相逢"],
    "一色四节高": ["一色三同顺", "双同刻", "三同刻"],
    "一色三节高": ["双同刻", "三同刻"],
    "大四喜": ["三风刻", "小四喜"],
    "小四喜": ["三风刻"],
    "大三元": ["小三元", "双箭刻"],
    "小三元": ["双箭刻"],
    "全不靠": ["门前清", "单钓将"],
    "七星不靠": ["全不靠", "门前清", "单钓将"],
    "不求人": ["自摸"],
    "推不倒": ["缺一门"],
    "混一色": ["缺一门"],
    "清一色": ["缺一门", "混一色"],
    "全带五": ["无字", "全带幺"],
    "全双刻": ["无字", "幺九刻"],
    "全大": ["断幺"],
    "全中": [],
    "全小": ["断幺"],
    "大于五": ["断幺"],
    "小于五": ["断幺"],
    "清龙": ["老少副", "喜相逢"],
    "花龙": ["喜相逢"],
    "一色四步高": ["一色三步高", "连六", "老少副"],
    "一色三步高": ["连六", "老少副"],
    "妙手回春": ["自摸"],
    "杠上开花": ["自摸"],
    "抢杠和": ["和绝张"],
    "全求人": ["单钓将"],
    "双暗杠": ["双暗刻", "暗杠"],
    "双明杠": ["明杠"],
    "一色双龙会": ["平和", "七对", "一般高", "老少副"],
    "三色双龙会": ["平和"],
    "平和": ["无字"],
    "断幺": ["无字"],
    "碰碰和": [],
}

# 「不计」项中被认为仍成立的番种（按实例单独计算，不做整项删除）
EXCLUDE_KEEP: Set[str] = {"幺九刻"}

# 明确指出「不计某项」但《问答》（1999 年座谈会精神）要求另加计的组合
EXCLUDE_DROP: Set[Tuple[str, str]] = {("三杠", "双暗杠")}


def collect_fans(ctx: Ctx) -> Dict[str, int]:
    """按《规则》算出一手牌命中的全部番种（尚未做排除处理）"""
    f: Dict[str, int] = {}
    o = ctx.opts

    def put(name: str, value: int) -> None:
        if name in f:
            f[name] = max(f[name], value)
        else:
            f[name] = value

    # ---------- 特殊牌型 ----------
    if ctx.tag == "十三幺":
        put("十三幺", 88)
    elif ctx.tag == "连七对":
        put("连七对", 88)
    elif ctx.tag == "七对":
        put("七对", 24)
    elif ctx.tag == "七星不靠":
        put("七星不靠", 24)
    elif ctx.tag == "全不靠":
        put("全不靠", 12)
    if ctx.d.long_dragon and ctx.tag != "七星不靠":
        put("组合龙", 12)

    # ---------- 88 番 ----------
    if fan_da_si_xi(ctx):
        put("大四喜", 88)
    if fan_da_san_yuan(ctx):
        put("大三元", 88)
    if fan_lv_yi_se(ctx):
        put("绿一色", 88)
    if fan_jiu_lian(ctx):
        put("九莲宝灯", 88)
    if ctx.kong_count >= 4:
        put("四杠", 88)

    # ---------- 64 番 ----------
    if fan_qing_yao_jiu(ctx):
        put("清幺九", 64)
    if fan_xiao_si_xi(ctx):
        put("小四喜", 64)
    if fan_xiao_san_yuan(ctx):
        put("小三元", 64)
    if fan_zi_yi_se(ctx):
        put("字一色", 64)
    if fan_si_an_ke(ctx):
        put("四暗刻", 64)
    if fan_yi_se_shuang_long(ctx):
        put("一色双龙会", 64)

    # ---------- 48 番 ----------
    if fan_yi_se_si_tong_shun(ctx):
        put("一色四同顺", 48)
    if fan_yi_se_si_jie_gao(ctx):
        put("一色四节高", 48)

    # ---------- 32 番 ----------
    if fan_yi_se_si_bu_gao(ctx):
        put("一色四步高", 32)
    if ctx.kong_count == 3:
        put("三杠", 32)
    if fan_hun_yao_jiu(ctx):
        put("混幺九", 32)

    # ---------- 24 番 ----------
    if fan_quan_shuang_ke(ctx):
        put("全双刻", 24)
    if fan_qing_yi_se(ctx):
        put("清一色", 24)
    if fan_yi_se_san_tong_shun(ctx):
        put("一色三同顺", 24)
    if fan_yi_se_san_jie_gao(ctx):
        put("一色三节高", 24)
    if fan_quan_da(ctx):
        put("全大", 24)
    if fan_quan_zhong(ctx):
        put("全中", 24)
    if fan_quan_xiao(ctx):
        put("全小", 24)

    # ---------- 16 番 ----------
    if fan_qing_long(ctx):
        put("清龙", 16)
    if fan_san_se_shuang_long(ctx):
        put("三色双龙会", 16)
    if fan_yi_se_san_bu_gao(ctx):
        put("一色三步高", 16)
    if fan_quan_dai_wu(ctx):
        put("全带五", 16)
    if fan_san_tong_ke(ctx):
        put("三同刻", 16)
    if fan_san_an_ke(ctx):
        put("三暗刻", 16)

    # ---------- 12 番 ----------
    if not ctx.has_honor and _nums_within(ctx, 6, 9) and \
            any(num_of(i) == 6 for i in range(34) if ctx.all_counts[i]):
        put("大于五", 12)
    if not ctx.has_honor and _nums_within(ctx, 1, 4) and \
            any(num_of(i) == 4 for i in range(34) if ctx.all_counts[i]):
        put("小于五", 12)
    if fan_san_feng_ke(ctx):
        put("三风刻", 12)

    # ---------- 8 番 ----------
    if fan_hua_long(ctx):
        put("花龙", 8)
    if fan_tui_bu_dao(ctx):
        put("推不倒", 8)
    if fan_san_se_san_tong_shun(ctx):
        put("三色三同顺", 8)
    if fan_san_se_san_jie_gao(ctx):
        put("三色三节高", 8)
    if o.last_draw:
        put("妙手回春", 8)
    if o.last_discard:
        put("海底捞月", 8)
    if o.kong_bloom:
        put("杠上开花", 8)
    if o.rob_kong:
        put("抢杠和", 8)

    # ---------- 6 番 ----------
    if fan_peng_peng_he(ctx):
        put("碰碰和", 6)
    if fan_hun_yi_se(ctx):
        put("混一色", 6)
    if fan_san_se_san_bu_gao(ctx):
        put("三色三步高", 6)
    if fan_wu_men_qi(ctx):
        put("五门齐", 6)
    if fan_quan_qiu_ren(ctx):
        put("全求人", 6)
    if fan_shuang_an_gang(ctx):
        put("双暗杠", 6)
    if fan_shuang_jian_ke(ctx):
        put("双箭刻", 6)

    # ---------- 4 番 ----------
    if fan_quan_dai_yao(ctx):
        put("全带幺", 4)
    if fan_bu_qiu_ren(ctx):
        put("不求人", 4)
    if fan_shuang_ming_gang(ctx):
        put("双明杠", 4)
    if o.last_tile:
        put("和绝张", 4)

    # ---------- 2 番 ----------
    jian_ke = sum(1 for d in DRAGON_IDS if any(
        s.is_triplet and s.tile == d for s in ctx.sets))
    if jian_ke == 1:
        put("箭刻", 2)
    if fan_quan_feng_ke(ctx):
        put("圈风刻", 2)
    if fan_men_feng_ke(ctx):
        put("门风刻", 2)
    if fan_men_qian_qing(ctx):
        put("门前清", 2)
    if fan_ping_he(ctx):
        put("平和", 2)
    n_si = _count_si_gui_yi(ctx)
    if n_si:
        put("四归一", 2 * n_si)
    n_shuang_tong = _count_shuang_tong_ke(ctx)
    if n_shuang_tong and not fan_san_tong_ke(ctx):
        put("双同刻", 2 * n_shuang_tong)
    if fan_shuang_an_ke(ctx):
        put("双暗刻", 2)
    if ctx.concealed_kongs == 1 and ctx.kong_count == 1:
        put("暗杠", 2)
    if not ctx.has_honor and not any(num_of(i) in (1, 9)
                                     for i in range(34) if ctx.all_counts[i]):
        put("断幺", 2)

    # ---------- 1 番 ----------
    n_ybg = _count_yi_ban_gao(ctx)
    if n_ybg:
        put("一般高", n_ybg)
    n_xxf = _count_xi_xiang_feng(ctx)
    if n_xxf:
        put("喜相逢", n_xxf)
    n_ll = _count_lian_liu(ctx)
    if n_ll:
        put("连六", n_ll)
    n_lsf = _count_lao_shao_fu(ctx)
    if n_lsf:
        put("老少副", n_lsf)

    excluded = _yao_jiu_covered(ctx)
    n_yao = _count_yao_jiu_ke(ctx, excluded)
    if n_yao:
        put("幺九刻", n_yao)

    # 杠（依《问答》第 41 条：明杠1 / 暗杠2 / 双明杠4 / 一明一暗6 / 双暗杠6）
    kc, ck, ek = ctx.kong_count, ctx.concealed_kongs, ctx.exposed_kongs
    if kc == 1:
        if ck:
            put("暗杠", 2)
        else:
            put("明杠", 1)
    elif kc == 2:
        if ck == 1 and ek == 1:
            put("双明杠", 4)
            put("暗杠", 2)
    elif kc == 3:
        if ck == 1:
            put("暗杠", 2)
        elif ck == 2:
            put("双暗杠", 6)
    suits = ctx.suits_present & {0, 1, 2}
    if len(suits) == 2:
        put("缺一门", 1)
    if not ctx.has_honor:
        put("无字", 1)
    if ctx.single_wait:
        shape = wait_shape(ctx)
        if shape:
            put(shape, 1)
    if o.tsumo:
        put("自摸", 1)

    return f


# ---------------------------------------------------------------- 主类


class MahjongFanCalculator:
    """国标麻将算番器

    兼容旧接口（calculate_fan / is_winning_hand / get_possible_winning_tiles），
    并新增面向 GUI 的 score / winning_tiles / waiting_tiles。
    """

    RULES_FILE = "国标麻将标准规则.json"

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = rules_path or self._find_rules()
        self.rules: Dict[str, object] = {}
        self.fan_values: Dict[str, int] = fan_value_map(DEFAULT_FAN_TABLE)
        self.excludes: Dict[str, List[str]] = {k: list(v) for k, v in DEFAULT_EXCLUDES.items()}
        self._load_rules()

    # ---------- 规则装载 ----------
    @classmethod
    def _find_rules(cls) -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        cand = [os.path.join(here, cls.RULES_FILE),
                os.path.join(os.getcwd(), cls.RULES_FILE)]
        for p in cand:
            if os.path.exists(p):
                return p
        return cand[0]

    def _load_rules(self) -> None:
        try:
            with open(self.rules_path, encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception:
            return
        self.rules = data
        table = data.get("番种") or {}
        values: Dict[str, int] = {}
        for key, items in table.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not name:
                    continue
                values[name] = int(item.get("fan", 0) or 0)
                ex = item.get("不计") or []
                if ex:
                    self.excludes.setdefault(name, [])
                    self.excludes[name] = list(dict.fromkeys(
                        list(self.excludes[name]) + list(ex)))
        if values:
            self.fan_values = values
        self.fan_values.setdefault("花牌", 1)
        # 合并《问答》补充的排除项
        for name, extra in EXTRA_EXCLUDES.items():
            cur = self.excludes.setdefault(name, [])
            self.excludes[name] = list(dict.fromkeys(list(cur) + list(extra)))

    # ---------- 排除处理 ----------
    def handle_exclusions(self, fans: Dict[str, int]) -> Dict[str, int]:
        """按「不计」表剔除被更高分番种覆盖的番种"""
        out = dict(fans)
        changed = True
        while changed:
            changed = False
            for name in sorted(out, key=lambda n: -out[n]):
                if name not in out:
                    continue
                for bad in self.excludes.get(name, []):
                    if bad in EXCLUDE_KEEP or bad not in out:
                        continue
                    if (name, bad) in EXCLUDE_DROP:
                        continue
                    out.pop(bad)
                    changed = True
        return out

    # ---------- 听牌 ----------
    def waiting_tiles(self, melds: Sequence[Meld],
                      concealed: Sequence[int]) -> List[int]:
        """返回暗手牌（应有 13 - 3m 张）的听牌集合

        用「快速布尔判定」代替建对象式分解（结论一致，快约一个数量级），
        另带七对 / 十三幺 / 全不靠 / 组合龙 的快速判定。
        """
        need = 4 - len(melds)
        cnt = counts_of(concealed)
        out: List[int] = []
        for t in range(34):
            if cnt[t] >= 4:
                continue
            cnt[t] += 1
            ok = _shape_win(cnt, need)
            if not ok and need == 4:
                ok = _special_win_quick(cnt) or _long_dragon_win(cnt)
            cnt[t] -= 1
            if ok:
                out.append(t)
        return out

    # ---------- 核心算番 ----------
    def score(self, melds: Sequence[Meld], concealed: Sequence[int],
              win_tile: Optional[int] = None,
              opts: Optional[Options] = None) -> Score:
        opts = opts or Options()
        melds = list(melds)
        concealed = list(concealed)
        # ★ 张数先校验（否则「张数不足」会被误报成「牌型不能和牌」）
        want = 14 - 3 * len(melds)
        if len(concealed) != want:
            s = Score()
            s.message = "手牌张数不足，无法算番（当前 %d 张，应为 %d 张）" % (
                len(concealed), want)
            return s
        if win_tile is None:
            win_tile = concealed[-1]

        if win_tile not in concealed:
            s = Score()
            s.message = "和张不在手牌中"
            return s

        # 合法性：每种牌不超过 4 张
        total = counts_of(concealed)
        for m in melds:
            for t in m.tiles:
                total[t] += 1
        if any(c > 4 for c in total):
            s = Score()
            s.message = "有牌超过 4 张，请检查输入"
            return s

        decs = decompositions(concealed, melds)
        if not decs:
            s = Score()
            s.message = "牌型不能和牌"
            return s

        # 和牌前的手牌 → 判断是否单听（边/坎/钓 只在单听时计）
        pre = list(concealed)
        pre.remove(win_tile)
        waits = self.waiting_tiles(melds, pre)
        single = len(waits) == 1

        best: Optional[Score] = None
        for d in decs:
            ctx = Ctx(d=d, melds=melds,
                      concealed_counts=counts_of(concealed),
                      all_counts=total,
                      win_tile=win_tile, opts=opts, single_wait=single)
            fans = collect_fans(ctx)
            fans = self.handle_exclusions(fans)
            base = sum(fans.values())
            if base == 0:
                fans = {"无番和": 8}
                base = 8
            flowers = max(0, int(opts.flowers or 0))
            total_fan = base + flowers * self.fan_values.get("花牌", 1)
            res = Score(
                fans=sorted(fans.items(), key=lambda kv: (-kv[1], kv[0])) +
                     ([("花牌", flowers * self.fan_values.get("花牌", 1))]
                      if flowers else []),
                total=total_fan, base=base, flowers=flowers,
                ok=base >= 8,
                pattern=(d.tag or ("组合龙" if d.long_dragon else "基本牌型")),
            )
            if best is None or res.total > best.total:
                best = res
        assert best is not None
        if not best.ok:
            best.message = "番种合计 %d 分，未达 8 分起和标准" % best.base
        return best

    def winning_tiles(self, melds: Sequence[Meld], concealed: Sequence[int],
                      opts: Optional[Options] = None) -> List[Tuple[int, Score]]:
        """听牌分析：返回 [(牌, Score)]（按总番降序）"""
        opts = opts or Options()
        out: List[Tuple[int, Score]] = []
        for t in self.waiting_tiles(melds, concealed):
            s = self.score(melds, list(concealed) + [t], t, opts)
            if s.ok:
                out.append((t, s))
        out.sort(key=lambda kv: -kv[1].total)
        return out

    # ---------- 旧接口兼容 ----------
    def calculate_fan(self, tiles: Sequence[str], hand_config: Optional[dict] = None) -> Dict[str, int]:
        """兼容旧签名：tiles 为 14 张牌代码（如 'W1'），返回 {番种: 番数}"""
        cfg = dict(hand_config or {})
        opts = Options(
            tsumo=bool(cfg.get("tsumo")) or ("自摸" in (cfg.get("special_fans") or [])),
            last_tile="和绝张" in (cfg.get("special_fans") or []),
            rob_kong="抢杠和" in (cfg.get("special_fans") or []),
            last_discard="海底捞月" in (cfg.get("special_fans") or []),
            kong_bloom="杠上开花" in (cfg.get("special_fans") or []),
            last_draw="妙手回春" in (cfg.get("special_fans") or []),
            round_wind=cfg.get("round_wind") or "东",
            seat_wind=cfg.get("seat_wind") or "东",
            flowers=int(cfg.get("flowers") or 0),
        )
        ids = [tile_of(t) for t in tiles if t in TILE_CODES]
        if len(ids) != 14:
            return {}
        s = self.score([], ids, ids[-1], opts)
        return s.fan_map

    def is_winning_hand(self, tiles: Sequence[str]) -> bool:
        ids = [tile_of(t) for t in tiles if t in TILE_CODES]
        if len(ids) != 14:
            return False
        return bool(decompositions(ids, []))

    def get_possible_winning_tiles(self, tiles: Sequence[str]) -> List[Tuple[str, Dict[str, int]]]:
        ids = [tile_of(t) for t in tiles if t in TILE_CODES]
        if len(ids) != 13:
            return []
        out = []
        for t, s in self.winning_tiles([], ids):
            out.append((code_of(t), s.fan_map))
        return out

    # ---------- 供「番表」页使用 ----------
    def fan_table(self) -> List[Tuple[int, List[Tuple[str, str]]]]:
        """返回 [(分值, [(番种名, 定义)])]，按分值降序"""
        table = (self.rules.get("番种") or {}) if isinstance(self.rules, dict) else {}
        rows: List[Tuple[int, List[Tuple[str, str]]]] = []
        if table:
            for key, items in table.items():
                try:
                    value = int(str(key).replace("分", ""))
                except ValueError:
                    continue
                rows.append((value, [(it.get("name", ""),
                                      (it.get("definition") or "") +
                                      ("（不计：%s）" % "、".join(it.get("不计") or [])
                                       if it.get("不计") else ""))
                                     for it in items if isinstance(it, dict)]))
            rows.sort(key=lambda r: -r[0])
        if not rows:
            for value in sorted(DEFAULT_FAN_TABLE, reverse=True):
                rows.append((value, [(n, "") for n in DEFAULT_FAN_TABLE[value]]))
        return rows


# ================================================================ 命令行 / 进程内调用
#
# ★ v2.6.0：别的程序（Python / C# / Excel / 任何语言）要用国标算番，**不需要 HTTP、不需要端口、
#   不需要先启动谁**：两种最直接的方式——
#     ① 能 import 的：`from mahjong_core import MahjongFanCalculator`（或便捷函数 `score_hand()`）
#     ② 不能 import 的：把牌当参数丢给 exe/py（subprocess 调一次即可）——
#         Mahjong_Calculator.exe --hand "1233455677899m" --win 9m --json
#         python mahjong_core.py --hand "..." --json
#   默认输出 JSON，`--text` 输出人话；算不出和牌 → 退出码 1（JSON 里 ok=false 带 message）。

CLI_FLAGS = ("-H", "--hand", "--score", "-w", "--win", "-m", "--meld",
             "--waits", "--waits-all", "--fan-table", "--version", "--help", "-h",
             "--text", "--json")

_CLI_SUIT_BASE = {"p": 0, "s": 9, "m": 18}      # 筒/索/万 的起始 id
_CN_TO_CODE: Dict[str, str] = {name_of(i): code_of(i) for i in range(34)}


def cli_wanted(argv: Sequence[str]) -> bool:
    """命令行里是否出现了「算番用」参数（GUI 用它决定要不要开界面）"""
    for a in argv or ():
        if a in CLI_FLAGS or a.startswith("--hand=") or a.startswith("--win="):
            return True
    return False


def _cli_norm_tiles(text: str) -> List[str]:
    """把牌串解析成代码列表。支持三种写法（可混用）：
        W1 W2 W3        纯代码（空白/逗号/分号分隔）
        一万 二万 东     中文名
        123m 456s 11z   麻将常用简写（m=万 s=索 p=筒 z=字牌：1~4 东南西北 5~7 中发白）
    """
    out: List[str] = []
    for raw in re.split(r"[\s,;/|+]+", str(text or "").strip()):
        if not raw:
            continue
        m = re.fullmatch(r"([1-9]+)([mspzMSPZ])", raw)
        if m:
            digits, suit = m.group(1), m.group(2).lower()
            for ch in digits:
                n = int(ch)
                if suit == "z":
                    if n > 7:
                        raise ValueError("字牌只有 1~7（东南西北中发白），收到 %dz" % n)
                    out.append(code_of(26 + n))
                else:
                    out.append(code_of(_CLI_SUIT_BASE[suit] + n - 1))
            continue
        up = raw.upper()
        if up in TILE_CODES:
            out.append(up)
        elif raw in _CN_TO_CODE:
            out.append(_CN_TO_CODE[raw])
        else:
            raise ValueError("认不出的牌「%s」：可用 W1、一万、123m（万/索/筒）、11z（字牌）等写法" % raw)
    return out


def _cli_parse_melds(items: Sequence[str]) -> List[Meld]:
    """副露：`类型:牌`，类型 = chi / peng / kong / angang（暗杠），牌支持与 --hand 同样的写法。
        例：chi:123m    peng:111z    kong:5555z    angang:22z
    """
    melds: List[Meld] = []
    for item in items or ():
        if ":" not in str(item):
            raise ValueError("副露要写成「类型:牌」，例如 chi:123m、peng:111z、angang:22z")
        kind_raw, tiles_raw = str(item).split(":", 1)
        kind = kind_raw.strip().lower()
        ids = tuple(tile_of(c) for c in _cli_norm_tiles(tiles_raw))
        if kind in ("chi", "吃"):
            if len(ids) != 3:
                raise ValueError("吃（chi）要 3 张，收到 %d 张" % len(ids))
            melds.append(Meld("chi", tuple(sorted(ids))))
        elif kind in ("peng", "pong", "碰"):
            if len(ids) != 3 or len(set(ids)) != 1:
                raise ValueError("碰（peng）要 3 张同牌")
            melds.append(Meld("pong", ids))
        elif kind in ("kong", "gang", "杠", "minggang", "明杠"):
            if len(ids) != 4 or len(set(ids)) != 1:
                raise ValueError("杠（kong）要 4 张同牌")
            melds.append(Meld("kong", ids, False))
        elif kind in ("angang", "concealed", "暗杠"):
            if len(ids) != 4 or len(set(ids)) != 1:
                raise ValueError("暗杠（angang）要 4 张同牌")
            melds.append(Meld("kong", ids, True))
        else:
            raise ValueError("副露类型只支持 chi / peng / kong / angang，收到「%s」" % kind_raw.strip())
    return melds


def score_hand(hand, win=None, melds=None, **opts) -> Dict[str, object]:
    """一行算番（给 import 用；返回 JSON 友好的 dict）

        hand  : 整手牌（含和张），字符串或列表；"W1 W2 ..." / "123m" / ["W1", ...]
        win   : 和张（可省，默认取 hand 最后一张）
        melds : 副露；字符串（"chi:123m" 或 "chi:123m peng:111z"）或 Meld 列表
        opts  : tsumo / last_tile / rob_kong / kong_bloom / last_draw / last_discard /
                round_wind / seat_wind / flowers
    返回：{"ok": bool, "total": int, "base": int, "fans": [{"name","fan"}], ...}
    """
    if isinstance(hand, str):
        hand = _cli_norm_tiles(hand)
    if isinstance(win, str):
        _w = _cli_norm_tiles(win)          # win 也允许 "9m" / "九万" 写法
        win = _w[0] if _w else None
    if isinstance(melds, str):
        melds = _cli_parse_melds(re.split(r"[\s,;]+", melds.strip())) if melds.strip() else []
    return score_codes(list(hand or []), win=win, melds=melds, **opts)


def score_codes(codes: Sequence[str], win=None, melds=None, **opts) -> Dict[str, object]:
    """与 `score_hand` 相同，但输入已经是牌代码列表"""
    calc = MahjongFanCalculator()
    ids = [tile_of(c) for c in codes]
    if win:
        win_id = tile_of(win) if isinstance(win, str) else int(win)
    else:
        win_id = ids[-1] if ids else None
    mels = list(melds or [])
    options = Options(
        tsumo=bool(opts.get("tsumo")),
        last_tile=bool(opts.get("last_tile")),
        rob_kong=bool(opts.get("rob_kong")),
        kong_bloom=bool(opts.get("kong_bloom")),
        last_draw=bool(opts.get("last_draw")),
        last_discard=bool(opts.get("last_discard")),
        round_wind=str(opts.get("round_wind") or "东"),
        seat_wind=str(opts.get("seat_wind") or "东"),
        flowers=int(opts.get("flowers") or 0),
    )
    need = 14 - 3 * len(mels)
    if len(ids) != need:
        return {"ok": False,
                "error": "牌数不对：%d 张，应为 %d 张（14 - 3×副露数）" % (len(ids), need)}
    if win_id is None or win_id not in ids:
        return {"ok": False, "error": "和张不在手牌里（--win 要指一手牌中的某一张）"}
    s = calc.score(mels, ids, win_id, options)
    return _score_to_dict(s)


def _score_to_dict(s: Score) -> Dict[str, object]:
    return {
        "ok": bool(s.fans),
        "total": int(s.total),
        "base": int(s.base),
        "flowers": int(s.flowers),
        "fans": [{"name": n, "fan": v} for n, v in s.fans],
        "text": s.text(),
        "pattern": s.pattern,
        "message": s.message,
    }


def _score_text(s: Score, header: str = "") -> str:
    lines = []
    if header:
        lines.append(header)
    if s.message and not s.fans:
        lines.append(s.message)
        return "\n".join(lines)
    lines.append("总番 %d（起和分 %d，花牌 %d）" % (s.total, s.base, s.flowers))
    if s.pattern:
        lines.append("牌型：%s" % s.pattern)
    lines.append("番种：")
    for n, v in s.fans:
        lines.append("  %3d  %s" % (v, n))
    if s.message:
        lines.append(s.message)
    return "\n".join(lines)


def cli_main(argv=None) -> int:
    """命令行入口。返回进程退出码：0 成功 / 1 不能和牌 / 2 参数或牌面有错。"""
    import argparse
    import sys as _sys

    # ★ 输出编码：JSON 一律用 `ensure_ascii=True`（纯 ASCII，任何语言按 UTF-8/GBK 读都不乱），
    #   而 --text / --help 有中文，所以把 stdout 尽量改成 UTF-8（改不了就算了）。
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:      # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(
        prog="mahjong_core",
        description="国标麻将算番（一次调用算完就退出：不需要 HTTP、不需要端口、不需要先启动谁）",
        epilog="例："
               "\n  mahjong_core.py --hand \"1233455677899m\" --json"
               "\n  mahjong_core.py --hand \"1112345678999m\" --win 9m --text"
               "\n  mahjong_core.py --hand \"123567m 99s 111z\" --meld kong:5555z --waits --json"
               "\n  牌写法：W1 / 一万 / 123m（万）/ 456s（索）/ 789p（筒）/ 11z（字牌:东南西北中发白）",
    )
    ap.add_argument("tiles", nargs="*", help="牌（位置参数，空格分隔）")
    ap.add_argument("-H", "--hand", default=None, help="整手牌（含和张）；与位置参数二选一")
    ap.add_argument("-w", "--win", default=None, help="和张（默认取最后一张）；支持 9m / W9 / 九万 等写法")
    ap.add_argument("-m", "--meld", action="append", default=[],
                    help="副露，可多次：chi:123m / peng:111z / kong:5555z / angang:22z")
    ap.add_argument("--waits", action="store_true", help="听牌模式（给 13−3×副露数 张，列出每张听牌与番数）")
    ap.add_argument("--waits-all", action="store_true", dest="waits_all",
                    help="听牌模式，但不筛 8 分起和分")
    ap.add_argument("--tsumo", action="store_true", help="自摸")
    ap.add_argument("--last-tile", action="store_true", dest="last_tile", help="和绝张")
    ap.add_argument("--rob-kong", action="store_true", dest="rob_kong", help="抢杠和")
    ap.add_argument("--kong-bloom", action="store_true", dest="kong_bloom", help="杠上开花")
    ap.add_argument("--last-draw", action="store_true", dest="last_draw", help="妙手回春")
    ap.add_argument("--last-discard", action="store_true", dest="last_discard", help="海底捞月")
    ap.add_argument("--round", default="东", help="圈风（东南西北），默认东")
    ap.add_argument("--seat", default="东", help="门风（东南西北），默认东")
    ap.add_argument("--flowers", type=int, default=0, help="花牌张数（每张 1 分，不计起和分）")
    ap.add_argument("--text", action="store_true", help="输出人话（默认 JSON）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（默认行为，显式写上更清楚）")
    ap.add_argument("--fan-table", action="store_true", dest="fan_table", help="输出 81 个番种表")
    ap.add_argument("--version", action="store_true", help="输出版本与引擎信息")
    args = ap.parse_args(argv)

    def out(obj, text=None):
        # ★ JSON 用 ensure_ascii=True：输出的全是 ASCII（中文写成 \uXXXX），
        #   这样 C# / Excel / 批处理怎么读都不会因编码出错；解析后仍是正常中文。
        print(text if (args.text and text)
              else json.dumps(obj, ensure_ascii=True, indent=2))

    try:
        if args.version:
            calc = MahjongFanCalculator()
            out({"ok": True, "name": "国标麻将算番器", "engine": "mahjong_core",
                 "fans": len(getattr(calc, "fan_values", {})), "tiles": len(TILE_CODES),
                 "rules": os.path.basename(getattr(calc, "rules_path", "")) or "（内置默认）"},
                "国标麻将算番器 · 引擎 mahjong_core，番种 %d，牌张 %d"
                % (len(getattr(calc, "fan_values", {})), len(TILE_CODES)))
            return 0
        if args.fan_table:
            rows = MahjongFanCalculator().fan_table()
            data = [{"value": v, "fans": [{"name": n, "definition": d} for n, d in items]}
                    for v, items in rows]
            lines = ["国标麻将番种表（%d 个番种）" % sum(len(x["fans"]) for x in data)]
            for row in data:
                lines.append("%d 分：%s" % (row["value"],
                                          "、".join(f["name"] for f in row["fans"])))
            out({"ok": True, "table": data}, "\n".join(lines))
            return 0

        hand_text = args.hand if args.hand is not None else " ".join(args.tiles)
        if not hand_text.strip():
            ap.print_help()
            return 2
        codes = _cli_norm_tiles(hand_text)
        melds = _cli_parse_melds(args.meld)
        # ★ --win 也允许 "9m"/"一万" 这种写法（统一走同一套解析）
        win_codes = _cli_norm_tiles(args.win) if args.win else []
        if len(win_codes) > 1:
            raise ValueError("--win 只能给一张牌（收到 %d 张）" % len(win_codes))
        win_code = win_codes[0] if win_codes else None
        wind_names = ("东", "南", "西", "北")
        for label, val in (("--round", args.round), ("--seat", args.seat)):
            if val not in wind_names:
                raise ValueError("%s 只能是东/南/西/北，收到「%s」" % (label, val))
        if args.waits or args.waits_all:
            calc = MahjongFanCalculator()
            ids = [tile_of(c) for c in codes]
            need = 13 - 3 * len(melds)
            if len(ids) != need:
                raise ValueError("听牌模式牌数不对：%d 张，应为 %d 张（13 - 3×副露数）" % (len(ids), need))
            options = Options(round_wind=args.round, seat_wind=args.seat,
                              flowers=int(args.flowers))
            result = calc.winning_tiles(melds, ids, options)
            only_reach = not args.waits_all
            items = []
            for tid, s in result:
                if only_reach and s.base < 8:
                    continue
                items.append({"tile": code_of(tid), "name": name_of(tid),
                              "total": int(s.total), "base": int(s.base),
                              "fans": [{"name": n, "fan": v} for n, v in s.fans],
                              "text": s.text()})
            lines = ["听牌 %d 张：" % len(items)]
            for it in items:
                lines.append("  %s（%s） %d 番：%s"
                             % (it["tile"], it["name"], it["total"], it["text"]))
            if not items:
                lines.append("  （没有达到起和分的听牌；加 --waits-all 看全部候选）")
            out({"ok": True, "count": len(items), "waits": items}, "\n".join(lines))
            return 0

        res = score_codes(codes, win=win_code, melds=melds,
                          tsumo=args.tsumo, last_tile=args.last_tile,
                          rob_kong=args.rob_kong, kong_bloom=args.kong_bloom,
                          last_draw=args.last_draw, last_discard=args.last_discard,
                          round_wind=args.round, seat_wind=args.seat,
                          flowers=int(args.flowers))
        if "error" in res:
            out({"ok": False, "error": res["error"]}, "错误：%s" % res["error"])
            return 2
        if args.text:
            calc = MahjongFanCalculator()
            ids = [tile_of(c) for c in codes]
            s = calc.score(melds, ids,
                           tile_of(win_code) if win_code else ids[-1],
                           Options(tsumo=args.tsumo, last_tile=args.last_tile,
                                   rob_kong=args.rob_kong, kong_bloom=args.kong_bloom,
                                   last_draw=args.last_draw, last_discard=args.last_discard,
                                   round_wind=args.round, seat_wind=args.seat,
                                   flowers=int(args.flowers)))
            print(_score_text(s))
        else:
            out(res)
        return 0 if res.get("ok") else 1
    except ValueError as exc:
        out({"ok": False, "error": str(exc)}, "错误：%s" % exc)
        return 2


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(cli_main(_sys.argv[1:]))


