# -*- coding: utf-8 -*-
"""国标麻将算番器 —— 主程序（唯一编译源）

数据源：同目录《国标麻将标准规则.json》（中国麻将竞赛规则(试行)1998 + 杜维忠《问答》2006 整理）

设置持久化约定（实时自动保存）：
    - 设置存同目录 `mahjong_settings.json`（打包后为 exe 同目录），原子写入（tmp + os.replace）。
    - 控件变更信号 → autosave()（500ms 防抖）→ _save_settings_now() 立即写盘。
    - 退出 closeEvent 强制保存；启动 _load_settings() 恢复。
    - 新增设置项必须三处成对实现：_collect_settings() 收集 + _apply_settings() 应用
      （用 blockSignals 防止加载时触发保存）+ _connect_autosave() 接信号。
"""
import json
import os
import sys
from collections import defaultdict  # 添加这行导入

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QCheckBox, QSpinBox, QScrollArea,
                             QAction, QMessageBox)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QSize, QTimer

__version__ = "1.1.0"
APP_NAME = "国标麻将算番器"
SETTINGS_FILE = "mahjong_settings.json"
RULES_FILE = "国标麻将标准规则.json"

# 特殊番种复选框（注意：国标 81 番种中并无『天和/地和/人和』，见规则文件
# 番种体系.未采用番种；此处保留是为了兼容旧界面，勾选后按 8 分计入）
SPECIAL_FANS = ["自摸", "和绝张", "抢杠和", "海底捞月", "天和", "地和"]
WIND_NAMES = ["东", "南", "西", "北"]
FLOWER_NAMES = ["春", "夏", "秋", "冬", "梅", "兰", "竹", "菊"]

HERE = os.path.dirname(os.path.abspath(__file__))


def app_dir() -> str:
    """程序目录：打包后取 exe 所在目录，源码运行时取脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return HERE


def resource_path(name: str) -> str:
    """定位随程序分发的资源（tiles/、数据表等）。"""
    return os.path.join(app_dir(), name)


def settings_path() -> str:
    return os.path.join(app_dir(), SETTINGS_FILE)


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
    except Exception:
        return {}


def save_settings(data: dict) -> bool:
    try:
        _atomic_write_json(settings_path(), data)
        return True
    except Exception as exc:  # noqa: BLE001
        print("保存设置失败: %r" % (exc,))
        return False


# mahjong_core 的核心计算模块（源码已丢失，仅剩 __pycache__ 中的 .pyc）。
# 这里做容错导入：拿不到时给出明确提示，而不是直接崩掉。
try:
    from mahjong_core import MahjongFanCalculator
    CORE_IMPORT_ERROR = None
except Exception as _exc:  # noqa: BLE001
    MahjongFanCalculator = None
    CORE_IMPORT_ERROR = repr(_exc)

class TileButton(QPushButton):
    """麻将牌按钮"""
    def __init__(self, tile_type: str, parent=None):
        super().__init__(parent)
        self.tile_type = tile_type
        self.setFixedSize(44, 60)
        self.setIconSize(QSize(44, 60))
        self.setStyleSheet("QPushButton { border: none; }")

        # 加载图片（用 resource_path，保证打包成 exe 后也能找到 tiles/）
        self.image_path = resource_path(os.path.join("tiles", f"{tile_type}.png"))
        if os.path.exists(self.image_path):
            self.setIcon(QIcon(self.image_path))
        else:
            # 如果图片不存在，使用空图标
            self.setIcon(QIcon())

        self.count = 0
        # 全部牌种每人最多 4 张（原代码里的 'S1'~'S4'、'P1'~'P4' 在本项目中并不存在，属死代码）
        self.max_count = 4
        self.clicked.connect(self.on_click)

    def on_click(self):
        if self.count < self.max_count:
            self.count += 1
        else:
            self.count = 0
        self.update_display()

    def update_display(self):
        if self.count == 0:
            # 使用空图标而不是不存在的empty.png
            self.setIcon(QIcon())
        elif os.path.exists(self.image_path):
            self.setIcon(QIcon(self.image_path))

        # 显示数量
        if self.count > 1:
            self.setText(str(self.count))
        else:
            self.setText("")

class MahjongFanCalculatorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.calculator = MahjongFanCalculator() if MahjongFanCalculator else None
        self.selected_tiles = []

        # ---- 设置持久化（实时自动保存） ----
        self._settings = load_settings()
        self._loading_settings = False          # 加载设置期间禁止回写
        self._settings_save_timer = QTimer(self)  # 500ms 防抖
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(500)
        self._settings_save_timer.timeout.connect(self._save_settings_now)
        self._start_maximized = bool(self._settings.get("window_maximized", False))

        self.init_ui()
        self._apply_settings()
        self._connect_autosave()

        if CORE_IMPORT_ERROR:
            self.hint_label.setText("⚠ 缺少 mahjong_core 计算模块，只能选牌不能算番")

    def init_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setMinimumSize(800, 600)

        self._build_menu_bar()

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 麻将牌选择区域
        self.create_tile_selection(main_layout)
        
        # 操作按钮区域
        self.create_action_buttons(main_layout)
        
        # 特殊番种复选框
        self.create_special_fan_checkboxes(main_layout)
        
        # 圈风门风选择
        self.create_wind_selection(main_layout)
        
        # 花牌选择
        self.create_flower_selection(main_layout)
        
        # 已选牌显示
        self.selected_tiles_label = QLabel("已选牌: ")
        main_layout.addWidget(self.selected_tiles_label)
        
        # 提示信息
        self.hint_label = QLabel("请选择14张牌")
        main_layout.addWidget(self.hint_label)
        
        # 听牌分析结果
        self.ting_result_label = QLabel("")
        main_layout.addWidget(self.ting_result_label)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def _build_menu_bar(self):
        menu = self.menuBar()
        help_menu = menu.addMenu("帮助(&H)")
        about = QAction("关于(&A)", self)
        about.triggered.connect(self.show_about)
        help_menu.addAction(about)
        rules = QAction("规则数据来源(&R)", self)
        rules.triggered.connect(self.show_rules_info)
        help_menu.addAction(rules)

    # ---------------- 设置持久化 ----------------
    def _collect_settings(self) -> dict:
        """把当前界面状态收集成 dict（新增设置项在此登记）。"""
        data = {
            "version": __version__,
            "round_wind": self.get_selected_wind(self.round_wind_group),
            "seat_wind": self.get_selected_wind(self.seat_wind_group),
            "special_fans": self.get_special_fans(),
            "flowers": {name: getattr(self, f"{name}_spin").value() for name in FLOWER_NAMES},
            "window_maximized": bool(self.isMaximized()),
        }
        try:
            geo = self.geometry()
            data["window_geometry"] = [geo.x(), geo.y(), geo.width(), geo.height()]
        except Exception:
            pass
        if self.isMaximized():
            # 最大化时保存"还原后"的几何，避免下次恢复成最大化时的小尺寸
            if "window_geometry" in self._settings:
                data["window_geometry"] = self._settings["window_geometry"]
        return data

    def _apply_settings(self):
        """把已加载的设置应用到控件（全程 blockSignals，避免触发自动保存）。"""
        data = self._settings
        if not data:
            return
        self._loading_settings = True
        try:
            geo = data.get("window_geometry")
            if isinstance(geo, (list, tuple)) and len(geo) == 4:
                try:
                    self.setGeometry(*[int(v) for v in geo])
                except Exception:
                    pass

            for group, key in ((self.round_wind_group, "round_wind"),
                               (self.seat_wind_group, "seat_wind")):
                want = data.get(key)
                for cb in group:
                    cb.blockSignals(True)
                    cb.setChecked(cb.text() == want)
                    cb.blockSignals(False)

            picked = set(data.get("special_fans") or [])
            for fan in SPECIAL_FANS:
                cb = getattr(self, f"{fan}_checkbox", None)
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setChecked(fan in picked)
                    cb.blockSignals(False)

            flowers = data.get("flowers") or {}
            for name in FLOWER_NAMES:
                spin = getattr(self, f"{name}_spin")
                spin.blockSignals(True)
                try:
                    spin.setValue(int(flowers.get(name, 0)))
                except Exception:
                    spin.setValue(0)
                spin.blockSignals(False)
        finally:
            self._loading_settings = False

    def _connect_autosave(self):
        """把所有"设置类"控件的变更信号接到自动保存（新增设置项在此登记）。"""
        for fan in SPECIAL_FANS:
            cb = getattr(self, f"{fan}_checkbox", None)
            if cb is not None:
                cb.stateChanged.connect(self._autosave_settings)
        for name in FLOWER_NAMES:
            getattr(self, f"{name}_spin").valueChanged.connect(self._autosave_settings)

    def _autosave_settings(self, *args):
        """控件变更 → 防抖后写盘。加载设置期间忽略。"""
        if self._loading_settings:
            return
        self._settings_save_timer.start()

    def _save_settings_now(self):
        if self._loading_settings:
            return
        data = self._collect_settings()
        self._settings.update(data)
        save_settings(self._settings)

    def closeEvent(self, event):
        try:
            self._settings_save_timer.stop()
            self._save_settings_now()
        finally:
            super().closeEvent(event)

    # ---------------- 关于 / 数据来源 ----------------
    def show_about(self):
        QMessageBox.about(
            self, f"关于 {APP_NAME}",
            f"<h3>{APP_NAME}</h3>"
            f"<p>版本: {__version__}</p>"
            f"<p>中国国标麻将（竞技麻将）算番与听牌分析工具。</p>"
            f"<p>规则数据：{RULES_FILE}</p>"
            f"<p>设置文件：{SETTINGS_FILE}</p>"
            f"<p>设置实时自动保存，下次启动自动沿用。</p>")

    def show_rules_info(self):
        path = resource_path(RULES_FILE)
        exists = os.path.exists(path)
        core = "已加载" if self.calculator else f"未加载（{CORE_IMPORT_ERROR}）"
        QMessageBox.information(
            self, "规则数据来源",
            f"<p><b>规则文件</b>：{path}（{'存在' if exists else '未找到'}）</p>"
            f"<p><b>计算模块</b>：mahjong_core.MahjongFanCalculator —— {core}</p>"
            f"<hr>"
            f"<p>规则内容依据：</p>"
            f"<ul>"
            f"<li>《中国麻将竞赛规则(试行)》——1998年7月国家体育总局审定，人民体育出版社</li>"
            f"<li>《中国麻将竞赛规则(试行)》问答——杜维忠 著，人民体育出版社 2006</li>"
            f"</ul>"
            f"<p>共 81 个番种、12 个分值级、9 大系列。</p>")
    
    def create_tile_selection(self, layout):
        # 创建麻将牌选择按钮
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        tile_widget = QWidget()
        tile_layout = QVBoxLayout()
        
        # 条子
        hbox = QHBoxLayout()
        for i in range(1, 10):
            btn = TileButton(f"T{i}")
            btn.clicked.connect(lambda _, t=f"T{i}": self.on_tile_selected(t))
            hbox.addWidget(btn)
        tile_layout.addLayout(hbox)
        
        # 筒子
        hbox = QHBoxLayout()
        for i in range(1, 10):
            btn = TileButton(f"B{i}")
            btn.clicked.connect(lambda _, t=f"B{i}": self.on_tile_selected(t))
            hbox.addWidget(btn)
        tile_layout.addLayout(hbox)
        
        # 万子
        hbox = QHBoxLayout()
        for i in range(1, 10):
            btn = TileButton(f"W{i}")
            btn.clicked.connect(lambda _, t=f"W{i}": self.on_tile_selected(t))
            hbox.addWidget(btn)
        tile_layout.addLayout(hbox)
        
        # 字牌
        hbox = QHBoxLayout()
        for i in range(1, 5):  # 东南西北
            btn = TileButton(f"F{i}")
            btn.clicked.connect(lambda _, t=f"F{i}": self.on_tile_selected(t))
            hbox.addWidget(btn)
        for i in range(1, 4):  # 中发白
            btn = TileButton(f"J{i}")
            btn.clicked.connect(lambda _, t=f"J{i}": self.on_tile_selected(t))
            hbox.addWidget(btn)
        tile_layout.addLayout(hbox)
        
        tile_widget.setLayout(tile_layout)
        scroll.setWidget(tile_widget)
        layout.addWidget(scroll)
    
    def create_action_buttons(self, layout):
        hbox = QHBoxLayout()
        actions = ["立牌", "吃", "碰", "明杠", "暗杠", "重置"]
        for action in actions:
            btn = QPushButton(action)
            btn.clicked.connect(lambda _, a=action: self.on_action_clicked(a))
            hbox.addWidget(btn)
        layout.addLayout(hbox)
    
    def create_special_fan_checkboxes(self, layout):
        hbox1 = QHBoxLayout()
        for fan in SPECIAL_FANS:
            cb = QCheckBox(fan)
            cb.stateChanged.connect(self.update_calculation)
            hbox1.addWidget(cb)
            setattr(self, f"{fan}_checkbox", cb)
        layout.addLayout(hbox1)
    
    def create_wind_selection(self, layout):
        # 圈风选择
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("圈风:"))
        self.round_wind_group = []
        for wind in WIND_NAMES:
            rb = QCheckBox(wind)
            rb.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
            rb.toggled.connect(lambda checked, w=wind: self.on_wind_toggled(checked, w, "round"))
            hbox.addWidget(rb)
            self.round_wind_group.append(rb)
        layout.addLayout(hbox)
        
        # 门风选择
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("门风:"))
        self.seat_wind_group = []
        for wind in WIND_NAMES:
            rb = QCheckBox(wind)
            rb.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
            rb.toggled.connect(lambda checked, w=wind: self.on_wind_toggled(checked, w, "seat"))
            hbox.addWidget(rb)
            self.seat_wind_group.append(rb)
        layout.addLayout(hbox)
    
    def on_wind_toggled(self, checked, wind, wind_type):
        # 确保同一时间只能选择一个风向
        if checked:
            group = self.round_wind_group if wind_type == "round" else self.seat_wind_group
            for rb in group:
                if rb.text() != wind:
                    rb.setChecked(False)
        self.update_calculation()
        self._autosave_settings()
    
    def create_flower_selection(self, layout):
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("花牌:"))
        for flower in FLOWER_NAMES:
            spin = QSpinBox()
            spin.setRange(0, 1)
            spin.valueChanged.connect(self.update_calculation)
            hbox.addWidget(QLabel(flower))
            hbox.addWidget(spin)
            setattr(self, f"{flower}_spin", spin)
        layout.addLayout(hbox)
    
    def on_tile_selected(self, tile_type):
        # 更新已选牌列表
        if len(self.selected_tiles) < 14:
            self.selected_tiles.append(tile_type)
        
        # 更新提示信息
        remaining = 14 - len(self.selected_tiles)
        if remaining > 0:
            self.hint_label.setText(f"请再选择{remaining}张牌")
        elif remaining == 0:
            self.hint_label.setText("已选择14张牌")
            self.check_winning_hand()
        else:
            self.selected_tiles = self.selected_tiles[:14]  # 限制最多14张牌
            self.hint_label.setText("已超过14张牌")
        
        # 更新已选牌显示
        self.update_selected_tiles_display()
        
        # 检查听牌状态
        if len(self.selected_tiles) == 13:
            self.analyze_ting()
        else:
            self.ting_result_label.setText("")
    
    def update_selected_tiles_display(self):
        # 统计每种牌的数量
        tile_count = defaultdict(int)
        for tile in self.selected_tiles:
            tile_count[tile] += 1
        
        # 生成显示文本
        display_text = "已选牌: "
        for tile, count in sorted(tile_count.items()):
            display_text += f"{tile}({count}) "
        
        self.selected_tiles_label.setText(display_text)
    
    def check_winning_hand(self):
        """和牌判断：优先调用核心模块的真实判断，核心缺失时退回占位逻辑。"""
        if self.calculator is not None:
            try:
                if self.calculator.is_winning_hand(self.selected_tiles):
                    self.hint_label.setText("和牌!")
                    self.update_calculation()
                else:
                    self.hint_label.setText("诈胡!")
                return
            except Exception as exc:  # noqa: BLE001
                self.hint_label.setText(f"算番失败: {exc}")
                return
        # 占位逻辑（mahjong_core 缺失时）
        if len(set(self.selected_tiles)) <= 5:
            self.hint_label.setText("和牌!(占位判断，未接入 mahjong_core)")
            self.update_calculation()
        else:
            self.hint_label.setText("诈胡!(占位判断，未接入 mahjong_core)")
    
    def analyze_ting(self):
        """听牌分析：优先调用核心模块，核心缺失时退回占位逻辑。"""
        if self.calculator is not None:
            try:
                results = self.calculator.get_possible_winning_tiles(self.selected_tiles)
                if not results:
                    self.ting_result_label.setText("不听牌")
                    return
                parts = []
                for tile, fans in results:
                    total = sum(fans.values()) if isinstance(fans, dict) else int(fans)
                    parts.append(f"{tile}({total}番)")
                self.ting_result_label.setText("听牌: " + " ".join(parts))
                return
            except Exception as exc:  # noqa: BLE001
                self.ting_result_label.setText(f"听牌分析失败: {exc}")
                return
        # 占位逻辑（mahjong_core 缺失时）
        possible_tiles = ["T1", "T9", "B1", "B9", "W1", "W9"]
        if not possible_tiles:
            self.ting_result_label.setText("不听牌")
            return
        result_text = "听牌(占位): "
        for tile in possible_tiles:
            result_text += f"{tile}(8番) "
        self.ting_result_label.setText(result_text)
    
    def update_calculation(self):
        if len(self.selected_tiles) != 14:
            return
        if self.calculator is None:
            self.ting_result_label.setText("缺少 mahjong_core 计算模块，无法算番")
            return
        
        # 获取当前配置
        config = {
            "round_wind": self.get_selected_wind(self.round_wind_group),
            "seat_wind": self.get_selected_wind(self.seat_wind_group),
            "flowers": self.get_flower_count(),
            "special_fans": self.get_special_fans()
        }
        
        # 计算番数
        try:
            fan_result = self.calculator.calculate_fan(self.selected_tiles, config)
        except Exception as exc:  # noqa: BLE001
            self.ting_result_label.setText(f"算番失败: {exc}")
            return
        
        # 显示结果
        self.display_fan_result(fan_result)
    
    def get_selected_wind(self, wind_group):
        for i, cb in enumerate(wind_group):
            if cb.isChecked():
                return WIND_NAMES[i]
        return None
    
    def get_flower_count(self):
        count = 0
        for flower in FLOWER_NAMES:
            count += getattr(self, f"{flower}_spin").value()
        return count
    
    def get_special_fans(self):
        special_fans = []
        for fan in SPECIAL_FANS:
            if getattr(self, f"{fan}_checkbox").isChecked():
                special_fans.append(fan)
        return special_fans
    
    def display_fan_result(self, fan_result):
        # 按番数从高到低排序
        sorted_result = sorted(fan_result.items(), key=lambda x: -x[1])
        
        # 显示结果
        result_text = "番种: "
        for name, value in sorted_result:
            result_text += f"{name}({value}番) "
        
        total_fan = sum(fan_result.values())
        # 起和分校验（《规则》第九条：番种分值之和至少 8 分，花牌不计在起和分内）
        base_fan = total_fan - self.get_flower_count()
        result_text += f"\n总番数: {total_fan}番"
        result_text += (f"（起和分 {base_fan} 分，"
                        f"{'达到' if base_fan >= 8 else '未达到'} 8 分起和标准）")
        
        self.ting_result_label.setText(result_text)
    
    def on_action_clicked(self, action):
        if action == "重置":
            self.selected_tiles = []
            self.selected_tiles_label.setText("已选牌: ")
            self.hint_label.setText("请选择14张牌")
            self.ting_result_label.setText("")
            
            # 重置所有复选框和微调框
            for fan in SPECIAL_FANS:
                getattr(self, f"{fan}_checkbox").setChecked(False)
            
            for wind in self.round_wind_group + self.seat_wind_group:
                wind.setChecked(False)
            
            for flower in FLOWER_NAMES:
                getattr(self, f"{flower}_spin").setValue(0)

            # 重置相当于「设置变更」，立即落盘
            self._settings_save_timer.stop()
            self._save_settings_now()


def main():
    app = QApplication(sys.argv)
    icon_path = resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MahjongFanCalculatorUI()
    if window._start_maximized:
        window.showMaximized()
    else:
        window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()