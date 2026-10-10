# -*- coding: utf-8 -*-
"""国标麻将算番器 —— 主程序（唯一编译源）

★ v2.7.3 起**英文名 = 文件名 = exe 名 = 打包目录**，统一叫 `Mahjong_Calculator`：
    主程序 `Mahjong_Calculator.py` → 打包出 `Mahjong_Calculator.exe`
    产物目录 `build_output\\Mahjong_Calculator.dist\\`
  界面上显示的**中文名「国标麻将算番器」保持不变**（常量 `APP_NAME`；英文名是 `APP_NAME_EN`）。

界面：PySide6 (Qt6)，Windows 桌面，中文界面，默认风格。
引擎：同目录 `mahjong_core.py`；规则数据：同目录《国标麻将标准规则.json》；
牌面图片：同目录《麻将图》子目录
    B1~B9 = 1筒~9筒      T1~T9 = 1索~9索      W1~W9 = 1万~9万
    F1~F4 = 东南西北      J1~J3 = 中 发 白     empty.png = 麻将背面

交互（按《软件设计构图》实现）
    · 牌选择区四行：索 / 筒 / 万 / 字牌。左键点一下加一张（最多 4 张），右键减一张。
      ★ **不用右键也能减牌**（v2.7.2，手机/触屏一样好使）：
        下面「已选牌」区里**点某一张牌＝取消这一张**：副露里点一张＝撤销那一组副露，
        「和张」点一下＝取消和张，「花牌」行点一张＝取消那张花牌。
      ★ **红色数字角标只显示「已选张数」，点它不再减牌**（v2.8.0）：
        红圈看着像删除按钮，误触一下手牌就少一张，所以取消了这个操作；
        角标对鼠标透明，点在上面等于点这张牌（正常加一张），不会出现「点了没反应」。
      ★ 牌与牌之间只留 4px（v2.4.2）：牌是固定尺寸，多余宽度靠 `setColumnStretch(空列, 1)`
        全部让给右侧空白，不要在 grid 上直接铺开（否则 9 列被均匀撑宽、缝隙很大）。
    · 立牌 = 手上其他牌（默认模式）；吃 / 碰 / 明杠 / 暗杠 都是「先点按钮，再选牌」：
        碰·明杠·暗杠 —— 点一次牌即成立；
        吃 —— 依次点出 3 张相连的牌后成立。
      ★ 点错了不要紧（v2.8.0）：**再点一次同一个按钮＝取消该模式**，回到「立牌」；
        已经做成的副露也能单独撤销 —— 在「副露」行**点那一组任意一张**（含暗杠牌背）即可（v2.7.2）。
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
          Mahjong_Calculator.exe --hand "11123456789999m" --win 9m --json
         python mahjong_core.py --hand "444z 123m 3z" --meld kong:6666z --waits --text
      牌写法：W1 / 一万 / 11123456789999m（m 万 s 索 p 筒 z 字牌）；副露：chi:/peng:/kong:/angang:
      默认输出 JSON（--text 为人话）；算不出和牌退出码 1、参数错退出码 2。

★ 读番（v2.9.0）：合计出番以后把「合计 N 番」念出来，音频是**现成的录音片段**，
  放在程序目录《数字》里（桌面版勾「读番」/点「🔊 读番」、Web 版点「🔊 读番」、
  接口 --readout/--speak 与 /api/readout）。
    · 念法＝合计 + 中文读法 + 番（123 → 合计一百二十三番；15 → 合计十五番）。
    · 放音用 Windows 自带播放器（MCI/winmm），**不需要第三方库**；其它系统静默降级。
    · ★ v2.9.3 **可选语音包**：《数字》下每个子目录就是一套录音（目录名＝语音包名，
      如「鲸宝」「女声」），**默认「女声」**。改的地方（就近覆盖）：
        ① 桌面端「设置 → 通用 → 语音包」（桌面端与 Web 页面的默认值一起改）；
        ② Web 页面上的「语音：」下拉（只影响这台手机/电脑，刷新还在）；
        ③ 别的程序：`score_hand(..., voice_set="鲸宝")` /
           `--voice-set 鲸宝` / `GET /api/readout?total=123&set=鲸宝`。
    · ★ **别的程序要用，不用复制我们的文件**：把目录告诉它即可 ——
        score_hand(..., readout=True, base_dir=r"D:\麻将\Mahjong_Calculator")
        Mahjong_Calculator.exe --say 123 --readout --dir "D:\麻将\Mahjong_Calculator"
        GET /api/readout?total=123     （返回中文读法 + 每段音频的文件名与下载地址）

Web 版（给手机/平板**浏览器**用；★ 不是给程序调用的接口）
    - 同目录 `mahjong_api.py`：单文件 Web 客户端（手机/平板浏览器可直接算番）。
    - ★ v2.9.1：菜单栏**「设置」**（Ctrl+,）点一下弹出**多标签设置窗口**：通用（默认开启自动读番 ·
      ★ v2.9.3 读番语音包）/
      Web 版（启动 Web 版 · 启动时自动开启 · 允许局域网访问 · 端口 · 口令 · 免口令 · 页面按钮 · 地址与用法）/
      高级（信息 · 打开程序目录 · 重置所有设置）。
      （原来是「工具」下拉菜单，v2.9.1 改成了菜单栏上的「设置」按钮 + 弹窗）
    - 默认只绑 127.0.0.1；勾上「允许局域网访问」改成 0.0.0.0，**默认不需要口令**
      （v2.6.0 起不再自动生成口令），手机打开 http://电脑IP:端口/ 即可。
    - ★ Web 端的**界面布局与桌面版一致**（v2.4.4）：牌选择区（索/筒/万/字牌四行）→ 模式行（+重置）
      → 选项区四行（□选项 / 风圈 / 风位 / 花牌 8 张小图 + 「N 张」）→ 已选牌 → 听牌候选 → 算番结果。
      花牌**不在牌池里**（跟桌面版一样放选项区第四行）；「重置」也是全部复位。
    - ★ **页面底部固定栏**（v2.9.4）：`↑ 牌池` `↓ 结果` 右边依次是 **`布局：`**、**`按键：`** 两个下拉框
      和 **`设置`** 按钮（窄屏放不下会自己换第二行，不会横向溢出）。
    - ★ Web 端是**给手机/平板用的**（v2.4.6）：手机没有右键，所以减牌入口是
      「在『已选牌→立牌』里点一张减一张」；长按/右键减牌仍保留给鼠标，
      并禁掉了长按系统菜单与文本选择（`-webkit-touch-callout:none; user-select:none`）。
    - ★ **桌面版也照这个来**（v2.7.2）：「已选牌」区（副露 / 立牌 / 和张 / 花牌）里
      点某一张＝取消这一张；右键仍然可用，不影响鼠标习惯。
    - ★ **红色数字角标不再可点**（v2.8.0，桌面版与 Web 版同步）：它只是「已选张数」
      的显示；红圈像删除按钮，误触一下就少一张牌，所以这个减牌操作已取消。
    - ★ Web 端也有**读番**（v2.9.0）：★ v2.9.4 起读番开关在页面底栏「**设置**」里（原来在模式行），
      点开后每算出总番就由**手机/平板自己念**（页面取 /api/readout 的清单，再逐段播 /audio/xxx；
      不用电脑出声，也不用复制音频）；用哪一套录音在同一个「设置」弹窗里选（★ v2.9.3）。
    - ★ **牌尺寸档位**（v2.7.0 起；v2.8.4 改成纯 px 共 27 档）：★ v2.9.4 起下拉框在页面**底栏**
      （`布局：38px（默认）`＝一张牌多宽、`按键：15px（默认）`＝字号），随时能调、选择记在 localStorage。
    - ★ 免口令白名单（v2.5.0）：口令设了之后，可以**分项**允许某些东西「不输入口令也能用」——
      设置窗口「Web 版 → 免口令访问设置…」里逐项勾选：**Web 客户端页面（含牌面图）** / 自测页 /
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
import platform
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon,
                           QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QRadioButton, QScrollArea, QStackedWidget, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

__version__ = "2.9.14"
APP_NAME = "国标麻将算番器"                 # 中文名（界面显示，保持不变）
APP_NAME_EN = "Mahjong_Calculator"        # ★ v2.7.3 英文名：文件名 / exe / 打包目录统一用它
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

# 模式按钮（同序）：键 ↔ 按钮 id 互转。
# ★ v2.8.0：选中「吃 / 碰 / 明杠 / 暗杠」后，**再点一次同一个按钮＝取消该模式**（回到「立牌」）。
MODE_KEYS = ["stand", "chi", "peng", "minggang", "angang"]
MODE_TEXTS = {"stand": "立牌", "chi": "吃", "peng": "碰",
              "minggang": "明杠", "angang": "暗杠"}

# ★ v2.9.1：默认是否「自动读番」——桌面版「读番」勾选框、以及 Web 版页面「🔊 读番」
#   都用它当默认值（默认开）⇒ **无论用哪个端，都自动读番**。
#   设置里存 `speak_default`（可在「设置 → 通用」里改）；用户自己点过某端的开关就以那端为准。
SPEAK_DEFAULT = True

# ★ v2.9.3：读番用哪一套录音 —— 《数字》下每个子目录就是一套（目录名＝语音包名），
#   默认用 `VOICE_SET_DEFAULT`（「女声」，见 mahjong_core）；设置里存 `voice_set`。
#   桌面端与 Web 端共用：桌面端在「设置 → 通用 → 语音包」里改，
#   Web 页面在页面上的「语音：」下拉里改（页面上的选择只影响那台手机/电脑）。
#   （`VOICE_SET` 这个默认值等下面 import 到 mahjong_core 之后再定，见「引擎导入」）

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
    from mahjong_core import (VOICE_DIR_NAME, VOICE_SET_DEFAULT, MahjongFanCalculator, Meld,
                              Options, VoicePlayer, cli_main, cli_wanted, code_of,
                              counts_of, count_voice_clips, find_voice_dir, is_suit,
                              name_of, readout_info, resolve_voice_dir, suit_of, tile_of,
                              voice_set_label, voice_set_names, voice_set_of, voice_sets)
    CORE_IMPORT_ERROR = None
except Exception as _exc:       # noqa: BLE001
    MahjongFanCalculator = None      # type: ignore[assignment]
    Meld = None                      # type: ignore[assignment]
    Options = None                   # type: ignore[assignment]
    VoicePlayer = None               # type: ignore[assignment]
    readout_info = find_voice_dir = count_voice_clips = None   # type: ignore[assignment]
    VOICE_DIR_NAME = "数字"
    VOICE_SET_DEFAULT = "女声"
    resolve_voice_dir = voice_sets = voice_set_names = None     # type: ignore[assignment]
    voice_set_label = voice_set_of = None                       # type: ignore[assignment]
    code_of = name_of = tile_of = suit_of = is_suit = counts_of = None
    cli_main = cli_wanted = None     # type: ignore[assignment]
    CORE_IMPORT_ERROR = repr(_exc)

# ★ v2.9.3：读番语音包的默认值（老设置里没有 `voice_set` 就用它；「重置所有设置」也回它）
VOICE_SET = VOICE_SET_DEFAULT

# ★ Web 版服务（同目录 mahjong_api.py；缺失时程序仍能正常运行，只是没有 Web 版）
#   注意：**给其它程序调用的「API」是 mahjong_core**（import 或命令行），不是这台 HTTP 服务；
#   这里的服务只为「手机/平板浏览器算番」的 Web 页面存在。
try:
    from mahjong_api import (ApiError as ApiError_, ApiServer as ApiServer_,
                            lan_ip as lan_ip_,
                            WEB_SHOW_ITEMS as WEB_SHOW_ITEMS_,
                            WEB_SHOW_KEYS as WEB_SHOW_KEYS_,
                            WEB_SHOW_DEFAULT as WEB_SHOW_DEFAULT_)
    API_IMPORT_ERROR = None
except Exception as _exc:       # noqa: BLE001
    ApiServer_ = None                # type: ignore[assignment]
    WEB_SHOW_ITEMS_ = ()             # type: ignore[assignment]
    WEB_SHOW_KEYS_ = []              # type: ignore[assignment]
    WEB_SHOW_DEFAULT_ = ()           # type: ignore[assignment]

    class ApiError_(Exception):      # type: ignore[no-redef]
        message = ""

    def lan_ip_() -> str:            # type: ignore[no-redef]
        return "127.0.0.1"

    API_IMPORT_ERROR = repr(_exc)

# ★ v2.9.6：算番统计库（SQLite / WAL）。落库失败不影响算番主流程。
try:
    from mahjong_stats import (StatsDB as StatsDB_,
                               fans_text as fans_text_)
    STATS_IMPORT_ERROR = None
except Exception as _exc:       # noqa: BLE001
    StatsDB_ = None                 # type: ignore[assignment]
    STATS_IMPORT_ERROR = repr(_exc)

    def fans_text_(fans) -> str:    # type: ignore[misc]
        """兜底：统计模块导入不了时，明细里番种就是空的，其余照常"""
        return ""

# ★ v2.9.7：统计面板「显示哪些列」的字典与规整函数（与 Web 端共用同一套 key）。
#   导入失败也要能跑（统计只是附加功能，缺了不能让主程序起不来）。
try:
    from mahjong_api import (STATS_COL_ITEMS as STATS_COL_ITEMS_,
                             STATS_COL_KEYS as STATS_COL_KEYS_,
                             STATS_COLS_DESKTOP_DEFAULT as STATS_COLS_DESKTOP_DEFAULT_,
                             stats_cols_normalize as stats_cols_normalize_,
                             stats_cols_new_merged as stats_cols_new_merged_,
                             # ★ v2.9.10：逐手明细的「显示哪些列」
                             DETAIL_COL_ITEMS as DETAIL_COL_ITEMS_,
                             DETAIL_COL_KEYS as DETAIL_COL_KEYS_,
                             DETAIL_COLS_DESKTOP_DEFAULT as DETAIL_COLS_DESKTOP_DEFAULT_,
                             detail_cols_normalize as detail_cols_normalize_,
                             detail_cols_new_merged as detail_cols_new_merged_)
except Exception as _exc:       # noqa: BLE001
    # ★ v2.9.12：与 mahjong_api.STATS_COL_ITEMS 保持同步（多了 nick/os/browser/dev）
    STATS_COL_ITEMS_ = (("user", "用户"), ("nick", "昵称"), ("ctype", "客户端"),
                        ("os", "系统"), ("browser", "浏览器"), ("dev", "设备型号"),
                        ("ip", "IP"), ("ua", "UA（设备）"), ("fan", "合计番数"),
                        ("cnt", "次数"), ("reach", "达标"), ("last", "最近"),
                        ("fans", "番种"))
    STATS_COL_KEYS_ = tuple(k for k, _ in STATS_COL_ITEMS_)
    STATS_COLS_DESKTOP_DEFAULT_ = STATS_COL_KEYS_

    def _norm_(val, keys, default):     # type: ignore[misc]
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

    def stats_cols_normalize_(val, default=STATS_COLS_DESKTOP_DEFAULT_):  # type: ignore[misc]
        return _norm_(val, STATS_COL_KEYS_, default)

    def stats_cols_new_merged_(val, default=STATS_COLS_DESKTOP_DEFAULT_):  # type: ignore[misc]
        cur = list(stats_cols_normalize_(val, default))
        for k in ("fans", "nick", "os", "browser", "dev"):
            if k not in cur:
                cur.append(k)
        return tuple(cur)

    # ★ v2.9.12：与 mahjong_api.DETAIL_COL_ITEMS 保持同步
    DETAIL_COL_ITEMS_ = (("day", "日期"), ("time", "时间（毫秒）"), ("nick", "昵称"),
                         ("ctype", "客户端"), ("os", "系统"), ("browser", "浏览器"),
                         ("dev", "设备型号"), ("ip", "IP"), ("ua", "UA（设备）"),
                         ("fan", "番数"), ("base", "起番"), ("reach", "达标"),
                         ("fans_n", "番种数"), ("fans", "番种"))
    DETAIL_COL_KEYS_ = tuple(k for k, _ in DETAIL_COL_ITEMS_)
    DETAIL_COLS_DESKTOP_DEFAULT_ = DETAIL_COL_KEYS_

    def detail_cols_normalize_(val, default=DETAIL_COLS_DESKTOP_DEFAULT_):  # type: ignore[misc]
        return _norm_(val, DETAIL_COL_KEYS_, default)

    def detail_cols_new_merged_(val, default=DETAIL_COLS_DESKTOP_DEFAULT_):  # type: ignore[misc]
        cur = list(detail_cols_normalize_(val, default))
        for k in ("nick", "os", "browser", "dev"):
            if k not in cur:
                cur.append(k)
        return tuple(cur)

    STATS_COLS_API_ERROR = repr(_exc)

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
    """牌选择区的「已选张数」红角标（★ v2.8.0 起**只显示张数，不再能点**）

    v2.7.2 曾让红角标「点一下＝减一张」，但红圈看着像删除按钮，太容易误触
    （想加牌却点掉一张）。现在角标纯做计数显示：减牌请**右键**，或在下面
    「已选牌」区点某一张牌取消。角标对鼠标事件透明，所以点在它上面＝点在
    这张牌上（左键加一张），不会留下「点了没反应」的死角。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(20, 20)
        self.setToolTip("已选张数（减牌：右键，或在下面「已选牌」里点一张）")
        self.setStyleSheet(
            "background:#e74c3c;color:#fff;border-radius:10px;font-size:11px;"
            "font-weight:bold;")
        # ★ v2.8.0：角标只是装饰，别拦住底下牌按钮的点击（也避免误触减牌）
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)


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
        # ★ v2.8.0：角标只显示张数（不可点，避免误触减牌）
        self.badge = CountBadge(self)
        self.badge.move(self.width() - self.badge.width() - 1, 1)
        self.badge.hide()
        self.clicked.connect(lambda: self.leftClicked.emit(self.code))
        self._apply_style()

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
<li><b>不用右键也能减牌</b>（手机 / 触屏一样好使）：
下面「已选牌」区里<b>点某一张牌也会取消这一张</b>
（副露里点一张＝撤销那一组，点「和张」＝取消和张，点「花牌」行＝取消那张花牌）。
牌上的<b>红色数字</b>只是「已选张数」，<b>点它不再减牌</b>（点在上面＝点这张牌）。</li>
<li><b>立牌</b>（默认）：点出来的牌都算「手上其他牌」，即门前的暗手牌。</li>
<li><b>吃 / 碰 / 明杠 / 暗杠</b>：都是<b>先点按钮，再选牌</b>。
    <ul>
    <li>碰、明杠、暗杠：点一次牌就成立（碰 3 张、杠 4 张自动补齐）。</li>
    <li>吃：依次点出 3 张相连的同花色牌，例如 一萬 / 二萬 / 三萬。</li>
    <li>点错了、或不想做这一手：<b>再点一次同一个按钮</b>（吃 / 碰 / 明杠 / 暗杠）
        ＝<b>取消该模式</b>，回到「立牌」。</li>
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
<code>Mahjong_Calculator.exe --hand "11123456789999m" --win 9m --json</code><br>
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
<li>★ <b>读番</b>（v2.9.0）：<code>--readout</code> 在结果里附上「合计 N 番」怎么念
（中文逐字 + 每段音频的文件名与路径），<code>--speak</code> 顺带念出来；
<code>--say 123</code> 可以不算番、只把数字 N 念出来（<code>--say 123 --speak</code> 直接出声）。</li>
<li>★ <b>别的程序要用读番，不用复制音频</b>：把我们的目录指过来就行 ——
<code>Mahjong_Calculator.exe --hand "..." --readout --dir "D:\麻将\Mahjong_Calculator"</code>，
或进程内 <code>score_hand(..., readout=True, base_dir=r"D:\麻将\Mahjong_Calculator")</code>；
返回里的 <code>dir</code> 就是《数字》音频目录，<code>clips</code> 是依次要播的文件。</li>
</ul>

<h3>六、Web 版（手机 / 平板浏览器算番）</h3>
<ul>
<li>菜单栏「<b>设置</b>」（Ctrl+,）→「Web 版」标签页：勾「启动 Web 版」（Ctrl+Alt+A）
会在本机开一个网页服务，
默认 <b>http://127.0.0.1:8718</b>（只监听本机）。<b>这是给浏览器用的</b>，
不是给其它程序调用的接口（程序请用上面第一条的 <code>mahjong_core</code>）。</li>
<li><b>手机 / 平板算番</b>：设置 → Web 版 → 勾「允许局域网访问（手机/平板）」，
手机浏览器打开弹出的地址就能用（页面与桌面版一致：牌池/副露/选项/听牌/算番）。
<b>默认不需要口令</b>。</li>
<li><b>牌太大/太小怎么办</b>：页面<b>底栏</b>里有「<b>布局：</b>」「<b>按键：</b>」两个下拉框
（布局＝一张牌多宽、按键＝字号），选中立刻生效、选择会记住（默认「38px」「15px」＝老样子）。
一页放不下时底栏会自己换行，不会挤坏页面。</li>
<li>地址可在「设置 → Web 版 → 地址与用法…」里查看（会复制手机链接到剪贴板）。</li>
<li>想加一道门槛：「设置 → Web 版 → 访问口令…」（留空即取消）；还可以在
「免口令访问设置…」里分项决定哪些内容不用口令。</li>
<li>只想用命令行起服务（比如开机自启）：
<code>python mahjong_api.py --host 0.0.0.0 --port 8718</code>（加 <code>--token 口令</code> 才要口令）。</li>
<li>★ <b>读番</b>（v2.9.0）：★ v2.9.4 起页面上读番开关在<b>底栏「设置」</b>里（原来在模式行）；
点开以后每算出总番就<b>由手机/平板自己念</b>一遍；同一个「设置」弹窗里还能选<b>语音包</b>
（用哪一套录音，★ v2.9.3）。其它程序用 <code>GET /api/readout?total=123</code>
拿「念法 + 每段音频的下载地址」即可，<b>不用复制音频</b>。</li>
<li>平安提醒：端口只建议在自家网络开；口令只防随手访问，不要当强密码用。</li>
</ul>

<h3>七、读番（把总番念出来）</h3>
<ul>
<li><b>怎么用</b>：选项行的「<b>读番</b>」勾上 = 合计出番以后自动念「合计 N 番」；
结果区右上角的「<b>🔊 读番</b>」= 随手把当前结果念一遍（不用勾选）。
「设置 → 通用 → 试听「合计 25 番」」会念一句，用来确认音频在不在。</li>
<li><b>★ v2.9.1 默认开启自动读番</b>：「设置 → 通用 → □默认开启自动读番」默认就是<b>勾上</b>的 ——
桌面版的「读番」勾选框、以及 <b>Web 版页面</b>上的「🔊 读番」都默认打开，
<b>无论用桌面还是手机/平板，都自动读番</b>；某一端自己点过开关，就以那端的选择为准。</li>
<li><b>音频在哪</b>：就在程序目录的《数字》文件夹里，
<b>文件名就是它读的那个词</b>：<code>一.mp3</code>…<code>九.mp3</code>、<code>零.mp3</code>、
<code>十/百/千/万.mp3</code>、<b>连读词</b> <code>一十.mp3</code>…<code>九十.mp3</code>、
<code>一百.mp3</code>…<code>九百.mp3</code>、<code>百万.mp3</code>，以及 <code>合计.mp3</code>、<code>番.mp3</code>。
（<b>没有</b>「亿」的录音；重录增删片段<b>不用改程序</b>。）</li>
<li><b>怎么挑录音</b>：先把番数读成中文（合计 + 读法 + 番），再<b>从前往后挑最长的整词录音</b>——
能对上整词就用整词（<code>一百.mp3</code> + <code>二十.mp3</code> + <code>三.mp3</code>），
对不上就逐字拆（<code>一千</code> → <code>一.mp3</code> + <code>千.mp3</code>；
<code>十万</code> → <code>十.mp3</code> + <code>万.mp3</code>）。</li>
<li><b>念法</b>：合计 + 中文读法 + 番 —— 123 → 「合计 一百二十三 番」；
15 → 「合计 十五 番」（十~十九省掉前面的「一」）；110 → 「一百一十」（用 <code>一十.mp3</code>）；
10010 → 「一万零一十」；1000000 → 「一百万」。</li>
<li><b>缺片段怎么办</b>：<b>桌面版整句不念</b>（宁可不出声，也不要把番数念错）；
接口会如实给出 <code>missing</code> 列表（例如读到「亿」时缺 <code>亿.mp3</code>）。算番照旧。</li>
<li><b>放音方式</b>：Windows 用系统自带的播放器（MCI），<b>不需要装任何东西</b>；
其它系统不出声（但 <code>--readout</code> / <code>/api/readout</code> 照样能看到音频清单）。</li>
<li><b>同一个番数不会连着重念</b>（点来点去、改风圈风位时不会一直吵）；「重置」不动这个开关，
只把正在念的停下来。</li>
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
<p>英文名 / 程序文件 / exe / 打包目录：<b>Mahjong_Calculator</b></p>
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


class WebDisplayDialog(QDialog):
    """Web 版显示设置（v2.7.5）——手机/平板页面上的「工具按钮」要不要显示。

    目前两项：接口自测页（/debug）、换口令。**默认两个都不显示**（对只想算番的人是干扰）。
    只负责收集选择；实际重启服务由 `MahjongFanWindow._api_set_show` 做。
    """

    def __init__(self, current: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Web 版显示设置")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        tip = QLabel(
            "手机/平板打开 Web 版页面时，模式行里默认只留「重置」（布局/按键/设置都在页面底栏）。\n"
            "下面两项是给调试/运维用的，勾上才会显示在页面上（默认都不显示）。")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        self.boxes: Dict[str, QCheckBox] = {}
        items = WEB_SHOW_ITEMS_ or ()
        if not items:
            warn = QLabel("⚠ 缺少 mahjong_api.py（拿不到可选项清单）")
            warn.setStyleSheet("color:#b45309;")
            lay.addWidget(warn)
        for key, label, detail in items:
            cb = QCheckBox(label)
            cb.setChecked(key in (current or []))
            cb.setToolTip(detail)
            self.boxes[key] = cb
            lay.addWidget(cb)
            sub = QLabel("　" + detail)
            sub.setStyleSheet("color:#6b7280; font-size:11px;")
            sub.setWordWrap(True)
            lay.addWidget(sub)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("确定")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def selected(self) -> List[str]:
        """按 WEB_SHOW_KEYS_ 顺序返回勾中的键"""
        return [k for k in WEB_SHOW_KEYS_ if self.boxes.get(k) is not None
                and self.boxes[k].isChecked()]


# ------------------------------------------------------------------ 主窗口

class SettingsDialog(QDialog):
    """设置窗口（★ v2.9.1）—— 多标签，把原来「工具」菜单里的设置全收进来

    设计取舍：
      · 只负责**显示与转发**：真正的动作仍是主窗口那几个 QAction
        （`win.act_api` / `act_api_lan` / `act_api_token` / `act_api_anon` /
        `act_api_show` / `act_api_info` / `act_api_port` / `act_speak` / `act_speak_default`），
        所以行为与老菜单逐字一致，测试也照旧能直接触发那些 action。
      · **改动即时生效并自动落盘**（沿用全程序「设置实时自动保存」的约定），
        因此没有「确定 / 取消」，只有「关闭」。
      · 复选框与 action **双向同步**：在这里勾选＝触发 action；action 被别处改动
        （比如启动失败自动回弹、或 Web 版被停止）复选框也跟着变。
    """

    def __init__(self, win, parent=None):
        super().__init__(parent if parent is not None else win)
        self.win = win
        self.setWindowTitle("设置 · " + APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(600, 470)
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        # ★ v2.9.11：原来「通用」一页塞了读番 + 算番选项 + 统计列 + 明细列，
        #   窗口被撑得很长 —— 拆成「读番 / 统计列」两页，一页只讲一件事
        self.tabs.addTab(self._tab_general(), "读番")
        self.tabs.addTab(self._tab_statcols(), "统计列")
        self.tabs.addTab(self._tab_web(), "Web 版")
        self.tabs.addTab(self._tab_advanced(), "高级")
        foot = QHBoxLayout()
        self.lbl_foot = QLabel("设置会实时保存，改动立刻生效。")
        self.lbl_foot.setStyleSheet("color:#6b7684;")
        foot.addWidget(self.lbl_foot)
        foot.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.setDefault(True)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        foot.addWidget(btn_close)
        outer.addLayout(foot)

    # ---- 小工具
    def _title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = QFont()
        f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet("color:#2f7ff4;")
        return lbl

    def _note(self, html: str) -> QLabel:
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#6b7684;")
        return lbl

    def _bind_check(self, box: QCheckBox, act) -> None:
        """复选框 ↔ action 双向同步（点复选框 = 触发那个 action）"""
        box.setChecked(act.isChecked())
        box.clicked.connect(lambda _checked=False, a=act: a.trigger())
        act.toggled.connect(box.setChecked)

    def _bind_button(self, text: str, act, tip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tip or act.toolTip())
        btn.clicked.connect(lambda _checked=False, a=act: a.trigger())
        return btn

    # ---- 语音包（★ v2.9.3：读番用哪一套录音）
    def _voice_options(self) -> List[Tuple[str, str]]:
        """可选语音包：[(名字, 显示文字)]（找不到音频就退回默认那套，别让下拉空着）"""
        try:
            packs = voice_sets(app_dir()) if voice_sets else []
        except Exception:       # noqa: BLE001
            packs = []
        out = [(str(s["name"]), "%s（%d 段）" % (voice_set_label(str(s["name"])), s["clips"]))
               for s in packs]
        cur = str(self.win.voice_set or VOICE_SET)
        if not out:
            return [(cur, "%s（没找到音频）" % voice_set_label(cur))]
        if cur not in [n for n, _ in out]:       # 设置里那套被删了 → 也列出来，看得见
            out.insert(0, (cur, "%s（已不存在）" % voice_set_label(cur)))
        return out

    def _fill_voice_options(self) -> None:
        self.cmb_voice.blockSignals(True)
        self.cmb_voice.clear()
        for name, text in self._voice_options():
            self.cmb_voice.addItem(text, name)
        idx = self.cmb_voice.findData(str(self.win.voice_set or VOICE_SET))
        self.cmb_voice.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_voice.blockSignals(False)
        self.refresh_voice_state()

    def _on_voice_changed(self, *args) -> None:      # noqa: ARG002
        self.win._set_voice_set(str(self.cmb_voice.currentData() or ""))  # noqa: SLF001
        self.refresh_voice_state()

    def refresh_voice_state(self) -> None:
        """语音包那行的说明：当前用哪一套、在哪个目录、有几段"""
        if not hasattr(self, "lbl_voice"):
            return
        w = self.win
        try:
            vdir = (resolve_voice_dir(w.voice_set, app_dir()) if resolve_voice_dir else "") or ""
            n = (count_voice_clips(app_dir(), w.voice_set) if count_voice_clips else 0) or 0
        except Exception:       # noqa: BLE001
            vdir, n = "", 0
        self.lbl_voice.setText(
            "当前语音包：<b>%s</b>（%d 段）<br>%s"
            % (voice_set_label(w.voice_set), n,
               vdir or "没找到《%s》目录" % VOICE_DIR_NAME))

    # ---- 通用
    def _tab_general(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)
        lay.addWidget(self._title("读番（合计出番以后念出来）"))
        self.cb_speak_default = QCheckBox("默认开启自动读番")
        self.cb_speak_default.setToolTip(
            "勾上（默认）：算完一手牌自动念「合计 N 番」——\n"
            "  · 桌面版：主界面的「读番」勾选框默认打开；\n"
            "  · Web 版：手机/平板页面上的「🔊 读番」默认也是打开的（刷新页面即生效）。\n"
            "所以**无论用桌面还是手机，都默认自动读番**。\n"
            "某一端自己点过开关，就以那端的选择为准；同一个番数不会连着重念。")
        self._bind_check(self.cb_speak_default, self.win.act_speak_default)
        lay.addWidget(self.cb_speak_default)
        # ★ v2.9.3：读番用哪一套录音（《数字》下的子目录名）—— 桌面端立刻生效，
        #   Web 页面刷新后跟着变；页面自己选过就以页面上的为准
        rowv = QHBoxLayout()
        rowv.addWidget(QLabel("读番语音包："))
        self.cmb_voice = QComboBox()
        self.cmb_voice.setToolTip(
            "读番用哪一套录音：《%s》下**每个子目录就是一套**（目录名＝语音包名，\n"
            "如「鲸宝」「女声」），默认用「%s」。\n"
            "· 桌面版：立刻改用这一套；\n"
            "· Web 版：页面上「语音：」下拉的默认值改成这一套（刷新页面即生效），\n"
            "  手机上自己选过就只影响那台手机。" % (VOICE_DIR_NAME, VOICE_SET_DEFAULT))
        rowv.addWidget(self.cmb_voice)
        rowv.addStretch(1)
        lay.addLayout(rowv)
        self.lbl_voice = self._note("")
        lay.addWidget(self.lbl_voice)
        self._fill_voice_options()
        self.cmb_voice.currentIndexChanged.connect(self._on_voice_changed)
        lay.addWidget(self._note(
            "音频用的是程序目录《%s》里现成的录音片段（<b>文件名就是它读的那个词</b>："
            "<code>一.mp3</code>、<code>二十.mp3</code>、<code>一百.mp3</code>…）。<br>"
            "念法：合计 + 中文读法 + 番 —— 123 → 「合计 一百二十三 番」；"
            "<b>缺片段就整句不念</b>（宁可不出声也不念错），算番照旧。"
            % VOICE_DIR_NAME))
        row = QHBoxLayout()
        self.btn_speak_try = self._bind_button("试听「合计 25 番」", self.win.act_speak)
        row.addWidget(self.btn_speak_try)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(self._note(
            "其它程序要用读番<b>不用复制音频</b>：把本程序目录告诉它即可 ——<br>"
            "<code>score_hand(..., readout=True, base_dir=r\"…\\Mahjong_Calculator\")</code>；<br>"
            "<code>Mahjong_Calculator.exe --say 123 --readout --dir \"…\\Mahjong_Calculator\"</code>；<br>"
            "<code>GET /api/readout?total=123</code>（返回中文读法 + 每段音频的下载地址）。"))
        lay.addWidget(self._title("算番选项"))
        lay.addWidget(self._note(
            "自摸 / 和绝张 / 抢杠和·杠上开花 / 海底捞月·妙手回春、圈风、风位、花牌 —— "
            "这些是<b>每一手牌</b>的选项，仍在主界面的「算番」页上直接点（不在这里）。"))
        lay.addStretch(1)
        return page

    # ---- 统计列（★ v2.9.11：从「通用」拆出来单独一页 —— 两个列组 + 说明太长，撑爆窗口）
    def _tab_statcols(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)
        lay.addWidget(self._title("统计显示列"))     # ★ v2.9.7
        lay.addWidget(self._note(
            "「工具 → 统计」窗口里显示哪几列：勾几个就显示几个（<b>至少留一个</b>）。<br>"
            "手机 / 平板上「统计」面板的<b>默认列</b>也跟着这里走；"
            "那台设备在自己「设置」里改过，就以设备上的选择为准。"))
        grid_sc = QGridLayout()
        grid_sc.setSpacing(4)
        self.stat_col_boxes: Dict[str, QCheckBox] = {}
        for _i, (_key, _label) in enumerate(STATS_COL_ITEMS_):
            _box = QCheckBox(_label)
            _box.setChecked(_key in self.win.stats_cols)
            _box.setToolTip("勾选 →「统计」窗口显示「%s」这一列" % _label)
            self.stat_col_boxes[_key] = _box
            grid_sc.addWidget(_box, _i // 4, _i % 4)
        for _box in self.stat_col_boxes.values():    # 全部建好后再连信号，避免初始化误触发
            _box.toggled.connect(lambda _c=False: self._on_stat_col_changed())
        lay.addLayout(grid_sc)
        _rowsc = QHBoxLayout()
        _btn_sc_all = QPushButton("全选")
        _btn_sc_all.setCursor(Qt.PointingHandCursor)
        _btn_sc_all.clicked.connect(lambda _c=False: self._set_stat_cols_all(True))
        _btn_sc_none = QPushButton("只留「用户」")
        _btn_sc_none.setCursor(Qt.PointingHandCursor)
        _btn_sc_none.clicked.connect(lambda _c=False: self._set_stat_cols_all(False))
        _rowsc.addWidget(_btn_sc_all)
        _rowsc.addWidget(_btn_sc_none)
        _rowsc.addStretch(1)
        lay.addLayout(_rowsc)

        # ---- ★ v2.9.10：逐手明细显示列（与上面「统计显示列」同一套做法）
        lay.addWidget(self._title("明细显示列"))
        lay.addWidget(self._note(
            "「统计」里选中某个人点「明细…」后，那个<b>逐手明细</b>窗口显示哪几列："
            "勾几个就显示几个（<b>至少留一个</b>）。<br>"
            "手机 / 平板上明细面板的<b>默认列</b>也跟着这里走；"
            "那台设备在自己「设置」里改过，就以设备上的选择为准。"))
        grid_dc = QGridLayout()
        grid_dc.setSpacing(4)
        self.detail_col_boxes: Dict[str, QCheckBox] = {}
        for _i, (_key, _label) in enumerate(DETAIL_COL_ITEMS_):
            _box = QCheckBox(_label)
            _box.setChecked(_key in self.win.detail_cols)
            _box.setToolTip("勾选 → 明细窗口显示「%s」这一列" % _label)
            self.detail_col_boxes[_key] = _box
            grid_dc.addWidget(_box, _i // 4, _i % 4)
        for _box in self.detail_col_boxes.values():   # 建好后再连信号，避免初始化误触发
            _box.toggled.connect(lambda _c=False: self._on_detail_col_changed())
        lay.addLayout(grid_dc)
        _rowdc = QHBoxLayout()
        _btn_dc_all = QPushButton("全选")
        _btn_dc_all.setCursor(Qt.PointingHandCursor)
        _btn_dc_all.clicked.connect(lambda _c=False: self._set_detail_cols_all(True))
        _btn_dc_min = QPushButton("只留「时间」")
        _btn_dc_min.setCursor(Qt.PointingHandCursor)
        _btn_dc_min.clicked.connect(lambda _c=False: self._set_detail_cols_all(False))
        _rowdc.addWidget(_btn_dc_all)
        _rowdc.addWidget(_btn_dc_min)
        _rowdc.addStretch(1)
        lay.addLayout(_rowdc)
        lay.addStretch(1)
        return page

    # ---- 统计显示列（★ v2.9.7）
    def _set_stat_cols_all(self, all_on: bool) -> None:
        """「全选」 / 「只留『用户』」两个快捷按钮"""
        for _key, _box in self.stat_col_boxes.items():
            want = True if all_on else (_key == "user")
            if _box.isChecked() != want:
                _box.setChecked(want)
        self._on_stat_col_changed()

    # ---- 明细显示列（★ v2.9.10）
    def _set_detail_cols_all(self, all_on: bool) -> None:
        """「全选」 / 「只留『时间』」两个快捷按钮"""
        for _key, _box in self.detail_col_boxes.items():
            want = True if all_on else (_key == "time")
            if _box.isChecked() != want:
                _box.setChecked(want)
        self._on_detail_col_changed()

    def _on_detail_col_changed(self, *args) -> None:      # noqa: ARG002
        cols = [k for k, b in self.detail_col_boxes.items() if b.isChecked()]
        if not cols:
            # ★ 一列都不勾 → 明细表全白，强制把「时间」勾回来
            box = self.detail_col_boxes.get("time")
            if box is not None:
                box.blockSignals(True)
                box.setChecked(True)
                box.blockSignals(False)
                cols = ["time"]
        self.win._set_detail_cols(cols)                  # noqa: SLF001

    def _on_stat_col_changed(self, *args) -> None:      # noqa: ARG002
        cols = [k for k, b in self.stat_col_boxes.items() if b.isChecked()]
        if not cols:
            # ★ 一列都不勾 → 表格是空的没法看，强制把「用户」勾回来
            box = self.stat_col_boxes.get("user")
            if box is not None:
                box.blockSignals(True)
                box.setChecked(True)
                box.blockSignals(False)
                cols = ["user"]
        self.win._set_stats_cols(cols)                   # noqa: SLF001

    # ---- Web 版
    def _tab_web(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)
        lay.addWidget(self._title("Web 版（手机 / 平板浏览器算番）"))
        self.cb_api = QCheckBox("启动 Web 版")
        self._bind_check(self.cb_api, self.win.act_api)
        lay.addWidget(self.cb_api)
        self.cb_api_auto = QCheckBox("启动程序时自动开启 Web 版")
        self.cb_api_auto.setToolTip(
            "勾上：下次打开本程序就自动开服务，手机/平板不用等你在电脑上点一下。\n"
            "（手动开启 / 停止 Web 版时这个开关会跟着变 —— 它记的就是「下次要不要自动开」）")
        self._bind_check(self.cb_api_auto, self.win.act_api_auto)
        lay.addWidget(self.cb_api_auto)
        self.cb_api_lan = QCheckBox("允许局域网访问（手机 / 平板）")
        self._bind_check(self.cb_api_lan, self.win.act_api_lan)
        lay.addWidget(self.cb_api_lan)
        self.lbl_web_state = self._note("")
        lay.addWidget(self.lbl_web_state)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        for i, (text, act) in enumerate((
                ("端口设置…", self.win.act_api_port),
                ("访问口令…", self.win.act_api_token),
                ("免口令访问设置…", self.win.act_api_anon),
                ("页面按钮显示设置…", self.win.act_api_show),
                ("地址与用法…", self.win.act_api_info))):
            grid.addWidget(self._bind_button(text, act), i // 2, i % 2)
        lay.addLayout(grid)
        lay.addWidget(self._note(
            "★ 这里开的是**给浏览器看的网页版**；其它程序要算番请直接用 <code>mahjong_core</code>"
            "（import 或命令行调用本程序，<b>不需要 HTTP / 端口 / 先启动谁</b>）。"))
        lay.addStretch(1)
        self.win.act_api.toggled.connect(lambda _c=False: self.refresh_web_state())
        self.win.act_api_lan.toggled.connect(lambda _c=False: self.refresh_web_state())
        self.refresh_web_state()
        return page

    def refresh_web_state(self) -> None:
        """把当前 Web 版状态说成人话（勾选/停止后立刻更新）"""
        w = self.win
        if not w._api_running():
            text = "当前：<b>未启动</b>"
        else:
            text = ("当前：<b>%s</b> —— 本机 %s；手机/平板 %s"
                    % ("局域网已开" if w.api_lan else "仅本机",
                       "http://127.0.0.1:%d/" % w.api_port, w._api_watch_url()))
        text += "<br>访问口令：%s；免口令：%s<br>页面按钮：%s" % (
            w.api_token or "（未设置 → 不需要口令）", w._anon_text(), w._web_show_text())
        self.lbl_web_state.setText(text)

    # ---- 高级
    def _tab_advanced(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)
        lay.addWidget(self._title("信息"))
        w = self.win
        fans = len(getattr(w.calc, "fan_values", {})) if w.calc else 0
        try:
            vcur = (resolve_voice_dir(w.voice_set, app_dir()) if resolve_voice_dir else "") or ""
            vall = voice_sets(app_dir()) if voice_sets else []
            nclips = (count_voice_clips(app_dir(), w.voice_set) if count_voice_clips else 0) or 0
        except Exception:           # noqa: BLE001
            vcur, vall, nclips = "", [], 0
        packs = "、".join("%s（%d 段）" % (voice_set_label(str(s["name"])), s["clips"])
                          for s in vall) or "（没找到任何语音包）"
        info = QLabel(
            "%s v%s（英文名 %s）<br>"
            "算番引擎：mahjong_core，番种 %d 个<br>"
            "设置文件：%s<br>"
            "读番语音包：<b>%s</b>（%d 段）<br>"
            "读番音频：%s<br>"
            "可选语音包：%s"
            % (APP_NAME, __version__, APP_NAME_EN, fans, settings_path(),
               voice_set_label(w.voice_set), nclips,
               vcur or "（未找到《%s》目录）" % VOICE_DIR_NAME, packs))
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(info)
        lay.addWidget(self._title("维护"))
        row = QHBoxLayout()
        btn_dir = QPushButton("打开程序目录")
        btn_dir.setCursor(Qt.PointingHandCursor)
        btn_dir.setToolTip("打开本程序所在目录（设置文件、《数字》音频、《麻将图》牌面图都在这里）")
        btn_dir.clicked.connect(lambda: self._open_dir())
        row.addWidget(btn_dir)
        btn_reset = QPushButton("重置所有设置…")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setToolTip("把全部设置恢复成默认值（手牌/副露等算番状态不受影响）")
        btn_reset.clicked.connect(lambda: self.win._reset_settings())
        row.addWidget(btn_reset)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(self._note(
            "「重置所有设置」会把：默认开启自动读番（回默认<b>开</b>）、读番语音包（回默认<b>%s</b>）、"
            "Web 版相关设置、窗口几何、读番勾选、圈风风位、花牌 等全部恢复默认；"
            "已经选好的牌/副露不受影响（那属于「重置」按钮的事）。" % VOICE_SET_DEFAULT))
        lay.addStretch(1)
        return page

    @staticmethod
    def _open_dir() -> None:
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(app_dir()))
        except Exception:           # noqa: BLE001
            pass


class MahjongFanWindow(QMainWindow):
    """国标麻将算番器主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s %s v%s" % (APP_NAME, APP_NAME_EN, __version__))
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
        # ★ v2.9.0 读番：念「合计 N 番」用的播放器 + 记录（同一个番数不重复念）
        self.voice = VoicePlayer() if VoicePlayer else None
        self._total: Optional[int] = None          # 最近算出的总番（None = 还没算出来）
        self._last_spoken: Optional[int] = None    # 上次念过的番数
        # ★ v2.9.1：默认开启自动读番（桌面端读番勾选框 + Web 页面默认值都看它）
        self.speak_default = bool(self._global_settings.get("speak_default", SPEAK_DEFAULT))
        # ★ v2.9.3：读番用哪一套录音（《数字》下的子目录名；桌面端与 Web 端默认值都看它）
        self.voice_set = str(self._global_settings.get("voice_set") or VOICE_SET)
        # ★ v2.9.7：统计面板显示哪几列（桌面端统计窗口用；同时作为 Web 端的默认值）
        # ★ v2.9.9：老设置里没有的**新列**（番种）自动补到末尾，否则升级后永远看不到
        self.stats_cols: List[str] = list(stats_cols_new_merged_(
            self._global_settings.get("stats_cols"), STATS_COLS_DESKTOP_DEFAULT_))
        # ★ v2.9.10：逐手明细显示哪几列（桌面端明细窗口用；同时作为 Web 端的默认值）
        self.detail_cols: List[str] = list(detail_cols_new_merged_(
            self._global_settings.get("detail_cols"), DETAIL_COLS_DESKTOP_DEFAULT_))
        self._settings_dlg = None                  # 设置窗口（打开时才有）
        self._stats_dlg = None                     # ★ v2.9.7 统计窗口（打开时才有；改列时要跟着刷新）
        self._detail_dlg = None                    # ★ v2.9.10 逐手明细窗口（打开时才有；改列时跟着刷新）
        self.api_server = None                # ★ 本地 HTTP API 服务（设置窗口「Web 版」里开/关）
        self.api_port = int(self._global_settings.get("api_port") or DEFAULT_API_PORT)
        self.api_auto_start = bool(self._global_settings.get("api_auto_start", False))
        self.api_lan = bool(self._global_settings.get("api_lan", False))
        self.api_token = str(self._global_settings.get("api_token") or "")
        # ★ v2.5.0：免口令白名单（设了口令后，哪些访问不用口令）
        _anon = self._global_settings.get("api_anon")
        self.api_anon: List[str] = ([k for k in ANON_KEYS if k in _anon]
                                   if isinstance(_anon, (list, tuple))
                                   else list(ANON_DEFAULT))
        # ★ v2.7.5：Web 页面上的「接口自测页 / 换口令」两个按钮要不要显示 —— 默认都不显示
        _show = self._global_settings.get("api_show")
        self.web_show: List[str] = ([k for k in WEB_SHOW_KEYS_ if k in _show]
                                   if isinstance(_show, (list, tuple))
                                   else list(WEB_SHOW_DEFAULT_))
        # ★ v2.9.6：算番统计库（SQLite / WAL）；**桌面端与 Web 端共用同一 db 文件**
        #   落库失败只记日志、不影响算番主流程。
        self.stats = None
        if StatsDB_ is not None:
            try:
                self.stats = StatsDB_(os.path.join(app_dir(), "mahjong_stats.db"))
            except Exception as _exc:      # noqa: BLE001
                self.stats = None
                sys.stderr.write("[stats] 统计库初始化失败：%r\n" % (_exc,))

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
                                          "左键加一张；减牌用右键，"
                                          "或点下方「已选牌」里的一张取消"))
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

        # 2) 操作按钮行（★ v2.9.5：重置 / 立牌 / 吃 / 碰 / 明杠 / 暗杠 —— 「重置」在「立牌」左边，
        #    与 Web 页面同一顺序；原来是放在最后）
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
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
        mode_row.addWidget(self._hint_label("模式"))
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for key in MODE_KEYS:
            btn = QPushButton(MODE_TEXTS[key])
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
            self.mode_group.addButton(btn, MODE_KEYS.index(key))
            mode_row.addWidget(btn)
            setattr(self, "btn_mode_" + key, btn)
        self.btn_mode_stand.setChecked(True)
        self.mode_group.idClicked.connect(self.on_mode_changed)
        mode_row.addStretch(1)
        box.addLayout(mode_row)

        # 3) 选项区（按设计图分四行：复选框 / 圈风 / 风位 / 花牌）
        #    行1：□自摸 □和绝张 □抢杠和 □海底捞月
        self.cb_tsumo = QCheckBox("自摸")
        self.cb_last_tile = QCheckBox("和绝张")
        self.cb_special_a = QCheckBox("抢杠和")
        self.cb_special_b = QCheckBox("海底捞月")
        # ★ v2.9.0 读番：勾上以后，每算出新的总番就念一遍「合计 N 番」
        self.cb_speak = QCheckBox("读番")
        self.cb_tsumo.setToolTip("自己抓进牌成和")
        self.cb_last_tile.setToolTip("和的这张牌，牌池中只剩最后一张")
        self.cb_special_a.setToolTip("勾选自摸时变为「杠上开花」")
        self.cb_special_b.setToolTip("勾选自摸时变为「妙手回春」")
        self.cb_speak.setToolTip(
            "算完番把总番念出来（合计 N 番）。\n"
            "音频取程序目录《%s》文件夹里现成的录音片段（★ 用哪一套在「设置 → 通用 → 读番语音包」里选）；\n"
            "同一个番数不会连着重念，想听当前结果可点结果区的「🔊 读番」"
            % VOICE_DIR_NAME)
        self.cb_tsumo.toggled.connect(self.on_tsumo_toggled)
        self.cb_speak.toggled.connect(self.on_speak_toggled)
        opt_row = QHBoxLayout()
        opt_row.setSpacing(14)
        for cb in (self.cb_tsumo, self.cb_last_tile,
                   self.cb_special_a, self.cb_special_b, self.cb_speak):
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
        # ★ v2.9.0 读番：总番旁边放一个「🔊 读番」，随时把当前结果念一遍
        head_row = QHBoxLayout()
        head_row.setContentsMargins(0, 0, 0, 0)
        head_row.setSpacing(8)
        self.lbl_total = QLabel("共 0 番")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        self.lbl_total.setFont(f)
        self.lbl_total.setStyleSheet("color:#2f7ff0;border:none;")
        head_row.addWidget(self.lbl_total)
        self.btn_speak = QPushButton("\U0001F50A 读番")
        self.btn_speak.setFocusPolicy(Qt.NoFocus)
        self.btn_speak.setCursor(Qt.PointingHandCursor)
        self.btn_speak.setToolTip("把当前总番念出来（合计 N 番）；音频在程序目录《%s》里"
                                  % VOICE_DIR_NAME)
        self.btn_speak.setStyleSheet(
            "QPushButton{border:1px solid #ccd4e0;border-radius:4px;background:#ffffff;"
            "color:#333;padding:3px 10px;} "
            "QPushButton:hover{background:#eef4ff;} "
            "QPushButton:disabled{color:#b6bcc6;border-color:#e6eaf0;background:#f7f8fa;}")
        self.btn_speak.clicked.connect(self.on_speak_clicked)
        head_row.addWidget(self.btn_speak)
        head_row.addStretch(1)
        rb.addLayout(head_row)
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
            "chi": "吃：先点「吃」，再依次点出 3 张相连的同花色牌；"
                   "再点一次「吃」＝取消",
            "peng": "碰：先点「碰」，再点要碰的牌（自动补足 3 张）；"
                    "再点一次「碰」＝取消",
            "minggang": "明杠：先点「明杠」，再点要杠的牌（自动补足 4 张）；"
                        "再点一次「明杠」＝取消",
            "angang": "暗杠：先点「暗杠」，再点要杠的牌（自动补足 4 张）；"
                      "再点一次「暗杠」＝取消",
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
        """菜单栏：文件 / **设置** / 帮助（★ v2.9.1）

        ★ v2.9.1：原来的「工具」菜单**改成菜单栏上的「设置」**——点一下直接弹出
          **多标签设置窗口**（`SettingsDialog`：通用 / Web 版 / 高级），
          原来工具菜单里的项都搬进窗口了（`_build_settings_actions()` 造的那些 QAction）。
        """
        bar = self.menuBar()
        self._build_settings_actions()
        m_file = bar.addMenu("文件(&F)")
        act_quit = QAction("退出(&Q)", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        # ★ 菜单栏上的「设置」：**不是下拉菜单**，是「点一下就弹窗」的动作
        #   （QMenuBar.addAction 一个没有子菜单的 action ＝ 菜单栏上的一个可点项）
        self.act_settings = QAction("设置(&S)", self)
        self.act_settings.setShortcut("Ctrl+,")          # 通用快捷键：偏好设置
        self.act_settings.setToolTip("打开设置窗口（通用 / Web 版 / 高级）；快捷键 Ctrl+,")
        self.act_settings.triggered.connect(lambda: self.open_settings())
        bar.addAction(self.act_settings)

        # ★ v2.9.6：统计（桌面端查看全部人的算番统计；手机/平板 Web 端在页面底栏「统计」看）
        self.act_stats = QAction("统计(&T)", self)
        self.act_stats.setToolTip("查看所有用户（含手机/平板 Web 端、桌面端本地）的算番统计")
        self.act_stats.triggered.connect(lambda: self.open_stats())
        bar.addAction(self.act_stats)

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

    # ---- 设置窗口（★ v2.9.1）
    def _build_settings_actions(self) -> None:
        """设置项的 QAction（原来「工具」菜单里的那些，v2.9.1 起由设置窗口承载）

        ★ 约定（踩过坑，别改）：这些 action **一律存成窗口属性**再引用，
          不要靠遍历 `menuBar()` 去找（拿到已失效的 QMenu 包装会报
          `RuntimeError: Internal C++ object already deleted`，v2.5.0 踩过）。
        ★ 也**不进任何菜单**了 —— 设置窗口里的复选框/按钮直接转发到这些 action；
          带快捷键的（Ctrl+Alt+A）额外 `self.addAction()` 挂到窗口上，快捷键照旧可用。
        """
        # Web 版（手机/平板浏览器算番）——**不是给程序调用的接口**，
        # 程序间调用请直接用 mahjong_core（见帮助页）
        self.act_api = QAction("启动 Web 版(&W)", self)
        self.act_api.setCheckable(True)
        self.act_api.setShortcut("Ctrl+Alt+A")
        self.act_api.setToolTip("给手机/平板浏览器用的 Web 版（默认 http://127.0.0.1:8718）\n"
                                "别的程序要算番请直接用 mahjong_core：import 或命令行调用，\n"
                                "不需要 HTTP、不需要端口、不需要先启动谁")
        self.act_api.triggered.connect(self._api_toggle)
        # ★ v2.9.1：记住「下次启动要不要自动开」——原来只是个藏在设置文件里的键，
        #   现在在设置窗口里露出来了（手动开/停时它也会跟着变，见 _api_start/_api_stop）
        self.act_api_auto = QAction("启动程序时自动开启 Web 版", self)
        self.act_api_auto.setCheckable(True)
        self.act_api_auto.setChecked(bool(self.api_auto_start))
        self.act_api_auto.setToolTip("勾上：下次打开本程序就自动开 Web 版服务，\n"
                                     "手机/平板不用等你在电脑上点一下")
        self.act_api_auto.triggered.connect(self._set_auto_start)
        self.act_api_lan = QAction("允许局域网访问（手机/平板）", self)
        self.act_api_lan.setCheckable(True)
        self.act_api_lan.setChecked(bool(self.api_lan))
        self.act_api_lan.setToolTip("勾上后服务绑到 0.0.0.0：同一 WiFi 下的手机/平板\n"
                                    "用浏览器打开 http://电脑IP:端口 即可算番（默认不要口令）")
        self.act_api_lan.triggered.connect(self._api_lan_toggle)
        self.act_api_token = QAction("设置访问口令(&K)…", self)
        self.act_api_token.triggered.connect(self._api_set_token)
        self.act_api_anon = QAction("免口令访问设置(&N)…", self)
        self.act_api_anon.setToolTip("设了口令后，哪些东西可以不输入口令直接用（含 Web 客户端）")
        self.act_api_anon.triggered.connect(self._api_set_anon)
        self.act_api_show = QAction("Web 版显示设置(&S)…", self)
        self.act_api_show.setToolTip("手机/平板页面上的「接口自测页」「换口令」按钮要不要显示"
                                     "（默认都不显示）")
        self.act_api_show.triggered.connect(self._api_set_show)
        self.act_api_info = QAction("Web 版地址与用法(&I)…", self)
        self.act_api_info.triggered.connect(self._api_show_info)
        self.act_api_port = QAction("Web 版端口设置(&P)…", self)
        self.act_api_port.triggered.connect(self._api_set_port)
        # ★ v2.9.0 读番：试听一句「合计 25 番」（顺便验一下《数字》音频在不在）
        self.act_speak = QAction("试听读番(&V)", self)
        self.act_speak.setToolTip("念一句「合计 25 番」听听效果；音频取程序目录《%s》"
                                  % VOICE_DIR_NAME)
        self.act_speak.triggered.connect(lambda: self._read_out(25))
        # ★ v2.9.1：默认开启自动读番（桌面版读番勾选框 + Web 页面默认值都看它）
        self.act_speak_default = QAction("默认开启自动读番", self)
        self.act_speak_default.setCheckable(True)
        self.act_speak_default.setChecked(bool(self.speak_default))
        self.act_speak_default.setToolTip(
            "勾上（默认）：算完一手牌自动念「合计 N 番」——\n"
            "  · 桌面版：主界面的「读番」勾选框默认打开；\n"
            "  · Web 版：手机/平板页面上的「🔊 读番」默认也是打开的。\n"
            "某一端自己点过开关，就以那端的选择为准。")
        self.act_speak_default.triggered.connect(self._set_speak_default)
        # ★ 这批 action 不再进任何菜单，快捷键就得自己挂到窗口上
        #   （Ctrl+Alt+A＝启动/停止 Web 版；设置窗口里的按钮转发到同一个 action）
        self.addAction(self.act_api)

    def open_settings(self, tab: int = 0) -> "SettingsDialog":
        """打开设置窗口（多标签：通用 / Web 版 / 高级）——菜单栏「设置」或 Ctrl+, 调它"""
        dlg = SettingsDialog(self, self)
        dlg.tabs.setCurrentIndex(max(0, min(int(tab), dlg.tabs.count() - 1)))
        self._settings_dlg = dlg
        try:
            dlg.exec()
        finally:
            self._settings_dlg = None
        return dlg

    def open_stats(self) -> Optional["StatsDialog"]:
        """打开统计窗口（★ v2.9.6）：查看全部用户的算番统计（按天聚合）"""
        dlg = StatsDialog(self, self.stats)
        self._stats_dlg = dlg
        try:
            dlg.exec()
        finally:
            self._stats_dlg = None
        return dlg

    def _set_stats_cols(self, cols) -> None:
        """★ v2.9.7：「统计」窗口显示哪几列

        来源：设置 → 通用 →「统计显示列」的复选框。
        改动立刻生效：① 已打开的统计窗口重建表头；② 自动落盘（下次启动沿用）；
        ③ 已开启的 Web 服务同步换新默认值（手机刷新页面后按新列显示，
           除非那台手机在自己「设置」里改过 —— 那就以手机为准）。
        """
        self.stats_cols = list(stats_cols_normalize_(cols, STATS_COLS_DESKTOP_DEFAULT_))
        dlg = getattr(self, "_stats_dlg", None)
        if dlg is not None:
            try:
                dlg.rebuild_columns(self.stats_cols)
            except Exception as _exc:      # noqa: BLE001
                sys.stderr.write("[stats] 刷新统计列失败：%r\n" % (_exc,))
        srv = getattr(self, "api_server", None)
        if srv is not None:
            try:                           # 服务已开着：直接改它的默认值，不用重启
                srv.stats_cols = tuple(self.stats_cols)
            except Exception:              # noqa: BLE001
                pass
        self._autosave_settings()

    def _set_detail_cols(self, cols) -> None:
        """★ v2.9.10：「逐手明细」窗口显示哪几列

        与 `_set_stats_cols` 完全对称：改动立刻生效、同步给已开启的 Web 服务、自动落盘。
        设置窗口与统计/明细窗口都是模态的，正常情况下改列时明细窗口是关着的；
        这里仍做一次刷新调用（防御性 —— 万一以后改成非模态就直接生效）。
        """
        self.detail_cols = list(detail_cols_normalize_(cols,
                                                       DETAIL_COLS_DESKTOP_DEFAULT_))
        dlg = getattr(self, "_detail_dlg", None)
        if dlg is not None:
            try:
                dlg.rebuild_columns(self.detail_cols)
            except Exception as _exc:      # noqa: BLE001
                sys.stderr.write("[stats] 刷新明细列失败：%r\n" % (_exc,))
        srv = getattr(self, "api_server", None)
        if srv is not None:
            try:
                srv.detail_cols = tuple(self.detail_cols)
            except Exception:              # noqa: BLE001
                pass
        self._autosave_settings()

    def _set_speak_default(self, checked: bool) -> None:
        """「默认开启自动读番」——桌面端勾选框与 Web 页面默认值一起跟着变"""
        self.speak_default = bool(checked)
        # 桌面端：立刻把主界面的「读番」也设成一样（setChecked 会连带触发念一次/存盘）
        if self.cb_speak.isChecked() != self.speak_default:
            self.cb_speak.setChecked(self.speak_default)
        # Web 版：页面是按请求现生成的，重启服务后手机/平板刷新即生效
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self._autosave_settings()
        if was_running:
            self._api_start(silent=True)
        self.statusBar().showMessage(
            "默认自动读番：%s（Web 版页面刷新后生效）"
            % ("开启" if self.speak_default else "关闭"), 5000)

    def _set_auto_start(self, checked: bool) -> None:
        """「启动程序时自动开启 Web 版」——只改偏好，不立刻起服务（下次启动才生效）"""
        self.api_auto_start = bool(checked)
        self._autosave_settings()
        self.statusBar().showMessage(
            "下次启动%s自动开启 Web 版" % ("" if self.api_auto_start else "不"), 5000)

    def _set_voice_set(self, name: str) -> None:
        """换读番语音包（★ v2.9.3）

        桌面端立刻改用这一套（下次读番就是新声音）；Web 版页面的默认值也跟着变 ——
        页面是按请求现生成的，重启一下服务，手机/平板刷新页面即生效
        （页面上自己选过的手机只影响那台手机，不受这里影响）。
        """
        name = str(name or "")
        if name == self.voice_set:
            return
        self.voice_set = name
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self._autosave_settings()
        if was_running:
            self._api_start(silent=True)
        try:
            vdir = (resolve_voice_dir(self.voice_set, app_dir())
                    if resolve_voice_dir else "") or ""
            n = (count_voice_clips(app_dir(), self.voice_set)
                 if count_voice_clips else 0) or 0
        except Exception:       # noqa: BLE001
            vdir, n = "", 0
        if self._settings_dlg is not None:
            self._settings_dlg.refresh_voice_state()
        self.statusBar().showMessage(
            "读番语音包：%s（%d 段）%s；Web 版页面刷新后生效"
            % (voice_set_label(self.voice_set), n, "——" + vdir if vdir else ""), 6000)

    def _reset_settings(self) -> None:
        """重置所有设置（高级页）——设置回默认；**算番状态（已选牌/副露）不动**"""
        if QMessageBox.question(
                self, "重置所有设置",
                "把全部设置恢复成默认值？\n\n"
                "· 默认开启自动读番 → 回到「开」\n"
                "· 读番语音包 → 回到「%s」\n" % VOICE_SET_DEFAULT +
                "· Web 版（自动开启 / 局域网 / 端口 / 口令 / 免口令 / 页面按钮）→ 回默认\n"
                "· 窗口大小与位置、读番勾选、圈风风位、花牌 → 回默认\n\n"
                "已经选好的牌 / 副露**不受影响**（那是「重置」按钮的事）。"
        ) != QMessageBox.Yes:
            return
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self._global_settings = {}
        self.speak_default = SPEAK_DEFAULT
        self.voice_set = VOICE_SET                                        # ★ v2.9.3 语音包
        self.api_port = DEFAULT_API_PORT
        self.api_lan = False
        self.api_token = ""
        self.api_anon = list(ANON_DEFAULT)
        self.web_show = list(WEB_SHOW_DEFAULT_)
        self.api_auto_start = False
        # 恢复默认几何（用 _apply_settings 走同一套逻辑，但别让它读回旧文件）
        self._apply_settings({"geo_ver": 0})
        self.resize(WIN_W, WIN_H)
        self._autosave_settings()
        if self.api_auto_start:
            self._api_start(silent=True)
        self._refresh_all()
        self.statusBar().showMessage("已重置所有设置（算番状态未动）", 5000)

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
          `Mahjong_Calculator.exe --hand "..." --json`（不需要 HTTP / 端口 / 先启动谁）。
        """
        if self._api_running():
            return True
        if ApiServer_ is None:
            if not silent:
                QMessageBox.warning(self, "Web 版不可用",
                                    "缺少 mahjong_api.py 或导入失败：\n%s" % API_IMPORT_ERROR)
            return False
        srv = ApiServer_(self._api_host(), self.api_port, self.api_token,
                         anon=tuple(self.api_anon), show=tuple(self.web_show),
                         # ★ v2.9.1：把「默认开启自动读番」告诉服务端 → 页面据此默认打开读番
                         speak_default=bool(self.speak_default),
                         # ★ v2.9.3：把「读番语音包」告诉服务端 → 页面「语音：」下拉的默认项
                         voice_set=str(self.voice_set or ""),
                         # ★ v2.9.6：把统计库交给 Web 服务，使 Web 端算番与桌面端查看共用同一份数据
                         stats=self.stats,
                         # ★ v2.9.7：Web 端「统计」面板默认显示哪几列 = 桌面端设置里的选择
                         stats_cols=list(self.stats_cols),
                         # ★ v2.9.10：Web 端「逐手明细」面板默认显示哪几列
                         detail_cols=list(self.detail_cols))
        try:
            url = srv.start()
        except Exception as exc:       # noqa: BLE001
            msg = getattr(exc, "message", None) or str(exc)
            self.statusBar().showMessage("Web 版启动失败：%s" % msg, 6000)
            if not silent:
                QMessageBox.warning(self, "Web 版启动失败",
                                    "%s\n\n可在「设置 → Web 版 → 端口设置…」里换一个端口。" % msg)
            return False
        self.api_server = srv
        self.api_port = srv.port_actual
        self.api_auto_start = True
        if getattr(self, "act_api", None) is not None:
            self.act_api.setChecked(True)
            self.act_api.setText("停止 Web 版(&W)")
        if getattr(self, "act_api_auto", None) is not None:
            self.act_api_auto.setChecked(True)      # 记住「下次启动也自动开」
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
        if remember and getattr(self, "act_api_auto", None) is not None:
            self.act_api_auto.setChecked(False)     # 「下次启动不自动开」跟着变
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
                "服务未启动。用「设置 → Web 版 → 启动 Web 版」（Ctrl+Alt+A）即可开启。\n\n"
                "默认只监听本机 127.0.0.1:%d；要让手机/平板用，请勾上"
                "「允许局域网访问」。\n\n"
                "★ 这是给**浏览器**看的网页版。其它程序要算番请直接用 mahjong_core：\n"
                "import 它，或用命令行调用本程序：\n"
                "  Mahjong_Calculator.exe --hand \"11123456789999m\" --win 9m --json"
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
            "  进程方式 ：Mahjong_Calculator.exe --hand \"11123456789999m\" --json\n"
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
                "想加一道门槛再自己设：设置 → Web 版 → 访问口令（可随手取消）。"
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

    def _api_set_show(self) -> None:
        """Web 版显示设置（v2.7.5）：页面上的「接口自测页」「换口令」按钮要不要显示：
        默认都不显示；改完存盘 + 重启服务（页面是按请求现生成的，重启后手机刷新即可看到）。
        """
        dlg = WebDisplayDialog(list(self.web_show), self)
        if dlg.exec() != QDialog.Accepted:
            return
        picked = dlg.selected()
        if picked == self.web_show:
            return
        self.web_show = picked
        was_running = self._api_running()
        if was_running:
            self._api_stop(silent=True, remember=False)
        self._autosave_settings()
        if was_running:
            self._api_start(silent=True)
        self.statusBar().showMessage("Web 版显示已更新：%s" % self._web_show_text(), 6000)

    def _web_show_text(self) -> str:
        """把当前「Web 页面显示」设置说成人话（状态栏/提示用）"""
        if not self.web_show:
            return "页面只显示「重置 / 布局」（默认，两个按钮都不显示）"
        names = {k: label.split("（")[0] for k, label, _ in (WEB_SHOW_ITEMS_ or ())}
        return "页面显示：" + "、".join(names.get(k, k) for k in self.web_show)

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
            "speak": bool(self.cb_speak.isChecked()),      # ★ v2.9.0 读番（当前开关）
            "speak_default": bool(self.speak_default),     # ★ v2.9.1 默认开启自动读番
            "voice_set": str(self.voice_set),              # ★ v2.9.3 读番语音包
            "stats_cols": list(self.stats_cols),           # ★ v2.9.7 统计面板显示哪几列
            "detail_cols": list(self.detail_cols),         # ★ v2.9.10 逐手明细显示哪几列
            "mode": self.mode,
            "page": self.stack.currentIndex(),
            "api_port": int(self.api_port),
            "api_auto_start": bool(self.api_auto_start),
            "api_lan": bool(self.api_lan),
            "api_token": str(self.api_token or ""),
            "api_anon": list(self.api_anon),
            "api_show": list(self.web_show),
        }

    def _apply_settings(self, s: dict) -> None:
        for w in (self.cb_tsumo, self.cb_last_tile,
                  self.cb_special_a, self.cb_special_b, self.cb_speak):
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
        # ★ v2.9.1：先取「默认开启自动读番」，再由它决定「读番」勾选框
        #   · 没这个键（老设置 / 新装）→ 用常量 SPEAK_DEFAULT（开）⇒「无论哪个端都自动读番」
        #   · 有这个键 → 说明设置已经过 v2.9.1，此时 `speak` 才是**用户自己的选择**，听它的
        #   （重要：v2.9.1 之前存下来的 `speak:false` 只是「当时的默认值」，不是用户的选择，
        #     所以要按新默认「开」处理，否则升级上来的人会看到「勾选框明明勾着、主界面却没勾」）
        self.speak_default = bool(s.get("speak_default", SPEAK_DEFAULT))
        speak_on = (bool(s.get("speak", self.speak_default)) if "speak_default" in s
                    else self.speak_default)
        self.cb_speak.setChecked(speak_on)                                   # v2.9.0 读番
        if getattr(self, "act_speak_default", None) is not None:
            self.act_speak_default.setChecked(self.speak_default)
        # ★ v2.9.3：读番语音包 —— 老设置（没有这个键）就用默认那套「女声」
        #   （名字对应的目录被删了也不用管：resolve_voice_dir() 会自动回退，不会没声音）
        self.voice_set = str(s.get("voice_set") or VOICE_SET)
        # ★ v2.9.7：统计面板显示哪几列（老设置没有这个键 → 桌面端默认全列）
        # ★ v2.9.9：老设置补齐新增列（番种）
        self.stats_cols = list(stats_cols_new_merged_(s.get("stats_cols"),
                                                      STATS_COLS_DESKTOP_DEFAULT_))
        # ★ v2.9.10：逐手明细显示哪几列（老设置没有这个键 → 明细 10 列全开）
        self.detail_cols = list(detail_cols_new_merged_(s.get("detail_cols"),
                                                        DETAIL_COLS_DESKTOP_DEFAULT_))
        for w in (self.cb_tsumo, self.cb_last_tile,
                  self.cb_special_a, self.cb_special_b, self.cb_speak):
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
        if mode in MODE_KEYS:
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
        # ★ v2.7.5：Web 页面显示项（老设置没这个键 → 回默认「都不显示」）
        picks_show = s.get("api_show")
        if isinstance(picks_show, (list, tuple)):
            self.web_show = [k for k in WEB_SHOW_KEYS_ if k in picks_show]
        else:
            self.web_show = list(WEB_SHOW_DEFAULT_)
        if getattr(self, "act_api_lan", None) is not None:
            self.act_api_lan.setChecked(self.api_lan)
        if getattr(self, "act_api_auto", None) is not None:
            self.act_api_auto.setChecked(self.api_auto_start)

    def _connect_autosave(self) -> None:
        for w in (self.cb_tsumo, self.cb_last_tile,
                  self.cb_special_a, self.cb_special_b, self.cb_speak):
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
        if self.voice is not None:      # ★ v2.9.0：退出时别还在念
            self.voice.stop()
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
        """切换模式；★ v2.8.0：再点一次同一个按钮＝取消该模式，回到默认的「立牌」"""
        key = MODE_KEYS[idx]
        if key != "stand" and key == self.mode:
            self.btn_mode_stand.setChecked(True)     # 取消 → 回「立牌」
            self.statusBar().showMessage(
                "已取消「%s」，回到「立牌」" % MODE_TEXTS[key], 2000)
            key = "stand"
        self.mode = key
        self.pending_chi = []
        self._refresh_all()
        self._autosave_settings()

    def _on_option_changed(self, *args) -> None:      # noqa: ARG002
        self._refresh_all()
        self._autosave_settings()

    # ---- 读番（★ v2.9.0）
    def _read_out(self, total: int) -> bool:
        """念「合计 N 番」：音频取程序目录《数字》（别的机器上只要目录对就行）

        返回「是否真的开始念了」；音频缺失 / 非 Windows → False（不影响算番）。
        ★ v2.9.2：音频缺一段就**整句不念**（宁可不出声，也不要把番数念错 ——
          `readout_paths()` 是「缺哪段跳哪段」，直接拿来播会少念一个字）。
        """
        if self.voice is None or readout_info is None:
            return False
        try:
            info = readout_info(int(total), base_dir=app_dir(), voice_set=self.voice_set)
        except Exception:       # noqa: BLE001
            return False
        if not info.get("ok"):
            return False
        paths = [c["path"] for c in info.get("clips", [])]     # type: ignore[union-attr]
        if not paths:
            return False
        self._last_spoken = int(total)
        return bool(self.voice.play(paths))

    def on_speak_clicked(self) -> None:
        """点结果区「🔊 读番」：把当前总番念一遍"""
        if self._total is None:
            self.statusBar().showMessage("还没有算出番数", 2000)
            return
        if not self._read_out(self._total):
            self.statusBar().showMessage(
                "念不出来：程序目录下没有《%s》音频（读番用系统自带播放器，"
                "Windows 才出声）" % VOICE_DIR_NAME, 4000)

    def on_speak_toggled(self, checked: bool) -> None:
        """勾上「读番」时，若已经有结果就先念一次（马上能听到效果）"""
        if checked and self._total is not None:
            self._read_out(self._total)

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
        # ★ v2.9.0 读番：正在念的停下、忘记念过的番数（**不动「读番」勾选** ——
        #   它是个偏好设置，不是这一手牌的状态；下次算出番照样会念）
        self._last_spoken = None
        if self.voice is not None:
            self.voice.stop()
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
    # 手机 / 触屏没有右键，所以「已选牌」区的每一张牌都可以直接点：点一下＝取消这张。
    # 右键仍保留，鼠标用户习惯不变；★ v2.8.0 起牌选择区的红角标不再可点（只显示张数）。
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
        self._total = None                      # ★ v2.9.0：还没得出总番
        self.btn_speak.setEnabled(False)
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
        # ★ v2.9.6：桌面端本地算番也计入统计（client_type='desktop'）
        self._record_desktop_stats(s, masked, win)
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
        # ★ v2.9.0 读番：合计出番以后念出来（勾了「读番」才念；同一个番数不重复念）
        self._total = s.total
        self.btn_speak.setEnabled(True)
        if s.fans and self.cb_speak.isChecked() and self._last_spoken != s.total:
            self._read_out(s.total)

    def _desktop_nick(self) -> str:
        """★ v2.9.12：把本机计算机名登记成「desktop」这个用户的昵称（只登记一次）

        统计表的「昵称」列读的是 user_nick 表，所以必须在**这里**登记，
        光把名字写进 score_log 只能让逐手明细显示，统计表里还是「-」。
        计算机名不会变，`_nick_done` 记住已登记过，避免每手牌都写一次库。
        """
        if getattr(self, "_nick_done", None):
            return self._nick_done
        name = desktop_nick()
        if name and self.stats is not None:
            try:
                name = self.stats.set_nick("desktop", "", name)
            except Exception as _exc:   # noqa: BLE001
                sys.stderr.write("[stats] 登记本机昵称失败：%r\n" % (_exc,))
        self._nick_done = name
        return name

    def _record_desktop_stats(self, s, masked, win) -> None:
        """★ v2.9.6：把桌面端本次算番结果落库（client_type='desktop'）。

        - 同一手牌（牌 + 副露 + 和张）只记一次，避免选项切换反复刷数；
        - 落库失败只记日志，绝不抛异常影响算番/界面。
        """
        if self.stats is None or s is None:
            return
        try:
            sig = "desktop|%s|%s|%s" % (
                tuple(sorted((t, n) for t, n in self.concealed.items())),
                tuple(tuple(m.tiles) for m in self.melds),
                win,
            )
            if getattr(self, "_last_stat_sig", None) == sig:
                return
            self._last_stat_sig = sig
            self.stats.record(
                ts_ms=int(time.time() * 1000),
                user_key="desktop", uuid="", client_type="desktop",
                ip="", ua="", total_fan=int(s.total), base=int(s.base),
                reach=1 if s.ok else 0, fans_n=len(s.fans), sig=sig,
                # ★ v2.9.9：番种名落库（明细里能看到这一手算了哪些番种）
                fans=fans_text_(s.fans),
                # ★ v2.9.12：昵称填本机计算机名 —— 统计里一眼认出「这是本机」。
                #   **必须先登记进昵称表**：统计表（聚合）的「昵称」列读的是
                #   user_nick 表，光写进 score_log 只能让明细显示，统计里还是「-」。
                #   计算机名不会变，所以只在第一次 / 改名时才写库，别每次算番都写。
                nick=self._desktop_nick(),
            )
        except Exception as _exc:      # noqa: BLE001
            sys.stderr.write("[stats] 桌面算番记录失败：%r\n" % (_exc,))

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


# ------------------------------------------------------------------ 统计窗口（★ v2.9.6）

# ★ v2.9.12：桌面端（本机程序）没有 UA，所以「系统 / 浏览器 / 设备型号」三列
#   在桌面行上本来会是一片「-」。但本机有两样东西是**真拿得到**的：
#     · 计算机名（platform.node()，Windows 上形如 DESKTOP-A1B2C3）
#       —— 这是全项目唯一一处真正的「设备名称」，填进「昵称」列
#     · 系统名（platform.system()）—— 填进「系统」列，桌面行就不会空着
#   浏览器 / 型号桌面端确实没有，老实显示「桌面程序」和「-」。
DESKTOP_OS = "Windows"
try:
    _s = (platform.system() or "").strip()
    if _s:
        DESKTOP_OS = _s
except Exception:       # noqa: BLE001
    pass


def desktop_nick() -> str:
    """本机计算机名 → 桌面记录的「昵称」列（拿不到就空串，不让统计崩）"""
    try:
        n = (platform.node() or "").strip()
        return n[:24] if n else ""
    except Exception:   # noqa: BLE001
        return ""


def _ua_brief(ua: str) -> str:
    """把一长串 User-Agent 压成一个一眼认得出的设备名（完整串放单元格 tip 里）"""
    low = (ua or "").lower()
    if not low:
        return "-"
    for kw, name in (("micromessenger", "微信"), ("ipad", "iPad"),
                     ("iphone", "iPhone"), ("harmony", "鸿蒙"),
                     ("android", "Android"), ("windows", "Windows"),
                     ("macintosh", "Mac"), ("mac os x", "Mac"),
                     ("linux", "Linux")):
        if kw in low:
            return name
    return (ua or "").split("/")[0].strip()[:14] or "-"


def _device_cell(key: str, r: dict) -> str:
    """★ v2.9.12：昵称 / 系统 / 浏览器 / 设备型号 四列的取值（统计窗口与明细窗口共用）

    桌面行（client_type='desktop'）压根没有 UA，所以「系统」列会落到本机系统名、
    「浏览器」列显示「桌面程序」—— 免得整列一片「-」看着像坏了。
    「设备型号」桌面端确实没有（那是手机的概念），老实显示「-」。
    """
    if key == "nick":
        return str(r.get("nick") or "-")
    if key == "os":
        v = str(r.get("os") or "")
        if v and v != "-":
            return v
        return DESKTOP_OS if r.get("client_type") == "desktop" else "-"
    if key == "browser":
        v = str(r.get("browser") or "")
        if v and v != "-":
            return v
        return "桌面程序" if r.get("client_type") == "desktop" else "-"
    if key == "dev":
        return str(r.get("dev") or "-")
    return ""


class StatsDialog(QDialog):
    """算番统计查看窗口（桌面端）。与 Web 端「统计」面板共用同一份 SQLite 数据。

    - 按天聚合（下拉框选某天，或「全部日期」跨天合计）
    - 列：标识(UUID) / 客户端 / IP / UA(设备) / 合计番数 / 次数 / 达标 / 最近
      —— ★ 用户的 IP + UUID + UA 都直接列出来，方便认出「这一条到底是谁」；
          完整 UA 太长，表格里只显示设备名，鼠标停在单元格上看全串。
    - ★ v2.9.7：**显示哪几列由「设置 → 通用 → 统计显示列」决定**，
      这里只按选中的列渲染；`rebuild_columns()` 可热切换，不用关窗口重开。
    - 统计库不可用时给出明确提示，不崩溃
    """

    # 列 key → 表头文字（key 与 mahjong_api.STATS_COL_ITEMS 完全一致）
    COL_LABELS = dict(STATS_COL_ITEMS_)
    # 需要「按内容撑宽」而不是「平分剩余宽度」的列（text 类）
    WIDE_COLS = ("ua", "last")

    def __init__(self, parent, stats):
        super().__init__(parent)
        self.stats = stats
        self.setWindowTitle("算番统计")
        # ★ v2.9.6：要并排显示 UUID / IP / UA，窗口比原来宽一些
        self.setMinimumSize(860, 460)
        self.cols: List[str] = []          # ★ v2.9.7 当前显示的列 key（按顺序）

        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("日期"))
        self.cmb_day = QComboBox()
        self.cmb_day.setMinimumWidth(170)
        self.cmb_day.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.cmb_day)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._refresh)
        top.addWidget(self.btn_refresh)
        # ★ v2.9.9：选中某个人 → 看他的逐手明细（双击表格任意一行也一样）
        self.btn_detail = QPushButton("明细…")
        self.btn_detail.setToolTip(
            "看选中那个人的<b>逐手明细</b>：每一手的时间（精确到毫秒）、番数、"
            "起番、是否达标和这一手算了哪些番种。\n"
            "（也可以直接<b>双击</b>表格里那一行）")
        self.btn_detail.clicked.connect(self._open_detail)
        top.addWidget(self.btn_detail)
        top.addStretch(1)
        lay.addLayout(top)

        self.lbl_sum = QLabel()
        self.lbl_sum.setStyleSheet("font-weight:bold;padding:4px 0;")
        lay.addWidget(self.lbl_sum)
        # ★ v2.9.9：全局番种榜（「无番和×3、碰碰和×1」）
        self.lbl_fans = QLabel()
        self.lbl_fans.setStyleSheet("color:#666;padding:0 0 4px;")
        self.lbl_fans.setWordWrap(True)
        lay.addWidget(self.lbl_fans)

        self.tbl = QTableWidget(0, 0)      # ★ v2.9.7：列数由 rebuild_columns() 决定
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.doubleClicked.connect(lambda _idx: self._open_detail())
        lay.addWidget(self.tbl, 1)

        self.lbl_tip = QLabel(
            "IP+UUID 为主、IP+UA 兜底；按天统计，毫秒级时间戳；桌面端本地算番也计入。"
            "★ 选中某个人点「明细…」（或双击那一行）看他的逐手记录。")
        self.lbl_tip.setStyleSheet("color:#666;font-size:11px;")
        lay.addWidget(self.lbl_tip)

        self._init_days()
        # ★ v2.9.8：按主窗口的设置建好列（内部会顺带刷一次数据）
        self.rebuild_columns(self._win_cols())

    def _win_cols(self) -> List[str]:
        """从主窗口拿「显示哪几列」；拿不到就全列（统计只是附加功能，不能因此崩）"""
        win = self.parent()
        cols = getattr(win, "stats_cols", None)
        if cols:
            return list(cols)
        return list(STATS_COL_KEYS_)

    def rebuild_columns(self, cols) -> None:
        """★ v2.9.7：重建表头（列数/列宽变了都要走这里），随后重刷数据"""
        self.cols = list(stats_cols_normalize_(cols, STATS_COLS_DESKTOP_DEFAULT_))
        self.tbl.setColumnCount(len(self.cols))
        self.tbl.setHorizontalHeaderLabels(
            [self.COL_LABELS.get(k, k) for k in self.cols])
        hh = self.tbl.horizontalHeader()
        for c, k in enumerate(self.cols):
            # 「用户」吃掉剩余宽度；「番种」那串可能很长，给固定宽度 + 可拖动（不然会把别的列挤出屏幕）
            if k == "user":
                mode = QHeaderView.Stretch
            elif k == "fans":
                mode = QHeaderView.Interactive
            else:
                mode = QHeaderView.ResizeToContents
            hh.setSectionResizeMode(c, mode)
        if "fans" in self.cols:
            self.tbl.setColumnWidth(self.cols.index("fans"), 240)
        self._refresh()

    def _init_days(self) -> None:
        self.cmb_day.blockSignals(True)
        self.cmb_day.clear()
        self.cmb_day.addItem("全部日期", None)
        if self.stats is not None:
            try:
                for d in self.stats.list_days():
                    self.cmb_day.addItem(d, d)
            except Exception:      # noqa: BLE001
                pass
        self.cmb_day.blockSignals(False)

    def _refresh(self) -> None:
        if self.stats is None:
            self.lbl_sum.setText("统计库不可用（mahjong_stats 导入失败）")
            self.tbl.setRowCount(0)
            return
        day = self.cmb_day.currentData()
        try:
            rows = self.stats.aggregate(day)
            sum_ = self.stats.total_summary(day)
        except Exception as exc:    # noqa: BLE001
            self.lbl_sum.setText("读取统计失败：%r" % (exc,))
            self.tbl.setRowCount(0)
            return
        self.lbl_sum.setText("共 %d 手 / %d 番 / %d 人"
                             % (sum_.get("hands", 0), sum_.get("fan", 0),
                                sum_.get("users", 0)))
        # ★ v2.9.9：全局番种榜
        fans_txt = str(sum_.get("fans_txt") or "")
        self.lbl_fans.setText("番种：" + fans_txt if fans_txt
                              else "番种：（还没有记录到番种——老记录没有番种名，"
                                   "升级后新算的手才有）")
        self._rows = rows           # ★ v2.9.9：明细窗口要按 user_key 反查，先留一份
        self.tbl.setRowCount(len(rows))
        for i, u in enumerate(rows):
            for c, k in enumerate(self.cols):
                item = QTableWidgetItem(self._cell_text(k, u))
                tip = self._cell_tip(k, u)          # ★ 完整 UUID / UA 挂 tooltip
                if tip:
                    item.setToolTip(tip)
                self.tbl.setItem(i, c, item)

    def _open_detail(self) -> None:
        """★ v2.9.9：打开选中那个人的「逐手明细」窗口"""
        if self.stats is None:
            QMessageBox.information(self, "明细", "统计库不可用，看不了明细。")
            return
        row = self.tbl.currentRow()
        rows = getattr(self, "_rows", None) or []
        if row < 0 or row >= len(rows):
            QMessageBox.information(self, "明细", "先在表格里选中一个人（点它那一行）。")
            return
        u = rows[row]
        dlg = StatsDetailDialog(self, self.stats,
                                str(u.get("user_key") or ""),
                                self.cmb_day.currentData())
        dlg.exec()

    # ---- 单元格取值（★ v2.9.7：按列 key 取，不再写死 8 列）
    def _cell_text(self, key: str, u: dict) -> str:
        if key == "user":
            # 有 UUID 用 UUID，没有就退回 user_key（h:<IP+UA哈希>）
            return str(u.get("uuid") or u.get("user_key") or "?")
        if key == "ctype":
            return "桌面" if u.get("client_type") == "desktop" else "Web"
        if key == "ip":
            return str(u.get("ip") or "-")
        if key == "ua":
            return _ua_brief(str(u.get("ua") or ""))
        if key == "fan":
            return str(u.get("total_fan", 0))
        if key == "cnt":
            return str(u.get("cnt", 0))
        if key == "reach":
            return str(u.get("reach_cnt", 0))
        if key == "last":
            last = u.get("last_ts")
            return (time.strftime("%Y-%m-%d %H:%M", time.localtime(last / 1000))
                    if last else "-")
        if key == "fans":                       # ★ v2.9.9 番种汇总
            return str(u.get("fans") or "-")
        return _device_cell(key, u)             # ★ v2.9.12 昵称/系统/浏览器/型号

    def _cell_tip(self, key: str, u: dict) -> str:
        """鼠标停下来看完整串：整列被截断时靠这个认人"""
        if key == "user":
            return "user_key：%s" % (u.get("user_key") or "-")
        if key == "ua":
            return str(u.get("ua") or "（无 UA）")
        if key == "fans":                       # ★ v2.9.9 番种串可能很长，给完整内容
            return str(u.get("fans") or "（无番种记录）")
        return ""


class StatsDetailDialog(QDialog):
    """★ v2.9.9：某个人的**逐手牌明细**（时间倒序）

    统计窗口是「按人聚合」的，看不出他具体打了哪几手。这里把 `score_log` 的原始行
    逐条列出来：时间（**精确到毫秒**）、客户端、IP、番数、起番、是否达标、
    番种数、**这一手算了哪些番种**。顶部还给这个人的番种榜。

    ★ 老记录（v2.9.9 之前算的）没有番种名 —— 那一行显示「-」，属正常，
      不是 bug：番种是从这一版才开始落库的，历史数据补不回来。

    ★ v2.9.10：**显示哪几列由「设置 → 通用 → 明细显示列」决定**，默认全开；
      `rebuild_columns()` 可热切换，不用关窗口重开。
    """

    # 列 key → 表头文字（key 与 mahjong_api.DETAIL_COL_ITEMS 完全一致）
    COL_LABELS = dict(DETAIL_COL_ITEMS_)
    # 需要「按内容撑宽」而不是「平分剩余宽度」的列（文字长的）
    WIDE_COLS = ("time", "ua")

    def __init__(self, parent, stats, user_key: str, day=None):
        super().__init__(parent)
        self.stats = stats
        self.user_key = user_key
        self.day = day
        self.cols: List[str] = []          # ★ v2.9.10 当前显示的列 key（按顺序）
        self.setWindowTitle("逐手明细 · " + (user_key or "?"))
        self.setMinimumSize(760, 420)

        lay = QVBoxLayout(self)
        self.lbl_head = QLabel()
        self.lbl_head.setStyleSheet("font-weight:bold;padding:2px 0;")
        lay.addWidget(self.lbl_head)
        self.lbl_fans = QLabel()
        self.lbl_fans.setWordWrap(True)
        self.lbl_fans.setStyleSheet("color:#666;padding:0 0 4px;")
        lay.addWidget(self.lbl_fans)

        self.tbl = QTableWidget(0, 0)      # ★ v2.9.10：列数由 rebuild_columns() 决定
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        lay.addWidget(self.tbl, 1)

        foot = QHBoxLayout()
        self.lbl_tip = QLabel("时间精确到毫秒；番种从 v2.9.9 起落库，更早的记录显示「-」。")
        self.lbl_tip.setStyleSheet("color:#666;font-size:11px;")
        foot.addWidget(self.lbl_tip)
        foot.addStretch(1)
        btn = QPushButton("关闭")
        btn.setDefault(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.accept)
        foot.addWidget(btn)
        lay.addLayout(foot)
        # ★ v2.9.10：先按主窗口的设置建好列（内部会顺带刷一次数据）
        self.rebuild_columns(self._win_cols())

    def _win_cols(self) -> List[str]:
        """沿父窗口链找主窗口的 `detail_cols`；拿不到就全列（明细不能因此崩）

        为什么是「沿链找」：这个窗口的 parent 可能是统计窗口（它才是主窗口的直接子窗口），
        也可能直接是主窗口，写死一层会漏。
        """
        w = self.parent()
        for _ in range(4):
            if w is None:
                break
            cols = getattr(w, "detail_cols", None)
            if cols:
                return list(cols)
            w = w.parent() if hasattr(w, "parent") else None
        return list(DETAIL_COL_KEYS_)

    def rebuild_columns(self, cols) -> None:
        """★ v2.9.10：重建明细表头（列数/列宽变了都走这里），随后重刷数据"""
        self.cols = list(detail_cols_normalize_(cols, DETAIL_COLS_DESKTOP_DEFAULT_))
        self.tbl.setColumnCount(len(self.cols))
        self.tbl.setHorizontalHeaderLabels(
            [self.COL_LABELS.get(k, k) for k in self.cols])
        hh = self.tbl.horizontalHeader()
        for c, k in enumerate(self.cols):
            # 「番种」「UA」这类长文本列吃掉剩余宽度；其余按内容撑宽
            if k in ("fans", "ua"):
                mode = QHeaderView.Stretch
            elif k in self.WIDE_COLS:
                mode = QHeaderView.ResizeToContents
            else:
                mode = QHeaderView.ResizeToContents
            hh.setSectionResizeMode(c, mode)
        self._refresh()

    def _refresh(self) -> None:
        if self.stats is None:
            self.lbl_head.setText("统计库不可用")
            self.tbl.setRowCount(0)
            return
        try:
            rows = self.stats.detail_rows(self.user_key, self.day)
            fans = self.stats.fans_top(self.day, self.user_key)
        except Exception as exc:        # noqa: BLE001
            self.lbl_head.setText("读取明细失败：%r" % (exc,))
            self.tbl.setRowCount(0)
            return
        when = ("%s" % self.day) if self.day else "全部日期"
        self.lbl_head.setText("%s　%s　共 %d 手" % (self.user_key, when, len(rows)))
        self.lbl_fans.setText(
            "番种：" + "、".join("%s×%d" % (n, c) for n, c in fans) if fans
            else "番种：（没有番种记录）")
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, k in enumerate(self.cols):
                item = QTableWidgetItem(self._cell_text(k, r))
                tip = self._cell_tip(k, r)
                if tip:
                    item.setToolTip(tip)
                self.tbl.setItem(i, c, item)

    # ---- 单元格取值（★ v2.9.10：按列 key 取，不再写死 8 列）
    def _cell_text(self, key: str, r: dict) -> str:
        if key == "day":
            return str(r.get("day") or "-")
        if key == "time":
            ts = int(r.get("ts_ms") or 0)
            # ★ 毫秒级：%Y-%m-%d %H:%M:%S + 三位毫秒
            return (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))
                    + ".%03d" % (ts % 1000)) if ts else "-"
        if key == "ctype":
            return "桌面" if r.get("client_type") == "desktop" else "Web"
        if key == "ip":
            return str(r.get("ip") or "-")
        if key == "ua":
            return _ua_brief(str(r.get("ua") or ""))
        if key == "fan":
            return str(r.get("total_fan", 0))
        if key == "base":
            return str(r.get("base", 0))
        if key == "reach":
            return "是" if r.get("reach") else "否"
        if key == "fans_n":
            return str(r.get("fans_n", 0))
        if key == "fans":
            names = [s for s in str(r.get("fans") or "").split("|") if s.strip()]
            return "、".join(names) or "-"
        return _device_cell(key, r)             # ★ v2.9.12 昵称/系统/浏览器/型号

    def _cell_tip(self, key: str, r: dict) -> str:
        """长串挂 tooltip：UA 完整串、番种完整清单"""
        if key == "ua":
            return str(r.get("ua") or "（无 UA）")
        if key == "fans":
            return str(r.get("fans") or "（无番种记录）")
        if key == "dev":                        # ★ v2.9.12 型号可能被截断，挂完整值
            return str(r.get("dev") or "（浏览器未提供型号）")
        return ""


# ------------------------------------------------------------------ 入口

def main() -> int:
    # ★ v2.6.0：带命令行参数时走「一次调用算番」，**不启动界面**（也不需要 HTTP / 端口 / 先启动谁）：
    #     Mahjong_Calculator.exe --hand "11123456789999m" --win 9m --json
    #     Mahjong_Calculator.exe --hand "..." --meld kong:5555z --waits --text
    if cli_wanted is not None and cli_wanted(sys.argv[1:]):
        return cli_main(sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_EN)       # 程序标识用英文名（v2.7.3）
    app.setApplicationDisplayName(APP_NAME)   # 界面上显示中文名
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
