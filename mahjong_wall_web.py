# -*- coding: utf-8 -*-
"""大屏看板的 **Web 版**（v2.9.35 新增）—— 给电视盒子 / 手机 / 平板的浏览器打开。

为什么要有它
------------
桌面版「📺 大屏看板」是个 Qt 窗口，要显示在电视上只能靠投屏（Miracast / DLNA），
而那些协议全在系统与网卡驱动层，应用层没有 API 可调，程序里加不了。
更省事的办法是：电视盒子用自带浏览器打开一个网址就行 —— 本项目本来就有
HTTP 服务（默认 8080），加一个 `/wall` 页面即可，不用投屏、不用装 App。

三台当贝盒子的系统版本都够用（`-webkit-text-stroke` 需要 Chromium 49+）：
    B1  Android 6/7   Amlogic S905X
    B3  Android 9     Amlogic S922X
    H5  Android 12    全志 H618

与桌面版的关系（**这是本文件最重要的约定**）
--------------------------------------------
1. 配色、分档、IP 显示名、撞名回退、自动描边色 —— **全部复用 `mahjong_wall_core`**，
   一个字都不在这里重写。重写就会两头不一致，那是本项目已经踩过多次的坑
   （例如 v2.9.31 修过的「上半显示 210、下半显示 192.168.1.210」）。
2. 唯一不同的是**描边怎么画**：桌面版用 QPainterPath.strokePath 自绘，
   网页版用 CSS `-webkit-text-stroke`。QSS 没有 text-stroke 是本项目的老限制，
   但浏览器里是有的 —— 这也正是网页版能做到「和桌面一模一样」的原因。
3. 本文件**不许 import PySide6**（除了间接通过 core，见下），因为 HTTP 服务
   跑在主进程里但可能在没有 QApplication 的场景被导入。
   `mahjong_wall_core` 顶部虽然 import 了 QtGui，但模块级只创建 QColor（值类型，
   不需要 QApplication），实测可直接 import；`pick_font_family()` 之类需要
   QGuiApplication 的函数这里一律不调用。
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------- 复用 core
# 配色 / 分档 / 标签 / 时间格式化全部来自这里，保证与桌面大屏逐字一致。
try:
    from mahjong_wall_core import (  # noqa: F401
        SCORE_MODE_RANK,
        STROKE_DEFAULT,
        UNKNOWN_IP_TEXT,
        assign_colors,
        auto_stroke_for_fill,
        build_labels,
        contrast_on_black,
        day_text,
        fmt_ts,
        group_by_ip,
        normalize_config,
        resolve_steps,
        stroke_setting,
    )
    CORE_IMPORT_ERROR: Optional[str] = None
except Exception as _exc:            # noqa: BLE001
    CORE_IMPORT_ERROR = repr(_exc)
    SCORE_MODE_RANK = "rank"         # type: ignore[assignment]
    STROKE_DEFAULT = 0.08            # type: ignore[assignment]
    UNKNOWN_IP_TEXT = "(未记录IP)"    # type: ignore[assignment]

    def normalize_config(cfg):       # type: ignore[misc]
        return dict(cfg or {})

    def resolve_steps(pid, cfg=None):    # type: ignore[misc]
        return ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8")

    def assign_colors(values, steps=None, mode=SCORE_MODE_RANK):  # type: ignore[misc]
        seq = tuple(steps or ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8"))
        return [seq[-1] for _ in values]

    def group_by_ip(rows, hide_unknown=False, only_ips=None):  # type: ignore[misc]
        bag: Dict[str, Dict] = {}
        only = set(only_ips or [])
        for r in rows:
            ip = str(r.get("ip") or "").strip()
            if hide_unknown and not ip:
                continue
            if only and ip not in only:
                continue
            b = bag.setdefault(ip, {"ip": ip, "cnt": 0, "fan": 0, "last_ts": 0})
            b["cnt"] += 1
            try:
                b["fan"] += int(r.get("total_fan") or 0)
            except Exception:        # noqa: BLE001
                pass
        return sorted(bag.values(), key=lambda x: (-x["fan"], -x["cnt"], x["ip"]))

    def build_labels(ips, names=None, mode="last"):  # type: ignore[misc]
        return ([str(ip or UNKNOWN_IP_TEXT) for ip in ips], [])

    def fmt_ts(ts_ms, pattern="%H:%M:%S"):  # type: ignore[misc]
        try:
            return time.strftime(pattern, time.localtime(int(ts_ms) / 1000.0))
        except Exception:            # noqa: BLE001
            return ""

    def day_text(day):               # type: ignore[misc]
        d = str(day or "").strip()
        return d or "全部日期"

    def stroke_setting(cfg):         # type: ignore[misc]
        return "#FFFFFF"

    def auto_stroke_for_fill(fill):  # type: ignore[misc]
        return "#FFFFFF"

    def contrast_on_black(color):    # type: ignore[misc]
        return 0.0


# ---------------------------------------------------------------- 常量
WALL_ROUTE = "/wall"
WALL_API_ROUTE = "/api/wall"

BG = "#000000"
TITLE_COLOR = "#35E1FF"
HEAD_COLOR = "#7FE9FF"
MUTED = "#8FA3B5"
DEFAULT_STEPS = ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8")

# 一屏最多取多少条原始记录（与桌面版一致：2000 条足够覆盖一天几百手）
MAX_ROWS = 2000


# ---------------------------------------------------------------- 数据
def build_payload(stats, day: str, cfg: Optional[Dict]) -> Dict:
    """算出页面要画的全部内容（**服务端口径 = 桌面端口径**）

    返回结构（JSON 可直接序列化）::

        {
          "ok": True, "day": "2026-11-24", "title": "2026-11-24  今日战绩",
          "sub": "共 105 手 · 5071 番 · 3 个 IP", "msg": "",
          "up_headers": ["IP", "次数", "总分"],
          "low_headers": ["IP", "时间", "分"],
          "people": [{"label": "100", "cnt": 7, "fan": 239, "color": "#E8F0F8"}],
          "recs":   [{"label": "100", "time": "20:00:05", "fan": 257, "color": "#FFD54A"}],
          "step0": "#FFD54A",
          "highlight_first": True,
          "stroke_width": 0.08,
          "stroke_mode": "#FFFFFF",
          "people_note": ""
        }

    `stroke_mode` 是**设置原值**：`"auto"` 或 `#RRGGBB`。
    选 auto 时每一格的颜色由 `stroke_color` 逐格给出（见 _cell），
    因为实测「整屏共用一个描边色」必然有某一档与字色撞色、等于没描。
    """
    cfg = normalize_config(cfg)
    out: Dict = {
        "ok": True, "day": str(day or ""), "title": "", "sub": "", "msg": "",
        "up_headers": [], "low_headers": [],
        "people": [], "recs": [], "step0": DEFAULT_STEPS[0],
        "highlight_first": bool(cfg.get("wall_highlight_first", True)),
        "stroke_width": STROKE_DEFAULT,
        "stroke_mode": "#FFFFFF",
        "people_note": "",
    }
    if CORE_IMPORT_ERROR:
        out["ok"] = False
        out["msg"] = "看板模块导入失败：%s" % CORE_IMPORT_ERROR
        return out
    if stats is None:
        out["ok"] = False
        out["msg"] = "统计库不可用"
        return out

    steps = resolve_steps(cfg.get("wall_palette"), cfg)
    out["step0"] = steps[0] if steps else DEFAULT_STEPS[0]
    try:
        out["stroke_width"] = float(cfg.get("wall_stroke", STROKE_DEFAULT))
    except Exception:                # noqa: BLE001
        out["stroke_width"] = STROKE_DEFAULT
    out["stroke_mode"] = stroke_setting(cfg)

    # ---- 取原始行（与桌面版 WallBoardDialog.reload 完全同一条查询）
    rows: List[Dict] = []
    try:
        rows = stats.recent_rows(str(day or "") or None, None, MAX_ROWS) or []
    except Exception as exc:         # noqa: BLE001
        out["ok"] = False
        out["msg"] = "读取统计失败：%r" % (exc,)
        return out

    # ---- 上半：按 IP 汇总
    people = group_by_ip(rows, bool(cfg.get("wall_hide_unknown")), cfg.get("wall_ips"))
    ips = [p["ip"] for p in people]
    labels, notes = build_labels(ips, cfg.get("wall_names"),
                                 cfg.get("wall_label_mode", "last"))
    for p, lab in zip(people, labels):
        p["label"] = lab
    out["people_note"] = "；".join(notes or [])

    # ---- 下半：最近 N 手（rows 本来就是时间倒序）
    # ★ 显示名必须复用上半算好的映射，否则撞名检测样本范围不同会导致
    #   同一台机器上半显示 "210"、下半显示 "192.168.1.210"（v2.9.31 修过）
    name_of = dict(zip(ips, labels))
    try:
        n = max(1, int(cfg.get("wall_recent_n") or 10))
    except Exception:                # noqa: BLE001
        n = 10
    recs = rows[:n]

    mode = str(cfg.get("wall_score_mode") or SCORE_MODE_RANK)
    p_colors = assign_colors([p["fan"] for p in people], steps, mode)
    r_colors = assign_colors([int(r.get("total_fan") or 0) for r in recs], steps, mode)

    out["people"] = [{"label": str(p["label"]), "cnt": int(p["cnt"]),
                      "fan": int(p["fan"]), "color": p_colors[i]}
                     for i, p in enumerate(people)]
    out["recs"] = [{"label": (name_of.get(str(r.get("ip") or "").strip())
                              or str(r.get("ip") or "").strip()
                              or UNKNOWN_IP_TEXT),
                    "time": fmt_ts(r.get("ts_ms") or 0),
                    "fan": int(r.get("total_fan") or 0),
                    "color": r_colors[i]}
                   for i, r in enumerate(recs)]

    # ---- 表头 / 标题
    out["up_headers"] = (["IP", "次数", "总分"] if cfg.get("wall_show_cnt")
                         else ["IP", "", "总分"])
    out["low_headers"] = ["IP", "时间", "分"]

    d = day_text(day)
    _day = str(day or "").strip()
    is_today = bool(_day) and _day == time.strftime("%Y-%m-%d")
    out["title"] = ("%s  今日战绩" % d) if is_today else ("%s  战绩" % d)
    total_hands = sum(p["cnt"] for p in out["people"])
    total_fan = sum(p["fan"] for p in out["people"])
    out["sub"] = ("共 %d 手 · %d 番 · %d 个 IP"
                  % (total_hands, total_fan, len(out["people"]))) if total_hands else ""
    return out


def cell_stroke(fill: str, mode: str) -> str:
    """某一格该用哪个描边色（`auto` 时就按这一格自己的字色现算）"""
    if str(mode or "").strip().lower() == "auto":
        return auto_stroke_for_fill(fill)
    return str(mode or "#FFFFFF")


# ---------------------------------------------------------------- 页面
WALL_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#000000">
<title>__APP__ · 大屏看板</title>
<style>
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;height:100%;background:#000;color:#fff;overflow:hidden;
    font-family:"HarmonyOS Sans SC","Noto Sans SC","Source Han Sans SC","DengXian",sans-serif;
    -webkit-font-smoothing:antialiased}
  #wrap{height:100%;display:flex;flex-direction:column;
    padding:2.2vh 3.4vw;box-sizing:border-box}
  /* 描边：宽度用 em（= 桌面版的「字号 × 系数」，跟着各自字号自动缩放），
     颜色逐格 inline 给 —— 选「自动」时每一格按自己的字色算，所以颜色不统一是正常的 */
  #title,#sub,.c{-webkit-text-stroke-width:__SW__em;
    -webkit-text-stroke-color:#fff;paint-order:stroke fill;
    -webkit-paint-order:stroke fill}
  #title{text-align:center;font-size:4.3vh;font-weight:700;letter-spacing:.05em;
    line-height:1.15;white-space:nowrap}
  #sub{text-align:center;font-size:1.85vh;color:#8FA3B5;margin-top:.5vh;
    line-height:1.2;white-space:nowrap}
  #body{flex:1 1 0;display:flex;flex-direction:column;margin-top:1.1vh;min-height:0;
    overflow:hidden;--cols:42% 24% 34%}
  /* ★ flex-basis 必须是 0！只写 flex-grow:1 时基准尺寸取「内容高度」，
     行一多就顶出容器（实测：上半第 3 行被分隔线切掉、下半末行被裁） */
  .sec{display:flex;flex-direction:column;flex:1 1 0;min-height:0;overflow:hidden}
  /* ★ 表头和行**都要** grid-template-columns：只给表头设，行会退化成单列网格，
     三个格子竖着堆成一列（实测踩过：数字跑到标签下面，行高翻倍被裁） */
  .hdr{display:grid;grid-template-columns:var(--cols);color:#7FE9FF;
    font-size:1.95vh;font-weight:700;
    padding-bottom:.35vh;border-bottom:2px solid #35E1FF;flex:none}
  .rows{flex:1 1 0;min-height:0;display:flex;flex-direction:column;overflow:hidden}
  /* 行高靠 flex 均分；字号由 JS 按「行高 × 0.62」现算并写进 --fs，
     否则固定 vh 字号在行多/窗口矮时会顶出格子（实测踩过：末行被裁） */
  .row{display:grid;grid-template-columns:var(--cols);align-items:center;
    flex:1 1 0;min-height:0;position:relative;
    border-bottom:1px solid rgba(255,255,255,.09)}
  .row:last-child{border-bottom:none}
  .c{font-size:var(--fs,3.1vh);font-weight:600;line-height:1.05;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis;padding:0 .3vw;z-index:1}
  .r{text-align:right}.m{text-align:center}.l{text-align:left}
  /* 榜首整行反色高亮：底色铺满、文字改黑（与桌面版 _paint_section 同语义）
     ★ 不要再加左右 padding —— 那会缩小内容盒，让榜首那行的三列和表头对不齐 */
  .row.hl{border-radius:.5vh}
  .empty{flex:1;display:flex;align-items:center;justify-content:center;
    color:#8FA3B5;font-size:1.9vh}
  #div{flex:none;height:3px;background:linear-gradient(
    to bottom,rgba(255,255,255,.30) 0,rgba(255,255,255,.30) 1px,
    transparent 1px,transparent 2px,rgba(255,255,255,.30) 2px,
    rgba(255,255,255,.30) 3px)}
  #foot{flex:none;text-align:center;font-size:1.35vh;color:#5A6B7A;
    padding-top:.6vh;letter-spacing:.04em}
  #err{position:fixed;left:0;right:0;bottom:0;background:#3a1414;color:#FFB4B4;
    font-size:1.5vh;padding:.6vh 1vw;display:none}
</style></head>
<body><div id="wrap">
  <div id="title">加载中…</div>
  <div id="sub"></div>
  <div id="body">
    <div class="sec" id="sup">
      <div class="hdr" id="hup"></div>
      <div class="rows" id="rup"><div class="empty">今日暂无记录</div></div>
    </div>
    <div id="div"></div>
    <div class="sec" id="slow">
      <div class="hdr" id="hlow"></div>
      <div class="rows" id="rlow"><div class="empty">今日暂无算番记录</div></div>
    </div>
  </div>
  <div id="foot"></div>
</div>
<div id="err"></div>
<script>
"use strict";
var COLS = "42% 24% 34%";
var COLW = [0.42, 0.24, 0.34];
var $ = function(id){ return document.getElementById(id); };
var lastOK = 0;
var lastData = null;
var _mc = null;

/* 量一段文字在指定字号下有多宽（用离屏 canvas，跟浏览器实际排版同字体）。
   ★ 只按行高算字号是不够的：手机竖屏时"08:10:56"会宽过格子被截成"08:1…" */
function textW(txt, fs){
  if(!_mc){ _mc = document.createElement("canvas").getContext("2d"); }
  _mc.font = "600 " + fs + 'px "HarmonyOS Sans SC","Noto Sans SC",' +
             '"Source Han Sans SC","DengXian",sans-serif';
  return _mc.measureText(String(txt == null ? "" : txt)).width;
}

function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(ch){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
  });
}
/* 一格：颜色 + 描边色（auto 时后端已经按这一格的字色算好） */
function cell(text, color, strokeColor, align){
  return '<div class="c ' + align + '" style="color:' + color +
         ';-webkit-text-stroke-color:' + strokeColor + '">' + esc(text) + '</div>';
}
/* 行高均分后，按「行高 × 0.62」定字号 —— 桌面版 _paint_section 就是这个比例。
   固定 vh 字号在行多/窗口矮时会把字顶出格子（实测：末行被裁掉一半）。 */
/* 行高均分后按「行高 × 0.62」定字号（桌面版 _paint_section 就是这个比例），
   再按「最宽那格文字不能超列宽 92%」往下压 —— 两者取小。
   ★ 只按行高算是不够的：手机竖屏时时间列会宽过格子被截成 "08:1…"（实测踩过） */
function fitRows(el, n){
  if(!n || !el) return;
  var h = el.clientHeight;
  if(!h) return;
  var fs = Math.max(9, Math.floor((h / n) * 0.62));
  var rows = el.children;
  if(rows && rows.length){
    /* 每列取「全表最长的那段文字」来试宽，只看第一行会漏掉 4 位数分数 */
    for(var c = 0; c < COLW.length; c++){
      var limit = el.clientWidth * COLW[c] * 0.92;
      var widest = "";
      for(var r = 0; r < rows.length; r++){
        var t = (rows[r].children[c] || {}).textContent || "";
        if(t.length > widest.length) widest = t;
      }
      if(!widest || textW(widest, fs) <= limit) continue;
      var lo = 9, hi = fs;
      for(var k = 0; k < 8; k++){
        var mid = (lo + hi) / 2;
        if(textW(widest, mid) > limit){ hi = mid; } else { lo = mid; }
      }
      fs = Math.max(9, Math.floor(lo));
    }
  }
  el.style.setProperty("--fs", fs + "px");
}
function buildSection(hdrEl, rowsEl, headers, items, emptyText,
                      scoreFirst, hlFirst, hlColor){
  var h = "";
  for(var i = 0; i < headers.length; i++){ h += "<div>" + esc(headers[i]) + "</div>"; }
  hdrEl.innerHTML = h;
  hdrEl.style.gridTemplateColumns = COLS;
  if(!items.length){
    rowsEl.innerHTML = '<div class="empty">' + esc(emptyText) + "</div>";
    return;
  }
  var out = "";
  for(var r = 0; r < items.length; r++){
    var it = items[r];
    var hl = hlFirst && r === 0 && hlColor;
    var cls = "row" + (hl ? " hl" : "");
    var style = hl ? (' style="background:' + hlColor + '"') : "";
    var fg = hl ? "#000000" : null;
    var st = hl ? hlColor : null;
    out += '<div class="' + cls + '"' + style + ">";
    // 第一列：标签
    out += cell(it.label, fg || it.colorL, st || it.strokeL, "l");
    // 第二列
    if(it.mid !== undefined){
      out += cell(it.mid, fg || it.colorM, st || it.strokeM, "m");
    }
    // 分数列
    out += cell(it.score, fg || it.color, st || it.strokeS, "r");
    out += "</div>";
  }
  rowsEl.innerHTML = out;
  fitRows(rowsEl, items.length);
}

function render(d){
  lastData = d;
  if(d.msg){ $("err").style.display = "block"; $("err").textContent = d.msg; }
  else { $("err").style.display = "none"; }
  $("title").textContent = d.title || "";
  $("title").style.webkitTextStrokeColor = d.titleStroke || "#FFFFFF";
  $("sub").textContent = d.sub || "";
  $("sub").style.webkitTextStrokeColor = d.subStroke || "#FFFFFF";
  var people = [], recs = [];
  for(var i = 0; i < (d.people || []).length; i++){
    var p = d.people[i];
    people.push({label: p.label,
                 mid: d.showCnt ? String(p.mid == null ? "" : p.mid) : "",
                 score: p.score, color: p.color,
                 strokeL: p.strokeL, strokeM: p.strokeM, strokeS: p.strokeS,
                 colorL: p.colorL, colorM: p.colorM});
  }
  for(var j = 0; j < (d.recs || []).length; j++){
    var r = d.recs[j];
    recs.push({label: r.label, mid: r.mid, score: r.score, color: r.color,
               strokeL: r.strokeL, strokeM: r.strokeM, strokeS: r.strokeS,
               colorL: r.colorL, colorM: r.colorM});
  }
  buildSection($("hup"), $("rup"), d.upHeaders || [], people,
               "今日暂无记录", true, d.highlightFirst, d.step0);
  buildSection($("hlow"), $("rlow"), d.lowHeaders || [], recs,
               "今日暂无算番记录", false, false, null);
  // 上下分区高度按行数加权（与桌面版 up_units / low_units 同口径）
  var uu = people.length + 1.3, lu = recs.length + 1.3, tot = uu + lu;
  var f = tot ? uu / tot : 0.5;
  f = Math.min(0.72, Math.max(0.28, f));
  $("sup").style.flexGrow = String(f);
  $("slow").style.flexGrow = String(1 - f);
}

function load(){
  var q = location.search || "";
  fetch("__API__" + q, {cache: "no-store"})
    .then(function(r){ return r.json(); })
    .then(function(d){
      render(d);
      lastOK = Date.now();
      var t = new Date();
      $("foot").textContent = "刷新于 " + t.toLocaleTimeString("zh-CN", {hour12: false}) +
        (d.day ? ("　·　" + d.day) : "");
    })
    .catch(function(e){
      $("err").style.display = "block";
      $("err").textContent = "取数据失败（" + e + "）" +
        (lastOK ? ("，最后一次成功 " + new Date(lastOK).toLocaleTimeString("zh-CN",{hour12:false})) : "");
      var t = new Date();
      $("foot").textContent = "刷新于 " + t.toLocaleTimeString("zh-CN", {hour12:false});
    });
}
load();
setInterval(load, __MS__);
/* 窗口尺寸变了要重新算字号，否则盒子横竖屏切换后字号还是旧的 */
var rz = 0;
window.addEventListener("resize", function(){
  clearTimeout(rz);
  rz = setTimeout(function(){ if(lastData) render(lastData); }, 120);
});
/* 键鼠/遥控器：F11 或双击切全屏，方便盒子浏览器隐藏地址栏 */
document.addEventListener("keydown", function(e){
  if(e.key === "F11"){ e.preventDefault(); toggleFS(); }
});
document.addEventListener("dblclick", function(){ toggleFS(); });
function toggleFS(){
  var el = document.documentElement;
  if(!document.fullscreenElement){
    if(el.requestFullscreen) el.requestFullscreen();
  } else if(document.exitFullscreen){ document.exitFullscreen(); }
}
</script></body></html>
"""


def render_wall_page(app_name: str = "国标算番器", refresh_ms: int = 2000) -> str:
    """生成 /wall 页面（纯静态 HTML；数据由 /api/wall 每 2 秒拉一次）"""
    html = WALL_HTML
    html = html.replace("__APP__", str(app_name or "国标算番器"))
    html = html.replace("__API__", WALL_API_ROUTE)
    html = html.replace("__MS__", str(max(500, int(refresh_ms or 2000))))
    html = html.replace("__SW__", "%.3f" % float(STROKE_DEFAULT))
    return html


def render_wall_payload(stats, day: str, cfg: Optional[Dict],
                        app_name: str = "国标算番器") -> Dict:
    """`/api/wall` 的返回：在 build_payload 基础上补上前端要的驼峰键 + 逐格描边色

    ★ 注意：`build_payload()` **只跑一次**。早先写成跑两次（一次取 people、
      一次取整包）纯粹是浪费 —— 每次请求都要多查一遍库、多算两遍分档色。
    """
    p = build_payload(stats, day, cfg)
    mode = p.get("stroke_mode") or "#FFFFFF"
    sw = p.get("stroke_width", STROKE_DEFAULT)

    steps = resolve_steps(cfg.get("wall_palette"), cfg)
    low_text = steps[-1] if steps else DEFAULT_STEPS[-1]

    def _deco(items: List[Dict], with_time: bool) -> List[Dict]:
        """把一行补成前端能直接渲染的样子（含三列各自的描边色）

        ★ 两区的「非分数列」颜色规则**本来就不一样**，这里必须照抄桌面版
          `_paint_section` 的取色分支，否则网页和桌面一眼能看出差别：
            上半（传了 fills）：标签 MUTED、中列 HEAD_COLOR
            下半（fills=None）：标签与中列都落到 `palette[-1]`（近白）
        """
        out: List[Dict] = []
        for it in items:
            color = it.get("color") or DEFAULT_STEPS[-1]
            lbl = MUTED if not with_time else low_text
            mid = HEAD_COLOR if not with_time else low_text
            row: Dict = {
                "label": it.get("label", ""),
                "score": it.get("fan", 0),
                "color": color,
                # 非分数列的字色（两区规则不同，见上面的 docstring）
                "colorL": lbl,
                "colorM": mid,
                # 选「自动」时每列按自己的字色现算，所以三列描边色不同 —— 这是对的
                "strokeL": cell_stroke(lbl, mode),
                "strokeM": cell_stroke(mid, mode),
                "strokeS": cell_stroke(color, mode),
            }
            row["mid"] = it.get("time", "") if with_time else it.get("cnt", 0)
            out.append(row)
        return out

    up_headers = p.get("up_headers") or []
    return {
        "ok": p.get("ok", True),
        "day": p.get("day", ""),
        "title": p.get("title", ""),
        "sub": p.get("sub", ""),
        "msg": p.get("msg", ""),
        "app": str(app_name or ""),
        "upHeaders": up_headers,
        "lowHeaders": p.get("low_headers") or [],
        # 次数列是否显示：桌面版把中间表头写成 "" 表示隐藏，这里照同样的判据
        "showCnt": len(up_headers) == 3 and bool(up_headers[1]),
        "people": _deco(p.get("people") or [], False),
        "recs": _deco(p.get("recs") or [], True),
        "step0": p.get("step0", DEFAULT_STEPS[0]),
        "highlightFirst": bool(p.get("highlight_first", True)),
        "strokeMode": mode,
        "strokeWidth": sw,
        # 标题用 TITLE_COLOR、副标题用 MUTED，各自的描边色也要按同一规则算
        "titleStroke": cell_stroke(TITLE_COLOR, mode),
        "subStroke": cell_stroke(MUTED, mode),
        "note": p.get("people_note", ""),
    }
