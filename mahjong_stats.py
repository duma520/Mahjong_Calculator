# -*- coding: utf-8 -*-
"""算番统计模块（v2.9.6 / v2.9.12 增设备信息与昵称）

职责：
  · 每次算番结果落库（SQLite，WAL 模式，线程安全）
  · 用户唯一性：IP+UUID 为主（UUID 是客户端 localStorage 里的设备标识），
    IP+UA 兜底（拿不到 UUID 时）；目标就是「不串号」
  · 时间戳精确到毫秒；按「天」聚合（每天一个统计单位）
  · 桌面端（本地 PySide6）算番也计入，client_type='desktop'

★ v2.9.12 增的四列：os（系统）/ browser（浏览器）/ dev（设备型号）/ nick（昵称）
  · os / browser / dev 里的前两个**实时解析** UA，不落库 —— UA 本来就存着，
    再存一份是浪费空间，而且 UA 规则以后改了历史数据也能跟着变
  · dev 优先用 score_log.model（客户端 JS 上报的型号，比 UA 解析准），
    没有再退回 UA 解析；都拿不到就是空串（安卓 16+ / 鸿蒙 / iOS 属正常现象）
  · nick 必须落库：这是用户自己填的，UA 里没有，只能存下来

设计要点（防御性编程 / 容错 / 不阻断主流程）：
  · 落库失败只写日志、返回 False，绝不抛异常影响算番
  · 同一手牌（相同 sig）2 秒内重复请求会去重，避免选项反复切换刷出大量脏数据
  · 每个 StatsDB 实例独占一个 sqlite 连接，配锁保证多线程写入安全
  · 老库升级：缺的列自动 ALTER 补上（fans / model / nick），历史数据不丢
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

# UA 解析（v2.9.12）。同目录文件，正常情况下必定存在；
# 万一被单独拷走导致缺失，这里降级成返回 "-"/""，不让统计功能整体瘫掉。
try:
    from mahjong_ua import ua_os, ua_browser, ua_model, model_pretty
except Exception:                                          # noqa: BLE001
    def ua_os(_ua) -> str:
        return "-"

    def ua_browser(_ua) -> str:
        return "-"

    def ua_model(_ua) -> str:
        return ""

    def model_pretty(m) -> str:
        return str(m or "")

SCHEMA_VERSION = 3
# 同一手牌去重窗口（毫秒）：2 秒内相同 sig 视为重复，跳过
DEDUP_WINDOW_MS = 2000
# ★ v2.9.9：score_log.fans 列里多个番种名的分隔符
FANS_SEP = "|"


def _day_local(ts_ms: int) -> str:
    """epoch 毫秒 → 本地日期 YYYY-MM-DD（按天统计的 key）"""
    return time.strftime("%Y-%m-%d", time.localtime(ts_ms / 1000.0))


# ---------------------------------------------------------------- 番种文本
# ★ v2.9.9：明细要能看到「这一手牌算了哪些番种」，所以要把番种名落库。
#   两端（桌面 / Web）算番结果的番种结构不一样，统一在这里兜住，调用方不用关心。

def fans_text(fans) -> str:
    """算番结果的番种列表 → "无番和|缺一门|碰碰和"（存进 score_log.fans）

    三种输入都吃：
      · [("无番和", 1), ...]          ← 桌面端 `ScoreResult.fans`（(名字, 番数) 元组）
      · [{"name":"无番和","fan":1}]   ← Web 端 `/api/score` 的 JSON
      · ["无番和", ...]               ← 只有名字
    拿不到就返回空串（老记录就是空串，明细里显示「-」）。
    """
    names: List[str] = []
    if isinstance(fans, (list, tuple)):
        for it in fans:
            if isinstance(it, (list, tuple)):
                n = str(it[0]) if it else ""
            elif isinstance(it, dict):
                n = str(it.get("name") or it.get("fan_name") or "")
            else:
                n = str(it)
            n = n.strip()
            if n:
                names.append(n)
    return FANS_SEP.join(names)


def fans_split(text: str) -> List[str]:
    """"a|b" → ["a","b"]（空串 → []）"""
    if not text:
        return []
    return [s.strip() for s in str(text).split(FANS_SEP) if s.strip()]


def fans_count(texts) -> List[Tuple[str, int]]:
    """多条 fans 文本合并计数 → [(番种名, 次数)]，按次数降序、同次数按名字"""
    d: Dict[str, int] = {}
    for t in (texts or ()):
        for n in fans_split(t):
            d[n] = d.get(n, 0) + 1
    return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))


def fans_brief(texts, top: int = 6, sep: str = "、") -> str:
    """「无番和×3、碰碰和×1、等 9 种」——统计表格一格放得下的短串

    超出 top 种就只列前几种 + 「等 N 种」，完整清单在明细窗口 / tooltip 里看。
    """
    items = fans_count(texts)
    if not items:
        return ""
    parts = ["%s×%d" % (n, c) for n, c in items[:top]]
    if len(items) > top:
        parts.append("等 %d 种" % len(items))
    return sep.join(parts)


def user_key_from(uuid: Optional[str], ip: str, ua: str) -> str:
    """用户唯一键：**IP+UUID 为主，IP+UA 兜底**（目标：确定唯一性、不串号）

    规则：
      · 有 UUID  → 'u:<uuid>'
        UUID 由客户端首次访问时生成并写入 localStorage（桌面端固定 'desktop'），
        是设备级标识，不随网络 / IP 变化，所以能把「同一个人」永远聚到同一条，
        也绝不会把不同用户混在一起。
      · 无 UUID  → 'h:<sha1(IP|UA) 前 16 位>'
        老客户端 / 取不到 localStorage 时用 IP + UA 组合兜底，至少区分不同设备。
      · IP、UA 原始值同时写进库表，人工核对时可看。

    ★ 为什么有 UUID 时不再把 IP 拼进 key：
      手机 WiFi ↔ 流量切换会导致同一个用户被拆成两条记录，按天统计会看到「两个人」，
      那才是真正的「串」。所以 UUID 存在时以 UUID 为准，IP/UA 只作兜底与留档。
    """
    _uuid = (uuid or "").strip()
    _ip = (ip or "").strip()
    _ua = (ua or "").strip()
    if _uuid:
        return "u:" + _uuid
    raw = "%s|%s" % (_ip or "?", _ua or "?")
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return "h:" + h


def hand_sig(*parts: object) -> str:
    """根据手牌相关字段生成去重签名（调用方负责拼装内容）"""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class StatsDB:
    """算番统计库（SQLite / WAL）"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._dup_lock = threading.Lock()
        self._dup: Dict[str, int] = {}          # sig -> 上次写入的 ts_ms
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError:
                pass
        self._conn = sqlite3.connect(path, check_same_thread=False)
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.Error:
            pass
        # ★ 可选列是否可用的缓存（None=还没探过）。
        #   老库（v2.9.6 建的）只有基础列，fans / model / nick 都是后来 ALTER 上去的，
        #   每次都 PRAGMA 太浪费，探一次就记住。
        self._cols: Dict[str, Optional[bool]] = {}
        self._init_schema()

    # ---- 建表
    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS score_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ms       INTEGER NOT NULL,
                    day         TEXT    NOT NULL,
                    user_key    TEXT    NOT NULL,
                    uuid        TEXT    NOT NULL DEFAULT '',
                    client_type TEXT    NOT NULL DEFAULT 'web',
                    ip          TEXT    NOT NULL DEFAULT '',
                    ua          TEXT    NOT NULL DEFAULT '',
                    total_fan   INTEGER NOT NULL,
                    base        INTEGER NOT NULL DEFAULT 0,
                    reach       INTEGER NOT NULL DEFAULT 0,
                    fans_n      INTEGER NOT NULL DEFAULT 0,
                    fans        TEXT    NOT NULL DEFAULT ''
                )"""
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_score_log_day_user "
                "ON score_log(day, user_key)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_score_log_ts "
                "ON score_log(ts_ms)"
            )
            # ★ v2.9.12：昵称表。nick 做主键 —— 「一个名字只属于一个人」，
            #   重名靠这张表拦，规则见 set_nick()。
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS user_nick (
                    nick     TEXT PRIMARY KEY,
                    user_key TEXT NOT NULL DEFAULT '',
                    ip       TEXT NOT NULL DEFAULT '',
                    ts_ms    INTEGER NOT NULL DEFAULT 0
                )"""
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_nick_key "
                "ON user_nick(user_key)"
            )
            self._conn.commit()
        # 老库（v2.9.6~2.9.11 建的）缺的列 —— 补上，历史数据不丢
        self._ensure_column("fans", "TEXT NOT NULL DEFAULT ''")     # v2.9.9
        self._ensure_column("model", "TEXT NOT NULL DEFAULT ''")    # v2.9.12
        self._ensure_column("nick", "TEXT NOT NULL DEFAULT ''")     # v2.9.12

    def _ensure_column(self, name: str, decl: str) -> bool:
        """老库升级：缺的列自动 ALTER 补上（成功 True / 本来就有 True / 失败 False）"""
        try:
            with self._lock:
                have = {r[1] for r in
                        self._conn.execute("PRAGMA table_info(score_log)")}
                if name in have:
                    self._cols[name] = True
                    return True
                self._conn.execute(
                    "ALTER TABLE score_log ADD COLUMN %s %s" % (name, decl))
                self._conn.commit()
            self._cols[name] = True
            return True
        except Exception as exc:       # noqa: BLE001
            try:
                sys.stderr.write("[stats] 补列 %s 失败：%r\n" % (name, exc))
            except Exception:          # noqa: BLE001
                pass
            self._cols[name] = False
            return False

    def has_col(self, name: str) -> bool:
        """score_log 里某个可选列能不能用（探过一次就缓存）"""
        v = self._cols.get(name)
        if v is None:
            try:
                with self._lock:
                    have = {r[1] for r in
                            self._conn.execute("PRAGMA table_info(score_log)")}
                v = name in have
            except Exception:          # noqa: BLE001
                v = False
            self._cols[name] = v
        return bool(v)

    def has_fans_col(self) -> bool:
        """fans 列能不能用（老库补列失败时降级：明细里番种显示「-」，其余照旧）"""
        return self.has_col("fans")

    # ---- 写入（落库失败绝不阻断算番）
    def record(self, *, ts_ms: int, user_key: str, uuid: str = "",
               client_type: str = "web", ip: str = "", ua: str = "",
               total_fan: int = 0, base: int = 0, reach: int = 0,
               fans_n: int = 0, sig: str = "", fans: str = "",
               model: str = "", nick: str = "") -> bool:
        # 去重：同一手牌短时间内重复只记一次
        if sig:
            with self._dup_lock:
                last = self._dup.get(sig)
                if last is not None and (ts_ms - last) < DEDUP_WINDOW_MS:
                    return False
                self._dup[sig] = ts_ms
                # 简单清理过期项，避免无限增长
                if len(self._dup) > 1000:
                    cutoff = ts_ms - 60000
                    self._dup = {k: v for k, v in self._dup.items() if v >= cutoff}
        # ★ 可选列（fans / model / nick）**动态拼**：老库缺哪列就自动不带哪列。
        #   以前是「有 fans / 没 fans」两套 SQL，再加两列就是 8 套，拼着写才不失控。
        cols = ["ts_ms", "day", "user_key", "uuid", "client_type", "ip", "ua",
                "total_fan", "base", "reach", "fans_n"]
        vals: List = [int(ts_ms), _day_local(ts_ms), user_key, uuid or "",
                      client_type or "web", ip or "", ua or "",
                      int(total_fan), int(base), int(reach), int(fans_n)]
        for nm, v in (("fans", str(fans or "")),
                      ("model", str(model or "")),
                      ("nick", str(nick or ""))):
            if self.has_col(nm):
                cols.append(nm)
                vals.append(v)
        sql = "INSERT INTO score_log (%s) VALUES (%s)" % (
            ",".join(cols), ",".join("?" * len(vals)))
        args = tuple(vals)
        try:
            with self._lock:
                self._conn.execute(sql, args)
                self._conn.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            try:
                sys.stderr.write("[stats] 记录失败：%r\n" % (exc,))
            except Exception:
                pass
            return False

    # ---- ★ v2.9.12：昵称（用户自己报的设备名，UA 里没有，只能落库）
    def set_nick(self, user_key: str, ip: str, raw: str) -> str:
        """上报昵称 → 返回**实际生效**的名字（可能带 #2 / #3 后缀）

        重名规则（用户定的）：
          1. 没人用这个名字   → 直接占用
          2. 同名且 IP 相同   → **过户**（视为同一台设备，只是 UUID 变了）
          3. 同名但 IP 不同   → 自动降级成 `老张#2`、`老张#3`… 直到不撞

        同一个 user_key 改名时会先清掉他占过的旧名字，避免一个人占好几个坑。
        空串 / 纯空白 = 「不设昵称」，直接返回 ""。
        """
        name = (raw or "").strip()
        if not name:
            # ★ 清空昵称 = 退掉自己占的坑（不然表里还留着旧名，统计里照样显示）
            try:
                with self._lock:
                    self._conn.execute(
                        "DELETE FROM user_nick WHERE user_key = ?", (user_key or "",))
                    self._conn.commit()
            except Exception as exc:  # noqa: BLE001
                try:
                    sys.stderr.write("[stats] 清空昵称失败：%r\n" % (exc,))
                except Exception:     # noqa: BLE001
                    pass
            return ""
        if len(name) > 24:            # 表格一格放得下的长度
            name = name[:24]
        uk = user_key or ""
        _ip = ip or ""
        try:
            with self._lock:
                # 先退掉这个人之前占的名字（改名不留坑）
                self._conn.execute(
                    "DELETE FROM user_nick WHERE user_key = ?", (uk,))
                # 从 base 开始试，撞了就加后缀；最多试 100 次防死循环
                base = name
                for n in range(1, 101):
                    cand = base if n == 1 else "%s#%d" % (base, n)
                    row = self._conn.execute(
                        "SELECT user_key, ip FROM user_nick WHERE nick = ?",
                        (cand,)).fetchone()
                    if row is None:
                        self._conn.execute(
                            "INSERT INTO user_nick (nick, user_key, ip, ts_ms) "
                            "VALUES (?,?,?,?)",
                            (cand, uk, _ip, int(time.time() * 1000)))
                        self._conn.commit()
                        return cand
                    owner_uk, owner_ip = row
                    # 自己占着 → 续期
                    if owner_uk == uk:
                        self._conn.execute(
                            "UPDATE user_nick SET ip=?, ts_ms=? WHERE nick=?",
                            (_ip, int(time.time() * 1000), cand))
                        self._conn.commit()
                        return cand
                    # 同 IP → 过户（同一台设备，UUID 变了而已）
                    if _ip and (owner_ip or "") == _ip:
                        self._conn.execute(
                            "UPDATE user_nick SET user_key=?, ts_ms=? WHERE nick=?",
                            (uk, int(time.time() * 1000), cand))
                        self._conn.commit()
                        return cand
                    # 不同 IP 且是别人 → 撞了，试下一个后缀
                self._conn.commit()
                return base
        except Exception as exc:      # noqa: BLE001
            try:
                sys.stderr.write("[stats] 设置昵称失败：%r\n" % (exc,))
            except Exception:         # noqa: BLE001
                pass
            return name

    def nick_map(self) -> Dict[str, str]:
        """{user_key: 昵称} —— 给聚合/明细结果补「昵称」列用"""
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT user_key, nick FROM user_nick").fetchall()
            return {k: (n or "") for k, n in rows if k}
        except Exception as exc:      # noqa: BLE001
            try:
                sys.stderr.write("[stats] 读取昵称失败：%r\n" % (exc,))
            except Exception:         # noqa: BLE001
                pass
            return {}

    # ---- 查询（聚合：按用户×天）
    def aggregate(self, day: Optional[str] = None,
                  limit: int = 500) -> List[Dict]:
        """按 user_key 聚合，返回每人的合计番数 / 次数 / 达标数 / 首末时间 / 最近 IP·UA。

        day=None 表示统计全部日期（按 user_key 跨天合计）。
        返回的 ip / ua 是该用户**最近一次**算番时的值（见 _fill_last_device）。
        """
        sql = (
            "SELECT user_key, uuid, client_type, "
            "SUM(total_fan) AS total_fan, COUNT(*) AS cnt, "
            "SUM(reach) AS reach_cnt, MIN(ts_ms) AS first_ts, "
            "MAX(ts_ms) AS last_ts "
            "FROM score_log"
        )
        params: List = []
        if day:
            sql += " WHERE day = ?"
            params.append(day)
        sql += " GROUP BY user_key ORDER BY total_fan DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        cols = ["user_key", "uuid", "client_type", "total_fan", "cnt",
                "reach_cnt", "first_ts", "last_ts"]
        rows = [dict(zip(cols, r)) for r in rows]
        self._fill_last_device(rows, day)
        self._fill_fans(rows, day)
        self._fill_device_info(rows)
        return rows

    def _fill_device_info(self, rows: List[Dict]) -> None:
        """★ v2.9.12：给每行补上 os / browser / dev / nick 四个**展示用**字段

        为什么不落库：os / browser / dev 都能从已存的 ua 现算出来，
        再存三列纯属浪费；而且 UA 解析规则以后改了，历史数据也能跟着变。
        dev 的取值优先级：JS 上报的 model（准确） → UA 解析（碰运气） → ""。
        """
        nicks = self.nick_map()
        for r in rows:
            ua = r.get("ua") or ""
            r["os"] = ua_os(ua)
            r["browser"] = ua_browser(ua)
            # 上报型号也过一遍 model_pretty：跟 UA 解析出来的显示样式保持一致
            _m = (r.get("model") or "").strip()
            r["dev"] = model_pretty(_m) if _m else ua_model(ua)
            # 明细行里有「当时记录的昵称」就用它（改名后历史不该跟着变）；
            # 聚合行没有这一列，退回查当前的昵称表。
            r["nick"] = r.get("nick") or nicks.get(r.get("user_key") or "", "")

    def _fill_fans(self, rows: List[Dict], day: Optional[str]) -> None:
        """★ v2.9.9：给每人补上「番种×次数」短串（统计表「番种」列用）

        为什么不在 SQL 里做：SQLite 没有「按分隔符拆字符串再分组计数」的能力，
        而一天的记录量最多几百手，取出来在 Python 里数最省事也最不容易写错。
        """
        for r in rows:
            r.setdefault("fans", "")
        if not rows or not self.has_fans_col():
            return
        sql = "SELECT user_key, fans FROM score_log"
        params: List = []
        if day:
            sql += " WHERE day = ?"
            params.append(day)
        try:
            with self._lock:
                got = self._conn.execute(sql, params).fetchall()
        except Exception as exc:       # noqa: BLE001
            try:
                sys.stderr.write("[stats] 读取番种失败：%r\n" % (exc,))
            except Exception:          # noqa: BLE001
                pass
            return
        bag: Dict[str, List[str]] = {}
        for uk, ft in got:
            bag.setdefault(uk, []).append(ft or "")
        for r in rows:
            r["fans"] = fans_brief(bag.get(r["user_key"], []))

    def _fill_last_device(self, rows: List[Dict], day: Optional[str]) -> None:
        """给每条聚合结果补上「最近一次」的 IP / UA。

        不能直接在 GROUP BY 里 SELECT ip,ua —— SQLite 取的是**任意一行**，
        同一 UUID 换过网络就可能显示旧 IP，人工核对「有没有串号」会被误导。
        这里显式取 ts_ms 最大的那一条。
        """
        if not rows:
            return
        keys = [r["user_key"] for r in rows]
        ph = ",".join("?" * len(keys))
        # ★ v2.9.12：顺带把最近一次的 model（JS 上报的型号）也取回来
        has_model = self.has_col("model")
        sel = "SELECT s.user_key, s.ip, s.ua" + (", s.model" if has_model else "")
        sql = (sel + " FROM score_log s "
               "WHERE s.ts_ms = (SELECT MAX(x.ts_ms) FROM score_log x "
               "WHERE x.user_key = s.user_key")
        params: List = []
        if day:
            sql += " AND x.day = ?"
            params.append(day)
        sql += ") AND s.user_key IN (%s)" % ph
        params.extend(keys)
        latest: Dict[str, Tuple[str, str, str]] = {}
        try:
            with self._lock:
                for row in self._conn.execute(sql, params):
                    k, ip, ua = row[0], row[1], row[2]
                    model = row[3] if (has_model and len(row) > 3) else ""
                    latest[k] = (ip or "", ua or "", model or "")
        except Exception as exc:       # noqa: BLE001
            try:
                sys.stderr.write("[stats] 读取最近设备信息失败：%r\n" % (exc,))
            except Exception:
                pass
        for r in rows:
            r["ip"], r["ua"], r["model"] = latest.get(
                r["user_key"], ("", "", ""))

    def list_days(self) -> List[str]:
        """去重日期列表（倒序），供日期选择器使用"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT day FROM score_log ORDER BY day DESC"
            ).fetchall()
        return [r[0] for r in rows]

    def total_summary(self, day: Optional[str] = None) -> Dict:
        """整体汇总：手数 / 总番数 / 用户数 / ★ v2.9.9 番种榜"""
        sql = ("SELECT COUNT(*) AS hands, COALESCE(SUM(total_fan),0) AS fan, "
               "COUNT(DISTINCT user_key) AS users FROM score_log")
        params: List = []
        if day:
            sql += " WHERE day = ?"
            params.append(day)
        with self._lock:
            r = self._conn.execute(sql, params).fetchone()
        out = {"hands": r[0] or 0, "fan": r[1] or 0, "users": r[2] or 0}
        top = self.fans_top(day)
        out["fans"] = [{"name": n, "cnt": c} for n, c in top]
        out["fans_txt"] = fans_brief([t for t in self._fans_texts(day)])
        return out

    def _fans_texts(self, day: Optional[str],
                    user_key: Optional[str] = None) -> List[str]:
        """取一批 fans 文本（给 fans_count / fans_brief 用）"""
        if not self.has_fans_col():
            return []
        sql = "SELECT fans FROM score_log"
        params: List = []
        cond = []
        if day:
            cond.append("day = ?")
            params.append(day)
        if user_key:
            cond.append("user_key = ?")
            params.append(user_key)
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        try:
            with self._lock:
                return [(r[0] or "") for r in self._conn.execute(sql, params)]
        except Exception as exc:       # noqa: BLE001
            try:
                sys.stderr.write("[stats] 读取番种榜失败：%r\n" % (exc,))
            except Exception:          # noqa: BLE001
                pass
            return []

    def fans_top(self, day: Optional[str] = None,
                 user_key: Optional[str] = None,
                 top: int = 50) -> List[Tuple[str, int]]:
        """★ v2.9.9 番种榜：[(番种名, 次数)] 按次数降序（day=None 表示全部日期）"""
        return fans_count(self._fans_texts(day, user_key))[:int(top)]

    # ---- ★ v2.9.9：逐手牌明细
    def detail_rows(self, user_key: str, day: Optional[str] = None,
                    limit: int = 1000) -> List[Dict]:
        """某个用户的**逐手牌明细**（时间倒序）

        返回的每行：id / ts_ms / day / client_type / ip / ua /
        total_fan / base / reach / fans_n / fans（番种名，老记录为空串）。
        fans 列不可用时那一项恒为空串，其余字段照常。
        """
        cols = ["id", "ts_ms", "day", "client_type", "ip", "ua",
                "total_fan", "base", "reach", "fans_n"]
        sel = ("id, ts_ms, day, client_type, ip, ua, total_fan, base, "
               "reach, fans_n")
        # 可选列动态拼（老库缺哪列就不带哪列）
        for nm in ("fans", "model", "nick"):
            if self.has_col(nm):
                cols.append(nm)
                sel += ", " + nm
        sql = "SELECT %s FROM score_log WHERE user_key = ?" % sel
        params: List = [user_key]
        if day:
            sql += " AND day = ?"
            params.append(day)
        sql += " ORDER BY ts_ms DESC, id DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            got = self._conn.execute(sql, params).fetchall()
        rows = [dict(zip(cols, r)) for r in got]
        for nm in ("fans", "model", "nick"):
            if nm not in cols:
                for r in rows:
                    r[nm] = ""
        # ★ 明细是按 user_key 查的，但 SELECT 里没取这一列 —— 补回去，
        #   否则 _fill_device_info 查昵称时 key 是 None，名字永远显示不出来。
        for r in rows:
            r["user_key"] = user_key
        self._fill_device_info(rows)
        return rows

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass
