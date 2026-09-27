# -*- coding: utf-8 -*-
"""国标麻将算番器 —— 主程序（唯一编译源）

界面：PySide6 (Qt6)，Windows 桌面，中文界面，默认风格。
引擎：同目录 `mahjong_core.py`；规则数据：同目录《国标麻将标准规则.json》；
牌面图片：同目录《麻将图》子目录
    B1~B9 = 1筒~9筒      T1~T9 = 1索~9索      W1~W9 = 1万~9万
    F1~F4 = 东南西北      J1~J3 = 中 发 白     empty.png = 麻将背面

交互（按《软件设计构图》实现）
    · 牌选择区四行：索 / 筒 / 万 / 字牌。左键点一下加一张（最多 4 张），右键减一张。
      ★ **不用右键也能减牌**（v2.7.2，手机/触屏一样好使）：
        ① 点牌上那个**红色数字角标**＝减一张（与 Web 端的「点红色数字 −1」一致）；
        ② 下面「已选牌」区里**点某一张牌＝取消这一张**：副露里点一张＝撤销那一组副露，
           「和张」点一下＝取消和张，「花牌」行点一张＝取消那张花牌。
      ★ 牌与牌之间只留 4px（v2.4.2）：牌是固定尺寸，多余宽度靠 `setColumnStretch(空列, 1)`
        全部让给右侧空白，不要在 grid 上直接铺开（否则 9 列被均匀撑宽、缝隙很大）。
    · 立牌 = 手上其他牌（默认模式）；吃 / 碰 / 明杠 / 暗杠 都是「先点按钮，再选牌」：
        碰·明杠·暗杠 —— 点一次牌即成立；
        吃 —— 依次点出 3 张相连的牌后成立。
    · 暗杠显示为「面·背·背·面」，中间两张用 empty.png。
    · 自摸勾选后，后面两个复选框变成 杠上开花 / 妙手回春；
      未勾选时为 抢杠和 / 海底捞月。
    · 风圈、风位任何时候都可以点。
    · ★ 「重置」= **全部**回到初始状态（v2.4.4）：手牌 / 副露 / 和张 / 待选 / 模式 / 花牌 /
      自摸·和绝张·抢杠和（杠上开花）·海底捞月（妙手回春）/ 圈风（回东风圈）/ 风位（回东风位），
      并且马上存进设置（下次启动也是干净的）。
    · ★ 选项区固定四行（按《软件设计构图》，v2.4.1 起）：
        第1行 自摸 / 和绝张 / 抢杠和（杠上开花）/ 海底捞月（妙手回春）
        第2行 东风圈 / 南风圈 / 西风圈 / 北风圈
        第3行 风位 + 东风位 / 南风位 / 西风位 / 北风位
        第4行 花牌: 春夏秋冬 梅兰竹菊（点一下选/取消，右侧显示张数）
    · 立牌选满 13 张后自动列出听牌候选（每个候选牌上方标出总番数），
      点候选牌或点上方牌区的牌即可得出总番数与番种列表。

★ 给其它程序调用的「API」＝ `mahjong_core`（v2.6.0）
    - 程序要算番，**不需要 HTTP、不需要端口、不需要先启动谁**，两种方式：
      ① 能 import 的：`from mahjong_core import MahjongFanCalculator`（或便捷函数 `score_hand()`）
      ② 不能 import 的：把牌当参数丢给 exe/py，算完就退出：
         国标麻将算番器.exe --hand "11123456789999m" --win 9m --json
         python mahjong_core.py --hand "444z 123m 3z" --meld kong:6666z --waits --text
      牌写法：W1 / 一万 / 11123456789999m（m 万 s 索 p 筒 z 字牌）；副露：chi:/peng:/kong:/angang:
      默认输出 JSON（--text 为人话）；算不出和牌退出码 1、参数错退出码 2。

Web 版（给手机/平板**浏览器**用；★ 不是给程序调用的接口）
    - 同目录 `mahjong_api.py`：单文件 Web 客户端（手机/平板浏览器可直接算番）。
    - 工具菜单：启动 Web 版（Ctrl+Alt+A）/ 允许局域网访问（手机·平板）/ 设置访问口令 /
      免口令访问设置 / Web 版地址与用法 / Web 版端口设置。
    - 默认只绑 127.0.0.1；勾上「允许局域网访问」改成 0.0.0.0，**默认不需要口令**
      （v2.6.0 起不再自动生成口令），手机打开 http://电脑IP:端口/ 即可。
    - ★ Web 端的**界面布局与桌面版一致**（v2.4.4）：牌选择区（索/筒/万/字牌四行）→ 模式行（+重置）
      → 选项区四行（□选项 / 风圈 / 风位 / 花牌 8 张小图 + 「N 张」）→ 已选牌 → 听牌候选 → 算番结果。
      花牌**不在牌池里**（跟桌面版一样放选项区第四行）；「重置」也是全部复位。
    - ★ Web 端是**给手机/平板用的**（v2.4.6）：手机没有右键，所以减牌入口改成
      「点牌上的红色数字 −1」＋「在『已选牌→立牌』里点一张减一张」；
      长按/右键减牌仍保留给鼠标，并禁掉了长按系统菜单与文本选择
      （`-webkit-touch-callout:none; user-select:none`）。
    - ★ **桌面版也照这个来**（v2.7.2）：牌选择区的红角标点一下就 −1，「已选牌」区
      （副露 / 立牌 / 和张 / 花牌）里点某一张＝取消这一张；右键仍然可用，不影响鼠标习惯。
    - ★ **牌尺寸两套布局共存**（v2.7.0）：默认仍是「经典」（固定尺寸，与老版本逐像素一致），
      点模式行里的「布局：经典」可在 **经典 ⇄ 自适应** 之间切（选择记在 localStorage `mj_layout`）。
      自适应按屏幕宽高算牌尺寸（一行 9 张不超宽 + 高度上限，夹在 20~46px）——
      手机上不会过大、平板上不会过小；经典模式会清掉 JS 写的 CSS 变量，回到 CSS 默认值。
    - ★ 免口令白名单（v2.5.0）：口令设了之后，可以**分项**允许某些东西「不输入口令也能用」——
      工具菜单「免口令访问设置…」里逐项勾选：**Web 客户端页面（含牌面图）** / 自测页 /
      查询类接口 / 算番接口 / 听牌接口。默认（web + debug）与旧版行为一致；
      口令留空时本就不校验口令，勾选怎么写都不影响。
    - 相关设置项：api_port / api_auto_start / api_lan / api_token / **api_anon**。

设置持久化（实时自动保存）
    - 设置存程序目录 `mahjong_settings.json`（打包后为 exe 同目录），
      原子写入（tmp + os.replace）。
    - 控件变更信号 → autosave()（500ms 防抖）→ _save_settings_now() 立即写盘。
    - 退出 closeEvent 强制保存；启动 _load_settings() 恢复。
    - 新增设置项必须三处成对实现：_collect_settings() 收集 +
      _apply_settings() 应用（用 blockSignals 防止加载时触发保存）+
      _connect_autosave() 接信号。

窗口尺寸（★ v2.4.3）
    - 默认 680×940、最小 600×560（常量 WIN_W/WIN_H/MIN_W/MIN_H）。牌池 9 列牌宽 54
      + 间距 4 ≈ 520px，加边距/滚动条约 560，所以 680 已经留了余量；
      以前是 1180×960 + 最小 1020（牌还铺得很开时的尺寸，太宽）。
    - 设置里同时存 `geometry` 与 `geo_ver`；`geo_ver < GEO_VER(2)` 的旧几何在首次升级时
      **一次性**把宽度收紧到 WIN_W（宽度只收紧这一次，高度/位置保留；用户手动拉宽后会
      存成 geo_ver=2，以后不会再被动收紧）。

程序图标 icon.ico（★ v2.4.7）
    - 根目录 `icon.ico`：红中牌样式（蓝底 #2f7ff0 + 白牌面 + 红「中」），共 7 张尺寸
      16/24/32/48/64/128/256。生成脚本 `_scaffold/make_icon.py`
      （PIL + 项目自带 `msyh.ttf`，**每个尺寸单独绘制**而不是缩放同一张，小尺寸才不糊）。
    - 运行时要读得到：`app_icon()` 依次找 exe/程序目录（打包后是 exe 同目录）下的
      `icon.ico`、`data/icon.ico`；**找不到或读坏就安静返回空 QIcon**（Qt 用默认图标），
      绝不因为图标让程序起不来。结果带缓存。
    - **两处 setWindowIcon 缺一不可**：`main()` 里的 app 级（任务栏/Alt+Tab）与
      `MahjongFanWindow.__init__` 里的窗口级；exe **文件自身**的图标靠打包参数
      `--windows-icon-from-ico=icon.ico`，并配 `--include-data-files=icon.ico=icon.ico`
      让运行时也能读到（`_scaffold/build_exe.py` 已自动带上这两个参数）。
"""
import json
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QStackedWidget, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

__version__ = "2.7.2"
APP_NAME = "国标麻将算番器"
SETTINGS_FILE = "mahjong_settings.json"
RULES_FILE = "国标麻将标准规则.json"
TILE_DIRS = ("麻将图", "tiles")

WIND_NAMES = ["东", "南", "西", "北"]

# 牌选择区四行（按设计图：索 / 筒 / 万 / 字牌）
POOL_ROWS = [
    ["T%d" % i for i in range(1, 10)],
    ["B%d" % i for i in range(1, 10)],
    ["W%d" % i for i in range(1, 10)],
    ["F1", "F2", "F3", "F4", "J1", "J2", "J3"],
]

POOL_SIZE = QSize(48, 65)
HAND_SIZE = QSize(36, 49)
CAND_SIZE = QSize(32, 43)
FLOWER_SIZE = QSize(30, 40)

# ★ 窗口尺寸（v2.4.3）：牌池 9 列牌宽 54 + 间距 4 ≈ 520，加左右边距/滚动条约 560，
#   留一点冗余就够（以前是 1180×960，那是牌还铺得很开时的尺寸，太宽了）。
#   窗口随时可以拉宽/拉高，拖动后会自动存进设置。
WIN_W, WIN_H = 680, 940        # 默认窗口尺寸
MIN_W, MIN_H = 600, 560        # 最小窗口尺寸（再小牌池就会被挤）
GEO_VER = 2                    # 几何版本：<2 表示旧版（牌铺开 + 最小宽度 1020）存下的尺寸

# ★ 花牌（`麻将图\` 里的 P1~P4 = 梅兰竹菊，S1~S4 = 春夏秋冬）
# 每张 1 分、不计入 8 分起和分；花牌不占 14 张手牌（补花后另抓）
FLOWER_CODES = ["S1", "S2", "S3", "S4", "P1", "P2", "P3", "P4"]

# ★ v2.5.0：免口令白名单 —— 设了口令后，勾中的这些「不用口令也能用」（含 Web 客户端）。
#   键名与 mahjong_api.ANON_GROUPS 一一对应；默认 web+debug 与旧版行为完全一致。
ANON_ITEMS = [
    ("web", "Web 客户端页面（手机/平板打开就能用）",
     "含页面本身与牌面图（/、/web、/index.html、/manifest、/favicon、/tiles/*）；"
     "取消勾选后要用 http://IP:端口/?token=口令 打开（页面里的牌面图会自动带上口令）"),
    ("debug", "接口自测页 /debug", "浏览器里直接试接口的调试页"),
    ("info", "查询类接口", "/api/health、/api/version、/api/tiles、/api/fan_table、/api/help"),
    ("score", "算番接口 /api/score", "别的程序/脚本调算番时用"),
    ("waits", "听牌接口", "/api/waits、/api/waits_all"),
]
ANON_KEYS = [k for k, _, _ in ANON_ITEMS]
ANON_DEFAULT = ["web", "debug"]
FLOWER_NAMES = {"S1": "春", "S2": "夏", "S3": "秋", "S4": "冬",
                "P1": "梅", "P2": "兰", "P3": "竹", "P4": "菊"}

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ 路径与设置

def app_dir() -> str:
    """程序目录：打包后取 exe 所在目录，源码运行时取脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return HERE


def resource_path(*parts: str) -> str:
    return os.path.join(app_dir(), *parts)


def settings_path() -> str:
    return os.path.join(app_dir(), SETTINGS_FILE)


_app_icon_cache = None


def app_icon() -> QIcon:
    """程序图标：取 exe/程序目录旁的 `icon.ico`（打包时与 dist 一起分发）。

    带缓存；**文件不存在/读坏时返回空 QIcon**（Qt 用默认图标），绝不抛异常 ——
    图标属于锦上添花，不能因为它让程序起不来。
    """
    global _app_icon_cache
    if _app_icon_cache is not None:
        return _app_icon_cache
    for p in (resource_path("icon.ico"),
              resource_path("data", "icon.ico"),
              os.path.join(HERE, "icon.ico")):
        try:
            if os.path.exists(p):
                ic = QIcon(p)
                if not ic.isNull():
                    _app_icon_cache = ic
                    return ic
        except Exception:       # noqa: BLE001
            continue
    _app_icon_cache = QIcon()
    return _app_icon_cache


def _atomic_write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings() -> dict:
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:       # noqa: BLE001
        return {}


def save_settings(data: dict) -> bool:
    try:
        _atomic_write_json(settings_path(), data)
        return True
    except Exception as exc:    # noqa: BLE001
        print("保存设置失败: %r" % (exc,))
        return False


# ------------------------------------------------------------------ 引擎导入

try:
    from mahjong_core import (MahjongFanCalculator, Meld, Options, cli_main,
                              cli_wanted, code_of, counts_of, is_suit, name_of,
                              suit_of, tile_of)
    CORE_IMPORT_ERROR = None
except Exception as _exc:       # noqa: BLE001
    MahjongFanCalculator = None      # type: ignore[assignment]
    Meld = None                      # type: ignore[assignment]
    Options = None                   # type: ignore[assignment]
    code_of = name_of = tile_of = suit_of = is_suit = counts_of = None
    cli_main = cli_wanted = None     # type: ignore[assignment]
    CORE_IMPORT_ERROR = repr(_exc)

# ★ Web 版服务（同目录 mahjong_api.py；缺失时程序仍能正常运行，只是没有 Web 版）
#   注意：**给其它程序调用的「API」是 mahjong_core**（import 或命令行），不是这台 HTTP 服务；
#   这里的服务只为「手机/平板浏览器算番」的 Web 页面存在。
try:
    from mahjong_api import (ApiError as ApiError_, ApiServer as ApiServer_,
                            lan_ip as lan_ip_)
    API_IMPORT_ERROR = None
except Exception as _exc:       # noqa: BLE001
    ApiServer_ = None                # type: ignore[assignment]

    class ApiError_(Exception):      # type: ignore[no-redef]
        message = ""

    def lan_ip_() -> str:            # type: ignore[no-redef]
        return "127.0.0.1"

    API_IMPORT_ERROR = repr(_exc)

DEFAULT_API_PORT = 8718

BACK_TILE = "\u0000BACK"          # 牌背哨兵（渲染时用 empty.png）
GAP = "\u0000GAP"                # 副露之间的间隔哨兵


# ------------------------------------------------------------------ 牌面图形

_PIX_CACHE: Dict[str, QPixmap] = {}


def _tile_file(code: str) -> Optional[str]:
    for d in TILE_DIRS:
        p = resource_path(d, code + ".png")
        if os.path.exists(p):
            return p
    return None


def tile_pixmap(code: str) -> QPixmap:
    """取牌面图；找不到时画一张带文字的兜底牌。"""
    if code in _PIX_CACHE:
        return _PIX_CACHE[code]
    fname = "empty" if code == BACK_TILE else code
    path = _tile_file(fname)
    if path:
        pix = QPixmap(path)
    else:
        pix = QPixmap(44, 60)
        pix.fill(QColor("#f7f9fc"))
        # 兜底：直接画文字，保证界面不空白
    if pix.isNull():
        pix = QPixmap(44, 60)
        pix.fill(QColor("#f7f9fc"))
    _PIX_CACHE[code] = pix
    return pix


def tile_icon(code: str, size: QSize) -> QIcon:
    return QIcon(tile_pixmap(code).scaled(
        size, Qt.KeepAspectRatio, Qt.SmoothTransformation))


def tile_label(code: str, size: QSize) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(tile_pixmap(code).scaled(
        size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    lbl.setFixedSize(size)
    lbl.setAlignment(Qt.AlignCenter)
    if code == BACK_TILE:
        lbl.setToolTip("牌背（暗杠 / 暗牌）")
    elif code in FLOWER_NAMES:
        lbl.setToolTip("花牌 · %s（%s）每张 1 分，不计入起和分"
                       % (FLOWER_NAMES[code], code))
    else:
        try:
            lbl.setToolTip(name_of(tile_of(code)))
        except Exception:       # noqa: BLE001
            pass
    return lbl


def clear_layout(layout) -> None:
    """安全清空布局（逐项摘下 + deleteLater，避免悬空指针）"""
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        else:
            clear_layout(item.layout())
        del item


class CountBadge(QLabel):
    """牌选择区的「已选张数」红角标

    ★ v2.7.2：**点一下＝减一张**（手机/触屏没有右键，右键只能算鼠标用户的便利）。
    尺寸比 v2.7.1 略放大（16→20），手指才好点中。
    """

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("点一下减一张（等于右键）")
        self.setStyleSheet(
            "background:#e74c3c;color:#fff;border-radius:10px;font-size:11px;"
            "font-weight:bold;")

    def mousePressEvent(self, event):     # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()           # 吃掉事件，不要传给底下的牌按钮（否则又加一张）
            return
        super().mousePressEvent(event)


class ClickTile(QLabel):
    """★ v2.7.2：**可点击的牌**（点一下＝取消这张）

    给手机/触屏用 —— 这类设备没有右键，桌面版原来「右键减一张」在触屏上完全用不了。
    用在「已选牌」区的四个牌行（副露 / 立牌 / 和张 / 花牌）里，
    外观与只读牌（`tile_label`）一致，只是多了悬停高亮 + 手型光标。
    """

    clicked = Signal(object)        # 发 payload（立牌/和张/花牌＝牌编码；副露＝组号）

    def __init__(self, code: str, size: QSize, payload, tip: str = "", parent=None):
        super().__init__(parent)
        self.code = code
        self.payload = payload
        self.setPixmap(tile_pixmap(code).scaled(
            size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setFixedSize(size)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip or "点一下取消这张")
        self.setStyleSheet(
            "QLabel{border:1px solid transparent;border-radius:4px;}"
            "QLabel:hover{background:#ffe3e3;border-color:#f5a9a9;}")

    def mousePressEvent(self, event):     # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.payload)
            event.accept()
            return
        super().mousePressEvent(event)


class TileButton(QToolButton):
    """牌选择区里的可点击牌（左上角显示已选张数）"""

    leftClicked = Signal(str)
    rightClicked = Signal(str)

    def __init__(self, code: str, size: QSize = POOL_SIZE, parent=None):
        super().__init__(parent)
        self.code = code
        self.setIcon(tile_icon(code, size))
        self.setIconSize(size)
        self.setFixedSize(size.width() + 6, size.height() + 6)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAutoRaise(True)
        if code in FLOWER_NAMES:
            self.setToolTip("花牌 · %s（%s）每张 1 分，不计入起和分"
                            % (FLOWER_NAMES[code], code))
        else:
            try:
                self.setToolTip(name_of(tile_of(code)))
            except Exception:       # noqa: BLE001
                pass
        self._count = 0
        # ★ v2.7.2：角标改成可点（点一下减一张 —— 手机/触屏没有右键）
        self.badge = CountBadge(self)
        self.badge.move(self.width() - self.badge.width() - 1, 1)
        self.badge.clicked.connect(self._on_badge_clicked)
        self.badge.hide()
        self.clicked.connect(lambda: self.leftClicked.emit(self.code))
        self._apply_style()

    def _on_badge_clicked(self) -> None:
        """点红角标＝减一张（与 Web 端「点红色数字 −1」一致）"""
        self.rightClicked.emit(self.code)

    # ---- 外观
    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QToolButton{border:2px solid transparent;border-radius:5px;"
            "background:#f4f6fa;} "
            "QToolButton:hover{background:#e6eefc;border-color:#a9c6f5;} "
            "QToolButton[selected=\"true\"]{background:#dceaff;"
            "border:2px solid #2f7ff0;}")

    def set_count(self, n: int) -> None:
        self._count = n
        if n > 0:
            self.badge.setText(str(n))
            self.badge.show()
            self.badge.raise_()
        else:
            self.badge.hide()
        self.set_selected(n > 0)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):     # noqa: N802
        if event.button() == Qt.RightButton:
            self.rightClicked.emit(self.code)
            return
        super().mousePressEvent(event)


class TileRow(QWidget):
    """一排牌（副露 / 立牌 / 和张 / 花牌）

    ★ v2.7.2：`clickable=True` 时每一张都能点 —— **点一下＝取消这张**，
    不再依赖右键（手机 / 平板触屏也能操作，与 Web 端口径一致）。
    `clicked` 发的是 `payloads` 里对应的值：
    立牌 / 和张 / 花牌 = 牌编码（str），副露 = 组号（int）。
    """

    clicked = Signal(object)

    def __init__(self, size: QSize = HAND_SIZE, empty_text: str = "",
                 parent=None, clickable: bool = False):
        super().__init__(parent)
        self._size = size
        self._empty_text = empty_text
        self._clickable = clickable
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(2)
        self.set_tiles([])

    def set_tiles(self, codes: List[str], payloads=None, tip: str = "") -> None:
        """codes = 要显示的牌串（可含 GAP / BACK_TILE）；
        payloads 与 codes 等长，值为 None 的那张不可点（如副露之间的间隔）。"""
        clear_layout(self._layout)
        if not codes:
            if self._empty_text:
                lbl = QLabel(self._empty_text)
                lbl.setStyleSheet("color:#9aa3ae;")
                self._layout.addWidget(lbl)
        else:
            for i, c in enumerate(codes):
                if c == GAP:
                    self._layout.addSpacing(10)
                    continue
                pay = payloads[i] if (payloads and i < len(payloads)) else None
                if self._clickable and pay is not None:
                    item = ClickTile(c, self._size, pay, tip)
                    item.clicked.connect(self.clicked)
                    self._layout.addWidget(item)
                else:
                    self._layout.addWidget(tile_label(c, self._size))
        self._layout.addStretch(1)


# ------------------------------------------------------------------ 帮助文本

HELP_TEXT = """
<h3>一、怎么算一手牌</h3>
<ol>
<li><b>选牌</b>：上方四行是牌选择区（索 / 筒 / 万 / 字牌）。
左键点一下加一张，最多四张；<b>右键点一下减一张</b>。</li>
<li><b>不用右键也能减牌</b>（v2.7.2，手机 / 触屏一样好使）：
点牌上那个<b>红色数字</b>就是 −1；下面「已选牌」区里<b>点某一张牌也会取消这一张</b>
（副露里点一张＝撤销那一组，点「和张」＝取消和张，点「花牌」行＝取消那张花牌）。</li>
<li><b>立牌</b>（默认）：点出来的牌都算「手上其他牌」，即门前的暗手牌。</li>
<li><b>吃 / 碰 / 明杠 / 暗杠</b>：都是<b>先点按钮，再选牌</b>。
    <ul>
    <li>碰、明杠、暗杠：点一次牌就成立（碰 3 张、杠 4 张自动补齐）。</li>
    <li>吃：依次点出 3 张相连的同花色牌，例如 一萬 / 二萬 / 三萬。</li>
    </ul>
</li>
<li>立牌（含副露折算）<b>选满 13 张</b>后，下面会自动列出<b>听牌候选</b>，
每个候选上方是这一张牌的<b>总番数</b>。</li>
<li>点下面的候选牌，或者直接点上方牌区的牌，即得出<b>总番数 + 番种列表</b>。</li>
<li><b>和张</b>会单独显示。点「和张」那张牌可以取消重选。</li>
<li><b>重置</b>（橙色）：清空所有已选牌与副露，回到「立牌」模式。</li>
</ol>

<h3>二、特殊和牌方式</h3>
<ul>
<li><b>自摸</b>：勾上表示自己抓牌成和。</li>
<li><b>和绝张</b>：和的这张牌，牌池里只剩最后一张。</li>
<li>勾上「自摸」后，后面两个复选框变成 <b>杠上开花</b>、<b>妙手回春</b>；</li>
<li>没有勾「自摸」时，它们分别是 <b>抢杠和</b>、<b>海底捞月</b>。</li>
<li>花牌（春夏秋冬梅兰竹菊）：在选顶行点 8 张小图即可选/取消，下方「花牌」行会显示已选的花牌。
每张 <b>1 分</b>，<b>但不计入 8 分起和分</b>；花牌也不占 14 张手牌。</li>
</ul>

<h3>三、界面约定</h3>
<ul>
<li>副露里 <b>明杠 = 4 张全部正面</b>；<b>暗杠 = 面·背·背·面</b>（中间两张用牌背图）。</li>
<li>风圈、风位（东/南/西/北）<b>任何时候都可以点</b>，点了立刻重算。</li>
<li>所有设置（勾选项、风圈风位、花牌、窗口大小）都会<b>自动保存</b>，下次打开自动恢复。</li>
</ul>

<h3>四、算番口径</h3>
<ul>
<li>起和标准：<b>8 分</b>（花牌不计入）。不足 8 分会明确提示。</li>
<li>番种合计后按《规则》的<b>「不计」表</b>去重（必然并存的番种不重复计分）。</li>
<li>边张 / 坎张 / 单钓将：<b>听两种及以上牌时不计</b>（1998 领队会规定）。</li>
<li>点炮补成的刻子按<b>明刻</b>处理，不算暗刻（暗杠除外）。</li>
<li>暗杠既算暗刻、也单独计 2 分（《问答》第 41 条）。</li>
<li><b>七对</b>：由 7 个对子组成，<b>4 张相同的牌算作两对</b>
（如 一一一一 二二 三三 四四 五五 六六 即为七对）；
但这 4 张必须是<b>留在手里</b>的牌，<b>已报明杠/暗杠的 4 张不能再当两对</b>（杠属于副露，七对必须门前无副露）。
连七对则必须是<b>同一花色序数相连的 7 个对子</b>。</li>
<li>国标没有天和 / 地和 / 人和，界面也不提供。</li>
</ul>

<h3>五、给程序用的算番 API（重点）</h3>
<ul>
<li>算番的「API」就是 <code>mahjong_core.MahjongFanCalculator</code>，
<b>不需要 HTTP、不需要端口、不需要先启动谁</b>。</li>
<li><b>能 import 的语言</b>（Python 等）：<code>from mahjong_core import MahjongFanCalculator</code>，
或一行版 <code>score_hand("11123456789999m", win="9m")</code> —— 直接拿到番数。</li>
<li><b>不能 import 的语言 / Excel / 批处理</b>：直接把牌丢给本程序，算完就退出：<br>
<code>国标麻将算番器.exe --hand "11123456789999m" --win 9m --json</code><br>
开发时也可以 <code>python mahjong_core.py --hand "..." --json</code>。</li>
<li>牌写法三种（可混用）：<code>W1</code>（代码）、<code>一万</code>（中文）、
<code>11123456789999m</code>（简写：m 万 / s 索 / p 筒 / z 字牌，
字牌 1~4 东南西北、5~7 中发白）。</li>
<li>副露用 <code>--meld</code>：<code>chi:123m</code>、<code>peng:11z</code>、
<code>kong:5555z</code>（明杠）、<code>angang:7777z</code>（暗杠）。</li>
<li>听牌用 <code>--waits</code>（给 13−3×副露数 张）→ 每张听牌的番数；
其它选项：<code>--tsumo</code>（自摸）、<code>--last-tile</code>（和绝张）、
<code>--rob-kong</code>（抢杠和）、<code>--round 东 --seat 南 --flowers 2</code>。</li>
<li>默认输出 JSON；<code>--text</code> 输出人话；<code>--version</code> 看引擎信息；
<code>--fan-table</code> 导出 81 个番种表。算不出和牌时退出码 1、参数错退出码 2。</li>
</ul>

<h3>六、Web 版（手机 / 平板浏览器算番）</h3>
<ul>
<li>菜单「工具 → 启动 Web 版」（Ctrl+Alt+A）会在本机开一个网页服务，
默认 <b>http://127.0.0.1:8718</b>（只监听本机）。<b>这是给浏览器用的</b>，
不是给其它程序调用的接口（程序请用上面第一条的 <code>mahjong_core</code>）。</li>
<li><b>手机 / 平板算番</b>：勾上「工具 → 允许局域网访问（手机/平板）」，
手机浏览器打开弹出的地址就能用（页面与桌面版一致：牌池/副露/选项/听牌/算番）。
<b>默认不需要口令</b>。</li>
<li><b>牌太大/太小怎么办</b>：模式行里有「<b>布局：经典</b>」按钮，点一下就在
<b>经典（固定尺寸）</b>与 <b>自适应（随屏幕缩放）</b>之间切换，选择会记住。
默认是经典，与老版本画面一致；平板上可以切成自适应，牌会放大更好点。</li>
<li>地址可在「工具 → Web 版地址与用法」里查看（会复制手机链接到剪贴板）。</li>
<li>想加一道门槛：工具 → 设置访问口令（留空即取消）；还可以在
「免口令访问设置」里分项决定哪些内容不用口令。</li>
<li>只想用命令行起服务（比如开机自启）：
<code>python mahjong_api.py --host 0.0.0.0 --port 8718</code>（加 <code>--token 口令</code> 才要口令）。</li>
<li>平安提醒：端口只建议在自家网络开；口令只防随手访问，不要当强密码用。</li>
</ul>
"""

ABOUT_TEXT = """
<h3>%s</h3>
<p>版本: %s</p>
<p>按《中国麻将竞赛规则（试行）》1998 年国家体育总局颁布，
并结合杜维忠《〈中国麻将竞赛规则（试行）〉问答》整理实现。</p>
<p>60 分起和表的 81 个番种全部实现，规则数据可直接查看同目录
《国标麻将标准规则.json》。</p>
<p>算番引擎：mahjong_core.py；界面：PySide6。</p>
""" % (APP_NAME, __version__)


class AnonAccessDialog(QDialog):
    """免口令访问设置（v2.5.0）——设了口令后，勾中的这些「不用口令也能用」。

    只负责收集选择；实际重启服务由调用方（`MahjongFanWindow._api_set_anon`）做。
    """

    def __init__(self, current: List[str], token: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("免口令访问设置")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        tip = QLabel(
            "设了口令之后，下面勾中的项目**不输入口令也能用**（没勾的要口令）。\n"
            "口令留空时本就不校验口令，这里怎么勾都不影响。")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        if not token:
            warn = QLabel("⚠ 当前没有设口令 → 所有访问都不需要口令。")
            warn.setStyleSheet("color:#b45309;")
            warn.setWordWrap(True)
            lay.addWidget(warn)
        self.boxes: Dict[str, QCheckBox] = {}
        for key, label, detail in ANON_ITEMS:
            cb = QCheckBox(label)
            cb.setChecked(key in (current or []))
            cb.setToolTip(detail)
            self.boxes[key] = cb
            lay.addWidget(cb)
            sub = QLabel("　" + detail)
            sub.setStyleSheet("color:#6b7280; font-size:11px;")
            sub.setWordWrap(True)
            lay.addWidget(sub)
        row = QHBoxLayout()
        btn_all = QPushButton("全部允许")
        btn_all.setToolTip("勾上全部：谁都不用口令（方便但基本等于没防护）")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("全部要口令")
        btn_none.setToolTip("全部取消：每一类访问都要口令（最严格）")
        btn_none.clicked.connect(lambda: self._set_all(False))
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        row.addStretch(1)
        lay.addLayout(row)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("确定")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _set_all(self, on: bool) -> None:
        for cb in self.boxes.values():
            cb.setChecked(on)

    def selected(self) -> List[str]:
        """按 ANON_KEYS 顺序返回勾中的键（顺序固定，便于存设置/比对）"""
        return [k for k in ANON_KEYS if self.boxes[k].isChecked()]


# ------------------------------------------------------------------ 主窗口

class MahjongFanWindow(QMainWindow):
    """国标麻将算番器主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s v%s" % (APP_NAME, __version__))
        self.setWindowIcon(app_icon())        # ★ 窗口/任务栏图标（打包后也能从 exe 旁读到）
        self.resize(WIN_W, WIN_H)
        self.setMinimumSize(MIN_W, MIN_H)

        self.calc = MahjongFanCalculator() if MahjongFanCalculator else None
        self.concealed: Dict[int, int] = {}
        self.melds: List = []
        self.win_tile: Optional[int] = None
        self.mode = "stand"
        self.pending_chi: List[int] = []
        self.flowers: List[str] = []          # ★ 已选花牌（S1~S4/P1~P4，按 FLOWER_CODES 顺序）
        self.buttons: Dict[str, TileButton] = {}
        self.candidates: List[Tuple[int, object]] = []
        self._loading = True
        self._global_settings: dict = load_settings()
        self.api_server = None                # ★ 本地 HTTP API 服务（工具菜单里开/关）
        self.api_port = int(self._global_settings.get("api_port") or DEFAULT_API_PORT)
        self.api_auto_start = bool(self._global_settings.get("api_auto_start", False))
        self.api_lan = bool(self._global_settings.get("api_lan", False))
        self.api_token = str(self._global_settings.get("api_token") or "")
        # ★ v2.5.0：免口令白名单（设了口令后，哪些访问不用口令）
        _anon = self._global_settings.get("api_anon")
        self.api_anon: List[str] = ([k for k in ANON_KEYS if k in _anon]
                                   if isinstance(_anon, (list, tuple))
                                   else list(ANON_DEFAULT))

        self._build_ui()
        self._build_menu()
        self._connect_autosave()
        self._load_settings()
        self._loading = False
        self._refresh_all()
        if self.api_auto_start:
            self._api_start(silent=True)

    # ---------------------------------------------------------- 界面搭建
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_calc_page())
        self.stack.addWidget(self._build_fan_page())
        self.stack.addWidget(self._build_help_page())
        root.addWidget(self.stack, 1)

        # 底部导航（算番 / 番表 / 用法）
        nav = QFrame()
        nav.setFrameShape(QFrame.NoFrame)
        nav.setStyleSheet("background:#f4f6fa;border-top:1px solid #d8dee8;")
        nav_box = QHBoxLayout(nav)
        nav_box.setContentsMargins(0, 4, 0, 4)
        nav_box.setSpacing(0)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, (icon, text) in enumerate((("\U0001F9EE", "算番"),
                                            ("\U0001F4D6", "番表"),
                                            ("\u2753", "用法"))):
            btn = QPushButton("%s %s" % (icon, text))
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumHeight(38)
            btn.setStyleSheet(
                "QPushButton{border:none;color:#5b6472;font-size:14px;} "
                "QPushButton:checked{color:#2f7ff0;font-weight:bold;} "
                "QPushButton:hover{background:#eaf1fd;}")
            self.nav_group.addButton(btn, idx)
            nav_box.addWidget(btn, 1)
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_group.button(0).setChecked(True)
        root.addWidget(nav)

        self.setCentralWidget(central)

    # ---- 算番页
    def _build_calc_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(8)
        scroll.setWidget(content)

        # 1) 牌选择区
        box.addWidget(self._section_title("牌选择区",
                                          "左键加一张；已选的牌点角标 −1，"
                                          "或点下方已选牌取消"))
        pool = QGridLayout()
        pool.setHorizontalSpacing(4)
        pool.setVerticalSpacing(4)
        for r, row in enumerate(POOL_ROWS):
            for c, code in enumerate(row):
                btn = TileButton(code)
                btn.leftClicked.connect(self.on_tile_clicked)
                btn.rightClicked.connect(self.on_tile_right_clicked)
                self.buttons[code] = btn
                pool.addWidget(btn, r, c)
        # ★ 多余宽度全部让给右侧的空白列：牌是 setFixedSize 的固定尺寸，若不给
        #   QGridLayout 留一个「吃掉剩余宽度」的空列，9 列会被均匀撑宽，
        #   牌与牌之间就出现大片空隙（用户反馈「牌与牌之间不需要间隔这么宽」）。
        pool.setColumnStretch(max(len(row) for row in POOL_ROWS), 1)
        box.addLayout(pool)

        # 2) 操作按钮行（立牌 / 吃 / 碰 / 明杠 / 暗杠  重置）
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_row.addWidget(self._hint_label("模式"))
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for key, text in (("stand", "立牌"), ("chi", "吃"), ("peng", "碰"),
                          ("minggang", "明杠"), ("angang", "暗杠")):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumHeight(32)
            btn.setMinimumWidth(62)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{border:1px solid #ccd4e0;border-radius:4px;"
                "background:#ffffff;color:#333;} "
                "QPushButton:hover{background:#eef4ff;} "
                "QPushButton:checked{background:#2f7ff0;color:#fff;"
                "border:1px solid #2f7ff0;font-weight:bold;}")
            btn.setToolTip(self._mode_tip(key))
            self.mode_group.addButton(btn, ("stand", "chi", "peng",
                                            "minggang", "angang").index(key))
            mode_row.addWidget(btn)
            setattr(self, "btn_mode_" + key, btn)
        self.btn_mode_stand.setChecked(True)
        self.mode_group.idClicked.connect(self.on_mode_changed)

        self.btn_reset = QPushButton("\u91cd\u7f6e")
        self.btn_reset.setFocusPolicy(Qt.NoFocus)
        self.btn_reset.setMinimumHeight(32)
        self.btn_reset.setMinimumWidth(62)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(
            "QPushButton{border:1px solid #e8a552;border-radius:4px;"
            "background:#fdf0dd;color:#b9670d;font-weight:bold;} "
            "QPushButton:hover{background:#fbe3c4;}")
        self.btn_reset.clicked.connect(self.on_reset)
        mode_row.addWidget(self.btn_reset)
        mode_row.addStretch(1)
        box.addLayout(mode_row)

        # 3) 选项区（按设计图分四行：复选框 / 圈风 / 风位 / 花牌）
        #    行1：□自摸 □和绝张 □抢杠和 □海底捞月
        self.cb_tsumo = QCheckBox("自摸")
        self.cb_last_tile = QCheckBox("和绝张")
        self.cb_special_a = QCheckBox("抢杠和")
        self.cb_special_b = QCheckBox("海底捞月")
        self.cb_tsumo.setToolTip("自己抓进牌成和")
        self.cb_last_tile.setToolTip("和的这张牌，牌池中只剩最后一张")
        self.cb_special_a.setToolTip("勾选自摸时变为「杠上开花」")
        self.cb_special_b.setToolTip("勾选自摸时变为「妙手回春」")
        self.cb_tsumo.toggled.connect(self.on_tsumo_toggled)
        opt_row = QHBoxLayout()
        opt_row.setSpacing(14)
        for cb in (self.cb_tsumo, self.cb_last_tile,
                   self.cb_special_a, self.cb_special_b):
            opt_row.addWidget(cb)
        opt_row.addStretch(1)
        box.addLayout(opt_row)

        #    行2：○东风圈 ○南风圈 ○西风圈 ○北风圈
        round_row = QHBoxLayout()
        round_row.setSpacing(14)
        self.wind_round_group = QButtonGroup(self)
        self.wind_round_group.setExclusive(True)
        self.cb_round = []
        for i, w in enumerate(WIND_NAMES):
            rb = QRadioButton("%s风圈" % w)
            rb.setChecked(i == 0)
            self.wind_round_group.addButton(rb, i)
            self.cb_round.append(rb)
            round_row.addWidget(rb)
        round_row.addStretch(1)
        box.addLayout(round_row)

        #    行3：风位 ○东风位 ○南风位 ○西风位 ○北风位
        opt_row2 = QHBoxLayout()
        opt_row2.setSpacing(14)
        lbl_seat = QLabel("风位")
        lbl_seat.setStyleSheet("color:#9aa3ae;")
        opt_row2.addWidget(lbl_seat)
        self.wind_seat_group = QButtonGroup(self)
        self.wind_seat_group.setExclusive(True)
        self.cb_seat = []
        for i, w in enumerate(WIND_NAMES):
            rb = QRadioButton("%s风位" % w)
            rb.setChecked(i == 0)
            self.wind_seat_group.addButton(rb, i)
            self.cb_seat.append(rb)
            opt_row2.addWidget(rb)
        opt_row2.addStretch(1)
        box.addLayout(opt_row2)

        #    行4：花牌: [春 夏 秋 冬 梅 兰 竹 菊]  N 张
        flower_row = QHBoxLayout()
        flower_row.setSpacing(6)
        lbl_flower = QLabel("花牌:")
        lbl_flower.setStyleSheet("color:#9aa3ae;")
        flower_row.addWidget(lbl_flower)
        # ★ 8 个花牌按钮（S1~S4 = 春夏秋冬，P1~P4 = 梅兰竹菊）：点一下选/取消
        self.btn_flowers: Dict[str, TileButton] = {}
        for code in FLOWER_CODES:
            btn = TileButton(code, FLOWER_SIZE)
            btn.leftClicked.connect(self.on_flower_clicked)
            self.btn_flowers[code] = btn
            flower_row.addWidget(btn)
        flower_row.addSpacing(4)
        self.lbl_flower_count = QLabel("0 张")
        self.lbl_flower_count.setStyleSheet("color:#6b7684;")
        self.lbl_flower_count.setToolTip("花牌每张 1 分，但不计入 8 分起和分；"
                                         "也不占 14 张手牌")
        flower_row.addWidget(self.lbl_flower_count)
        flower_row.addStretch(1)
        box.addLayout(flower_row)

        # 任何选项变化都立即重算（风圈、风位、自摸、特殊番种、花牌）
        for cb in (self.cb_last_tile, self.cb_special_a, self.cb_special_b):
            cb.toggled.connect(self._on_option_changed)
        for rb in self.cb_round + self.cb_seat:
            rb.toggled.connect(self._on_option_changed)

        # 4) 已选牌区
        hand_frame = QFrame()
        hand_frame.setStyleSheet(
            "QFrame{background:#fbfcfe;border:1px solid #e2e8f0;"
            "border-radius:6px;}")
        hb = QVBoxLayout(hand_frame)
        hb.setContentsMargins(8, 6, 8, 6)
        hb.setSpacing(4)

        mrow = QHBoxLayout()
        mrow.setSpacing(6)
        self.lbl_melds_title = QLabel("副露")
        self.lbl_melds_title.setFixedWidth(52)
        self.lbl_melds_title.setStyleSheet("color:#6b7684;font-weight:bold;")
        mrow.addWidget(self.lbl_melds_title, 0, Qt.AlignTop)
        self.row_melds = TileRow(HAND_SIZE, "（暂无吃碰杠）", clickable=True)
        self.row_melds.clicked.connect(self.on_meld_row_clicked)
        mrow.addWidget(self.row_melds, 1)
        hb.addLayout(mrow)

        crow = QHBoxLayout()
        crow.setSpacing(6)
        self.lbl_hand_title = QLabel("立牌")
        self.lbl_hand_title.setFixedWidth(52)
        self.lbl_hand_title.setStyleSheet("color:#6b7684;font-weight:bold;")
        crow.addWidget(self.lbl_hand_title, 0, Qt.AlignTop)
        self.row_hand = TileRow(HAND_SIZE, "（请在牌选择区点牌）", clickable=True)
        self.row_hand.clicked.connect(self.on_hand_row_clicked)
        crow.addWidget(self.row_hand, 1)
        hb.addLayout(crow)

        wrow = QHBoxLayout()
        wrow.setSpacing(6)
        lbl_win = QLabel("和张")
        lbl_win.setFixedWidth(52)
        lbl_win.setStyleSheet("color:#6b7684;font-weight:bold;")
        wrow.addWidget(lbl_win, 0, Qt.AlignTop)
        self.row_win = TileRow(HAND_SIZE, "（未指定，选满 13 张后自动提示）",
                               clickable=True)
        self.row_win.clicked.connect(self.on_win_row_clicked)
        wrow.addWidget(self.row_win, 1)
        hb.addLayout(wrow)

        # ★ 花牌行（点上方「花牌」里的 8 张图选/取消）
        flrow = QHBoxLayout()
        flrow.setSpacing(6)
        self.lbl_flower_title = QLabel("花牌")
        self.lbl_flower_title.setFixedWidth(52)
        self.lbl_flower_title.setStyleSheet("color:#6b7684;font-weight:bold;")
        flrow.addWidget(self.lbl_flower_title, 0, Qt.AlignTop)
        self.row_flowers = TileRow(HAND_SIZE, "（未选花牌，点上方 8 张小图即可）",
                                   clickable=True)
        self.row_flowers.clicked.connect(self.on_flower_row_clicked)
        flrow.addWidget(self.row_flowers, 1)
        hb.addLayout(flrow)

        self.lbl_hint = QLabel("")
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("color:#2f7ff0;")
        hb.addWidget(self.lbl_hint)
        box.addWidget(hand_frame)

        # 5) 听牌候选区
        self.lbl_wait_title = QLabel("听牌候选")
        self.lbl_wait_title.setStyleSheet("color:#6b7684;font-weight:bold;")
        box.addWidget(self.lbl_wait_title)
        self.cand_area = QWidget()
        self.cand_layout = QHBoxLayout(self.cand_area)
        self.cand_layout.setContentsMargins(0, 0, 0, 0)
        self.cand_layout.setSpacing(6)
        self.cand_layout.addStretch(1)
        box.addWidget(self.cand_area)

        # 6) 算番结果
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame{background:#fbfcfe;border:1px solid #e2e8f0;"
            "border-radius:6px;}")
        rb = QVBoxLayout(res_frame)
        rb.setContentsMargins(10, 8, 10, 8)
        self.lbl_total = QLabel("共 0 番")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        self.lbl_total.setFont(f)
        self.lbl_total.setStyleSheet("color:#2f7ff0;border:none;")
        rb.addWidget(self.lbl_total)
        self.list_fans = QListWidget()
        self.list_fans.setFrameShape(QFrame.NoFrame)
        self.list_fans.setMinimumHeight(150)
        self.list_fans.setStyleSheet(
            "QListWidget{background:transparent;border:none;} "
            "QListWidget::item{padding:2px;}")
        rb.addWidget(self.list_fans)
        box.addWidget(res_frame)

        box.addStretch(1)
        return page

    def _section_title(self, title: str, tip: str = "") -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet("color:#6b7684;font-weight:bold;")
        lay.addWidget(lbl)
        if tip:
            t = QLabel(tip)
            t.setStyleSheet("color:#9aa3ae;font-size:12px;")
            lay.addWidget(t)
        lay.addStretch(1)
        return w

    def _hint_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#9aa3ae;")
        return lbl

    @staticmethod
    def _mode_tip(key: str) -> str:
        return {
            "stand": "立牌：点出的牌作为手上其他牌（门前暗手牌）",
            "chi": "吃：先点「吃」，再依次点出 3 张相连的同花色牌",
            "peng": "碰：先点「碰」，再点要碰的牌（自动补足 3 张）",
            "minggang": "明杠：先点「明杠」，再点要杠的牌（自动补足 4 张）",
            "angang": "暗杠：先点「暗杠」，再点要杠的牌（自动补足 4 张）",
        }.get(key, "")

    # ---- 番表页
    def _build_fan_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("搜索番种:"))
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("输入番种名称，如：清一色 / 龙 / 杠")
        self.ed_search.textChanged.connect(self.on_search_fan)
        search_row.addWidget(self.ed_search, 1)
        lay.addLayout(search_row)
        self.txt_fan = QTextBrowser()
        self.txt_fan.setOpenExternalLinks(False)
        lay.addWidget(self.txt_fan, 1)
        self._fill_fan_table()
        return page

    def _fill_fan_table(self) -> None:
        if self.calc is None:
            self.txt_fan.setHtml(
                "<p style='color:#c0392b'>算番引擎导入失败：%s</p>"
                % CORE_IMPORT_ERROR)
            self._fan_html = ""
            return
        rows = self.calc.fan_table()
        parts = ["<h3>国标麻将番种表（共 81 个番种 + 花牌）</h3>"]
        plain = ["国标麻将番种表（共 81 个番种 + 花牌）", ""]
        for value, items in rows:
            parts.append("<p style='margin-top:10px'><b style='color:#2f7ff0'>"
                         "%d 分</b></p>" % value)
            plain.append("【%d 分】" % value)
            for name, definition in items:
                parts.append(
                    "<p style='margin:2px 0 0 10px'><b>%s</b> "
                    "<span style='color:#5b6472'>%s</span></p>"
                    % (name, definition))
                plain.append("  %s  %s" % (name, definition))
            plain.append("")
        self._fan_html = "".join(parts)
        self._fan_plain = "\n".join(plain)
        self.txt_fan.setHtml(self._fan_html)

    def on_search_fan(self, text: str) -> None:
        text = (text or "").strip()
        if not hasattr(self, "_fan_plain"):
            return
        if not text:
            self.txt_fan.setHtml(self._fan_html)
            return
        groups: List[Tuple[str, str]] = []
        header = ""
        for ln in self._fan_plain.splitlines():
            if ln.startswith("【"):
                header = ln
            elif text in ln:
                groups.append((header, ln.strip()))
        if not groups:
            self.txt_fan.setHtml(
                "<h3>搜索结果：%s</h3><p>（没有找到相关番种）</p>" % text)
            return
        parts = ["<h3>搜索结果：%s</h3>" % text]
        cur = None
        for head, ln in groups:
            if head != cur:
                if head:
                    parts.append("<p style='margin-top:8px'>"
                                 "<b style='color:#2f7ff0'>%s</b></p>" % head)
                cur = head
            parts.append("<p style='margin:2px 0 0 10px'>%s</p>" % ln)
        self.txt_fan.setHtml("".join(parts))

    # ---- 用法页
    def _build_help_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 10, 12, 10)
        self.txt_help = QTextBrowser()
        self.txt_help.setHtml(HELP_TEXT)
        lay.addWidget(self.txt_help, 1)
        return page

    def _build_menu(self) -> None:
        bar = self.menuBar()
        m_file = bar.addMenu("文件(&F)")
        act_quit = QAction("退出(&Q)", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)
        # ★ 工具：Web 版（手机/平板浏览器算番）——**不是给程序调用的接口**，
        #   程序间调用请直接用 mahjong_core（见帮助页）
        m_tool = bar.addMenu("工具(&T)")
        self.act_api = QAction("启动 Web 版(&W)", self)
        self.act_api.setCheckable(True)
        self.act_api.setShortcut("Ctrl+Alt+A")
        self.act_api.setToolTip("给手机/平板浏览器用的 Web 版（默认 http://127.0.0.1:8718）\n"
                                "别的程序要算番请直接用 mahjong_core：import 或命令行调用，\n"
                                "不需要 HTTP、不需要端口、不需要先启动谁")
        self.act_api.triggered.connect(self._api_toggle)
        m_tool.addAction(self.act_api)
        self.act_api_lan = QAction("允许局域网访问（手机/平板）", self)
        self.act_api_lan.setCheckable(True)
        self.act_api_lan.setToolTip("勾上后服务绑到 0.0.0.0：同一 WiFi 下的手机/平板\n"
                                    "用浏览器打开 http://电脑IP:端口 即可算番（默认不要口令）")
        self.act_api_lan.triggered.connect(self._api_lan_toggle)
        m_tool.addAction(self.act_api_lan)
        # ★ 保存为属性：测试与内部逻辑都直接引用，不要靠遍历 menuBar().actions() 去找
        #   （遍历时拿到已失效的 QMenu 包装会报 "already deleted"，v2.5.0 踩过）
        act_api_token = QAction("设置访问口令(&K)…", self)
        act_api_token.triggered.connect(self._api_set_token)
        self.act_api_token = act_api_token
        m_tool.addAction(act_api_token)
        act_api_anon = QAction("免口令访问设置(&N)…", self)
        act_api_anon.setToolTip("设了口令后，哪些东西可以不输入口令直接用（含 Web 客户端）")
        act_api_anon.triggered.connect(self._api_set_anon)
        self.act_api_anon = act_api_anon
        m_tool.addAction(act_api_anon)
        act_api_info = QAction("Web 版地址与用法(&I)…", self)
        act_api_info.triggered.connect(self._api_show_info)
        m_tool.addAction(act_api_info)
        act_api_port = QAction("Web 版端口设置(&P)…", self)
        act_api_port.triggered.connect(self._api_set_port)
        m_tool.addAction(act_api_port)
        m_help = bar.addMenu("帮助(&H)")
        act_help = QAction("用法说明(&H)", self)
        act_help.triggered.connect(lambda: self._goto_page(2))
        act_fan = QAction("番种表(&T)", self)
        act_fan.triggered.connect(lambda: self._goto_page(1))
        act_about = QAction("关于(&A)", self)
        act_about.triggered.connect(self.show_about)
        m_help.addAction(act_help)
        m_help.addAction(act_fan)
        m_help.addSeparator()
        m_help.addAction(act_about)

    def _goto_page(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self.nav_group.button(idx).setChecked(True)

    def show_about(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("关于 " + APP_NAME)
        box.setTextFormat(Qt.RichText)
        box.setText(ABOUT_TEXT)
        box.setIcon(QMessageBox.Information)
        box.exec()

    # ---------------------------------------------------------- Web 版（手机/平板浏览器）
    #   注意：这组方法管的是「Web 版服务」，**不是**给其它程序调用的 API ——
    #   程序间调用请用 mahjong_core（import 或命令行，见文件头与帮助页）。
    def _api_running(self) -> bool:
        return bool(self.api_server is not None and self.api_server.running)

    def _api_host(self) -> str:
        """局域网访问 → 0.0.0.0；否则只绑本机 127.0.0.1"""
        return "0.0.0.0" if self.api_lan else "127.0.0.1"

    @staticmethod
    def _api_gen_token() -> str:
        """6 位数字口令（手机上好输）

        ★ v2.6.0：**不再自动使用** —— Web 版默认完全不要口令；
          这里留着只是给「想随手捏一个口令」的场景（比如以后加个按钮）。
        """
        return "%06d" % random.randrange(1000000)

    def _api_watch_url(self) -> str:
        """手机上应打开的地址（设了口令才附 ?token=；默认不需要口令）"""
        ip = lan_ip_() if self.api_lan else "127.0.0.1"
        url = "http://%s:%d/" % (ip, self.api_port)
        if self.api_token:
            url += "?token=" + self.api_token
        return url

    def _api_start(self, silent: bool = False) -> bool:
        """启动 Web 版服务（给手机/平板浏览器用；失败不影响主程序）

        ★ 注意：这**不是**给其它程序调用的「API」。程序间调用请直接用 `mahjong_core`：
          `from mahjong_core import MahjongFanCalculator` 或
          `国标麻将算番器.exe --hand "..." --json`（不需要 HTTP / 端口 / 先启动谁）。
        """
        if self._api_running():
            return True
        if ApiServer_ is None:
            if not silent:
                QMessageBox.warning(self, "Web 版不可用",
                                    "缺少 mahjong_api.py 或导入失败：\n%s" % API_IMPORT_ERROR)
            return False
        srv = ApiServer_(self._api_host(), self.api_port, self.api_token,
                         anon=tuple(self.api_anon))
        try:
            url = srv.start()
        except Exception as exc:       # noqa: BLE001
            msg = getattr(exc, "message", None) or str(exc)
            self.statusBar().showMessage("Web 版启动失败：%s" % msg, 6000)
            if not silent:
                QMessageBox.warning(self, "Web 版启动失败",
                                    "%s\n\n可在「工具 → Web 版端口设置」里换一个端口。" % msg)
            return False
        self.api_server = srv
        self.api_port = srv.port_actual
        self.api_auto_start = True
        if getattr(self, "act_api", None) is not None:
            self.act_api.setChecked(True)
            self.act_api.setText("停止 Web 版(&W)")
        if getattr(self, "act_api_lan", None) is not None:
            self.act_api_lan.setChecked(self.api_lan)
        if self.api_lan:
            self.statusBar().showMessage("Web 版已开启（局域网）：%s" % self._api_watch_url(), 8000)
        else:
            self.statusBar().showMessage("Web 版已开启（仅本机）：%s" % url, 6000)
        self._autosave_settings()
        return True

    def _api_stop(self, silent: bool = False, remember: bool = True) -> None:
        """停止 Web 版服务；remember=False 表示只是退出程序时的清理（下次启动仍自动开）"""
        srv, self.api_server = self.api_server, None
        if srv is not None:
            try:
                srv.stop()
            except Exception:       # noqa: BLE001
                pass
        if remember:
            self.api_auto_start = False
        if getattr(self, "act_api", None) is not None:
            self.act_api.setChecked(False)
            self.act_api.setText("启动 Web 版(&W)")
        if srv is not None and not silent:
            self.statusBar().showMessage("Web 版已停止", 4000)
        if remember:
            self._autosave_settings()

    def _api_toggle(self, checked: bool) -> None:
        if checked:
            if not self._api_start():
                self.act_api.setChecked(False)
                self.act_api.setText("启动 Web 版(&W)")
        else:
            self._api_stop()

    def _api_show_info(self) -> None:
        if not self._api_running():
            self._api_start(silent=True)
        if not self._api_running():
            QMessageBox.information(
                self, "Web 版（手机/平板）",
                "服务未启动。用「工具 → 启动 Web 版」（Ctrl+Alt+A）即可开启。\n\n"
                "默认只监听本机 127.0.0.1:%d；要让手机/平板用，请勾上"
                "「允许局域网访问」。\n\n"
                "★ 这是给**浏览器**看的网页版。其它程序要算番请直接用 mahjong_core：\n"
                "import 它，或用命令行调用本程序：\n"
                "  国标麻将算番器.exe --hand \"11123456789999m\" --win 9m --json"
                % self.api_port)
            return
        home = "http://127.0.0.1:%d/" % self.api_port
        phone = self._api_watch_url()
        try:
            QApplication.clipboard().setText(phone)
            copied = "（手机链接已复制到剪贴板，发到手机上直接打开即可）"
        except Exception:           # noqa: BLE001
            copied = ""
        lan_note = ("已开启局域网访问：同一 WiFi 下的手机/平板可直接用。"
                    if self.api_lan else
                    "当前仅本机可用；要让手机用，请勾上「允许局域网访问」。")
        QMessageBox.information(
            self, "Web 版（手机/平板）",
            "本机浏览器：%s\n手机/平板：%s\n%s\n\n%s\n\n"
            "访问口令：%s\n免口令访问：%s\n"
            "（Web 页面自带牌池/选项/听牌/算番，和桌面版一致；\n"
            "也可直接在浏览器地址栏访问该地址。默认不需要口令。）\n\n"
            "★ 给其它程序用的算番入口不是这里，而是 **mahjong_core**：\n"
            "  import 方式：from mahjong_core import MahjongFanCalculator\n"
            "  进程方式 ：国标麻将算番器.exe --hand \"11123456789999m\" --json\n"
            "（都不需要 HTTP、不需要端口、不需要先启动谁）\n\n"
            "页面内部使用的 JSON 路由：/api/score、/api/waits、/api/fan_table 等，"
            "详见 /api/help，自测页在 /debug"
            % (home, phone, copied, lan_note,
               self.api_token or "（未设置 → 不需要口令）",
               self._anon_text()))

    def _api_lan_toggle(self, checked: bool) -> None:
        """允许局域网访问：重启服务（★ 默认不生成口令 —— Web 版可以完全不要密码）"""
        self.api_lan = bool(checked)
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self._autosave_settings()
        if was_running:
            self._api_start(silent=True)
        if self.api_lan:
            QMessageBox.information(
                self, "已允许局域网访问",
                "手机/平板用浏览器打开下面这个地址即可算番（同一 WiFi，**不需要口令**）：\n\n%s\n\n"
                "想加一道门槛再自己设：工具 → 设置访问口令（可随手取消）。"
                % self._api_watch_url())
        else:
            self.statusBar().showMessage("已关闭局域网访问（回到仅本机）", 5000)

    def _api_set_token(self) -> None:
        """可选的访问口令（默认不需要口令；留空就回到免口令）"""
        text, ok = QInputDialog.getText(self, "访问口令",
                                        "口令（默认不需要；留空 = 不校验）：",
                                        text=self.api_token)
        if not ok:
            return
        self.api_token = str(text or "").strip()
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
            self._api_start(silent=True)
        self._autosave_settings()
        if was_running:
            self.statusBar().showMessage("口令已更新：%s" % (self.api_token or "（不校验）"), 5000)

    def _anon_text(self) -> str:
        """把当前免口令设置说成人话（状态栏/提示框用）"""
        if not self.api_token:
            return "未设口令 → 所有访问都不需要口令"
        if not self.api_anon:
            return "全部需要口令"
        names = {k: label.split("（")[0] for k, label, _ in ANON_ITEMS}
        return "免口令：" + "、".join(names.get(k, k) for k in self.api_anon)

    def _api_set_anon(self) -> None:
        """免口令访问设置（含 Web 客户端）：改完存盘 + 重启服务"""
        dlg = AnonAccessDialog(list(self.api_anon), self.api_token or "", self)
        if dlg.exec() != QDialog.Accepted:
            return
        picked = dlg.selected()
        if picked == self.api_anon:
            return
        self.api_anon = picked
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self._autosave_settings()
        if was_running:
            self._api_start(silent=True)
        self.statusBar().showMessage("免口令访问已更新：%s" % self._anon_text(), 6000)

    def _api_set_port(self) -> None:
        port, ok = QInputDialog.getInt(self, "Web 版端口设置",
                                       "监听端口（1024~65535）：", self.api_port,
                                       1024, 65535, 1)
        if not ok:
            return
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self.api_port = int(port)
        self._autosave_settings()
        if was_running and not self._api_start(silent=True):
            QMessageBox.warning(self, "端口不可用",
                                "新端口 %d 无法监听，已保持停止状态，可再换一个端口。" % port)
        elif was_running:
            self.statusBar().showMessage("Web 版已在新端口重启：%s" % self.api_server.url, 5000)

    # ---------------------------------------------------------- 设置持久化
    def _collect_settings(self) -> dict:
        g = self.geometry()
        return {
            "geometry": [g.x(), g.y(), g.width(), g.height()],
            "geo_ver": GEO_VER,
            "window_maximized": self.isMaximized(),
            "wind_round": self._wind_round(),
            "wind_seat": self._wind_seat(),
            "flowers": len(self.flowers),
            "flowers_picked": list(self.flowers),
            "tsumo": bool(self.cb_tsumo.isChecked()),
            "last_tile": bool(self.cb_last_tile.isChecked()),
            "special_a": bool(self.cb_special_a.isChecked()),
            "special_b": bool(self.cb_special_b.isChecked()),
            "mode": self.mode,
            "page": self.stack.currentIndex(),
            "api_port": int(self.api_port),
            "api_auto_start": bool(self.api_auto_start),
            "api_lan": bool(self.api_lan),
            "api_token": str(self.api_token or ""),
            "api_anon": list(self.api_anon),
        }

    def _apply_settings(self, s: dict) -> None:
        for w in (self.cb_tsumo, self.cb_last_tile,
                  self.cb_special_a, self.cb_special_b):
            w.blockSignals(True)
        if s.get("wind_round") in WIND_NAMES:
            self.cb_round[WIND_NAMES.index(s["wind_round"])].setChecked(True)
        if s.get("wind_seat") in WIND_NAMES:
            self.cb_seat[WIND_NAMES.index(s["wind_seat"])].setChecked(True)
        picks = s.get("flowers_picked")
        if isinstance(picks, (list, tuple)):
            self.flowers = [c for c in FLOWER_CODES if c in picks]
        else:                     # 兼容旧设置（只存张数）
            try:
                n = max(0, min(8, int(s.get("flowers", 0) or 0)))
            except Exception:     # noqa: BLE001
                n = 0
            self.flowers = FLOWER_CODES[:n]
        self.cb_tsumo.setChecked(bool(s.get("tsumo", False)))
        self.cb_last_tile.setChecked(bool(s.get("last_tile", False)))
        self._update_special_labels()
        self.cb_special_a.setChecked(bool(s.get("special_a", False)))
        self.cb_special_b.setChecked(bool(s.get("special_b", False)))
        for w in (self.cb_tsumo, self.cb_last_tile,
                  self.cb_special_a, self.cb_special_b):
            w.blockSignals(False)
        geo = s.get("geometry")
        try:
            geo_ver = int(s.get("geo_ver") or 1)
        except Exception:       # noqa: BLE001
            geo_ver = 1
        if isinstance(geo, (list, tuple)) and len(geo) == 4:
            try:
                gw, gh = int(geo[2]), int(geo[3])
                # ★ v2.4.3：牌池已经收拢，窗口不用那么宽。旧版（牌铺开 + 最小宽度 1020）
                #   存下的几何在首次升级时一次性收紧到新默认宽度（用 geo_ver 标记，
                #   只做一次 —— 以后用户手动拉宽会存成 geo_ver=2，不会再被动收紧）。
                if geo_ver < GEO_VER:
                    gw = WIN_W
                self.setGeometry(int(geo[0]), int(geo[1]),
                                 max(MIN_W, gw), max(MIN_H, gh))
            except Exception:   # noqa: BLE001
                pass
        mode = s.get("mode")
        if mode in ("stand", "chi", "peng", "minggang", "angang"):
            getattr(self, "btn_mode_" + mode).setChecked(True)
            self.mode = mode
        page = s.get("page")
        if isinstance(page, int) and 0 <= page <= 2:
            self._goto_page(page)
        try:
            self.api_port = int(s.get("api_port") or DEFAULT_API_PORT)
        except Exception:           # noqa: BLE001
            self.api_port = DEFAULT_API_PORT
        self.api_auto_start = bool(s.get("api_auto_start", False))
        self.api_lan = bool(s.get("api_lan", False))
        self.api_token = str(s.get("api_token") or "")
        # ★ v2.5.0：免口令白名单；老设置（没这个键）回退默认，行为不变
        picks_anon = s.get("api_anon")
        if isinstance(picks_anon, (list, tuple)):
            self.api_anon = [k for k in ANON_KEYS if k in picks_anon]
        else:
            self.api_anon = list(ANON_DEFAULT)
        if getattr(self, "act_api_lan", None) is not None:
            self.act_api_lan.setChecked(self.api_lan)

    def _connect_autosave(self) -> None:
        for w in (self.cb_tsumo, self.cb_last_tile,
                  self.cb_special_a, self.cb_special_b):
            w.toggled.connect(self._autosave_settings)
        for rb in self.cb_round + self.cb_seat:
            rb.toggled.connect(self._autosave_settings)
        self.timer_autosave = QTimer(self)
        self.timer_autosave.setSingleShot(True)
        self.timer_autosave.setInterval(500)
        self.timer_autosave.timeout.connect(self._save_settings_now)

    def _autosave_settings(self, *args) -> None:      # noqa: ARG002
        if self._loading:
            return
        self.timer_autosave.start()

    def _save_settings_now(self) -> bool:
        ok = save_settings(self._collect_settings())
        if ok:
            self.statusBar().showMessage("设置已自动保存", 1500)
        return ok

    def _load_settings(self) -> None:
        self._apply_settings(self._global_settings or {})

    def closeEvent(self, event):       # noqa: N802
        try:
            self.timer_autosave.stop()
        except Exception:       # noqa: BLE001
            pass
        # ★ 先关本地 API（记住「下次启动自动开」的状态），再存设置
        self._api_stop(silent=True, remember=False)
        self._save_settings_now()
        super().closeEvent(event)

    # ---------------------------------------------------------- 状态辅助
    def _wind_round(self) -> str:
        return WIND_NAMES[self.wind_round_group.checkedId()
                          if self.wind_round_group.checkedId() >= 0 else 0]

    def _wind_seat(self) -> str:
        return WIND_NAMES[self.wind_seat_group.checkedId()
                          if self.wind_seat_group.checkedId() >= 0 else 0]

    def _options(self):
        tsumo = self.cb_tsumo.isChecked()
        a = self.cb_special_a.isChecked()
        b = self.cb_special_b.isChecked()
        return Options(
            tsumo=tsumo,
            last_tile=self.cb_last_tile.isChecked(),
            rob_kong=bool(a and not tsumo),
            last_discard=bool(b and not tsumo),
            kong_bloom=bool(a and tsumo),
            last_draw=bool(b and tsumo),
            round_wind=self._wind_round(),
            seat_wind=self._wind_seat(),
            flowers=len(self.flowers),
        )

    def _concealed_list(self) -> List[int]:
        out: List[int] = []
        for tid in sorted(self.concealed):
            out.extend([tid] * self.concealed[tid])
        return out

    def _physical_counts(self) -> Dict[int, int]:
        used: Dict[int, int] = dict(self.concealed)
        for m in self.melds:
            used[m.tiles[0]] = used.get(m.tiles[0], 0) + len(m.tiles)
        if self.win_tile is not None:
            used[self.win_tile] = used.get(self.win_tile, 0) + 1
        return used

    def _need_concealed(self) -> int:
        """立牌应有张数（13 张听牌口径）"""
        return 13 - 3 * len(self.melds)

    # ---------------------------------------------------------- 交互
    def on_mode_changed(self, idx: int) -> None:
        self.mode = ("stand", "chi", "peng", "minggang", "angang")[idx]
        self.pending_chi = []
        self._refresh_all()
        self._autosave_settings()

    def _on_option_changed(self, *args) -> None:      # noqa: ARG002
        self._refresh_all()
        self._autosave_settings()

    def on_tsumo_toggled(self, checked: bool) -> None:    # noqa: ARG002
        self._update_special_labels(reset=True)
        self._refresh_all()

    def _update_special_labels(self, reset: bool = False) -> None:
        """自摸勾选后：杠上开花 / 妙手回春；未勾选：抢杠和 / 海底捞月"""
        tsumo = self.cb_tsumo.isChecked()
        self.cb_special_a.setText("杠上开花" if tsumo else "抢杠和")
        self.cb_special_b.setText("妙手回春" if tsumo else "海底捞月")
        if reset:
            # 语义变了，清掉旧勾选，避免误算
            for cb in (self.cb_special_a, self.cb_special_b):
                if cb.isChecked():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

    def on_flower_clicked(self, code: str) -> None:
        """点花牌图：选中 / 取消（花牌每张 1 分，不计入起和分）"""
        if code in self.flowers:
            self.flowers.remove(code)
            self.statusBar().showMessage("取消花牌 %s" % FLOWER_NAMES.get(code, code), 1500)
        else:
            self.flowers.append(code)
            self.flowers = [c for c in FLOWER_CODES if c in self.flowers]
            self.statusBar().showMessage("选中花牌 %s（共 %d 张，%d 分）"
                                         % (FLOWER_NAMES.get(code, code),
                                            len(self.flowers), len(self.flowers)), 1500)
        self._refresh_all()
        self._autosave_settings()

    def on_reset(self) -> None:
        """★ 全部重置（v2.4.4）：手牌 / 副露 / 和张 / 待选 / 模式 / 花牌 /
        自摸·和绝张·抢杠和·海底捞月 / 圈风 / 风位 —— 一律回到初始状态，并立即存进设置
        """
        self.concealed.clear()
        self.melds = []
        self.win_tile = None
        self.pending_chi = []
        self.flowers = []
        self.mode = "stand"
        # 控件状态一起回位（blockSignals：一次性重置，不要每改一个就重算/存盘一遍）
        widgets = [self.btn_mode_stand, self.cb_tsumo, self.cb_last_tile,
                   self.cb_special_a, self.cb_special_b,
                   self.cb_round[0], self.cb_seat[0]]
        for w in widgets:
            w.blockSignals(True)
        try:
            self.btn_mode_stand.setChecked(True)        # 模式回「立牌」
            for cb in (self.cb_tsumo, self.cb_last_tile,
                       self.cb_special_a, self.cb_special_b):
                cb.setChecked(False)                    # 四个选项复选框全不勾
            self.cb_round[0].setChecked(True)           # 圈风回「东风圈」
            self.cb_seat[0].setChecked(True)            # 风位回「东风位」
            self._update_special_labels()               # 文案回「抢杠和 / 海底捞月」
        finally:
            for w in widgets:
                w.blockSignals(False)
        self._refresh_all()
        self.statusBar().showMessage(
            "已全部重置：手牌 · 副露 · 和张 · 花牌 · 选项 · 风圈风位", 3000)
        self._autosave_settings()

    def on_tile_right_clicked(self, code: str) -> None:
        tid = tile_of(code)
        if self.mode == "chi" and self.pending_chi:
            self.pending_chi.pop()
            self._refresh_all()
            return
        if self.concealed.get(tid):
            self.concealed[tid] -= 1
            if self.concealed[tid] <= 0:
                self.concealed.pop(tid, None)
            self._refresh_all()
            return
        if self.win_tile == tid:
            self.win_tile = None
            self._refresh_all()

    # -------------------------------------- 点已选牌取消（★ v2.7.2，没有右键也能操作）
    # 手机 / 触屏没有右键，所以「已选牌」区的每一张牌都可以直接点：点一下＝取消这张；
    # 牌选择区的红角标同理（点一下 −1）。右键仍保留，鼠标用户习惯不变。
    def on_hand_row_clicked(self, code) -> None:
        """点「立牌」区的一张牌＝取消这一张"""
        if not isinstance(code, str):
            return
        tid = tile_of(code)
        if not self.concealed.get(tid):
            return
        self.concealed[tid] -= 1
        if self.concealed[tid] <= 0:
            self.concealed.pop(tid, None)
        self._refresh_all()
        self.statusBar().showMessage("已取消一张 %s" % name_of(tid), 1500)

    def on_win_row_clicked(self, code=None) -> None:      # noqa: ARG002
        """点「和张」＝取消和张（再点牌区的牌可以重新指定）"""
        if self.win_tile is None:
            return
        msg = "已取消和张 %s" % name_of(self.win_tile)
        self.win_tile = None
        self._refresh_all()
        self.statusBar().showMessage(msg, 2000)

    def on_meld_row_clicked(self, group) -> None:
        """点副露里的一张牌＝撤销这一组副露（原来只能整个「重置」）"""
        if not isinstance(group, int) or not (0 <= group < len(self.melds)):
            return
        m = self.melds.pop(group)
        if m.kind == "kong":
            kind = "暗杠" if m.concealed else "明杠"
        elif m.kind == "pong":
            kind = "碰"
        else:
            kind = "吃"
        self.win_tile = None          # 副露变了，和张要重新指定
        self._refresh_all()
        self.statusBar().showMessage(
            "已撤销%s %s（点错了可以重新选）" % (kind, name_of(m.tiles[0])), 2500)

    def on_flower_row_clicked(self, code) -> None:
        """点「花牌」行的一张＝取消这张花牌"""
        if isinstance(code, str) and code in self.flowers:
            self.on_flower_clicked(code)

    def on_tile_clicked(self, code: str) -> None:
        tid = tile_of(code)
        if self.mode == "stand":
            self._add_concealed(tid)
        elif self.mode == "chi":
            self.pending_chi.append(tid)
            if len(self.pending_chi) == 3:
                self._finish_chi()
        elif self.mode in ("peng", "minggang", "angang"):
            self._finish_meld(self.mode, tid)
        self._refresh_all()

    def _add_concealed(self, tid: int) -> None:
        used = self._physical_counts()
        if used.get(tid, 0) >= 4:
            self.statusBar().showMessage("这种牌最多 4 张", 2500)
            return
        need = self._need_concealed()
        cur = sum(self.concealed.values())
        if cur + (1 if self.win_tile is not None else 0) >= 14 - 3 * len(self.melds):
            self.statusBar().showMessage("已经满 14 张了，先「重置」或点已选的牌减一张", 3000)
            return
        if cur < need:
            self.concealed[tid] = self.concealed.get(tid, 0) + 1
        else:
            # 已经满 13 张，这一张直接作为「和张」
            self.win_tile = tid

    def _finish_meld(self, kind: str, tid: int) -> None:
        if len(self.melds) >= 4:
            self.statusBar().showMessage("副露最多 4 组", 3000)
            return
        used = self._physical_counts()
        n = 4 if kind in ("minggang", "angang") else 3
        if used.get(tid, 0) + n > 4:
            self.statusBar().showMessage("这种牌最多 4 张", 3000)
            return
        if sum(self.concealed.values()) > 13 - 3 * (len(self.melds) + 1):
            self.statusBar().showMessage("立牌里的牌太多，先减几张再做副露", 3000)
            return
        if kind == "peng":
            self.melds.append(Meld("pong", (tid, tid, tid), False))
        elif kind == "minggang":
            self.melds.append(Meld("kong", (tid, tid, tid, tid), False))
        else:
            self.melds.append(Meld("kong", (tid, tid, tid, tid), True))
        self.pending_chi = []
        self.win_tile = None
        self.statusBar().showMessage(
            "%s 完成" % {"peng": "碰", "minggang": "明杠",
                         "angang": "暗杠"}[kind], 2000)

    def _finish_chi(self) -> None:
        tids = sorted(self.pending_chi)
        self.pending_chi = []
        if len(set(tids)) != 3 or not all(is_suit(t) for t in tids) or \
                len({suit_of(t) for t in tids}) != 1 or \
                tids[1] != tids[0] + 1 or tids[2] != tids[1] + 1:
            self.statusBar().showMessage(
                "吃需要 3 张相连的同花色牌，请重新选择", 3500)
            return
        if len(self.melds) >= 4:
            self.statusBar().showMessage("副露最多 4 组", 3000)
            return
        used = self._physical_counts()
        if any(used.get(t, 0) + 1 > 4 for t in tids):
            self.statusBar().showMessage("有牌超过了 4 张", 3000)
            return
        if sum(self.concealed.values()) > 13 - 3 * (len(self.melds) + 1):
            self.statusBar().showMessage("立牌里的牌太多，先减几张再吃", 3000)
            return
        self.melds.append(Meld("chi", tuple(tids), False))
        self.win_tile = None
        self.statusBar().showMessage("吃 完成", 2000)

    # ---------------------------------------------------------- 刷新与算番
    def _refresh_all(self, *args) -> None:       # noqa: ARG002
        self._update_special_labels()
        # 牌区计数徽标
        for code, btn in self.buttons.items():
            tid = tile_of(code)
            n = self.concealed.get(tid, 0)
            if self.mode == "chi":
                n += self.pending_chi.count(tid)
            if self.win_tile == tid:
                n += 1
            btn.set_count(n)
        # 副露（★ 点某一张＝撤销那一组副露）
        items = self._meld_items()
        self.row_melds.set_tiles([c for c, _ in items],
                                 [g for _, g in items],
                                 "点一下撤销这一组副露")
        # 立牌（★ 点某一张＝减一张，不用右键）
        hand_codes = [code_of(t) for t in self._concealed_list()]
        self.row_hand.set_tiles(hand_codes, list(hand_codes),
                                "点一下减一张（等于右键）")
        # 和张（★ 点一下＝取消和张）
        if self.win_tile is not None:
            wcode = code_of(self.win_tile)
            self.row_win.set_tiles([wcode], [wcode], "点一下取消和张")
        else:
            self.row_win.set_tiles([])
        # 花牌（点上方 8 张小图选/取消）
        for code, btn in self.btn_flowers.items():
            btn.set_selected(code in self.flowers)
        self.lbl_flower_count.setText("%d 张" % len(self.flowers))
        self.row_flowers.set_tiles(list(self.flowers), list(self.flowers),
                                   "点一下取消这张花牌")
        self._update_wait_area()
        self._update_result()

    def _meld_items(self) -> List[Tuple[str, Optional[int]]]:
        """副露渲染项：`(牌编码, 组号)`，组间是 `(GAP, None)`。

        ★ v2.7.2：带上组号是为了「点已选牌取消」—— 点副露里的任何一张
        （含暗杠的牌背）＝ 撤销那一组副露。
        """
        out: List[Tuple[str, Optional[int]]] = []
        for gi, m in enumerate(self.melds):
            if out:
                out.append((GAP, None))
            if m.kind == "kong" and m.concealed:
                # 暗杠：面 · 背 · 背 · 面
                out.extend([(code_of(m.tiles[0]), gi), (BACK_TILE, gi),
                            (BACK_TILE, gi), (code_of(m.tiles[0]), gi)])
            else:
                out.extend([(code_of(t), gi) for t in m.tiles])
        return out

    def _meld_codes(self) -> List[str]:
        """只取牌编码（不需要点击的地方用）"""
        return [c for c, _ in self._meld_items()]

    def _update_wait_area(self) -> None:
        clear_layout(self.cand_layout)
        self.candidates = []
        cur = sum(self.concealed.values())
        need = self._need_concealed()
        total_cap = 14 - 3 * len(self.melds)

        if self.calc is None:
            self.lbl_hint.setText("算番引擎不可用：%s" % CORE_IMPORT_ERROR)
            self.lbl_wait_title.setText("听牌候选")
            self.cand_layout.addStretch(1)
            return

        if cur + (1 if self.win_tile is not None else 0) > total_cap:
            self.lbl_hint.setText(
                "牌数超出（立牌 %d + 和张 %d > %d），请点已选的牌减一张或重置"
                % (cur, 1 if self.win_tile is not None else 0, total_cap))
        elif self.win_tile is None and cur == need:
            self.lbl_hint.setText("已选满 %d 张，下面列出可以和的牌" % need)
        elif self.win_tile is None and cur < need:
            self.lbl_hint.setText("还需选择 %d 张牌（当前 %d / %d）"
                                  % (need - cur, cur, need))
        elif self.win_tile is not None:
            self.lbl_hint.setText("和张：%s（点下方候选或牌区的牌可换）"
                                  % name_of(self.win_tile))
        else:
            self.lbl_hint.setText("")

        if self.win_tile is None and cur == need and need > 0:
            masked = self._concealed_list()
            opts = self._options()
            for t in self.calc.waiting_tiles(self.melds, masked):
                s = self.calc.score(self.melds, masked + [t], t, opts)
                if s.message and not s.fans:
                    continue
                self.candidates.append((t, s))
            self.candidates.sort(key=lambda kv: -kv[1].total)
            self.lbl_wait_title.setText("听 %d 张牌" % len(self.candidates))
            for t, s in self.candidates:
                self.cand_layout.addWidget(self._cand_widget(t, s))
        else:
            self.lbl_wait_title.setText("听牌候选")
        self.cand_layout.addStretch(1)

    def _cand_widget(self, tid: int, score) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        top = QLabel("%d番" % score.total)
        top.setAlignment(Qt.AlignCenter)
        top.setStyleSheet("color:%s;font-weight:bold;font-size:12px;"
                          % ("#2f7ff0" if score.ok else "#c0392b"))
        top.setToolTip("该张牌的总番数：%d 番%s"
                       % (score.total, "" if score.ok
                          else "（不足 8 分起和）"))
        btn = TileButton(code_of(tid), CAND_SIZE)
        btn.setToolTip("点这里把「%s」设为和张" % name_of(tid))
        btn.leftClicked.connect(lambda _c, t=tid: self.set_win_tile(t))
        lay.addWidget(top)
        lay.addWidget(btn, 0, Qt.AlignHCenter)
        return w

    def set_win_tile(self, tid: int) -> None:
        cur = sum(self.concealed.values())
        need = self._need_concealed()
        if self.concealed.get(tid, 0) > 0 and cur > need:
            self.concealed[tid] -= 1
            if self.concealed[tid] <= 0:
                self.concealed.pop(tid, None)
        self.win_tile = tid
        self._refresh_all()

    def _update_result(self) -> None:
        self.list_fans.clear()
        if self.calc is None:
            self.lbl_total.setText("算番引擎不可用")
            return
        target = 14 - 3 * len(self.melds)      # 完整手牌张数（含和张）
        cur = sum(self.concealed.values())
        masked = self._concealed_list()
        win = self.win_tile
        auto = False
        if win is None:
            if cur != target:
                # 还没到能算番的状态，只给提示，不算「不能和牌」
                self.lbl_total.setText("共 0 番")
                self.lbl_total.setStyleSheet("color:#2f7ff0;border:none;")
                if cur == target - 1:
                    self._add_fan_item("还没选和张：点下面列出的听牌候选，"
                                       "或直接点牌区里的牌")
                else:
                    self._add_fan_item("还需在牌选择区选 %d 张牌"
                                       % max(0, target - 1 - cur))
                return
            win, auto = self._guess_win_tile(masked)
            if win is None:
                self.lbl_total.setText("共 0 番")
                self.lbl_total.setStyleSheet("color:#c0392b;border:none;")
                self._add_fan_item("牌型不能和牌（请检查已选的牌）", "#c0392b")
                return
        opts = self._options()
        s = self.calc.score(self.melds, masked + [win], win, opts)
        if auto:
            self.win_tile = win
            wcode = code_of(win)
            self.row_win.set_tiles([wcode], [wcode], "点一下取消和张")
            self.lbl_hint.setText("和张：%s（自动判定）" % name_of(win))
        title = "共 %d 番" % s.total
        if not s.ok:
            title += "（不足 8 分起和）"
        self.lbl_total.setText(title)
        self.lbl_total.setStyleSheet(
            "color:%s;border:none;" % ("#2f7ff0" if s.ok else "#c0392b"))
        if s.fans:
            for name, value in s.fans:
                self._add_fan_item("%d番    %s" % (value, name))
        else:
            self._add_fan_item("无番种")
        if s.pattern:
            self._add_fan_item("牌型：%s" % s.pattern)
        if s.message:
            self._add_fan_item(s.message, "#c0392b")

    def _add_fan_item(self, text: str, color: str = "") -> None:
        item = QListWidgetItem(text)
        if color:
            item.setForeground(QColor(color))
        self.list_fans.addItem(item)

    def _guess_win_tile(self, masked: List[int]):
        """立牌满 14 张但未指定和张时，自动找出一张能和的牌"""
        if self.calc is None or not masked:
            return None, False
        opts = self._options()
        for t in sorted(set(masked), key=lambda x: -masked.count(x)):
            s = self.calc.score(self.melds, masked, t, opts)
            if not s.message and s.fans:
                return t, True
        return None, False


# ------------------------------------------------------------------ 入口

def main() -> int:
    # ★ v2.6.0：带命令行参数时走「一次调用算番」，**不启动界面**（也不需要 HTTP / 端口 / 先启动谁）：
    #     国标麻将算番器.exe --hand "11123456789999m" --win 9m --json
    #     国标麻将算番器.exe --hand "..." --meld kong:5555z --waits --text
    if cli_wanted is not None and cli_wanted(sys.argv[1:]):
        return cli_main(sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())             # ★ 应用级图标（任务栏/Alt+Tab 用）
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    win = MahjongFanWindow()
    if load_settings().get("window_maximized"):
        win.showMaximized()
    else:
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
