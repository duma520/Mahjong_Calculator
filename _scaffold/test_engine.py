# -*- coding: utf-8 -*-
"""mahjong_core 算番引擎自测（不依赖 GUI）

运行：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/test_engine.py
日志写 _scaffold/_engine_out.txt（UTF-8）。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mahjong_core import (MahjongFanCalculator, Meld, Options, tile_of, name_of,  # noqa: E402
                          code_of, names_of, decompositions, counts_of)

LOG = []
PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        LOG.append("  [OK]   %s" % name)
    else:
        FAIL += 1
        LOG.append("  [FAIL] %s  %s" % (name, extra))


def T(*codes):
    return [tile_of(c) for c in codes]


def show(tag, s):
    LOG.append("  %-26s 共%d番(%s) %s"
               % (tag, s.total, s.pattern, s.text()))
    if s.message:
        LOG.append("      ! %s" % s.message)


def main():
    calc = MahjongFanCalculator()
    LOG.append("规则文件: %s" % os.path.basename(calc.rules_path))
    LOG.append("番种定义数: %d" % len(calc.fan_values))

    LOG.append("\n== 1. 九莲宝灯（1112345678999万 + 1万）==")
    hand = T("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
             "W9", "W9", "W9", "W1")
    s = calc.score([], hand, tile_of("W1"), Options(round_wind="东", seat_wind="东"))
    show("九莲宝灯", s)
    check("命中九莲宝灯88", s.fan_map.get("九莲宝灯") == 88, str(s.fan_map))
    check("命中清龙16", s.fan_map.get("清龙") == 16, str(s.fan_map))
    check("含四归一2", s.fan_map.get("四归一") == 2, str(s.fan_map))

    LOG.append("\n== 2. 九莲宝灯牌型的听牌（应听 9 张）==")
    waiting = T("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
                "W9", "W9", "W9")
    waits = calc.waiting_tiles([], waiting)
    check("听 9 张", len(waits) == 9, "实际 %d: %s" % (len(waits), names_of(waits)))
    check("九莲宝灯听牌=1~9万", set(waits) == set(T(*["W%d" % i for i in range(1, 10)])))

    LOG.append("\n== 3. 七对 ==")
    hand = T("W1", "W1", "W2", "W2", "W3", "W3", "W4", "W4",
             "W5", "W5", "W6", "W6", "J1", "J1")
    s = calc.score([], hand, hand[-1], Options())
    show("七对·混一色", s)
    check("七对24", s.fan_map.get("七对") == 24, str(s.fan_map))
    check("混一色6", s.fan_map.get("混一色") == 6, str(s.fan_map))
    check("七对不计门前清", "门前清" not in s.fan_map, str(s.fan_map))
    check("七对不计单钓将", "单钓将" not in s.fan_map, str(s.fan_map))

    LOG.append("\n== 4. 连七对 ==")
    hand = T("T3", "T3", "T4", "T4", "T5", "T5", "T6", "T6",
             "T7", "T7", "T8", "T8", "T9", "T9")
    s = calc.score([], hand, hand[-1], Options())
    show("连七对", s)
    check("连七对88", s.fan_map.get("连七对") == 88, str(s.fan_map))

    # ★ 跨花色的七对不是连七对（必须「同花色 + 序数连续」）
    hand = T("B6", "B6", "B7", "B7", "B8", "B8", "B9", "B9",
             "T1", "T1", "T2", "T2", "T3", "T3")
    s = calc.score([], hand, hand[-1], Options())
    show("跨花色·筒6~9+索1~3", s)
    check("跨花色不是连七对", "连七对" not in s.fan_map, str(s.fan_map))
    check("跨花色记为七对24", s.fan_map.get("七对") == 24, str(s.fan_map))

    hand = T("T7", "T7", "T8", "T8", "T9", "T9", "W1", "W1",
             "W2", "W2", "W3", "W3", "W4", "W4")
    s = calc.score([], hand, hand[-1], Options())
    show("跨花色·索7~9+万1~4", s)
    check("跨花色不是连七对②", "连七对" not in s.fan_map, str(s.fan_map))

    # 三个花色的真连七对都要能识别
    for suit, code in ((0, "B"), (1, "T"), (2, "W")):
        hand = T(*["%s%d" % (code, n) for n in (2, 3, 4, 5, 6, 7, 8) for _ in (0, 1)])
        s = calc.score([], hand, hand[-1], Options())
        check("连七对·%s2~%s8" % (code, code), s.fan_map.get("连七对") == 88, str(s.fan_map))
    for code in ("B", "T", "W"):
        hand = T(*["%s%d" % (code, n) for n in (3, 4, 5, 6, 7, 8, 9) for _ in (0, 1)])
        s = calc.score([], hand, hand[-1], Options())
        check("连七对·%s3~%s9" % (code, code), s.fan_map.get("连七对") == 88, str(s.fan_map))

    # ★ 4 张相同的牌算作两对（国标口径）：1111 + 5 个对子 = 七对
    hand = T("W1", "W1", "W1", "W1", "W2", "W2", "W3", "W3",
             "W4", "W4", "W5", "W5", "W6", "W6")
    s = calc.score([], hand, hand[-1], Options())
    show("七对·含四张（1 个四张）", s)
    check("含四张仍是七对", s.fan_map.get("七对") == 24, str(s.fan_map))
    check("含四张不计四归一（必然并存）", "四归一" not in s.fan_map, str(s.fan_map))

    hand = T("W1", "W1", "W1", "W1", "W2", "W2", "W2", "W2",
             "W3", "W3", "W4", "W4", "W5", "W5")
    s = calc.score([], hand, hand[-1], Options())
    show("七对·含两个四张", s)
    check("含两个四张仍是七对", s.fan_map.get("七对") == 24, str(s.fan_map))

    hand = T("B1", "B1", "B1", "B1", "B2", "B2", "B3", "B3",
             "B4", "B4", "B5", "B5", "B6", "B6")
    s = calc.score([], hand, hand[-1], Options())
    show("七对·含四张 + 清一色", s)
    check("含四张+清一色", s.fan_map.get("七对") == 24 and s.fan_map.get("清一色") == 24,
          str(s.fan_map))

    # 含四张的牌不会变成连七对（连七对必须 7 个各 2 张）
    hand = T("B1", "B1", "B1", "B1", "B2", "B2", "B3", "B3",
             "B4", "B4", "B5", "B5", "B6", "B6")
    check("含四张不判连七对", "连七对" not in s.fan_map, str(s.fan_map))

    # 4 张 + 3 张 + …（对子数不是 7）不算七对
    hand = T("W1", "W1", "W1", "W1", "W2", "W2", "W2",
             "W3", "W3", "W3", "W4", "W4", "W5", "W5")
    s = calc.score([], hand, hand[-1], Options())
    show("四张+刻子（不是七对）", s)
    check("对子数≠7 不算七对", "七对" not in s.fan_map and "连七对" not in s.fan_map,
          str(s.fan_map))

    # 听牌判定也要认「含四张的七对」（东东东东 南南 西西 北北 中中 发 → 听发）
    ting = T("F1", "F1", "F1", "F1", "F2", "F2", "F3", "F3",
             "F4", "F4", "J1", "J1", "J2")
    waits = calc.waiting_tiles([], ting)
    check("含四张的七对听牌含发", tile_of("J2") in waits, names_of(waits))
    hand = sorted(list(ting) + [tile_of("J2")])
    s = calc.score([], hand, tile_of("J2"), Options())
    show("含四张的七对·字牌", s)
    check("含四张的七对能算番", s.fan_map.get("七对") == 24, str(s.fan_map))
    check("含四张的七对另加字一色", s.fan_map.get("字一色") == 64, str(s.fan_map))

    # ★ 那 4 张必须是「留在手里」的牌：若已报明杠/暗杠（副露），就不再是七对
    concealed = T("W2", "W2", "W3", "W3", "W4", "W4", "W5", "W5", "W6", "W6", "W7")
    for kong_tag, is_concealed in (("暗杠", True), ("明杠", False)):
        melds = [Meld("kong", tuple(T("W1", "W1", "W1", "W1")), is_concealed)]
        tags = {d.tag for d in decompositions(concealed, melds) if d.tag}
        check("%s 的 4 张不算两对（无七对 tag）" % kong_tag, not tags, str(tags))
    # 合法的「杠 + 3 面子 + 将」也不会被当成七对
    melds = [Meld("kong", tuple(T("W1", "W1", "W1", "W1")), True),
             Meld("chi", tuple(T("T7", "T8", "T9")), False)]
    hand = T("B1", "B2", "B3", "B4", "B5", "B6", "B9", "B9")
    s = calc.score(melds, hand, hand[-1], Options())
    show("暗杠+2面子+将（不是七对）", s)
    check("杠手牌不判七对", "七对" not in s.fan_map and "连七对" not in s.fan_map,
          str(s.fan_map))
    check("杠手牌算得出番（暗杠另计）", "暗杠" in s.fan_map, str(s.fan_map))

    # ★ 七对里的「分组类番种」口径（《问答》71 的牌例）
    #   4 张相同的牌算两对 ⇒ 没有刻子 ⇒ 大三元这类刻子番种不能算；
    #   但定义中不含对子的整手型番种（清幺九/混幺九/字一色…）可以另加计。
    hand = T("J1", "J1", "J1", "J1", "J2", "J2", "J2", "J2",
             "J3", "J3", "J3", "J3", "T8", "T8")
    s = calc.score([], hand, hand[-1], Options())
    show("七对含4张箭牌", s)
    check("七对里不算大三元", "大三元" not in s.fan_map, str(s.fan_map))

    hand = T("F1", "F1", "F1", "F1", "F2", "F2", "F2", "F2",
             "F3", "F3", "F3", "F3", "F4", "F4")
    s = calc.score([], hand, hand[-1], Options())
    show("七对含4张风牌", s)
    check("七对里不算大四喜", "大四喜" not in s.fan_map, str(s.fan_map))
    check("七对里不算三风刻", "三风刻" not in s.fan_map, str(s.fan_map))
    check("七对·字一色另加计", s.fan_map.get("字一色") == 64, str(s.fan_map))

    # 《问答》71 牌例 2：全部 1/9 的七对 → 另加计清幺九 64
    hand = T("B1", "B1", "B9", "B9", "B9", "B9", "T1", "T1",
             "T9", "T9", "W1", "W1", "W9", "W9")
    s = calc.score([], hand, hand[-1], Options())
    show("七对+清幺九（全幺九）", s)
    check("七对另加计清幺九64", s.fan_map.get("清幺九") == 64, str(s.fan_map))

    # 《问答》71 牌例 6：混幺九 + 五门齐
    hand = T("B1", "B1", "B9", "B9", "T1", "T1", "W9", "W9",
             "F2", "F2", "F4", "F4", "J3", "J3")
    s = calc.score([], hand, hand[-1], Options())
    show("七对+混幺九+五门齐", s)
    check("七对另加计混幺九32", s.fan_map.get("混幺九") == 32, str(s.fan_map))
    check("七对另加计五门齐6", s.fan_map.get("五门齐") == 6, str(s.fan_map))

    # 十三幺不能因为「全是幺九字」被误加混幺九
    hand = T("W1", "W9", "T1", "T9", "B1", "B9", "F1", "F2", "F3", "F4",
             "J1", "J2", "J3", "J3")
    s = calc.score([], hand, tile_of("J3"), Options())
    check("十三幺不误加混幺九", "混幺九" not in s.fan_map, str(s.fan_map))

    # 常规（四刻子）的清幺九不受影响
    hand = T("B1", "B1", "B1", "B9", "B9", "B9", "T1", "T1",
             "T1", "W9", "W9", "W9", "T9", "T9")
    s = calc.score([], hand, hand[-1], Options())
    show("清幺九（四刻子·常规）", s)
    check("常规清幺九仍成立", s.fan_map.get("清幺九") == 64, str(s.fan_map))

    LOG.append("\n== 5. 十三幺 ==")
    hand = T("W1", "W9", "T1", "T9", "B1", "B9", "F1", "F2", "F3", "F4",
             "J1", "J2", "J3", "J3")
    s = calc.score([], hand, tile_of("J3"), Options())
    show("十三幺", s)
    check("十三幺88", s.fan_map.get("十三幺") == 88, str(s.fan_map))

    LOG.append("\n== 6. 七星不靠 ==")
    hand = T("F1", "F2", "F3", "F4", "J1", "J2", "J3",
             "W1", "W4", "W7", "T2", "T5", "T8", "B3")
    s = calc.score([], hand, tile_of("B3"), Options())
    show("七星不靠", s)
    check("七星不靠24", s.fan_map.get("七星不靠") == 24, str(s.fan_map))

    LOG.append("\n== 7. 组合龙 ==")
    hand = T("W1", "W4", "W7", "T2", "T5", "T8", "B3", "B6", "B9",
             "W3", "W3", "W3", "T9", "T9")
    s = calc.score([], hand, tile_of("T9"), Options())
    show("组合龙", s)
    check("组合龙12", s.fan_map.get("组合龙") == 12, str(s.fan_map))

    LOG.append("\n== 8. 大四喜 + 字一色 ==")
    hand = T("F1", "F1", "F1", "F2", "F2", "F2", "F3", "F3", "F3",
             "F4", "F4", "F4", "J1", "J1")
    s = calc.score([], hand, tile_of("J1"), Options())
    show("大四喜·字一色", s)
    check("大四喜88", s.fan_map.get("大四喜") == 88, str(s.fan_map))
    check("字一色64", s.fan_map.get("字一色") == 64, str(s.fan_map))
    check("大四喜不计圈/门风刻",
          "圈风刻" not in s.fan_map and "门风刻" not in s.fan_map, str(s.fan_map))

    LOG.append("\n== 9. 碰碰和 + 双同刻（含碰出的面子）==")
    melds9 = [Meld("pong", (tile_of("W3"),) * 3)]
    concealed9 = T("T3", "T3", "T3", "B7", "B7", "B7",
                   "F2", "F2", "F2", "T9", "T9")
    s = calc.score(melds9, concealed9, tile_of("T9"), Options())
    show("碰碰和·双同刻", s)
    check("碰碰和6", s.fan_map.get("碰碰和") == 6, str(s.fan_map))
    check("双同刻2", s.fan_map.get("双同刻") == 2, str(s.fan_map))
    check("幺九刻≥1", (s.fan_map.get("幺九刻") or 0) >= 1, str(s.fan_map))

    LOG.append("\n== 10. 平胡 + 断幺 + 一般高 ==")
    hand = T("W2", "W3", "W4", "W2", "W3", "W4", "T5", "T6", "T7",
             "B6", "B7", "B8", "B5", "B5")
    s = calc.score([], hand, tile_of("B5"), Options())
    show("平胡·断幺·一般高", s)
    check("平和2", s.fan_map.get("平和") == 2, str(s.fan_map))
    check("断幺2", s.fan_map.get("断幺") == 2, str(s.fan_map))
    check("一般高1", s.fan_map.get("一般高") == 1, str(s.fan_map))

    LOG.append("\n== 11. 副露：碰 + 明杠 + 暗杠（按设计图那手牌）==")
    melds = [Meld("kong", (tile_of("J2"),) * 4, concealed=False),      # 明杠 發
             Meld("kong", (tile_of("J3"),) * 4, concealed=True)]       # 暗杠 白
    concealed = T("F4", "F4", "F4", "W1", "W2", "W3", "F3", "F3")      # 北北北 一二三萬 西西
    s = calc.score(melds, concealed, tile_of("F3"),
                   Options(round_wind="东", seat_wind="东"))
    show("明杠+暗杠手牌", s)
    check("混一色6", s.fan_map.get("混一色") == 6, str(s.fan_map))
    check("双箭刻6", s.fan_map.get("双箭刻") == 6, str(s.fan_map))
    check("一明一暗=双明杠4+暗杠2",
          s.fan_map.get("双明杠") == 4 and s.fan_map.get("暗杠") == 2, str(s.fan_map))
    check("全带幺4", s.fan_map.get("全带幺") == 4, str(s.fan_map))
    check("单钓将1", s.fan_map.get("单钓将") == 1, str(s.fan_map))

    LOG.append("\n== 12. 听牌分析（多面听）==")
    hand13 = T("T1", "T1", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8",
               "T9", "T9", "T9")
    res = calc.winning_tiles([], hand13)
    LOG.append("  听牌候选: " + ", ".join("%s(%d番)" % (name_of(t), s.total)
                                          for t, s in res))
    check("清一色牌型听 9 张", len(res) == 9, "实际 %d" % len(res))

    LOG.append("\n== 13. 门槛：不足 8 分不起和 ==")
    hand = T("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9",
             "T2", "T3", "T4", "B5", "B5")
    s = calc.score([], hand, tile_of("B5"),
                   Options(round_wind="西", seat_wind="北"))
    show("清龙+平和(西圈北位)", s)
    check("达到起和标准", s.ok and s.base >= 8, "base=%d" % s.base)

    LOG.append("\n== 14. 自摸/杠上开花/妙手回春 互斥 ==")
    hand = T("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
             "W8", "W9", "W9", "W9", "W9")
    s1 = calc.score([], hand, tile_of("W9"), Options(tsumo=True))
    s2 = calc.score([], hand, tile_of("W9"),
                    Options(tsumo=True, kong_bloom=True))
    s3 = calc.score([], hand, tile_of("W9"),
                    Options(tsumo=True, last_draw=True))
    check("自摸时不计杠上开花/妙手回春", "杠上开花" not in s1.fan_map
          and "妙手回春" not in s1.fan_map, str(s1.fan_map))
    check("杠上开花不计自摸", "自摸" not in s2.fan_map and s2.fan_map.get("杠上开花") == 8,
          str(s2.fan_map))
    check("妙手回春不计自摸", "自摸" not in s3.fan_map and s3.fan_map.get("妙手回春") == 8,
          str(s3.fan_map))

    LOG.append("\n== 15. 花牌不计入起和分 ==")
    hand = T("W1", "W2", "W3", "T1", "T2", "T3", "B1", "B2", "B3",
             "W7", "W8", "W9", "F1", "F1")
    s0 = calc.score([], hand, tile_of("F1"), Options())
    s1 = calc.score([], hand, tile_of("F1"), Options(flowers=8))
    check("花牌只加总番不改起和分",
          s1.base == s0.base and s1.total == s0.total + 8,
          "base %d->%d total %d->%d" % (s0.base, s1.base, s0.total, s1.total))
    check("未达 8 分时给出提示", (not s0.ok) or s0.base >= 8, s0.message)

    LOG.append("\n== 16. 旧接口兼容 ==")
    codes = ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
             "W8", "W9", "W9", "W9", "W9"]
    fm = calc.calculate_fan(codes, {"round_wind": "东", "seat_wind": "东"})
    check("calculate_fan 返回 dict", isinstance(fm, dict) and "九莲宝灯" in fm, str(fm))
    check("is_winning_hand", calc.is_winning_hand(codes))
    check("is_winning_hand 反例",
          not calc.is_winning_hand(["W1", "W3", "W5", "W7", "W9",
                                    "T1", "T3", "T5", "T7", "T9",
                                    "B1", "B3", "B5", "B7"]))
    pw = calc.get_possible_winning_tiles(codes[:13])
    check("get_possible_winning_tiles 非空", len(pw) > 0, str(pw))

    LOG.append("\n== 17. 非法输入保护 ==")
    s = calc.score([], T("W1", "W1", "W1", "W1", "W1"), None, Options())
    check("张数不足给出提示", bool(s.message), s.message)
    s = calc.score([], T("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
                         "W9", "T2", "T3", "T5", "B5"), None, Options())
    check("不能和牌给出提示", bool(s.message), s.message)

    LOG.append("\n== 18. 番表可用 ==")
    ft = calc.fan_table()
    total = sum(len(v) for _, v in ft)
    check("番表 12 档", len(ft) == 12, "实际 %d" % len(ft))
    check("番表 81 个番种", total == 81, "实际 %d" % total)

    LOG.append("")
    LOG.append("结果: 通过 %d 项，失败 %d 项" % (PASS, FAIL))
    text = "\n".join(LOG)
    with io.open(os.path.join(HERE, "_engine_out.txt"), "w",
                 encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print(text)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
