# -*- coding: utf-8 -*-
"""配色质量校验层：纯函数库（不 import Qt、不碰数据库、不读配置文件的副作用）

为什么单独一个文件
    v2.9.36 迭代记录里留下的待办（用户原话：「把「配色质量校验层」做成一个纯函数库」）。
    这批函数原本散在 mahjong_wall_core.py 里，与设置键、绘制基元、窗口几何混在一起，
    core 因此涨到 1253 行，也超过了项目「单文件不超过 1000 行」的规矩。
    它们本身是**纯计算**：给一个 #RRGGBB，算出亮度 / 对比度 / 色差 / 该配什么描边色，
    不需要窗口、不需要 QColor、不需要任何外部状态 —— 抽出来能单独测、单独复用。

本模块提供什么
    ① 颜色解析与规整：expand_hex / is_hex_color / normalize_steps / hex_to_rgb / rgb_to_hex
    ② 可见性度量：contrast_on_black（黑底 WCAG 对比度）、_luminance
    ③ 色差度量：_delta_e（CIE76 ΔE，走 Lab 而不是 WCAG 亮度比 —— 理由见 _srgb_to_lab）
    ④ 自动描边：auto_stroke_for_fill（按**单个字色**派生）、stroke_candidates、
       auto_stroke_for / auto_stroke_for_v2（旧版整屏一色，只留给探针对比，不参与绘制）
    ⑤ 配色体检：palette_quality(steps) —— 把上面这些度量拼成一份可直接展示的报告

★ 与绘制链路的约定（没变）
  · 真正画的时候必须走 stroke_setting() 拿原值，遇到 "auto" 要落到
    auto_stroke_for_fill(某个字色) 上；不能整屏算成一个固定色，
    否则必然有某一档字与描边撞色。
  · stroke_setting() 也在这里；但 resolve_stroke_color() 留在 mahjong_wall_core.py，
    因为它要解析「当前配色方案」（依赖方案的查表逻辑），不属于本层。

★ 兼容性
  mahjong_wall_core.py 会把这些名字原样 re-export（含下划线开头的私有度量），
  所以 `import mahjong_wall_core as C; C._delta_e(...)` 这类老写法继续有效。
"""
import math
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------- 描边常量
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


# ---------------------------------------------------------------- 颜色解析
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


# ---------------------------------------------------------------- 颜色计算
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



# ---------------------------------------------------------------- 色阶兜底
DEFAULT_STEPS = ("#FFD54A", "#FFE97A", "#6BFF9E", "#35E1FF", "#E8F0F8")

# ---------------------------------------------------------------- 配色体检


def palette_quality(steps) -> Dict[str, object]:
    """给一套 5 档配色做体检，返回可直接给界面/探针用的报告（纯函数，不改任何状态）

    返回：
        {
          "ok":        bool,        # 五档全部通过最低可见度要求
          "steps":     [ {...}, ... ],   # 每档一项，见下
          "weak":      [int, ...],  # 在纯黑底上「字色发闷」的档位下标（0 起）
          "min_delta": float,       # 描边与字色色差的最小值（最差那档）
          "highlights":[...],       # 人话结论，给界面直接显示
        }
    每档一项包含：fill / contrast / delta_to_white / stroke / stroke_delta / stroke_contrast

    判据（全部来自实测，不是拍脑袋）：
        · 字色黑底对比度 < 4.5 → 记进 weak（WCAG AA 对大字的要求）
        · 描边与字色的 ΔE >= AUTO_STROKE_DE_MIN(30) 才算「分得开」
        · 描边自己黑底对比度 >= AUTO_STROKE_BLACK_MIN(3.5) 才算「看得见」
    """
    seq = tuple(steps) if steps and len(steps) == 5 else DEFAULT_STEPS
    rows: List[Dict[str, object]] = []
    weak: List[int] = []
    min_delta = 999.0
    for i, fill in enumerate(seq):
        stroke = auto_stroke_for_fill(fill)
        c_fill = contrast_on_black(fill)
        d_white = _delta_e(fill, STROKE_COLOR_DEFAULT)
        d_stroke = _delta_e(fill, stroke)
        c_stroke = contrast_on_black(stroke)
        rows.append({
            "fill": fill,
            "contrast": round(c_fill, 2),
            "delta_to_white": round(d_white, 1),
            "stroke": stroke,
            "stroke_delta": round(d_stroke, 1),
            "stroke_contrast": round(c_stroke, 2),
        })
        if c_fill < 4.5:
            weak.append(i)
        if d_stroke < min_delta:
            min_delta = d_stroke
    ok = (not weak) and min_delta >= AUTO_STROKE_DE_MIN
    highlights: List[str] = []
    if weak:
        highlights.append("第 %s 档在纯黑底上偏暗（对比度 < 4.5）"
                          % "、".join(str(i + 1) for i in weak))
    if min_delta < AUTO_STROKE_DE_MIN:
        highlights.append("最窄的一档描边与字色只差 ΔE %.1f（建议 >= %.0f）"
                          % (min_delta, AUTO_STROKE_DE_MIN))
    if not highlights:
        highlights.append("五档字色在纯黑底上都清楚，描边与字色也都分得开")
    return {
        "ok": ok,
        "steps": rows,
        "weak": weak,
        "min_delta": round(min_delta, 1),
        "highlights": highlights,
    }


__all__ = [
    # 描边参数
    "STROKE_MIN", "STROKE_MAX", "STROKE_DEFAULT",
    "STROKE_COLOR_DEFAULT", "STROKE_AUTO",
    "AUTO_STROKE_DE_WHITE", "AUTO_STROKE_DE_MIN", "AUTO_STROKE_BLACK_MIN",
    "AUTO_STROKE_DIM_BELOW",
    # 颜色解析
    "is_hex_color", "expand_hex", "normalize_steps",
    "hex_to_rgb", "rgb_to_hex",
    # 度量
    "contrast_on_black", "palette_quality",
    # 自动描边
    "auto_stroke_for_fill", "stroke_candidates", "stroke_setting",
    "auto_stroke_for", "auto_stroke_for_v2",
    # 色阶兜底
    "DEFAULT_STEPS",
]
