# -*- coding: utf-8 -*-
"""User-Agent 解析（v2.9.12）

职责：把一长串 UA 拆成「系统 / 浏览器 / 设备型号」三段人话，
      给统计表与明细表的 os / browser / dev 三列用。

为什么单独一个模块：
  · 桌面端（Mahjong_Calculator.py）和 Web 端（mahjong_api.py）都要解析，
    各自写一份迟早不一致；
  · mahjong_stats.py 只管落库与聚合，塞进 UA 规则会让它职责变糊；
  · UA 规则会随浏览器更新而变，独立文件改起来不用碰统计逻辑。

★ 必须知道的现实（2026 年）——不是我们解析得不好，是浏览器不给：
  · 安卓 Chrome / Edge / Opera / 三星浏览器：UA 削减后型号恒为字母 "K"，
    Android 版本恒为 10（`Android 10; K`），型号**拿不到**；
  · 安卓 WebView（微信 X5 等）：Android 16 起同样被削减（Google 官方公告），
    只有 Android 15 及以下还留着真实型号；
  · 鸿蒙 NEXT 全系：UA 结构里**根本没有型号字段**（官方字段表只有
    DeviceType / OSName / OSVersion / DistributionOS / ArkWeb / Mobile）；
  · iOS 全系：只有 "iPhone"，分不出 13 还是 16。
  → 所以 dev 列在很多设备上只能是 "-"，这属于预期行为，不是 bug。
    真正能补上型号的只有 UA-CH 的 Sec-CH-UA-Model，但它只在 Chromium +
    HTTPS 安全上下文才发，局域网明文 http 拿不到。
"""
from __future__ import annotations

import re
from typing import Optional

__all__ = ["ua_os", "ua_browser", "ua_model", "model_pretty", "ua_brief"]


# ---------------------------------------------------------------- 系统
# iOS 的版本号是**真的**（苹果没削减），可以显示；
# Android 的版本号在 Chromium 上恒为 10（假的），所以不显示，避免误导。
_RE_IOS_VER = re.compile(r"(?:iPhone OS|CPU OS|iPad; CPU OS)\s+(\d+)_(\d+)")
_RE_OHM_VER = re.compile(r"HarmonyOS\s+(\d+(?:\.\d+)?)")
_RE_OHM_VER2 = re.compile(r"OpenHarmony\s+(\d+(?:\.\d+)?)")
_RE_ANDROID_VER = re.compile(r"Android\s+(\d+(?:\.\d+)?)")


def ua_os(ua: Optional[str]) -> str:
    """UA → 系统名："鸿蒙 6.0" / "iOS 17.0" / "Android" / "Windows" / "macOS" / "Linux"

    拿不到就返回 "-"（不返回空串，表格里要有东西可看）。
    """
    s = (ua or "").strip()
    if not s:
        return "-"
    low = s.lower()

    # 鸿蒙：优先发行版 HarmonyOS，退回底座 OpenHarmony
    m = _RE_OHM_VER.search(s)
    if m:
        return "鸿蒙 %s" % m.group(1)
    if "openharmony" in low or "harmony" in low or "arkweb" in low:
        m2 = _RE_OHM_VER2.search(s)
        return ("鸿蒙 %s" % m2.group(1)) if m2 else "鸿蒙"

    # iOS / iPadOS
    if "iphone" in low or "ipad" in low or "ipod" in low:
        m = _RE_IOS_VER.search(s)
        if m:
            return "iOS %s.%s" % (m.group(1), m.group(2))
        return "iOS"

    # Android：版本已被 Chromium 冻结成 10，不显示版本号以免误导
    if "android" in low:
        return "Android"

    if "windows" in low:
        return "Windows"
    if "macintosh" in low or "mac os x" in low:
        return "macOS"
    if "cros" in low:
        return "ChromeOS"
    if "linux" in low:
        return "Linux"

    return "-"


# ---------------------------------------------------------------- 浏览器 / App
# ★ 顺序很重要：App 内置标识必须排在 Chrome 前面 ——
#   微信 / QQ / UC 的 UA 里都带 "Chrome"，先判 Chrome 就全变成 Chrome 了。
_BROWSER_RULES = (
    ("micromessenger", "微信"),
    ("mqqbrowser",     "QQ浏览器"),
    (" qq/",           "QQ浏览器"),
    ("ucbrowser",      "UC浏览器"),
    ("ubrowser",       "UC浏览器"),
    ("quark",          "夸克"),
    ("aweme",          "抖音"),
    ("newsarticle",    "今日头条"),
    ("alipay",         "支付宝"),
    ("aliapp",         "支付宝"),
    ("weibo",          "微博"),
    ("baiduboxapp",    "百度"),
    ("baidubrowser",   "百度"),
    ("dingtalk",       "钉钉"),
    ("huaweibrowser",  "华为浏览器"),
    ("arkweb",         "鸿蒙内置"),
    ("heytapbrowser",  "OPPO浏览器"),
    ("vivobrowser",    "vivo浏览器"),
    ("miuibrowser",    "小米浏览器"),
    ("samsungbrowser", "三星浏览器"),
    ("opr/",           "Opera"),
    ("edg/",           "Edge"),
    ("edga/",          "Edge"),
    ("edgios/",        "Edge"),
    ("firefox",        "Firefox"),
    ("fxios/",         "Firefox"),
    ("chrome",         "Chrome"),
    ("safari",         "Safari"),
)


def ua_browser(ua: Optional[str]) -> str:
    """UA → 浏览器 / App 名："微信" / "Chrome" / "Edge" / "鸿蒙内置"

    这一项 100% 拿得到（App 名和浏览器名浏览器都会说），实在认不出才返回 "-"。
    """
    s = (ua or "").strip()
    if not s:
        return "-"
    low = s.lower()
    for kw, name in _BROWSER_RULES:
        if kw in low:
            return name
    # 什么标志都没有，但有 wv（Android WebView）→ 某个 App 的内置浏览器
    if "wv)" in low or "; wv" in low:
        return "App内置"
    return "-"


# ---------------------------------------------------------------- 设备型号
# Android 完整格式：(Linux; Android 14; SM-S918U Build/UP1A.231005.007; wv)
#                                      ^^^^^^^^ 型号就在这里
# 鸿蒙 / iOS 的 UA 里压根没有这一段，所以这两个平台自然解析不出。
_RE_ANDROID_MODEL = re.compile(
    r"Android\s+\d+(?:\.\d+)*\s*;\s*([^;)]+)"
)

# 被削减后的占位符 / 噪音，抓到这些等于没抓到
_JUNK_MODELS = {"k", "mobile", "linux", "unknown", "android", "tablet", "phone"}

# 型号前缀 → 品牌（只列一眼能定死的前缀，猜不准的宁可不标，免得标错反而误导）
_BRAND_RULES = (
    ("sm-",                       "三星"),
    ("pixel",                     "Google"),
    ("huawei",                    "华为"),
    ("honor",                     "荣耀"),
    ("redmi",                     "红米"),
    ("mi ",                       "小米"),
    ("m2101",                     "小米"),
    ("m2012",                     "小米"),
    ("m2007",                     "小米"),
    ("2201",                      "小米"),
    ("2301",                      "小米"),
    ("2311",                      "小米"),
    ("2312",                      "小米"),
    ("2403",                      "小米"),
    ("cph",                       "OPPO"),
    ("pem",                       "OPPO"),
    ("pgt",                       "OPPO"),
    ("phk",                       "OPPO"),
    ("oneplus",                   "一加"),
    ("kb20",                      "一加"),
    ("rmx",                       "realme"),
    ("rmx3",                      "realme"),
    ("v20",                       "vivo"),
    ("v21",                       "vivo"),
    ("v22",                       "vivo"),
    ("v23",                       "vivo"),
    ("v24",                       "vivo"),
    ("vivo",                      "vivo"),
    ("iqoo",                      "iQOO"),
    ("meizu",                     "魅族"),
    ("mot",                       "摩托罗拉"),
    ("nokia",                     "诺基亚"),
    ("asus",                      "华硕"),
    ("lenovo",                    "联想"),
    ("zte",                       "中兴"),
    ("sony",                      "索尼"),
    ("lg-",                       "LG"),
    ("hmd",                       "诺基亚"),
)
# 华为/荣耀型号形如 ELS-AN00 / MLA-AL10 / ANY-AN00 / BVL-AN16
_RE_HUAWEI_MODEL = re.compile(r"\b([A-Z]{3}-[A-Z]{2}\d{2}[A-Z0-9]*)\b")

# 品牌中文名 → 型号里可能出现的英文写法。
# UA 里常写成 "HUAWEI ELS-AN00"，拼上品牌会变成啰嗦的 "华为 HUAWEI ELS-AN00"，
# 所以加品牌前缀前先把型号里重复的英文品牌词去掉。
_BRAND_EN = {
    "华为": "huawei", "三星": "samsung", "小米": "xiaomi", "红米": "redmi",
    "vivo": "vivo", "iQOO": "iqoo", "OPPO": "oppo", "荣耀": "honor",
    "一加": "oneplus", "魅族": "meizu", "realme": "realme",
    "Google": "pixel", "摩托罗拉": "motorola", "索尼": "sony",
    "华硕": "asus", "联想": "lenovo", "中兴": "zte", "诺基亚": "nokia",
}


def _clean_model(raw: str) -> str:
    """从 Android UA 抓出来的片段里剥出真型号：去掉 Build/xxx、wv 等噪音"""
    s = (raw or "").strip()
    if not s:
        return ""
    # "SM-S918U Build/UP1A.231005.007" → 砍掉 Build 之后
    s = re.split(r"\bBuild\b", s)[0]
    s = re.split(r"\bwv\b", s)[0]
    s = s.strip().strip(";").strip()
    # 有些 UA 写成 "HUAWEI ELS-AN00; HMSCore 6.x"
    s = re.split(r"\bHMSCore\b", s)[0].strip().strip(";").strip()
    if not s or s.lower() in _JUNK_MODELS:
        return ""
    # 型号一般不长，超长的多半是拼错了别的东西
    if len(s) > 40:
        return ""
    return s


def _brand_of(model: str) -> str:
    """型号 → 品牌名（猜不准返回空串，宁缺勿错）"""
    low = model.lower()
    for pre, brand in _BRAND_RULES:
        if low.startswith(pre):
            return brand
    if "huawei" in low:
        return "华为"
    if _RE_HUAWEI_MODEL.search(model):
        return "华为"
    if re.match(r"^\d{4}[A-Z]{2}\d{2}[A-Z0-9]*$", model):      # 2201123C 类
        return "小米"
    if re.match(r"^[VP]\d{4}[A-Z]{1,2}$", model):              # V2318A / PAFM00
        return "vivo" if model.startswith("V") else "OPPO"
    return ""


def ua_model(ua: Optional[str]) -> str:
    """UA → 设备型号："三星 SM-S918U" / "Pixel 7" / "23013RK75C"（带品牌前缀）

    抓不到返回 ""（空串）—— 调用方负责显示成 "-"。
    安卓 16+ / 鸿蒙 / iOS 基本都抓不到，这是浏览器不给，不是解析失败。
    """
    s = (ua or "").strip()
    if not s:
        return ""
    low = s.lower()

    # 非安卓平台：UA 里没有型号字段，别瞎找
    if "android" not in low:
        return ""

    m = _RE_ANDROID_MODEL.search(s)
    if not m:
        return ""
    model = _clean_model(m.group(1))
    return model_pretty(model) if model else ""


def model_pretty(model: Optional[str]) -> str:
    """给**裸型号**加品牌前缀："SM-S918U" → "三星 SM-S918U"

    两条路都走这里：UA 解析出来的型号、客户端 JS 上报的型号（Sec-CH-UA-Model），
    这样不管型号从哪来，表格里显示的样式都一样。
    """
    s = (model or "").strip()
    if not s:
        return ""
    brand = _brand_of(s)
    if not brand:
        return s
    en = _BRAND_EN.get(brand, "")
    if en and s.lower().startswith(en):
        rest = s[len(en):].strip()
        # 砍完不能剩个光秃秃的数字（"Pixel 8" 砍成 "8" 就没意义了）
        if len(rest) >= 3 and re.search(r"[A-Za-z]", rest):
            s = rest
    return "%s %s" % (brand, s)


# ---------------------------------------------------------------- 一行摘要
def ua_brief(ua: Optional[str]) -> str:
    """UA → 一行短摘要："鸿蒙 6.0 · 微信" / "iOS 17.0 · Safari"

    给那些不想开 4 列、只想一眼认人的场景（比如 tooltip）用。
    """
    s = (ua or "").strip()
    if not s:
        return "-"
    os_ = ua_os(s)
    br = ua_browser(s)
    dev = ua_model(s)
    parts = [os_]
    if br and br != "-":
        parts.append(br)
    if dev:
        parts.append(dev)
    return " · ".join(p for p in parts if p)
