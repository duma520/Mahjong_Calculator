# -*- coding: utf-8 -*-
"""国标麻将算番器 —— 本地 HTTP API（JSON）

把算番引擎 `mahjong_core.MahjongFanCalculator` 封装成一组 HTTP 接口，
方便别的程序（脚本 / 安卓端 / 网页 / 微信小程序 / Excel）直接调用算番与听牌。

单独运行：
    python mahjong_api.py [--host 127.0.0.1] [--port 8718] [--token 口令] [--verbose]
也可以由主程序内嵌启动：mahjong_gui.py →「工具 → 启动本地 API」
（两者用同一份代码，行为一致）。

★ 默认只监听 127.0.0.1（仅本机可访问）。若要对局域网/安卓真机开放，
   显式传 --host 0.0.0.0，并建议同时用 --token 设一个口令（请求头 X-Api-Token）。

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
:root{--blue:#2f7ff0;--bg:#f4f6fa;--card:#fff;--line:#dde3ec;--grey:#6b7684;--red:#e74c3c}
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
.tiles{display:flex;gap:4px;flex-wrap:wrap;align-items:center}
.tiles img{width:34px;height:46px;display:block}
.tiles .ph{width:34px;height:46px;border:1px dashed var(--line);border-radius:4px;
 display:flex;align-items:center;justify-content:center;color:#b9c2cd;font-size:11px}
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
.wait img{width:28px;height:38px}
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
.tile{position:relative;width:38px;height:52px;border:2px solid transparent;border-radius:7px;
 background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer}
.tile img{width:32px;height:44px;pointer-events:none}
.tile.sel{border-color:var(--blue);background:#eaf2ff}
.tile .cnt{position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;border-radius:8px;
 background:var(--red);color:#fff;font-size:10px;line-height:16px;text-align:center;padding:0 3px}
.tile .cnt.hide{display:none}
/* ★ 牌池每行必须横排（索/筒/万/字牌 4 行，每行 9/9/9/7 张）——
   不能只靠祖先 .pool 类（v2.4.4 漏过一次：类名没带上，结果每张牌各占一行） */
#pool .line,.pool .line{display:flex;gap:3px;flex-wrap:wrap;margin:0 0 3px}
#pool .line:last-child,.pool .line:last-child{margin-bottom:0}
/* ★ 花牌小图（选项区第 4 行，与桌面版 FLOWER_SIZE 一样比普通牌小一圈） */
.ftile{position:relative;width:34px;height:46px;border:2px solid transparent;border-radius:7px;
 background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer}
.ftile img{width:28px;height:38px;pointer-events:none}
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
    <h2>牌选择区（点一下加一张，长按 / 右键减一张）</h2>
    <div class="pool" id="pool"></div>
  </div>

  <!-- ② 模式行（立牌/吃/碰/明杠/暗杠 + 重置） -->
  <div class="card">
    <div class="mod" id="modes"></div>
    <div class="btns" style="margin-top:8px">
      <button class="warn" onclick="resetAll()">重置</button>
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
function img(code){return '<img src="/tiles/'+code+'.png" alt="'+code+'" title="'+(NAMES[code]||"")+'">';}
function mkTiles(box,codes,emptyText){
  box.innerHTML = codes.length? codes.map(img).join("")
    : '<div class="empty">'+(emptyText||"（空）")+'</div>';
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
  mkTiles(el("m_melds"),S.melds.flatMap(m=>m.tiles),"（暂无吃碰杠）");
  mkTiles(el("m_hand"),concealedList(),"（请在牌池点牌）");
  mkTiles(el("m_win"),S.win?[S.win]:[],"（未指定）");
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
    '<div class="cnt hide"></div></div>').join("")+'</div>').join("");
  bindPool();
  POOL_BUILT=true;
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
  try{
    const h=await api("/api/health");
    el("st").textContent="已连接";
  }catch(e){el("st").textContent="未连接";}
  render();
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

    def _check_token(self) -> bool:
        if not self.token:
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
        # ---- 静态资源（不需要口令；页面自己再用 X-Api-Token 调 /api/*）
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
        if not self._check_token():
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
                 verbose: bool = False):
        self.host = host
        self.port = int(port)
        self.token = token or ""
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
                       {"engine": self.engine, "token": self.token})
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
    ap.add_argument("--verbose", action="store_true", help="打印访问日志")
    args = ap.parse_args(argv)

    srv = ApiServer(args.host, args.port, args.token, verbose=args.verbose)
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
