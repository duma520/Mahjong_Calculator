# -*- coding: utf-8 -*-
"""大屏看板 ·「上墙设置」窗口（v2.9.32 从单页改成四个标签页）。

为什么拆成独立文件
    项目规矩「单文件不超过 1000 行」。四个标签页 + 配色库浏览 + 自定义配色编辑
    加起来四百多行，塞回 mahjong_wall.py 会把它顶到 1200 行以上。
    拆分边界沿用原来的思路：**本文件 = 只跟「设置界面」有关的窗口**，
    画布与看板窗口留在 mahjong_wall.py。

四个标签页（用户要求「后续有很多需要设置和自定义的」）
    📊 数据   哪些 IP 上墙 / 自定义显示名 / 最近几手 / IP 显示方式 / 显示开关
    🎨 外观   描边粗细（带实时预览）
    🌈 配色   240 套内置方案 + 自定义配色保存/删除（带实时预览）
    🪟 窗口   当前尺寸 / 启动最大化 / 恢复默认尺寸

两项兜底（用户要求「避免出现问题无法恢复」）
    · 每页右下角「本页恢复默认」—— 只重置这一页，不影响其它页
    · 窗口底部「全部恢复默认」—— 二次确认后整份重置回出厂值

所有改动**实时回调**给宿主并立刻落盘（与主程序「设置实时自动保存」一致），
没有「保存」按钮，也不该有 —— 用户点关闭时不该还要问「要不要保存」。
"""
import time
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFontMetricsF, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog,
                               QComboBox, QDialog, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton,
                               QRadioButton, QSlider, QSpinBox, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from mahjong_wall_core import (
    BG,
    CUSTOM_NAME_MAX,
    CUSTOM_PALETTE_MAX,
    DEFAULT_GEO_SIZE,
    DEFAULT_PALETTE_ID,
    DEFAULT_STEPS,
    LABEL_MODE_ITEMS,
    SCORE_MODE_ITEMS,
    SCORE_MODE_RANK,
    SCORE_MODE_RATIO,
    STROKE_AUTO,
    STROKE_COLOR_DEFAULT,
    STROKE_DEFAULT,
    STROKE_MAX,
    STROKE_MIN,
    UNKNOWN_IP_TEXT,
    assign_colors,
    build_labels,
    contrast_on_black,
    custom_palette_id,
    default_config,
    draw_outlined,
    expand_hex,
    is_custom_palette_id,
    is_hex_color,
    make_font,
    normalize_config,
    normalize_steps,
    palette_groups,
    palettes_all,
    pick_font_family,
    resolve_palette_name,
    resolve_steps,
    resolve_stroke_color,
    stroke_setting,
)

# 每页「本页恢复默认」要重置的键 —— 与标签页一一对应，漏写会导致「点了没反应」
PAGE_KEYS: Dict[str, Tuple[str, ...]] = {
    "data": ("wall_ips", "wall_names", "wall_recent_n", "wall_label_mode",
             "wall_show_lines", "wall_hide_unknown", "wall_show_cnt"),
    "style": ("wall_stroke", "wall_stroke_color"),
    "palette": ("wall_palette", "wall_palettes",
                "wall_score_mode", "wall_highlight_first"),
    "window": ("wall_geo", "wall_maximized"),
}

PAGE_TITLES = (("data", "📊 数据"), ("style", "🎨 外观"),
               ("palette", "🌈 配色"), ("window", "🪟 窗口"))


class StylePreview(QWidget):
    """配色 / 描边效果预览条：黑底 + 5 档示例分数 + 白描边

    为什么要有预览：描边粗细和配色都是「看着调」的东西，让用户改完回去看大屏
    再回来改，来回三四次就烦了。这里直接按大屏的真实画法（同一套
    draw_outlined + 色阶）缩小画一遍，改哪个参数立刻能看到差别。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(104)
        self.steps: Tuple[str, ...] = tuple(DEFAULT_STEPS)
        self.ratio: float = STROKE_DEFAULT
        self.stroke: str = STROKE_COLOR_DEFAULT
        self.family = pick_font_family()

    def set_style(self, steps, ratio: float, stroke: str = STROKE_COLOR_DEFAULT) -> None:
        st = tuple(steps) if steps and len(steps) == 5 else tuple(DEFAULT_STEPS)
        r = float(ratio)
        s = str(stroke or STROKE_COLOR_DEFAULT)
        if st == self.steps and abs(r - self.ratio) < 1e-6 and s == self.stroke:
            return
        self.steps = st
        self.ratio = r
        self.stroke = s
        self.update()

    def paintEvent(self, _e):        # noqa: N802
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            rect = self.rect()
            p.fillRect(rect, QColor(BG))
            w, h = float(rect.width()), float(rect.height())
            if w < 40 or h < 30:
                return
            nums = ("7900", "501", "794", "241", "88")
            col_w = w / len(nums)
            # 字号不能只看高度：配色页右侧那条预览只有 300 来像素宽，
            # 只按高度算会把 46px 的字塞进 60px 的格子，5 个数字直接叠在一起
            # （实测「7900 501」糊成「7900501」）。所以按「最宽的那个数字
            # 放得进一格」再回退一步，取两者较小值。
            px = max(11.0, min(h * 0.46, 46.0))
            for _ in range(30):
                fm = QFontMetricsF(make_font(self.family, int(px)))
                widest = max(fm.horizontalAdvance(t) for t in nums)
                if widest <= col_w * 0.92 or px <= 11.0:
                    break
                px = max(11.0, px * 0.92)
            font = make_font(self.family, int(px))
            top_pad = max(6.0, h * 0.08)
            cell_h = h - top_pad * 2
            for i, txt in enumerate(nums):
                cr = QRectF(i * col_w, top_pad, col_w, cell_h)
                draw_outlined(p, txt, cr, font, self.steps[i], "center",
                              ratio=self.ratio, stroke=self.stroke)
        finally:
            p.end()


class WallConfigDialog(QDialog):
    """看板的「上墙设置」：四个标签页，改动实时生效并自动保存"""

    def __init__(self, cfg: Optional[Dict], ips: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("大屏看板 · 上墙设置")
        self.setMinimumSize(720, 560)
        self.cfg = normalize_config(cfg)
        self._ips = [str(x or "").strip() for x in (ips or [])]
        self._loading = True
        self._status = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        tip = QLabel("改动立刻生效并自动保存，不用点保存。任一页改乱了，"
                     "点右下角「本页恢复默认」；全乱了点底部「全部恢复默认」。")
        tip.setStyleSheet("color:#555;")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_data_page(), PAGE_TITLES[0][1])
        self.tabs.addTab(self._build_style_page(), PAGE_TITLES[1][1])
        self.tabs.addTab(self._build_palette_page(), PAGE_TITLES[2][1])
        self.tabs.addTab(self._build_window_page(), PAGE_TITLES[3][1])
        self.tabs.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tabs, 1)

        # ---- 底部：状态 + 全局恢复默认 + 关闭
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#b26a00;font-size:11px;")
        self.lbl_status.setWordWrap(True)
        bottom.addWidget(self.lbl_status, 1)
        btn_reset_all = QPushButton("全部恢复默认…")
        btn_reset_all.setToolTip("把看板的所有设置（含自定义配色）重置回出厂值")
        btn_reset_all.clicked.connect(self._reset_all)
        bottom.addWidget(btn_reset_all)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        lay.addLayout(bottom)

        self._loading = False
        self._refresh_note()
        self._refresh_stroke_label()
        self._refresh_stroke_color_ui()
        self._refresh_score_mode_label()
        self._refresh_style_preview()
        self._fill_palette_values()

    # ================================================================ 📊 数据页
    def _build_data_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        box_ip = QGroupBox("哪些 IP 上墙")
        bl = QVBoxLayout(box_ip)
        bl.setSpacing(6)
        hint = QLabel("勾选「上墙」= 这个 IP 显示在看板上；一个都不勾 = 当天有几个 IP 就上几个。"
                      "「显示名」留空 = 按下面的默认规则；填了就一律用它，比如填「2-10」。")
        hint.setStyleSheet("color:#666;")
        hint.setWordWrap(True)
        bl.addWidget(hint)

        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["上墙", "实际 IP", "显示名（可双击改）"])
        self.tbl.setEditTriggers(QAbstractItemView.DoubleClicked
                                 | QAbstractItemView.EditKeyPressed)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        bl.addWidget(self.tbl, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, tip_txt, slot in (
            ("全选上墙", "所有 IP 都上墙", lambda: self._set_all(True)),
            ("全不选（=全部上墙）", "清空勾选；当天有几个 IP 就上几个", lambda: self._set_all(False)),
            ("清空自定义名", "把显示名全部清空，回到「末位段 / 完整 IP」规则", self._clear_names),
        ):
            b = QPushButton(text)
            b.setToolTip(tip_txt)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        bl.addLayout(row)
        lay.addWidget(box_ip, 1)

        self.lbl_note = QLabel("")
        self.lbl_note.setStyleSheet("color:#b26a00;")
        self.lbl_note.setWordWrap(True)
        lay.addWidget(self.lbl_note)

        # ---- 显示规则
        box2 = QGroupBox("显示规则")
        g = QVBoxLayout(box2)
        g.setSpacing(6)
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        r1.addWidget(QLabel("下面显示最近"))
        self.spn_n = QSpinBox()
        self.spn_n.setRange(1, 50)
        self.spn_n.setValue(int(self.cfg["wall_recent_n"]))
        self.spn_n.setSuffix(" 手")
        self.spn_n.setToolTip("下半部分显示最近多少条算番记录（1~50）")
        self.spn_n.valueChanged.connect(self._on_any_change)
        r1.addWidget(self.spn_n)
        r1.addSpacing(12)
        r1.addWidget(QLabel("IP 显示"))
        self.cmb_mode = QComboBox()
        for key, label in LABEL_MODE_ITEMS:
            self.cmb_mode.addItem(label, key)
        idx = self.cmb_mode.findData(self.cfg["wall_label_mode"])
        self.cmb_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_mode.currentIndexChanged.connect(self._on_any_change)
        r1.addWidget(self.cmb_mode, 1)
        g.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(12)
        self.cb_cnt = QCheckBox("显示「次数」列")
        self.cb_cnt.setChecked(bool(self.cfg["wall_show_cnt"]))
        self.cb_cnt.toggled.connect(self._on_any_change)
        r2.addWidget(self.cb_cnt)
        self.cb_lines = QCheckBox("行间分隔线")
        self.cb_lines.setChecked(bool(self.cfg["wall_show_lines"]))
        self.cb_lines.toggled.connect(self._on_any_change)
        r2.addWidget(self.cb_lines)
        self.cb_unknown = QCheckBox("隐藏「%s」那行" % UNKNOWN_IP_TEXT)
        self.cb_unknown.setChecked(bool(self.cfg["wall_hide_unknown"]))
        self.cb_unknown.setToolTip(
            "早期记录 / 桌面端没上报 IP 的记录会归到「%s」这一行" % UNKNOWN_IP_TEXT)
        self.cb_unknown.toggled.connect(self._on_any_change)
        r2.addWidget(self.cb_unknown)
        r2.addStretch(1)
        g.addLayout(r2)
        lay.addWidget(box2)

        self.tbl.itemChanged.connect(self._on_any_change)
        self._fill_table()
        lay.addLayout(self._page_reset_row("data"))
        return page

    # ================================================================ 🎨 外观页
    def _build_style_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        box = QGroupBox("字体描边粗细")
        g = QVBoxLayout(box)
        g.setSpacing(6)
        info = QLabel("字是彩色的、背景是纯黑，不描边的话深色字在几米外会糊进背景。"
                      "粗细按**字号的比例**算，不是固定像素 —— 所以窗口放大、字变大时，"
                      "白边的比例不变。")
        info.setStyleSheet("color:#666;")
        info.setWordWrap(True)
        g.addWidget(info)

        r = QHBoxLayout()
        r.setSpacing(8)
        r.addWidget(QLabel("细"))
        self.sld_stroke = QSlider(Qt.Horizontal)
        self.sld_stroke.setRange(int(STROKE_MIN * 100), int(STROKE_MAX * 100))
        self.sld_stroke.setValue(int(round(float(self.cfg["wall_stroke"]) * 100)))
        self.sld_stroke.setTickPosition(QSlider.TicksBelow)
        self.sld_stroke.setTickInterval(2)
        self.sld_stroke.valueChanged.connect(self._on_stroke_changed)
        r.addWidget(self.sld_stroke, 1)
        r.addWidget(QLabel("粗"))
        g.addLayout(r)

        self.lbl_stroke = QLabel("")
        self.lbl_stroke.setStyleSheet("color:#333;")
        g.addWidget(self.lbl_stroke)

        r2 = QHBoxLayout()
        r2.setSpacing(6)
        for text, val, tip_txt in (("细（推荐）", 0.08, "43px 字约 3.4px 白边，远看清晰、近看不发肿"),
                                   ("中", 0.11, "43px 字约 4.7px"),
                                   ("粗（v2.9.31 旧值）", 0.14, "43px 字约 6.0px，笔画容易糊在一起")):
            b = QPushButton(text)
            b.setToolTip(tip_txt)
            b.clicked.connect(lambda _=False, v=val: self.sld_stroke.setValue(int(v * 100)))
            r2.addWidget(b)
        r2.addStretch(1)
        g.addLayout(r2)
        lay.addWidget(box)

        # ---- 描边颜色（v2.9.32 新增）：白色 / 自动配色 / 自定义
        box_color = QGroupBox("字体描边颜色")
        gc = QVBoxLayout(box_color)
        gc.setSpacing(6)
        cinfo = QLabel("白色描边最保险，但不是每套配色都好看 —— 亮黄、亮金这类浅色字"
                       "配白边几乎看不出轮廓，只剩一团亮。选「自动配色」会按当前配色方案"
                       "算一个同色系的深/浅罩边：偏暗的配色托一圈亮边，偏亮的配色描一圈暗边。")
        cinfo.setStyleSheet("color:#666;")
        cinfo.setWordWrap(True)
        gc.addWidget(cinfo)

        self.rb_stroke_white = QRadioButton("白色（默认，所有配色通用）")
        self.rb_stroke_auto = QRadioButton("自动配色（按当前配色自动选更合适的描边色）")
        self.rb_stroke_custom = QRadioButton("自定义")
        for rb in (self.rb_stroke_white, self.rb_stroke_auto, self.rb_stroke_custom):
            rb.toggled.connect(self._on_stroke_color_changed)
            gc.addWidget(rb)

        crow = QHBoxLayout()
        crow.setSpacing(6)
        crow.addSpacing(22)
        self.ed_stroke_color = QLineEdit()
        self.ed_stroke_color.setMaxLength(7)
        self.ed_stroke_color.setFixedWidth(96)
        self.ed_stroke_color.setPlaceholderText("#RRGGBB")
        self.ed_stroke_color.editingFinished.connect(self._on_stroke_color_text)
        crow.addWidget(self.ed_stroke_color)
        self.btn_stroke_pick = QPushButton("取色…")
        self.btn_stroke_pick.clicked.connect(self._pick_stroke_color)
        crow.addWidget(self.btn_stroke_pick)
        self.sw_stroke_preview = QLabel("")
        self.sw_stroke_preview.setFixedSize(44, 20)
        self.sw_stroke_preview.setToolTip("当前描边色的实际颜色")
        crow.addWidget(self.sw_stroke_preview)
        crow.addStretch(1)
        gc.addLayout(crow)

        self.lbl_stroke_color = QLabel("")
        self.lbl_stroke_color.setStyleSheet("color:#333;")
        self.lbl_stroke_color.setWordWrap(True)
        gc.addWidget(self.lbl_stroke_color)
        lay.addWidget(box_color)

        self.preview_style = StylePreview()
        lay.addWidget(QLabel("实时预览（黑底 + 当前描边色 + 当前配色）："))
        lay.addWidget(self.preview_style)
        lay.addStretch(1)
        lay.addLayout(self._page_reset_row("style"))
        return page

    # ================================================================ 🌈 配色页
    def _build_palette_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(QLabel("搜索"))
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("输入色名筛选，如「森林」「马卡龙」「红」")
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.textChanged.connect(self._on_search_changed)
        top.addWidget(self.ed_search, 1)
        lay.addLayout(top)

        mid = QHBoxLayout()
        mid.setSpacing(8)
        self.lst_palette = QListWidget()
        self.lst_palette.setMinimumWidth(240)
        self.lst_palette.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lst_palette.currentItemChanged.connect(self._on_palette_picked)
        mid.addWidget(self.lst_palette, 2)

        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(QLabel("选中方案的效果："))
        self.preview_palette = StylePreview()
        right.addWidget(self.preview_palette)
        self.lbl_palette = QLabel("")
        self.lbl_palette.setStyleSheet("color:#333;")
        self.lbl_palette.setWordWrap(True)
        right.addWidget(self.lbl_palette)
        right.addStretch(1)
        mid.addLayout(right, 3)
        lay.addLayout(mid, 1)

        # ---- 分档方式 + 第一名高亮（★ v2.9.33）
        box_mode = QGroupBox("分档方式（五档颜色怎么分配给一列分数）")
        gm = QVBoxLayout(box_mode)
        gm.setSpacing(6)
        mr = QHBoxLayout()
        mr.setSpacing(6)
        mr.addWidget(QLabel("口径"))
        self.cmb_score_mode = QComboBox()
        for mid_, label in SCORE_MODE_ITEMS:
            self.cmb_score_mode.addItem(label, mid_)
        self.cmb_score_mode.currentIndexChanged.connect(self._on_score_mode_changed)
        mr.addWidget(self.cmb_score_mode, 1)
        gm.addLayout(mr)
        self.lbl_score_mode = QLabel("")
        self.lbl_score_mode.setStyleSheet("color:#333;")
        self.lbl_score_mode.setWordWrap(True)
        gm.addWidget(self.lbl_score_mode)
        self.cb_hl_first = QCheckBox("第一名整行反色高亮（底色铺满、文字改黑）")
        self.cb_hl_first.setChecked(bool(self.cfg.get("wall_highlight_first", True)))
        self.cb_hl_first.setToolTip(
            "把榜首那一行铺成该档的底色、文字改黑，几米外第一眼就能看出谁是第一名。\n"
            "底色本身太暗（黑字压不上去）时会自动放弃这一行的高亮，不会看不清。")
        self.cb_hl_first.toggled.connect(self._on_any_change)
        gm.addWidget(self.cb_hl_first)
        gm.addWidget(QLabel("说明：麻将一桌最多 4 人，「按名次铺开」能让 4 个人各占一个颜色，最好分辨；\n"
                            "「按分值比例」会让分差悬殊时多数人挤在最低档（都变白色），只有想强调分差时才用。"))
        lay.addWidget(box_mode)

        # ---- 自定义配色
        box = QGroupBox("自定义配色（把自己的 5 个颜色存成有名字的方案）")
        g = QVBoxLayout(box)
        g.setSpacing(6)
        r = QHBoxLayout()
        r.setSpacing(6)
        r.addWidget(QLabel("方案名"))
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("例如：我的电视专用")
        self.ed_name.setMaxLength(CUSTOM_NAME_MAX)
        r.addWidget(self.ed_name, 1)
        g.addLayout(r)

        cr = QHBoxLayout()
        cr.setSpacing(6)
        cr.addWidget(QLabel("5 档颜色"))
        self.ed_colors: List[QLineEdit] = []
        for i in range(5):
            ed = QLineEdit()
            ed.setMaxLength(7)
            ed.setFixedWidth(84)
            ed.setToolTip("第 %d 档（%s）—— 格式 #RRGGBB"
                          % (i + 1, "最高分" if i == 0 else ("最低分" if i == 4 else "中间")))
            ed.textChanged.connect(self._on_custom_color_edited)
            self.ed_colors.append(ed)
            cr.addWidget(ed)
            pick = QPushButton("…")
            pick.setFixedWidth(26)
            pick.setToolTip("打开取色器")
            pick.clicked.connect(lambda _=False, k=i: self._pick_color(k))
            cr.addWidget(pick)
        cr.addStretch(1)
        g.addLayout(cr)

        br = QHBoxLayout()
        br.setSpacing(6)
        b_save = QPushButton("保存为自定义方案")
        b_save.clicked.connect(self._save_custom)
        br.addWidget(b_save)
        b_del = QPushButton("删除选中自定义方案")
        b_del.clicked.connect(self._del_custom)
        br.addWidget(b_del)
        b_from = QPushButton("用当前方案填充")
        b_from.setToolTip("把当前选中方案的 5 个颜色填进上面，再微调")
        b_from.clicked.connect(self._fill_colors_from_current)
        br.addWidget(b_from)
        br.addStretch(1)
        g.addLayout(br)
        g.addWidget(QLabel("提示：色值必须是 #RRGGBB；保存后会出现在列表最上面的「自定义」组里。"))
        lay.addWidget(box)

        self._fill_palette_list()
        lay.addLayout(self._page_reset_row("palette"))
        return page

    # ================================================================ 🪟 窗口页
    def _build_window_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        box = QGroupBox("看板窗口")
        g = QVBoxLayout(box)
        g.setSpacing(8)
        self.lbl_geo = QLabel("")
        self.lbl_geo.setStyleSheet("color:#333;")
        g.addWidget(self.lbl_geo)

        self.cb_max = QCheckBox("打开时自动最大化")
        self.cb_max.setChecked(bool(self.cfg["wall_maximized"]))
        self.cb_max.setToolTip("勾上后每次点「大屏看板」直接铺满屏幕，再按 F11 可全屏无边框")
        self.cb_max.toggled.connect(self._on_any_change)
        g.addWidget(self.cb_max)

        r = QHBoxLayout()
        r.setSpacing(6)
        self.btn_geo_reset = QPushButton(
            "恢复默认尺寸（%d × %d 并居中）" % DEFAULT_GEO_SIZE[:2])
        self.btn_geo_reset.setToolTip(
            "看板窗口被拖到奇怪的地方、或者尺寸弄乱了，点这里回到默认大小并居中")
        self.btn_geo_reset.clicked.connect(self._reset_geometry)
        r.addWidget(self.btn_geo_reset)
        r.addStretch(1)
        g.addLayout(r)

        info = QLabel("看板窗口可以随便拖、随便拉大小，关掉时会记住位置和尺寸，下次打开还原。"
                      "拔掉副屏 / 投影后再打开也不会跑到看不见的地方 —— 程序会检查窗口是否"
                      "落在当前接着的屏幕上，落不上就只保留尺寸、重新居中。")
        info.setStyleSheet("color:#666;")
        info.setWordWrap(True)
        g.addWidget(info)
        lay.addWidget(box)
        lay.addStretch(1)
        lay.addLayout(self._page_reset_row("window"))
        return page

    def _page_reset_row(self, page_key: str) -> QHBoxLayout:
        """每页右下角的「本页恢复默认」——只重置这一页的键"""
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("本页恢复默认")
        b.setToolTip("只把这一页的设置恢复成出厂值，其它页不动")
        b.clicked.connect(lambda _=False, k=page_key: self._reset_page(k))
        row.addWidget(b)
        return row

    # ================================================================ 数据表
    def _fill_table(self) -> None:
        picking = set(self.cfg["wall_ips"])
        names = dict(self.cfg["wall_names"])
        self.tbl.blockSignals(True)
        try:
            self.tbl.setRowCount(len(self._ips))
            for i, ip in enumerate(self._ips):
                chk = QTableWidgetItem("")
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk.setCheckState(Qt.Checked if ip in picking else Qt.Unchecked)
                chk.setData(Qt.UserRole, ip)
                self.tbl.setItem(i, 0, chk)
                it_ip = QTableWidgetItem(ip or UNKNOWN_IP_TEXT)
                it_ip.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if not ip:
                    it_ip.setForeground(QBrush(QColor("#999999")))
                self.tbl.setItem(i, 1, it_ip)
                self.tbl.setItem(i, 2, QTableWidgetItem(names.get(ip, "")))
        finally:
            self.tbl.blockSignals(False)

    def _read_table(self) -> Tuple[List[str], Dict[str, str]]:
        picking: List[str] = []
        names: Dict[str, str] = {}
        for i in range(self.tbl.rowCount()):
            chk = self.tbl.item(i, 0)
            raw = str(chk.data(Qt.UserRole) or "") if chk else ""
            if chk is not None and chk.checkState() == Qt.Checked:
                picking.append(raw)
            cell = self.tbl.item(i, 2)
            nm = (cell.text().strip() if cell is not None else "")
            if nm:
                names[raw] = nm
        return picking, names

    def _set_all(self, on: bool) -> None:
        self.tbl.blockSignals(True)
        try:
            for i in range(self.tbl.rowCount()):
                it = self.tbl.item(i, 0)
                if it is not None:
                    it.setCheckState(Qt.Checked if on else Qt.Unchecked)
        finally:
            self.tbl.blockSignals(False)
        self._on_any_change()

    def _clear_names(self) -> None:
        self.tbl.blockSignals(True)
        try:
            for i in range(self.tbl.rowCount()):
                it = self.tbl.item(i, 2)
                if it is not None:
                    it.setText("")
        finally:
            self.tbl.blockSignals(False)
        self._on_any_change()

    def _refresh_note(self) -> None:
        labels, notes = build_labels(self._ips, self.cfg["wall_names"],
                                     self.cfg["wall_label_mode"])
        msgs = list(notes)
        if len(set(labels)) < len(labels):
            msgs.append("有 %d 行显示名重复，看板上会分不清是谁，建议填自定义名。"
                        % (len(labels) - len(set(labels))))
        if not self._ips:
            msgs = ["今天还没有任何记录，等有人算番后这里会列出 IP。"]
        self.lbl_note.setText("\n".join(msgs))

    # ================================================================ 配色列表
    def _fill_palette_list(self, keyword: str = "") -> None:
        kw = str(keyword or "").strip().lower()
        cur = str(self.cfg.get("wall_palette") or DEFAULT_PALETTE_ID)
        self.lst_palette.blockSignals(True)
        try:
            self.lst_palette.clear()
            cur_item = None

            def add_header(text: str) -> None:
                it = QListWidgetItem(text)
                it.setFlags(Qt.NoItemFlags)
                f = it.font()
                f.setBold(True)
                it.setFont(f)
                it.setForeground(QBrush(QColor("#0b6fa4")))
                self.lst_palette.addItem(it)

            def add_palette(pid: str, label: str) -> None:
                nonlocal cur_item
                if kw and kw not in label.lower():
                    return
                same = (pid == cur)
                it = QListWidgetItem(("● " if same else "○ ") + label)
                it.setData(Qt.UserRole, pid)
                if is_custom_palette_id(pid):
                    it.setForeground(QBrush(QColor("#7a3ea1")))
                self.lst_palette.addItem(it)
                if same:
                    cur_item = it

            customs = dict(self.cfg.get("wall_palettes") or {})
            if customs:
                add_header("★ 自定义（%d 套）" % len(customs))
                for nm in sorted(customs):
                    add_palette(custom_palette_id(nm), nm)

            add_header("★ 精选方案（%d 套，手挑）" % len(_curated_ids()))
            for pid, nm, _note in _curated_meta():
                add_palette(pid, "%s — %s" % (nm, _note))

            groups = palette_groups()
            if groups:
                add_header("▸ 色名派生方案（按色名派生，非权威色卡值）")
                for gname, items in groups:
                    shown = [(i, n) for i, n in items if not kw or kw in n.lower()]
                    if not shown:
                        continue
                    add_header("   · %s" % gname)
                    for pid, nm in items:
                        add_palette(pid, nm)

            if cur_item is not None:
                self.lst_palette.setCurrentItem(cur_item)
        finally:
            self.lst_palette.blockSignals(False)

    def _on_search_changed(self, text: str) -> None:
        self._fill_palette_list(text)

    # -------------------------------------------------- 分档方式（★ v2.9.33）
    def _on_score_mode_changed(self, _idx: int = 0) -> None:
        if self._loading:
            return
        mid_ = self.cmb_score_mode.currentData()
        self.cfg["wall_score_mode"] = str(mid_ or SCORE_MODE_RANK)
        self._refresh_score_mode_label()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    def _refresh_score_mode_label(self) -> None:
        mode = str(self.cfg.get("wall_score_mode") or SCORE_MODE_RANK)
        n = len(getattr(self, "_ips", []) or [])
        if not n:
            n = 4        # 典型场景就是一桌 4 人，没数据时按 4 人演示
        # 用一列「典型 4 人」的虚拟分值算一遍，直观告诉用户这个口径下一屏出几种颜色
        demo = [1000 - i * (400 // max(1, n - 1)) for i in range(n)] if n > 1 else [1000]
        steps = resolve_steps(self.cfg.get("wall_palette"), self.cfg)
        cols = assign_colors(demo, steps, mode)
        uniq = len(set(cols))
        if mode == SCORE_MODE_RATIO:
            warn = ("注意：分差悬殊时（如 8000 / 200 / 150 / 100）后几名会全部落进\n"
                    "最低档，一屏只剩 2 种颜色 —— 这是老口径的固有行为。")
        elif mode == SCORE_MODE_RANK:
            warn = ("它表达的是「名次」不是「分差」：两人只差 100 番也会拉开一档颜色。\n"
                    "想让颜色反映真实分差就切回「按分值比例」。")
        else:
            warn = ("阈值按 φ 衰减（1 / 0.618 / 0.382 / 0.236 / 0.146），\n"
                    "分值分布比较均匀时铺得最开；极端悬殊时和「按分值比例」差不多。")
        self.lbl_score_mode.setText(
            "当前口径下一屏约出 <b>%d 种颜色</b>（按 %d 人估算）。<br>%s"
            % (uniq, n, warn.replace("\n", "<br>")))

    def _on_palette_picked(self, cur, _prev) -> None:
        if self._loading or cur is None:
            return
        pid = cur.data(Qt.UserRole)
        if not pid:
            return
        self.cfg["wall_palette"] = str(pid)
        self._refresh_style_preview()
        self._fill_palette_values()
        self._on_any_change(rebuild_list=False)

    def _fill_colors_from_current(self) -> None:
        steps = resolve_steps(self.cfg.get("wall_palette"), self.cfg)
        self._loading = True
        try:
            for ed, c in zip(self.ed_colors, steps):
                ed.setText(str(c))
        finally:
            self._loading = False
        self._refresh_style_preview()

    def _fill_palette_values(self) -> None:
        pid = str(self.cfg.get("wall_palette") or DEFAULT_PALETTE_ID)
        name = resolve_palette_name(pid, self.cfg)
        steps = resolve_steps(pid, self.cfg)
        note = ""
        if is_custom_palette_id(pid):
            note = "自定义方案"
        else:
            for p in palettes_all():
                if p["id"] == pid:
                    note = "精选" if p.get("kind") == "curated" else p.get("group") or ""
                    break
        self.lbl_palette.setText("当前：%s（%s）\n色阶：%s"
                                 % (name, note or "内置", " → ".join(steps)))

    # ================================================================ 自定义配色
    def _on_custom_color_edited(self, *_a) -> None:
        if self._loading:
            return
        steps = normalize_steps([e.text() for e in self.ed_colors])
        if steps is None:
            for e in self.ed_colors:
                t = e.text().strip()
                ok = len(t) == 7 and t.startswith("#") and is_hex_color(t)
                e.setStyleSheet("" if ok or not t else "border:1px solid #d33;")
            return
        for e in self.ed_colors:
            e.setStyleSheet("")
        self.preview_palette.set_style(
            steps, float(self.cfg["wall_stroke"]),
            stroke_setting(self.cfg))
        self.lbl_palette.setText("编辑中（未保存）：%s" % " → ".join(steps))

    def _pick_color(self, idx: int) -> None:
        ed = self.ed_colors[idx]
        first = ed.text().strip() if is_hex_color(ed.text().strip()) else "#FFFFFF"
        c = QColorDialog.getColor(QColor(first), self, "选择第 %d 档颜色" % (idx + 1))
        if c.isValid():
            ed.setText(c.name().upper())

    def _save_custom(self) -> None:
        nm = self.ed_name.text().strip()
        if not nm:
            QMessageBox.warning(self, "还差一个方案名", "请先给这套配色起个名字。")
            return
        for bad in ("/", "\\", ":", "*", "?", '"', "<", ">", "|"):
            if bad in nm:
                QMessageBox.warning(self, "方案名里有非法字符",
                                    "方案名不能包含 %s 这类字符（要和设置文件、"
                                    "下拉框兼容）。" % bad)
                return
        steps = normalize_steps([e.text() for e in self.ed_colors])
        if steps is None:
            QMessageBox.warning(self, "色值不合法",
                                "5 档颜色都要填成 #RRGGBB（6 位十六进制），"
                                "例如 #FFD54A。")
            return
        pals = dict(self.cfg.get("wall_palettes") or {})
        if nm in pals:
            r = QMessageBox.question(self, "覆盖同名方案",
                                     "已经有叫「%s」的自定义方案，要用现在的颜色覆盖它吗？" % nm,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        elif len(pals) >= CUSTOM_PALETTE_MAX:
            QMessageBox.warning(self, "自定义方案太多了",
                                "最多存 %d 套，先删掉几套不用的。" % CUSTOM_PALETTE_MAX)
            return
        pals[nm] = list(steps)
        self.cfg["wall_palettes"] = pals
        self.cfg["wall_palette"] = custom_palette_id(nm)
        self._status = "已保存自定义方案「%s」并设为当前配色。" % nm
        self._refresh_status()
        self._fill_palette_list(self.ed_search.text())
        self._fill_palette_values()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    def _del_custom(self) -> None:
        cur = self.lst_palette.currentItem()
        pid = str(cur.data(Qt.UserRole) or "") if cur is not None else ""
        if not is_custom_palette_id(pid):
            QMessageBox.information(self, "没选中自定义方案",
                                    "请先在列表里选中一个「自定义」组里的方案。")
            return
        nm = pid[len("custom:"):]
        r = QMessageBox.question(self, "删除自定义方案",
                                 "确定删除自定义方案「%s」吗？删了不可恢复。" % nm,
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        pals = dict(self.cfg.get("wall_palettes") or {})
        pals.pop(nm, None)
        self.cfg["wall_palettes"] = pals
        if str(self.cfg.get("wall_palette") or "") == pid:
            self.cfg["wall_palette"] = DEFAULT_PALETTE_ID
        self._status = "已删除自定义方案「%s」。" % nm
        self._refresh_status()
        self._fill_palette_list(self.ed_search.text())
        self._fill_palette_values()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    # ================================================================ 描边
    def _on_stroke_changed(self, val: int) -> None:
        if self._loading:
            return
        ratio = max(STROKE_MIN, min(STROKE_MAX, val / 100.0))
        self.cfg["wall_stroke"] = ratio
        self._refresh_stroke_label()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    def _refresh_stroke_label(self) -> None:
        r = float(self.cfg["wall_stroke"])
        # 用大屏上真实出现的字号换算，让用户看到的就是「大屏上多粗」
        px43 = 43 * r
        px60 = 60 * r
        if r <= 0.085:
            hint = "细（推荐）"
        elif r <= 0.12:
            hint = "中"
        else:
            hint = "粗（v2.9.31 旧值档）"
        self.lbl_stroke.setText(
            "系数 %.2f（%s）—— 43px 的字白边约 %.1f 像素，60px 的字约 %.1f 像素。"
            % (r, hint, px43, px60))

    def _refresh_style_preview(self) -> None:
        steps = resolve_steps(self.cfg.get("wall_palette"), self.cfg)
        r = float(self.cfg["wall_stroke"])
        # 传「设置原值」而不是解析后的颜色：选「自动」时要传 "auto"，
        # 由 draw_outlined 按每一档字色各算一个描边色（预览才与看板一致）。
        stroke = stroke_setting(self.cfg)
        self.preview_style.set_style(steps, r, stroke)
        self.preview_palette.set_style(steps, r, stroke)

    # ------------------------------------------------ 描边颜色
    def _stroke_mode(self) -> str:
        """界面当前选的描边模式：white / auto / custom"""
        if self.rb_stroke_auto.isChecked():
            return STROKE_AUTO
        if self.rb_stroke_custom.isChecked():
            return "custom"
        return STROKE_COLOR_DEFAULT

    def _switch_rb(self, rb) -> None:
        """切换单选按钮必须屏蔽信号，否则两个按钮互相触发一圈"""
        for r in (self.rb_stroke_white, self.rb_stroke_auto, self.rb_stroke_custom):
            r.blockSignals(True)
        try:
            rb.setChecked(True)
        finally:
            for r in (self.rb_stroke_white, self.rb_stroke_auto, self.rb_stroke_custom):
                r.blockSignals(False)

    def _refresh_stroke_color_ui(self) -> None:
        """按 cfg 回填单选按钮 / 色值框 / 色块 / 说明文字"""
        raw = str(self.cfg.get("wall_stroke_color") or STROKE_COLOR_DEFAULT)
        is_auto = raw == STROKE_AUTO
        if is_auto:
            self._switch_rb(self.rb_stroke_auto)
        elif raw.upper() == STROKE_COLOR_DEFAULT:
            self._switch_rb(self.rb_stroke_white)
        else:
            self._switch_rb(self.rb_stroke_custom)

        steps = resolve_steps(self.cfg.get("wall_palette"), self.cfg)
        actual = resolve_stroke_color(self.cfg, steps)
        custom = is_auto or raw.upper() == STROKE_COLOR_DEFAULT
        self.ed_stroke_color.setEnabled(not is_auto)
        self.btn_stroke_pick.setEnabled(not is_auto)
        if not custom:
            self.ed_stroke_color.setText(raw.upper())
        elif is_auto:
            self.ed_stroke_color.setText("")
        self.sw_stroke_preview.setStyleSheet(
            "background:%s;border:1px solid #888;" % actual)

        if is_auto:
            txt = ("自动配色：按「%s」的每一档字色**各自**算描边色，"
                   "例如最高分那档 %s 配 %s（黑底对比度 %.1f）。"
                   "换配色时全部自动跟着变。"
                   % (resolve_palette_name(self.cfg.get("wall_palette"), self.cfg),
                      steps[0], actual, contrast_on_black(actual)))
        elif raw.upper() == STROKE_COLOR_DEFAULT:
            txt = "白色描边 #FFFFFF —— 与 v2.9.31 一致，所有配色都能用。"
        else:
            txt = ("自定义描边色 %s（黑底对比度 %.1f）。"
                   "对比度低于 2.0 时描边基本看不见，建议挑亮一点的。"
                   % (actual, contrast_on_black(actual)))
        self.lbl_stroke_color.setText(txt)

    def _on_stroke_color_changed(self, _checked: bool = False) -> None:
        if self._loading:
            return
        mode = self._stroke_mode()
        if mode == STROKE_AUTO:
            self.cfg["wall_stroke_color"] = STROKE_AUTO
        elif mode == STROKE_COLOR_DEFAULT:
            self.cfg["wall_stroke_color"] = STROKE_COLOR_DEFAULT
        else:
            # 切到「自定义」但框里还没值 → 用当前生效色继承，避免一进来就是空白
            cur = str(self.cfg.get("wall_stroke_color") or "")
            txt = self.ed_stroke_color.text().strip()
            got = expand_hex(txt) or expand_hex(cur)
            if not got:
                got = "#B9C4CE"
            self.cfg["wall_stroke_color"] = got
        self._refresh_stroke_color_ui()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    def _on_stroke_color_text(self) -> None:
        if self._loading or self._stroke_mode() == STROKE_AUTO:
            return
        got = expand_hex(self.ed_stroke_color.text())
        if not got:
            self._refresh_stroke_color_ui()      # 非法输入回填上一次合法值
            return
        self.cfg["wall_stroke_color"] = got
        self._refresh_stroke_color_ui()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    def _pick_stroke_color(self) -> None:
        if self._stroke_mode() == STROKE_AUTO:
            return
        cur = QColor(str(self.cfg.get("wall_stroke_color") or STROKE_COLOR_DEFAULT))
        c = QColorDialog.getColor(cur, self, "选择描边颜色")
        if not c.isValid():
            return
        self.cfg["wall_stroke_color"] = c.name().upper()
        self._refresh_stroke_color_ui()
        self._refresh_style_preview()
        self._on_any_change(rebuild_list=False)

    # ================================================================ 窗口页
    def _refresh_geo_label(self) -> None:
        p = self.parent()
        txt = ""
        if p is not None and hasattr(p, "geometry_summary"):
            try:
                txt = str(p.geometry_summary())
            except Exception:       # noqa: BLE001
                txt = ""
        if not txt:
            geo = self.cfg.get("wall_geo") or []
            txt = ("上次记住的尺寸：%d × %d" % (geo[2], geo[3])) if len(geo) == 4 \
                else "还没有记住过窗口尺寸（当前用默认 %d × %d）" % (1100, 720)
        self.lbl_geo.setText(txt)

    def _reset_geometry(self) -> None:
        self.cfg["wall_geo"] = []
        self.cfg["wall_maximized"] = False
        self.cb_max.setChecked(False)
        p = self.parent()
        if p is not None and hasattr(p, "reset_geometry"):
            try:
                p.reset_geometry()
            except Exception:       # noqa: BLE001
                pass
        self._refresh_geo_label()
        self._on_any_change(rebuild_list=False)

    # ================================================================ 收集 / 回调
    def _collect(self) -> Dict:
        cfg = dict(self.cfg)
        picking, names = self._read_table()
        cfg["wall_ips"] = picking
        cfg["wall_names"] = names
        cfg["wall_recent_n"] = int(self.spn_n.value())
        cfg["wall_label_mode"] = str(self.cmb_mode.currentData() or "last")
        cfg["wall_show_cnt"] = bool(self.cb_cnt.isChecked())
        cfg["wall_show_lines"] = bool(self.cb_lines.isChecked())
        cfg["wall_hide_unknown"] = bool(self.cb_unknown.isChecked())
        cfg["wall_stroke"] = max(STROKE_MIN, min(STROKE_MAX,
                                                 self.sld_stroke.value() / 100.0))
        # 描边色：以 cfg 里的值为准（单选按钮 / 色值框的回调都已写进 cfg）；
        # 「自定义」模式下再兜一次色值框，防止用户改了框没触发 editingFinished
        mode = self._stroke_mode()
        if mode == STROKE_AUTO:
            cfg["wall_stroke_color"] = STROKE_AUTO
        elif mode == STROKE_COLOR_DEFAULT:
            cfg["wall_stroke_color"] = STROKE_COLOR_DEFAULT
        else:
            got = expand_hex(self.ed_stroke_color.text()) or expand_hex(
                cfg.get("wall_stroke_color"))
            cfg["wall_stroke_color"] = got or STROKE_COLOR_DEFAULT
        cfg["wall_maximized"] = bool(self.cb_max.isChecked())
        cfg["wall_score_mode"] = str(self.cmb_score_mode.currentData()
                                     or SCORE_MODE_RANK)
        cfg["wall_highlight_first"] = bool(self.cb_hl_first.isChecked())
        return normalize_config(cfg)

    def _on_any_change(self, *_a, rebuild_list: bool = True) -> None:
        if self._loading:
            return
        self.cfg = self._collect()
        if rebuild_list:
            pass
        parent = self.parent()
        cb = getattr(parent, "on_config_changed", None)
        if callable(cb):
            cb(self.cfg)
        self._refresh_note()

    def _refresh_status(self) -> None:
        self.lbl_status.setText(self._status)

    # ================================================================ 恢复默认
    def _reset_page(self, page_key: str) -> None:
        keys = PAGE_KEYS.get(page_key, ())
        dft = default_config()
        for k in keys:
            self.cfg[k] = dft[k]
        self._loading = True
        try:
            if page_key == "data":
                self.spn_n.setValue(int(dft["wall_recent_n"]))
                i = self.cmb_mode.findData(dft["wall_label_mode"])
                self.cmb_mode.setCurrentIndex(i if i >= 0 else 0)
                self.cb_cnt.setChecked(bool(dft["wall_show_cnt"]))
                self.cb_lines.setChecked(bool(dft["wall_show_lines"]))
                self.cb_unknown.setChecked(bool(dft["wall_hide_unknown"]))
                self._fill_table()
            elif page_key == "style":
                self.sld_stroke.setValue(int(round(dft["wall_stroke"] * 100)))
                self._refresh_stroke_label()
                self._refresh_stroke_color_ui()
            elif page_key == "palette":
                i = self.cmb_score_mode.findData(dft["wall_score_mode"])
                self.cmb_score_mode.setCurrentIndex(i if i >= 0 else 0)
                self.cb_hl_first.setChecked(bool(dft["wall_highlight_first"]))
                self._refresh_score_mode_label()
                self._fill_palette_list(self.ed_search.text())
                self._fill_palette_values()
            elif page_key == "window":
                self.cb_max.setChecked(bool(dft["wall_maximized"]))
                self._reset_geometry()
        finally:
            self._loading = False
        self._refresh_style_preview()
        self._status = "已恢复「%s」页的默认设置。" % dict(PAGE_TITLES).get(page_key, page_key)
        self._refresh_status()
        self._on_any_change(rebuild_list=False)

    def _reset_all(self) -> None:
        r = QMessageBox.question(
            self, "全部恢复默认",
            "把所有看板设置恢复成出厂值吗？\n\n"
            "会一起重置：上墙 IP、自定义显示名、最近几手、显示开关、描边粗细、"
            "描边颜色、配色方案、分档方式、第一名高亮、全部自定义配色、窗口尺寸。\n\n"
            "这一步不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        self.cfg = default_config()
        self._loading = True
        try:
            self.spn_n.setValue(int(self.cfg["wall_recent_n"]))
            i = self.cmb_mode.findData(self.cfg["wall_label_mode"])
            self.cmb_mode.setCurrentIndex(i if i >= 0 else 0)
            self.cb_cnt.setChecked(bool(self.cfg["wall_show_cnt"]))
            self.cb_lines.setChecked(bool(self.cfg["wall_show_lines"]))
            self.cb_unknown.setChecked(bool(self.cfg["wall_hide_unknown"]))
            self.cb_max.setChecked(bool(self.cfg["wall_maximized"]))
            _i = self.cmb_score_mode.findData(self.cfg["wall_score_mode"])
            self.cmb_score_mode.setCurrentIndex(_i if _i >= 0 else 0)
            self.cb_hl_first.setChecked(bool(self.cfg["wall_highlight_first"]))
            self._refresh_score_mode_label()
            self.sld_stroke.setValue(int(round(self.cfg["wall_stroke"] * 100)))
            self._refresh_stroke_label()
            self._refresh_stroke_color_ui()
            self.ed_name.setText("")
            for e in self.ed_colors:
                e.setText("")
            self._fill_table()
            self._fill_palette_list(self.ed_search.text())
            self._fill_palette_values()
        finally:
            self._loading = False
        p = self.parent()
        if p is not None and hasattr(p, "reset_geometry"):
            try:
                p.reset_geometry()
            except Exception:       # noqa: BLE001
                pass
        self._refresh_style_preview()
        self._status = "已全部恢复默认。"
        self._refresh_status()
        self._on_any_change(rebuild_list=False)

    # ================================================================ 标签切换
    def _on_tab_changed(self, idx: int) -> None:
        if idx == 1:
            self._refresh_stroke_label()
            self._refresh_stroke_color_ui()
            self._refresh_style_preview()
        elif idx == 2:
            _i = self.cmb_score_mode.findData(self.cfg.get("wall_score_mode"))
            self.cmb_score_mode.setCurrentIndex(_i if _i >= 0 else 0)
            self.cb_hl_first.setChecked(bool(self.cfg.get("wall_highlight_first", True)))
            self._refresh_score_mode_label()
            self._fill_palette_values()
            self._refresh_style_preview()
        elif idx == 3:
            self._refresh_geo_label()


def _curated_meta():
    """精选方案的 (id, 名字, 说明) 三元组（配色模块缺失时返回兜底一条）"""
    out = []
    for p in palettes_all():
        if p.get("kind") == "curated":
            out.append((p["id"], p["name"], p.get("note") or ""))
    return out


def _curated_ids():
    return [t[0] for t in _curated_meta()]
