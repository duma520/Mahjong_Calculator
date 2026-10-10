# -*- coding: utf-8 -*-
"""国标麻将算番器 —— **Web 版（手机/平板浏览器算番）的服务端**，附带页面内部用的 JSON 路由

★ 先分清两件事（v2.6.0）：
    · **给其它程序调用的「API」是 `mahjong_core`，不是这个文件**：
        能 import 的： from mahjong_core import MahjongFanCalculator   # 或 score_hand()
        不能 import 的： Mahjong_Calculator.exe --hand "..." --json
                        （开发时用 python mahjong_core.py --hand "..." --json）
        这两种方式都**不需要 HTTP、不需要端口、不需要先启动谁**。
    · ★ v2.9.0 读番：算完番可以把「合计 N 番」念出来（音频在程序目录的《数字》子目录）。
      **别的程序要用不用复制我们的文件** —— 把程序目录告诉它就行：
        · 进程内： score_hand(..., readout=True, base_dir=r"D:\麻将\Mahjong_Calculator",
                             voice_set="鲸宝")
        · 命令行： Mahjong_Calculator.exe --hand "..." --readout --dir "D:\麻将\Mahjong_Calculator"
                   （加 `--voice-set 鲸宝` 换语音包；默认用「女声」）
        · HTTP  ： GET /api/readout?total=123  → 中文读法 + 每段音频的文件名与下载地址
                   （加 `&set=女声` 换语音包）
    · ★ v2.9.3 《数字》下可以放**多套**录音（一套一个子目录，目录名＝语音包名）；
    · 本文件只为**浏览器**服务：内联一份单文件 Web 客户端（手机/平板打开就能算番），
      `/api/*` 是这份页面自己用的路由。**默认不需要口令**（想加门槛再传 --token）。

单独运行（起 Web 版服务）：
    python mahjong_api.py [--host 127.0.0.1] [--port 8718] [--token 口令] [--anon web,info] [--verbose]
也可以由主程序内嵌启动：Mahjong_Calculator.py →「设置 → Web 版 → 启动 Web 版」（Ctrl+Alt+A）
（两者用同一份代码，行为一致）。

★ 默认只监听 127.0.0.1（仅本机可访问）。若要对局域网/手机开放，
   显式传 --host 0.0.0.0（建议只在自家网络用；需要门槛时再加 --token）。

★ 免口令白名单（v2.5.0）：设了口令后，可以**分项**允许某些东西「不用口令也能用」，
   主程序里在「设置 → Web 版 → 免口令访问设置…」逐项勾选（含 Web 客户端）。分组：
     web   = Web 客户端页面 + 牌面图（/、/web、/index.html、/manifest、/favicon、/tiles/*）
     debug = 自测页 /debug        info = /api/health·/version·/tiles·/fan_table·/help
     score = /api/score           waits = /api/waits·/waits_all·/wins
   默认等同于旧行为：web + debug 免口令，其余 `/api/*` 要口令。
   单独跑服务时用 `--anon web,score` 指定（`--anon none` = 全部要口令）。

★ Web 版界面布局与桌面版一致（v2.4.4，改 Web 布局请先看桌面版怎么排）：
    ① 牌选择区（索 / 筒 / 万 / 字牌 四行，点一下加一张、长按或右键减一张；
       ★ v2.8.0：红色数字只显示「已选张数」，点它不再减牌）
    ② 模式行（★ v2.9.5：重置 + 立牌/吃/碰/明杠/暗杠，重置在最左边；重置 = 全部复位；
       ★ v2.8.0：再点一次当前模式按钮 = 取消该模式，回到「立牌」；★ 重置要建在模式按钮之前）
    ③ 选项区固定四行：□自摸 □和绝张 □抢杠和/杠上开花 □海底捞月/妙手回春 ／
       风圈 ／ 风位 ／ 花牌（8 张小图 + 「N 张」；花牌**不在牌池里**）
    ④ 已选牌（副露 / 立牌 / 和张 / 花牌 + 提示行）→ ⑤ 听牌候选 → ⑥ 算番结果
       ★ v2.8.1：**已选牌这一整块都能点掉**，不必整手「重置」—— 点副露任意一张（含暗杠牌背）
       ＝撤销那一组吃/碰/杠；点立牌一张＝减一张；点和张＝取消和张；点花牌行一张＝取消那张花牌。

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
    ★ v2.9.0 读番（把「合计 N 番」念出来）：
    GET  /api/readout?total=123   念法 + 音频清单：[{"word","file","url"}]（别的程序直接放音）
    POST /api/readout             同上（JSON 体：{"total":123,"speak":false}）
    GET  /audio/<文件名>          取读番音频片段（牌面图那样按白名单放行）
    另外 /api/score 的请求体加 "readout":true 会在结果里附 "readout" 字段；
    加 "speak":true 则在**这台电脑上**念出来（手机端请用 /api/readout 自己放音）。
    ★ v2.9.3 选语音包：《数字》下可以放**多套**录音（一套一个子目录，目录名就是包名，
    如 `数字\\鲸宝\\`、`数字\\女声\\`）。用哪一套一共有三个层次，就近覆盖：
        ① 请求参数：`/api/readout?total=123&set=女声`（POST 里写 "set"）；
        ② 服务器端默认：桌面端「设置 → 通用 → 语音包」（默认「女声」），
           起服务时也可用 `--voice-set 名字` 指定；/api/version 会报 voice_set / voice_sets；
        ③ 页面自己的选择：Web 页面上「语音：」下拉（存在浏览器本地，刷新还在）。
    取音频：默认套用 `/audio/<文件名>`，指定套用 `/audio/<语音包>/<文件名>`
    （读番接口返回的 url 已经带好包名，页面直接放就行）。
    名字不认识 / 那套被删了会自动回退（默认包 → 《数字》根目录 → 第一个可用包），不会没声音。
    ★ v2.9.1 自动读番的默认值：桌面端「设置 → 通用 → 默认开启自动读番」（默认开）会把
    Web 页面「🔊 读番」的初始状态也设成开（渲染进页面的 SPEAK_DEFAULT），
    所以**无论用桌面端还是手机/平板，都默认自动读番**；页面自己点过就以页面选择为准。
    起服务时可用 `--speak-default 0` 把页面默认改成关；/api/version 会报 speak_default。

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
              "flower_tiles":["S1","P4"]},     # 也可直接给花牌代码
  "readout": true,                             # ★ v2.9.0 结果里附读番（念法与音频清单）
  "speak": false                               # ★ 顺手在本机念出来（手机端用 /api/readout）
}
读番相关参数（★ v2.9.3）：`set=女声` 选用《数字》下的哪一套录音（不给＝服务器端默认）。

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
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

from mahjong_stats import (StatsDB, hand_sig, user_key_from,  # noqa: E402
                           fans_text, fans_split)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mahjong_core import (MahjongFanCalculator, Meld, Options, TILE_CODES,  # noqa: E402
                          VOICE_DIR_NAME, VOICE_SET_DEFAULT, VoicePlayer, code_of,
                          count_voice_clips, find_voice_dir, name_of, num_of, readout_info,
                          resolve_voice_dir, suit_of, tile_of, voice_name_ok,
                          voice_set_label, voice_set_names, voice_set_of, voice_set_ok,
                          voice_sets)

APP_NAME = "国标麻将算番器"
# ★ v2.9.7：Web 客户端（手机/平板/浏览器）的标题 —— 与桌面端区分开
WEB_TITLE = "国标算番器客户端"
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

    def __init__(self, rules_path: Optional[str] = None, base_dir: Optional[str] = None,
                 speak_default: bool = True, voice_set: Optional[str] = None):
        self._lock = threading.Lock()
        self._calc = MahjongFanCalculator(rules_path=rules_path)
        # ★ v2.9.0：读番音频（《数字》目录）从哪儿找 —— 默认就找本文件所在目录
        self.base_dir = base_dir
        # ★ v2.9.1：Web 页面「🔊 读番」的默认状态（桌面端设置里的「默认开启自动读番」）
        self.speak_default = bool(speak_default)
        # ★ v2.9.3：**服务器端默认用哪一套录音**（《数字》下的子目录名，如「鲸宝」；
        #   空＝用默认包 VOICE_SET_DEFAULT）。请求里带 `set=` 可以覆盖它。
        self.voice_set = str(voice_set or "")
        self._voice: Optional[VoicePlayer] = None

    # ---- 读番（★ v2.9.0；★ v2.9.3 支持选语音包）
    def voice_dir(self, voice_set: Optional[str] = None) -> Optional[str]:
        """当前该用哪一套录音目录（voice_set=None → 用服务器端默认）"""
        name = self.voice_set if voice_set is None else str(voice_set or "")
        return resolve_voice_dir(name, self.base_dir)

    @staticmethod
    def _with_urls(info: dict) -> dict:
        """给每段音频补一个下载地址（文件名是中文，按 URL 规范转义）

        ★ v2.9.3：地址里带上语音包（`/audio/<语音包>/<文件>`），这样页面选了哪套就播哪套；
        根目录那套（没有包名）仍是 `/audio/<文件>`。
        """
        pack = str(info.get("voice_set") or "")
        head = "/audio/" + (quote(pack) + "/" if pack else "")
        info["clips"] = [dict(c, url=(head + quote(c["file"])) if c["file"] else "")
                         for c in info["clips"]]
        return info

    def readout(self, total: int, prefix: bool = True,
                voice_set: Optional[str] = None) -> dict:
        """「合计 N 番」怎么念：中文读法 + 每段音频（别的程序拿去自己放音即可）"""
        return self._with_urls(readout_info(total, base_dir=self.base_dir, prefix=prefix,
                                            voice_set=self.voice_set
                                            if voice_set is None else voice_set))

    def speak(self, total: int, prefix: bool = True,
              voice_set: Optional[str] = None) -> dict:
        """在本机念出来（Windows）；手机/浏览器端请拿 /api/readout 自己放音"""
        with self._lock:
            if self._voice is None:
                self._voice = VoicePlayer()
            voice = self._voice
        info = readout_info(total, base_dir=self.base_dir, prefix=prefix,
                            voice_set=self.voice_set if voice_set is None else voice_set)
        played = False
        if info["ok"]:
            played = voice.play([c["path"] for c in info["clips"]])
        self._with_urls(info)
        info["played"] = played
        return info

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

    def readout_request(self, body: dict) -> dict:
        """读番接口的请求体解析（GET 查询串 / POST JSON 共用）

        {"total":123,"prefix":true,"speak":false,"set":"女声"} → 念法 + 音频清单
        ★ v2.9.3：`set`（别名 voice_set / pack）＝用《数字》下哪一套录音；不给就用服务器端默认。
        """
        raw = body.get("total", body.get("n"))
        if raw in (None, ""):
            raise ApiError("缺少 total（要念的番数），例：/api/readout?total=123")
        try:
            total = int(str(raw).strip())
        except Exception:                             # noqa: BLE001
            raise ApiError("total 必须是整数，收到 %r" % (raw,))
        if total < 0:
            raise ApiError("total 不能是负数，收到 %d" % total)
        prefix = body.get("prefix")
        with_prefix = True if prefix is None else \
            str(prefix).lower() not in ("0", "false", "no", "off")
        # ★ v2.9.3：语音包（不给＝服务器端默认；给了就用它，名字不认识会自动回退）
        pack = None
        for key in ("set", "voice_set", "pack"):
            if body.get(key) not in (None, ""):
                pack = str(body[key]).strip()
                break
        if body.get("speak"):
            return self.speak(total, prefix=with_prefix, voice_set=pack)
        return self.readout(total, prefix=with_prefix, voice_set=pack)

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
        # ★ v2.9.0 读番：只要 "readout"（清单）/ "speak"（本机出声）任一为真就附上读番信息
        if body.get("readout") or body.get("speak"):
            out["readout"] = (self.speak(res.total) if body.get("speak")
                              else self.readout(res.total))
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
        voice_dir = self.voice_dir()
        sets = voice_sets(self.base_dir)
        return {"ok": True, "server": API_NAME, "app": APP_NAME,
                "engine_fans": len(getattr(self._calc, "fan_values", {})),
                "rules_file": os.path.basename(rules) if rules else "",
                "rules_loaded": bool(getattr(self._calc, "rules", None)),
                # ★ v2.9.0 读番：音频目录 + 片段数 + 本机能不能出声
                # ★ v2.9.3：语音包（可选哪几套 / 服务器端默认用哪一套）
                "voice_dir": voice_dir or "",
                "voice_clips": count_voice_clips(self.base_dir, self.voice_set),
                "voice_set": voice_set_of(voice_dir),
                "voice_set_default": VOICE_SET_DEFAULT,
                "voice_set_server": self.voice_set,
                "voice_sets": [{"name": s["name"], "label": voice_set_label(str(s["name"])),
                                "clips": s["clips"]} for s in sets],
                "voice_can_play": VoicePlayer.available(),
                # ★ v2.9.1：Web 页面「🔊 读番」的默认状态（别的程序也能据此跟着念）
                "speak_default": bool(self.speak_default)}


# ------------------------------------------------------------------ HTTP 层

HELP_TEXT = __doc__

# ------------------------------------------------------------------ 牌面图
# Web 客户端直接用程序自带的《麻将图》里的 PNG（B1~B9/T1~T9/W1~W9/F1~F4/J1~J3/S1~S4/P1~P4/empty）
import re                                                      # noqa: E402

TILE_FILE_RE = re.compile(r"^(?:B[1-9]|T[1-9]|W[1-9]|F[1-4]|J[1-3]|S[1-4]|P[1-4]|empty)\.png$")

# ★ v2.9.0：读番音频（《数字》目录）按白名单放行，别的文件名一律 404。
# ★ v2.9.2：录音改成「一个文件＝一个中文词」，白名单也随之改成**词形匹配**
#   （合计 / 番 / 1~3 个中文数字词 + .mp3/.wav）—— 重录增删片段都不用改代码。
#   防目录穿越靠 `voice_name_ok()` 里「不含 / 与 \\」那两条。

# ------------------------------------------------------------------ 免口令白名单
# ★ v2.5.0：设了口令后，哪些东西可以「不用口令也能用」由调用方（GUI 设置）逐项勾选。
#   口令为空时本来就不校验口令，这里不生效。
#   分组表：key → 该组的路径；**以 "*" 结尾表示前缀匹配**，否则要求路径完全相等
#   （注意 "/" 必须当「精确项」——写成前缀就会把一切路径都放行）
ANON_GROUPS = {
    "web":   ("/", "/web", "/index.html", "/manifest.webmanifest",
               "/favicon.ico", "/apple-touch-icon.png", "/tiles/*",
               "/audio/*"),          # ★ v2.9.0：读番音频跟牌面图一样，属于「Web 客户端」资源
    "debug": ("/debug",),
    "info":  ("/api/health", "/api/version", "/api/tiles",
               "/api/fan_table", "/api/help",
               "/api/readout"),      # ★ v2.9.0：读番属于查询类接口
    "score": ("/api/score",
               "/api/stats",
               "/api/stats_detail",   # ★ v2.9.9：逐手明细跟统计走（不然点明细会被 401 挡回）
               "/api/set_nick"),      # ★ v2.9.12：设昵称跟算番走（不然免口令的手机设不了）
    "waits": ("/api/waits", "/api/waits_all", "/api/wins"),
}
# 默认值：与 v2.4.x 行为完全一致（Web 页面/牌面图/自测页免口令，`/api/*` 要口令）
ANON_DEFAULT = ("web", "debug")

# ★ v2.7.5：Web 页面模式行里的两个「工具按钮」——默认**都不显示**
#   （对只想算番的人来说它们是干扰：一个是开发者自测页，一个是换口令）。
#   想用就在桌面端「设置 → Web 版 → 页面按钮显示设置…」里勾上（或命令行 --show debug,token）。
WEB_SHOW_ITEMS = (
    ("debug", "接口自测页", "页面上的「接口自测页」按钮（打开 /debug 表单页，逐项试接口）"),
    ("token", "换口令", "页面上的「换口令」按钮（换成新口令后记在浏览器里）"),
)
WEB_SHOW_KEYS = [k for k, _, _ in WEB_SHOW_ITEMS]
WEB_SHOW_DEFAULT: Tuple[str, ...] = ()      # 默认：两个都不显示

# ★ v2.9.7：统计面板「显示哪些列」—— 两端（桌面端统计窗口 / Web 统计弹窗）共用同一套 key
STATS_COL_ITEMS = (
    ("user",    "用户"),
    ("nick",    "昵称"),        # ★ v2.9.12：用户在客户端「设置」里自己填的
    ("ctype",   "客户端"),
    ("os",      "系统"),        # ★ v2.9.12：鸿蒙 6.0 / Android / iOS 17.0
    ("browser", "浏览器"),      # ★ v2.9.12：微信 / Chrome / 华为浏览器
    ("dev",     "设备型号"),    # ★ v2.9.12：三星 SM-S918U（安卓16+/鸿蒙/iOS 常为空）
    ("ip",      "IP"),
    ("ua",      "UA（设备）"),
    ("fan",     "合计番数"),
    ("cnt",     "次数"),
    ("reach",   "达标"),
    ("last",    "最近"),
    ("fans",    "番种"),        # ★ v2.9.9：番种汇总（「无番和×3、碰碰和×1」）
)
STATS_COL_KEYS = tuple(k for k, _ in STATS_COL_ITEMS)
# Web 客户端默认＝用户指定的 7 列 + v2.9.12 认人四件套（不含 UA：手机上 UA 基本没用，
# 还占地方；也不含「番种」——那串字太长，手机上会挤爆；想要就在「设置 → 统计列」里勾）
STATS_COLS_WEB_DEFAULT = ("user", "nick", "ctype", "os", "browser", "dev",
                          "ip", "fan", "cnt", "reach", "last")
# 桌面端默认＝全部列全开（能把 UUID / IP / UA / 番种都摊开，方便认人）
STATS_COLS_DESKTOP_DEFAULT = STATS_COL_KEYS
# ★ v2.9.9：老设置里没有的新列，启动时自动补到末尾（用户从没见过这一列，
#   不算违背他的选择；只有他**主动勾掉过**才尊重他的选择——见 stats_cols_new_merged）
STATS_COL_NEW_KEYS = ("fans",) + ("nick", "os", "browser", "dev")   # v2.9.12

# ★ v2.9.10：**逐手明细**「显示哪些列」—— 与统计列同一套机制，两端（桌面明细窗口 /
#   Web 明细面板）共用同一套 key。明细是 v2.9.9 才有的，所以没有「老设置」要补。
DETAIL_COL_ITEMS = (
    ("day",     "日期"),
    ("time",    "时间（毫秒）"),
    ("nick",    "昵称"),        # ★ v2.9.12：这一手牌时该用户填的昵称（改名不改历史）
    ("ctype",   "客户端"),
    ("os",      "系统"),        # ★ v2.9.12
    ("browser", "浏览器"),      # ★ v2.9.12
    ("dev",     "设备型号"),    # ★ v2.9.12
    ("ip",      "IP"),
    ("ua",      "UA（设备）"),
    ("fan",     "番数"),
    ("base",    "起番"),
    ("reach",   "达标"),
    ("fans_n",  "番种数"),
    ("fans",    "番种"),
)
DETAIL_COL_KEYS = tuple(k for k, _ in DETAIL_COL_ITEMS)
# Web 客户端默认：原来 6 列 + v2.9.12 认人四件套（手机上横向放不下 14 列，
# 先给「认得出这一手」最有用的几列；想要剩下的在「设置 → 明细列」里勾上）
DETAIL_COLS_WEB_DEFAULT = ("time", "nick", "ctype", "os", "browser", "dev",
                           "ip", "fan", "reach", "fans")
# 桌面端默认＝全部列全开
DETAIL_COLS_DESKTOP_DEFAULT = DETAIL_COL_KEYS
# ★ v2.9.12：明细列第一次有新列要补（老用户升级后自动勾上，不勾就永远看不到）
DETAIL_COL_NEW_KEYS = ("nick", "os", "browser", "dev")


def _cols_normalize(val, keys, default) -> tuple:
    """列序规整的**唯一实现**（统计列 / 明细列共用）：去非法、去重、保序。

    全部不合法就退回默认值；**绝不返回空**（空列＝表格全白，等于功能坏了）。
    """
    if isinstance(val, (list, tuple)):
        res, seen = [], set()
        for k in val:
            k = str(k)
            if k in keys and k not in seen:
                seen.add(k)
                res.append(k)
        if res:
            return tuple(res)
    return tuple(default)


def _cols_new_merged(val, keys, default, new_keys) -> tuple:
    """老设置 + 新增列：把用户没见过的**新列**补到末尾（统计列 / 明细列共用）"""
    cur = list(_cols_normalize(val, keys, default))
    for k in new_keys:
        if k in keys and k not in cur:
            cur.append(k)
    return tuple(cur)


def stats_cols_normalize(val, default=STATS_COLS_WEB_DEFAULT) -> tuple:
    """把任意输入（JSON / 设置项）规整成合法的**统计列**序"""
    return _cols_normalize(val, STATS_COL_KEYS, default)


def detail_cols_normalize(val, default=DETAIL_COLS_WEB_DEFAULT) -> tuple:
    """把任意输入规整成合法的**明细列**序（★ v2.9.10）"""
    return _cols_normalize(val, DETAIL_COL_KEYS, default)


def stats_cols_new_merged(val, default=STATS_COLS_DESKTOP_DEFAULT,
                          new_keys=STATS_COL_NEW_KEYS) -> tuple:
    """★ v2.9.9：老设置 + 新增列 —— 把用户没见过的**新列**补到末尾

    为什么需要：v2.9.8 存下来的设置里没有 `fans`，如果直接沿用，用户升级后
    「番种」列永远不出现，等于新功能白做。但也不能无脑用默认值覆盖 —— 那会
    把用户自己勾掉的列又勾回来。所以只补「新版本才有的 key」，且补到末尾。

    ★ 用户**主动勾掉过**的情况无法区分（存下来的都是"不在列表里"），这一点
      在文档里写明了：新列首次出现默认给用户看，不想要再勾掉一次即可。
    """
    return _cols_new_merged(val, STATS_COL_KEYS, default, new_keys)


def detail_cols_new_merged(val, default=DETAIL_COLS_DESKTOP_DEFAULT,
                           new_keys=DETAIL_COL_NEW_KEYS) -> tuple:
    """★ v2.9.10：老设置 + 明细新增列（当前没有新增列，保留给以后加列用）"""
    return _cols_new_merged(val, DETAIL_COL_KEYS, default, new_keys)

WEB_CLIENT = r"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#2f7ff0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="麻将算番">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/tiles/J1.png">
<title>__APP_TITLE__</title>
<style>
:root{--blue:#2f7ff0;--bg:#f4f6fa;--card:#fff;--line:#dde3ec;--grey:#6b7684;--red:#e74c3c;
 /* ★ v2.7.0 牌尺寸全部改成变量：这组默认值 = 「布局：38px（默认）」，
    与老版本逐个像素一致（38/52、34/46、28/38、间距 3/4）；
    ★ v2.8.4 起其余档位由 JS 按 W/38 **等比缩放这 12 个值**（不再看屏幕），
    选「38px（默认）」时清掉内联变量回到这里 ⇒ 老布局一个像素都不差 */
 --tw:38px;--th:52px;--pw:34px;--ph:46px;
 --gw:4px;--pgap:3px;
 --fw:34px;--fh:46px;--fwi:28px;--fhi:38px;
 --ww:28px;--wh:38px;
 /* ★ v2.7.6 按钮尺寸档位（客户端模式行「按钮：…」循环切换，共 5 档）：
    这组默认值 = 升级前的样子（字号 15px、内边距 7/11px）——
    选「默认（3/5）」这一档时 JS 会把内联变量清掉、回落到这里 ⇒ 与老版本逐像素一致 */
 --btn-fs:15px;--btn-pad-y:7px;--btn-pad-x:11px}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:#1f2937;
 font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;font-size:15px}
header{position:sticky;top:0;z-index:9;background:var(--blue);color:#fff;
 padding:10px 12px;display:flex;align-items:center;gap:8px;box-shadow:0 1px 6px #0002;
 /* ★ v2.9.7：标题要**严格居中**（不受左右控件宽度影响），用绝对定位实现。
    position:sticky 本身就提供定位上下文，h1 的 left:50% 以 header 为基准 */
 justify-content:space-between}
/* ★ v2.9.7：标题绝对定位到正中间（严格居中，不受左右控件宽度影响）。
   窄屏兜底：屏幕太窄时标题改为常规流、铺满一行，避免和两侧下拉重叠 */
header h1{font-size:16px;margin:0;font-weight:600;
 position:absolute;left:50%;transform:translateX(-50%);
 white-space:nowrap;pointer-events:none}
header .st{font-size:11px;opacity:.9;white-space:nowrap;margin-left:auto}
/* ★ v2.9.7：顶栏里的「布局/按键」——同尺寸变量，跟底部按钮一起缩放 */
header .selwrap{color:#fff;opacity:.95}
header select{background:#fff}
/* ★ v2.9.7：窄屏（手机竖屏）—— 顶栏放不下「两个下拉 + 居中标题」，改成两行：
   第一行标题，第二行左右两个下拉。宁可换行，也不让标题被压住。 */
@media (max-width:560px){
  header{flex-wrap:wrap;row-gap:6px}
  header h1{position:static;transform:none;order:-1;width:100%;
            text-align:center;pointer-events:auto}
  header .st{margin-left:auto}
}
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
button{font:inherit;font-size:var(--btn-fs);border:1px solid var(--line);background:#fff;
 border-radius:8px;padding:var(--btn-pad-y) var(--btn-pad-x);cursor:pointer}
button.on{background:var(--blue);border-color:var(--blue);color:#fff}
button.warn{background:#fff3e6;border-color:#f0c08a}
button:active{transform:translateY(1px)}
/* ★ v2.7.9：页面不足一屏时「跳转」按钮置灰；被跳转到的区块闪一下边框作为反馈 */
button:disabled{opacity:.45;cursor:default}
.card.flash{outline:2px solid var(--blue);outline-offset:2px}
/* ★ v2.8.3：「布局」「按键」是下拉框（原来是一圈圈循环的按钮，选起来费劲）——
   跟 button 同一套尺寸变量，所以「按键」档位一变它也一起变 */
select{font:inherit;font-size:var(--btn-fs);border:1px solid var(--line);background:#fff;
 border-radius:8px;padding:var(--btn-pad-y) var(--btn-pad-x);cursor:pointer;max-width:46vw}
.selwrap{display:inline-flex;align-items:center;gap:4px;color:var(--grey);font-size:var(--btn-fs)}
.mod{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
/* ★ v2.9.5：「重置」挪到「立牌」左边 —— 与模式按钮同一行、一起换行，不再单独占一行
   （`flex:1 1 0` 让模式块可以压到 0 宽：窄屏时是**行内**继续换行，而不是整块跳到下一行） */
.modrow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
.modrow .mod{margin-bottom:0;flex:1 1 0;min-width:0}
.pool{margin:0 0 8px}
.pool .line{display:flex;gap:3px;flex-wrap:wrap}
.tile{position:relative;width:var(--tw);height:var(--th);border:2px solid transparent;border-radius:7px;
 background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;
 -webkit-user-select:none;user-select:none;-webkit-touch-callout:none;touch-action:manipulation}
.tile img{width:calc(var(--tw) - 6px);height:calc(var(--th) - 8px);pointer-events:none}
.tile.sel{border-color:var(--blue);background:#eaf2ff}
/* ★ v2.8.0：红色数字只显示「已选张数」，不再可点 —— pointer-events:none 让点击落到牌上。
   以前它是「−1」减牌按钮，但红圈太像删除键，误触一下手牌就少一张，所以这个操作已取消。 */
.tile .cnt{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;border-radius:9px;
 background:var(--red);color:#fff;font-size:11px;font-weight:700;line-height:18px;text-align:center;
 padding:0 3px;pointer-events:none;box-shadow:0 0 0 2px #fff}
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
 padding:8px 10px;display:flex;gap:8px;justify-content:center;align-items:center;
 /* ★ v2.9.4：底栏里多了「布局 / 按键 / 设置」，窄屏放不下就换行（2 行也够用） */
 flex-wrap:wrap;row-gap:6px}
footer .selwrap{font-size:var(--btn-fs)}
footer select{max-width:42vw}
.livetot{font-size:12px;color:#2f7ff0;margin-right:auto}
.statsdlg .box{width:min(94vw,440px);max-height:84vh;overflow:auto}
.statsdlg table{width:100%;border-collapse:collapse;font-size:13px}
.statsdlg th,.statsdlg td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}
.statsdlg th:first-child,.statsdlg td:first-child{text-align:left;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.statsdlg .sum{margin:8px 0;font-weight:bold}
.statsdlg select{font:inherit;padding:6px;border:1px solid var(--line);border-radius:8px;max-width:42vw}
/* ★ v2.9.11：弹窗内的**分页标签**（统计弹窗：统计 / 明细；设置弹窗：读番 / 列显示）
   手机上弹窗本来就是一屏，内容一多就「什么都挤在一起」——用标签一页只显示一类内容。 */
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:0 0 10px}
.tabs button{border:none;background:none;padding:6px 10px;border-radius:8px 8px 0 0;
 color:var(--grey);font-size:14px;cursor:pointer;position:relative;top:1px}
.tabs button.on{color:#2f7ff0;font-weight:600;background:#eef3fb;
 border:1px solid var(--line);border-bottom-color:#eef3fb}
.tabpane{display:none}
.tabpane.show{display:block}
/* ★ v2.9.7：设置里「统计列」的勾选区（一列两个，窄屏自动折行） */
.colswrap{display:flex;flex-wrap:wrap;gap:6px 14px;flex:1;min-width:0}
.colswrap label{display:inline-flex;align-items:center;gap:5px;font-size:13px;
 cursor:pointer;white-space:nowrap}
.colswrap input{width:16px;height:16px;cursor:pointer}
</style></head><body>
<header>
  <!-- ★ v2.9.7：「布局 / 按键」从底栏搬到顶栏左侧，标题居中 -->
  <span class="selwrap">布局：<select id="lysel" onchange="setLayout(this.value)"></select></span>
  <span class="selwrap">按键：<select id="szsel" onchange="applyBtnSize(this.value)"></select></span>
  <h1>__APP_TITLE__</h1>
  <div class="st" id="st">连接中…</div>
</header>
<main>
  <!-- ① 牌选择区（与桌面版一致：索 / 筒 / 万 / 字牌 四行） -->
  <div class="card" id="c_pool">
    <h2>牌选择区（点一下加一张；减牌请在下面「已选牌」里点一张）</h2>
    <div class="pool" id="pool"></div>
  </div>

  <!-- ② 模式行（★ v2.9.5：「重置」在「立牌」左边，同一行；★ v2.9.4：读番/语音/布局/按键都搬走了） -->
  <div class="card">
    <div class="modrow">
      <button class="warn" id="btn_reset" onclick="resetAll()">重置</button>
      <div class="mod" id="modes"></div>
    </div>
    <div class="btns" style="margin-top:8px">
      <button id="btn_debug" style="__SHOW_DEBUG__" onclick="window.open('/debug','_blank')">接口自测页</button>
      <button id="btn_token" style="__SHOW_TOKEN__" onclick="setToken()">换口令</button>
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
  <div class="card" id="c_res">
    <h2>算番结果 <span id="pat" class="tip"></span></h2>
    <div class="tot" id="tot">—</div>
    <div class="tip" id="msg"></div>
    <div class="tags" id="fans"></div>
    <div class="tip" style="margin-top:6px">
      手机：点牌加一张；<b>点错了不用「重置」</b>，「已选牌」里那一块都能点掉 ——
      点<b>立牌</b>一张减一张、点<b>副露</b>一张撤销那一组（吃/碰/杠）、点<b>和张</b>取消和张、
      点<b>花牌</b>行取消那张（牌上的红色数字只是「已选张数」，点它不再减牌）。
      立牌满 13 张（有副露时 13 − 3×副露数）会自动列出听牌；点牌池里的牌或候选牌即可出结果。
    </div>
  </div>
</main>
<footer>
  <span class="livetot" id="livetot"></span>
  <button id="jump_pool" onclick="gotoBlock('c_pool')">↑ 牌池</button>
  <button id="jump_res" onclick="gotoBlock('c_res')">↓ 结果</button>
  <!-- ★ v2.9.7：「布局 / 按键」已搬到**顶部蓝条**（标题左右居中那一带），底栏不再放 -->
  <!-- ★ v2.9.4：设置按钮 —— 读番开关与语音包都收进这个弹窗里 -->
  <button id="btn_set" onclick="showSet()" title="设置：读番 / 语音">设置</button>
  <!-- ★ v2.9.6：统计按钮（在「设置」右边）—— 查看所有用户的算番统计 -->
  <button id="btn_stats" onclick="showStats()" title="查看所有人的算番统计">统计</button>
</footer>

<!-- ★ v2.9.4：页面「设置」弹窗（读番开关 + 语音包）—— 原来这两个在模式行里，太占地方 -->
<div class="dlg" id="setdlg" onclick="if(event.target===this)hideSet()"><div class="box">
  <h3 style="margin:0 0 8px">设置</h3>
  <div class="row">
    <div class="lb">读番</div>
    <button id="btn_speak" onclick="toggleSpeak()"
            title="读出总番：合计 N 番（音频在电脑端《数字》目录，手机也会出声）">🔊 读番</button>
    <span class="tip">开启后每算出一手牌就念一次</span>
  </div>
  <div class="row" id="vswrap" style="__VOICE_SET_HIDE__">
    <div class="lb">语音</div>
    <select id="vssel" onchange="setVoicePack(this.value)"
            title="读番用哪一套录音（《数字》下每个子目录一套）"></select>
  </div>
  <!-- ★ v2.9.12：昵称（这台设备在统计里叫什么）——真正的「设备名称」浏览器不给，
       只能让用户自己填；填了统计表里一眼就能认出是谁 -->
  <div class="row">
    <div class="lb">昵称</div>
    <input id="nickinput" type="text" maxlength="24" placeholder="比如：老张的红米"
           style="flex:1;min-width:0" onchange="onNickChange(this.value)"
           onkeydown="if(event.key==='Enter')this.blur()">
    <button onclick="onNickChange(el('nickinput').value)">保存</button>
  </div>
  <div class="row"><div class="lb"></div>
    <span id="nickhint" class="tip"></span>
  </div>
  <!-- ★ v2.9.7：统计面板显示哪些列（只影响这台设备） -->
  <div class="row" style="align-items:flex-start">
    <div class="lb">统计列</div>
    <div id="statcolswrap" class="colswrap"></div>
  </div>
  <!-- ★ v2.9.10：逐手明细显示哪些列（只影响这台设备） -->
  <div class="row" style="align-items:flex-start">
    <div class="lb">明细列</div>
    <div id="detailcolswrap" class="colswrap"></div>
  </div>
  <div class="tip">
    「读番」＝把「合计 N 番」念出来（音频在电脑端《数字》目录里，手机自己出声）。<br>
    「语音」＝读番用哪一套录音，默认「女声」；电脑端「设置 → 通用 → 语音包」改的是它的默认值。<br>
    「昵称」＝这台设备在统计里叫什么（只认人用，随便填；重名会自动加 #2）。<br>
    「统计列」＝点「统计」后表格里显示哪几列，勾了立刻生效。<br>
    「明细列」＝在统计里点某个人展开的「逐手明细」显示哪几列。<br>
    这里选的都只记在<b>这台设备</b>上，刷新、下次打开都还在。<br>
    <span style="opacity:.8">注：「系统 / 浏览器 / 设备型号」是从浏览器自报的 UA 里读的 ——
    安卓 16+ 与鸿蒙的型号浏览器不再提供，所以「设备型号」可能显示「-」，属正常。</span>
  </div>
  <div class="btns" style="margin-top:10px">
    <button class="on" onclick="hideSet()">关闭</button>
  </div>
</div></div>

<div class="dlg" id="dlg"><div class="box">
  <h3 style="margin:0 0 8px">需要访问口令</h3>
  <p class="tip" id="dlgmsg">请输入电脑端「设置 → Web 版 → 地址与用法」里显示的口令。</p>
  <input id="tkin" placeholder="口令" autocomplete="one-time-code">
  <div class="btns" style="margin-top:10px">
    <button class="on" onclick="saveToken()">确定</button>
    <button onclick="hideDlg()">取消</button>
  </div>
</div></div>

<!-- ★ v2.9.6：统计弹窗（查看全部人的算番统计，按天聚合）
     ★ v2.9.11：拆成「统计 / 明细」两个分页标签 —— 原来表格 + 明细挤在一屏，太乱 -->
<div class="dlg statsdlg" id="statsdlg" onclick="if(event.target===this)hideStats()"><div class="box">
  <h3 style="margin:0 0 8px">算番统计</h3>
  <div class="tabs">
    <button id="stab_stat" class="on" onclick="showStatTab('stat')">统计</button>
    <button id="stab_detail" onclick="showStatTab('detail')">明细</button>
  </div>

  <!-- ---- 分页 1：统计表（按人聚合） -->
  <div class="tabpane show" id="spane_stat">
    <div class="row">
      <div class="lb">日期</div>
      <select id="statday" onchange="loadStats()"></select>
      <button onclick="loadStats()">刷新</button>
    </div>
    <div class="sum" id="statsum"></div>
    <div style="overflow:auto">
      <!-- ★ v2.9.7：表头由 JS 按「设置」里勾选的列动态生成（不在 HTML 里写死） -->
      <table id="stattab"><thead><tr id="stathead"></tr></thead>
        <tbody id="statbody"></tbody></table>
    </div>
    <div class="tip">IP+UUID 为主、IP+UA 兜底；按天统计，毫秒级时间戳；桌面端本地算番也计入。<br>
      ★ 点表格里<b>任意一行</b>切到「明细」页看这个人的<b>逐手记录</b>（每一手的时间/番数/番种）。</div>
  </div>

  <!-- ---- 分页 2：逐手明细（点统计表某一行后自动切过来） -->
  <div class="tabpane" id="spane_detail">
    <!-- ★ v2.9.9：逐手牌明细；★ v2.9.11 挪进单独一页 -->
    <div id="statdetail"><div class="tip">在「统计」页点一个人的那一行，这里就显示他的逐手明细。</div></div>
  </div>

  <div class="btns" style="margin-top:10px"><button class="on" onclick="hideStats()">关闭</button></div>
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
  if(MY_UUID)h["X-Client-UUID"]=MY_UUID;   /* ★ v2.9.6：客户端唯一标识，服务端据此区分用户 */
  const r=await fetch(path,{method:body?"POST":"GET",headers:h,
                            body:body?JSON.stringify(body):undefined});
  if(r.status===401){showDlg();throw new Error("需要访问口令");}
  const j=await r.json();
  if(j.ok===false)throw new Error(j.error||"接口错误");
  return j;
}
function el(id){return document.getElementById(id);}
/* ---------- 布局（★ v2.7.0 起是 CSS 变量；★ v2.8.4 起＝**精确 px 档位**，28~80 每 2px） ----------
   用户要求（v2.8.4）：「布局：38px（默认），其他只写多少px；从 38px 起每减 2px 一档到 28px，
   每加 2px 一档到 80px」⇒ **28 / 30 / … / 80 共 27 档**，默认 38px。
   档位数字＝**牌池一张牌有多宽**（CSS 的 `--tw`）；其余 11 个尺寸变量按 38px 时的原值
   **等比缩放**（牌间距、已选牌行、花牌、候选牌一起缩），所以整块版面比例不变。
   ★ 「38px（默认）」这一档＝**清掉内联变量、回落 CSS 原值** ⇒ 与升级前逐个像素一致。
   ★ 尺寸不再跟屏幕走（原来「自适应」那档按屏幕算）—— 手机觉得大的话直接选小几档即可；
     牌池仍是 flex-wrap，放不下会自动换行，不会溢出。
   选择记在 localStorage（mj_layout4，存**档位下标**），刷新/切页都保留 */
const LAYOUT_PX_MIN=28, LAYOUT_PX_STEP=2, LAYOUT_PX_MAX=80, LAYOUT_PX_DEFAULT=38;
const LAYOUT_LEVELS=(()=>{const a=[];for(let p=LAYOUT_PX_MIN;p<=LAYOUT_PX_MAX;p+=LAYOUT_PX_STEP){a.push(p);}return a;})();
const LAYOUT_DEFAULT=(LAYOUT_PX_DEFAULT-LAYOUT_PX_MIN)/LAYOUT_PX_STEP;   /* 38px 落在下标 5 */
const LAYOUT_KEY="mj_layout4";   /* ★ v2.8.4 再换键名：档位表从「7 个名字档」变成「27 个 px 档」，
                                    下标含义完全不同（老键 mj_layout3 的 2＝经典，这里 2＝32px），不再读 */
/* 38px 这一档在 CSS 里的原值（其余档＝按 W/38 等比缩放）—— 改 CSS 的这组默认值要同步改这里 */
const LAYOUT_BASE={"--tw":38,"--th":52,"--pw":34,"--ph":46,"--gw":4,"--pgap":3,
                   "--fw":34,"--fh":46,"--fwi":28,"--fhi":38,"--ww":28,"--wh":38};
const LAYOUT_VARS=Object.keys(LAYOUT_BASE);
const LAYOUT_TIP="布局：一张牌多宽（px）。默认 38px；往小每 2px 一档到 28px，"
  +"往大每 2px 一档到 80px，共 "+LAYOUT_LEVELS.length+" 档。只改牌的大小，不影响算番。";
const BTN_TIP="按键大小：字号 px。默认 15px；往小每 2px 到 11px、往大每 2px 到 23px。"
  +"模式行 / 重置 / 两个下拉框 / 选项 / 风圈风位 / 底部按钮一起变。";
let LAYOUT_IDX=LAYOUT_DEFAULT;
function loadLayout(){
  try{const v=parseInt(localStorage.getItem(LAYOUT_KEY),10);
      if(v>=0&&v<LAYOUT_LEVELS.length)return v;}catch(e){}
  return LAYOUT_DEFAULT;
}
function layoutPx(){return LAYOUT_LEVELS[LAYOUT_IDX];}
function layoutLabel(p,i){return (i===LAYOUT_DEFAULT)?(p+"px（默认）"):(p+"px");}
function fillLayoutOptions(){
  const s=el("lysel");
  if(!s)return;
  if(s.options.length!==LAYOUT_LEVELS.length){
    s.innerHTML=LAYOUT_LEVELS.map((_,i)=>'<option value="'+i+'"></option>').join("");
  }
  LAYOUT_LEVELS.forEach((p,i)=>{         /* 只改文字，不重建（重建会把当前选中/展开的列表打断） */
    s.options[i].value=String(i);
    s.options[i].textContent=layoutLabel(p,i);   /* ★ 用户要求：只有默认档写「（默认）」，其余只写 px */
  });
  s.value=String(LAYOUT_IDX);
  s.title=LAYOUT_TIP;
}
function setLayout(idx,remember){
  LAYOUT_IDX=Math.max(0,Math.min(LAYOUT_LEVELS.length-1,idx|0));
  S.layout=layoutPx();                   /* 只作状态记录/调试用 */
  autoSize();
  fillLayoutOptions();
  if(remember!==false){try{localStorage.setItem(LAYOUT_KEY,String(LAYOUT_IDX));}catch(e){}}
}
/* ---------- 按键尺寸（★ v2.7.6 多档；★ v2.7.7 默认＝最小档；★ v2.8.2 补两个更小的档；
                 ★ v2.8.3 按钮 → 下拉框，选项里直接写清多少 px） ----------
   用户要求：默认＝现在的大小，再往大 4 档、往小 2 档（v2.8.2），一级级调看哪级顺手。
   只改 3 个 CSS 变量（--btn-fs / --btn-pad-y / --btn-pad-x）——
   模式行（立牌/吃/碰/明杠/暗杠）、重置、布局与按键两个下拉框、选项勾选、风圈/风位、
   底部 ↑↓、弹窗按钮 一次全跟着变。
   ★ 默认档（下标 BTN_DEFAULT）＝**清掉内联变量、回落 CSS 默认值** ⇒ 与升级前逐像素一致 */
const BTN_KEY="mj_btnsize3";   /* ★ v2.8.2 换键名：档位表变了（默认档由下标 0 变 2），
                                  老键 mj_btnsize2 存的下标含义已不同，不再读 */
const BTN_LEVELS=[
  {name:"极小",fs:11,py:3, px:5},    /* ★ v2.8.2：比「最小」小两档 */
  {name:"更小",fs:13,py:5, px:8},
  {name:"最小",fs:15,py:7, px:11},   /* ★ 默认档＝与升级前一模一样，别改这行（下标＝BTN_DEFAULT） */
  {name:"大",  fs:17,py:9, px:14},
  {name:"更大",fs:19,py:11,px:17},
  {name:"很大",fs:21,py:13,px:20},
  {name:"最大",fs:23,py:15,px:23},
];
const BTN_DEFAULT=2;                   /* ★ v2.8.2：默认仍是「最小」（＝升级前的大小），下标由 0 变 2 */
let BTN_IDX=BTN_DEFAULT;
function loadBtnSize(){
  try{const v=parseInt(localStorage.getItem(BTN_KEY),10);
      if(v>=0&&v<BTN_LEVELS.length)return v;}catch(e){}
  return BTN_DEFAULT;
}
/* ★ v2.8.3：下拉框各档的 px ＝字号（与 CSS 变量同一口径，所以「按键：15px」就是实际字号） */
function fillBtnOptions(){
  const s=el("szsel");
  if(!s)return;
  if(s.options.length!==BTN_LEVELS.length){
    s.innerHTML=BTN_LEVELS.map((_,i)=>'<option value="'+i+'"></option>').join("");
  }
  BTN_LEVELS.forEach((L,i)=>{
    s.options[i].value=String(i);
    s.options[i].textContent=(i===BTN_DEFAULT)?(L.fs+"px（默认）"):(L.fs+"px");  /* 同布局：只默认档写「（默认）」 */
  });
  s.value=String(BTN_IDX);
  s.title=BTN_TIP;
}
function applyBtnSize(idx,remember){
  BTN_IDX=Math.max(0,Math.min(BTN_LEVELS.length-1,idx|0));
  const L=BTN_LEVELS[BTN_IDX];
  const root=document.documentElement;
  if(BTN_IDX===BTN_DEFAULT){           /* 默认档：清内联值 → CSS 默认（老样子） */
    ["--btn-fs","--btn-pad-y","--btn-pad-x"].forEach(k=>root.style.removeProperty(k));
  }else{
    root.style.setProperty("--btn-fs",L.fs+"px");
    root.style.setProperty("--btn-pad-y",L.py+"px");
    root.style.setProperty("--btn-pad-x",L.px+"px");
  }
  fillBtnOptions();
  if(remember!==false){try{localStorage.setItem(BTN_KEY,String(BTN_IDX));}catch(e){}}
}
/* ★ v2.8.4：尺寸＝**直接按档位 px 等比缩放**（不再看屏幕）——
   默认 38px 那一档清掉内联变量、回落 CSS 原值 ⇒ 与升级前逐像素一致；
   其余档按 W/38 缩放全部 12 个变量（`--tw` 缩完正好＝W，所以下拉框里写的 px 就是牌的实际宽度）。 */
function autoSize(){
  const root=document.documentElement;
  const W=layoutPx();
  if(W===LAYOUT_PX_DEFAULT){             /* 默认档：回到 CSS 原值（老样子，一个像素都不差） */
    LAYOUT_VARS.forEach(k=>root.style.removeProperty(k));
    return;
  }
  const f=W/LAYOUT_PX_DEFAULT;           /* 等比缩放；--tw 缩完＝round(38*f)＝＝W */
  LAYOUT_VARS.forEach(k=>root.style.setProperty(k,Math.max(1,Math.round(LAYOUT_BASE[k]*f))+"px"));
}
let asTimer=null;
function autoSizeLater(){clearTimeout(asTimer);asTimer=setTimeout(()=>{
  autoSize();updateJumpBtns();},120);}   /* 尺寸是固定 px，不再随屏幕变；resize 只需重算跳转按钮 */
window.addEventListener("resize",autoSizeLater);
window.addEventListener("orientationchange",autoSizeLater);
/* ★ v2.7.9：底部两个「跳转」按钮——滚到牌池 / 结果**区块**并闪一下边框。
   原来是无反馈的 scrollTo 顶/底：页面本来就在顶部/底部、或内容不足一屏时，
   点了自然「没反应」（那是正常的）—— 现在改成滚到区块 + 高亮，且没得滚时置灰 */
function gotoBlock(id){
  const box=el(id);
  if(!box)return;
  const hd=document.querySelector("header");
  const off=(hd?hd.offsetHeight:0)+6;          /* 躲开固定顶栏 */
  const top=box.getBoundingClientRect().top+(window.pageYOffset||0)-off;
  window.scrollTo({top:Math.max(0,top),behavior:"smooth"});
  box.classList.remove("flash");
  void box.offsetWidth;                        /* 强制重排，让动画能重播 */
  box.classList.add("flash");
  setTimeout(()=>box.classList.remove("flash"),1300);
}
function updateJumpBtns(){
  const can=document.documentElement.scrollHeight>window.innerHeight+8;
  const bp=el("jump_pool"),br=el("jump_res");
  if(bp){bp.disabled=!can;bp.title=can?"滚到「牌选择区」":"页面内容不足一屏，无需滚动";}
  if(br){br.disabled=!can;br.title=can?"滚到「算番结果」":"页面内容不足一屏，无需滚动";}
}
/* ★ v2.5.0：图片地址也用 q() 带上口令 —— 这样即使「Web 客户端」被设成要口令，
   用 http://ip:端口/?token=xxx 打开页面时牌面图照样能加载（不会一片碎图） */
function img(code){return '<img src="'+q("/tiles/"+code+".png")+'" alt="'+code+'" title="'+(NAMES[code]||"")+'">';}
/* 已选牌也可点：手机/平板没有右键，点一下就是减一张（桌面鼠标同样好用）。
   ★ v2.8.1：fn 指定点击时调用的函数（默认 minus；花牌行用 toggleFlower） */
function imgClk(code,fn){return '<img class="clk" onclick="'+(fn||"minus")+'(\''+code+'\')" src="'+
  q("/tiles/"+code+".png")+'" alt="'+code+'" title="点上一下可减一张">';}
function mkTiles(box,codes,emptyText,clickable,fn){
  box.innerHTML = codes.length? codes.map(c=>clickable?imgClk(c,fn):img(c)).join("")
    : '<div class="empty">'+(emptyText||"（空）")+'</div>';
}
/* ★ 副露渲染（与桌面版一致，v2.7.1 修）：
   明杠 / 碰 / 吃 = 全部正面；**暗杠 = 面·背·背·面**（中间两张用 empty.png 牌背）；
   不同副露之间留一段间隔（桌面版用 GAP 哨兵，这里用 .meldgap）。
   ★ v2.8.1：每一张都能点（**含暗杠的牌背**）＝**撤销那一组吃/碰/杠** ——
   点错牌不用整手「重置」，点一下那一组就没了（与桌面版 v2.7.2 同口径）。 */
function meldHtml(){
  if(!S.melds.length)return '<div class="empty">（暂无吃碰杠）</div>';
  return S.melds.map((m,i)=>{
    const t=(m.tiles||[]).slice();
    let codes=t;
    if(m.kind==="kong"&&m.concealed&&t.length>=4){
      codes=[t[0],"empty","empty",t[3]];          /* 面·背·背·面 */
    }
    const body=codes.map(c=>c==="empty"
      ? '<img class="clk" onclick="removeMeld('+i+')" src="'+q("/tiles/empty.png")+'" alt="暗杠" title="暗杠（点一下撤销这一组）">'
      : '<img class="clk" onclick="removeMeld('+i+')" src="'+q("/tiles/"+c+".png")+'" alt="'+c+'" title="点一下撤销这一组吃碰杠">'
    ).join("");
    return (i?'<span class="meldgap"></span>':'')+body;
  }).join("");
}
/* ★ v2.8.1：点副露里的任意一张＝撤销那一组（不必整手「重置」） */
function removeMeld(gi){
  const i=+gi;
  if(!(i>=0&&i<S.melds.length))return;
  S.melds.splice(i,1);
  S.win=null;                /* 副露变了，和张要重新指定（与桌面版一致） */
  render();
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
  stopSpeak();                     /* ★ v2.9.0：正在念的也停掉（「读番」开关本身不动） */
  S.melds=[];S.concealed={};S.win=null;S.pending=[];S.flowers=[];S.mode="stand";
  S.opts={tsumo:false,last_tile:false,special_a:false,special_b:false,
          round:"东",seat:"东"};
  render();
}
/* 减一张（★ 手机友好入口：「已选牌」的立牌 / 和张行里点一张；
   v2.8.0 起牌池上的红色数字不再可点） */
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
function setMode(m){/* ★ v2.8.0：再点一次当前模式按钮＝取消该模式，回到「立牌」 */
  if(m!=="stand"&&S.mode===m)m="stand";
  S.mode=m;S.pending=[];render();}
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
  setTimeout(updateJumpBtns,0);           /* ★ v2.7.9：内容长度变了→跳转按钮该亮/该灰 */
  el("m_melds").innerHTML=meldHtml();      /* ★ 副露：暗杠要显示为 面·背·背·面 */
  mkTiles(el("m_hand"),concealedList(),"（请在牌池点牌）",true);   /* 点一张 = 减一张 */
  mkTiles(el("m_win"),S.win?[S.win]:[],"（未指定）",true);
  mkTiles(el("m_flower"),S.flowers,"（未选花牌）",true,"toggleFlower");  /* ★ v2.8.1：点一张＝取消这张花牌 */
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
/* ★ v2.8.0：红色角标不再绑定任何事件（只显示张数）——
   以前它是「−1」减牌按钮，红圈太像删除键、容易误触；现在点它＝点这张牌（加一张）。
   CSS 里 .cnt 已设 pointer-events:none，事件自然落到 .tile 上。 */
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
      /* ★ v2.9.12：顺带把昵称和（能问到的）设备型号报上去 */
      const body={melds:meldsBody(),concealed:hand,
                  win:S.win||null,options:optsBody(),uuid:MY_UUID,
                  nick:MY_NICK,model:MY_MODEL};
      const j=await api("/api/score",body);
      el("tot").textContent=j.total+" 番";
      el("tot").className="tot"+(j.reach_standard?"":" low");
      el("pat").textContent=j.pattern?("牌型："+j.pattern):"";
      el("msg").textContent=j.message||(j.reach_standard?"已达起和标准（8 分）":
                                         "番种合计 "+j.base+" 分，未达 8 分起和标准");
      el("fans").innerHTML=(j.fans||[]).map(f=>'<div class="tag"><b>'+f.value+
        '</b>'+f.name+'</div>').join("");
      /* ★ v2.9.0：记下总番；开着「读番」就念出来（合计 N 番） */
      currentTotal=j.total;
      if(SPEAK)speakTotal(j.total);
      /* ★ v2.9.6：本机实时累计（仅当天；同一手牌只计一次，避免选项切换刷数） */
      const hs=sigHand();
      if(hs!==lastHandSig){lastHandSig=hs;liveTotal+=j.total||0;liveCount++;updateLive();}
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
      currentTotal=null;
    }else{
      el("c_wait").style.display="none";
      el("tot").textContent="—";el("tot").className="tot";
      el("pat").textContent="";el("fans").innerHTML="";
      el("msg").textContent="已选共 "+totalTiles()+" 张，再选 "+
        Math.max(0,(need+1)-totalTiles())+" 张即可算番。";
      currentTotal=null;
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

/* ---------- 读番（★ v2.9.0）：把「合计 N 番」读出来 ----------
   点模式行的「🔊 读番」开/关；开着时每算出总番就念一遍。
   音频是**电脑端《数字》目录**里的片段：/api/readout?total=N 给清单（中文读法 + 每段文件名），
   /audio/<文件名> 是音频本身 —— 所以**手机/平板自己出声**，电脑不用装任何东西、也不占电脑喇叭。
   ★ v2.9.3：《数字》下可以放多套录音（`数字\鲸宝\`、`数字\女声\`…），
   请求带 `&set=<语音包名>` 就是「用哪一套」，取音频也变成 `/audio/<语音包>/<文件名>`；
   页面上的「语音：」下拉就是给这个用的（本机选择存在 localStorage，不影响别人）。
   别的程序（微信小程序 / 网页 / 自家软件）同样调这两个接口即可，**不用复制音频文件**。 */
const SPEAK_KEY="mj_speak";
/* ★ v2.9.1：默认是否自动读番 —— 由**服务器端设置**（桌面端「设置 → 通用 → 默认开启自动读番」）
   渲染进来，默认 true。这样「无论用哪个端，都能自动读番」。 */
const SPEAK_DEFAULT=__SPEAK_DEFAULT__;
let SPEAK=SPEAK_DEFAULT, speakQueue=[], speakAudio=null, currentTotal=null;
/* ★ v2.9.3：读番用哪一套录音 —— 《数字》下有几个子目录就有几套（目录名＝语音包名），
   默认用服务器端设置的那一套；本机在这儿选过就只影响本机（存 localStorage）。 */
const VOICE_SETS=__VOICE_SETS__, VOICE_SET_SERVER=__VOICE_SET__, VOICE_KEY="mj_voice";
let VOICE_SET=VOICE_SET_SERVER;
function loadVoicePack(){
  try{const v=localStorage.getItem(VOICE_KEY);
      VOICE_SET=(v&&VOICE_SETS.indexOf(v)>=0)?v:VOICE_SET_SERVER;}
  catch(e){VOICE_SET=VOICE_SET_SERVER;}
  if(VOICE_SETS.indexOf(VOICE_SET)<0)VOICE_SET=VOICE_SETS.length?VOICE_SETS[0]:"";  /* 那套被删了 */
  fillVoiceOptions();
}
function fillVoiceOptions(){
  const s=el("vssel");
  if(!s)return;
  if(s.options.length!==VOICE_SETS.length){          /* 选项变了才重建（保住当前选择） */
    s.innerHTML=VOICE_SETS.map(n=>'<option value="'+n+'">'+
                  (n||"（数字 根目录）")+'</option>').join("");
  }
  s.value=VOICE_SET;
}
function setVoicePack(name){
  VOICE_SET=name;
  try{localStorage.setItem(VOICE_KEY,name);}catch(e){}
  if(SPEAK)speakTotal(currentTotal!==null?currentTotal:0);   /* 换了就念一遍新的 */
}
function loadSpeak(){
  /* 这个浏览器自己选过（点过「🔊 读番」）就听本机的；没选过才用服务器给的默认值 */
  try{const v=localStorage.getItem(SPEAK_KEY);
      SPEAK=(v===null||v===undefined)?SPEAK_DEFAULT:(v==="1");}
  catch(e){SPEAK=SPEAK_DEFAULT;}
}
function markSpeak(){
  const b=el("btn_speak");
  if(b)b.className=SPEAK?"on":"";
  /* ★ v2.9.4：读番开关收进「设置」了，就在设置按钮上留个提示，免得不知道现在开着没 */
  const s=el("btn_set");
  if(s)s.title="设置：读番"+((SPEAK?"开启":"关闭"))+" / 语音包";
}
function toggleSpeak(){
  SPEAK=!SPEAK;
  try{localStorage.setItem(SPEAK_KEY,SPEAK?"1":"0");}catch(e){}
  markSpeak();
  if(SPEAK)speakTotal(currentTotal!==null?currentTotal:0); /* 点开就先念一次（顺便解锁自动播放） */
  else stopSpeak();
}
function stopSpeak(){
  speakQueue=[];
  if(speakAudio){try{speakAudio.pause();}catch(e){} speakAudio=null;}
}
function playClips(urls){
  speakQueue=urls.slice();
  const next=()=>{
    if(!speakQueue.length){speakAudio=null;return;}
    const a=new Audio(q(speakQueue.shift()));      /* q() 带上口令（设了口令时） */
    speakAudio=a;
    a.onended=next; a.onerror=next;
    a.play().catch(()=>{speakAudio=null;});         /* 浏览器不让自动播就安静放弃 */
  };
  next();
}
async function speakTotal(n){
  if(n===null||n===undefined||n==="")return;
  try{
    /* ★ v2.9.3：把本机选的语音包一起带上（服务器按它挑录音；不给就用服务器端默认） */
    const j=await api("/api/readout?total="+encodeURIComponent(n)
                      +"&set="+encodeURIComponent(VOICE_SET));
    const urls=(j.clips||[]).map(c=>c.url).filter(u=>u);
    if(urls.length)playClips(urls);
  }catch(e){/* 读番失败不影响算番 */}
}

/* ---------- 设置弹窗（★ v2.9.4：读番开关 + 语音包；点底栏「设置」打开） ---------- */
function showSet(){el("setdlg").classList.add("show");}
function hideSet(){el("setdlg").classList.remove("show");}

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

/* ---------- 统计（★ v2.9.6）：客户端唯一标识 + 本机实时累计 + 查看全部人 ---------- */
const UUID_KEY="mj_uuid";
let MY_UUID="";
let liveTotal=0, liveCount=0, lastHandSig="";

/* ---------- ★ v2.9.12：昵称（自己填的设备名）+ 设备型号（能问到就上报） ----------
   浏览器**不提供**设备名称，只能让用户自己填；型号则试试 UA-CH 的
   getHighEntropyValues(['model'])（只有 Chromium + HTTPS 才给，局域网明文多半失败，
   失败了就是空串，服务端退回 UA 解析，不影响别的）。 */
const NICK_KEY="mj_nick", MODEL_KEY="mj_model";
let MY_NICK="", MY_MODEL="";
function loadNick(){
  try{MY_NICK=localStorage.getItem(NICK_KEY)||"";}catch(e){MY_NICK="";}
  const i=el("nickinput"); if(i)i.value=MY_NICK;
}
function nickHint(t){const h=el("nickhint"); if(h)h.textContent=t||"";}
function onNickChange(v){
  const raw=String(v||"").trim().slice(0,24);
  const i=el("nickinput"); if(i)i.value=raw;
  nickHint("保存中…");
  api("/api/set_nick",{uuid:MY_UUID,nick:raw}).then(function(j){
    if(!j||!j.ok){nickHint("保存失败："+((j&&j.error)||"未知错误"));return;}
    MY_NICK=j.nick||raw;
    try{localStorage.setItem(NICK_KEY,MY_NICK);}catch(e){}
    const i2=el("nickinput"); if(i2)i2.value=MY_NICK;
    /* 服务端可能因为重名给加了 #2 —— 必须如实告诉用户，否则他不知道自己显示成啥 */
    if(!MY_NICK)nickHint("昵称已清空");
    else if(MY_NICK===raw)nickHint("已保存：统计里会显示「"+MY_NICK+"」");
    else nickHint("同名已存在，你被记为「"+MY_NICK+"」");
    if(el("statsdlg")&&el("statsdlg").classList.contains("show"))loadStats();
  }).catch(function(e){nickHint("保存失败："+e);});
}
function probeModel(){
  try{MY_MODEL=localStorage.getItem(MODEL_KEY)||"";}catch(e){}
  try{
    const ud=navigator.userAgentData;
    if(ud&&ud.getHighEntropyValues){
      ud.getHighEntropyValues(["model"]).then(function(d){
        const m=(d&&d.model)?String(d.model).slice(0,40):"";
        if(m&&m!==MY_MODEL){MY_MODEL=m;try{localStorage.setItem(MODEL_KEY,m);}catch(e){}}
      }).catch(function(){});
    }
  }catch(e){}
}
function clientUUID(){
  try{let u=localStorage.getItem(UUID_KEY);
    if(!u){u=(window.crypto&&crypto.randomUUID)?crypto.randomUUID()
            :"u"+Date.now().toString(16)+Math.random().toString(16).slice(2);
      try{localStorage.setItem(UUID_KEY,u);}catch(e){}}
    return u;}catch(e){return "";}
}
function sigHand(){
  /* 手牌签名（含牌/副露/和张），同手牌只累计一次，避免选项切换刷数 */
  try{return JSON.stringify(concealedList())+"|"+JSON.stringify(meldsBody())+"|"+(S.win||"");}
  catch(e){return ""+Math.random();}
}
function updateLive(){
  const e=el("livetot");
  if(e)e.textContent="今日累计 "+liveTotal+" 番（"+liveCount+" 手）";
}
/* UUID / UA 是**客户端可控**的字符串，不能直接拼进 innerHTML，否则一个恶意
   客户端就能往别人的统计表里塞标签。统一过一遍转义。 */
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}

/* ---------- ★ v2.9.7：统计面板「显示哪些列」（可自定义） ----------
   STAT_COLS_DEF  = 全部可选列（服务端给，与桌面端同一套 key）
   STAT_COLS_DEF0 = 服务端默认显示那几列（桌面端「设置 → 通用 → 统计显示列」）
   本机在「设置」里勾过 → 存 localStorage，只影响这台设备；没勾过 → 用服务端那套。  */
const STAT_COLS_DEF=__STATS_COL_DEF__;
const STAT_COLS_DEF0=__STATS_COL_DEFAULT__;
const STATCOLS_KEY="mj_statscols";
/* ★ v2.9.10：明细列（与统计列同一套机制，只是换了一组 key 和 localStorage 键） */
const DETAIL_COLS_DEF=__DETAIL_COL_DEF__;
const DETAIL_COLS_DEF0=__DETAIL_COL_DEFAULT__;
const DETAILCOLS_KEY="mj_detailcols";
/* 一组列的「读 / 存 / 画勾 / 改动」逻辑完全一样，抽成一个工厂，避免复制两遍 */
function colStore(key,def,def0){
  return {
    get:function(){
      try{const v=localStorage.getItem(key);
        if(v){const a=JSON.parse(v);
          if(Array.isArray(a)){const ok=a.filter(k=>def.some(d=>d.k===k));
            if(ok.length)return ok;}}}catch(e){}
      return def0.slice();
    },
    save:function(a){try{localStorage.setItem(key,JSON.stringify(a));}catch(e){}},
    render:function(wrapId,onchg){
      const w=el(wrapId); if(!w)return;
      const cur=this.get();
      w.innerHTML=def.map(d=>
        '<label><input type="checkbox" data-k="'+esc(d.k)+'"'
        +(cur.indexOf(d.k)>=0?" checked":"")+' onchange="'+onchg+'()">'
        +esc(d.n)+'</label>').join("");
    },
    /* 返回本次勾选结果；一列都没勾时返回 null（调用方负责把兜底列勾回来） */
    changed:function(wrapId){
      const w=el(wrapId); if(!w)return null;
      const a=[];
      w.querySelectorAll("input[data-k]").forEach(i=>{
        if(i.checked)a.push(i.getAttribute("data-k"));});
      if(!a.length)return null;
      this.save(a);
      return a;
    }
  };
}
const STATC=colStore(STATCOLS_KEY,STAT_COLS_DEF,STAT_COLS_DEF0);
const DETAILC=colStore(DETAILCOLS_KEY,DETAIL_COLS_DEF,DETAIL_COLS_DEF0);
function statCols(){return STATC.get();}
function saveStatCols(a){STATC.save(a);}
function detailCols(){return DETAILC.get();}
function renderStatColBoxes(){STATC.render("statcolswrap","onStatColChange");}
function renderDetailColBoxes(){DETAILC.render("detailcolswrap","onDetailColChange");}
function onStatColChange(){
  /* 至少留一列：一列都不勾表格就全白，等于把功能弄坏了 */
  if(!STATC.changed("statcolswrap")){renderStatColBoxes();return;}
  buildStatHead();
  if(el("statsdlg").classList.contains("show"))loadStats();
}
function onDetailColChange(){
  /* 明细至少留「时间」——没有时间就不叫「逐手」记录了 */
  const a=DETAILC.changed("detailcolswrap");
  if(!a){renderDetailColBoxes();return;}
  if(DETAIL_UK)openDetail(DETAIL_UK);      /* 明细正开着 → 立刻按新列重画 */
}
function buildStatHead(){
  const h=el("stathead"); if(!h)return;
  const cur=statCols();
  h.innerHTML=STAT_COLS_DEF.filter(d=>cur.indexOf(d.k)>=0)
    .map(d=>"<th>"+esc(d.n)+"</th>").join("");
}
function statCell(k,u){
  switch(k){
    case "user":  return esc((u.uuid||u.user_key||"?").slice(0,16));
    case "ctype": return u.client_type==="desktop"?"桌面":"Web";
    case "ip":    return '<span style="font-size:12px">'+esc(u.ip||"-")+"</span>";
    case "ua":    return '<span style="font-size:12px">'+esc(uaBrief(u.ua))+"</span>";
    case "fan":   return String(u.total_fan||0);
    case "cnt":   return String(u.cnt||0);
    case "reach": return String(u.reach_cnt||0);
    case "last":  return '<span style="font-size:12px">'
      +esc(u.last_ts?new Date(u.last_ts/1).toLocaleString("zh-CN"):"-")+"</span>";
    /* ★ v2.9.9：番种汇总（「无番和×3、碰碰和×1」），太长会挤，所以小字 + 完整串挂 title */
    case "fans":  return '<span style="font-size:12px" title="'+esc(u.fans||"")+'">'
      +esc(u.fans||"-")+"</span>";
    /* ★ v2.9.12：认人四件套。os/browser/dev/nick 都是服务端算好塞进来的，
       这里不用再解析一遍 UA（两端规则一致靠的就是这件事） */
    case "nick":    return nickHtml(u.nick);
    case "os":      return '<span style="font-size:12px">'+esc(u.os||"-")+"</span>";
    case "browser": return '<span style="font-size:12px">'+esc(u.browser||"-")+"</span>";
    case "dev":     return '<span style="font-size:12px" title="'+esc(u.dev||"")+'">'
      +esc(u.dev||"-")+"</span>";
  }
  return "";
}
/* 昵称：认人的主力，稍微显眼一点；没填就一个淡淡的「-」 */
function nickHtml(n){
  n=(n||"").trim();
  if(!n)return '<span style="font-size:12px;opacity:.45">-</span>';
  return '<b style="font-size:12px">'+esc(n)+"</b>";
}
/* 把一长串 User-Agent 压成一个一眼认得出的设备名（与桌面端 _ua_brief 同一套判断） */
function uaBrief(ua){
  const low=(ua||"").toLowerCase();
  if(!low)return "-";
  const M=[["micromessenger","微信"],["ipad","iPad"],["iphone","iPhone"],
           ["harmony","鸿蒙"],["android","Android"],["windows","Windows"],
           ["macintosh","Mac"],["mac os x","Mac"],["linux","Linux"]];
  for(let i=0;i<M.length;i++) if(low.indexOf(M[i][0])>=0) return M[i][1];
  return (ua||"").split("/")[0].trim().slice(0,14)||"-";
}
function showStats(){
  el("statsdlg").classList.add("show");
  showStatTab("stat");          /* ★ v2.9.11：每次打开都回到「统计」页 */
  loadStats();
}
function hideStats(){el("statsdlg").classList.remove("show");closeDetail();}
/* ---------- ★ v2.9.11：统计弹窗的两个分页标签（统计 / 明细） ----------
   `_statTab` 记住当前页。注意：切页**不重新拉数据** ——
   统计表已经画好了，明细是点某一行时才拉的（切回「统计」不该把表格刷没）。 */
let _statTab="stat";
function showStatTab(name){
  _statTab=(name==="detail")?"detail":"stat";
  const a=el("stab_stat"), b=el("stab_detail");
  const pa=el("spane_stat"), pb=el("spane_detail");
  if(a)a.classList.toggle("on",_statTab==="stat");
  if(b)b.classList.toggle("on",_statTab==="detail");
  if(pa)pa.classList.toggle("show",_statTab==="stat");
  if(pb)pb.classList.toggle("show",_statTab==="detail");
}

/* ---------- ★ v2.9.9：逐手牌明细（点统计表某一行展开） ----------
   统计表是「按人聚合」的，看不出他到底打了哪几手；明细把 score_log 的原始行
   按时间倒序列出来，时间精确到毫秒，并列出这一手算了哪些番种。            */
let DETAIL_UK="";
function statRowClick(ev){
  const tr=(ev.target&&ev.target.closest)?ev.target.closest("tr"):null;
  if(!tr)return;
  const uk=tr.getAttribute("data-uk")||"";
  if(!uk)return;
  if(DETAIL_UK===uk){closeDetail();return;}   /* 再点同一行 = 收起 */
  openDetail(uk);
}
function closeDetail(){
  DETAIL_UK="";
  const d=el("statdetail");
  /* ★ v2.9.11：显隐由「统计 / 明细」标签页管（原来是自己控制 display） */
  if(d)d.innerHTML='<div class="tip">在「统计」页点一个人的那一行，这里就显示他的逐手明细。</div>';
}
function openDetail(uk){
  DETAIL_UK=uk;
  const d=el("statdetail");
  if(!d)return;
  showStatTab("detail");        /* ★ v2.9.11：点统计表某行 → 自动切到「明细」页 */
  d.innerHTML='<div class="tip">正在读取明细…</div>';
  const day=(el("statday")&&el("statday").value)||"";
  const q="user_key="+encodeURIComponent(uk)+(day?"&day="+encodeURIComponent(day):"");
  api("/api/stats_detail?"+q).then(j=>{
    if(DETAIL_UK!==uk)return;                 /* 期间又点了别人 → 丢弃这次结果 */
    d.innerHTML=(!j||j.ok===false)
      ? '<div class="tip">明细读取失败：'+esc((j&&j.error)||"未知错误")+'</div>'
      : detailHtml(j);
  }).catch(e=>{
    if(DETAIL_UK!==uk)return;
    d.innerHTML='<div class="tip">明细读取失败：'+esc(e)+'</div>';
  });
}
/* 毫秒级时间：2026/10/9 00:12:33.456 */
function msTime(ts){
  if(!ts)return "-";
  const d=new Date(ts/1);
  return d.toLocaleString("zh-CN")+"."+String(ts%1000).padStart(3,"0");
}
function detailHtml(j){
  const rows=j.rows||[];
  let h='<div style="margin:8px 0 4px;font-weight:600">逐手明细'
       +'　<span style="font-weight:400;color:#6b7684">'+esc(j.user_key||"")
       +'　'+rows.length+' 手'+(j.day?("　"+esc(j.day)):"（全部日期）")+'</span></div>';
  if(j.fans&&j.fans.length)
    h+='<div class="tip">这个人打出的番种：'
      +j.fans.map(f=>esc(f.name)+"×"+f.cnt).join("、")+'</div>';
  if(!rows.length){h+='<div class="tip">没有明细记录。</div>';return h;}
  /* ★ v2.9.10：只画「设置 → 明细列」里勾上的那几列 */
  const cur=detailCols();
  h+='<div style="max-height:240px;overflow:auto"><table><thead><tr>'
    +DETAIL_COLS_DEF.filter(d=>cur.indexOf(d.k)>=0)
      .map(d=>"<th>"+esc(d.n)+"</th>").join("")
    +'</tr></thead><tbody>';
  rows.forEach(r=>{
    h+='<tr>'+cur.map(k=>"<td>"+detailCell(k,r)+"</td>").join("")+'</tr>';
  });
  return h+'</tbody></table></div>';
}
/* ★ v2.9.10：明细单元格按列 key 取值（与统计表的 statCell 一一对应） */
function detailCell(k,r){
  switch(k){
    case "day":    return esc(r.day||"-");
    case "time":   return esc(msTime(r.ts_ms));
    case "ctype":  return r.client_type==="desktop"?"桌面":"Web";
    case "ip":     return esc(r.ip||"-");
    case "ua":     return '<span style="font-size:12px" title="'+esc(r.ua||"")+'">'
                     +esc(uaBrief(r.ua))+"</span>";
    case "fan":    return String(r.total_fan||0);
    case "base":   return String(r.base||0);
    case "reach":  return r.reach?"是":"否";
    case "fans_n": return String(r.fans_n||0);
    case "fans":   {const fs=(r.fans||"").split("|").filter(s=>s.trim());
                    const t=fs.join("、")||"-";
                    return '<span title="'+esc(t)+'">'+esc(t)+"</span>";}
    /* ★ v2.9.12：明细里的 nick 是「这一手牌时」的昵称（改名不改历史），
       os/browser/dev 由服务端算好塞进来 */
    case "nick":    return nickHtml(r.nick);
    case "os":      return '<span style="font-size:12px">'+esc(r.os||"-")+"</span>";
    case "browser": return '<span style="font-size:12px">'+esc(r.browser||"-")+"</span>";
    case "dev":     return '<span style="font-size:12px" title="'+esc(r.dev||"")+'">'
                     +esc(r.dev||"-")+"</span>";
  }
  return "";
}
function _todayStr(){
  const t=new Date();
  return t.getFullYear()+"-"+String(t.getMonth()+1).padStart(2,"0")+"-"+String(t.getDate()).padStart(2,"0");
}
function fillStatDays(){
  const sel=el("statday");
  if(!sel)return;
  const today=_todayStr();
  sel.innerHTML='<option value="">全部日期</option><option value="'+today+'">今天（'+today+'）</option>';
}
function loadStats(){
  const day=el("statday")?el("statday").value:"";
  api("/api/stats?day="+encodeURIComponent(day||"")).then(j=>{
    if(!j||j.ok===false){el("statsum").textContent="加载失败";return;}
    const sum=j.summary||{hands:0,fan:0,users:0};
    /* ★ v2.9.9：汇总行带上全局番种榜（「无番和×3、碰碰和×1」） */
    el("statsum").textContent="共 "+sum.hands+" 手 / "+sum.fan+" 番 / "+sum.users+" 人"
      +(sum.fans_txt?"　番种："+sum.fans_txt:"");
    const tb=el("statbody"); tb.innerHTML="";
    closeDetail();                 /* 换日期 / 刷新 → 明细区收起，避免停在旧数据上 */
    const cur=statCols();          /* ★ v2.9.7：只画「设置」里勾上的那几列 */
    (j.users||[]).forEach(u=>{
      const tr=document.createElement("tr");
      tr.setAttribute("data-uk",u.user_key||"");   /* ★ v2.9.9：点这一行看明细 */
      tr.innerHTML=cur.map(k=>"<td>"+statCell(k,u)+"</td>").join("");
      tb.appendChild(tr);
    });
    if(!(j.users||[]).length)
      tb.innerHTML='<tr><td colspan="'+Math.max(cur.length,1)+
        '" style="text-align:center;color:#999">暂无数据</td></tr>';
  }).catch(e=>{el("statsum").textContent="加载失败："+e.message;});
}
function seedLive(){
  fillStatDays();
  api("/api/stats?day="+encodeURIComponent(_todayStr())).then(j=>{
    liveTotal=0;liveCount=0;
    (j&&j.users||[]).forEach(u=>{if(u.uuid===MY_UUID){liveTotal+=u.total_fan||0;liveCount+=u.cnt||0;}});
    updateLive();
  }).catch(()=>{updateLive();});
}

/* ---------- 启动 ---------- */
(async function(){
  loadToken();
  MY_UUID=clientUUID();
  loadNick();probeModel();             /* ★ v2.9.12 恢复昵称 + 试着问出设备型号 */
  setLayout(loadLayout(),false);       /* ★ v2.7.8 恢复上次选的布局档位（默认「经典」）；内部会填下拉框 */
  applyBtnSize(loadBtnSize(),false);   /* ★ v2.7.6 恢复上次的按键大小（默认「最小」＝老样子）；内部会填下拉框 */
  loadSpeak();markSpeak();             /* ★ v2.9.0 恢复「读番」开关（默认关） */
  loadVoicePack();                     /* ★ v2.9.3 恢复「语音包」选择（默认服务器端那套） */
  renderStatColBoxes();buildStatHead();/* ★ v2.9.7 恢复「统计列」勾选 + 生成表头 */
  renderDetailColBoxes();             /* ★ v2.9.10 恢复「明细列」勾选 */
  /* ★ v2.9.9：统计表用**事件委托**接点击（行是后画的，不能逐个绑） */
  {const sb=el("statbody"); if(sb&&sb.addEventListener)sb.addEventListener("click",statRowClick);}
  updateJumpBtns();                    /* ★ v2.7.9 底部跳转按钮：没得滚就置灰 */
  try{
    const h=await api("/api/health");
    el("st").textContent="已连接";
  }catch(e){el("st").textContent="未连接";}
  render();
  seedLive();
  autoSize();
  document.addEventListener("keydown",e=>{
    /* ★ v2.9.4：Esc 先把「设置 / 口令」弹窗关掉，再取消待选吃 */
    if(e.key==="Escape"){hideSet();hideDlg();S.pending=[]&&render();}
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
<code>/api/fan_table</code> <code>/api/score</code> <code>/api/waits</code>
<code>/api/readout</code> <code>/audio/&lt;文件名&gt;</code>
<code>/audio/&lt;语音包&gt;/&lt;文件名&gt;</code></p>
<textarea id="req">{
  "melds": [{"kind":"chi","tiles":["W1","W2","W3"]}],
  "concealed": ["W4","W5","W6","T2","T3","T4","B5","B6","B7","B9","B9"],
  "win": "W6",
  "options": {"tsumo": true, "round_wind": "东", "seat_wind": "南", "flowers": 2}
}</textarea><br>
<button onclick="call('/api/score')">算番 /api/score</button>
<button onclick="call('/api/waits')">听牌 /api/waits</button>
<button onclick="load('/api/readout?total=123')">读番 /api/readout?total=123</button>
<button onclick="load('/api/readout?total=123&set=女声')">读番（换语音包 /api/readout?total=123&amp;set=女声）</button>
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
    "name": WEB_TITLE,
    "short_name": "算番客户端",
    "start_url": "./",
    "display": "standalone",
    "background_color": "#f4f6fa",
    "theme_color": "#2f7ff0",
    "icons": [{"src": "/tiles/J1.png", "sizes": "44x60", "type": "image/png"}],
}


def render_web_client(app_name: str = APP_NAME, show=(), speak_default: bool = True,
                      voice_set=None, voice_sets=None, stats_cols=None,
                      detail_cols=None) -> str:
    """生成 Web 客户端页面（★ v2.7.5；★ v2.9.1 加 `speak_default`；★ v2.9.3 加语音包）

    四件事：① 填应用名；② 决定模式行里「接口自测页 / 换口令」两个按钮**显示还是隐藏**（见 WEB_SHOW_ITEMS）；
    ③ ★ v2.9.1 把「默认开启自动读番」写进页面（`SPEAK_DEFAULT`），页面据此决定「🔊 读番」默认开不开；
    ④ ★ v2.9.3 把**可选语音包**与**服务器端默认那套**写进页面（`VOICE_SETS` / `VOICE_SET`），
    页面上的「语音：」下拉据此列出可选项 —— 服务器端一改，手机/平板刷新页面就跟着变。
    ⑤ ★ v2.9.7 把**统计面板可用列**与**服务器端默认显示哪几列**写进页面
    （`STATS_COL_DEF` / `STATS_COL_DEFAULT`），手机在本页「设置」里改过就以那台设备为准。
    """
    on = set(show or ())
    html = WEB_CLIENT.replace("__APP__", app_name)
    # ★ v2.9.7：Web 客户端标题固定叫「国标算番器客户端」（浏览器标签与页头都用它）
    html = html.replace("__APP_TITLE__", WEB_TITLE)
    html = html.replace("__SHOW_DEBUG__", "" if "debug" in on else "display:none")
    html = html.replace("__SHOW_TOKEN__", "" if "token" in on else "display:none")
    html = html.replace("__SPEAK_DEFAULT__", "true" if speak_default else "false")
    packs = [str(s["name"]) if isinstance(s, dict) else str(s)
             for s in (voice_sets or ())]
    cur = resolve_voice_dir(voice_set, None)
    cur_name = voice_set_of(cur)
    html = html.replace("__VOICE_SETS__", json.dumps(packs, ensure_ascii=True))
    html = html.replace("__VOICE_SET__", json.dumps(cur_name, ensure_ascii=True))
    html = html.replace("__VOICE_SET_HIDE__", "" if packs else "display:none")
    # ★ v2.9.7：统计列（全部可选项 + 服务器端默认显示的那几列）
    html = html.replace("__STATS_COL_DEF__", json.dumps(
        [{"k": k, "n": n} for k, n in STATS_COL_ITEMS], ensure_ascii=True))
    html = html.replace("__STATS_COL_DEFAULT__", json.dumps(
        list(stats_cols_normalize(stats_cols, STATS_COLS_WEB_DEFAULT)),
        ensure_ascii=True))
    # ★ v2.9.10：明细列（全部可选项 + 服务器端默认显示的那几列）
    html = html.replace("__DETAIL_COL_DEF__", json.dumps(
        [{"k": k, "n": n} for k, n in DETAIL_COL_ITEMS], ensure_ascii=True))
    html = html.replace("__DETAIL_COL_DEFAULT__", json.dumps(
        list(detail_cols_normalize(detail_cols, DETAIL_COLS_WEB_DEFAULT)),
        ensure_ascii=True))
    return html


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


def _voice_file_bytes(name: str, voice_dir: Optional[str]) -> Optional[bytes]:
    """把指定语音包里的读番音频读出来给 Web 客户端播（白名单文件名，防目录穿越）

    ★ v2.9.13：整句语音包会把录音按数字段分目录放（`女声\\100-199\\123.mp3`），
    只在包根目录找会 404 —— 根目录没有就再看它下面一层（和 `_pack_clip_count()` 同一口径）。
    """
    if not voice_dir or not voice_name_ok(name):
        return None
    p = os.path.join(voice_dir, name)
    if not os.path.exists(p):                       # 根目录没有 → 往下看一层
        try:
            for sub in sorted(os.listdir(voice_dir)):
                cand = os.path.join(voice_dir, sub, name)
                if os.path.isdir(os.path.join(voice_dir, sub)) and os.path.exists(cand):
                    p = cand
                    break
        except OSError:
            return None
    if not os.path.exists(p):
        return None
    try:
        with open(p, "rb") as fp:
            return fp.read()
    except OSError:
        return None


def _voice_mime(name: str) -> str:
    return "audio/wav" if name.lower().endswith(".wav") else "audio/mpeg"


# ★ v2.7.4：客户端（手机/平板浏览器）「提前断开」时会抛这几个异常 —— 属于正常现象，
#   不当错误处理（见下方 Handler.handle_one_request / QuietHTTPServer.handle_error）
CLIENT_GONE_ERRORS = (ConnectionResetError, ConnectionAbortedError,
                      BrokenPipeError, TimeoutError)


class Handler(BaseHTTPRequestHandler):
    server_version = "MahjongApi/1.0"
    protocol_version = "HTTP/1.1"
    engine: Engine = None          # 由 ApiServer 注入
    token: str = ""
    anon: tuple = ()               # ★ v2.5.0 免口令分组（见 ANON_GROUPS）
    show: tuple = ()               # ★ v2.7.5 Web 页面上要显示的可选按钮（见 WEB_SHOW_ITEMS）
    speak_default: bool = True     # ★ v2.9.1 Web 页面「🔊 读番」默认开不开（桌面端设置）
    voice_set: str = ""            # ★ v2.9.3 Web 页面「语音：」下拉的默认选项（桌面端设置）

    # ---- 基础
    def log_message(self, fmt, *args):        # noqa: A003
        if getattr(self.server, "verbose", False):
            sys.stderr.write("[api] %s - %s\n" % (self.address_string(), fmt % args))

    # ★ v2.7.4：手机 / 平板浏览器随时会「提前断开」—— 刷新页面、切到后台、关掉标签页，
    #   都会让 TCP 连接直接被切掉（RST）。标准库此时会在 rfile.readline() 里抛
    #   ConnectionResetError，并在控制台打一整屏 traceback：
    #       Exception occurred during processing of request from ('192.168.x.x', 52542)
    #   那是**噪声，不是程序出错**（不影响服务、不影响算番）；这里直接忽略。
    def handle_one_request(self) -> None:      # noqa: N802
        try:
            super().handle_one_request()
        except CLIENT_GONE_ERRORS:
            self.close_connection = True

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Api-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, obj, status: int = 200, ctype: str = "application/json; charset=utf-8",
              no_store: bool = False):
        if isinstance(obj, (dict, list)):
            body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        else:
            body = str(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if no_store:
            # ★ v2.9.6：HTML 页面一律不缓存。否则程序已经升级到新版本，手机浏览器还拿着
            #   昨天那份旧页面——新加的按钮（比如「统计」）就永远显示不出来，
            #   看起来像「功能没实现」，实际只是页面没更新。
            self.send_header("Cache-Control", "no-store, max-age=0")
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

    # ---- 统计（★ v2.9.6）
    def _record_score(self, out: dict, body: dict) -> None:
        """把一次算番结果落库。失败仅记日志，绝不抛异常影响算番主流程。"""
        stats = getattr(self, "stats", None)
        if stats is None or not isinstance(out, dict):
            return
        try:
            uuid = (str(body.get("uuid") or "").strip()
                    or (self.headers.get("X-Client-UUID") or "").strip())
            ip = self.client_address[0] if self.client_address else ""
            ua = self.headers.get("User-Agent") or ""
            uk = user_key_from(uuid, ip, ua)
            ts_ms = int(time.time() * 1000)
            total = int(out.get("total") or 0)
            base = int(out.get("base") or 0)
            reach = 1 if out.get("reach_standard") else 0
            fans_n = len(out.get("fans") or [])
            # 去重签名：同一手牌（UUID + 牌 + 和张）2 秒内重复请求不重复记
            sig = hand_sig(uuid,
                           json.dumps(body.get("concealed"), ensure_ascii=False),
                           json.dumps(body.get("melds"), ensure_ascii=False),
                           body.get("win") or "")
            # ★ v2.9.12：客户端上报的昵称 / 设备型号
            #   型号：navigator.userAgentData.getHighEntropyValues(['model']) 拿到的，
            #   比 UA 解析准（UA 在安卓 16+ 被削减成 "K"）。局域网明文 http 多半拿不到，
            #   拿不到就是空串，退回 UA 解析，不影响别的。
            nick = str(body.get("nick") or "").strip()[:24]
            model = str(body.get("model") or "").strip()[:40]
            if nick:
                # 走一遍冲突处理：同名同 IP 过户、异 IP 加 #N，拿回真正生效的名字
                nick = stats.set_nick(uk, ip, nick)
            stats.record(ts_ms=ts_ms, user_key=uk, uuid=uuid, client_type="web",
                         ip=ip, ua=ua, total_fan=total, base=base,
                         reach=reach, fans_n=fans_n, sig=sig,
                         # ★ v2.9.9：番种名落库（明细里能看到这一手算了哪些番）
                         fans=fans_text(out.get("fans")),
                         # ★ v2.9.12
                         model=model, nick=nick)
        except Exception as exc:             # noqa: BLE001
            try:
                sys.stderr.write("[stats] 记录算番失败：%r\n" % (exc,))
            except Exception:
                pass

    def _stats_json(self) -> dict:
        """GET /api/stats 的返回（★ v2.9.6）：按天聚合的全部用户统计。

        ?day=YYYY-MM-DD 限定某天；不带 day 则统计全部日期（按用户跨天合计）。
        """
        stats = getattr(self, "stats", None)
        if stats is None:
            return {"ok": False, "error": "统计库不可用"}
        q = parse_qs(urlparse(self.path).query)
        day = (q.get("day") or [""])[0].strip() or None
        return {"ok": True, "day": day,
                "summary": stats.total_summary(day),
                "users": stats.aggregate(day)}

    def _stats_detail_json(self) -> dict:
        """GET /api/stats_detail?user_key=…&day=…（★ v2.9.9）：某个用户的逐手牌明细

        不带 day = 全部日期。返回 `rows`（时间倒序）+ 该用户的番种榜 `fans`。
        user_key 是必填；拿不到就给 ok:false（前端弹提示，不要静默空表）。
        """
        stats = getattr(self, "stats", None)
        if stats is None:
            return {"ok": False, "error": "统计库不可用"}
        q = parse_qs(urlparse(self.path).query)
        uk = (q.get("user_key") or [""])[0].strip()
        day = (q.get("day") or [""])[0].strip() or None
        if not uk:
            return {"ok": False, "error": "缺少 user_key"}
        try:
            rows = stats.detail_rows(uk, day)
            fans = [{"name": n, "cnt": c} for n, c in stats.fans_top(day, uk)]
        except Exception as exc:       # noqa: BLE001
            return {"ok": False, "error": "读取明细失败：%r" % (exc,)}
        return {"ok": True, "user_key": uk, "day": day, "rows": rows,
                "fans": fans}

    def _set_nick_json(self, body: Optional[dict] = None) -> dict:
        """POST /api/set_nick（★ v2.9.12）：客户端上报「我叫什么」

        请求体 {uuid, nick}；空 nick = 取消昵称。
        返回 **实际生效**的名字 `nick` —— 可能带 #2/#3 后缀（撞名且不同 IP 时），
        前端要把它回写进 localStorage，否则用户看到的和实际显示的不一样。

        ★ body 由 do_POST 传进来：请求体只能读一次，这里再 `self._json_body()`
          会读不到东西（do_POST 已经读过了）。
        """
        stats = getattr(self, "stats", None)
        if stats is None:
            return {"ok": False, "error": "统计库不可用"}
        if body is None:
            try:
                body = self._json_body()
            except ApiError as exc:
                return {"ok": False, "error": str(exc)}
        uuid = (str(body.get("uuid") or "").strip()
                or (self.headers.get("X-Client-UUID") or "").strip())
        ip = self.client_address[0] if self.client_address else ""
        ua = self.headers.get("User-Agent") or ""
        uk = user_key_from(uuid, ip, ua)
        raw = str(body.get("nick") or "").strip()[:24]
        try:
            nick = stats.set_nick(uk, ip, raw)
        except Exception as exc:              # noqa: BLE001
            sys.stderr.write("[stats] 设置昵称失败：%r\n" % (exc,))
            return {"ok": False, "error": "设置昵称失败"}
        return {"ok": True, "user_key": uk, "nick": nick}

    def _query_readout(self) -> dict:
        """读番的 GET 查询串 → 与 POST 相同的结构（/api/readout?total=123&speak=1&set=女声）"""
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        body: dict = {}
        for key in ("total", "n"):
            if key in q:
                body["total"] = q[key]
                break
        for key in ("prefix", "speak"):
            if key in q:
                body[key] = str(q[key]).lower() in ("1", "true", "yes", "on")
        for key in ("set", "voice_set", "pack"):        # ★ v2.9.3 选语音包
            if key in q:
                body["set"] = q[key]
                break
        return body

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
            return self._send(render_web_client(APP_NAME, getattr(self, "show", ()),
                                                bool(getattr(self, "speak_default", True)),
                                                voice_set=getattr(self, "voice_set", ""),
                                                voice_sets=voice_sets(
                                                    getattr(self.engine, "base_dir", None)),
                                                # ★ v2.9.7：统计面板默认显示哪几列
                                                stats_cols=getattr(
                                                    self, "stats_cols", None),
                                                # ★ v2.9.10：明细面板默认显示哪几列
                                                detail_cols=getattr(
                                                    self, "detail_cols", None)),
                              ctype="text/html; charset=utf-8", no_store=True)
        if path == "/debug":
            return self._send(DEBUG_HTML.replace("__APP__", APP_NAME),
                              ctype="text/html; charset=utf-8", no_store=True)
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
        # ★ v2.9.0：读番音频（和牌面图一样按白名单放行，手机端直接播）
        # ★ v2.9.3：支持 `/audio/<语音包>/<文件>`（页面选了哪套就取哪套）；不带包名就用服务器的当前套
        if path.startswith("/audio/"):
            rest = path[len("/audio/"):]
            head, _, tail = rest.rpartition("/")
            pack, name = (head, tail) if head else ("", tail)
            pack, name = unquote(pack), unquote(name)
            data = _voice_file_bytes(name, self.engine.voice_dir(pack or None))
            if data is None:                      # 有些客户端直接把中文按原字节发过来
                raw = unquote(head.encode("latin-1", "ignore").decode("utf-8", "ignore"))
                name = unquote(tail.encode("latin-1", "ignore").decode("utf-8", "ignore"))
                data = _voice_file_bytes(name, self.engine.voice_dir(raw or None))
            if data is None:
                return self._fail("找不到读番音频：%s（见 /api/help）" % name, 404)
            self.send_response(200)
            self.send_header("Content-Type", _voice_mime(name))
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
                body = self._query_body()
                out = self.engine.score(body)
                self._record_score(out, body)
                return self._send(out)
            if path == "/api/stats":
                return self._send(self._stats_json())
            if path == "/api/stats_detail":      # ★ v2.9.9 逐手牌明细
                return self._send(self._stats_detail_json())
            if path in ("/api/waits", "/api/wins", "/api/waits_all"):
                return self._send(self.engine.waits(self._query_body(),
                                                    only_reach=path != "/api/waits_all"))
            if path == "/api/readout":             # ★ v2.9.0 读番（GET 简写形式）
                return self._send(self.engine.readout_request(self._query_readout()))
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
                out = self.engine.score(body)
                self._record_score(out, body)
                return self._send(out)
            if path in ("/api/waits", "/api/wins", "/api/waits_all"):
                return self._send(self.engine.waits(body,
                                                    only_reach=path != "/api/waits_all"))
            if path == "/api/readout":             # ★ v2.9.0 读番
                return self._send(self.engine.readout_request(body))
            if path == "/api/set_nick":            # ★ v2.9.12 上报昵称
                return self._send(self._set_nick_json(body))
            if path in ("/api/health", "/api/version"):
                return self.do_GET()
            self._fail("未知接口：%s（见 /api/help）" % path, 404)
        except ApiError as exc:
            self._fail(exc.message, exc.status)
        except Exception as exc:               # noqa: BLE001
            self._fail("内部错误：%r" % (exc,), 500)


class QuietHTTPServer(ThreadingHTTPServer):
    """★ v2.7.4：把「客户端提前断开」类异常的 traceback 静音

    `socketserver` 默认的 `handle_error()` 会把**任何**异常连 traceback 一起打到控制台，
    而手机上最常见的就是刷新/关闭页面导致的 ConnectionResetError（一大屏
    「Exception occurred during processing of request from ('192.168.x.x', 52542)」）。
    那类异常对服务毫无影响，属于噪声；**其余异常照旧完整打印**（不掩盖真问题）。
    开了 verbose 时会打一行简短提示，便于排查「连接数异常」这类情况。
    """

    def handle_error(self, request, client_address) -> None:     # noqa: ARG002
        exc = sys.exc_info()[1]
        if isinstance(exc, CLIENT_GONE_ERRORS):
            if getattr(self, "verbose", False):
                ip = client_address[0] if client_address else "?"
                sys.stderr.write("[api] %s 提前断开连接（正常现象，已忽略）\n" % ip)
            return
        super().handle_error(request, client_address)


class ApiServer:
    """本地 API 服务（可在主程序里内嵌启动，也可单独运行）"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 token: str = "", rules_path: Optional[str] = None,
                 verbose: bool = False, anon=None, show=None,
                 base_dir: Optional[str] = None, speak_default: bool = True,
                 voice_set: Optional[str] = None,
                 stats: Optional["StatsDB"] = None, stats_cols=None,
                 detail_cols=None):
        self.host = host
        self.port = int(port)
        self.token = token or ""
        # ★ v2.5.0 免口令分组：anon=None 表示「用默认」（web+debug，与旧版行为一致）；
        #   anon=() 才是「全部要口令」。
        self.anon = tuple(ANON_DEFAULT if anon is None else anon)
        # ★ v2.7.5：Web 页面上要显示的可选按钮（接口自测页 / 换口令），默认都不显示
        self.show = tuple(WEB_SHOW_DEFAULT if show is None else show)
        self.verbose = verbose
        # ★ v2.9.0：base_dir＝算番器所在目录（读番找《数字》音频、规则表用）；None＝本文件所在目录
        self.base_dir = base_dir or HERE
        # ★ v2.9.1：Web 页面「🔊 读番」默认状态（桌面端「设置 → 通用 → 默认开启自动读番」传进来）
        self.speak_default = bool(speak_default)
        # ★ v2.9.3：服务器端默认用哪一套录音（桌面端「设置 → 通用 → 语音包」传进来；
        #   空＝用默认包；页面上的「语音：」下拉初始值也用它）
        self.voice_set = str(voice_set or "")
        # ★ v2.9.7：Web 统计弹窗默认显示哪几列（桌面端「设置 → 通用 → 统计显示列」传进来；
        #   手机自己在本页「设置」里改过就以那台设备为准，存在 localStorage）
        self.stats_cols = stats_cols_normalize(stats_cols, STATS_COLS_WEB_DEFAULT)
        # ★ v2.9.10：Web 明细面板默认显示哪几列（桌面端「设置 → 通用 → 明细显示列」传进来）
        self.detail_cols = detail_cols_normalize(detail_cols,
                                                 DETAIL_COLS_WEB_DEFAULT)
        self.engine = Engine(rules_path, base_dir=self.base_dir,
                             speak_default=self.speak_default, voice_set=self.voice_set)
        # ★ v2.9.6：算番统计库（SQLite / WAL）。
        #   优先用调用方传进来的实例（桌面端与 Web 端共用同一份文件）；
        #   没传则在 base_dir 下新建。落库失败绝不能影响 API 主流程，所以这里兜底。
        try:
            if stats is None:
                stats = StatsDB(os.path.join(self.base_dir, "mahjong_stats.db"))
            self.stats = stats
        except Exception as exc:      # noqa: BLE001
            sys.stderr.write("[stats] 统计库初始化失败（不影响算番）：%r\n" % (exc,))
            self.stats = None
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
                        "anon": self.anon, "show": self.show,
                        "speak_default": self.speak_default,
                        "stats": self.stats,
                        # ★ v2.9.3：页面「语音：」下拉的默认项（解析后的真实包名）
                        "voice_set": voice_set_of(
                            resolve_voice_dir(self.voice_set, self.base_dir))})
        try:
            self._httpd = QuietHTTPServer((self.host, self.port), handler)
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
    # ★ v2.9.1：`--help` / 横幅里若有 GBK 编不出的字符（emoji 等），
    #   argparse 的 print_help 会直接抛 UnicodeEncodeError 把 `--help` 弄崩
    #   （真踩过：help 文案里一个 🔊 就让 `python mahjong_api.py --help` 报错）。
    #   这里尽量把 stdout 改成 UTF-8，和 mahjong_core.cli_main 一个做法；改不了就算了。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                         # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="%s · 本地 HTTP API" % APP_NAME)
    ap.add_argument("--host", default=DEFAULT_HOST,
                    help="监听地址，默认 %s（仅本机）；局域网请用 0.0.0.0" % DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口，默认 %d" % DEFAULT_PORT)
    ap.add_argument("--token", default="", help="可选口令：请求头 X-Api-Token 或 ?token=")
    ap.add_argument("--anon", default=None,
                    help="免口令分组（逗号分隔）：web,debug,info,score,waits；"
                         "none = 全部要口令；默认 " + ",".join(ANON_DEFAULT))
    ap.add_argument("--show", default=None,
                    help="Web 页面上要显示的按钮（逗号分隔）：debug（接口自测页）、"
                         "token（换口令）；默认**两个都不显示**")
    ap.add_argument("--dir", default=None, metavar="目录",
                    help="算番器所在目录（找《%s》读番音频、规则表）；"
                         "默认＝本文件所在目录" % VOICE_DIR_NAME)
    ap.add_argument("--speak-default", default="1", choices=("0", "1"), dest="speak_default",
                    help="Web 页面上「读番」按钮默认开不开：1（默认）/ 0；"
                         "页面自己点过就以页面上的选择为准")
    ap.add_argument("--voice-set", "--set", default=None, metavar="语音包", dest="voice_set",
                    help="读番用《%s》下哪一套录音（目录名）；默认「%s」。可选：%s"
                         % (VOICE_DIR_NAME, VOICE_SET_DEFAULT,
                            "、".join(voice_set_label(n) for n in voice_set_names())
                            or "（没找到任何语音包）"))
    ap.add_argument("--verbose", action="store_true", help="打印访问日志")
    args = ap.parse_args(argv)
    if args.anon is None:
        anon = list(ANON_DEFAULT)
    elif str(args.anon).strip().lower() in ("", "none", "-"):
        anon = []
    else:
        anon = [k.strip() for k in str(args.anon).split(",") if k.strip()]
    if args.show is None:
        show = list(WEB_SHOW_DEFAULT)          # 默认：接口自测页 / 换口令 都不显示
    else:
        show = [k.strip() for k in str(args.show).split(",") if k.strip()]

    srv = ApiServer(args.host, args.port, args.token, verbose=args.verbose,
                    anon=anon, show=show, base_dir=args.dir,
                    speak_default=str(args.speak_default) != "0",
                    voice_set=args.voice_set)
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
    print("  页面按钮  : %s（--show debug,token 可显示接口自测页 / 换口令）"
          % ("、".join(show) if show else "都不显示（默认）"))
    vdir = srv.engine.voice_dir()
    print("  读番音频  : /api/readout?total=123 → %s（%s）"
          % (vdir or "没找到《%s》目录（用 --dir 指到程序目录）" % VOICE_DIR_NAME,
             "本机可出声" if VoicePlayer.available() else "本机不能出声（非 Windows）"))
    packs = voice_sets(args.dir)
    print("  语音包    : 当前「%s」（%d 段）；可选：%s（--voice-set 名字 可换，"
          "页面上的「语音：」下拉也能换）"
          % (voice_set_label(voice_set_of(vdir)), count_voice_clips(args.dir, args.voice_set),
             "、".join("%s(%d 段)" % (voice_set_label(str(s["name"])), s["clips"])
                       for s in packs) or "（没找到任何语音包）"))
    print("  自动读番  : 页面默认 %s（--speak-default 0 可关；页面自己点过就听页面的）"
          % ("开启" if srv.speak_default else "关闭"))
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
