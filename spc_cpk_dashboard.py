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
        self.all_charts_info = None
        self.raw_charts_dict = {}
        self.cpk_results = {}  # {(group_name, chart_name): {'Cpk': value}}
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
        self.recalc_btn = QtWidgets.QPushButton("重新計算")
        self.switch_view_btn = QtWidgets.QPushButton("切換視圖")
        self.export_btn = QtWidgets.QPushButton("匯出圖片")
        # 改成具名 label 以便設定透明背景
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
        top_bar.addWidget(self.switch_view_btn)
        top_bar.addWidget(self.export_btn)
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
            # 強制實體背景為純白（避免透明造成底色透出）
            pal = frame.palette()
            pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
            frame.setAutoFillBackground(True)
            frame.setPalette(pal)
            layout = QtWidgets.QVBoxLayout(frame)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(4)
            title_label = QtWidgets.QLabel(title)
            title_label.setObjectName("metricTitle")
            # 也確保標題與值 label 背景純白
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
        create_metric_card("custom", "自訂區間 Cpk", 3)
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
        title_lbl = QtWidgets.QLabel("SPC 控制圖")
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
        self.export_btn.clicked.connect(self.export_chart)
        self.chart_combo.currentIndexChanged.connect(self.update_cpk_labels)
        # 套用主題
        self.apply_theme()

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
        
        # 載入 All_Chart_Information 資料
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

        # 填入 chart_combo 下拉選單
        if self.all_charts_info is not None:
            self.chart_combo.clear()
            self.chart_combo.addItem("請選擇 Chart")
            for idx, chart_info in self.all_charts_info.iterrows():
                chart_label = f"{chart_info['GroupName']} - {chart_info['ChartName']}"
                self.chart_combo.addItem(chart_label)

        # 初始化 raw chart 與 Cpk 結果
        self.raw_charts_dict = {}
        self.cpk_results = {}

        if self.all_charts_info is not None:
            raw_data_dir = os.path.join(os.path.dirname(__file__), 'input', 'raw_charts')

            for idx, chart_info in self.all_charts_info.iterrows():
                # 防呆：chart_info 應為 pandas.Series
                if not isinstance(chart_info, pd.Series):
                    print(f"[ERROR] chart_info 不是 Series：{type(chart_info)}，跳過 index={idx}")
                    continue

                group_name = str(chart_info['GroupName'])
                chart_name = str(chart_info['ChartName'])
                print(f"[DEBUG] chart_info idx={idx}, group_name={group_name}, chart_name={chart_name}")

                raw_path = self.oob_module.find_matching_file(raw_data_dir, group_name, chart_name)
                print(f"[DEBUG] raw_path: {raw_path}")

                if raw_path and os.path.exists(raw_path):
                    try:
                        raw_df = pd.read_csv(raw_path)
                        print(f"[DEBUG] raw_df columns: {raw_df.columns}")
                        usl = chart_info.get('USL', None)
                        lsl = chart_info.get('LSL', None)
                        # 只保留 USL/LSL 內的資料
                        if usl is not None and lsl is not None:
                            raw_df = raw_df[(raw_df['point_val'] <= usl) & (raw_df['point_val'] >= lsl)]
                        elif usl is not None:
                            raw_df = raw_df[raw_df['point_val'] <= usl]
                        elif lsl is not None:
                            raw_df = raw_df[raw_df['point_val'] >= lsl]
                        self.raw_charts_dict[(group_name, chart_name)] = raw_df

                        # 依據最新資料時間往前推一個月、兩個月、三個月分別計算 Cpk
                        cpk_dict = {'Cpk': None, 'Cpk_last_month': None, 'Cpk_last2_month': None}
                        if 'point_time' in raw_df.columns and not raw_df.empty:
                            raw_df['point_time'] = pd.to_datetime(raw_df['point_time'])
                            latest_time = raw_df['point_time'].max()
                            # 當月
                            start1 = latest_time - pd.DateOffset(months=1)
                            mask1 = (raw_df['point_time'] > start1) & (raw_df['point_time'] <= latest_time)
                            cpk_dict['Cpk'] = calculate_cpk(raw_df[mask1], chart_info)['Cpk']
                            # 上月
                            start2 = latest_time - pd.DateOffset(months=2)
                            mask2 = (raw_df['point_time'] > start2) & (raw_df['point_time'] <= start1)
                            cpk_dict['Cpk_last_month'] = calculate_cpk(raw_df[mask2], chart_info)['Cpk']
                            # 上上月
                            start3 = latest_time - pd.DateOffset(months=3)
                            mask3 = (raw_df['point_time'] > start3) & (raw_df['point_time'] <= start2)
                            cpk_dict['Cpk_last2_month'] = calculate_cpk(raw_df[mask3], chart_info)['Cpk']
                        else:
                            # 沒有時間欄位就用全部資料
                            cpk_dict['Cpk'] = calculate_cpk(raw_df, chart_info)['Cpk']
                        self.cpk_results[(group_name, chart_name)] = cpk_dict
                        print(f"[DEBUG] Cpk result: {self.cpk_results[(group_name, chart_name)]}")
                    except Exception as e:
                        print(f"[ERROR] Cpk計算失敗: {e}")
                        QtWidgets.QMessageBox.warning(self, "警告", f"讀取/處理 raw chart 失敗: {group_name}/{chart_name}: {e}")
                        self.raw_charts_dict[(group_name, chart_name)] = None
                        self.cpk_results[(group_name, chart_name)] = {'Cpk': None}
                else:
                    print(f"[ERROR] 找不到 raw chart 檔案: {group_name}/{chart_name}")
                    QtWidgets.QMessageBox.warning(self, "警告", f"找不到 raw chart 檔案: {group_name}/{chart_name}")
                    self.raw_charts_dict[(group_name, chart_name)] = None
                    self.cpk_results[(group_name, chart_name)] = {'Cpk': None}

        # SPC圖清空（尚未繪製）
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_title("SPC 控制圖（尚未繪製）")
        ax.set_xlabel("日期")
        ax.set_ylabel("值")
        self.canvas.draw()
        # 更新圖卡
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
            /* 固定灰色卡片，不再依狀態變色 */
            QFrame#metricCard, QFrame#metricCard * { background:#ffffff !important; }
            QFrame#metricCard { border:1px solid #d8dde2; border-radius:16px; }
            QLabel#metricTitle { font-size:11px; font-weight:600; color:#6c7681; letter-spacing:1px; }
            QLabel#metricValue { font-size:30px; font-weight:700; color:#111827; }
            QFrame#metricCard:hover { border:1px solid #aeb5bb; }
            QFrame#chartFrame { background:#ffffff; border:1px solid #d2d7dc; border-radius:22px; }
            QLabel#sectionTitle { font-size:15px; font-weight:600; color:#1f2937; background:transparent; }
            QLabel#plainLabel { background:transparent; color:#1f2937; font-weight:600; }
            """)
        # 陰影 (增強卡片與背景對比)
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
        
        # 載入 All_Chart_Information 資料
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

        # 填入 chart_combo 下拉選單
        if self.all_charts_info is not None:
            self.chart_combo.clear()
            self.chart_combo.addItem("請選擇 Chart")
            for idx, chart_info in self.all_charts_info.iterrows():
                chart_label = f"{chart_info['GroupName']} - {chart_info['ChartName']}"
                self.chart_combo.addItem(chart_label)

        # 初始化 raw chart 與 Cpk 結果
        self.raw_charts_dict = {}
        self.cpk_results = {}

        if self.all_charts_info is not None:
            raw_data_dir = os.path.join(os.path.dirname(__file__), 'input', 'raw_charts')

            for idx, chart_info in self.all_charts_info.iterrows():
                # 防呆：chart_info 應為 pandas.Series
                if not isinstance(chart_info, pd.Series):
                    print(f"[ERROR] chart_info 不是 Series：{type(chart_info)}，跳過 index={idx}")
                    continue

                group_name = str(chart_info['GroupName'])
                chart_name = str(chart_info['ChartName'])
                print(f"[DEBUG] chart_info idx={idx}, group_name={group_name}, chart_name={chart_name}")

                raw_path = self.oob_module.find_matching_file(raw_data_dir, group_name, chart_name)
                print(f"[DEBUG] raw_path: {raw_path}")

                if raw_path and os.path.exists(raw_path):
                    try:
                        raw_df = pd.read_csv(raw_path)
                        print(f"[DEBUG] raw_df columns: {raw_df.columns}")
                        usl = chart_info.get('USL', None)
                        lsl = chart_info.get('LSL', None)
                        # 只保留 USL/LSL 內的資料
                        if usl is not None and lsl is not None:
                            raw_df = raw_df[(raw_df['point_val'] <= usl) & (raw_df['point_val'] >= lsl)]
                        elif usl is not None:
                            raw_df = raw_df[raw_df['point_val'] <= usl]
                        elif lsl is not None:
                            raw_df = raw_df[raw_df['point_val'] >= lsl]
                        self.raw_charts_dict[(group_name, chart_name)] = raw_df

                        # 依據最新資料時間往前推一個月、兩個月、三個月分別計算 Cpk
                        cpk_dict = {'Cpk': None, 'Cpk_last_month': None, 'Cpk_last2_month': None}
                        if 'point_time' in raw_df.columns and not raw_df.empty:
                            raw_df['point_time'] = pd.to_datetime(raw_df['point_time'])
                            latest_time = raw_df['point_time'].max()
                            # 當月
                            start1 = latest_time - pd.DateOffset(months=1)
                            mask1 = (raw_df['point_time'] > start1) & (raw_df['point_time'] <= latest_time)
                            cpk_dict['Cpk'] = calculate_cpk(raw_df[mask1], chart_info)['Cpk']
                            # 上月
                            start2 = latest_time - pd.DateOffset(months=2)
                            mask2 = (raw_df['point_time'] > start2) & (raw_df['point_time'] <= start1)
                            cpk_dict['Cpk_last_month'] = calculate_cpk(raw_df[mask2], chart_info)['Cpk']
                            # 上上月
                            start3 = latest_time - pd.DateOffset(months=3)
                            mask3 = (raw_df['point_time'] > start3) & (raw_df['point_time'] <= start2)
                            cpk_dict['Cpk_last2_month'] = calculate_cpk(raw_df[mask3], chart_info)['Cpk']
                        else:
                            # 沒有時間欄位就用全部資料
                            cpk_dict['Cpk'] = calculate_cpk(raw_df, chart_info)['Cpk']
                        self.cpk_results[(group_name, chart_name)] = cpk_dict
                        print(f"[DEBUG] Cpk result: {self.cpk_results[(group_name, chart_name)]}")
                    except Exception as e:
                        print(f"[ERROR] Cpk計算失敗: {e}")
                        QtWidgets.QMessageBox.warning(self, "警告", f"讀取/處理 raw chart 失敗: {group_name}/{chart_name}: {e}")
                        self.raw_charts_dict[(group_name, chart_name)] = None
                        self.cpk_results[(group_name, chart_name)] = {'Cpk': None}
                else:
                    print(f"[ERROR] 找不到 raw chart 檔案: {group_name}/{chart_name}")
                    QtWidgets.QMessageBox.warning(self, "警告", f"找不到 raw chart 檔案: {group_name}/{chart_name}")
                    self.raw_charts_dict[(group_name, chart_name)] = None
                    self.cpk_results[(group_name, chart_name)] = {'Cpk': None}

        # SPC圖清空（尚未繪製）
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_title("SPC 控制圖（尚未繪製）")
        ax.set_xlabel("日期")
        ax.set_ylabel("值")
        self.canvas.draw()
        # 更新圖卡
        self.update_cpk_labels()

    def _apply_card_status(self, key: str, status: str):
        # 不再改變邊框顏色，保持固定樣式
        return

    def update_cpk_labels(self):
        idx = self.chart_combo.currentIndex() - 1
        for key, comp in self.metric_cards.items():
            comp["value_label"].setText("-")
        if idx < 0 or self.all_charts_info is None:
            return
        chart_info = self.all_charts_info.iloc[idx]
        group_name = str(chart_info['GroupName'])
        chart_name = str(chart_info['ChartName'])
        cpk_result = self.cpk_results.get((group_name, chart_name), {})
        cpk = cpk_result.get('Cpk')
        l1 = cpk_result.get('Cpk_last_month')
        l2 = cpk_result.get('Cpk_last2_month')
        def set_card(key, value, is_percent=False):
            comp = self.metric_cards[key]
            if value is None:
                comp["value_label"].setText("-")
            else:
                if is_percent:
                    comp["value_label"].setText(f"{value:.1f}%")
                else:
                    comp["value_label"].setText(f"{value:.3f}")
        set_card("cpk", cpk)
        set_card("l1", l1)
        set_card("l2", l2)
        # R1 R2
        r1 = r2 = None
        if cpk is not None and l1 is not None and l1 != 0 and cpk <= l1:
            r1 = (1 - (cpk / l1)) * 100
        if cpk is not None and l1 is not None and l2 is not None and l2 != 0 and cpk <= l1 <= l2:
            r2 = (1 - (cpk / l2)) * 100
        set_card("r1", r1, is_percent=True)
        set_card("r2", r2, is_percent=True)

    def export_chart(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "匯出圖片", "spc_chart.png", "PNG Files (*.png)")
        if path:
            self.figure.savefig(path)
            QtWidgets.QMessageBox.information(self, "匯出成功", f"已匯出圖片到：{path}")
