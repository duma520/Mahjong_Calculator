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

# ---------------------------------------------------------------- 配色质量校验层（v2.9.37 抽出）
# 颜色解析 / 可见性度量 / 色差 / 自动描边，全部搬进 mahjong_color_quality.py，
# 本文件把这些名字**原样 re-export**：绘制链路、上墙设置界面、三个探针脚本
# （_stroke_auto_probe.py / _v34_rainbow_check.py / _board_stroke_cmp.py）
# 一律沿用 `mahjong_wall_core.xxx` 的旧写法，外部接口一个都没变。
from mahjong_color_quality import (  # noqa: F401
    # 描边参数
    STROKE_MIN, STROKE_MAX, STROKE_DEFAULT,
    STROKE_COLOR_DEFAULT, STROKE_AUTO,
    AUTO_STROKE_DE_WHITE, AUTO_STROKE_DE_MIN, AUTO_STROKE_BLACK_MIN,
    AUTO_STROKE_DIM_BELOW,
    # 色阶兜底
    DEFAULT_STEPS,
    # 颜色解析与度量
    is_hex_color, expand_hex, normalize_steps,
    hex_to_rgb, rgb_to_hex,
    contrast_on_black, palette_quality,
    # 自动描边
    auto_stroke_for_fill, stroke_candidates, stroke_setting,
    auto_stroke_for, auto_stroke_for_v2,
    # 私有度量：探针脚本直接按这些名字断言，必须一起 re-export
    _luminance, _mix, _contrast_pair, _hsl_of, _hsl_hex, _srgb_to_lab, _delta_e,
    _auto_stroke_for_fill_uncached, _AUTO_STROKE_CACHE,
)

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
    # 倒计时（⏱ ★ v2.9.37 新增；v2.9.45 加字号倍数）
    "wall_cd_minutes", "wall_cd_state", "wall_cd_remain_ms", "wall_cd_saved_at",
    "wall_cd_font_scale",
)

# ---------------------------------------------------------------- 倒计时（★ v2.9.37）
# 用户要求（原话）：「在上墙哪里增加 倒计时，分别是1小时，2小时，3小时，可选。
#   显示在"今日战绩"后面，显示方式为 HH:MM:SS，就是时分秒。」
# 交互口径（已与用户确认）：手动开始 / 暂停 / 重置；归零后**停住**显示 00:00:00
#   并闪红 + 播提示音；关掉看板再打开，按**真实经过的时间**接着走。
#
# 为什么存「剩余毫秒 + 落盘时刻」而不是只存一个截止时间戳：
#   running 时剩余 = remain_ms - (now - saved_at)，两个数一起存才能跨进程重启
#   正确续算；paused / done 时 now 不再参与，remain_ms 就是定格值。
#   只存截止时间戳的话，暂停后时间还在走，暂停等于没暂停。
CD_STATE_IDLE = "idle"
CD_STATE_RUNNING = "running"
CD_STATE_PAUSED = "paused"
CD_STATE_DONE = "done"
CD_STATES = (CD_STATE_IDLE, CD_STATE_RUNNING, CD_STATE_PAUSED, CD_STATE_DONE)

# 可选时长（分钟）—— 用户点名 1 / 2 / 3 小时；0 = 不显示倒计时（默认，老用户零感知）
CD_MINUTES_CHOICES = (0, 60, 120, 180)
CD_MINUTES_ITEMS = (
    (0, "关闭倒计时"),
    (60, "1 小时"),
    (120, "2 小时"),
    (180, "3 小时"),
)

# 倒计时字号的倍数（★ v2.9.45）—— 基准是**标题「今日战绩」的字号**，不是绝对像素。
# 用户 v2.9.44 反馈：网页版倒计时比标题小一档看着太小，要求「跟今日战绩一样大」。
# 所以默认 1.0（完全等大）；要小一档填 0.78（v2.9.37~v2.9.44 的旧观感），要大最多 2.0。
# 用倍数而不是绝对字号：窗口放大、换分辨率时两者一起缩放，比例永远不变
# —— 与 wall_stroke「按字号比例算描边」是同一套思路。
CD_FONT_SCALE_DEFAULT = 1.0
CD_FONT_SCALE_MIN = 0.5
CD_FONT_SCALE_MAX = 2.0

# 倒计时字色：与标题（#35E1FF 亮青）刻意错开，一眼能分清「这是表盘不是标题」
CD_COLOR_RUN = "#FFD54A"     # 正常运行：金黄
CD_COLOR_WARN = "#FF9F43"    # 剩余 < 5 分钟：转橙提醒
CD_COLOR_DONE = "#FF5252"    # 归零：红（配合闪动）
CD_WARN_MS = 5 * 60 * 1000   # 5 分钟警戒线
CD_FLASH_MS = 500            # 归零后闪动周期（亮/灭各半）
CD_TICK_MS = 250             # 界面刷新节拍：1 秒的显示 + 500ms 的闪动都够用


def fmt_countdown(remain_ms: int) -> str:
    """剩余毫秒 → `HH:MM:SS`（用户指定格式）；负数按 0 算，不出现 -00:00:01"""
    ms = max(0, int(remain_ms or 0))
    total = ms // 1000
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return "%02d:%02d:%02d" % (h, m, s)


def countdown_color(remain_ms: int, state: str, blink_on: bool = True) -> str:
    """倒计时该用哪个颜色

    done 时按 blink_on 在红色与暗红之间跳 —— 这是「闪红」的实现：不靠 Qt 动画，
    靠 250ms 的刷新节拍换色，投屏上看得见，也不额外占一个 QTimer。
    分档：inactive 灰（选了时长但没开始）/ paused 橙（停住了，不是坏了）/
          剩 5 分钟内橙 / 正常金 / 归零闪红。
    """
    st = str(state or "")
    if st == CD_STATE_IDLE:
        return MUTED                 # 待开始：灰，和「正在走」一眼分开
    if st == CD_STATE_PAUSED:
        return CD_COLOR_WARN
    if st == CD_STATE_DONE or int(remain_ms or 0) <= 0:
        return CD_COLOR_DONE if blink_on else "#7A1E1E"
    if int(remain_ms or 0) <= CD_WARN_MS:
        return CD_COLOR_WARN
    return CD_COLOR_RUN


def countdown_visible(cfg: Optional[Dict]) -> bool:
    """当前配置下倒计时是否要显示（时长 0 或没设置 = 完全不显示，行为同老版本）"""
    try:
        return int((cfg or {}).get("wall_cd_minutes") or 0) > 0
    except Exception:       # noqa: BLE001
        return False


def resume_countdown(cfg: Optional[Dict], now: Optional[float] = None) -> Dict:
    """按落盘状态算出「现在」应该是什么状态（关掉看板再打开时用它接上）

    返回 {state, remain_ms, expired}：
      · running → 剩余 = 落盘剩余 - 真实经过秒数；减到 <=0 就是 done/expired
      · paused  → 原样（暂停期间时间不该走）
      · done    → 原样 0
      · idle    → 时长（若已经选过时长，回到满格待开始）
    ★ 只在这里做一次「扣时间」，之后由窗口自己的 QTimer 在内存里累减，
      不读系统时钟，避免每次重绘都算一遍时间差。
    """
    c = normalize_config(cfg)
    total = int(c["wall_cd_minutes"]) * 60 * 1000
    st = str(c["wall_cd_state"])
    remain = int(c["wall_cd_remain_ms"])
    expired = False
    if not countdown_visible(c):
        return {"state": CD_STATE_IDLE, "remain_ms": 0, "expired": False}
    if st == CD_STATE_RUNNING:
        saved = int(c["wall_cd_saved_at"] or 0)
        t = float(now if now is not None else time.time())
        elapsed_ms = int(max(0.0, t - saved) * 1000) if saved > 0 else 0
        remain = max(0, remain - elapsed_ms)
        if remain <= 0:
            remain = 0
            st = CD_STATE_DONE
            expired = True
        else:
            st = CD_STATE_RUNNING
    elif st == CD_STATE_PAUSED:
        # 暂停在 0 上不成立（0 就是 done）→ 至少留 1 秒，这样「继续」一定还能走
        remain = max(1, min(total, remain))
        st = CD_STATE_PAUSED
    elif st == CD_STATE_DONE:
        st = CD_STATE_DONE
        remain = 0
    else:
        st = CD_STATE_IDLE
        remain = total          # 选好时长但没开始 → 满格显示，等点「开始」
    return {"state": st, "remain_ms": remain, "expired": expired}


def countdown_next(cfg: Optional[Dict]) -> Dict:
    """「开始」按钮按下后应该切到什么状态（选好时长才允许开始）

    已归零(done) 再点开始 → 从满格重新来；暂停中点开始 → 接着走。
    """
    c = normalize_config(cfg)
    total = int(c["wall_cd_minutes"]) * 60 * 1000
    if total <= 0:
        return {"state": CD_STATE_IDLE, "remain_ms": 0}
    st = str(c["wall_cd_state"])
    remain = int(c["wall_cd_remain_ms"])
    if st == CD_STATE_DONE or remain <= 0:
        return {"state": CD_STATE_RUNNING, "remain_ms": total}
    if st == CD_STATE_IDLE:
        return {"state": CD_STATE_RUNNING, "remain_ms": total}
    return {"state": CD_STATE_RUNNING, "remain_ms": max(1, remain)}


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
        # ---- 倒计时（★ v2.9.37）----
        "wall_cd_minutes": 0,      # 0=关闭（默认，老用户零感知）/ 60 / 120 / 180
        "wall_cd_state": CD_STATE_IDLE,   # idle / running / paused / done
        "wall_cd_remain_ms": 0,    # 剩余毫秒（paused/done 时是定格值）
        "wall_cd_saved_at": 0,     # 保存时刻（epoch 秒）；running 时用它扣掉真实流逝
        "wall_cd_font_scale": CD_FONT_SCALE_DEFAULT,  # 字号 = 标题字号 × 本值（1.0=等大）
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
    # ---- 倒计时（★ v2.9.37）----
    # 时长只认 0/60/120/180，其它值一律回 0（关）。脏数据不能让看板显示个怪时长。
    try:
        mins = int(cfg.get("wall_cd_minutes") or 0)
    except Exception:       # noqa: BLE001
        mins = 0
    out["wall_cd_minutes"] = mins if mins in CD_MINUTES_CHOICES else 0
    st = str(cfg.get("wall_cd_state") or CD_STATE_IDLE).strip().lower()
    out["wall_cd_state"] = st if st in CD_STATES else CD_STATE_IDLE
    # 剩余毫秒：夹在 [0, 时长] 之间。**不能超过总时长**，否则手工改设置文件能造出
    # 「3 小时的表盘显示 99 小时」；也不能是负的。
    total_ms = int(out["wall_cd_minutes"]) * 60 * 1000
    try:
        remain = int(cfg.get("wall_cd_remain_ms") or 0)
    except Exception:       # noqa: BLE001
        remain = 0
    if total_ms <= 0:
        out["wall_cd_remain_ms"] = 0
        if out["wall_cd_state"] != CD_STATE_IDLE:
            out["wall_cd_state"] = CD_STATE_IDLE
    else:
        out["wall_cd_remain_ms"] = max(0, min(total_ms, remain))
    try:
        out["wall_cd_saved_at"] = max(0, int(cfg.get("wall_cd_saved_at") or 0))
    except Exception:       # noqa: BLE001
        out["wall_cd_saved_at"] = 0
    # 字号倍数（★ v2.9.45）：夹在 [0.5, 2.0]。脏数据（0、负数、nan、字符串）
    # 一律回默认 1.0 —— 否则会算出 0 号字，表盘直接看不见了。
    fsv = cfg.get("wall_cd_font_scale")
    if fsv is not None:
        try:
            f = float(fsv)
            if f != f:          # nan 不等于自己，单独挡一下
                raise ValueError("nan")
            out["wall_cd_font_scale"] = max(CD_FONT_SCALE_MIN,
                                            min(CD_FONT_SCALE_MAX, f))
        except Exception:   # noqa: BLE001
            out["wall_cd_font_scale"] = CD_FONT_SCALE_DEFAULT
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



# ---------------------------------------------------------------- 描边颜色解析
# ★ 留在本文件而不是搬去 mahjong_color_quality.py：它要查「当前配色方案」的色阶
#   （resolve_steps），而方案查表依赖 palette 模块与用户自定义方案，不属于纯颜色计算。
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
