# -*- coding: utf-8 -*-
"""统计页「大屏看板」—— 当天每个 IP 的总分 / 次数 + 最近几手的分数。

为什么单独一个模块，不塞进主程序
    主程序 Mahjong_Calculator.py 已经 5000+ 行（项目规矩：单文件不超过 1000 行）。
    看板是**纯自绘**（QPainterPath 描边 + 分数色阶），跟主界面的控件逻辑几乎不相干，
    拆出来既好维护，也方便 `_scaffold/` 里单独离屏渲染做视觉回归。

为什么必须自绘，不能用 QTableWidget
    ① 用户要求「字体白色描边」；Qt 样式表（QSS）没有 text-stroke 这类属性，
       QTableWidgetItem 里的文字**无法描边**。要描边只能用
       QPainterPath.addText() 取字形轮廓 → strokePath() 描白边 → fillPath() 填色。
    ② 行数是「当天有几个 IP 就几行」动态变化的，字号还得跟着窗口高度自动缩放，
       控件方案在这些地方都很别扭。

版面（照用户那块手写板）
    ┌────────────────────────────────────┐
    │        标题（日期 + 今日战绩）       │
    │  IP（或末位段） │  次数  │   总分    │  ← 表头：亮青细下划线，不画竖线
    │     100        │    3   │    501   │  ← 每IP一行，分数按高低给不同亮色
    │     212        │    2   │    794   │
    │ ══════════════════════════════════ │  ← 双线分区
    │  IP           │  时间    │    分    │
    │     210       │ 20:00:05 │    257   │  ← 最近 N 手，时间倒序
    └────────────────────────────────────┘

不画网格线的理由
    · 竖线在 4~8 米外看会变成一片竖条纹，反而压住数字
    · 用户自己的手写板就是只有横线、没有竖线
    · 但对齐必须保留（不然没法快速比大小）：IP 左对齐 / 次数居中 / 总分右对齐，
      三列按比例分配，分数右对齐天然让个位对齐
    · 行间分隔可选、默认极淡（12% 白），设置里能一键关掉

数据口径（与统计页逐字一致，不另算一套）
    · 上半「次数 / 总分」= 当天该 IP 全部记录 COUNT(*) 与 SUM(total_fan)
      （用户已确认：算全部手，不是只算达标的手）
    · 下半「最近 N 手」= 当天全部记录里按 ts_ms 倒序取前 N 条
    · 全部数据来自 StatsDB.recent_rows(day, None, ...) 一次查询，
      按 ip 在 Python 里分组（一天最多几百手，比再写一条 GROUP BY SQL 更好核对口径）

★ 与主程序的数据契约：本模块只依赖 StatsDB 的两个方法
      recent_rows(day, client_type, limit) -> List[dict]   # 已按 ts_ms DESC 排序
      signal() -> (max_id, count)                          # 用来判断「真的变了没」
  两个方法签名变了要同步改这里（以及 _scaffold/_wall_board_probe.py）。

★ 拆成两个文件（都不超 1000 行）
    mahjong_wall_core.py  纯逻辑：设置键 / 视觉常量 / 标签生成 / 描边与绘制基元
    本文件                 三个窗口类：画布 WallBoardWidget / 上墙设置 / 看板窗口
    为了调用方一行都不用改，本文件把 core 里的公共符号**全部原样 re-export**，
    所以 `from mahjong_wall import default_config, SETTING_KEYS, ...` 依然有效。
"""
import time
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QFontMetricsF,
                           QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

# ---- 底层逻辑全部从 core 进来，并在本模块原样可见（re-export）----
# ★ 这里的名字必须与 core 里的定义一一对应：漏一个，本文件的类在运行时就会
#   NameError（2026-11-24 踩过一次同类坑：mahjong_wall.py 漏导入 QPixmap）。
from mahjong_wall_core import (  # noqa: F401
    BG,
    DEFAULT_GEO_SIZE,
    DEFAULT_STEPS,
    FONT_CANDIDATES,
    HEAD_COLOR,
    LABEL_MODE_ITEMS,
    LINE_COLOR,
    MIN_GEO_SIZE,
    MUTED,
    ROW_LINE_COLOR,
    SCORE_MODE_RANK,
    SCORE_STEPS,
    SETTING_KEYS,
    STROKE,
    STROKE_COLOR_DEFAULT,
    STROKE_DEFAULT,
    TITLE_COLOR,
    UNKNOWN_IP_TEXT,
    _FONT_CACHE,
    _GLYPH_CACHE,
    _GLYPH_CACHE_MAX,
    _get_glyph,
    _hline,
    _render_glyph,
    _stroke_width,
    assign_colors,
    build_labels,
    clear_glyph_cache,
    contrast_on_black,
    day_text,
    default_config,
    draw_outlined,
    fmt_ts,
    group_by_ip,
    ip_label,
    make_font,
    normalize_config,
    normalize_geo,
    pick_font_family,
    resolve_palette_name,
    resolve_steps,
    resolve_stroke_color,
    score_color,
    stroke_setting,
)
# ★ v2.9.32：四页标签的设置窗口已拆到 mahjong_wall_config.py。
#   这里必须是顶层真导入，不能用模块级 __getattr__ 延迟导入 ——
#   `open_config()` 里写的是函数内全局名，走 LOAD_GLOBAL，
#   不会触发模块的 __getattr__，会直接 NameError。
#   不会循环：config 只 import core，不回头 import 本文件。
from mahjong_wall_config import (  # noqa: F401
    PAGE_KEYS,
    PAGE_TITLES,
    StylePreview,
    WallConfigDialog,
)

# ---------------------------------------------------------------- 看板画布
class WallBoardWidget(QWidget):
    """大屏看板画布（纯自绘）。数据由外部 set_data() 灌进来，本身不碰数据库。"""

    def __init__(self, cfg: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self.cfg = normalize_config(cfg)
        self.day = ""
        self.rows: List[Dict] = []          # 原始记录（ts_ms 倒序）
        self.msg = ""                       # 库不可用 / 读失败时的说明
        self._font_family = pick_font_family()
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    # -------------------------------------------------- 外部灌数据
    def set_config(self, cfg: Optional[Dict]) -> None:
        self.cfg = normalize_config(cfg)
        self.update()

    def set_data(self, day: str, rows: List[Dict], msg: str = "") -> None:
        self.day = str(day or "")
        self.rows = list(rows or [])
        self.msg = str(msg or "")
        self.update()

    # -------------------------------------------------- 取「上半 / 下半」两批行
    def compute(self) -> Tuple[List[Dict], List[Dict], List[str]]:
        """算出要画的两批行 + 撞名说明

        上半：按 IP 汇总，label 已经在 prepare() 里算好放在 'label' 键
        下半：最近 N 手（rows 本来就是 ts_ms DESC，直接切前 N 条）
        """
        cfg = self.cfg
        people = group_by_ip(self.rows, cfg["wall_hide_unknown"], cfg["wall_ips"])
        ips = [p["ip"] for p in people]
        labels, notes = build_labels(ips, cfg["wall_names"], cfg["wall_label_mode"])
        for p, lab in zip(people, labels):
            p["label"] = lab

        # ★ 关键：上下半的显示名必须用**同一份 ips 列表**来算。
        #   原来下半只拿「最近 N 条里的 ip」去 build_labels，
        #   撞名检测的样本范围不同 → 同一台机器上半显示 "210"、下半显示
        #   "192.168.1.210"，图上直接对不上（已实测复现）。
        #   现在复用上半算好的映射，保证一台上机器全屏只有一个名字。
        name_of = dict(zip(ips, labels))
        n = int(cfg["wall_recent_n"])
        recs = self.rows[:max(1, n)]
        out = []
        for r in recs:
            ip = str(r.get("ip") or "").strip()
            d = dict(r)
            d["label"] = name_of.get(ip) or ip or UNKNOWN_IP_TEXT
            out.append(d)
        return people, out, notes

    # -------------------------------------------------- 画
    def paintEvent(self, event):        # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor(BG))
        try:
            self._paint_all(painter)
        except Exception:       # noqa: BLE001
            # 画板绝不允许把程序带崩：出错就把原因写在屏上，方便现场排查
            import traceback
            painter.setPen(QPen(QColor("#FF8A8A")))
            painter.drawText(self.rect().adjusted(20, 20, -20, -20),
                             Qt.AlignLeft | Qt.TextWordWrap,
                             "看板绘制出错：\n" + traceback.format_exc()[-900:])
        finally:
            painter.end()

    def _paint_all(self, painter: QPainter) -> None:
        w, h = float(self.width()), float(self.height())
        if w < 80 or h < 80:
            return
        people, recs, _notes = self.compute()
        cfg = self.cfg
        # 配色与描边：每帧解析一次就够了（resolve_steps 走 dict 查找，成本可忽略），
        # 这样用户在设置窗口里改配色/改粗细，下一帧立刻变，不需要重启看板。
        steps = resolve_steps(cfg.get("wall_palette"), cfg)
        ratio = float(cfg.get("wall_stroke", STROKE_DEFAULT))
        # 描边色：默认白色；选「自动」时这里拿到的是 `"auto"` 标记，
        # 真正的颜色由 draw_outlined 在绘制每一笔时按**该笔自己的字色**现算
        # （auto_stroke_for_fill）。不能在这里算成一个固定色 —— 实测整屏
        # 共用一个描边色，必然有某一档字与描边撞色、等于没描。
        stroke = stroke_setting(cfg)
        # 外边距按窗口比例走 —— 小窗口 / 大屏都不溢出
        mx = max(10.0, w * 0.035)
        my = max(8.0, h * 0.022)
        inner = QRectF(mx, my, w - 2 * mx, h - 2 * my)

        # ---- 标题行（+ 一行小字副标题：共几手 / 几番 / 几个 IP）
        title_h = max(22.0, inner.height() * 0.082)
        title_rect = QRectF(inner.left(), inner.top(), inner.width(), title_h)
        head_text, sub_text = self._title_texts(people, recs)
        draw_outlined(painter, head_text, title_rect,
                      make_font(self._font_family, title_h * 0.62, True),
                      TITLE_COLOR, "center", ratio=ratio, stroke=stroke)

        sub_h = max(0.0, min(title_h * 0.46, inner.height() * 0.05)) if sub_text else 0.0
        if sub_h >= 9.0:
            draw_outlined(painter, sub_text,
                          QRectF(inner.left(), title_rect.bottom(),
                                 inner.width(), sub_h),
                          make_font(self._font_family, sub_h * 0.78), MUTED, "center",
                          ratio=ratio, stroke=stroke)

        body = QRectF(inner.left(), title_rect.bottom() + sub_h,
                      inner.width(), inner.bottom() - title_rect.bottom() - sub_h)
        if body.height() < 40:
            return

        # ---- 上下分区比例：按各自行数加权，并夹在 28% ~ 72% 之间
        up_units = len(people) + 1.3
        low_units = len(recs) + 1.3
        total_units = up_units + low_units
        up_frac = (up_units / total_units) if total_units else 0.5
        up_frac = min(0.72, max(0.28, up_frac))
        split_y = body.top() + body.height() * up_frac

        up_rect = QRectF(body.left(), body.top(), body.width(),
                         split_y - body.top())
        low_rect = QRectF(body.left(), split_y, body.width(),
                          body.bottom() - split_y)

        # 两区表头字号统一：按「较矮的那个区」算，保证两边都放得下且一样大
        min_sec_h = min(up_rect.height(), low_rect.height())
        sec_head_px = max(11.0, min(min_sec_h * 0.22 * 0.62, 90.0))

        # ---- 分数颜色：整列一次算好（★ v2.9.33）
        # 必须是整列，不能逐行调用 score_color：按名次分档要知道「一共几个人、
        # 谁排第几」，只看单个数字根本算不出来。上下两区各自独立算，
        # 因为上半是「每个 IP 的总分」，下半是「每一手的分数」，量纲不同。
        mode = str(cfg.get("wall_score_mode") or SCORE_MODE_RANK)
        score_mode_colors = assign_colors([p["fan"] for p in people], steps, mode)
        rec_colors = assign_colors([r.get("total_fan") or 0 for r in recs], steps, mode)

        self._paint_section(
            painter, up_rect,
            headers=self._up_headers(),
            aligns=("left", "center", "right"),
            cells=[[p["label"],
                    (str(p["cnt"]) if cfg["wall_show_cnt"] else ""),
                    str(p["fan"])] for p in people],
            # 上半：每个 IP 的【总分】整体算色 —— 按名次分档时必须看到全部人才知道谁第几名
            fills=[[MUTED, HEAD_COLOR, col]
                   for col in score_mode_colors],
            empty_text="今日暂无记录",
            score_colors=score_mode_colors,
            highlight_first=bool(cfg.get("wall_highlight_first", True)),
            head_px=sec_head_px, steps=steps, ratio=ratio, stroke=stroke)

        # ---- 上下之间的双线（明确分区，但不用格子）
        self._paint_divider(painter, QRectF(body.left(), split_y - 1.5,
                                            body.width(), 3.0))

        self._paint_section(
            painter, low_rect,
            headers=self._low_headers(),
            aligns=("left", "center", "right"),
            cells=[[str(r.get("label") or ""),
                    fmt_ts(r.get("ts_ms") or 0),
                    str(r.get("total_fan") or 0)] for r in recs],
            fills=None,
            empty_text="今日暂无算番记录",
            score_index=2,
            score_colors=rec_colors,
            head_px=sec_head_px, steps=steps, ratio=ratio, stroke=stroke)

    # -------------------------------------------------- 标题文字
    def _title_texts(self, people: List[Dict], recs: List[Dict]):
        d = day_text(self.day)
        # ★ day 为空 = 「全部日期」，那不是今天；只有日期真的等于今天才算今日
        _day = str(self.day or "").strip()
        is_today = bool(_day) and _day == time.strftime("%Y-%m-%d")
        total_hands = sum(int(p["cnt"]) for p in people)
        total_fan = sum(int(p["fan"]) for p in people)
        # 「全部日期」和「今日战绩」不能同时出现（自相矛盾）；只有真的是今天才写「今日」
        title = ("%s  今日战绩" % d) if is_today else ("%s  战绩" % d)
        if total_hands:
            sub = "共 %d 手 · %d 番 · %d 个 IP" % (total_hands, total_fan, len(people))
        else:
            # 空状态：副标题不再重复「今日暂无记录」（分区里已经写了），留空更干净
            sub = ""
        if self.msg:
            sub = self.msg
        return title, sub

    # -------------------------------------------------- 表头
    def _up_headers(self) -> List[str]:
        if self.cfg["wall_show_cnt"]:
            return ["IP", "次数", "总分"]
        return ["IP", "", "总分"]

    def _low_headers(self) -> List[str]:
        return ["IP", "时间", "分"]

    # -------------------------------------------------- 一整个分区
    def _paint_section(self, painter: QPainter, rect: QRectF,
                       headers: List[str], aligns: Tuple[str, ...],
                       cells: List[List[str]], fills: Optional[List[List[str]]],
                       empty_text: str, score_index: Optional[int] = None,
                       score_colors: Optional[List[str]] = None,
                       header_gap: float = 0.0,
                       head_px: Optional[float] = None,
                       steps: Optional[List[str]] = None,
                       ratio: float = STROKE_DEFAULT,
                       stroke: str = STROKE_COLOR_DEFAULT,
                       highlight_first: bool = False) -> None:
        if rect.height() < 24 or rect.width() < 60:
            return
        cols = self._col_rects(rect, len(headers))

        # 表头高度
        # ★ 上下两区的表头字号必须一样大。原来按「本区高度 × 0.22」算，
        #   下半区行数少、分到的高度多 → 表头「IP 时间 分」比上半大一圈，
        #   一眼看过去像两套版式。所以字号统一由 _paint_all 算好传进来。
        if head_px is None:
            head_h = max(16.0, min(rect.height() * 0.22, rect.height() * 0.5))
            head_px = max(11.0, min(head_h * 0.62, 90.0))
        else:
            head_h = max(16.0, min(rect.height() * 0.34, float(head_px) / 0.62))
        head_rect = QRectF(rect.left(), rect.top(), rect.width(), head_h)
        hf = make_font(self._font_family, head_px, True)
        for i, (txt, cr) in enumerate(zip(headers, cols)):
            if not txt:
                continue
            draw_outlined(painter, txt,
                          QRectF(cr.left(), head_rect.top(), cr.width(), head_h),
                          hf, HEAD_COLOR, aligns[i] if i < len(aligns) else "left",
                          ratio=ratio, stroke=stroke)
        # 表头下划线（只有这一条，不画竖线）
        ly = head_rect.bottom()
        _hline(painter, rect.left(), rect.right(), ly,
               QColor(53, 225, 255, 150), max(1.0, head_h * 0.055))

        area_top = ly + max(2.0, head_h * 0.12) + header_gap
        area_h = rect.bottom() - area_top
        if area_h <= 6:
            return
        n = len(cells)
        if n == 0:
            # 空状态文字别放太大：之前 80px 上限让「今日暂无记录」压过整屏，
            # 变成比数据还抢眼。压到区域高度的 1/5，并封顶 42px。
            px = max(12.0, min(area_h * 0.20, 42.0))
            draw_outlined(painter, empty_text,
                          QRectF(rect.left(), area_top, rect.width(), area_h),
                          make_font(self._font_family, px), MUTED, "center",
                          ratio=ratio, stroke=stroke)
            return

        # 一行的理想高度；太挤就减少显示行数并标注「还有 N 条」
        row_h = area_h / n
        min_row = 14.0
        shown = n
        if row_h < min_row:
            shown = max(1, int(area_h // min_row))
            row_h = area_h / shown
        font_px = max(12.0, min(row_h * 0.66, 300.0))
        body_font = make_font(self._font_family, font_px)
        # 分数颜色：调用方（_paint_all）已经整列算好传进来。
        # ★ v2.9.33 起不再在本函数内逐个 score_color —— 因为「按名次分档」
        #   必须看到整列才知道谁是第几名，逐个算根本做不到。
        colors = score_colors if score_colors is not None else []
        top_score = 0
        if score_index is not None and not colors:
            # 兼容老调用（没人传 score_colors）：退回按最高分归一化
            for row in cells:
                try:
                    top_score = max(top_score, int(row[score_index]))
                except Exception:       # noqa: BLE001
                    pass

        for r in range(shown):
            row = cells[r]
            y = area_top + row_h * r
            row_rect = QRectF(rect.left(), y, rect.width(), row_h)
            # ★ v2.9.33：第一名反色高亮 —— 整行铺该档底色、字改黑，远看第一眼就能认出榜首
            hl = bool(highlight_first) and r == 0 and bool(colors)
            if hl:
                # 底色自身够亮（黑字对比度 >= 4.5）才反色；深色底上黑字等于看不见，那就放弃反色
                if contrast_on_black(colors[0]) < 4.5:
                    hl = False
            if hl:
                band = QRectF(rect.left(), y + row_h * 0.06,
                              rect.width(), row_h * 0.88)
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(colors[0])))
                radius = min(row_h * 0.18, 10.0)
                painter.drawRoundedRect(band, radius, radius)
                painter.restore()
            elif self.cfg["wall_show_lines"] and r > 0:
                _hline(painter, rect.left(), rect.right(), y, ROW_LINE_COLOR, 1.0)
            for i, txt in enumerate(row[:len(cols)]):
                if not txt:
                    continue
                palette = steps or DEFAULT_STEPS
                # 反色行：字改黑、描边同底色（描边不外扩，块内更干净）
                row_stroke = colors[0] if hl else stroke
                if fills is not None and r < len(fills) and i < len(fills[r]):
                    col = fills[r][i]
                elif i == len(row) - 1:
                    # 最后一列（分数）用整列算好的颜色
                    if r < len(colors):
                        col = colors[r]
                    else:
                        try:
                            col = score_color(int(txt), top_score, palette)
                        except Exception:       # noqa: BLE001
                            col = palette[-1]
                else:
                    col = palette[-1]
                if hl:
                    col = "#000000"
                draw_outlined(painter, txt,
                              QRectF(cols[i].left(), row_rect.top(),
                                     cols[i].width(), row_h),
                              body_font, col,
                              aligns[i] if i < len(aligns) else "left",
                              ratio=ratio, stroke=row_stroke)

        if shown < n:
            # 放不下时**明确告知**，不静默丢行
            note = "还有 %d 条未显示（窗口太矮，可放大或调小条数）" % (n - shown)
            draw_outlined(painter, note,
                          QRectF(rect.left(), area_top + row_h * shown - 1,
                                 rect.width(), max(12.0, row_h * 0.9)),
                          make_font(self._font_family, max(10.0, font_px * 0.42)),
                          MUTED, "right", ratio=ratio, stroke=stroke)

    # -------------------------------------------------- 列宽分配
    def _col_rects(self, rect: QRectF, ncols: int) -> List[QRectF]:
        """三列比例：IP 42% / 中间 24% / 分数 34%（分数右对齐，个位天然对齐）"""
        if ncols <= 1:
            return [rect]
        if ncols == 2:
            ratios = [0.62, 0.38]
        else:
            ratios = [0.42, 0.24, 0.34][:ncols]
            s = sum(ratios)
            ratios = [r / s for r in ratios]
        out: List[QRectF] = []
        x = rect.left()
        for i, rt in enumerate(ratios):
            cw = rect.width() * rt
            out.append(QRectF(x, rect.top(), cw, rect.height()))
            x += cw
        return out

    # -------------------------------------------------- 分区双线
    def _paint_divider(self, painter: QPainter, rect: QRectF) -> None:
        _hline(painter, rect.left(), rect.right(), rect.top(),
               QColor(53, 225, 255, 200), 2.0)
        _hline(painter, rect.left(), rect.right(), rect.top() + 2.5,
               QColor(53, 225, 255, 70), 1.0)


# ---------------------------------------------------------------- 上墙设置窗口
# ★ v2.9.32：设置窗口从单页改成四个标签页，已拆到 mahjong_wall_config.py。
#   拆的理由同样是「单文件不超过 1000 行」；对外名字不变，
#   所以主程序仍然可以 `from mahjong_wall import WallConfigDialog`。
# ---------------------------------------------------------------- 看板窗口
class WallBoardDialog(QDialog):
    """独立的大屏看板窗口

    · 黑底 + 白描边 + 分数色阶，纯自绘（见 WallBoardWidget）
    · F11 / 双击 全屏，Esc 退出全屏（全屏时底部按钮条自动隐藏）
    · 自带 2 秒轮询；只在 `StatsDB.signal()` 变了才重新查库，挂一整天也不费资源
    · 数据源是宿主的 StatsDB（stat_db）；库不可用时屏上直接写原因，不弹窗打扰
    """

    def __init__(self, stats, day: str, cfg: Optional[Dict], parent=None,
                 on_config_changed=None):
        super().__init__(parent)
        self.setWindowTitle("大屏看板")
        self.resize(1100, 720)
        self.setMinimumSize(420, 320)
        self.stats = stats
        # ★ 默认「今天」：用户要的就是当天数据。传空串进来也当今天处理。
        self.day = str(day or "").strip() or time.strftime("%Y-%m-%d")
        self.cfg = normalize_config(cfg)
        self._on_cfg_changed = on_config_changed
        self._sig: Optional[Tuple[int, int]] = None
        self._last_rows: List[Dict] = []
        self._msg = ""
        self._fs = False
        # ★ v2.9.32：几何持久化。拖动/缩放/最大化都记住，下次开窗还原。
        self._geo_dirty = False
        self._applying_geo = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.board = WallBoardWidget(self.cfg)
        lay.addWidget(self.board, 1)

        # 底部按钮条（全屏时藏起来；看板本身是黑底，这条也用深色）
        self.bar = QWidget()
        self.bar.setStyleSheet("background:#0d1319;")
        bl = QHBoxLayout(self.bar)
        bl.setContentsMargins(8, 5, 8, 5)
        bl.setSpacing(6)
        self.lbl_state = QLabel("")
        self.lbl_state.setStyleSheet("color:#8fa3b5;font-size:11px;")
        bl.addWidget(self.lbl_state, 1)

        # ★ 看板自己的日期选择：默认「今天」
        #   用户需求原话是「因为这个是当天的数据」，所以绝不能跟着统计页
        #   默认的「全部日期」走 —— 那样大屏上会滚出全部历史（实测 560 手）。
        self.cmb_day = QComboBox()
        self.cmb_day.setMinimumWidth(130)
        self.cmb_day.setToolTip("看板显示哪一天的数据（默认今天）")
        self.cmb_day.setStyleSheet(
            "QComboBox{background:#16202b;color:#d7e3ee;border:1px solid #24313f;"
            "border-radius:4px;padding:3px 6px;}"
            "QComboBox QAbstractItemView{background:#16202b;color:#d7e3ee;"
            "selection-background-color:#24313f;}")
        self._fill_days()
        self.cmb_day.currentIndexChanged.connect(self._day_changed)
        bl.addWidget(self.cmb_day)
        for text, tip, slot in (
            ("⚙ 上墙设置", "选哪些 IP 上墙、自定义显示名、最近显示几手",
             self.open_config),
            ("🔄 刷新", "立刻重读数据库（平时每 2 秒自己看一眼）",
             lambda: self.reload(force=True)),
            ("⛶ 全屏", "F11 全屏投屏；Esc 退出全屏", self.toggle_fullscreen),
            ("✕ 关闭", "关闭看板（窗口位置会记住）", self.close),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet(
                "QPushButton{background:#16202b;color:#d7e3ee;border:1px solid #24313f;"
                "border-radius:4px;padding:4px 10px;}"
                "QPushButton:hover{background:#1e2c3a;}")
            b.clicked.connect(slot)
            bl.addWidget(b)
        lay.addWidget(self.bar)

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.reload)
        self.timer.start()
        self.reload(force=True)
        # 几何放在最后应用：前面 self.resize(1100,720) 只是兜底初值
        self.apply_geometry()

    # -------------------------------------------------- 数据
    def _fill_days(self) -> None:
        """日期下拉：今天 / 全部日期 + 库里实际有的日期（倒序）"""
        box = self.cmb_day
        today = time.strftime("%Y-%m-%d")
        days = []
        try:
            if self.stats is not None:
                days = [str(d) for d in self.stats.list_days()]
        except Exception:       # noqa: BLE001
            days = []
        box.blockSignals(True)
        try:
            box.clear()
            box.addItem("今天（%s）" % today, today)
            if today not in days:
                pass        # 今天还没记录也照样能选中，看到「今日暂无记录」才有意义
            box.addItem("全部日期", "")
            for d in days:
                if d != today:
                    box.addItem(d, d)
            want = self.day or today
            pos = box.findData(want)
            box.setCurrentIndex(pos if pos >= 0 else 0)
        finally:
            box.blockSignals(False)

    def _day_changed(self, _i: int = -1) -> None:
        self.day = str(self.cmb_day.currentData() or "")
        self.reload(force=True)

    def set_day(self, day: str) -> None:
        """外部指定日期（主窗口用）；空串 = 今天"""
        d = str(day or "").strip() or time.strftime("%Y-%m-%d")
        self.day = d
        pos = self.cmb_day.findData(d)
        if pos >= 0 and pos != self.cmb_day.currentIndex():
            self.cmb_day.blockSignals(True)
            try:
                self.cmb_day.setCurrentIndex(pos)
            finally:
                self.cmb_day.blockSignals(False)
        self.reload(force=True)

    def set_config(self, cfg: Optional[Dict]) -> None:
        old_geo = list(self.cfg.get("wall_geo") or [])
        old_max = bool(self.cfg.get("wall_maximized"))
        self.cfg = normalize_config(cfg)
        self.board.set_config(self.cfg)
        # 窗口页改了尺寸/最大化 → 立刻作用到真窗口（用户点完就能看到）
        if (list(self.cfg.get("wall_geo") or []) != old_geo
                or bool(self.cfg.get("wall_maximized")) != old_max):
            self.apply_geometry()
        self._sig = None            # 配置变了（可能筛掉了 IP）→ 强制重算
        self.reload(force=True)

    def reload(self, force: bool = False) -> None:
        """读一天的全部记录 → 交给画布

        ★ 轮询只查 `signal()`（SELECT MAX(id), COUNT(*)），没变化直接返回，
          不做任何渲染，所以挂一整天也几乎不耗 CPU。
        """
        db = self.stats
        if db is None:
            self._apply([], "统计库不可用（mahjong_stats.db 打不开）")
            return
        try:
            sig = db.signal()
        except Exception as exc:        # noqa: BLE001
            self._apply([], "读取数据库信号失败：%r" % (exc,))
            return
        if not force and self._sig is not None and sig == self._sig:
            return
        self._sig = sig
        try:
            # 一次取够：上半要按 IP 全量汇总，下半只取前 N 条（切在画布里做）
            rows = db.recent_rows(self.day or None, None, 2000)
        except Exception as exc:        # noqa: BLE001
            self._apply([], "读取记录失败：%r" % (exc,))
            return
        self._apply(rows, "")

    def _apply(self, rows: List[Dict], msg: str) -> None:
        self._last_rows = list(rows or [])
        self._msg = msg
        self.board.set_data(self.day, self._last_rows, self._msg)
        if msg:
            self.lbl_state.setText(msg)
        else:
            self.lbl_state.setText(
                "共 %d 条记录 · %s · 每 2 秒自动刷新"
                % (len(self._last_rows), day_text(self.day)))

    # -------------------------------------------------- 设置
    def open_config(self) -> None:
        ips = sorted({str(r.get("ip") or "").strip() for r in self._last_rows})
        dlg = WallConfigDialog(self.cfg, ips, self)
        dlg.exec()
        # 对话框内部已经通过 on_config_changed 实时推过来了；这里再确保一次
        self.set_config(dlg.cfg)

    def on_config_changed(self, cfg: Dict) -> None:
        """设置窗口改动 → 立刻生效 + 交给宿主存盘（实时自动保存）"""
        self.set_config(cfg)
        cb = self._on_cfg_changed
        if callable(cb):
            cb(self.cfg)

    # -------------------------------------------------- 窗口几何
    # ★ v2.9.32：用户要求「可以最大化，也可以自定义拖动大小，并且持久记忆，
    #   还有一键恢复默认，避免出现问题无法恢复」。
    #   保存时机：拖动/缩放停下、最大化状态变化、关窗时。存的是 cfg["wall_geo"]，
    #   由宿主 _autosave_settings() 落盘（500ms 防抖），所以是「实时自动保存」。
    def _screens(self) -> List:
        try:
            from PySide6.QtGui import QGuiApplication
            return list(QGuiApplication.screens())
        except Exception:       # noqa: BLE001
            return []

    def apply_geometry(self) -> None:
        """把 cfg 里的几何应用到真窗口（带屏幕兜底）"""
        if self._fs:
            return              # 全屏时不折腾几何，退出全屏再说
        geo = normalize_geo(self.cfg.get("wall_geo"), self._screens())
        self._applying_geo = True
        try:
            if geo is not None:
                x, y, w, h = geo
                if x is None or y is None:
                    # 记住的位置已经不在任何屏幕上（比如副屏被拔了）→ 只保留尺寸
                    self.resize(w, h)
                else:
                    self.setGeometry(x, y, w, h)
            if bool(self.cfg.get("wall_maximized")):
                self.showMaximized()
            elif self.isMaximized():
                self.showNormal()
        finally:
            self._applying_geo = False

    def capture_geometry(self, save: bool = True) -> None:
        """把当前窗口几何写回 cfg（最大化时保留原始尺寸，别记成满屏尺寸）"""
        if self._applying_geo or self._fs or not self.isVisible():
            return
        maximized = bool(self.isMaximized())
        # normalGeometry() 才是「还原后」的尺寸，最大化时用它，否则退出最大化会
        # 变成一个占满整屏、但又不是最大化的怪窗口。
        g = self.normalGeometry() if maximized else self.geometry()
        geo = [int(g.x()), int(g.y()), int(g.width()), int(g.height())]
        changed = (geo != list(self.cfg.get("wall_geo") or [])
                   or maximized != bool(self.cfg.get("wall_maximized")))
        if not changed:
            return
        self.cfg["wall_geo"] = geo
        self.cfg["wall_maximized"] = maximized
        if save:
            cb = self._on_cfg_changed
            if callable(cb):
                cb(self.cfg)

    def geometry_summary(self) -> str:
        """给人看的一句话：现在多大 / 是否最大化"""
        g = self.normalGeometry() if self.isMaximized() else self.geometry()
        txt = "%d × %d" % (g.width(), g.height())
        if self._fs:
            return txt + "（全屏中）"
        if self.isMaximized():
            return txt + "（已最大化）"
        return txt + "（位置 %d, %d）" % (g.x(), g.y())

    def reset_geometry(self) -> None:
        """一键恢复默认窗口大小（不动其它设置）"""
        self._fs = False
        self.cfg["wall_geo"] = []
        self.cfg["wall_maximized"] = False
        self._applying_geo = True
        try:
            if self.isMaximized() or self.isFullScreen():
                self.showNormal()
            self.resize(*DEFAULT_GEO_SIZE)
            self.move(max(0, (self.screen().availableGeometry().width()
                              - DEFAULT_GEO_SIZE[0]) // 2),
                      max(0, (self.screen().availableGeometry().height()
                              - DEFAULT_GEO_SIZE[1]) // 2))
        finally:
            self._applying_geo = False
        cb = self._on_cfg_changed
        if callable(cb):
            cb(self.cfg)

    def moveEvent(self, event):                 # noqa: N802
        super().moveEvent(event)
        self.capture_geometry()

    def resizeEvent(self, event):               # noqa: N802
        super().resizeEvent(event)
        self.capture_geometry()

    def changeEvent(self, event):               # noqa: N802
        super().changeEvent(event)
        try:
            if event.type() == QEvent.WindowStateChange:
                self.capture_geometry()
        except Exception:       # noqa: BLE001
            pass

    # -------------------------------------------------- 全屏
    def toggle_fullscreen(self) -> None:
        self._set_fullscreen(not self._fs)

    def _set_fullscreen(self, on: bool) -> None:
        self._fs = bool(on)
        self.bar.setVisible(not self._fs)
        if on:
            self.showFullScreen()
        else:
            self.showNormal()

    def mouseDoubleClickEvent(self, event):     # noqa: N802
        if event.button() == Qt.LeftButton:
            self.toggle_fullscreen()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):             # noqa: N802
        k = event.key()
        if k == Qt.Key_F11:
            self.toggle_fullscreen()
            return
        if k == Qt.Key_Escape and self._fs:
            self._set_fullscreen(False)
            return
        super().keyPressEvent(event)

    def showEvent(self, event):                 # noqa: N802
        super().showEvent(event)
        self.reload(force=True)
        self.timer.start()

    def closeEvent(self, event):                # noqa: N802
        # 关窗前最后确认一次几何（拖动后立刻关窗也不能丢）
        try:
            self.capture_geometry()
        except Exception:       # noqa: BLE001
            pass
        try:
            self.timer.stop()
        except Exception:       # noqa: BLE001
            pass
        super().closeEvent(event)
