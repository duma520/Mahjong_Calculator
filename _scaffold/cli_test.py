# -*- coding: utf-8 -*-
"""「不用 HTTP / 不用端口 / 不用先启动谁」的算番入口测试（v2.6.0）

验证两件事：
    ① 命令行：`python mahjong_core.py --hand "..." --json`、
       `python Mahjong_Calculator.py --hand "..." --json`（**带参数时不启动界面**）——
       算完就退出，靠退出码 + stdout 拿结果。
    ② import：`from mahjong_core import MahjongFanCalculator` / `score_hand()` 直接算。

跑法：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/cli_test.py
日志写 _scaffold/_cli_out.txt（UTF-8），退出码 0 = 全通过。
"""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import mahjong_core as C                                                    # noqa: E402

LOG = []
PASS = FAIL = 0
OUT = os.path.join(HERE, "_cli_out.txt")
CORE = os.path.join(ROOT, "mahjong_core.py")
GUI = os.path.join(ROOT, "Mahjong_Calculator.py")


def log(msg=""):
    LOG.append(str(msg))
    try:
        with io.open(OUT, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write("\n".join(LOG))
    except Exception:                                                       # noqa: BLE001
        pass
    try:
        print(msg, flush=True)
    except Exception:                                                       # noqa: BLE001
        pass


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        log("  [OK]   %s" % name)
    else:
        FAIL += 1
        log("  [FAIL] %s  %s" % (name, extra))


def run(args, timeout=90):
    """跑一次子进程（UTF-8 输出），返回 (退出码, stdout, 耗时秒)"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.time()
    p = subprocess.run([sys.executable, "-u"] + args, capture_output=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout)
    return p.returncode, (p.stdout or ""), time.time() - t0


def as_json(text):
    try:
        return json.loads(text)
    except Exception:                                                       # noqa: BLE001
        return None


def main():
    log("=" * 74)
    log("国标麻将算番器 —— 命令行 / import 算番入口测试（v2.6.0）")
    log("时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 74)

    # ---------------- 1. mahjong_core.py 命令行
    log("\n【1】python mahjong_core.py（一次调用算完就退出）")
    rc, so, dt = run([CORE, "--hand", "11123456789999m", "--win", "9m", "--json"])
    js = as_json(so)
    check("九莲宝灯手：退出码 0", rc == 0, "%s %s" % (rc, so[:120]))
    check("九莲宝灯手：总番 106", isinstance(js, dict) and js.get("total") == 106,
          str(js)[:140])
    check("番种含 九莲宝灯 88 / 清龙 16 / 四归一 2",
          isinstance(js, dict) and {(f["name"], f["fan"]) for f in js.get("fans", [])}
          >= {("九莲宝灯", 88), ("清龙", 16), ("四归一", 2)}, str(js)[:160])
    check("ok=true", isinstance(js, dict) and js.get("ok") is True, str(js)[:80])
    check("默认就是 JSON（不写 --json 也能解析）",
          isinstance(as_json(run([CORE, "--hand", "11123456789999m",
                                  "--win", "9m"])[1]), dict))
    check("输出是纯 ASCII（跨语言/跨编码都安全）", so.isascii(), so[:80])

    rc, so, _ = run([CORE, "--hand", "11123456789999m", "--win", "9m", "--text"])
    check("--text 输出人话（含「总番 106」）",
          rc == 0 and "总番 106" in so, so[:160])

    rc, so, _ = run([CORE, "--hand", "11123456789999m"])     # 省略 --win → 取最后一张
    check("省略 --win 时取最后一张（仍 106 番）",
          rc == 0 and as_json(so).get("total") == 106, so[:120])

    rc, so, _ = run([CORE, "--hand", "一万 一万 一万 二万 三万 四万 五万 六万 七万 "
                                      "八万 九万 九万 九万 九万", "--win", "九万", "--json"])
    check("中文写法也认（总番 106）",
          rc == 0 and as_json(so).get("total") == 106, so[:120])

    rc, so, _ = run([CORE, "--hand", "1112345678999m", "--waits", "--json"])
    js = as_json(so)
    check("听牌（--waits）：9 张", rc == 0 and isinstance(js, dict)
          and js.get("count") == 9, str(js)[:140])
    check("听牌项带 tile/name/total/fans",
          isinstance(js, dict) and js.get("waits")
          and {"tile", "name", "total", "fans"} <= set(js["waits"][0]),
          str(js)[:140])
    rc, so2, _ = run([CORE, "--hand", "1112345678999m", "--waits-all", "--json"])
    check("--waits-all 不筛起和分（数量 ≥ --waits）",
          rc == 0 and as_json(so2).get("count", 0) >= 9, so2[:120])

    rc, so, _ = run([CORE, "--hand", "444z 123m 3z", "--meld", "kong:6666z",
                     "--meld", "angang:7777z", "--waits", "--text"])
    check("副露（明杠+暗杠）+ 听牌：听 西（F3）",
          rc == 0 and "F3（西）" in so, so[:200])

    rc, so, _ = run([CORE, "--hand", "444z 123m 33z", "--meld", "kong:6666z",
                     "--meld", "angang:7777z", "--json"])
    check("副露算番：26 番", rc == 0 and as_json(so).get("total") == 26, so[:160])

    rc, so, _ = run([CORE, "--hand", "11123456789999m", "--win", "9m", "--tsumo", "--json"])
    js = as_json(so)
    check("--tsumo 生效（含自摸/不求人类番种）",
          rc == 0 and any(f["name"] in ("自摸", "不求人", "门前清自摸和")
                          for f in js.get("fans", [])), str(js)[:160])

    rc, so, _ = run([CORE, "--version"])
    check("--version 报引擎信息（81 番种 / 34 牌）",
          rc == 0 and as_json(so).get("fans") == 81
          and as_json(so).get("tiles") == 34, so[:160])
    rc, so, _ = run([CORE, "--fan-table", "--json"])
    check("--fan-table 输出番表（12 个分值档）",
          rc == 0 and len(as_json(so).get("table", [])) == 12, so[:120])
    rc, so, _ = run([CORE, "--help"])
    check("--help 退出码 0 且含用法", rc == 0 and "mahjong_core" in so, so[:120])

    # 错误分支：退出码要能被脚本判断
    rc, so, _ = run([CORE, "--hand", "123m 456s 789p 111z 2z 3z", "--json"])
    check("不能和牌 → 退出码 1 且 ok=false",
          rc == 1 and as_json(so).get("ok") is False, "%s %s" % (rc, so[:120]))
    rc, so, _ = run([CORE, "--hand", "1m 2m", "--json"])
    check("牌数不对 → 退出码 2 且 error 说明应为 14 张",
          rc == 2 and "14" in (as_json(so).get("error") or ""), "%s %s" % (rc, so[:140]))
    rc, so, _ = run([CORE, "--hand", "Z9 Z9", "--json"])
    check("认不出的牌 → 退出码 2", rc == 2 and as_json(so).get("ok") is False,
          "%s %s" % (rc, so[:140]))
    rc, so, _ = run([CORE, "--hand", "444z 123m 3z", "--meld", "kong:6666z",
                     "--meld", "angang:7777z", "--json"])   # 算番要 8 张
    check("带副露时牌数不对 → 退出码 2 且提示 14-3×副露", rc == 2, "%s %s" % (rc, so[:140]))

    # ---------------- 2. 主程序（exe）带参数：不启动界面
    log("\n【2】Mahjong_Calculator.py 带参数（= 打包后的 exe 用法）")
    rc, so, dt = run([GUI, "--hand", "11123456789999m", "--win", "9m", "--json"],
                     timeout=120)
    check("主程序带参数：退出码 0 + 总番 106",
          rc == 0 and as_json(so).get("total") == 106, "%s %s" % (rc, so[:140]))
    check("主程序带参数：没启动界面（%0.1fs 内结束）" % dt, dt < 25, "耗时 %0.1fs" % dt)
    rc, so, _ = run([GUI, "--version"], timeout=120)
    check("主程序 --version 也走命令行", rc == 0 and as_json(so), so[:120])
    rc, so, _ = run([GUI, "--hand", "1112345678999m", "--waits", "--text"], timeout=120)
    check("主程序 --waits --text：输出人话听牌",
          rc == 0 and "听牌" in so, so[:140])

    # ---------------- 3. import 方式（进程内）
    log("\n【3】import mahjong_core（能 import 的语言最省事）")
    calc = C.MahjongFanCalculator()
    ids = [C.tile_of(c) for c in
           ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
            "W9", "W9", "W9", "W9")]
    s = calc.score([], ids, C.tile_of("W9"), C.Options())
    check("直接构造 MahjongFanCalculator().score() → 106 番", s.total == 106, s.text())
    check("score_hand(简写字符串) → 106 番",
          C.score_hand("11123456789999m", win="9m")["total"] == 106)
    check("score_hand(列表 + 中文和张) 一样",
          C.score_hand(["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
                        "W8", "W9", "W9", "W9", "W9"], win="九万")["total"] == 106)
    check("score_hand(带副露字符串) → 26 番",
          C.score_hand("444z 123m 33z", win="3z",
                       melds="kong:6666z angang:7777z")["total"] == 26,
          str(C.score_hand("444z 123m 33z", win="3z",
                           melds="kong:6666z angang:7777z")))
    check("score_hand 牌数不对 → 返回 error（不抛异常）",
          "error" in C.score_hand("1m 2m"))
    check("winning_tiles() 直接可用（听 9 张）",
          len(calc.winning_tiles([], [C.tile_of(c) for c in
                                      ("W1", "W1", "W1", "W2", "W3", "W4", "W5",
                                       "W6", "W7", "W8", "W9", "W9", "W9")],
                                 C.Options())) == 9)

    # ---------------- 4. 真的不需要服务 / 端口
    log("\n【4】不依赖服务与端口")
    with io.open(CORE, encoding="utf-8") as fp:
        src = fp.read()
    check("mahjong_core 里没有任何网络/服务代码（socket / HTTPServer）",
          "ThreadingHTTPServer" not in src and "import socket" not in src
          and "BaseHTTPRequestHandler" not in src)
    check("core 的 CLI 走的是同一套引擎（不是另一个实现）",
          "MahjongFanCalculator()" in src and "cli_main" in src)

    log("\n" + "=" * 74)
    log("结果: 通过 %d 项，失败 %d 项" % (PASS, FAIL))
    log("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
