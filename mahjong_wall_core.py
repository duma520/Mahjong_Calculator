# -*- coding: utf-8 -*-
"""大屏看板的「底层」：设置键、视觉常量、标签生成、绘制基元。

为什么要拆成两个文件（项目规矩：单文件不超过 1000 行）
    mahjong_wall.py 三个类加起来 1100+ 行，超了。按「有没有 QWidget」拆最自然：
      · 本文件 = 不依赖窗口的逻辑与绘制积木（纯函数 + 缓存 + 字体 + 描边）
      · mahjong_wall.py = 三个窗口类（画布 / 上墙设置 / 看板窗口）
    对外接口**一个都没变**：mahjong_wall.py 把这里的一切原样 re-export，
    主程序仍然 `from mahjong_wall import WallBoardDialog, default_config, ...`。

★ 与主程序的数据契约（不变）：本模块不碰数据库，只收 List[dict]。
"""
import time
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QFontMetricsF,
                           QPainter, QPainterPath, QPen, QPixmap)

# ---------------------------------------------------------------- 设置键（存 mahjong_settings.json）
# ★ 新增设置项必须三处成对实现（见主程序 docstring「设置持久化」）：
#   _collect_settings() 收集 + _apply_settings() 应用 + 这里的默认值
SETTING_KEYS = (
    # 数据（📊）
    "wall_ips", "wall_names", "wall_recent_n", "wall_label_mode",
    "wall_show_lines", "wall_hide_unknown", "wall_show_cnt",
    # 外观（🎨）
    "wall_stroke", "wall_stroke_color",
    # 配色（🌈）
    "wall_palette", "wall_palettes", "wall_score_mode", "wall_highlight_first",
    # 窗口（🪟）
    "wall_geo", "wall_maximized",
)

# 描边系数：白边宽度 = 字号 × 系数。
# ★ v2.9.32 起默认 0.08（用户反馈「太粗，细一点」）。原值 0.14 在 43px 字上
#   是 6.02px，粗到笔画糊在一起；0.08 是 3.44px，远看仍清晰、近看不发肿。
STROKE_MIN = 0.02
STROKE_MAX = 0.20
STROKE_DEFAULT = 0.08

# 描边颜色：默认纯白（v2.9.31 行为），可选 "auto" 自动配色，或任意 #RRGGBB
# ★ v2.9.32 新增。用户原话：「有些颜色用白色描边就是不怎么好，希望在不同颜色的时候
#   能使用更适合的描边颜色」——白边在亮色字周围会糊出一圈光晕，在暗色字周围又必须
#   靠它把字从纯黑里托出来，所以「合适」取决于这一屏字的明暗。
STROKE_COLOR_DEFAULT = "#FFFFFF"
STROKE_AUTO = "auto"
# ── 「自动描边」的判据阈值（全部用 Lab 色差 / 黑底对比度，不用 WCAG 亮度比）──
# 白边与字色的 ΔE 达到这个值 → 白边本来就分得开，保持白色，不要动
AUTO_STROKE_DE_WHITE = 40.0
# 换出来的描边色与字色的 ΔE 至少要这么大，否则等于没描
AUTO_STROKE_DE_MIN = 30.0
# 换出来的描边色自己在黑底上的对比度下限（大屏是纯黑底，暗边等于没描边）
AUTO_STROKE_BLACK_MIN = 3.5
# ↓ 旧版「整屏一个描边色」用的阈值，算法已被 auto_stroke_for_fill 取代，
#   这两个函数（auto_stroke_for / auto_stroke_for_v2）只留给探针对比，不参与绘制。
AUTO_STROKE_DIM_BELOW = 6.0


# ── 分档方式（v2.9.33 新增）──
# 五档色阶怎么分配给一列分数，有三种口径：
#   rank   —— 按名次分档：第 1 名最高档、最后一名最低档，中间按名次线性铺开（默认）
#   ratio  —— 按「占最高分多少」分档（v2.9.31/32 的原有行为）
#   golden —— 阈值按黄金比例 φ 衰减（1, φ, φ², φ³, φ⁴），分布均匀时铺得更开
# ★ 为什么默认改成 rank：麻将一桌最多 4 人（国标规则）。实测 4 人场景下
#   ratio 在「均势 [900,800,700,600]」和「极端独大 [8000,200,150,100]」都只出
#   2 种颜色（两两同色 / 后三名同色），而 rank 稳定 4 种色、每人一色。
#   10 人一家独大时差距更明显：ratio 2 种 vs rank 5 种。
# ★ rank 的代价（必须在设置页写明）：它表达的是「名次」，不是「分差」——
#   第 2 名 800 番和第 3 名 700 番只差 100 番，颜色也会拉开一档。
#   想让颜色反映真实分差，就切回 ratio。
SCORE_MODE_RATIO = "ratio"
SCORE_MODE_RANK = "rank"
SCORE_MODE_GOLDEN = "golden"
SCORE_MODES = (SCORE_MODE_RATIO, SCORE_MODE_RANK, SCORE_MODE_GOLDEN)
SCORE_MODE_ITEMS = (
    ("rank", "按名次铺开（默认；4 人各一色，最好认）"),
    ("ratio", "按分值比例（老口径；差距悬殊时只出 2 种色）"),
    ("golden", "黄金比例衰减（分值分布均匀时更平滑）"),
)

# 黄金比例衰减阈值：φ⁰=1.0、φ¹≈0.618、φ²≈0.382、φ³≈0.236、φ⁴≈0.146
_PHI = 0.6180339887498949
GOLDEN_THRESHOLDS = tuple(round(_PHI ** i, 4) for i in range(5))


# 自定义配色方案上限（防止设置文件被塞爆，每帧要遍历）
CUSTOM_PALETTE_MAX = 60
CUSTOM_NAME_MAX = 24

# 看板窗口默认尺寸与最小尺寸（几何持久化的兜底基准）
DEFAULT_GEO_SIZE = (1100, 720)
MIN_GEO_SIZE = (420, 320)

_GEOMETRY_PENDING = None   # 占位（保持文件结构清晰，无逻辑含义）


def default_config() -> Dict:
    """看板设置的默认值（老设置里没有这些键时就用它，行为不变）"""
    return {
        "wall_ips": [],            # [] = 当天有几个 IP 就上几个；填了就只上这几个
        "wall_names": {},          # {"192.168.1.20": "2-10"} 自定义显示名，优先于一切
        "wall_recent_n": 10,       # 下半显示最近几手（1~50）
        "wall_label_mode": "last",  # last=只显示末位段（默认）/ full=完整 IP
        "wall_show_lines": True,   # 行间极淡分隔线
        "wall_hide_unknown": False,  # 是否隐藏「(未记录IP)」那一行
        "wall_show_cnt": True,     # 上半是否显示「次数」列
        "wall_stroke": STROKE_DEFAULT,   # 描边系数（0.02~0.20）
        "wall_stroke_color": STROKE_COLOR_DEFAULT,  # 描边颜色；"auto"=按配色自动
        "wall_palette": DEFAULT_PALETTE_ID,  # 当前配色方案 id（内置 id 或 custom:名字）
        "wall_palettes": {},       # 自定义配色 {"我的方案": [5 个 #RRGGBB]}
        "wall_score_mode": SCORE_MODE_RANK,  # 分档方式：rank(默认) / ratio / golden
        "wall_highlight_first": True,  # 第一名整行反色高亮（底色铺满、字改黑）
        "wall_geo": [],            # [x, y, w, h]；[] = 用默认尺寸、由 Qt 摆位
        "wall_maximized": False,   # 上次是否最大化
    }


def normalize_config(cfg: Optional[Dict]) -> Dict:
    """把外部传进来的设置规整成**一定可用**的 dict（脏数据不抛异常，一律回默认）"""
    out = default_config()
    if not isinstance(cfg, dict):
        return out
    ips = cfg.get("wall_ips")
    if isinstance(ips, (list, tuple)):
        out["wall_ips"] = [str(x) for x in ips if str(x or "").strip()]
    names = cfg.get("wall_names")
    if isinstance(names, dict):
        out["wall_names"] = {str(k): str(v) for k, v in names.items()
                             if str(k or "").strip() and str(v or "").strip()}
    try:
        out["wall_recent_n"] = max(1, min(50, int(cfg.get("wall_recent_n", 10))))
    except Exception:       # noqa: BLE001
        pass
    mode = str(cfg.get("wall_label_mode") or "last")
    out["wall_label_mode"] = mode if mode in ("last", "full") else "last"
    for k in ("wall_show_lines", "wall_hide_unknown", "wall_show_cnt",
              "wall_maximized", "wall_highlight_first"):
        # ★ 必须判 None：主程序启动时传的是 {k: s.get(k) for k in SETTING_KEYS}，
        #   老设置文件里没这些键 → 键存在但值是 None，`if k in cfg` 会当成
        #   「用户明确关掉了」，bool(None)=False 把「次数列/分隔线」全关掉。
        v = cfg.get(k)
        if v is not None:
            out[k] = bool(v)
    # 描边系数
    v = cfg.get("wall_stroke")
    if v is not None:
        try:
            out["wall_stroke"] = max(STROKE_MIN, min(STROKE_MAX, float(v)))
        except Exception:   # noqa: BLE001
            pass
    # 描边颜色："auto" 或 #RRGGBB；其它一律回纯白
    sc = cfg.get("wall_stroke_color")
    if sc is not None:
        s = str(sc or "").strip()
        if s.lower() == STROKE_AUTO:
            out["wall_stroke_color"] = STROKE_AUTO
        else:
            got = expand_hex(s)
            if got:
                out["wall_stroke_color"] = got
    # 配色方案 id
    pid = cfg.get("wall_palette")
    if pid is not None:
        s = str(pid or "").strip()
        out["wall_palette"] = s or DEFAULT_PALETTE_ID
    # 分档方式：只认三个合法值，脏数据回默认（不能因为设置文件被改坏就画不出）
    sm = cfg.get("wall_score_mode")
    if sm is not None:
        s = str(sm or "").strip().lower()
        out["wall_score_mode"] = s if s in SCORE_MODES else SCORE_MODE_RANK
    # 自定义配色：名字做长度限制、色值做格式校验、总数设上限
    pals = cfg.get("wall_palettes")
    if isinstance(pals, dict):
        clean: Dict[str, List[str]] = {}
        for k, v in pals.items():
            nm = str(k or "").strip()[:CUSTOM_NAME_MAX]
            steps = normalize_steps(v)
            if nm and steps:
                clean[nm] = list(steps)
            if len(clean) >= CUSTOM_PALETTE_MAX:
                break
        out["wall_palettes"] = clean
    # 窗口几何
    geo = cfg.get("wall_geo")
    if isinstance(geo, (list, tuple)) and len(geo) == 4:
        try:
            out["wall_geo"] = [int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3])]
        except Exception:   # noqa: BLE001
            pass
    return out


# ---------------------------------------------------------------- 配色方案
# 内置方案库放 mahjong_wall_palettes.py（生成产物，240 套）。
# 这里做一层**容错包装**：配色模块万一缺失/损坏，看板仍能用默认配色画出来，
# 不能因为「配色文件读不到」就把整个大屏功能炸掉。
DEFAULT_PALETTE_ID = "classic"

try:                                            # pragma: no cover
    from mahjong_wall_palettes import (
        ALL_IDS as PALETTE_IDS, CURATED as PALETTE_CURATED,
        DEFAULT_PALETTE as DEFAULT_PALETTE_ID_INNER,
        all_palettes as palettes_all, get_palette as palette_get,
        groups as palette_groups, palette_name as palette_name_of,
        steps_of as palette_steps_of,
    )
    DEFAULT_PALETTE_ID = DEFAULT_PALETTE_ID_INNER
    PALETTE_IMPORT_ERROR = ""
except Exception as _exc:                       # noqa: BLE001  pragma: no cover
    PALETTE_IMPORT_ERROR = repr(_exc)
    PALETTE_IDS = ("classic",)
    PALETTE_CURATED = (("classic", "经典（默认）", "配色模块缺失，使用内置兜底色阶",
                        ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8")),)

    def palettes_all():                          # noqa: D103
        return [{"id": "classic", "name": "经典（默认）", "note": "",
                 "steps": ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8"),
                 "group": "", "kind": "curated"}]

    def palette_get(pid, fallback="classic"):    # noqa: D103
        return palettes_all()[0]

    def palette_steps_of(pid, fallback="classic"):   # noqa: D103
        return palettes_all()[0]["steps"]

    def palette_name_of(pid):                    # noqa: D103
        return "经典（默认）"

    def palette_groups():                        # noqa: D103
        return []


_HEX_OK = set("0123456789ABCDEFabcdef")


def is_hex_color(v) -> bool:
    """`#RRGGBB` 校验（只认 6 位，短写 #FFF 一律当非法，避免歧义）"""
    s = str(v or "").strip()
    if len(s) != 7 or s[0] != "#":
        return False
    return all(c in _HEX_OK for c in s[1:])


def expand_hex(v) -> Optional[str]:
    """把用户可能手填的 `#FFF` / `#ffffff` / `ffffff` 规整成 `#FFFFFF`

    不合法返回 None（不猜、不补）。界面允许简写，是因为取色器面板上常有
    3 位写法，用户在输入框里手打时也会这么打，直接判非法体验很差。
    """
    s = str(v or "").strip()
    if not s:
        return None
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:
        s = "#" + s[1] * 2 + s[2] * 2 + s[3] * 2
    if not is_hex_color(s):
        return None
    return s.upper()


def normalize_steps(v) -> Optional[Tuple[str, ...]]:
    """把外部传的 5 个色值规整成大写 hex；不合法返回 None（不猜、不补）"""
    if not isinstance(v, (list, tuple)) or len(v) != 5:
        return None
    out = []
    for c in v:
        s = str(c or "").strip()
        if not s.startswith("#"):
            s = "#" + s
        if not is_hex_color(s):
            return None
        out.append(s.upper())
    return tuple(out)


def custom_palette_id(name: str) -> str:
    return "custom:" + str(name or "").strip()


def is_custom_palette_id(pid: str) -> bool:
    return str(pid or "").startswith("custom:")


def resolve_steps(pid: str, cfg: Optional[Dict] = None) -> Tuple[str, ...]:
    """把「当前方案 id」解析成 5 档色阶

    优先级：自定义方案（custom:名字）> 内置方案 > 默认方案。
    ★ 自定义方案找不到时**静默回退内置默认**，不抛异常 —— 用户删了方案、
      或设置文件被手改坏，看板必须照常出图。
    """
    pid = str(pid or "").strip()
    if is_custom_palette_id(pid):
        nm = pid[len("custom:"):].strip()
        pals = (cfg or {}).get("wall_palettes") if isinstance(cfg, dict) else None
        if isinstance(pals, dict):
            steps = normalize_steps(pals.get(nm))
            if steps:
                return steps
        return palette_steps_of(DEFAULT_PALETTE_ID)
    return palette_steps_of(pid)


def resolve_palette_name(pid: str, cfg: Optional[Dict] = None) -> str:
    """给界面显示用的人类可读名字"""
    pid = str(pid or "").strip()
    if is_custom_palette_id(pid):
        return "自定义：" + pid[len("custom:"):].strip()
    return palette_name_of(pid)


# ---------------------------------------------------------------- 颜色计算
def hex_to_rgb(color: str) -> Optional[Tuple[int, int, int]]:
    """`#RRGGBB`（也接受 `#FFF` / 无 #）→ (r,g,b)；非法返回 None（不猜）"""
    s = expand_hex(color)
    if not s:
        return None
    return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """(0~255) → `#RRGGBB`（越界自动夹紧，不抛异常）"""
    def _q(v):
        return max(0, min(255, int(round(float(v)))))
    return "#%02X%02X%02X" % (_q(r), _q(g), _q(b))


def _luminance(color: str) -> float:
    """WCAG 相对亮度（0~1）；非法色返回 0.0（等于纯黑，最坏情况）"""
    rgb = hex_to_rgb(color)
    if not rgb:
        return 0.0

    def _lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_on_black(color: str) -> float:
    """该颜色在纯黑底上的对比度（1~21）；大屏是纯黑底，只有这一个背景要算"""
    return (_luminance(color) + 0.05) / 0.05


def _mix(color: str, other: str, t: float) -> str:
    """把 color 朝 other 混 t（0~1）"""
    a = hex_to_rgb(color)
    b = hex_to_rgb(other)
    if not a or not b:
        return str(color or STROKE_COLOR_DEFAULT)
    t = max(0.0, min(1.0, float(t)))
    return rgb_to_hex(a[0] + (b[0] - a[0]) * t,
                      a[1] + (b[1] - a[1]) * t,
                      a[2] + (b[2] - a[2]) * t)


def auto_stroke_for(steps, ratio: float = STROKE_DEFAULT) -> str:
    """按配色算出「更合适的描边色」（wall_stroke_color == "auto" 时用）

    怎么定的（两个方向，都不是拍脑袋，见 _scaffold/_stroke_auto_probe.py 的实测）：
      ① 整份配色**偏暗**（最暗那档黑底对比度 < AUTO_STROKE_DIM_BELOW）：
         白边是唯一的救命绳，必须留亮。但不能用纯白 —— 亮色字上纯白边会在
         深色底上糊出一圈光晕，把笔画吃细。所以取「整份配色的平均色提亮」，
         保持同一色相家族，白边变成「同色系亮边」，亮字仍透、暗字仍托得住。
      ② 整份配色**够亮**（暗档也够显眼）：
         这时白边是纯负担（亮色 + 白边 = 光晕、笔画发胖）。改用「平均色压暗」，
         描边变成比字色深一档的同色暗边，起到「勾轮廓」的作用，不抢字。
      ③ 描边太粗时（用户调到 > 0.12）再把结果往中性灰收一点，
         粗边如果还是高饱和，会像彩虹描边；中性一点更稳。
      ④ 任何情况下都保证描边与黑底对比度 >= 3.0，否则「描边看不见，
         等于没描」，宁可变白。
    """
    seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
    # 平均色（5 档等权；大屏上五档都会出现，不能只看榜首）
    rs = gs = bs = 0.0
    for c in seq:
        rgb = hex_to_rgb(c)
        if not rgb:
            continue
        rs += rgb[0]
        gs += rgb[1]
        bs += rgb[2]
    avg = rgb_to_hex(rs / 5.0, gs / 5.0, bs / 5.0)
    dimmest = min(contrast_on_black(c) for c in seq)
    if dimmest < AUTO_STROKE_DIM_BELOW:
        # 偏暗：往亮里提，但别到纯白（0.55 混白 → 同色系亮边）
        out = _mix(avg, "#FFFFFF", 0.55)
    else:
        # 够亮：往暗里压（0.45 混黑 → 同色系暗边），勾轮廓不抢字
        out = _mix(avg, "#000000", 0.45)
    if float(ratio) > 0.12:
        out = _mix(out, "#B9C4CE", 0.35)     # 粗边收一点饱和度，避免彩虹边
    if contrast_on_black(out) < 3.0:
        out = "#FFFFFF"                      # 保不住可见度就退回白色
    return out


def auto_stroke_for_v2(steps, ratio: float = STROKE_DEFAULT):
    """在候选色里打分选优（返回 (颜色, (区分度, 黑底对比度))）"""
    seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
    best = None
    for cand in stroke_candidates(seq):
        bg = contrast_on_black(cand)
        if bg < 3.2:
            continue
        sep = min(_contrast_pair(f, cand) for f in seq)
        if best is None or sep > best[1][0]:
            best = (cand, (sep, bg))
    if best is None:
        return STROKE_COLOR_DEFAULT, (0.0, contrast_on_black(STROKE_COLOR_DEFAULT))
    return best


def _contrast_pair(a: str, b: str) -> float:
    """两色之间的 WCAG 对比度（1~21）"""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _hsl_of(color: str):
    """`#RRGGBB` → (h, s, l)，h/s/l 都是 0~1；非法返回 None"""
    rgb = hex_to_rgb(color)
    if not rgb:
        return None
    r, g, b = (v / 255.0 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return (0.0, 0.0, l)
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d) % 6.0
    elif mx == g:
        h = (b - r) / d + 2.0
    else:
        h = (r - g) / d + 4.0
    return (h / 6.0, s, l)


def _hsl_hex(h: float, s: float, l: float) -> str:
    """(h,s,l) 都是 0~1 → `#RRGGBB`"""
    h = float(h) % 1.0
    s = max(0.0, min(1.0, float(s)))
    l = max(0.0, min(1.0, float(l)))
    if s <= 0.0:
        v = int(round(l * 255))
        return "#%02X%02X%02X" % (v, v, v)
    q = l * (1.0 + s) if l < 0.5 else l + s - l * s
    p = 2.0 * l - q

    def _c(t):
        t = t % 1.0
        if t < 1.0 / 6.0:
            return p + (q - p) * 6.0 * t
        if t < 0.5:
            return q
        if t < 2.0 / 3.0:
            return p + (q - p) * (2.0 / 3.0 - t) * 6.0
        return p
    return "#%02X%02X%02X" % (int(round(_c(h + 1.0 / 3.0) * 255)),
                              int(round(_c(h) * 255)),
                              int(round(_c(h - 1.0 / 3.0) * 255)))


# 「自动描边」的结果缓存：key = 大写色值，value = 描边色。
# auto_stroke_for_fill 是纯函数（只看 fill），缓存绝对安全；
# 不缓存实测一帧 60 段文字要 36ms，等于把 v2.9.31 的性能优化全部白做。
# 上限取 512：一屏最多 5 档 + 表头/标题/次要字 3 个，240 套配色全换一遍也到不了。
_AUTO_STROKE_CACHE: Dict[str, str] = {}
_AUTO_STROKE_CACHE_MAX = 512


def auto_stroke_for_fill(fill: str) -> str:
    """给**某一个字色**算它自己的描边色（按色相派生，不是整份配色一个色）

    为什么按字色而不是整份配色取一个
        大屏上一屏里五档色都在。若全屏只用一个描边色，必然有某一档与描边
        太接近（实测 candy 的最后两档接近白，白描边等于没描）。按每个字色
        各自算，才能保证「每一档都有轮廓」。

    怎么定（针对纯黑底）
        · 字色本身够亮（黑底对比度 >= 4.5）：描边往**同色相的暗侧**走，
          起到收边、勾轮廓的作用；但不能暗到融进黑底，黑底对比度保 >= 2.6。
        · 字色偏暗：描边往**同色相的亮侧**走，把字从黑底里托出来。
        · 色相保持不变、饱和度略降（0.85），避免出现彩虹感描边。
        · ★ 硬约束：算出来的色与字色的区分度必须**严格优于白边**，否则退回白色。
          这条不能省 —— 实测 lava 那套暗红字，自动算出的暗红边区分度只有 2.26，
          而白边是 5.99，用了自动反而更难认。「自动」的底线是「不比白边差」，
          不是「换个颜色」。
        · 找不到满足条件的就退回白色（白边最保险，至少看得见）。

    ★ 结果缓存：本函数只依赖 fill 一个输入，纯函数，缓存绝对安全。
      不缓存的话实测一帧画 60 段文字要 36ms（每次探测最多 34 轮 × 每轮
      几次 WCAG 亮度换算），会把「按字色各算」这个正确做法拖成性能灾难。
      key 用大写色值；配色方案在界面里点点换换也不会超过几百条。
    """
    key = str(fill or "").strip().upper()
    hit = _AUTO_STROKE_CACHE.get(key)
    if hit is not None:
        return hit
    got = _auto_stroke_for_fill_uncached(key)
    if len(_AUTO_STROKE_CACHE) >= _AUTO_STROKE_CACHE_MAX:
        _AUTO_STROKE_CACHE.clear()
    _AUTO_STROKE_CACHE[key] = got
    return got


def _srgb_to_lab(color: str):
    """#RRGGBB -> CIELAB（D65）。算色差用，算不了返回 None

    为什么要 Lab 而不是直接比 WCAG 对比度
        WCAG 对比度只吃**亮度**。两个都接近白的颜色（比如 #E8F0F8 与 #FFFFFF）
        亮度几乎一样，算出来的对比度是 1.15 —— 看着像「分得开」，其实人眼看到
        的是「同样一坨亮」，白描边糊在字上完全看不出轮廓。
        Lab 的 ΔE 把色相/彩度也算进去，#E8F0F8 与白的 ΔE 只有 7.4，这才是
        「白边等于没描」的真实数字。反过来 #FFD54A 与白 ΔE 高达 71.9，白边
        清清楚楚 —— 旧判据却把它判成「需要换色」，这是全部错误的来源。
    """
    rgb = hex_to_rgb(color)
    if not rgb:
        return None
    ch = []
    for v in rgb:
        u = v / 255.0
        ch.append(((u + 0.055) / 1.055) ** 2.4 if u > 0.04045 else u / 12.92)
    r, g, b = ch
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883
    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0
    fx, fy, fz = _f(x), _f(y), _f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _delta_e(a: str, b: str) -> float:
    """两色的 Lab 色差（CIE76）。算不了返回 0.0"""
    la = _srgb_to_lab(a)
    lb = _srgb_to_lab(b)
    if not la or not lb:
        return 0.0
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5


def _auto_stroke_for_fill_uncached(fill: str) -> str:
    """真正的算法：**只在白边确实分不开时才换色**，且换出的色必须同色相、黑底可见

    三道门（按顺序，任一不过就退回白色）：
      ① 白边够不够用：`_delta_e(fill, 白) >= AUTO_STROKE_DE_WHITE` 就保持白色。
         这是本函数的**主开关**。大多数配色（实测 240 套里 205 套）白边本来就
         好看，不该被动。只有「近白字」才真正需要自动。
      ② 换出来的色与字色要分得开：`_delta_e(fill, cand) >= AUTO_STROKE_DE_MIN`。
      ③ 换出来的色自己要在黑底上看得见：`contrast_on_black(cand) >= AUTO_STROKE_BLACK_MIN`。
         这条不能省 —— 早期版本漏了它，把亮金字配了暗绿边，远看等于没描边，
         字反而比白边更细。
    取色方向：同色相、每次压暗 0.07 明度、最多 15 步（`s*0.95` 保住色相家族）。
    绝不跨色相（早期试过「最大化 ΔE」，会把 mono 推成紫色、cream 推成红色，
    大屏上看着像描错了色）。
    """
    hsl = _hsl_of(fill)
    if not hsl:
        return STROKE_COLOR_DEFAULT
    h, s, l = hsl
    # ① 白边本来就分得开 → 白边就是最合适的，不要动
    if _delta_e(fill, STROKE_COLOR_DEFAULT) >= AUTO_STROKE_DE_WHITE:
        return STROKE_COLOR_DEFAULT
    # ②③ 近白字：同色相压暗，直到既分得开又在黑底看得见
    for step in range(1, 16):
        nl = l - 0.07 * step
        if nl < 0.0:
            break
        cand = _hsl_hex(h, min(1.0, s * 0.95), nl)
        if (contrast_on_black(cand) >= AUTO_STROKE_BLACK_MIN
                and _delta_e(fill, cand) >= AUTO_STROKE_DE_MIN):
            return cand
    return STROKE_COLOR_DEFAULT



def stroke_candidates(steps) -> Tuple[str, ...]:
    """候选描边色：白 / 黑 / 同色相多档明度×多档饱和度 / 中性灰阶"""
    seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
    hs, ss = [], []
    for c in seq:
        hsl = _hsl_of(c)
        if hsl:
            hs.append(hsl[0])
            ss.append(hsl[1])
    out = ["#FFFFFF", "#000000"]
    if hs:
        # 色相取圆周平均（红色跨 0/1 时直接算术平均会跑偏，用向量平均）
        import math
        ang = [x * 2.0 * math.pi for x in hs]
        h0 = (math.atan2(sum(math.sin(a) for a in ang),
                         sum(math.cos(a) for a in ang)) / (2.0 * math.pi)) % 1.0
        s0 = sum(ss) / len(ss)
        for li in range(8, 97, 4):
            for sf in (0.0, 0.3, 0.6, 1.0):
                out.append(_hsl_hex(h0, s0 * sf, li / 100.0))
    for li in range(10, 91, 8):
        out.append(_hsl_hex(0.0, 0.0, li / 100.0))
    return tuple(dict.fromkeys(out))


def stroke_setting(cfg: Optional[Dict]) -> str:
    """取「描边设置」原值：`"auto"` 或 `#RRGGBB`

    ★ 和 resolve_stroke_color() 的区别：
      · resolve_stroke_color() 永远给你一个**具体颜色**（界面色块、对比度显示要用它）
      · stroke_setting() 可能返回 `"auto"` 这个标记 —— 真正的颜色要等知道
        「这一笔是哪个字色」时才算得出来（见 auto_stroke_for_fill）。
      绘制链路必须用这个，否则「自动」会退化成整屏一个颜色，
      而实测整屏一色必然有某一档字与描边撞色（见 _stroke_plan_probe.py）。
    """
    c = cfg if isinstance(cfg, dict) else {}
    raw = str(c.get("wall_stroke_color") or "").strip()
    if raw.lower() == STROKE_AUTO:
        return STROKE_AUTO
    if is_hex_color(raw):
        return raw.upper()
    return expand_hex(raw) or STROKE_COLOR_DEFAULT


def resolve_stroke_color(cfg: Optional[Dict], steps=None) -> str:
    """把 `wall_stroke_color` 解析成一个**具体颜色**（UI 色块 / 对比度提示用）

    非 auto：直接就是那个色。
    auto：返回「最高分那档」字色对应的描边色，仅作代表色展示；
          实际绘制是每档字色各自算一个（见 auto_stroke_for_fill / stroke_setting）。
    """
    c = cfg if isinstance(cfg, dict) else {}
    raw = str(c.get("wall_stroke_color") or "").strip()
    if raw.lower() == STROKE_AUTO:
        if steps is None:
            steps = resolve_steps(c.get("wall_palette"), c)
        seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
        try:
            return auto_stroke_for_fill(seq[0])
        except Exception:       # noqa: BLE001
            return STROKE_COLOR_DEFAULT
    if is_hex_color(raw):
        return raw.upper()
    got = expand_hex(raw)
    return got or STROKE_COLOR_DEFAULT


# ---------------------------------------------------------------- 视觉常量
BG = "#000000"                 # 纯黑底（用户指定）
STROKE = "#FFFFFF"             # 白色描边（用户指定：不描边色差小就看不清）
TITLE_COLOR = "#35E1FF"        # 标题：亮青
HEAD_COLOR = "#7FE9FF"         # 表头：浅亮青
LINE_COLOR = QColor(255, 255, 255, 30)     # 表头 / 分区线（约 12% 白）
ROW_LINE_COLOR = QColor(255, 255, 255, 22)  # 行间极淡分隔线
MUTED = "#8FA3B5"              # 「暂无记录」这类提示字，故意压暗
UNKNOWN_IP_TEXT = "(未记录IP)"

# 分数色阶：从「当天最高分」往下归一化取色。
# ★ 刻意不用红 / 橙做主色 —— 用户此前明确否决过红橙系（在深底上对比度不够）。
# ★ v2.9.32 起这 5 档只是**默认方案的兜底副本**，实际绘制用 resolve_steps()，
#   颜色来自当前选中的配色方案（内置 240 套或用户自定义）。
SCORE_STEPS = (
    (0.80, "#FFD54A"),   # 亮金   —— 榜首
    (0.55, "#FFE97A"),   # 亮黄
    (0.30, "#6BFF9E"),   # 亮绿
    (0.10, "#35E1FF"),   # 亮青
    (0.00, "#E8F0F8"),   # 灰白   —— 最低
)

DEFAULT_STEPS = ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8")

# 色阶阈值（与 SCORE_STEPS 的第一列一致，只保留一份，避免两处不同步）
SCORE_THRESHOLDS = (0.80, 0.55, 0.30, 0.10, 0.00)

# 中文字体优先级：只用**免费可商用**的（项目规矩禁微软雅黑 / 苹方 / 方正 / 汉仪）
FONT_CANDIDATES = ("HarmonyOS Sans SC", "Noto Sans SC", "Source Han Sans SC",
                   "Alibaba PuHuiTi", "DengXian", "SimHei")

LABEL_MODE_ITEMS = (("last", "只显示末位段（默认，如 100）"),
                    ("full", "显示完整 IP（如 192.168.1.100）"))


def _to_float(v) -> Optional[float]:
    """尽力把值转成数字；转不了返回 None（脏数据不抛异常）"""
    try:
        return float(v)
    except Exception:       # noqa: BLE001
        return None


def _color_by_ratio(x: float, top: float, seq, thresholds) -> str:
    """按「占最高分多少」在给定阈值表里取档"""
    if top <= 0:
        return seq[-1]
    ratio = x / top
    for th, col in zip(thresholds, seq):
        if ratio >= th:
            return col
    return seq[-1]


def assign_colors(values, steps=None, mode: str = SCORE_MODE_RANK) -> List[str]:
    """给一列分值**整体**分配色阶颜色，返回同序的颜色列表。

    ★ 为什么要「整列一起算」而不是逐个调 score_color：
      rank 口径必须看到整列才知道谁是第几名，逐个算做不到。
      而 ratio / golden 口径虽然逐个可算，也统一走这里，避免两套代码分叉。

    mode：
      rank   —— 按**名次**分档：第 1 名最高档、最后一名最低档，中间线性铺开（默认）
      ratio  —— 占最高分的比例分档（v2.9.31/32 的老口径）
      golden —— 同上，但阈值换成 φ 衰减（1, 0.618, 0.382, 0.236, 0.146）

    ★ rank 口径的两个刻意选择：
      1. **相同分数给相同颜色** —— 按「唯一值」排名次，不按行排名次。
         否则 10 个 IP 里有 5 个同分，会因为排序不稳定而出现「同分不同色」，
         用户一眼就会看出来是错的。
      2. 只有 1 个唯一值时全部用最高档（只有一名，谈不上分档）。
    """
    seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
    try:
        vals = list(values)
    except Exception:       # noqa: BLE001
        return []
    nums = [_to_float(v) for v in vals]
    # 转不出数字的按「最低」处理（不能因为一个脏值毁掉整屏配色）
    clean = [x if x is not None else -1.0 for x in nums]
    n = len(clean)
    if n == 0:
        return []
    try:
        top = max(clean)
    except Exception:       # noqa: BLE001
        top = 0.0

    m = str(mode or SCORE_MODE_RANK).strip().lower()
    if m == SCORE_MODE_RANK:
        # ★ 全是 0 分（或全是同一个值且该值 <=0）时不能给最高档：
        #   一分没得的那一屏，全员标成金色「榜首」是明显的错。
        if top <= 0:
            return [seq[-1]] * n
        # 唯一值降序 → 建立「值 → 名次比」映射；名次比 1.0 = 第 1 名，0.0 = 最后一名
        uniq = sorted(set(clean), reverse=True)
        k = len(uniq)
        rank_ratio: Dict[float, float] = {}
        for i, u in enumerate(uniq):
            rank_ratio[u] = 1.0 if k <= 1 else 1.0 - (i / float(k - 1))
        return [_color_by_ratio(rank_ratio.get(x, 0.0), 1.0, seq, SCORE_THRESHOLDS)
                for x in clean]

    thresholds = GOLDEN_THRESHOLDS if m == SCORE_MODE_GOLDEN else SCORE_THRESHOLDS
    return [_color_by_ratio(x, top, seq, thresholds) for x in clean]


def score_color(score: int, top: int, steps=None) -> str:
    """按「占最高分多少」取色（top<=0 时一律用最低档，避免除零）

    steps 传当前配色方案的 5 档色阶；不传就退回内置默认色阶。

    ★ v2.9.33 起绘制不再逐个调它 —— 改用 assign_colors() 整列分配（支持名次分档）。
      这个函数保留给「只有一个值要看」的场合（设置页色块、探针）。
    """
    seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
    x = _to_float(score)
    t = _to_float(top)
    if x is None or t is None:
        return seq[-1]
    return _color_by_ratio(x, t, seq, SCORE_THRESHOLDS)


def pick_font_family() -> str:
    """挑一个可用的免费商用中文字体；一个都没有就用 Qt 默认（绝不因此报错）"""
    try:
        families = set(QFontDatabase.families())
    except Exception:       # noqa: BLE001
        return ""
    for name in FONT_CANDIDATES:
        if name in families:
            return name
    return ""


def ip_label(ip: str, names: Optional[Dict[str, str]] = None,
             mode: str = "last") -> str:
    """把一条原始 IP 变成上墙显示的名字

    优先级：自定义显示名 > 末位段（默认）/ 完整 IP
    ★ 重名兜底不在这里做（要看到整张表才知道撞没撞），见 build_labels()。
    """
    ip = str(ip or "").strip()
    if not ip:
        return UNKNOWN_IP_TEXT
    custom = (names or {}).get(ip) or ""
    if custom.strip():
        return custom.strip()
    if mode == "full":
        return ip
    parts = ip.split(".")
    if len(parts) == 4 and all(parts):
        return parts[-1]
    return ip


def build_labels(ips: List[str], names: Optional[Dict[str, str]] = None,
                 mode: str = "last") -> Tuple[List[str], List[str]]:
    """算出每行显示名，并做**重名兜底**

    ★ 为什么要兜底：默认只显示末位段，`192.168.1.20` 与 `192.168.1.20`
      都会变成 `20`，两行看起来一模一样、彻底分不出是谁。
      规则：撞名的这几行自动回退成完整 IP（宁可长一点，也不能张冠李戴）。
    返回 (显示名列表, 撞名说明列表)；说明列表非空时设置窗口会提示用户。
    """
    labels = [ip_label(ip, names, mode) for ip in ips]
    seen: Dict[str, List[int]] = {}
    for i, lab in enumerate(labels):
        seen.setdefault(lab, []).append(i)
    notes: List[str] = []
    for lab, idxs in seen.items():
        if len(idxs) <= 1:
            continue
        for i in idxs:
            raw = str(ips[i] or "").strip()
            full = raw if raw else UNKNOWN_IP_TEXT
            if full != lab:
                labels[i] = full
        raws = "、".join(str(ips[i] or "").strip() or UNKNOWN_IP_TEXT for i in idxs)
        notes.append("显示名「%s」撞名，已自动回退为完整 IP：%s" % (lab, raws))
    return labels, notes


def fmt_ts(ts_ms: int, pattern: str = "%H:%M:%S") -> str:
    """毫秒时间戳 → 本地时间串（与主程序统计页同一套 time.localtime 用法）"""
    try:
        return time.strftime(pattern, time.localtime(int(ts_ms) / 1000.0))
    except Exception:       # noqa: BLE001
        return "--:--:--"


def day_text(day: str) -> str:
    """标题用的日期文字（空 = 全部日期，不硬编成「今天」）"""
    d = str(day or "").strip()
    if not d:
        return "全部日期"
    return d


# ---------------------------------------------------------------- 数据汇总
def group_by_ip(rows: List[Dict], hide_unknown: bool = False,
                only_ips: Optional[List[str]] = None) -> List[Dict]:
    """把当天全部记录按 IP 汇总成「每 IP 一行」

    用 Python 分组而不是再写一条 GROUP BY SQL：看板要的口径和统计页
    「合计番数 / 次数」必须逐字一致，用同一份 recent_rows 原始行来做最不容易算岔；
    一天最多几百手，这点开销可以忽略。

    返回 [{ip, label_ip, cnt, fan, last_ts}]，按 fan 倒序。
    """
    bag: Dict[str, Dict] = {}
    only = set(only_ips or [])
    for r in rows:
        ip = str(r.get("ip") or "").strip()
        if hide_unknown and not ip:
            continue
        if only and ip not in only:
            continue
        b = bag.get(ip)
        if b is None:
            b = bag[ip] = {"ip": ip, "cnt": 0, "fan": 0, "last_ts": 0}
        b["cnt"] += 1
        try:
            b["fan"] += int(r.get("total_fan") or 0)
        except Exception:       # noqa: BLE001
            pass
        try:
            ts = int(r.get("ts_ms") or 0)
        except Exception:       # noqa: BLE001
            ts = 0
        if ts > b["last_ts"]:
            b["last_ts"] = ts
    out = list(bag.values())
    out.sort(key=lambda x: (-x["fan"], -x["cnt"], x["ip"]))
    return out


# ---------------------------------------------------------------- 绘制基元
def _stroke_width(px: float, ratio: float = STROKE_DEFAULT) -> float:
    """描边粗细：跟着字号走，但有下限（小字也得描得出来）

    ratio 是用户可调的系数（0.02~0.20）。
    ★ v2.9.32：原实现写死 0.14 且下限 3.0px，43px 字号算出 6.02px 的白边，
      用户反馈「太粗」。现在默认 0.08（43px → 3.44px），下限降到 1.0px，
      让大字时白边按比例细下来；小字仍保底 1px 不然根本看不见。
    """
    r = float(ratio)
    if r < STROKE_MIN:
        r = STROKE_MIN
    elif r > STROKE_MAX:
        r = STROKE_MAX
    return max(1.0, float(px) * r)


# 描边文字的**字形缓存**：key = (字体族, 像素字号, 是否粗体, 填充色, 描边色, 描边粗细, 文字)
# value = (QPixmap, offset_x, offset_y, advance) —— offset 是「字形左上角相对 (x, baseline)」的偏移
# ★ 描边粗细必须进 key：用户改了粗细而缓存没失效的话，屏幕上还是旧白边（真 bug 温床）
# ★ 描边**颜色**也必须进 key（v2.9.32 加自动配色时踩过的坑）：不加的话选了「自动」
#   屏幕上一点变化都没有，因为命中的还是白色那份缓存。
_GLYPH_CACHE: Dict[Tuple[str, int, bool, str, str, float, str],
                   Tuple[object, float, float, float]] = {}
_GLYPH_CACHE_MAX = 4000
# 字体对象缓存：(族, 像素, 粗体) -> QFont。一帧要建上百个 QFont，复用省 CPU
_FONT_CACHE: Dict[Tuple[str, int, bool], QFont] = {}


def clear_glyph_cache() -> None:
    """换字体族 / 改字号 / 改描边粗细后清缓存（粗细变了 key 会变，这里给显式入口）"""
    _GLYPH_CACHE.clear()


def _render_glyph(text: str, font: QFont, fill: str, dpr: float,
                  ratio: float = STROKE_DEFAULT,
                  stroke: str = STROKE_COLOR_DEFAULT):
    """把「白描边 + 色填充」的字形渲染成一张小 QPixmap（只做一次，之后贴图复用）

    为什么要缓存（实测数据，见 _scaffold/_wall_bench_text.py）：
        43px 字号下画 7 段文字，strokePath 就占 29.2ms、fillPath 占 9.9ms，
        合计 36.5ms；而把结果缓存成 pixmap 后贴一次只要 0.03ms/条。
        原来整屏重绘 111ms，绝大部分时间都耗在「每次都重新描一遍边」上。
    """
    px = int(font.pixelSize() or 16)
    path = QPainterPath()
    path.addText(QPointF(0.0, 0.0), font, text)
    br = path.boundingRect()
    sw = _stroke_width(px, ratio)
    pad = sw + 2.0
    w = max(1.0, br.width() + pad * 2.0)
    h = max(1.0, br.height() + pad * 2.0)
    scale = max(1.0, float(dpr))
    pm = QPixmap(int(w * scale + 0.999), int(h * scale + 0.999))
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    try:
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.scale(scale, scale)
        # 把字形挪进 pixmap 里，并留出描边溢出的余量
        p.translate(pad - br.left(), pad - br.top())
        pen = QPen(QColor(stroke or STROKE_COLOR_DEFAULT))
        pen.setWidthF(sw)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.strokePath(path, pen)             # ① 先描白边（粗）
        p.fillPath(path, QBrush(QColor(fill)))   # ② 再填色 —— 顺序反了就没描边
    finally:
        p.end()
    # advance 一起缓存：QFontMetricsF.horizontalAdvance 单次不算贵，
    # 但一帧要调上百次（实测 3.3ms/帧），缓存后归零。
    adv = float(QFontMetricsF(font).horizontalAdvance(text))
    # 贴图时的落点：(x + offset_x, baseline + offset_y)
    return pm, float(br.left() - pad), float(br.top() - pad), adv


def _get_glyph(text: str, font: QFont, fill: str, dpr: float,
               ratio: float = STROKE_DEFAULT,
               stroke: str = STROKE_COLOR_DEFAULT):
    key = (str(font.family()), int(font.pixelSize() or 16), bool(font.bold()),
           str(fill), str(stroke), round(float(ratio), 4), text)
    hit = _GLYPH_CACHE.get(key)
    if hit is not None:
        return hit
    if len(_GLYPH_CACHE) >= _GLYPH_CACHE_MAX:
        # 缓存满了直接清空重来：正常一天几百手根本到不了这里，
        # 真到了也是「一次性重建」，比逐个淘汰好写且不会漏算偏移。
        _GLYPH_CACHE.clear()
    got = _render_glyph(text, font, fill, dpr, ratio, stroke)
    _GLYPH_CACHE[key] = got
    return got


def draw_outlined(painter: QPainter, text: str, rect: QRectF, font: QFont,
                  fill: str, align: str = "left",
                  ratio: float = STROKE_DEFAULT,
                  stroke: str = STROKE_COLOR_DEFAULT) -> None:
    """在 rect 里**垂直居中**画一段带描边的文字

    ★ 顺序不能反：先 strokePath（描边色，粗）再 fillPath（色阶色），
      描边才会露在外面一圈；反了就被填色盖掉，等于没描边。
    ★ 走字形缓存：同样的 (文字, 字体, 颜色, 描边色, 粗细) 只栅格化一次，
      之后都是 drawPixmap（实测快 100 倍以上）。
    ★ stroke 可以是 `"auto"`：这时按**这一笔自己的字色**现算描边色
      （auto_stroke_for_fill）。所以「自动」必须落在这一层解，
      上层拿不到 fill，只能给一个整屏共用的色 —— 那必然有某一档撞色。
    """
    if not text:
        return
    painter.setFont(font)
    if str(stroke or "").strip().lower() == STROKE_AUTO:
        try:
            stroke = auto_stroke_for_fill(fill)
        except Exception:       # noqa: BLE001
            stroke = STROKE_COLOR_DEFAULT
    try:
        dpr = float(painter.device().devicePixelRatio())
    except Exception:       # noqa: BLE001
        dpr = 1.0
    try:
        pm, ox, oy, tw = _get_glyph(text, font, fill, dpr, ratio, stroke)
    except Exception:       # noqa: BLE001
        return
    fm = QFontMetricsF(font)
    if align == "center":
        x = rect.left() + (rect.width() - tw) / 2.0
    elif align == "right":
        x = rect.left() + rect.width() - tw
    else:
        x = rect.left()
    baseline = rect.top() + (rect.height() - fm.height()) / 2.0 + fm.ascent()
    painter.drawPixmap(QPointF(x + ox, baseline + oy), pm)


def _hline(painter: QPainter, x1: float, x2: float, y: float,
           color: QColor, width: float = 1.0) -> None:
    """画一条水平线

    ★ 不能用 drawLine + 抗锯齿：1900px 长的 1px 斜线在 AA 下要单独做覆盖率
      混合，实测 360 条线 / 帧要 11.2ms（占整帧 1/4）。水平线用 fillRect
      让 Qt 走最快的块填充路径，视觉上一模一样。
    """
    h = max(1.0, float(width))
    painter.fillRect(QRectF(float(x1), float(y) - h / 2.0,
                            max(0.0, float(x2) - float(x1)), h), color)


def make_font(family: str, px: int, bold: bool = False) -> QFont:
    """按像素建字体（用 setPixelSize 而不是 pointSize，缩放窗口时字号才可控）"""
    f = QFont(family) if family else QFont()
    f.setPixelSize(max(8, int(px)))
    f.setBold(bool(bold))
    return f


# ---------------------------------------------------------------- 窗口几何
def normalize_geo(geo, screens=None) -> Optional[Tuple[int, int, int, int]]:
    """把记住的窗口几何**校验成当前屏幕放得下**的 (x, y, w, h)

    为什么要这一步（真实风险，不是理论问题）：
        看板常放在副屏 / 投影仪上。拔掉副屏后原来记的 `x=1920` 就落在屏幕外，
        Qt 会把窗口摆到不可见位置 —— 用户看到的是「点了按钮什么都没出现」，
        而且自己没法救回来（找不到窗口就没法点「恢复默认」）。
    规则：
        1. 尺寸先夹到最小尺寸以上；
        2. 窗口矩形必须与某块屏幕有**足够大的交集**（至少 80px 可见），否则只
           保留尺寸、丢掉位置（交给 Qt 居中）；
        3. 任何异常一律返回 None（= 用默认尺寸），绝不因为几何数据脏而报错。
    """
    if not isinstance(geo, (list, tuple)) or len(geo) != 4:
        return None
    try:
        x, y, w, h = (int(v) for v in geo)
    except Exception:       # noqa: BLE001
        return None
    w = max(MIN_GEO_SIZE[0], w)
    h = max(MIN_GEO_SIZE[1], h)
    if screens is None:
        return (x, y, w, h)
    rects = []
    try:
        for r in screens:
            # 同时接受 QRect（真实调用）与 (x, y, w, h) 四元组（测试/兜底）
            if hasattr(r, "x") and hasattr(r, "width"):
                rects.append((int(r.x()), int(r.y()), int(r.width()), int(r.height())))
            else:
                rx, ry, rw, rh = (int(v) for v in r)
                rects.append((rx, ry, rw, rh))
    except Exception:       # noqa: BLE001
        return (x, y, w, h)
    if not rects:
        return (x, y, w, h)
    for sx, sy, sw, sh in rects:
        # 可见宽度 / 高度都要够，才算「放得下」
        vis_w = min(x + w, sx + sw) - max(x, sx)
        vis_h = min(y + h, sy + sh) - max(y, sy)
        if vis_w >= 80 and vis_h >= 40:
            return (x, y, w, h)
    # 没有一块屏幕接得住 → 只保留尺寸
    return (None, None, w, h)
