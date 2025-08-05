import os
import pandas as pd
import numpy as np
from PyQt6 import QtWidgets, QtCore
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
        grid = QtWidgets.QGridLayout(self)
        grid.setSpacing(18)
        grid.setContentsMargins(20, 20, 20, 20)

        # 1. 資料區塊
        data_group = QtWidgets.QGroupBox("資料設定")
        data_layout = QtWidgets.QGridLayout(data_group)
        # Chart 選擇下拉選單
        self.chart_combo = QtWidgets.QComboBox()
        self.chart_combo.addItem("請選擇 Chart")
        # 之後 load_all_chart_data 會自動填入 chart_combo
        data_layout.addWidget(QtWidgets.QLabel("選擇 Chart:"), 0, 0)
        data_layout.addWidget(self.chart_combo, 0, 1, 1, 3)
        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-3))
        self.start_date.setCalendarPopup(True)
        self.end_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        data_layout.addWidget(QtWidgets.QLabel("起始日期:"), 2, 0)
        data_layout.addWidget(self.start_date, 2, 1)
        data_layout.addWidget(QtWidgets.QLabel("結束日期:"), 2, 2)
        data_layout.addWidget(self.end_date, 2, 3)
        grid.addWidget(data_group, 0, 0, 1, 2)

        # 2. SPC 圖區塊
        spc_group = QtWidgets.QGroupBox("SPC 控制圖")
        spc_layout = QtWidgets.QVBoxLayout(spc_group)
        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        spc_layout.addWidget(self.canvas)
        grid.addWidget(spc_group, 1, 0, 2, 2)

        # 3. Cpk 指標區塊
        cpk_group = QtWidgets.QGroupBox("Cpk 指標")
        cpk_layout = QtWidgets.QVBoxLayout(cpk_group)
        self.cpk_labels = []
        for label in ["Cpk", "L1 Cpk", "L2 Cpk", "自訂區間 Cpk"]:
            l = QtWidgets.QLabel(f"{label}: N/A")
            cpk_layout.addWidget(l)
            self.cpk_labels.append(l)
        grid.addWidget(cpk_group, 0, 2)

        # 4. R 值區塊
        r_group = QtWidgets.QGroupBox("R 值比較")
        r_layout = QtWidgets.QVBoxLayout(r_group)
        self.r1_label = QtWidgets.QLabel("R1: N/A")
        self.r2_label = QtWidgets.QLabel("R2: N/A")
        self.r_custom_label = QtWidgets.QLabel("自訂區間比較: N/A")
        r_layout.addWidget(self.r1_label)
        r_layout.addWidget(self.r2_label)
        r_layout.addWidget(self.r_custom_label)
        grid.addWidget(r_group, 1, 2)

        # 5. 控制按鈕區塊
        btn_group = QtWidgets.QGroupBox("操作")
        btn_layout = QtWidgets.QHBoxLayout(btn_group)
        self.recalc_btn = QtWidgets.QPushButton("重新計算")
        self.switch_view_btn = QtWidgets.QPushButton("切換視圖")
        self.export_btn = QtWidgets.QPushButton("匯出圖片")
        btn_layout.addWidget(self.recalc_btn)
        btn_layout.addWidget(self.switch_view_btn)
        btn_layout.addWidget(self.export_btn)
        grid.addWidget(btn_group, 2, 2)

        # 事件連接
        self.recalc_btn.clicked.connect(self.recalculate)
        self.export_btn.clicked.connect(self.export_chart)
        self.chart_combo.currentIndexChanged.connect(self.update_cpk_labels)

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

        # 更新畫面
        self.update_cpk_labels()
        self.r1_label.setText("R1: N/A")
        self.r2_label.setText("R2: N/A")
        self.r_custom_label.setText("自訂區間比較: N/A")

    def update_cpk_labels(self):
        # 根據 chart_combo 選擇，更新 Cpk 指標區塊
        idx = self.chart_combo.currentIndex() - 1  # 第一個是"請選擇 Chart"
        for l in self.cpk_labels:
            l.setText(l.text().split(":")[0] + ": N/A")
        if idx < 0 or self.all_charts_info is None:
            return
        chart_info = self.all_charts_info.iloc[idx]
        group_name = str(chart_info['GroupName'])
        chart_name = str(chart_info['ChartName'])
        cpk_result = self.cpk_results.get((group_name, chart_name), {'Cpk': None, 'Cpk_last_month': None, 'Cpk_last2_month': None})
        self.cpk_labels[0].setText(f"Cpk: {cpk_result['Cpk'] if cpk_result['Cpk'] is not None else 'N/A'}")
        self.cpk_labels[1].setText(f"L1 Cpk: {cpk_result['Cpk_last_month'] if cpk_result['Cpk_last_month'] is not None else 'N/A'}")
        self.cpk_labels[2].setText(f"L2 Cpk: {cpk_result['Cpk_last2_month'] if cpk_result['Cpk_last2_month'] is not None else 'N/A'}")

        # R1, R2 計算
        cpk = cpk_result['Cpk']
        l1_cpk = cpk_result['Cpk_last_month']
        l2_cpk = cpk_result['Cpk_last2_month']
        r1 = None
        r2 = None
        if cpk is not None and l1_cpk is not None:
            if cpk <= l1_cpk:
                r1 = 1 - (cpk / l1_cpk) if l1_cpk != 0 else None
        if cpk is not None and l1_cpk is not None and l2_cpk is not None:
            if cpk <= l1_cpk <= l2_cpk:
                r2 = 1 - (cpk / l2_cpk) if l2_cpk != 0 else None
        r1_text = f"R1: {round(r1*100, 1)}%" if r1 is not None else "R1: N/A"
        r2_text = f"R2: {round(r2*100, 1)}%" if r2 is not None else "R2: N/A"
        self.r1_label.setText(r1_text)
        self.r2_label.setText(r2_text)

    def export_chart(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "匯出圖片", "spc_chart.png", "PNG Files (*.png)")
        if path:
            self.figure.savefig(path)
            QtWidgets.QMessageBox.information(self, "匯出成功", f"已匯出圖片到：{path}")
