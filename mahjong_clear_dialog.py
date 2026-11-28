# -*- coding: utf-8 -*-
"""★ v2.9.37：一键清除数据对话框（今日 / 本月 / 本年 / 指定日·月·年 / 全部）

为什么单独放一个文件：主程序 `Mahjong_Calculator.py` 已经 5400 多行，一个纯 UI
对话框再往里塞 300 行，后面谁都不敢改。这里**只放对话框本身**，
数据层仍然走 `mahjong_stats.StatsDB.plan_clear()` / `clear_data()`（那两个函数
早在 v2.9.26 就写好了，只是从来没接过界面）。

设计约束（跟需求方确认过的）
--------------------------
1. **先预览再删**：每改一下范围就重算一遍
   「将删除 N 条 / M 手 / X 番 / K 个 IP / D 天」。
   一条都删不到时「开始清除」直接变灰 —— 省得点了没反应，还以为程序坏了。
2. **「全部」要手打「删除全部」**：它是唯一会连 `user_nick` 昵称表一起清的
   （记录都没了，名字留着下次同名上报会莫名变成「老张#2」），光点「确定」太容易误触。
3. **任何范围都再过一次二次确认**，并写明将删多少条 —— 删除不可恢复。
4. **进度条**：单条 DELETE 是毫秒级，但大库也可能卡一下。删除期间把进度条切成
   「不确定进度」的循环动画，删完落到 100%。**不假装有百分比**，也不让界面看着死掉。
5. 范围下拉里「指定某一天」用日历（默认停在库里最近有数据的那天），
   「指定某一月」用「年 + 月」两个下拉，「指定某一年」用年份下拉。
   年份只列**库里真有数据的年份**（另加今年兜底），不从一堆空白年份里挑。
"""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)


class StatsClearDialog(QDialog):
    """一键清除数据（先预览、再二次确认、后执行）"""

    # 下拉项文案 / 内部 key（顺序就是下拉顺序）
    SCOPE_ITEMS = (
        ("today", "今天"),
        ("month_now", "本月"),
        ("year_now", "本年"),
        ("day", "指定某一天"),
        ("month", "指定某一月"),
        ("year", "指定某一年"),
        ("all", "全部数据"),
    )
    # 每个 key 对应 QStackedWidget 的页号
    PAGE_OF_SCOPE = {"today": 0, "month_now": 1, "year_now": 2,
                     "day": 3, "month": 4, "year": 5, "all": 6}
    # 真正交给 stats 的 scope（month_now / year_now 会换算成具体年月）
    STATS_SCOPE = {"today": "today", "month_now": "month", "year_now": "year",
                   "day": "day", "month": "month", "year": "year", "all": "all"}

    def __init__(self, parent, stats):
        super().__init__(parent)
        self.stats = stats
        self.setWindowTitle("一键清除数据")
        self.setMinimumSize(760, 620)
        self._plan: dict = {}
        self._done = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QLabel("按范围整批删掉算番记录（先预览，确认条数对得上再删）")
        head.setStyleSheet("font-weight:bold;")
        lay.addWidget(head)

        why = QLabel(
            "这里删的是<b>统计库里的历史成绩</b>（统计页那几张表、看板、"
            "「今日战绩」都读它）。删掉的<b>找不回来</b>，所以每一步都先算给你看。\n"
            "只清数据，不动设置：倒计时、看板配色、显示列这些都在设置文件里，"
            "清完还照旧。")
        why.setWordWrap(True)
        why.setStyleSheet("color:#666;font-size:11px;")
        lay.addWidget(why)

        # ---- 范围选择 + 两个按钮
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(QLabel("清除范围"))
        self.cmb_scope = QComboBox()
        for key, label in self.SCOPE_ITEMS:
            self.cmb_scope.addItem(label, key)
        self.cmb_scope.currentIndexChanged.connect(self._scope_changed)
        bar.addWidget(self.cmb_scope)
        bar.addStretch(1)
        self.btn_preview = QPushButton("重新预览")
        self.btn_preview.setToolTip("按当前范围重新算一遍会删多少（只读，不动库）")
        self.btn_preview.clicked.connect(self._scan)
        bar.addWidget(self.btn_preview)
        self.btn_run = QPushButton("开始清除")
        self.btn_run.setToolTip("按上面的预览结果删除（不可恢复）")
        self.btn_run.clicked.connect(self._run)
        self.btn_run.setEnabled(False)
        bar.addWidget(self.btn_run)
        lay.addLayout(bar)

        # ---- 各范围自己的参数区
        self.stack = QStackedWidget()

        # 0 今天
        self.stack.addWidget(self._make_note_page("lbl_today"))
        # 1 本月
        self.stack.addWidget(self._make_note_page("lbl_month_now"))
        # 2 本年
        self.stack.addWidget(self._make_note_page("lbl_year_now"))

        # 3 指定某一天（日历）
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.setSpacing(4)
        self.cal_day = QCalendarWidget()
        self.cal_day.setGridVisible(True)
        try:
            self.cal_day.setVerticalHeaderFormat(
                QCalendarWidget.NoVerticalHeader)
        except Exception:                  # noqa: BLE001 —— 老版本枚举名不同，不影响用
            pass
        self.cal_day.selectionChanged.connect(self._scan)
        l3.addWidget(self.cal_day, 1)
        self.lbl_day_pick = QLabel()
        self.lbl_day_pick.setStyleSheet("color:#666;font-size:11px;")
        l3.addWidget(self.lbl_day_pick)
        self.stack.addWidget(p3)

        # 4 指定某一月（年 + 月）
        p4 = QWidget()
        l4 = QHBoxLayout(p4)
        l4.setContentsMargins(0, 0, 0, 0)
        l4.setSpacing(6)
        l4.addWidget(QLabel("年"))
        self.cmb_month_year = QComboBox()
        self.cmb_month_year.setMinimumWidth(90)
        self.cmb_month_year.currentIndexChanged.connect(self._scan)
        l4.addWidget(self.cmb_month_year)
        l4.addWidget(QLabel("月"))
        self.cmb_month = QComboBox()
        self.cmb_month.setMinimumWidth(90)
        for m in range(1, 13):
            self.cmb_month.addItem("%d 月" % m, m)
        self.cmb_month.currentIndexChanged.connect(self._scan)
        l4.addWidget(self.cmb_month)
        l4.addStretch(1)
        self.stack.addWidget(p4)

        # 5 指定某一年
        p5 = QWidget()
        l5 = QHBoxLayout(p5)
        l5.setContentsMargins(0, 0, 0, 0)
        l5.setSpacing(6)
        l5.addWidget(QLabel("年份"))
        self.cmb_year = QComboBox()
        self.cmb_year.setMinimumWidth(120)
        self.cmb_year.currentIndexChanged.connect(self._scan)
        l5.addWidget(self.cmb_year)
        l5.addStretch(1)
        self.stack.addWidget(p5)

        # 6 全部
        p6 = QWidget()
        l6 = QVBoxLayout(p6)
        l6.setContentsMargins(0, 0, 0, 0)
        l6.setSpacing(4)
        warn = QLabel(
            "全部数据 = <b>整张成绩表清空</b>，并且连「谁是谁」的昵称表一起清掉。\n"
            "这一步做完，统计页 / 看板 / 网页版会一起变成空的，没有任何撤销办法。\n"
            "确认无误就点下面的「开始清除」，届时还要再手打一遍「删除全部」。")
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#B00020;font-size:11px;")
        l6.addWidget(warn)
        l6.addStretch(1)
        self.stack.addWidget(p6)

        lay.addWidget(self.stack)

        # ---- 预览结论
        self.lbl_sum = QLabel()
        self.lbl_sum.setStyleSheet("font-weight:bold;padding:4px 0;")
        self.lbl_sum.setWordWrap(True)
        lay.addWidget(self.lbl_sum)

        self.pb = QProgressBar()
        self.pb.setRange(0, 100)
        self.pb.setValue(0)
        self.pb.setTextVisible(True)
        lay.addWidget(self.pb)

        tip = QLabel(
            "「今天 / 本月 / 本年」按本机时间算；指定日·月·年只认库里确实有记录的。\n"
            "清完不会动设置文件，也不影响当前这手牌的计算。")
        tip.setStyleSheet("color:#666;font-size:11px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Close).setText("关闭")
        box.rejected.connect(self.reject)
        lay.addWidget(box)

        self._load_choices()
        self._scan()

    # ------------------------------------------------------------------ 构建
    def _make_note_page(self, attr: str) -> QWidget:
        """「今天 / 本月 / 本年」这种不需要选参数的页：一行说明文字"""
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel()
        setattr(self, attr, lbl)
        h.addWidget(lbl)
        h.addStretch(1)
        return page

    def _load_choices(self) -> None:
        """把年份 / 月份下拉、日历初始日期按库里实际数据填好"""
        years = []
        months = []
        days = []
        if self.stats is not None:
            try:
                years = [str(y) for y in (self.stats.list_years() or [])]
            except Exception:              # noqa: BLE001 —— 读不到就当没有，不拦着用户用别的范围
                years = []
            try:
                months = [str(m) for m in (self.stats.list_months() or [])]
            except Exception:              # noqa: BLE001
                months = []
            try:
                days = [str(d) for d in (self.stats.list_days() or [])]
            except Exception:              # noqa: BLE001
                days = []

        # 年份：库里有数据的 + 今年兜底（去重后倒序）
        cur_y = QDate.currentDate().year()
        yset = set(years)
        yset.add(str(cur_y))
        year_list = sorted(yset, key=lambda s: (-int(s) if s.isdigit() else 0,
                                                s))
        for cmb in (self.cmb_month_year, self.cmb_year):
            cmb.blockSignals(True)
            cmb.clear()
            for y in year_list:
                cmb.addItem(y, y)
            cmb.blockSignals(False)

        # 某年默认选「库里最近的那个月」，月份下拉停在它上面
        if months:
            try:
                latest = months[0]                     # 'YYYY-MM'
                ly, lm = latest.split("-")[0], int(latest.split("-")[1])
                i = self.cmb_month_year.findData(ly)
                if i >= 0:
                    self.cmb_month_year.blockSignals(True)
                    self.cmb_month_year.setCurrentIndex(i)
                    self.cmb_month_year.blockSignals(False)
                self.cmb_month.blockSignals(True)
                self.cmb_month.setCurrentIndex(max(0, min(11, lm - 1)))
                self.cmb_month.blockSignals(False)
            except Exception:              # noqa: BLE001 —— 格式怪就当没设置，用默认值
                pass

        # 日历默认停在库里最近有数据的那天（没有数据就停今天）
        d = QDate.currentDate()
        for s in days:
            try:
                qd = QDate.fromString(s, "yyyy-MM-dd")
                if qd.isValid():
                    d = qd
                    break
            except Exception:              # noqa: BLE001
                continue
        self.cal_day.blockSignals(True)
        self.cal_day.setSelectedDate(d)
        self.cal_day.blockSignals(False)
        self.lbl_day_pick.setText("日历里能选任意一天；选了库里没有的日子，预览会是 0 条。")

    # ------------------------------------------------------------------ 参数取值
    def _scope_key(self) -> str:
        return str(self.cmb_scope.currentData() or "today")

    def _params(self) -> tuple:
        """按当前范围算出 (stats_scope, day, month, year)"""
        key = self._scope_key()
        scope = self.STATS_SCOPE.get(key, "today")
        today = QDate.currentDate()
        day = today.toString("yyyy-MM-dd")
        month = today.toString("yyyy-MM")
        year = today.toString("yyyy")
        try:
            if key == "day":
                day = self.cal_day.selectedDate().toString("yyyy-MM-dd")
            elif key == "month":
                y = str(self.cmb_month_year.currentData() or year)
                m = int(self.cmb_month.currentData() or 1)
                month = "%s-%02d" % (y, m)
            elif key == "year":
                year = str(self.cmb_year.currentData() or year)
        except Exception:                  # noqa: BLE001 —— 取不到就用今天，别把对话框搞崩
            pass
        return scope, day, month, year

    def _describe(self, scope: str, day: str, month: str, year: str) -> str:
        if scope == "today":
            return "今天（%s）" % day
        if scope == "day":
            return "%s 这一天" % day
        if scope == "month":
            return "%s 这个月" % month
        if scope == "year":
            return "%s 这一年" % year
        return "全部数据"

    # ------------------------------------------------------------------ 预览
    def _scope_changed(self, _idx: int = 0) -> None:
        self.stack.setCurrentIndex(
            self.PAGE_OF_SCOPE.get(self._scope_key(), 0))
        self._scan()

    def _scan(self) -> None:
        """重算预览（只读，不动库）"""
        key = self._scope_key()
        scope, day, month, year = self._params()
        today = QDate.currentDate().toString("yyyy-MM-dd")
        self.lbl_today.setText("今天就是 %s（本机日期）" % today)
        self.lbl_month_now.setText("本月就是 %s（本机日期）" % today[:7])
        self.lbl_year_now.setText("本年就是 %s（本机日期）" % today[:4])

        if self.stats is None:
            self.lbl_sum.setText("统计库没打开，没法清理。")
            self.btn_run.setEnabled(False)
            return
        try:
            plan = self.stats.plan_clear(scope, day=day, month=month,
                                         year=year)
        except Exception:                  # noqa: BLE001
            plan = {"ok": False}
        self._plan = dict(plan or {})
        self.pb.setValue(0)

        if not self._plan.get("ok"):
            self.lbl_sum.setText("预览失败：统计库读取异常，先看看程序日志（stderr）。")
            self.btn_run.setEnabled(False)
            return

        hands = int(self._plan.get("hands") or 0)
        fan = int(self._plan.get("fan") or 0)
        users = int(self._plan.get("users") or 0)
        days = int(self._plan.get("days") or 0)
        what = self._describe(scope, day, month, year)
        if hands <= 0:
            self.lbl_sum.setText(
                "%s：库里一条记录都没有 —— 不用清。" % what)
            self.btn_run.setEnabled(False)
            return
        self.lbl_sum.setText(
            "将删除 <span style='color:#B00020'>%d</span> 条记录（%d 手）·"
            " 合计 %d 番 · %d 个 IP · 覆盖 %d 天　范围：%s"
            % (hands, hands, fan, users, days, what))
        self.btn_run.setEnabled(True)
        if key == "all":
            self.btn_run.setText("开始清除（需输入确认词）")
        else:
            self.btn_run.setText("开始清除")

    # ------------------------------------------------------------------ 执行
    def _run(self) -> None:
        scope, day, month, year = self._params()
        hands = int(self._plan.get("hands") or 0)
        if hands <= 0 or self.stats is None:
            return
        what = self._describe(scope, day, month, year)

        # ---- 二次确认（「全部」还要手打确认词）
        if scope == "all":
            from PySide6.QtWidgets import QInputDialog
            txt, ok = QInputDialog.getText(
                self, "确认清空全部数据",
                "这一步会清空成绩表、连昵称一起清，没有撤销办法。\n"
                "确实要做，请在下面输入「删除全部」四个字：",
                text="")
            if not ok:
                return
            if str(txt or "").strip() != "删除全部":
                QMessageBox.information(
                    self, "没删", "输入的不是「删除全部」，已取消，什么都没动。")
                return
        ans = QMessageBox.question(
            self, "确认清除",
            "将删除 %d 条记录（%s）。\n\n"
            "统计页、看板、网页版都会立刻跟着变；删掉的找不回来。\n"
            "确定要删吗？" % (hands, what),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return

        self.btn_run.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.cmb_scope.setEnabled(False)
        self.pb.setRange(0, 0)                 # 不确定进度：不假装知道百分比
        self.pb.setFormat("正在清除…")
        QApplication.processEvents()
        n = 0
        try:
            n = int(self.stats.clear_data(scope, day=day, month=month,
                                          year=year) or 0)
        except Exception:                      # noqa: BLE001 —— 清理失败不能把窗口搞崩
            import traceback
            traceback.print_exc()
        self.pb.setRange(0, 100)
        self.pb.setValue(100)
        self.pb.setFormat("%p%")
        self._done = True
        self.btn_preview.setEnabled(True)
        self.cmb_scope.setEnabled(True)
        QMessageBox.information(
            self, "清除完成",
            "已删除 %d 条记录（%s）。" % (n, what))
        self._scan()                           # 重算一次，通常变成「一条都没有，不用清」

    def changed(self) -> bool:
        """调用方据此决定要不要刷新统计页"""
        return bool(self._done)
