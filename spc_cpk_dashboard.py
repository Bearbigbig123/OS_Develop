import os
import pandas as pd
import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

def calculate_cpk(raw_df, chart_info):
    print(raw_df)
    print(f"[DEBUG] chart_info type: {type(chart_info)}")
    print(f"[DEBUG] chart_info keys: {list(chart_info.keys()) if hasattr(chart_info, 'keys') else chart_info}")
    print(f"[DEBUG] chart_info: {chart_info}")
    mean = raw_df['point_val'].mean()
    print(f"[DEBUG] mean: {mean}")
    std = raw_df['point_val'].std()
    print(f"[DEBUG] std: {std}")
    characteristic = chart_info['Characteristics']
    usl = chart_info.get('USL', None)
    print(f"[DEBUG] usl: {usl}")
    lsl = chart_info.get('LSL', None)
    print(f"[DEBUG] lsl: {lsl}")
    print(f"[DEBUG] usl: {usl}, lsl: {lsl}, characteristic: {characteristic}")
    cpk = None
    if std > 0:
        if characteristic == 'Nominal':
            if usl is not None and lsl is not None:
                cpu = (usl - mean) / (3 * std)
                cpl = (mean - lsl) / (3 * std)
                cpk = min(cpu, cpl)
        elif characteristic == 'Smaller':
            if usl is not None:
                cpk = (usl - mean) / (3 * std)
        elif characteristic == 'Bigger':
            if lsl is not None:
                cpk = (mean - lsl) / (3 * std)
    if cpk is not None:
        cpk = round(cpk, 3)
    return {'Cpk': cpk}

class SPCCpkDashboard(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SPC Cpk Dashboard")
        self.resize(1200, 800)
        # 資料結構初始化
        self.all_charts_info = None
        self.raw_charts_dict = {}
        self.cpk_results = {}  # {(group_name, chart_name): {'Cpk': value}}
        self.chart_date_states = {}  # 每張圖的日期狀態：{'custom': bool, 'start': date, 'end': date}
        self.axis_mode = 'index'  # 'index' (等距) 或 'time'
        self.init_ui()
    def load_all_chart_data(self):
        # 已廢棄，邏輯移到 recalculate
        pass

    def init_ui(self):
        # 重新打造為 Dashboard 版型
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)
        # ===== Top Filter / Action Bar =====
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setSpacing(12)
        self.chart_combo = QtWidgets.QComboBox()
        self.chart_combo.addItem("請選擇 Chart")
        self.chart_combo.setMinimumWidth(280)
        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-3))
        self.start_date.setCalendarPopup(True)
        self.end_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        # 只保留執行分析按鈕，並重新設計
        self.recalc_btn = QtWidgets.QPushButton("執行分析")
        self.recalc_btn.setMinimumHeight(38)
        self.recalc_btn.setMinimumWidth(120)
        self.recalc_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4fd8);
                color: #fff;
                border: none;
                border-radius: 18px;
                font-size: 16px;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4fd8, stop:1 #2563eb);
            }
            QPushButton:pressed {
                background: #163fae;
            }
        """)
        lbl_chart = QtWidgets.QLabel("Chart:")
        lbl_chart.setObjectName("plainLabel")
        lbl_start = QtWidgets.QLabel("起始:")
        lbl_start.setObjectName("plainLabel")
        lbl_end = QtWidgets.QLabel("結束:")
        lbl_end.setObjectName("plainLabel")
        top_bar.addWidget(lbl_chart)
        top_bar.addWidget(self.chart_combo)
        top_bar.addSpacing(6)
        top_bar.addWidget(lbl_start)
        top_bar.addWidget(self.start_date)
        top_bar.addWidget(lbl_end)
        top_bar.addWidget(self.end_date)
        top_bar.addStretch(1)
        top_bar.addWidget(self.recalc_btn)
        root.addLayout(top_bar)
        # ===== Metric Cards Row =====
        self.metric_cards = {}
        cards_layout = QtWidgets.QGridLayout()
        cards_layout.setHorizontalSpacing(16)
        cards_layout.setVerticalSpacing(14)
        def create_metric_card(key, title, col, row=0):
            frame = QtWidgets.QFrame()
            frame.setObjectName("metricCard")
            frame.setProperty("status", "neutral")
            pal = frame.palette()
            pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
            frame.setAutoFillBackground(True)
            frame.setPalette(pal)
            layout = QtWidgets.QVBoxLayout(frame)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(4)
            title_label = QtWidgets.QLabel(title)
            title_label.setObjectName("metricTitle")
            title_label.setAutoFillBackground(True)
            tpal = title_label.palette()
            tpal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
            title_label.setPalette(tpal)
            value_label = QtWidgets.QLabel("-")
            value_label.setObjectName("metricValue")
            value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            value_label.setAutoFillBackground(True)
            vpal = value_label.palette()
            vpal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
            value_label.setPalette(vpal)
            layout.addWidget(title_label)
            layout.addWidget(value_label)
            layout.addStretch(1)
            cards_layout.addWidget(frame, row, col)
            self.metric_cards[key] = {"frame": frame, "value_label": value_label, "title_label": title_label}
        create_metric_card("cpk", "Cpk", 0)
        create_metric_card("l1", "L1 Cpk", 1)
        create_metric_card("l2", "L2 Cpk", 2)
        create_metric_card("custom", "Long-Term Cpk", 3)
        create_metric_card("r1", "R1", 4)
        create_metric_card("r2", "R2", 5)
        root.addLayout(cards_layout)
        # ===== Chart Area =====
        self.chart_frame = QtWidgets.QFrame()
        self.chart_frame.setObjectName("chartFrame")
        chart_layout = QtWidgets.QVBoxLayout(self.chart_frame)
        chart_layout.setContentsMargins(18, 16, 18, 16)
        chart_layout.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel("SPC Chart")
        title_lbl.setObjectName("sectionTitle")
        header.addWidget(title_lbl)
        header.addStretch(1)
        chart_layout.addLayout(header)
        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas, 1)
        root.addWidget(self.chart_frame, 1)
        # 事件連接
        self.recalc_btn.clicked.connect(self.recalculate)
        self.chart_combo.currentIndexChanged.connect(self.update_cpk_labels)
        self.start_date.dateChanged.connect(self.on_date_changed)
        self.end_date.dateChanged.connect(self.on_date_changed)
        self.apply_theme()

    # === 檔案載入 ===
    def load_csv(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "選擇 CSV 檔案", "", "CSV Files (*.csv)")
        if path:
            try:
                self.data = pd.read_csv(path)
                self.file_label.setText(f"已載入：{os.path.basename(path)}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "錯誤", f"載入失敗：{e}")
                self.file_label.setText("載入失敗")
            self.recalculate()

    # === 重新計算 ===
    def recalculate(self):
        print("[DEBUG] recalculate called")
        # 重新載入 chart 資訊
        chart_excel_path = os.path.join(os.path.dirname(__file__), 'input', 'All_Chart_Information.xlsx')
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("oob_module", os.path.join(os.path.dirname(__file__), "0621.py"))
            oob_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(oob_module)
            self.oob_module = oob_module
            self.all_charts_info = oob_module.load_chart_information(chart_excel_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "錯誤", f"載入圖表資訊失敗: {e}")
            self.all_charts_info = None
            return

        # 更新下拉選單
        if self.all_charts_info is not None:
            self.chart_combo.clear()
            self.chart_combo.addItem("請選擇 Chart")
            for _, chart_info in self.all_charts_info.iterrows():
                self.chart_combo.addItem(f"{chart_info['GroupName']} - {chart_info['ChartName']}")

        # 重置資料結構
        self.raw_charts_dict = {}
        self.cpk_results = {}
        self.chart_date_states = {}

        if self.all_charts_info is not None:
            raw_data_dir = os.path.join(os.path.dirname(__file__), 'input', 'raw_charts')
            for _, chart_info in self.all_charts_info.iterrows():
                if not isinstance(chart_info, pd.Series):
                    continue
                group_name = str(chart_info['GroupName'])
                chart_name = str(chart_info['ChartName'])
                raw_path = self.oob_module.find_matching_file(raw_data_dir, group_name, chart_name)
                if raw_path and os.path.exists(raw_path):
                    try:
                        raw_df = pd.read_csv(raw_path)
                        usl = chart_info.get('USL', None)
                        lsl = chart_info.get('LSL', None)
                        if usl is not None and lsl is not None:
                            raw_df = raw_df[(raw_df['point_val'] <= usl) & (raw_df['point_val'] >= lsl)]
                        elif usl is not None:
                            raw_df = raw_df[raw_df['point_val'] <= usl]
                        elif lsl is not None:
                            raw_df = raw_df[raw_df['point_val'] >= lsl]
                        self.raw_charts_dict[(group_name, chart_name)] = raw_df
                        quick_cpk = calculate_cpk(raw_df, chart_info)['Cpk']
                        self.cpk_results[(group_name, chart_name)] = {'Cpk': quick_cpk}
                        self.chart_date_states[(group_name, chart_name)] = {'custom': False, 'start': None, 'end': None}
                    except Exception as e:
                        self.raw_charts_dict[(group_name, chart_name)] = None
                        self.cpk_results[(group_name, chart_name)] = {'Cpk': None}
                        print(f"[ERROR] raw chart 載入失敗 {group_name}/{chart_name}: {e}")
                else:
                    self.raw_charts_dict[(group_name, chart_name)] = None
                    self.cpk_results[(group_name, chart_name)] = {'Cpk': None}
        # 清空圖表並等待選擇
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_title("SPC 控制圖（尚未繪製）")
        ax.set_xlabel("日期")
        ax.set_ylabel("值")
        self.canvas.draw()
        self.update_cpk_labels()

    def load_csv(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "選擇 CSV 檔案", "", "CSV Files (*.csv)")
        if path:
            try:
                self.data = pd.read_csv(path)
                self.file_label.setText(f"已載入：{os.path.basename(path)}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "錯誤", f"載入失敗：{e}")
                self.file_label.setText("載入失敗")
            self.recalculate()

    def recalculate(self):
        print("[DEBUG] recalculate called")
        # 重新載入 chart 資訊
        chart_excel_path = os.path.join(os.path.dirname(__file__), 'input', 'All_Chart_Information.xlsx')
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("oob_module", os.path.join(os.path.dirname(__file__), "0621.py"))
            oob_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(oob_module)
            self.oob_module = oob_module
            self.all_charts_info = oob_module.load_chart_information(chart_excel_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "錯誤", f"載入圖表資訊失敗: {e}")
            self.all_charts_info = None
            return

        # 更新下拉選單
        if self.all_charts_info is not None:
            self.chart_combo.clear()
            self.chart_combo.addItem("請選擇 Chart")
            for _, chart_info in self.all_charts_info.iterrows():
                self.chart_combo.addItem(f"{chart_info['GroupName']} - {chart_info['ChartName']}")

        # 重置資料結構
        self.raw_charts_dict = {}
        self.cpk_results = {}
        self.chart_date_states = {}

        if self.all_charts_info is not None:
            raw_data_dir = os.path.join(os.path.dirname(__file__), 'input', 'raw_charts')
            for _, chart_info in self.all_charts_info.iterrows():
                if not isinstance(chart_info, pd.Series):
                    continue
                group_name = str(chart_info['GroupName'])
                chart_name = str(chart_info['ChartName'])
                raw_path = self.oob_module.find_matching_file(raw_data_dir, group_name, chart_name)
                if raw_path and os.path.exists(raw_path):
                    try:
                        raw_df = pd.read_csv(raw_path)
                        usl = chart_info.get('USL', None)
                        lsl = chart_info.get('LSL', None)
                        if usl is not None and lsl is not None:
                            raw_df = raw_df[(raw_df['point_val'] <= usl) & (raw_df['point_val'] >= lsl)]
                        elif usl is not None:
                            raw_df = raw_df[raw_df['point_val'] <= usl]
                        elif lsl is not None:
                            raw_df = raw_df[raw_df['point_val'] >= lsl]
                        self.raw_charts_dict[(group_name, chart_name)] = raw_df
                        quick_cpk = calculate_cpk(raw_df, chart_info)['Cpk']
                        self.cpk_results[(group_name, chart_name)] = {'Cpk': quick_cpk}
                        self.chart_date_states[(group_name, chart_name)] = {'custom': False, 'start': None, 'end': None}
                    except Exception as e:
                        self.raw_charts_dict[(group_name, chart_name)] = None
                        self.cpk_results[(group_name, chart_name)] = {'Cpk': None}
                        print(f"[ERROR] raw chart 載入失敗 {group_name}/{chart_name}: {e}")
                else:
                    self.raw_charts_dict[(group_name, chart_name)] = None
                    self.cpk_results[(group_name, chart_name)] = {'Cpk': None}
        # 清空圖表並等待選擇
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_title("SPC 控制圖（尚未繪製）")
        ax.set_xlabel("日期")
        ax.set_ylabel("值")
        self.canvas.draw()
        self.update_cpk_labels()

    def apply_theme(self, mode: str = "light"):
        if mode == "light":
            self.setStyleSheet("""
            QWidget { background:#eef1f5; color:#222; font-family:'Microsoft YaHei'; font-size:13px; }
            QComboBox, QDateEdit { background:#ffffff; border:1px solid #c5ccd4; padding:4px 8px; border-radius:7px; }
            QComboBox:hover, QDateEdit:hover { border:1px solid #98a3af; }
            QPushButton { background:#2563eb; color:#fff; border:none; padding:7px 18px; border-radius:8px; font-weight:600; }
            QPushButton:hover { background:#1d4fd8; }
            QPushButton:pressed { background:#163fae; }
            QFrame#metricCard, QFrame#metricCard * { background:#ffffff !important; }
            QFrame#metricCard { border:1px solid #d8dde2; border-radius:16px; }
            QLabel#metricTitle { font-size:11px; font-weight:600; color:#6c7681; letter-spacing:1px; }
            QLabel#metricValue { font-size:30px; font-weight:700; color:#111827; }
            QFrame#metricCard:hover { border:1px solid #aeb5bb; }
            QFrame#chartFrame { background:#ffffff; border:1px solid #d2d7dc; border-radius:22px; }
            QLabel#sectionTitle { font-size:15px; font-weight:600; color:#1f2937; background:transparent; }
            QLabel#plainLabel { font-size:13px; font-weight:600; color:#1f2937; background:transparent; }
            """)
        for meta in self.metric_cards.values():
            if meta["frame"].graphicsEffect() is None:
                eff = QtWidgets.QGraphicsDropShadowEffect(self)
                eff.setBlurRadius(18)
                eff.setOffset(0, 4)
                eff.setColor(QtGui.QColor(0, 0, 0, 26))
                meta["frame"].setGraphicsEffect(eff)
        if self.chart_frame.graphicsEffect() is None:
            eff2 = QtWidgets.QGraphicsDropShadowEffect(self)
            eff2.setBlurRadius(28)
            eff2.setOffset(0, 5)
            eff2.setColor(QtGui.QColor(0, 0, 0, 30))
            self.chart_frame.setGraphicsEffect(eff2)

    # ==== 重複定義刪除 (上方已有 recalculate) ====

    # (duplicate apply_theme & recalculate removed)

    def _apply_card_status(self, key: str, status: str):
        # 不再改變邊框顏色，保持固定樣式
        return

    def update_cpk_labels(self):
        """選擇 chart 時：若該 chart 尚未自訂日期 -> 自動用最新往回三個月，之後使用者調整不再被覆蓋。"""
        idx = self.chart_combo.currentIndex() - 1
        for key, comp in self.metric_cards.items():
            comp["value_label"].setText("-")
        if idx < 0 or self.all_charts_info is None:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_title("SPC 控制圖（尚未選擇）")
            self.canvas.draw()
            return
        chart_info = self.all_charts_info.iloc[idx]
        group_name = str(chart_info['GroupName'])
        chart_name = str(chart_info['ChartName'])
        key = (group_name, chart_name)
        raw_df = self.raw_charts_dict.get(key)
        state = self.chart_date_states.get(key)
        if state is None:
            state = {'custom': False, 'start': None, 'end': None}
            self.chart_date_states[key] = state
        # 第一次自動套日期
        if (not state['custom']) and raw_df is not None and not raw_df.empty and 'point_time' in raw_df.columns:
            try:
                tmp = raw_df.copy()
                tmp['point_time'] = pd.to_datetime(tmp['point_time'])
                latest = tmp['point_time'].max()
                start_candidate = latest - pd.DateOffset(months=3)
                earliest = tmp['point_time'].min()
                if start_candidate < earliest:
                    start_candidate = earliest
                blocker1 = QtCore.QSignalBlocker(self.start_date)
                blocker2 = QtCore.QSignalBlocker(self.end_date)
                self.end_date.setDate(QtCore.QDate(latest.year, latest.month, latest.day))
                self.start_date.setDate(QtCore.QDate(start_candidate.year, start_candidate.month, start_candidate.day))
                del blocker1, blocker2
                state['start'] = start_candidate.date()
                state['end'] = latest.date()
            except Exception as e:
                print(f"[WARN] 自動日期設定失敗: {e}")
        # 動態計算 + 繪圖
        self._update_current_chart_dynamic(chart_info)

    # === 使用者調整日期事件 ===
    def on_date_changed(self, *_):
        idx = self.chart_combo.currentIndex() - 1
        if idx < 0 or self.all_charts_info is None:
            return
        chart_info = self.all_charts_info.iloc[idx]
        group_name = str(chart_info['GroupName'])
        chart_name = str(chart_info['ChartName'])
        key = (group_name, chart_name)
        state = self.chart_date_states.get(key)
        if state is None:
            state = {'custom': False, 'start': None, 'end': None}
            self.chart_date_states[key] = state
        state['custom'] = True
        state['start'] = self.start_date.date().toPyDate()
        state['end'] = self.end_date.date().toPyDate()
        self._update_current_chart_dynamic(chart_info)

    # === Cpk 動態計算 ===
    def _compute_cpk_windows(self, raw_df: pd.DataFrame, chart_info: pd.Series, end_time: pd.Timestamp):
        """以 end_time 為基準計算最近三個連續月度窗口的 Cpk。"""
        result = {'Cpk': None, 'Cpk_last_month': None, 'Cpk_last2_month': None}
        if raw_df is None or raw_df.empty:
            return result
        if 'point_time' not in raw_df.columns:
            result['Cpk'] = calculate_cpk(raw_df, chart_info)['Cpk']
            return result
        df = raw_df.copy()
        df['point_time'] = pd.to_datetime(df['point_time'])
        df = df[df['point_time'] <= end_time]
        if df.empty:
            return result
        start1 = end_time - pd.DateOffset(months=1)
        start2 = end_time - pd.DateOffset(months=2)
        start3 = end_time - pd.DateOffset(months=3)
        mask1 = (df['point_time'] > start1) & (df['point_time'] <= end_time)
        mask2 = (df['point_time'] > start2) & (df['point_time'] <= start1)
        mask3 = (df['point_time'] > start3) & (df['point_time'] <= start2)
        if mask1.any():
            result['Cpk'] = calculate_cpk(df[mask1], chart_info)['Cpk']
        if mask2.any():
            result['Cpk_last_month'] = calculate_cpk(df[mask2], chart_info)['Cpk']
        if mask3.any():
            result['Cpk_last2_month'] = calculate_cpk(df[mask3], chart_info)['Cpk']
        return result

    def _recompute_cpk_for_chart(self, chart_info: pd.Series, end_date):
        group_name = str(chart_info['GroupName'])
        chart_name = str(chart_info['ChartName'])
        raw_df = self.raw_charts_dict.get((group_name, chart_name))
        if raw_df is None or raw_df.empty:
            return {'Cpk': None, 'Cpk_last_month': None, 'Cpk_last2_month': None}
        if 'point_time' not in raw_df.columns:
            return {'Cpk': calculate_cpk(raw_df, chart_info)['Cpk'], 'Cpk_last_month': None, 'Cpk_last2_month': None}
        raw_df_local = raw_df.copy()
        raw_df_local['point_time'] = pd.to_datetime(raw_df_local['point_time'])
        latest = raw_df_local['point_time'].max()
        end_time = pd.to_datetime(end_date)
        if end_time > latest:
            end_time = latest
        return self._compute_cpk_windows(raw_df_local, chart_info, end_time)

    def _update_current_chart_dynamic(self, chart_info: pd.Series):
        group_name = str(chart_info['GroupName'])
        chart_name = str(chart_info['ChartName'])
        # 重新計算 Cpk 以目前 end_date 為基準
        end_d = self.end_date.date().toPyDate()
        cpk_res = self._recompute_cpk_for_chart(chart_info, end_d)
        # 改為全部資料 Cpk
        all_data_cpk = None
        raw_df = self.raw_charts_dict.get((group_name, chart_name))
        if raw_df is not None and not raw_df.empty:
            all_data_cpk = calculate_cpk(raw_df, chart_info)['Cpk']
        def set_card(key, value, is_percent=False):
            comp = self.metric_cards[key]
            if value is None:
                comp['value_label'].setText('-')
            else:
                comp['value_label'].setText(f"{value:.1f}%" if is_percent else f"{value:.3f}")
        set_card('cpk', cpk_res.get('Cpk'))
        set_card('l1', cpk_res.get('Cpk_last_month'))
        set_card('l2', cpk_res.get('Cpk_last2_month'))
        set_card('custom', all_data_cpk)
        cpk = cpk_res.get('Cpk')
        l1 = cpk_res.get('Cpk_last_month')
        l2 = cpk_res.get('Cpk_last2_month')
        r1 = r2 = None
        if cpk is not None and l1 is not None and l1 != 0 and cpk <= l1:
            r1 = (1 - (cpk / l1)) * 100
        if cpk is not None and l1 is not None and l2 is not None and l2 != 0 and cpk <= l1 <= l2:
            r2 = (1 - (cpk / l2)) * 100
        set_card('r1', r1, is_percent=True)
        set_card('r2', r2, is_percent=True)
        # 依目前日期範圍重畫圖
        self.draw_spc_chart(group_name, chart_name, chart_info)

    # === X 軸模式切換 ===
    def toggle_axis_mode(self):
        self.axis_mode = 'time' if self.axis_mode == 'index' else 'index'
        # 更新按鈕文字
        self.axis_mode_btn.setText('等距軸' if self.axis_mode == 'time' else '時間軸')
        # 重新繪圖（若已選 chart）
        idx = self.chart_combo.currentIndex() - 1
        if idx >= 0 and self.all_charts_info is not None:
            chart_info = self.all_charts_info.iloc[idx]
            group_name = str(chart_info['GroupName'])
            chart_name = str(chart_info['ChartName'])
            self.draw_spc_chart(group_name, chart_name, chart_info)

    def draw_spc_chart(self, group_name: str, chart_name: str, chart_info):
        raw_df = self.raw_charts_dict.get((group_name, chart_name))
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        # 標題格式: [GroupName@ChartName@Characteristics]
        characteristics = chart_info.get('Characteristics', '')
        ax.set_title(f"{group_name}@{chart_name}@{characteristics}")
        ax.set_xlabel("" if self.axis_mode == 'index' else "")
        ax.set_ylabel("值")
        if raw_df is None or raw_df.empty:
            ax.text(0.5, 0.5, "無資料", ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw()
            return
        plot_df = raw_df.copy()
        original_len = len(plot_df)
        # 日期過濾 (若有 point_time 欄位)
        if 'point_time' in plot_df.columns:
            try:
                plot_df['point_time'] = pd.to_datetime(plot_df['point_time'])
                start_ts = pd.to_datetime(self.start_date.date().toString('yyyy-MM-dd'))
                end_ts = pd.to_datetime(self.end_date.date().toString('yyyy-MM-dd')) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
                filtered = plot_df[(plot_df['point_time'] >= start_ts) & (plot_df['point_time'] <= end_ts)]
                if not filtered.empty:
                    plot_df = filtered
                # 若篩完完全沒有資料，則退回全部而不顯示『日期區間無資料』
            except Exception:
                pass
        if plot_df.empty:
            ax.text(0.5, 0.5, "無資料", ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw()
            return
        # X 軸處理：
        y = plot_df['point_val'].values
        use_time_axis = False
        if self.axis_mode == 'time' and 'point_time' in plot_df.columns:
            try:
                plot_df['point_time'] = pd.to_datetime(plot_df['point_time'])
                plot_df = plot_df.sort_values('point_time')
                x = plot_df['point_time'].values
                use_time_axis = True
            except Exception:
                x = range(1, len(y) + 1)
        else:
            # 等距模式：保持所有點等距，避免同時間戳疊在一起
            if 'point_time' in plot_df.columns:
                try:
                    plot_df['point_time'] = pd.to_datetime(plot_df['point_time'])
                    plot_df = plot_df.sort_values('point_time').reset_index(drop=True)
                except Exception:
                    pass
            x = range(1, len(y) + 1)
        # 計算統計線
        usl = chart_info.get('USL', None)
        lsl = chart_info.get('LSL', None)
        target = None
        for key in ['Target', 'TARGET', 'TargetValue', '中心線', 'Center']:
            if key in chart_info and pd.notna(chart_info[key]):
                target = chart_info[key]
                break
        mean_val = float(np.mean(y)) if len(y) else None
        # 繪製點與線 (主數據線與超規點不加入 legend)
        ax.plot(x, y, linestyle='-', marker='o', color='#2563eb', markersize=5, linewidth=1.2, label='_nolegend_')
        if usl is not None:
            ax.scatter([xi for xi, yi in zip(x, y) if yi > usl], [yi for yi in y if yi > usl], color='#dc2626', s=36, zorder=5, label='_nolegend_')
        if lsl is not None:
            ax.scatter([xi for xi, yi in zip(x, y) if yi < lsl], [yi for yi in y if yi < lsl], color='#dc2626', marker='s', s=36, zorder=5, label='_nolegend_')
        # 計算 y 範圍（納入 USL/LSL/Target/Mean）避免被裁切
        extra_vals = [v for v in [usl, lsl, target, mean_val]
                      if v is not None and not (isinstance(v, float) and np.isnan(v))]
        if len(y) > 0:
            ymin_sel = float(np.min(y))
            ymax_sel = float(np.max(y))
        else:
            ymin_sel, ymax_sel = (0.0, 1.0)
        if extra_vals:
            ymin_sel = min(ymin_sel, min(extra_vals))
            ymax_sel = max(ymax_sel, max(extra_vals))
        rng = ymax_sel - ymin_sel
        margin = 0.05 * rng if rng > 0 else 1.0
        ax.set_ylim(ymin_sel - margin, ymax_sel + margin)

        # 畫短水平線，並讓文字直接接在線的末端
        from matplotlib import transforms as mtransforms
        trans = mtransforms.blended_transform_factory(ax.transAxes, ax.transData)
        def segment_with_label(val, name, color, va='center'):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return
            x0, x1 = 0.0, 0.965  # 線更長，文字更貼近右邊界
            ax.plot([x0, x1], [val, val], transform=trans, color=color, linestyle='--', linewidth=1.1)
            ax.text(x1, val, name, transform=trans, color=color, va=va, ha='left', fontsize=9)

        segment_with_label(usl, 'USL', '#ef4444', va='center')
        segment_with_label(lsl, 'LSL', '#ef4444', va='center')
        segment_with_label(target, 'Target', '#f59e0b', va='center')
        segment_with_label(mean_val, 'Mean', '#16a34a', va='center')
        # 時間軸格式化
        if use_time_axis:
            try:
                import matplotlib.dates as mdates
                locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
                formatter = mdates.ConciseDateFormatter(locator)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(formatter)
                for label in ax.get_xticklabels():
                    label.set_rotation(90)
                    label.set_ha('center')
            except Exception:
                pass
        else:
            # 等距模式若有時間欄位，挑選部分刻度顯示對應日期字串
            if 'point_time' in plot_df.columns and not plot_df.empty:
                times = plot_df['point_time'].tolist()
                total = len(times)
                if total <= 12:
                    tick_idx = list(range(1, total + 1))
                else:
                    step = max(1, total // 8)
                    tick_idx = list(range(1, total + 1, step))
                    if tick_idx[-1] != total:
                        tick_idx.append(total)
                labels = [times[i-1].strftime('%Y-%m-%d') for i in tick_idx]
                ax.set_xticks(tick_idx)
                ax.set_xticklabels(labels, rotation=90, ha='center', fontsize=8)
        ax.grid(True, linestyle=':', linewidth=0.6, alpha=0.5)
        self.figure.tight_layout()
        self.canvas.draw()
    def export_chart(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "匯出圖片", "spc_chart.png", "PNG Files (*.png)")
        if path:
            self.figure.savefig(path)
            QtWidgets.QMessageBox.information(self, "匯出成功", f"已匯出圖片到：{path}")
