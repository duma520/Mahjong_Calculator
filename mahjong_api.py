# -*- coding: utf-8 -*-
"""国标麻将算番器 —— **Web 版（手机/平板浏览器算番）的服务端**，附带页面内部用的 JSON 路由

★ 先分清两件事（v2.6.0）：
    · **给其它程序调用的「API」是 `mahjong_core`，不是这个文件**：
        能 import 的： from mahjong_core import MahjongFanCalculator   # 或 score_hand()
        不能 import 的： 国标麻将算番器.exe --hand "..." --json
                        （开发时用 python mahjong_core.py --hand "..." --json）
        这两种方式都**不需要 HTTP、不需要端口、不需要先启动谁**。
    · 本文件只为**浏览器**服务：内联一份单文件 Web 客户端（手机/平板打开就能算番），
      `/api/*` 是这份页面自己用的路由。**默认不需要口令**（想加门槛再传 --token）。

单独运行（起 Web 版服务）：
    python mahjong_api.py [--host 127.0.0.1] [--port 8718] [--token 口令] [--anon web,info] [--verbose]
也可以由主程序内嵌启动：mahjong_gui.py →「工具 → 启动 Web 版」
（两者用同一份代码，行为一致）。

★ 默认只监听 127.0.0.1（仅本机可访问）。若要对局域网/手机开放，
   显式传 --host 0.0.0.0（建议只在自家网络用；需要门槛时再加 --token）。

★ 免口令白名单（v2.5.0）：设了口令后，可以**分项**允许某些东西「不用口令也能用」，
   主程序里在「工具 → 免口令访问设置…」逐项勾选（含 Web 客户端）。分组：
     web   = Web 客户端页面 + 牌面图（/、/web、/index.html、/manifest、/favicon、/tiles/*）
     debug = 自测页 /debug        info = /api/health·/version·/tiles·/fan_table·/help
     score = /api/score           waits = /api/waits·/waits_all·/wins
   默认等同于旧行为：web + debug 免口令，其余 `/api/*` 要口令。
   单独跑服务时用 `--anon web,score` 指定（`--anon none` = 全部要口令）。

★ Web 版界面布局与桌面版一致（v2.4.4，改 Web 布局请先看桌面版怎么排）：
    ① 牌选择区（索 / 筒 / 万 / 字牌 四行，点一下加一张、长按或右键减一张）
    ② 模式行（立牌/吃/碰/明杠/暗杠 + 重置；重置 = 全部复位）
    ③ 选项区固定四行：□自摸 □和绝张 □抢杠和/杠上开花 □海底捞月/妙手回春 ／
       风圈 ／ 风位 ／ 花牌（8 张小图 + 「N 张」；花牌**不在牌池里**）
    ④ 已选牌（副露 / 立牌 / 和张 / 花牌 + 提示行）→ ⑤ 听牌候选 → ⑥ 算番结果

接口一览（全部返回 JSON，UTF-8；错误返回 {"ok":false,"error":"..."}）
    GET  /                ★ Web 版算番器（手机/平板/电脑浏览器直接打开就能算番）
    GET  /debug           浏览器自测页（表单 + 实时结果）
    GET  /manifest.webmanifest  可「添加到主屏」的应用清单
    GET  /tiles/<编号>.png     牌面图片（B1~B9/T1~T9/W1~W9/F1~F4/J1~J3/S1~S4/P1~P4/empty）
    GET  /api/help        接口说明（纯文本）
    GET  /api/health      存活探测 → {"ok":true,"server":"mahjong-api"}
    GET  /api/version     版本 / 牌张编码表 / 规则文件
    GET  /api/tiles       34 张牌：{tid, code, name, suit, num}
    GET  /api/fan_table   81 番种：[{value, fans:[{name, definition}]}]
    GET  /api/score?...   算番（GET 简写形式）
    POST /api/score       算番（推荐）
    POST /api/waits       听牌：13 张 → 每张听牌的番数
    POST /api/waits_all   听牌（不筛起和分，含不足 8 分的候选）
    POST /api/wins        /api/waits 的别名

牌张编码（与界面、图片文件名一致）
    B1~B9 = 1~9 筒    T1~T9 = 1~9 索    W1~W9 = 1~9 万
    F1~F4 = 东 南 西 北               J1~J3 = 中 发 白
    S1~S4 = 春 夏 秋 冬               P1~P4 = 梅 兰 竹 菊（花牌，每张 1 分、不计起和分）

请求体（POST，JSON）
{
  "melds": [ {"kind":"chi",  "tiles":["W1","W2","W3"], "concealed":false},
             {"kind":"kong", "tiles":["B7","B7","B7","B7"], "concealed":true} ],
  "concealed": ["W4","W5","W6","..."],        # 或 "counts":{"W4":2,...}
  "win": "W6",                                 # 可省；省了取 concealed 最后一张
  "options": {"tsumo":true, "last_tile":false, "rob_kong":false,
              "kong_bloom":false, "last_draw":false, "last_discard":false,
              "round_wind":"东", "seat_wind":"南",
              "flowers":2,                     # 花牌张数（每张 1 分）
              "flower_tiles":["S1","P4"]}      # 也可直接给花牌代码
}

张数口径（易错）：`concealed` 是「整手牌」且**包含和张**，长度必须 = 14 - 3×副露数；
`win` 只用来指出其中哪一张是和张（可省，则取 concealed 最后一张）。
拿「13 张立牌 + 1 张和张」算番时，要把和张也拼进 concealed（听牌接口相反：给 13 张）。
杠虽然占 4 张实体牌，但按 1 个面子折算，所以 1 个杠 + 3 面子 + 将 = concealed 11 张。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mahjong_core import (MahjongFanCalculator, Meld, Options, TILE_CODES,  # noqa: E402
                          code_of, name_of, num_of, suit_of, tile_of)

APP_NAME = "国标麻将算番器"
API_NAME = "mahjong-api"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8718

SUIT_NAMES = {0: "筒", 1: "索", 2: "万", 3: "风", 4: "箭", 5: "花"}


class ApiError(Exception):
    """请求错误（返回 400）"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# ------------------------------------------------------------------ 引擎封装

class Engine:
    """线程安全的算番引擎封装（引擎本身只读，这里再加一把锁更稳妥）"""

    def __init__(self, rules_path: Optional[str] = None):
        self._lock = threading.Lock()
        self._calc = MahjongFanCalculator(rules_path=rules_path)

    # ---- 工具
    def tiles_of(self, codes) -> List[int]:
        out = []
        for c in codes:
            if not isinstance(c, str) or c not in TILE_CODES:
                raise ApiError("无效的牌张代码：%r（应为 B1~B9/T1~T9/W1~W9/F1~F4/J1~J3）" % (c,))
            out.append(tile_of(c))
        return out

    def parse_melds(self, data) -> List[Meld]:
        melds: List[Meld] = []
        if data in (None, ""):
            return melds
        if not isinstance(data, list):
            raise ApiError("melds 必须是数组")
        for i, item in enumerate(data):
            if isinstance(item, dict):
                kind = str(item.get("kind") or item.get("type") or "").lower()
                codes = item.get("tiles") or item.get("codes") or []
                concealed = bool(item.get("concealed", False))
            elif isinstance(item, (list, tuple)):
                kind, codes, concealed = "chi", list(item), False
            else:
                raise ApiError("melds[%d] 格式不对" % i)
            kind = {"chi": "chi", "chow": "chi", "吃": "chi",
                    "pong": "pong", "peng": "pong", "碰": "pong",
                    "kong": "kong", "gang": "kong", "杠": "kong",
                    "mkong": "kong", "akang": "kong"}.get(kind, kind)
            if kind not in ("chi", "pong", "kong"):
                raise ApiError("melds[%d].kind 应为 chi/pong/kong，收到 %r" % (i, kind))
            tiles = self.tiles_of(codes)
            want = 4 if kind == "kong" else 3
            if len(tiles) != want:
                raise ApiError("melds[%d] 需要 %d 张牌，收到 %d 张" % (i, want, len(tiles)))
            if kind != "chi" and len(set(tiles)) != 1:
                raise ApiError("melds[%d] 碰/杠 必须是同一种牌" % i)
            if kind == "chi":
                t = sorted(tiles)
                if not (t[0] + 1 == t[1] and t[1] + 1 == t[2]
                        and num_of(t[0]) + 2 == num_of(t[2])):
                    raise ApiError("melds[%d] 吃 必须是同花色相连的 3 张" % i)
            melds.append(Meld(kind, tuple(tiles), concealed))
        return melds

    def parse_concealed(self, data) -> List[int]:
        if isinstance(data, dict):                    # {"W4":2,"T3":1}
            codes: List[str] = []
            for code, n in data.items():
                try:
                    cnt = int(n)
                except Exception:                     # noqa: BLE001
                    raise ApiError("counts[%s] 张数不是整数" % code)
                if cnt < 0:
                    raise ApiError("counts[%s] 张数不能为负" % code)
                codes.extend([code] * cnt)
            return self.tiles_of(codes)
        if not isinstance(data, list):
            raise ApiError("concealed 必须是数组或 {牌:张数} 对象")
        return self.tiles_of(data)

    def parse_options(self, data) -> Options:
        d = data or {}
        if not isinstance(d, dict):
            raise ApiError("options 必须是对象")
        flowers = d.get("flowers")
        ft = d.get("flower_tiles")
        if ft is not None:
            if not isinstance(ft, list):
                raise ApiError("options.flower_tiles 必须是数组")
            flowers = len([c for c in ft if c])
        try:
            flowers = max(0, int(flowers or 0))
        except Exception:                             # noqa: BLE001
            raise ApiError("options.flowers 必须是整数 0~8")
        if flowers > 8:
            raise ApiError("options.flowers 最多 8 张")
        rw = d.get("round_wind", "东")
        sw = d.get("seat_wind", "东")
        for label, v in (("round_wind", rw), ("seat_wind", sw)):
            if v not in ("东", "南", "西", "北"):
                raise ApiError("options.%s 应为 东/南/西/北，收到 %r" % (label, v))
        return Options(
            tsumo=bool(d.get("tsumo", False)),
            last_tile=bool(d.get("last_tile", False)),
            rob_kong=bool(d.get("rob_kong", False)),
            kong_bloom=bool(d.get("kong_bloom", False)),
            last_draw=bool(d.get("last_draw", False)),
            last_discard=bool(d.get("last_discard", False)),
            round_wind=rw, seat_wind=sw, flowers=flowers,
        )

    # ---- 业务
    @staticmethod
    def score_json(score) -> dict:
        return {
            "total": int(score.total),
            "base": int(score.base),
            "flowers": int(score.flowers),
            "reach_standard": bool(score.ok),
            "pattern": score.pattern,
            "message": score.message,
            "fans": [{"name": n, "value": v} for n, v in score.fans],
        }

    def score(self, body: dict) -> dict:
        melds = self.parse_melds(body.get("melds"))
        concealed = self.parse_concealed(body.get("concealed"))
        opts = self.parse_options(body.get("options"))
        win = body.get("win")
        win_tid = None if win in (None, "") else self.tiles_of([win])[0]
        self.check_shape(melds, concealed, win_tid)
        with self._lock:
            res = self._calc.score(melds, concealed, win_tid, opts)
        out = self.score_json(res)
        out.update({
            "ok": True,
            "win": code_of(win_tid) if win_tid is not None else (
                code_of(concealed[-1]) if concealed else None),
            "melds": [[code_of(t) for t in m.tiles] for m in melds],
        })
        return out

    def check_shape(self, melds: List[Meld], concealed: List[int],
                    win_tid: Optional[int]) -> None:
        """输入合法性前置校验（不合法直接 400，而不是返回一个 0 番结果）"""
        want = 14 - 3 * len(melds)
        if len(concealed) != want:
            raise ApiError("concealed 应为 %d 张（14 - 3×副露数 %d），收到 %d 张"
                           % (want, len(melds), len(concealed)))
        if win_tid is not None and win_tid not in concealed:
            raise ApiError("win（和张 %s）不在 concealed 里" % code_of(win_tid))
        total = [0] * 34
        for t in concealed:
            total[t] += 1
        for m in melds:
            for t in m.tiles:
                total[t] += 1
        over = [code_of(i) for i, v in enumerate(total) if v > 4]
        if over:
            raise ApiError("有牌超过 4 张：%s（请检查输入）" % "、".join(over))

    def waits(self, body: dict, only_reach: bool = True) -> dict:
        melds = self.parse_melds(body.get("melds"))
        concealed = self.parse_concealed(body.get("concealed"))
        opts = self.parse_options(body.get("options"))
        want = 14 - 3 * len(melds)
        if len(concealed) != want - 1:
            raise ApiError("听牌时 concealed 应为 %d 张（14 - 3×副露数 - 1），收到 %d 张"
                           % (want - 1, len(concealed)))
        with self._lock:
            tiles = self._calc.waiting_tiles(melds, concealed)
            items = []
            for t in tiles:
                s = self._calc.score(melds, list(concealed) + [t], t, opts)
                if only_reach and not s.ok:
                    continue
                item = self.score_json(s)
                item.update({"tile": code_of(t), "name": name_of(t)})
                items.append(item)
        items.sort(key=lambda it: (-it["total"], it["tile"]))
        return {"ok": True, "count": len(items),
                "concealed": [code_of(t) for t in concealed],
                "waits": items}

    def tiles_table(self) -> List[dict]:
        out = []
        for tid in range(34):
            out.append({"tid": tid, "code": code_of(tid), "name": name_of(tid),
                        "suit": SUIT_NAMES.get(suit_of(tid), "?"), "num": num_of(tid)})
        return out

    def fan_table(self) -> List[dict]:
        with self._lock:
            rows = self._calc.fan_table()
        return [{"value": v,
                 "fans": [{"name": n, "definition": d} for n, d in items]}
                for v, items in rows]

    def version(self) -> dict:
        rules = getattr(self._calc, "rules_path", "")
        return {"ok": True, "server": API_NAME, "app": APP_NAME,
                "engine_fans": len(getattr(self._calc, "fan_values", {})),
                "rules_file": os.path.basename(rules) if rules else "",
                "rules_loaded": bool(getattr(self._calc, "rules", None))}


# ------------------------------------------------------------------ HTTP 层

HELP_TEXT = __doc__

# ------------------------------------------------------------------ 牌面图
# Web 客户端直接用程序自带的《麻将图》里的 PNG（B1~B9/T1~T9/W1~W9/F1~F4/J1~J3/S1~S4/P1~P4/empty）
import re                                                      # noqa: E402

TILE_FILE_RE = re.compile(r"^(?:B[1-9]|T[1-9]|W[1-9]|F[1-4]|J[1-3]|S[1-4]|P[1-4]|empty)\.png$")

# ------------------------------------------------------------------ 免口令白名单
# ★ v2.5.0：设了口令后，哪些东西可以「不用口令也能用」由调用方（GUI 设置）逐项勾选。
#   口令为空时本来就不校验口令，这里不生效。
#   分组表：key → 该组的路径；**以 "*" 结尾表示前缀匹配**，否则要求路径完全相等
#   （注意 "/" 必须当「精确项」——写成前缀就会把一切路径都放行）
ANON_GROUPS = {
    "web":   ("/", "/web", "/index.html", "/manifest.webmanifest",
               "/favicon.ico", "/apple-touch-icon.png", "/tiles/*"),
    "debug": ("/debug",),
    "info":  ("/api/health", "/api/version", "/api/tiles",
               "/api/fan_table", "/api/help"),
    "score": ("/api/score",),
    "waits": ("/api/waits", "/api/waits_all", "/api/wins"),
}
# 默认值：与 v2.4.x 行为完全一致（Web 页面/牌面图/自测页免口令，`/api/*` 要口令）
ANON_DEFAULT = ("web", "debug")

WEB_CLIENT = r"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#2f7ff0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="麻将算番">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/tiles/J1.png">
<title>__APP__ · Web 版</title>
<style>
:root{--blue:#2f7ff0;--bg:#f4f6fa;--card:#fff;--line:#dde3ec;--grey:#6b7684;--red:#e74c3c;
 /* ★ v2.7.0 牌尺寸全部改成变量：这组默认值 = 「经典（固定尺寸）」布局，
    与老版本逐个像素一致（38/52、34/46、28/38、间距 3/4）；
    「自适应」布局时由 JS 按屏幕大小改写这些变量（body.auto）——
    两套布局共存，切换不会把旧布局改坏 */
 --tw:38px;--th:52px;--pw:34px;--ph:46px;
 --gw:4px;--pgap:3px;
 --fw:34px;--fh:46px;--fwi:28px;--fhi:38px;
 --ww:28px;--wh:38px}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:#1f2937;
 font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;font-size:15px}
header{position:sticky;top:0;z-index:9;background:var(--blue);color:#fff;
 padding:10px 12px;display:flex;align-items:center;gap:8px;box-shadow:0 1px 6px #0002}
header h1{font-size:16px;margin:0;flex:1;font-weight:600}
header .st{font-size:11px;opacity:.9;white-space:nowrap}
main{padding:10px 10px 120px;max-width:760px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:8px 10px;margin:0 0 10px}
.card h2{font-size:13px;color:var(--grey);margin:0 0 6px;font-weight:600}
.row{display:flex;align-items:center;gap:6px;min-height:46px;flex-wrap:wrap}
.row .lb{width:44px;flex:none;color:var(--grey);font-size:13px}
.tiles{display:flex;gap:var(--gw);flex-wrap:wrap;align-items:center}
.tiles img{width:var(--pw);height:var(--ph);display:block}
.tiles .ph{width:var(--pw);height:var(--ph);border:1px dashed var(--line);border-radius:4px;
 display:flex;align-items:center;justify-content:center;color:#b9c2cd;font-size:11px}
.meldgap{display:inline-block;width:10px;flex:none}
.empty{color:#9aa3ae;font-size:13px}
.tot{font-size:30px;font-weight:700;line-height:1.1}
.tot.low{color:var(--red)}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.tag{background:#eef3fb;border:1px solid #d6e3fa;border-radius:6px;padding:2px 6px;font-size:13px}
.tag b{color:var(--blue);margin-right:4px}
.waits{display:flex;flex-wrap:wrap;gap:6px}
.wait{border:1px solid var(--line);border-radius:8px;background:#fff;padding:4px 6px;
 display:flex;flex-direction:column;align-items:center;min-width:52px;cursor:pointer}
.wait.on{border-color:var(--blue);background:#eaf2ff}
.wait img{width:var(--ww);height:var(--wh)}
.wait span{font-size:11px;color:var(--grey)}
.wait span.low{color:var(--red)}
.btns{display:flex;gap:6px;flex-wrap:wrap}
button{font:inherit;border:1px solid var(--line);background:#fff;border-radius:8px;
 padding:7px 11px;cursor:pointer}
button.on{background:var(--blue);border-color:var(--blue);color:#fff}
button.warn{background:#fff3e6;border-color:#f0c08a}
button:active{transform:translateY(1px)}
.mod{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.pool{margin:0 0 8px}
.pool .line{display:flex;gap:3px;flex-wrap:wrap}
.tile{position:relative;width:var(--tw);height:var(--th);border:2px solid transparent;border-radius:7px;
 background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;
 -webkit-user-select:none;user-select:none;-webkit-touch-callout:none;touch-action:manipulation}
.tile img{width:calc(var(--tw) - 6px);height:calc(var(--th) - 8px);pointer-events:none}
.tile.sel{border-color:var(--blue);background:#eaf2ff}
.tile .cnt{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;border-radius:9px;
 background:var(--red);color:#fff;font-size:11px;font-weight:700;line-height:18px;text-align:center;
 padding:0 3px;cursor:pointer;pointer-events:auto;box-shadow:0 0 0 2px #fff}
/* ★ 手机没有右键：红色数字就是「−1」按钮（点它减一张） */
.tile .cnt:active{transform:scale(.9)}
.tiles img.clk{cursor:pointer}
.tiles img.clk:active{opacity:.55}
.tile .cnt.hide{display:none}
/* ★ 牌池每行必须横排（索/筒/万/字牌 4 行，每行 9/9/9/7 张）——
   不能只靠祖先 .pool 类（v2.4.4 漏过一次：类名没带上，结果每张牌各占一行） */
#pool .line,.pool .line{display:flex;gap:var(--pgap);flex-wrap:wrap;margin:0 0 3px}
#pool .line:last-child,.pool .line:last-child{margin-bottom:0}
/* ★ 花牌小图（选项区第 4 行，与桌面版 FLOWER_SIZE 一样比普通牌小一圈） */
.ftile{position:relative;width:var(--fw);height:var(--fh);border:2px solid transparent;border-radius:7px;
 background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer}
.ftile img{width:var(--fwi);height:var(--fhi);pointer-events:none}
.ftile.sel{border-color:var(--blue);background:#eaf2ff}
.fcount{color:var(--grey);font-size:13px;margin-left:4px}
.tip{color:var(--grey);font-size:12px;line-height:1.6}
.dlg{position:fixed;inset:0;background:#0006;display:none;align-items:center;justify-content:center;z-index:20}
.dlg.show{display:flex}
.dlg .box{background:#fff;border-radius:12px;padding:16px;width:min(92vw,360px)}
.dlg input{font:inherit;width:100%;padding:8px;border:1px solid var(--line);border-radius:8px}
footer{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--line);
 padding:8px 10px;display:flex;gap:8px;justify-content:center}
</style></head><body>
<header>
  <h1>__APP__ · Web 版</h1>
  <div class="st" id="st">连接中…</div>
</header>
<main>
  <!-- ① 牌选择区（与桌面版一致：索 / 筒 / 万 / 字牌 四行） -->
  <div class="card">
    <h2>牌选择区（点一下加一张；点牌上红色数字 −1）</h2>
    <div class="pool" id="pool"></div>
  </div>

  <!-- ② 模式行（立牌/吃/碰/明杠/暗杠 + 重置） -->
  <div class="card">
    <div class="mod" id="modes"></div>
    <div class="btns" style="margin-top:8px">
      <button class="warn" onclick="resetAll()">重置</button>
      <button id="lybtn" onclick="toggleLayout()">布局：经典</button>
      <button onclick="window.open('/debug','_blank')">接口自测页</button>
      <button onclick="setToken()">换口令</button>
    </div>
  </div>

  <!-- ③ 选项区：固定四行（①复选框 ②圈风 ③风位 ④花牌），与桌面版一致 -->
  <div class="card">
    <h2>选项</h2>
    <div class="row"><div class="btns" id="opts"></div></div>
    <div class="row"><div class="lb">风圈</div><div class="btns" id="rwind"></div></div>
    <div class="row"><div class="lb">风位</div><div class="btns" id="swind"></div></div>
    <div class="row"><div class="lb">花牌</div><div class="tiles" id="flowers"></div>
      <span class="fcount" id="fcount">0 张</span></div>
  </div>

  <!-- ④ 已选牌 -->
  <div class="card">
    <h2>已选牌</h2>
    <div class="row"><div class="lb">副露</div><div class="tiles" id="m_melds"></div></div>
    <div class="row"><div class="lb">立牌</div><div class="tiles" id="m_hand"></div></div>
    <div class="row"><div class="lb">和张</div><div class="tiles" id="m_win"></div></div>
    <div class="row"><div class="lb">花牌</div><div class="tiles" id="m_flower"></div></div>
    <div class="tip" id="hint"></div>
  </div>

  <!-- ⑤ 听牌候选 -->
  <div class="card" id="c_wait" style="display:none">
    <h2>听牌候选（点一下设为和张）</h2>
    <div class="waits" id="waits"></div>
  </div>

  <!-- ⑥ 算番结果 -->
  <div class="card">
    <h2>算番结果 <span id="pat" class="tip"></span></h2>
    <div class="tot" id="tot">—</div>
    <div class="tip" id="msg"></div>
    <div class="tags" id="fans"></div>
    <div class="tip" style="margin-top:6px">
      手机：点牌加一张，点牌上的<b>红色数字</b>减一张（也可以在「立牌」里点一张减）。
      立牌满 13 张（有副露时 13 − 3×副露数）会自动列出听牌；点牌池里的牌或候选牌即可出结果。
    </div>
  </div>
</main>
<footer>
  <button onclick="scrollTo({top:0,behavior:'smooth'})">↑ 牌池</button>
  <button onclick="scrollTo({top:document.body.scrollHeight,behavior:'smooth'})">↓ 结果</button>
</footer>
<div class="dlg" id="dlg"><div class="box">
  <h3 style="margin:0 0 8px">需要访问口令</h3>
  <p class="tip" id="dlgmsg">请输入电脑端「工具 → API 地址与用法」里显示的口令。</p>
  <input id="tkin" placeholder="口令" autocomplete="one-time-code">
  <div class="btns" style="margin-top:10px">
    <button class="on" onclick="saveToken()">确定</button>
    <button onclick="hideDlg()">取消</button>
  </div>
</div></div>

<script>
const POOL=[["T1","T2","T3","T4","T5","T6","T7","T8","T9"],
            ["B1","B2","B3","B4","B5","B6","B7","B8","B9"],
            ["W1","W2","W3","W4","W5","W6","W7","W8","W9"],
            ["F1","F2","F3","F4","J1","J2","J3"]];
/* ★ 花牌不在牌池里：与桌面版一致，放在**选项区第 4 行**（点一下选/再点取消） */
const FLOWER=["S1","S2","S3","S4","P1","P2","P3","P4"];
const MODES=[["stand","立牌"],["chi","吃"],["peng","碰"],["minggang","明杠"],["angang","暗杠"]];
const ROUNDS=["东","南","西","北"];
const NAMES={};["B","T","W"].forEach(s=>{for(let i=1;i<=9;i++)NAMES[s+i]=(i)+(s=="B"?"筒":s=="T"?"索":"万")});
["东","南","西","北"].forEach((n,i)=>NAMES["F"+(i+1)]=n);
["中","发","白"].forEach((n,i)=>NAMES["J"+(i+1)]=n);
["春","夏","秋","冬"].forEach((n,i)=>NAMES["S"+(i+1)]=n);
["梅","兰","竹","菊"].forEach((n,i)=>NAMES["P"+(i+1)]=n);
const SPECIAL_PREFIX={"stand":"","chi":"吃","peng":"碰","minggang":"明杠","angang":"暗杠"};

let S={melds:[],concealed:{},win:null,flowers:[],mode:"stand",pending:[],
       layout:"fixed",     /* ★ v2.7.0：fixed=经典（默认，与老版本一样）/ auto=自适应 */
       opts:{tsumo:false,last_tile:false,special_a:false,special_b:false,round:"东",seat:"东"}};
let TOKEN="";
let BUSY=false;

/* ---------- 工具 ---------- */
function q(u){return u+(TOKEN?("?"+(u.includes("?")?"&":"")+"token="+encodeURIComponent(TOKEN)):"");}
async function api(path,body){
  const h={"Content-Type":"application/json"};
  if(TOKEN)h["X-Api-Token"]=TOKEN;
  const r=await fetch(path,{method:body?"POST":"GET",headers:h,
                            body:body?JSON.stringify(body):undefined});
  if(r.status===401){showDlg();throw new Error("需要访问口令");}
  const j=await r.json();
  if(j.ok===false)throw new Error(j.error||"接口错误");
  return j;
}
function el(id){return document.getElementById(id);}
/* ---------- 布局（★ v2.7.0：经典 / 自适应两套共存，默认还是经典） ----------
   经典 = 固定尺寸（与老版本像素一致，CSS 变量的默认值就是它）
   自适应 = 按屏幕宽高算出牌尺寸，手机上不会过大、平板上不会过小
   选择记在 localStorage（mj_layout），刷新/切页都保留 */
const LAYOUT_KEY="mj_layout";
const LAYOUT_VARS=["--tw","--th","--pw","--ph","--gw","--pgap",
                   "--fw","--fh","--fwi","--fhi","--ww","--wh"];
function loadLayout(){try{const v=localStorage.getItem(LAYOUT_KEY);return v==="auto"?"auto":"fixed";}
  catch(e){return "fixed";}}
function layoutName(){return S.layout==="auto"?"自适应":"经典";}
function setLayout(m,remember){
  S.layout=(m==="auto")?"auto":"fixed";
  document.body.classList.toggle("auto",S.layout==="auto");
  const b=el("lybtn");
  if(b){b.textContent="布局："+layoutName();
        b.title=S.layout==="auto"?"当前：自适应（按屏幕自动缩放）——点一下回到经典固定尺寸"
                                  :"当前：经典（固定尺寸）——点一下换成自适应";
        b.classList.toggle("on",S.layout==="auto");}
  autoSize();
  if(remember!==false){try{localStorage.setItem(LAYOUT_KEY,S.layout);}catch(e){}}
}
function toggleLayout(){setLayout(S.layout==="auto"?"fixed":"auto");}
function autoSize(){
  const root=document.documentElement;
  if(S.layout!=="auto"){                 /* 经典：清掉 JS 写的值，回到 CSS 默认（老样子） */
    LAYOUT_VARS.forEach(k=>root.style.removeProperty(k));
    return;
  }
  const vw=Math.min(document.documentElement.clientWidth||360,760);
  const avail=Math.max(220,vw-42);        /* main 10+10 + card 8+8 + 滚动条余量 */
  const pgap=vw<380?2:3;
  const nine=(avail-pgap*8-4)/9;          /* 一行 9 张（筒/索/万） */
  const vh=window.innerHeight||640;
  const byH=Math.min(vh*0.115,74);        /* 牌池 4 行，不能把屏占满 */
  let w=Math.floor(Math.min(nine,byH/1.364));
  w=Math.max(20,Math.min(w,46));     /* 夹紧：手机不会太小、平板也不会太大 */
  const h=Math.round(w*1.364);
  root.style.setProperty("--pw",w+"px");
  root.style.setProperty("--ph",h+"px");
  root.style.setProperty("--tw",(w+6)+"px");
  root.style.setProperty("--th",(h+8)+"px");
  root.style.setProperty("--gw",Math.max(2,Math.round(w/9))+"px");
  root.style.setProperty("--pgap",pgap+"px");
  const fw=Math.round(w*0.9),fh=Math.round(h*0.9);
  root.style.setProperty("--fw",(fw+6)+"px");
  root.style.setProperty("--fh",(fh+8)+"px");
  root.style.setProperty("--fwi",fw+"px");
  root.style.setProperty("--fhi",fh+"px");
  root.style.setProperty("--ww",Math.round(w*0.83)+"px");
  root.style.setProperty("--wh",Math.round(h*0.83)+"px");
}
let asTimer=null;
function autoSizeLater(){clearTimeout(asTimer);asTimer=setTimeout(autoSize,120);}
window.addEventListener("resize",autoSizeLater);
window.addEventListener("orientationchange",autoSizeLater);
/* ★ v2.5.0：图片地址也用 q() 带上口令 —— 这样即使「Web 客户端」被设成要口令，
   用 http://ip:端口/?token=xxx 打开页面时牌面图照样能加载（不会一片碎图） */
function img(code){return '<img src="'+q("/tiles/"+code+".png")+'" alt="'+code+'" title="'+(NAMES[code]||"")+'">';}
/* 已选牌也可点：手机/平板没有右键，点一下就是减一张（桌面鼠标同样好用） */
function imgClk(code){return '<img class="clk" onclick="minus(\''+code+'\')" src="'+
  q("/tiles/"+code+".png")+'" alt="'+code+'" title="点上一下可减一张">';}
function mkTiles(box,codes,emptyText,clickable){
  box.innerHTML = codes.length? codes.map(c=>clickable?imgClk(c):img(c)).join("")
    : '<div class="empty">'+(emptyText||"（空）")+'</div>';
}
/* ★ 副露渲染（与桌面版一致，v2.7.1 修）：
   明杠 / 碰 / 吃 = 全部正面；**暗杠 = 面·背·背·面**（中间两张用 empty.png 牌背）；
   不同副露之间留一段间隔（桌面版用 GAP 哨兵，这里用 .meldgap） */
function meldHtml(){
  if(!S.melds.length)return '<div class="empty">（暂无吃碰杠）</div>';
  return S.melds.map((m,i)=>{
    const t=(m.tiles||[]).slice();
    let codes=t;
    if(m.kind==="kong"&&m.concealed&&t.length>=4){
      codes=[t[0],"empty","empty",t[3]];          /* 面·背·背·面 */
    }
    const body=codes.map(c=>c==="empty"
      ? '<img src="'+q("/tiles/empty.png")+'" alt="暗杠" title="暗杠（中间两张显示牌背）">'
      : img(c)).join("");
    return (i?'<span class="meldgap"></span>':'')+body;
  }).join("");
}

/* ---------- 请求体 ---------- */
function concealedList(){const a=[];for(const k in S.concealed)for(let i=0;i<S.concealed[k];i++)a.push(k);return a;}
function meldsBody(){
  return S.melds.map(m=>({kind:m.kind,tiles:m.tiles,concealed:!!m.concealed}));
}
function optsBody(){
  const o={round_wind:S.opts.round,seat_wind:S.opts.seat};
  o.tsumo=!!S.opts.tsumo;o.last_tile=!!S.opts.last_tile;
  const t=!!S.opts.tsumo;
  o.kong_bloom=!!(S.opts.special_a&&t); o.rob_kong=!!(S.opts.special_a&&!t);
  o.last_draw=!!(S.opts.special_b&&t);  o.last_discard=!!(S.opts.special_b&&!t);
  o.flowers=S.flowers.length;
  return o;
}
function totalTiles(){let n=concealedList().length;
  S.melds.forEach(m=>n+=3); if(S.win)n+=1; return n;}
function needConcealed(){return 13-3*S.melds.length;}

/* ---------- 交互 ---------- */
function tap(code){
  if(/^[SP]/.test(code)){toggleFlower(code);return;}   /* 花牌：点一下选/再点取消 */
  if(S.mode=="chi"){chiTap(code);return;}
  if(S.mode!="stand"){meldFromPool(code);return;}
  const used=(S.concealed[code]||0)+(S.win===code?1:0);
  if(used>=4){flash("这种牌最多 4 张");return;}
  if(S.win){                       /* 已有和张：再点一张 = 换和张（点同一张则取消） */
    S.win=(S.win===code)?null:code;render();return;
  }
  if(concealedList().length>=needConcealed()){S.win=code;render();return;}
  S.concealed[code]=(S.concealed[code]||0)+1;
  render();
}
function longTap(code){
  if(/^[SP]/.test(code)){toggleFlower(code);return;}
  if(S.mode=="chi"&&S.pending.length){S.pending.pop();render();return;}
  if(S.win===code){S.win=null;render();return;}
  if(S.mode=="stand"&&S.concealed[code]){
    S.concealed[code]--;if(!S.concealed[code])delete S.concealed[code];}
  render();
}
function meldFromPool(code){
  const kind=S.mode=="peng"?"pong":(S.mode=="stand"?"pong":"kong");
  const want=kind=="kong"?4:3;
  const isNumber=/^[BTW]/.test(code);
  if(kind=="pong"&&!isNumber&&false){}
  if(/^[SP]/.test(code)){flash("花牌请点花牌行选择");return;}
  const used=countUsed(code);
  if(used+want>4){flash("这种牌超过 4 张");return;}
  if(kind=="pong"){
    const t=[[code,code,code]];
    pushMeld(kind,t[0],false);
  }else{
    pushMeld("kong",[code,code,code,code],S.mode=="angang");
  }
}
function pushMeld(kind,tiles,concealed){
  if(S.melds.length>=4){flash("副露最多 4 组");return;}
  S.melds.push({kind,tiles,concealed});
  S.win=null;render();
}
function chiTap(code){
  if(!/^[BTW]/.test(code)){flash("吃只能吃数牌");return;}
  const tids=S.pending.concat([code]);
  S.pending=tids;
  if(S.pending.length==3){
    const nums=S.pending.map(c=>parseInt(c[1])).sort((a,b)=>a-b);
    const suit=S.pending[0][0];
    const sameSuit=S.pending.every(c=>c[0]===suit);
    if(sameSuit&&nums[0]+1===nums[1]&&nums[1]+1===nums[2]){
      pushMeld("chi",S.pending.slice(),false);S.pending=[];
    }else{flash("吃需要 3 张同花色相连的牌");S.pending=[];}
  }
  render();
}
function countUsed(code){
  let n=S.concealed[code]||0;
  S.melds.forEach(m=>m.tiles.forEach(t=>{if(t===code)n++;}));
  if(S.win===code)n++;
  return n;
}
function chooseWin(code){
  const n=(S.concealed[code]||0)+(S.win===code?1:0);
  if(n>=4&&S.win!==code){flash("这种牌最多 4 张");return;}
  S.win=(S.win===code)?null:code;render();
}
function resetAll(){/* ★ 全部重置（与桌面版一致） */
  S.melds=[];S.concealed={};S.win=null;S.pending=[];S.flowers=[];S.mode="stand";
  S.opts={tsumo:false,last_tile:false,special_a:false,special_b:false,
          round:"东",seat:"东"};
  render();
}
/* 减一张（★ 手机友好入口：牌上的红色数字 / 「已选牌→立牌」里点一张） */
function minus(code){
  if(S.mode=="chi"&&S.pending.length){S.pending.pop();render();return;}
  if(S.win===code){S.win=null;render();return;}
  if(S.concealed[code]){
    S.concealed[code]--;
    if(!S.concealed[code])delete S.concealed[code];
  }
  render();
}
function toggleFlower(code){
  const i=S.flowers.indexOf(code);
  if(i>=0)S.flowers.splice(i,1);else S.flowers.push(code);
  S.flowers=FLOWER.filter(c=>S.flowers.includes(c));   /* 固定顺序（春夏秋冬梅兰竹菊），与桌面版一致 */
  render();
}
function setMode(m){S.mode=m;S.pending=[];render();}
function toggleOpt(k){S.opts[k]=!S.opts[k];
  if(k==="tsumo"){S.opts.special_a=false;S.opts.special_b=false;}
  render();}
function setWind(k,v){S.opts[k]=v;render();}
let flashTimer=null;
function flash(t){el("hint").textContent=t;clearTimeout(flashTimer);
  flashTimer=setTimeout(()=>{el("hint").textContent=baseHint();},2500);}
function baseHint(){return "立牌还差 "+Math.max(0,needConcealed()-concealedList().length)+
  " 张；已选 "+totalTiles()+" 张（副露 "+S.melds.length+" 组）";}

/* ---------- 渲染 ---------- */
function render(){
  el("m_melds").innerHTML=meldHtml();      /* ★ 副露：暗杠要显示为 面·背·背·面 */
  mkTiles(el("m_hand"),concealedList(),"（请在牌池点牌）",true);   /* 点一张 = 减一张 */
  mkTiles(el("m_win"),S.win?[S.win]:[],"（未指定）",true);
  mkTiles(el("m_flower"),S.flowers,"（未选花牌）");
  el("hint").textContent=baseHint();

  /* 模式 */
  el("modes").innerHTML=MODES.map(([k,t])=>
    '<button class="'+(S.mode===k?"on":"")+'" onclick="setMode(\''+k+'\')">'+t+'</button>').join("");
  /* 选项区第 1 行：复选框（☐/☑ 对应桌面版 QCheckBox，文案随「自摸」切换） */
  const t=!!S.opts.tsumo;
  el("opts").innerHTML=
    '<button class="'+(S.opts.tsumo?"on":"")+'" onclick="toggleOpt(\'tsumo\')">'+(S.opts.tsumo?"☑":"☐")+' 自摸</button>'+
    '<button class="'+(S.opts.last_tile?"on":"")+'" onclick="toggleOpt(\'last_tile\')">'+(S.opts.last_tile?"☑":"☐")+' 和绝张</button>'+
    '<button class="'+(S.opts.special_a?"on":"")+'" onclick="toggleOpt(\'special_a\')">'+(S.opts.special_a?"☑":"☐")+' '+(t?"杠上开花":"抢杠和")+'</button>'+
    '<button class="'+(S.opts.special_b?"on":"")+'" onclick="toggleOpt(\'special_b\')">'+(S.opts.special_b?"☑":"☐")+' '+(t?"妙手回春":"海底捞月")+'</button>';
  /* 选项区第 2 行：圈风；第 3 行：风位（●/○ 对应桌面版 QRadioButton） */
  el("rwind").innerHTML=ROUNDS.map(w=>'<button class="'+(S.opts.round===w?"on":"")+
    '" onclick="setWind(\'round\',\''+w+'\')">'+(S.opts.round===w?"●":"○")+' '+w+'风圈</button>').join("");
  el("swind").innerHTML=ROUNDS.map(w=>'<button class="'+(S.opts.seat===w?"on":"")+
    '" onclick="setWind(\'seat\',\''+w+'\')">'+(S.opts.seat===w?"●":"○")+' '+w+'风位</button>').join("");
  /* 牌池（只建一次，刷新只改状态：手机快速连点不会因为重建 DOM 丢点击） */
  updatePool();
  /* 选项区第 4 行：花牌（8 张小图，点一下选/取消，右侧显示张数） */
  updateFlowers();
  compute();
}
/* 花牌行：与桌面版一样，8 张小图 + 「N 张」；只建一次，刷新只改选中状态 */
let FLOWER_BUILT=false;
function buildFlowers(){
  el("flowers").innerHTML=FLOWER.map(code=>
    '<div class="ftile" data-code="'+code+'">'+img(code)+'</div>').join("");
  document.querySelectorAll("#flowers .ftile").forEach(node=>{
    node.addEventListener("click",e=>{e.preventDefault();toggleFlower(node.dataset.code);});
  });
  FLOWER_BUILT=true;
}
function updateFlowers(){
  if(!FLOWER_BUILT){buildFlowers();return;}
  document.querySelectorAll("#flowers .ftile").forEach(node=>{
    node.classList.toggle("sel",S.flowers.includes(node.dataset.code));
  });
  el("fcount").textContent=S.flowers.length+" 张";
}
let POOL_BUILT=false;
function buildPool(){
  el("pool").innerHTML=POOL.map(row=>'<div class="line">'+row.map(code=>
    '<div class="tile" data-code="'+code+'">'+img(code)+
    '<div class="cnt hide" data-minus="'+code+'"></div></div>').join("")+'</div>').join("");
  bindPool();
  bindMinus();
  POOL_BUILT=true;
}
/* ★ 红色角标 = 「−1」按钮：单独绑定并把事件截住，不让它冒泡成「加一张」 */
function bindMinus(){
  document.querySelectorAll("#pool .cnt").forEach(node=>{
    const code=node.dataset.minus;
    const stop=e=>{e.stopPropagation();};
    ["mousedown","mouseup","click","touchstart","touchend","contextmenu"]
      .forEach(ev=>node.addEventListener(ev,stop));
    node.addEventListener("click",e=>{e.stopPropagation();minus(code);});
  });
}
function updatePool(){
  if(!POOL_BUILT){buildPool();return;}
  document.querySelectorAll("#pool .tile").forEach(node=>{
    const code=node.dataset.code;
    const n=(S.concealed[code]||0)+(S.win===code?1:0)+
            (S.mode=="chi"?S.pending.filter(c=>c===code).length:0);
    node.classList.toggle("sel", n>0||S.pending.includes(code));
    const cnt=node.querySelector(".cnt");
    if(cnt){ cnt.textContent=n; cnt.classList.toggle("hide", n===0); }
  });
}
function bindPool(){
  document.querySelectorAll("#pool .tile").forEach(node=>{
    const code=node.dataset.code;
    let timer=null,long=false;
    const start=()=>{long=false;timer=setTimeout(()=>{long=true;longTap(code);},450);};
    const end=()=>{clearTimeout(timer);if(!long)tap(code);};
    node.addEventListener("mousedown",start);
    node.addEventListener("mouseup",end);
    node.addEventListener("mouseleave",()=>clearTimeout(timer));
    node.addEventListener("contextmenu",e=>{e.preventDefault();longTap(code);});
    node.addEventListener("touchstart",e=>{e.preventDefault();start();},{passive:false});
    node.addEventListener("touchend",e=>{e.preventDefault();end();},{passive:false});
  });
}

/* ---------- 算番 / 听牌 ---------- */
async function compute(){
  if(BUSY)return; BUSY=true;
  try{
    const n=concealedList().length, need=needConcealed();
    const withWin=n+(S.win?1:0);
    if(withWin>=need+1){                /* 14-3m：算番（含「13 张 + 指定和张」） */
      el("c_wait").style.display="none";
      const hand=concealedList().slice();      /* ★ 接口要「含和张」的整手牌 */
      if(S.win)hand.push(S.win);
      const body={melds:meldsBody(),concealed:hand,
                  win:S.win||null,options:optsBody()};
      const j=await api("/api/score",body);
      el("tot").textContent=j.total+" 番";
      el("tot").className="tot"+(j.reach_standard?"":" low");
      el("pat").textContent=j.pattern?("牌型："+j.pattern):"";
      el("msg").textContent=j.message||(j.reach_standard?"已达起和标准（8 分）":
                                         "番种合计 "+j.base+" 分，未达 8 分起和标准");
      el("fans").innerHTML=(j.fans||[]).map(f=>'<div class="tag"><b>'+f.value+
        '</b>'+f.name+'</div>').join("");
    }else if(n===need){                 /* 13-3m：列听牌候选 */
      el("c_wait").style.display="";
      try{
        const j=await api("/api/waits_all",{melds:meldsBody(),
          concealed:concealedList(),win:null,options:optsBody()});
        drawWaits(j.waits||[]);
      }catch(e){el("waits").innerHTML='<div class="empty">听牌查询失败：'+e.message+'</div>';}
      el("tot").textContent="—";el("fans").innerHTML="";
      el("msg").textContent="已选满 13 张，点上面的候选或点一张牌作为和张即可出结果。";
      el("tot").className="tot";
    }else{
      el("c_wait").style.display="none";
      el("tot").textContent="—";el("tot").className="tot";
      el("pat").textContent="";el("fans").innerHTML="";
      el("msg").textContent="已选共 "+totalTiles()+" 张，再选 "+
        Math.max(0,(need+1)-totalTiles())+" 张即可算番。";
    }
  }catch(e){
    el("msg").textContent="接口错误："+e.message;
  }finally{BUSY=false;}
}
function drawWaits(list){
  if(!list.length){el("waits").innerHTML='<div class="empty">（没有能和的牌）</div>';return;}
  el("waits").innerHTML=list.map(w=>{
    const low=w.reach_standard?"":" low";
    const on=S.win===w.tile?" on":"";
    return '<div class="wait'+on+'" onclick="chooseWin(\''+w.tile+'\')">'+img(w.tile)+
           '<span>'+NAMES[w.tile]+'</span><span class="'+low+'">'+w.total+'番</span></div>';
  }).join("");
}

/* ---------- 口令 ---------- */
function showDlg(){el("dlg").classList.add("show");}
function hideDlg(){el("dlg").classList.remove("show");}
function setToken(){el("tkin").value=TOKEN;showDlg();}
function saveToken(){TOKEN=el("tkin").value.trim();try{localStorage.setItem("mj_token",TOKEN);}catch(e){}
  hideDlg();render();}
function loadToken(){
  const m=location.search.match(/[?&]token=([^&]+)/);
  if(m){TOKEN=decodeURIComponent(m[1]);try{localStorage.setItem("mj_token",TOKEN);}catch(e){}}
  else{try{TOKEN=localStorage.getItem("mj_token")||"";}catch(e){TOKEN="";}}
}

/* ---------- 启动 ---------- */
(async function(){
  loadToken();
  setLayout(loadLayout(),false);       /* 恢复上次选的布局（默认经典，不影响老布局） */
  try{
    const h=await api("/api/health");
    el("st").textContent="已连接";
  }catch(e){el("st").textContent="未连接";}
  render();
  autoSize();
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape")S.pending=[]&&render();
  });
})();
</script></body></html>"""

DEBUG_HTML = r"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>__APP__ · 接口自测</title>
<style>
 body{font-family:system-ui,"Microsoft YaHei";margin:24px;max-width:960px}
 textarea{width:100%;height:190px;font-family:Consolas,monospace;font-size:13px}
 button{padding:6px 14px;font-size:14px;margin:6px 8px 6px 0}
 pre{background:#f5f7fa;border:1px solid #dde3ec;padding:10px;overflow:auto}
 code{background:#eef2f7;padding:1px 4px;border-radius:3px}
</style>
<h2>__APP__ · 接口自测</h2>
<p>Web 客户端在 <a href="/">/</a>；接口说明见 <a href="/api/help">/api/help</a></p>
<p>端点：<code>/api/health</code> <code>/api/version</code> <code>/api/tiles</code>
<code>/api/fan_table</code> <code>/api/score</code> <code>/api/waits</code></p>
<textarea id="req">{
  "melds": [{"kind":"chi","tiles":["W1","W2","W3"]}],
  "concealed": ["W4","W5","W6","T2","T3","T4","B5","B6","B7","B9","B9"],
  "win": "W6",
  "options": {"tsumo": true, "round_wind": "东", "seat_wind": "南", "flowers": 2}
}</textarea><br>
<button onclick="call('/api/score')">算番 /api/score</button>
<button onclick="call('/api/waits')">听牌 /api/waits</button>
<button onclick="load('/api/tiles')">牌张表</button>
<button onclick="load('/api/fan_table')">番种表</button>
<button onclick="load('/api/version')">版本</button>
<pre id="out">（结果）</pre>
<script>
let TK=new URLSearchParams(location.search).get('token')||'';
function hd(){return TK?{'Content-Type':'application/json','X-Api-Token':TK}
                    :{'Content-Type':'application/json'};}
async function call(path){
  const out=document.getElementById('out');
  try{
    const r=await fetch(path,{method:'POST',headers:hd(),
                              body:document.getElementById('req').value});
    out.textContent=JSON.stringify(await r.json(),null,2);
  }catch(e){out.textContent='请求失败: '+e;}
}
async function load(path){
  const out=document.getElementById('out');
  try{const r=await fetch(path,{headers:hd()});
      out.textContent=JSON.stringify(await r.json(),null,2);}
  catch(e){out.textContent='请求失败: '+e;}
}
</script></html>"""

MANIFEST = {
    "name": APP_NAME + " · Web 版",
    "short_name": "麻将算番",
    "start_url": "./",
    "display": "standalone",
    "background_color": "#f4f6fa",
    "theme_color": "#2f7ff0",
    "icons": [{"src": "/tiles/J1.png", "sizes": "44x60", "type": "image/png"}],
}


def _tile_image_bytes(name: str) -> Optional[bytes]:
    """把《麻将图》里的牌面图读出来给 Web 客户端用（只允许白名单文件名）"""
    if not TILE_FILE_RE.match(name):
        return None
    for d in ("麻将图", "tiles"):
        p = os.path.join(HERE, d, name)
        if os.path.exists(p):
            try:
                with open(p, "rb") as fp:
                    return fp.read()
            except OSError:
                return None
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "MahjongApi/1.0"
    protocol_version = "HTTP/1.1"
    engine: Engine = None          # 由 ApiServer 注入
    token: str = ""
    anon: tuple = ()               # ★ v2.5.0 免口令分组（见 ANON_GROUPS）

    # ---- 基础
    def log_message(self, fmt, *args):        # noqa: A003
        if getattr(self.server, "verbose", False):
            sys.stderr.write("[api] %s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Api-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, obj, status: int = 200, ctype: str = "application/json; charset=utf-8"):
        if isinstance(obj, (dict, list)):
            body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        else:
            body = str(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:                     # noqa: BLE001
            pass

    def _fail(self, message: str, status: int = 400) -> None:
        self._send({"ok": False, "error": message}, status)

    def _anon_ok(self) -> bool:
        """当前请求路径是不是在所勾的「免口令」范围里（口令为空时本就不校验，不用它）"""
        groups = self.anon or ()
        if not groups:
            return False
        path = urlparse(self.path).path.rstrip("/") or "/"
        for g in groups:
            for pref in ANON_GROUPS.get(g, ()):
                if pref.endswith("*"):            # 前缀项（如 /tiles/*）
                    if path.startswith(pref[:-1]):
                        return True
                elif path == pref:                 # 精确项（"/"、"/debug"、"/api/score"…）
                    return True
        return False

    def _check_token(self) -> bool:
        if not self.token:
            return True
        if self._anon_ok():          # ★ 勾了「免口令」的那几类直接放行
            return True
        got = self.headers.get("X-Api-Token") or ""
        if not got:
            q = parse_qs(urlparse(self.path).query)
            got = (q.get("token") or [""])[0]
        if got != self.token:
            self._fail("缺少或错误的 X-Api-Token", 401)
            return False
        return True

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:              # noqa: BLE001
            raise ApiError("请求体不是合法 JSON：%s" % exc)
        if not isinstance(data, dict):
            raise ApiError("请求体必须是 JSON 对象")
        return data

    def _query_body(self) -> dict:
        """把 GET 查询串转成与 POST 相同的结构"""
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        body: dict = {}
        if "melds" in q:
            try:
                body["melds"] = json.loads(q["melds"])
            except Exception:                 # noqa: BLE001
                raise ApiError("melds 参数应为 JSON 数组字符串")
        for key in ("concealed", "counts", "hand"):
            if key in q:
                try:
                    val = json.loads(q[key])
                except Exception:             # noqa: BLE001
                    val = [c for c in q[key].split(",") if c]
                body["concealed" if key != "counts" else "counts"] = val
                break
        if "counts" in body:
            body["concealed"] = body.pop("counts")
        if "win" in q:
            body["win"] = q["win"]
        opts = {}
        for key in ("tsumo", "last_tile", "rob_kong", "kong_bloom",
                    "last_draw", "last_discard"):
            if key in q:
                opts[key] = str(q[key]).lower() in ("1", "true", "yes", "on")
        for key in ("round_wind", "seat_wind"):
            if key in q:
                opts[key] = q[key]
        if "flowers" in q:
            opts["flowers"] = q["flowers"]
        if opts:
            body["options"] = opts
        return body

    # ---- 方法
    def do_OPTIONS(self):                     # noqa: N802
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_GET(self):                         # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        # ★ v2.5.0：静态资源也走一次口令检查（它们默认在免口令白名单里；
        #   若用户在「免口令访问设置」里把 Web 客户端/自测页关了，则会要口令 ——
        #   这时用 http://ip:端口/?token=口令 打开页面即可）
        if not self._check_token():
            return
        # ---- 静态资源
        if path in ("/", "/web", "/index.html"):
            return self._send(WEB_CLIENT.replace("__APP__", APP_NAME),
                              ctype="text/html; charset=utf-8")
        if path == "/debug":
            return self._send(DEBUG_HTML.replace("__APP__", APP_NAME),
                              ctype="text/html; charset=utf-8")
        if path == "/manifest.webmanifest":
            return self._send(MANIFEST,
                              ctype="application/manifest+json; charset=utf-8")
        if path in ("/favicon.ico", "/apple-touch-icon.png"):
            data = _tile_image_bytes("J1.png")   # 用「中」当图标
            if data is None:
                return self._fail("没有可用的图标", 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self._cors()
            self.end_headers()
            try:
                self.wfile.write(data)
            except Exception:                 # noqa: BLE001
                pass
            return
        if path.startswith("/tiles/"):
            name = path.split("/")[-1]
            data = _tile_image_bytes(name)
            if data is None:
                return self._fail("找不到牌面图：%s" % name, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self._cors()
            self.end_headers()
            try:
                self.wfile.write(data)
            except Exception:                 # noqa: BLE001
                pass
            return
        try:
            if path == "/api/help":
                return self._send(HELP_TEXT, ctype="text/plain; charset=utf-8")
            if path == "/api/health":
                return self._send({"ok": True, "server": API_NAME})
            if path == "/api/version":
                return self._send(self.engine.version())
            if path == "/api/tiles":
                return self._send({"ok": True, "tiles": self.engine.tiles_table()})
            if path == "/api/fan_table":
                return self._send({"ok": True, "table": self.engine.fan_table()})
            if path == "/api/score":
                return self._send(self.engine.score(self._query_body()))
            if path in ("/api/waits", "/api/wins", "/api/waits_all"):
                return self._send(self.engine.waits(self._query_body(),
                                                    only_reach=path != "/api/waits_all"))
            self._fail("未知接口：%s（见 /api/help）" % path, 404)
        except ApiError as exc:
            self._fail(exc.message, exc.status)
        except Exception as exc:               # noqa: BLE001
            self._fail("内部错误：%r" % (exc,), 500)

    def do_POST(self):                        # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if not self._check_token():
            return
        try:
            body = self._body()
            if path == "/api/score":
                return self._send(self.engine.score(body))
            if path in ("/api/waits", "/api/wins", "/api/waits_all"):
                return self._send(self.engine.waits(body,
                                                    only_reach=path != "/api/waits_all"))
            if path in ("/api/health", "/api/version"):
                return self.do_GET()
            self._fail("未知接口：%s（见 /api/help）" % path, 404)
        except ApiError as exc:
            self._fail(exc.message, exc.status)
        except Exception as exc:               # noqa: BLE001
            self._fail("内部错误：%r" % (exc,), 500)


class ApiServer:
    """本地 API 服务（可在主程序里内嵌启动，也可单独运行）"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 token: str = "", rules_path: Optional[str] = None,
                 verbose: bool = False, anon=None):
        self.host = host
        self.port = int(port)
        self.token = token or ""
        # ★ v2.5.0 免口令分组：anon=None 表示「用默认」（web+debug，与旧版行为一致）；
        #   anon=() 才是「全部要口令」。
        self.anon = tuple(ANON_DEFAULT if anon is None else anon)
        self.verbose = verbose
        self.engine = Engine(rules_path)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ---- 生命周期
    @property
    def running(self) -> bool:
        return self._httpd is not None

    @property
    def port_actual(self) -> int:
        if self._httpd is None:
            return self.port
        try:
            return int(self._httpd.server_address[1])
        except Exception:                     # noqa: BLE001
            return self.port

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return "http://%s:%d" % (host, self.port_actual)

    def start(self) -> str:
        if self._httpd is not None:
            return self.url
        handler = type("_Handler", (Handler,),
                       {"engine": self.engine, "token": self.token,
                        "anon": self.anon})
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError as exc:
            raise ApiError("端口 %d 无法监听（%s）" % (self.port, exc))
        self._httpd.daemon_threads = True
        self._httpd.verbose = self.verbose
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="mahjong-api", daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:                 # noqa: BLE001
                pass
            try:
                httpd.server_close()
            except Exception:                 # noqa: BLE001
                pass
        self._thread = None


def lan_ip() -> str:
    """尽力猜出局域网 IP（仅供提示用）"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:                         # noqa: BLE001
        return "127.0.0.1"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="%s · 本地 HTTP API" % APP_NAME)
    ap.add_argument("--host", default=DEFAULT_HOST,
                    help="监听地址，默认 %s（仅本机）；局域网请用 0.0.0.0" % DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口，默认 %d" % DEFAULT_PORT)
    ap.add_argument("--token", default="", help="可选口令：请求头 X-Api-Token 或 ?token=")
    ap.add_argument("--anon", default=None,
                    help="免口令分组（逗号分隔）：web,debug,info,score,waits；"
                         "none = 全部要口令；默认 " + ",".join(ANON_DEFAULT))
    ap.add_argument("--verbose", action="store_true", help="打印访问日志")
    args = ap.parse_args(argv)
    if args.anon is None:
        anon = list(ANON_DEFAULT)
    elif str(args.anon).strip().lower() in ("", "none", "-"):
        anon = []
    else:
        anon = [k.strip() for k in str(args.anon).split(",") if k.strip()]

    srv = ApiServer(args.host, args.port, args.token, verbose=args.verbose,
                    anon=anon)
    try:
        url = srv.start()
    except ApiError as exc:
        print("启动失败：%s" % exc.message)
        return 1
    print("%s · Web 版 / 本地 API 已启动" % APP_NAME)
    print("  Web 本机 : %s        （手机/电脑浏览器打开就能算番）" % url)
    if args.host == "0.0.0.0":
        tip = "http://%s:%d/" % (lan_ip(), srv.port_actual)
        if args.token:
            tip += "?token=" + args.token
        print("  手机/平板: %s   （同一 WiFi 直接打开）" % tip)
    if args.token:
        print("  口令      : %s（请求头 X-Api-Token: %s）" % (args.token, args.token))
        print("  免口令    : %s（改 --anon 可调）"
              % ("、".join(anon) if anon else "无（全部要口令）"))
    print("  JSON 接口: %s/api/help     接口自测页: %s/debug     按 Ctrl+C 结束"
          % (url, url))
    try:
        while True:
            srv._thread.join(0.5)             # noqa: SLF001
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        srv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
