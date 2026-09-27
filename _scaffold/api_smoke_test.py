# -*- coding: utf-8 -*-
"""本地 HTTP API 冒烟测试（真实起服务 + 真实 HTTP 请求）

跑法：
    & "D:/Program Files/Python310/python.exe" -u _scaffold/api_smoke_test.py
日志写 _scaffold/_api_out.txt（UTF-8），退出码 0 = 全通过。
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import mahjong_api as A                                                    # noqa: E402

LOG = []
PASS = FAIL = 0
OUT = os.path.join(HERE, "_api_out.txt")


def log(msg=""):
    LOG.append(str(msg))
    try:
        with io.open(OUT, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write("\n".join(LOG))
    except Exception:                                                      # noqa: BLE001
        pass
    try:
        print(msg, flush=True)
    except Exception:                                                      # noqa: BLE001
        pass


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        log("  [OK]   %s" % name)
    else:
        FAIL += 1
        log("  [FAIL] %s  %s" % (name, extra))


def req(url, method="GET", body=None, headers=None, raw=None):
    """返回 (status, json_or_text, headers)"""
    data = None
    hdrs = dict(headers or {})
    if raw is not None:
        data = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            txt = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(txt), dict(resp.headers)
            except Exception:                                              # noqa: BLE001
                return resp.status, txt, dict(resp.headers)
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(txt), dict(e.headers)
        except Exception:                                                  # noqa: BLE001
            return e.code, txt, dict(e.headers)


def main():
    log("=" * 74)
    log("国标麻将算番器 —— 本地 HTTP API 冒烟测试")
    log("时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 74)

    srv = A.ApiServer("127.0.0.1", 0)
    url = srv.start()
    log("\n【1】服务启动：%s" % url)
    check("端口由系统分配", srv.port_actual > 0 and srv.running, srv.port_actual)

    # ---------------- 基础端点
    log("\n【2】基础端点")
    st, js, hd = req(url + "/api/health")
    check("GET /api/health", st == 200 and js.get("ok") and js.get("server") == "mahjong-api",
          "%s %s" % (st, js))
    check("CORS 头存在", hd.get("Access-Control-Allow-Origin") == "*", hd)
    st, js, _ = req(url + "/api/version")
    check("GET /api/version 番种数 81", st == 200 and js.get("engine_fans") == 81
          and js.get("rules_loaded"), str(js)[:120])
    st, js, _ = req(url + "/api/tiles")
    tiles = js.get("tiles") if isinstance(js, dict) else None
    check("GET /api/tiles 34 张", st == 200 and isinstance(tiles, list) and len(tiles) == 34,
          str(js)[:80])
    check("牌张表首尾正确", tiles[0]["code"] == "B1" and tiles[-1]["code"] == "J3",
          "%s %s" % (tiles[0], tiles[-1]))
    check("牌张表带花色/数字", tiles[0]["suit"] == "筒" and tiles[8]["num"] == 9,
          str(tiles[0]))
    st, js, _ = req(url + "/api/fan_table")
    table = js.get("table") if isinstance(js, dict) else None
    total_fans = sum(len(r["fans"]) for r in table) if table else 0
    check("GET /api/fan_table 12 档", st == 200 and isinstance(table, list) and len(table) == 12,
          str(js)[:80])
    check("番种合计 81", total_fans == 81, total_fans)
    check("番表含定义文本", bool(table[0]["fans"][0]["definition"]), str(table[0])[:80])
    st, js, hd = req(url + "/api/help")
    check("GET /api/help 文本", st == 200 and "api/score" in str(js), st)

    # ---------------- Web 客户端（手机/平板浏览器直接算番）
    log("\n【2b】Web 客户端 / 静态资源")
    st, html, hd = req(url + "/")
    check("GET / 返回 Web 客户端页面", st == 200 and "<!doctype html" in html.lower(),
          str(html)[:60])
    check("HTML Content-Type", "text/html" in hd.get("Content-Type", ""),
          hd.get("Content-Type"))
    check("页面含牌池/结果/听牌 区块",
          all(k in html for k in ('id="pool"', 'id="fans"', 'id="waits"')), "")
    check("页面引用牌面图路由", "/tiles/" in html, "")
    check("页面调用 /api/score 与 /api/waits",
          "/api/score" in html and "/api/waits" in html, "")
    check("页面含 8 张花牌编码", all(k in html for k in ("S1", "S4", "P1", "P4")), "")
    check("页面支持 ?token= 与 localStorage",
          "localStorage" in html and "mj_token" in html, "")
    check("页面未残留模板占位符", "__APP__" not in html, "")
    # ★ 白盒回归（浏览器里踩过的坑，Python 测试只能盯住源码特征）
    check("算番请求把和张拼进 concealed（14 张口径）",
          "hand.push(S.win)" in html, "")
    check("设了和张后走算番分支（不再落到听牌分支）",
          "withWin>=need+1" in html, "")
    check("牌池只建一次、刷新只改状态（避免快速连点丢点击）",
          "function buildPool" in html and "function updatePool" in html, "")
    check("点花牌走选花牌逻辑（不进手牌）",
          "/^[SP]/.test(code)" in html, "")
    # ★ v2.4.4：Web 端布局与桌面版一致（牌池 4 行 → 模式+重置 → 选项四行 → 已选牌 → 听牌 → 结果）
    check("选项区四行齐全（复选框/圈风/风位/花牌）",
          all(k in html for k in ('id="opts"', 'id="rwind"', 'id="swind"',
                                  'id="flowers"', 'id="fcount"')), "")
    check("花牌已移出牌池（牌池只有索/筒/万/字牌 4 行）",
          '["S1","S2","S3","S4","P1","P2","P3","P4"]]' not in html
          and "const FLOWER=" in html, "")
    check("牌池 → 模式 → 选项 → 已选牌 的顺序与桌面版一致",
          html.index('id="pool"') < html.index('id="modes"')
          < html.index('id="opts"') < html.index('id="m_melds"'), "")
    check("花牌行只建一次、刷新只改状态",
          "function buildFlowers" in html and "function updateFlowers" in html, "")
    check("花牌固定顺序（春夏秋冬梅兰竹菊）",
          "FLOWER.filter(c=>S.flowers.includes(c))" in html, "")
    check("重置=全部复位（含花牌/选项/风圈风位）",
          "S.flowers=[]" in html and 'round:"东"' in html, "")
    check("底部两个按钮＝滚到牌池/结果区块（不再是无反馈的 scrollTo 顶/底）",
          'id="jump_pool"' in html and 'id="jump_res"' in html
          and "onclick=\"gotoBlock('c_pool')\"" in html
          and "onclick=\"gotoBlock('c_res')\"" in html, "")
    check("跳转目标卡片有 id（c_pool / c_res）",
          'class="card" id="c_pool"' in html and 'class="card" id="c_res"' in html, "")
    check("跳转后区块高亮（.flash）+ 不足一屏时置灰（button:disabled）",
          "card.flash{outline:2px solid var(--blue)" in html
          and "button:disabled{opacity:.45" in html, "")
    check("gotoBlock 滚到区块（躲开固定顶栏）+ updateJumpBtns 在启动/render/resize 都跟",
          "function gotoBlock(id){" in html and "function updateJumpBtns(){" in html
          and "setTimeout(updateJumpBtns,0)" in html and "updateJumpBtns();" in html
          and "setTimeout(()=>{autoSize();updateJumpBtns();},120)" in html, "")
    check("牌池每行是 flex 横排（四行 9/9/9/7 张，不是一行一只）",
          "#pool .line,.pool .line{display:flex" in html
          or "#pool .line{display:flex" in html
          or ".pool .line{display:flex" in html, "")
    check("牌池容器带 .pool 类（行样式才生效）",
          'class="pool" id="pool"' in html, "")
    # ★ v2.4.5：手机没有右键 → 减牌入口必须「单指可点」
    check("牌上红色数字是可点的「−1」按钮",
          'class="cnt hide" data-minus=' in html and "function bindMinus" in html, "")
    check("角标事件被截住（不会冒泡成加一张）",
          "e.stopPropagation" in html and "bindMinus();" in html, "")
    check("已选牌区点一张可减（立牌/和张）",
          "function imgClk" in html and "function minus(code)" in html, "")
    check("提示文案不再依赖右键",
          "红色数字" in html and "长按 / 右键减一张" not in html, "")
    check("禁掉长按系统菜单/文本选择（手机体验）",
          "-webkit-touch-callout:none" in html and "user-select:none" in html, "")
    # ★ v2.7.0：手机/平板「自适应」布局（与经典固定布局共存，默认仍是经典）
    check("牌尺寸改成 CSS 变量、默认值＝经典固定尺寸（旧布局不变）",
          "--tw:38px" in html and "--th:52px" in html and "--pw:34px" in html
          and "--ph:46px" in html and "--fw:34px" in html and "--ww:28px" in html, "")
    check("牌池/已选牌/花牌/候选牌都走变量",
          "width:var(--tw);height:var(--th)" in html
          and "width:var(--pw);height:var(--ph)" in html
          and "width:var(--fw);height:var(--fh)" in html
          and "width:var(--ww);height:var(--wh)" in html, "")
    check("牌池行内间距也走变量（自适应时会收紧）",
          "gap:var(--pgap)" in html, "")
    check("布局按钮：5 档循环（经典→自适应→大→更大→最大）", 'id="lybtn"' in html
          and 'onclick="cycleLayout()"' in html and "布局：经典（1/5）" in html, "")
    check("默认布局是经典（第 1 档）——不动老布局",
          'layout:"fixed"' in html and "const LAYOUT_DEFAULT=0;" in html
          and "const LAYOUT_LEVELS=[" in html, "")
    import re as _re
    LBLK = html.split("const LAYOUT_LEVELS=[", 1)[1].split("];", 1)[0]
    lnames = _re.findall(r'name:"([^"]+)"', LBLK)
    check("布局 5 档名字：经典/自适应/大/更大/最大",
          lnames == ["经典", "自适应", "大", "更大", "最大"], lnames)
    lsc = [float(x) for x in _re.findall(r"scale:([\d.]+)", LBLK)]
    check("布局档位系数：0（经典固定）/ 1（自适应）/ 1.2 / 1.4 / 1.6",
          lsc == [0, 1, 1.2, 1.4, 1.6], lsc)
    check("布局选择记在 localStorage（mj_layout2，存档位索引）",
          'const LAYOUT_KEY="mj_layout2"' in html
          and "localStorage.setItem(LAYOUT_KEY,String(LAYOUT_IDX))" in html, "")
    check("自适应：按屏幕宽高算牌尺寸（一行 9 张 + 高度上限）",
          "function autoSize()" in html and "nine=(avail-pgap*8-4)/9" in html
          and "Math.min(vh*0.115,74)" in html, "")
    check("自适应基准夹紧区间不变（20~46），3~5 档在基准上乘系数",
          "Math.max(20,Math.min(base,46))" in html
          and "Math.round(base*L.scale)" in html, "")
    check("经典模式：清掉 JS 写的变量，回到 CSS 默认（像素级还原旧布局）",
          "LAYOUT_VARS.forEach(k=>root.style.removeProperty(k))" in html, "")
    check("窗口尺寸/横竖屏变化时会重算（防抖）",
          'addEventListener("resize",autoSizeLater)' in html
          and 'addEventListener("orientationchange",autoSizeLater)' in html
          and "function autoSizeLater()" in html, "")
    # ★ v2.7.1：副露渲染（暗杠必须与明杠不同：面·背·背·面）
    check("副露渲染有专门函数（不再把所有牌平铺）",
          "function meldHtml()" in html and 'el("m_melds").innerHTML=meldHtml()' in html,
          "")
    check("暗杠渲染为 面·背·背·面（中间两张用牌背 empty.png）",
          'codes=[t[0],"empty","empty",t[3]]' in html
          and 'q("/tiles/empty.png")' in html, "")
    check("明杠/碰/吃仍是全部正面（只有暗杠盖牌）",
          'if(m.kind==="kong"&&m.concealed&&t.length>=4)' in html, "")
    check("不同副露之间有间隔（.meldgap）",
          'class="meldgap"' in html and ".meldgap{display:inline-block" in html, "")
    st, js, _ = req(url + "/debug")
    check("GET /debug 接口自测页", st == 200 and "接口自测" in str(js), str(js)[:60])
    st, js, hd = req(url + "/manifest.webmanifest")
    check("GET /manifest.webmanifest",
          st == 200 and isinstance(js, dict) and js.get("short_name") == "麻将算番",
          "%s %s" % (st, str(js)[:60]))
    check("manifest Content-Type", "manifest+json" in hd.get("Content-Type", ""),
          hd.get("Content-Type"))
    st, png, _ = req(url + "/tiles/B1.png")
    check("GET /tiles/B1.png 图片", st == 200 and isinstance(png, str) and png[1:4] == "PNG",
          st)
    st, png, _ = req(url + "/tiles/empty.png")
    check("GET /tiles/empty.png", st == 200, st)
    st, png, _ = req(url + "/tiles/P1.png")
    check("花牌图 /tiles/P1.png", st == 200 and len(str(png)) > 1000, st)
    st, js, _ = req(url + "/tiles/nope.png")
    check("非法牌面图 → 404", st == 404, st)
    st, js, _ = req(url + "/tiles/..%2Fmahjong_core.py")
    check("牌面图路由拒绝路径穿越", st == 404 and "找不到" in str(js),
          "%s %s" % (st, str(js)[:50]))

    # ---------------- 算番
    log("\n【3】算番 POST /api/score")
    body = {"concealed": ["W1", "W1", "W1", "W1", "W2", "W2", "W3", "W3",
                          "W4", "W4", "W5", "W5", "W6", "W6"],
            "options": {"tsumo": True}}
    st, js, _ = req(url + "/api/score", "POST", body)
    names = [f["name"] for f in js.get("fans", [])]
    check("七对含四张 → 49 番", st == 200 and js.get("total") == 49, "%s %s" % (st, js))
    check("番种含 七对/清一色/自摸", {"七对", "清一色", "自摸"} <= set(names), names)
    check("不计四归一（必然并存）", "四归一" not in names, names)
    check("起和达标 reach_standard", js.get("reach_standard") is True, js)
    check("返回和张", js.get("win") == "W6", js.get("win"))

    # 副露 + 暗杠（张数口径：14 - 3×副露数）
    body = {"melds": [{"kind": "kong", "tiles": ["W1", "W1", "W1", "W1"], "concealed": True},
                      {"kind": "chi", "tiles": ["T7", "T8", "T9"]}],
            "concealed": ["B1", "B2", "B3", "B4", "B5", "B6", "B9", "B9"],
            "win": "B9"}
    st, js, _ = req(url + "/api/score", "POST", body)
    check("副露+暗杠算得出番", st == 200 and js.get("ok") and "暗杠" in
          [f["name"] for f in js.get("fans", [])], "%s %s" % (st, js))
    check("副露不吃七对", "七对" not in [f["name"] for f in js.get("fans", [])], js)

    # 字牌 + 门风
    body = {"concealed": ["F3", "F3", "F3", "B1", "B2", "B3", "B4", "B5", "B6",
                          "T7", "T8", "T9", "B9", "B9"],
            "win": "B9", "options": {"seat_wind": "西"}}
    st, js, _ = req(url + "/api/score", "POST", body)
    check("门风刻（西）生效", st == 200 and "门风刻" in
          [f["name"] for f in js.get("fans", [])], "%s %s" % (st, js))

    # 花牌
    body = {"concealed": ["W1", "W1", "W1", "W1", "W2", "W3", "W4", "W5",
                          "W6", "W7", "W8", "W9", "W9", "W9"],
            "win": "W1", "options": {"flower_tiles": ["S1", "P4", "S3"]}}
    st, js, _ = req(url + "/api/score", "POST", body)
    check("花牌 3 张 → 花牌 3 分", st == 200 and js.get("flowers") == 3, "%s %s" % (st, js))
    check("花牌不计入起和分", js.get("base") == js.get("total") - 3, js)

    # counts 形式 + GET 形式
    log("\n【4】其它入参形式")
    body = {"concealed": {"W1": 2, "W2": 2, "W3": 2, "W4": 2, "W5": 2, "W6": 2, "J1": 2},
            "win": "J1"}
    st, js, _ = req(url + "/api/score", "POST", body)
    check("concealed 支持 {牌:张数}", st == 200 and js.get("total") == 30,
          "%s %s" % (st, js))
    q = ("/api/score?concealed=" + urllib.parse.quote(
        '["W1","W1","W1","W1","W2","W3","W4","W5","W6","W7","W8","W9","W9","W9"]')
         + "&win=W1&tsumo=1")
    st, js, _ = req(url + q)
    check("GET /api/score 简写形式", st == 200 and js.get("total", 0) > 0, "%s %s" % (st, js))
    check("GET 形式能识别 tsumo", "自摸" in [f["name"] for f in js.get("fans", [])], js)

    # ---------------- 听牌
    log("\n【5】听牌 POST /api/waits")
    body = {"concealed": ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                          "W7", "W8", "W9", "W9", "W9"],
            "options": {"tsumo": True}}
    st, js, _ = req(url + "/api/waits", "POST", body)
    waits = js.get("waits") if isinstance(js, dict) else None
    check("九莲宝灯听牌 9 张（1~9 万均可和）", st == 200 and js.get("count") == 9,
          "%s %s" % (st, js.get("count")))
    check("九莲宝灯 88 番（听任意张都是 88+）", waits and all(
        any(f["name"] == "九莲宝灯" for f in w["fans"]) and w["total"] >= 88
        for w in waits), str(waits)[:120])
    check("听牌项带 tile/name/total", waits and {"tile", "name", "total"} <= set(waits[0]),
          str(waits)[:120])
    check("听 9 万算得出九莲宝灯", any(w["tile"] == "W9" and any(
        f["name"] == "九莲宝灯" for f in w["fans"]) for w in waits), str(waits)[:160])

    body = {"concealed": ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
                          "B9", "T1", "T2", "T3", "W5"]}
    st, js, _ = req(url + "/api/waits_all", "POST", body)
    check("/api/waits_all 不筛起和分", st == 200 and js.get("count", 0) >= 1,
          "%s %s" % (st, js))
    check("waits_all 含不足 8 分项", any(not w["reach_standard"] for w in js.get("waits", []))
          or all(w["reach_standard"] for w in js.get("waits", [])), str(js)[:100])

    # ---------------- 错误处理
    log("\n【6】错误处理")
    st, js, _ = req(url + "/api/score", "POST", {"concealed": ["X9"], "win": "X9"})
    check("非法牌张代码 → 400", st == 400 and js.get("ok") is False
          and "无效的牌张代码" in js.get("error", ""), "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST", {"concealed": ["W1", "W2"], "win": "W1"})
    check("张数不足 → 400 提示", st == 400 and "14" in js.get("error", ""),
          "%s %s" % (st, js))
    # ★ 口径踩坑回归：concealed 必须「含和张」的整手牌（13 张 + win 应被拒）
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                                   "W7", "W8", "W9", "W9", "W9"], "win": "W9"})
    check("concealed 不含和张（13 张）→ 400 并说明应为 14 张",
          st == 400 and "应为 14 张" in js.get("error", ""), "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                                   "W7", "W8", "W9", "W9", "W9", "W9"], "win": "W9"})
    check("concealed 含和张（14 张）→ 九莲宝灯 106 番",
          st == 200 and js.get("total") == 106, "%s %s" % (st, js.get("total")))
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                                   "W7", "W8", "W9", "W9", "W9", "W9"], "win": "B9"})
    check("和张不在 concealed 里 → 400",
          st == 400 and "不在" in js.get("error", ""), "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W1", "W1", "W1", "W1", "W2", "W3", "W4",
                                   "W5", "W6", "W7", "W8", "W9", "W9"], "win": "W9"})
    check("同一张牌 5 张 → 400", st == 400 and "4" in js.get("error", ""),
          "%s %s" % (st, js))
    st, js, _ = req(url + "/api/waits", "POST", {"concealed": ["W1", "W2"]})
    check("听牌张数不对 → 400", st == 400 and "听牌时" in js.get("error", ""),
          "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST", raw="{not json")
    check("请求体非 JSON → 400", st == 400 and js.get("ok") is False, "%s %s" % (st, js))
    st, js, _ = req(url + "/api/melds", "POST", {})
    check("未知接口 → 404", st == 404 and js.get("ok") is False, "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST",
                    {"melds": [{"kind": "chi", "tiles": ["W1", "W3", "W4"]}],
                     "concealed": ["W5", "W6", "W7", "W8", "W9", "B1", "B2", "B3",
                                   "B4", "B5", "B9", "B9"], "win": "B9"})
    check("非法吃（不连） → 400", st == 400 and "吃" in js.get("error", ""),
          "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W2", "W3"], "options": {"round_wind": "中"}})
    check("非法风位 → 400", st == 400 and "round_wind" in js.get("error", ""),
          "%s %s" % (st, js))
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W2", "W3"], "options": {"flowers": 99}})
    check("花牌超 8 → 400", st == 400 and "8" in js.get("error", ""), "%s %s" % (st, js))

    # 不算和牌的手牌：应返回 ok=True 且 message 说明
    st, js, _ = req(url + "/api/score", "POST",
                    {"concealed": ["W1", "W3", "W5", "W7", "W9", "T1", "T3", "T5",
                                   "T7", "T9", "B2", "B4", "B6", "B8"], "win": "B8"})
    check("不能和牌时 message 有说明", st == 200 and js.get("ok") is True
          and js.get("message"), "%s %s" % (st, js))

    # ---------------- 口令与 OPTIONS
    log("\n【7】口令 / CORS 预检 / 重启")
    st, js, _ = req(url + "/api/health", "OPTIONS")
    check("OPTIONS 预检 204", st == 204, st)
    srv2 = A.ApiServer("127.0.0.1", 0, token="s3cret")
    url2 = srv2.start()
    st, js, _ = req(url2 + "/api/health")
    check("带口令时无 token → 401", st == 401 and js.get("ok") is False, "%s %s" % (st, js))
    st, js, _ = req(url2 + "/api/health", headers={"X-Api-Token": "s3cret"})
    check("带 token 头 → 200", st == 200 and js.get("ok"), "%s %s" % (st, js))
    st, js, _ = req(url2 + "/api/health?token=s3cret")
    check("?token= 也认", st == 200 and js.get("ok"), "%s %s" % (st, js))
    st, html2, _ = req(url2 + "/")
    check("带口令时首页免口令可访问（Web 客户端）",
          st == 200 and "<!doctype html" in str(html2).lower(), st)
    st, png2, _ = req(url2 + "/tiles/B1.png")
    check("带口令时牌面图免口令可访问", st == 200, st)
    st, js, _ = req(url2 + "/api/tiles")
    check("带口令时数据接口仍拦（无 token）", st == 401, st)
    srv2.stop()
    check("口令服务已停止", not srv2.running)

    # ---------------- 免口令白名单（v2.5.0）
    log("\n【7b】免口令白名单（v2.5.0：设了口令后，分项允许「不用口令也能用」）")
    body106 = {"concealed": ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                             "W7", "W8", "W9", "W9", "W9", "W9"], "win": "W9"}
    body_wait = {"concealed": ["W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6",
                               "W7", "W8", "W9", "W9", "W9"]}
    check("默认 ANON_DEFAULT = web+debug（与 v2.4.x 行为一致）",
          tuple(A.ANON_DEFAULT) == ("web", "debug"), A.ANON_DEFAULT)
    check("不传 anon 时按默认（web+debug）",
          A.ApiServer("127.0.0.1", 0, token="x").anon == tuple(A.ANON_DEFAULT),
          A.ApiServer("127.0.0.1", 0, token="x").anon)
    check("显式 anon=() 则是「全部要口令」",
          A.ApiServer("127.0.0.1", 0, token="x", anon=()).anon == (),
          A.ApiServer("127.0.0.1", 0, token="x", anon=()).anon)
    check("分组表齐全（web/debug/info/score/waits）",
          set(A.ANON_GROUPS) == {"web", "debug", "info", "score", "waits"},
          sorted(A.ANON_GROUPS))
    # ★ 回归："/" 必须当精确项，否则会前缀命中一切路径（v2.5.0 踩过）
    srvZ = A.ApiServer("127.0.0.1", 0, token="tz", anon=("web",))
    urlZ = srvZ.start()
    st, _g, _ = req(urlZ + "/")
    check("anon=web → 首页免口令", st == 200, st)
    st, _g, _ = req(urlZ + "/api/score", "POST", body106)
    check("anon=web 不会误放行 /api/score（“/”不能当前缀）", st == 401, st)
    st, _g, _ = req(urlZ + "/api/health")
    check("anon=web 不会误放行 /api/health", st == 401, st)
    srvZ.stop()

    # (a) 只开 info：查询类免口令，其余一律要口令（含 Web 页面）
    srvA = A.ApiServer("127.0.0.1", 0, token="t1", anon=("info",))
    urlA = srvA.start()
    st, js, _ = req(urlA + "/api/health")
    check("anon=info → /api/health 免口令可用", st == 200 and js.get("ok"),
          "%s %s" % (st, js))
    st, js, _ = req(urlA + "/api/tiles")
    check("anon=info → /api/tiles 免口令可用", st == 200, st)
    st, js, _ = req(urlA + "/api/score", "POST", body106)
    check("anon=info → /api/score 仍然要口令", st == 401, st)
    st, got, _ = req(urlA + "/")
    check("anon 没开 web → 首页也要口令", st == 401, st)
    st, got, _ = req(urlA + "/?token=t1")
    check("关掉 web 后：带 ?token= 仍能打开首页",
          st == 200 and "<!doctype html" in str(got).lower(), st)
    st, got, _ = req(urlA + "/tiles/B1.png")
    check("anon 没开 web → 牌面图要口令", st == 401, st)
    st, got, _ = req(urlA + "/tiles/B1.png?token=t1")
    check("牌面图带 token 可取（200 + PNG）", st == 200 and str(got)[:1] != "{", st)
    st, got, _ = req(urlA + "/debug")
    check("anon 没开 debug → 自测页要口令", st == 401, st)
    srvA.stop()

    # (b) 只开 score+waits：算番/听牌免口令，查询接口要口令
    srvB = A.ApiServer("127.0.0.1", 0, token="t2", anon=("score", "waits"))
    urlB = srvB.start()
    st, js, _ = req(urlB + "/api/score", "POST", body106)
    check("anon=score → POST 算番免口令（106 番）",
          st == 200 and js.get("total") == 106, "%s %s" % (st, js.get("total")))
    st, js, _ = req(urlB + "/api/score?concealed="
                    + ",".join(body106["concealed"]) + "&win=W9")
    check("anon=score → GET 简写也免口令", st == 200 and js.get("total") == 106,
          "%s %s" % (st, js.get("total")))
    st, js, _ = req(urlB + "/api/waits", "POST", body_wait)
    check("anon=waits → 听牌免口令可用", st == 200 and js.get("count") == 9,
          "%s %s" % (st, js.get("count")))
    st, js, _ = req(urlB + "/api/waits_all", "POST", body_wait)
    check("anon=waits → /api/waits_all 也在白名单内", st == 200, st)
    st, js, _ = req(urlB + "/api/health")
    check("anon=score,waits → /api/health 仍要口令", st == 401, st)
    srvB.stop()

    # (c) 一个都不开 / 全部开
    srvC = A.ApiServer("127.0.0.1", 0, token="t3", anon=())
    urlC = srvC.start()
    st, got, _ = req(urlC + "/")
    check("anon=() → 连首页也要口令", st == 401, st)
    st, got, _ = req(urlC + "/?token=t3")
    check("anon=() → 带 token 首页 200", st == 200, st)
    st, js, _ = req(urlC + "/api/health")
    check("anon=() → 接口要口令", st == 401, st)
    srvC.stop()
    srvD = A.ApiServer("127.0.0.1", 0, token="t4", anon=tuple(A.ANON_GROUPS))
    urlD = srvD.start()
    st, got, _ = req(urlD + "/")
    check("anon=全部 → 首页免口令", st == 200, st)
    st, js, _ = req(urlD + "/api/health")
    check("anon=全部 → 查询接口免口令", st == 200, st)
    st, js, _ = req(urlD + "/api/score", "POST", body106)
    check("anon=全部 → 算番免口令", st == 200 and js.get("total") == 106, st)
    st, got, _ = req(urlD + "/debug")
    check("anon=全部 → 自测页免口令", st == 200, st)
    srvD.stop()

    # (d) 没设口令时 anon 不起作用（本来就全放行）
    srvE = A.ApiServer("127.0.0.1", 0, token="", anon=())
    urlE = srvE.start()
    st, js, _ = req(urlE + "/api/health")
    check("没设口令 → anon=() 也免口令（口令为空不校验）", st == 200, st)
    st, got, _ = req(urlE + "/")
    check("没设口令 → 首页免口令", st == 200, st)
    srvE.stop()

    # (e) 不认识的键被忽略，且不会误放行
    srvF = A.ApiServer("127.0.0.1", 0, token="t5", anon=("nope", "info"))
    urlF = srvF.start()
    st, js, _ = req(urlF + "/api/health")
    check("未知分组键不报错，其它组照常生效", st == 200, st)
    st, js, _ = req(urlF + "/api/score", "POST", body106)
    check("未知分组键不会误放行 score", st == 401, st)
    srvF.stop()

    port = srv.port_actual
    srv.stop()
    check("服务已停止", not srv.running)
    srv3 = A.ApiServer("127.0.0.1", port)
    srv3.start()
    st, js, _ = req(srv3.url + "/api/health")
    check("端口可复用（重新启动）", st == 200 and js.get("ok"), st)
    srv3.stop()

    # ---------------- 【7c】客户端「提前断开」不该刷 traceback（v2.7.4）
    #   手机浏览器刷新 / 关标签页 / 切后台时，TCP 会被直接掐掉（RST），标准库会因此
    #   在控制台刷一整屏「Exception occurred during processing of request from (...)」。
    #   那是噪声不是错误 —— 这里真发 RST 验证它已经被静音。
    log("\n【7c】客户端提前断开（手机刷新/关页面）不刷 traceback（v2.7.4）")
    import socket as _socket
    import struct as _struct

    check("有统一的 CLIENT_GONE_ERRORS 常量",
          isinstance(getattr(A, "CLIENT_GONE_ERRORS", None), tuple)
          and ConnectionResetError in A.CLIENT_GONE_ERRORS, "")
    check("Handler 覆盖了 handle_one_request（吞掉断开异常）",
          "handle_one_request" in A.Handler.__dict__, "")
    check("服务用 QuietHTTPServer（handle_error 静音）",
          issubclass(A.QuietHTTPServer, A.ThreadingHTTPServer)
          and "handle_error" in A.QuietHTTPServer.__dict__, "")

    srvQ = A.ApiServer("127.0.0.1", 0)
    srvQ.start()
    noise = io.StringIO()
    real_err, sys.stderr = sys.stderr, noise
    try:
        for _ in range(4):
            sock = _socket.socket()
            # SO_LINGER + 立刻 close ⇒ 直接发 RST，模拟「手机把连接掐掉」
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_LINGER,
                            _struct.pack("ii", 1, 0))
            sock.connect(("127.0.0.1", srvQ.port_actual))
            sock.sendall(b"GET /api/health HTTP/1.1\r\n")     # 只发一半就断
            sock.close()
        time.sleep(0.6)
    finally:
        sys.stderr = real_err
    out = noise.getvalue()
    check("4 次 RST 断开：控制台没有 'Exception occurred'",
          "Exception occurred" not in out, out[:200].replace("\n", " | "))
    check("4 次 RST 断开：控制台没有 traceback / ConnectionResetError",
          "Traceback" not in out and "ConnectionResetError" not in out,
          out[:200].replace("\n", " | "))
    st, js, _ = req(srvQ.url + "/api/health")
    check("断开之后服务照常可用", st == 200 and js.get("ok"), st)
    srvQ.stop()

    # ---------------- 【7d】Web 页面上的两个可选按钮（v2.7.5：默认都不显示）
    log("\n【7d】Web 页面「接口自测页 / 换口令」按钮默认不显示（v2.7.5）")
    check("WEB_SHOW_ITEMS = debug/token 两项",
          [k for k, _, _ in A.WEB_SHOW_ITEMS] == ["debug", "token"], A.WEB_SHOW_ITEMS)
    check("默认值 WEB_SHOW_DEFAULT 为空（都不显示）",
          tuple(A.WEB_SHOW_DEFAULT) == (), A.WEB_SHOW_DEFAULT)

    srvD0 = A.ApiServer("127.0.0.1", 0)
    srvD0.start()
    st, html0, _ = req(srvD0.url + "/")
    check("默认首页 HTTP 200", st == 200, st)
    check("默认：接口自测页按钮被隐藏",
          'id="btn_debug" style="display:none"' in html0, "")
    check("默认：换口令按钮被隐藏",
          'id="btn_token" style="display:none"' in html0, "")
    check("页面里没有残留占位符（__SHOW_/__APP__）",
          "__SHOW_" not in html0 and "__APP__" not in html0, "")
    srvD0.stop()

    srvD1 = A.ApiServer("127.0.0.1", 0, "", show=("debug",))
    srvD1.start()
    st, html1, _ = req(srvD1.url + "/web")
    check("show=debug：自测页按钮显示（style 为空）",
          'id="btn_debug" style=""' in html1, "")
    check("show=debug：换口令仍然隐藏",
          'id="btn_token" style="display:none"' in html1, "")
    srvD1.stop()

    srvD2 = A.ApiServer("127.0.0.1", 0, "", show=("debug", "token"))
    srvD2.start()
    st, html2, _ = req(srvD2.url + "/index.html")
    check("show=debug,token：两个按钮都显示",
          'id="btn_debug" style=""' in html2 and 'id="btn_token" style=""' in html2, "")
    srvD2.stop()

    page = A.render_web_client("X", ("debug", "token"))
    check("render_web_client：应用名与占位符都替换掉",
          "__SHOW_" not in page and "__APP__" not in page and "X · Web 版" in page, "")

    # ---------------- 【7e】客户端「按钮：…」5 档大小（v2.7.6）
    log("\n【7e】客户端「按钮：…」5 档大小（v2.7.6 起；v2.7.7 调档：默认＝最小、只往大）")
    import re as _re
    W = A.WEB_CLIENT
    check("CSS 默认按钮尺寸 = 升级前的 15px / 7px 11px（默认档不动老外观）",
          "--btn-fs:15px" in W and "--btn-pad-y:7px" in W and "--btn-pad-x:11px" in W, "")
    check("button 规则走变量（字号 + 内边距）",
          "font-size:var(--btn-fs)" in W
          and "padding:var(--btn-pad-y) var(--btn-pad-x)" in W, "")
    check("localStorage 键 = mj_btnsize2", 'BTN_KEY="mj_btnsize2"' in W, "")
    blk = W.split("BTN_LEVELS=[", 1)[1].split("];", 1)[0] if "BTN_LEVELS=[" in W else ""
    check("BTN_LEVELS 共 5 档", blk.count("{name:") == 5, blk.count("{name:"))
    lv = [int(x) for x in _re.findall(r"fs:(\d+)", blk)]
    check("5 档字号递增 15/17/19/21/23（只数 BTN_LEVELS 里的）",
          lv == [15, 17, 19, 21, 23], lv)
    pads = _re.findall(r"py:(\d+),\s*px:(\d+)", blk)
    check("5 档内边距 7/11 → 9/14 → 11/17 → 13/20 → 15/23",
          [(int(a), int(b)) for a, b in pads] == [(7, 11), (9, 14), (11, 17), (13, 20), (15, 23)],
          pads)
    check("默认档 = 第 1 档（最小），字号 15 且内边距 7/11（＝现在的大小）",
          "const BTN_DEFAULT=0;" in W and lv and lv[0] == 15
          and (int(pads[0][0]), int(pads[0][1])) == (7, 11), "")
    check("没有比默认更小的档（第一档就是最小）",
          lv == sorted(lv) and all(fs >= 15 for fs in lv), lv)
    check("按钮 #szbtn 加在「布局」按钮之后、点击即切换",
          'id="lybtn"' in W and 'id="szbtn"' in W and 'onclick="cycleBtnSize()"' in W
          and W.index('id="lybtn"') < W.index('id="szbtn"'), "")
    check("cycleBtnSize 在 5 档之间循环", "(BTN_IDX+1)%BTN_LEVELS.length" in W, "")
    check("默认档清掉内联变量（回落 CSS 默认＝与升级前逐像素一致）",
          '["--btn-fs","--btn-pad-y","--btn-pad-x"].forEach'
          '(k=>root.style.removeProperty(k))' in W, "")
    check("启动时恢复上次档位（刷新/切页都记得）",
          "applyBtnSize(loadBtnSize(),false)" in W, "")
    check("loadBtnSize 读 localStorage + 越界回默认档",
          "parseInt(localStorage.getItem(BTN_KEY),10)" in W and "return BTN_DEFAULT;" in W, "")
    check("szbtn 首屏文案与默认档一致（按钮：最小（1/5））", "按钮：最小（1/5）" in W, "")

    log("\n" + "=" * 74)
    log("结果: 通过 %d 项，失败 %d 项" % (PASS, FAIL))
    log("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
