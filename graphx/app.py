from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QDockWidget,
    QFileDialog, QMessageBox, QLabel, QScrollArea, QApplication,
)
from PyQt6.QtGui import QAction, QActionGroup, QDragEnterEvent, QDropEvent, QKeyEvent
from PyQt6.QtCore import Qt, QFileSystemWatcher
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
import pandas as pd
import os
import subprocess
import io

from .state import PlotState
from .canvas import MplCanvas
from .widgets.plot_controls import PlotControlsWidget, CurvePanelWidget
from .widgets.data_table import DataTableWindow
from .widgets.tool_panel import ToolPanelWidget
from .dialogs.fit_window import FitWindow

FIT_DASH_COLORS = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
    "#ff7f00", "#a65628", "#f781bf", "#999999",
]


class GraphXApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = PlotState()
        self.canvas = MplCanvas(self)
        self._data_table_window = None
        self._fit_windows = {}     # curve id -> FitWindow
        self._analysis_fit_win = None  # menu-triggered FitWindow
        self._source_path = None      # track loaded file for watcher & open-in-excel
        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.fileChanged.connect(self._on_source_file_changed)
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_dock_widgets()
        self._setup_status_bar()
        self.setWindowTitle("GraphX")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

    # --- Menu bar ---
    def _setup_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        open_action = QAction("&Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)
        paste_action = QAction("&Paste from Clipboard", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self._on_paste)
        file_menu.addAction(paste_action)
        file_menu.addSeparator()
        export_action = QAction("E&xport Plot...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)
        export_data_action = QAction("Export &Data...", self)
        export_data_action.setShortcut("Ctrl+Shift+E")
        export_data_action.triggered.connect(self._on_export_data)
        file_menu.addAction(export_data_action)
        file_menu.addSeparator()
        excel_action = QAction("Open in E&xcel", self)
        excel_action.triggered.connect(self._on_open_in_excel)
        file_menu.addAction(excel_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Plot menu
        plot_menu = menubar.addMenu("&Plot")
        self.plot_group = QActionGroup(self)
        self.plot_group.setExclusive(True)
        for label, ptype in [
            ("&Line", "line"), ("&Scatter", "scatter"),
            ("&Bar", "bar"), ("&Histogram", "histogram"),
            ("&Pie", "pie"), ("3D &Surface", "surface_3d"),
        ]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(ptype)
            action.triggered.connect(lambda checked, t=ptype: self._on_change_plot_type(t))
            self.plot_group.addAction(action)
            plot_menu.addAction(action)
        self.plot_group.actions()[0].setChecked(True)

        # View menu
        view_menu = menubar.addMenu("&View")
        self.toggle_table_action = QAction("&Data Table", self)
        self.toggle_table_action.setCheckable(True)
        self.toggle_table_action.setChecked(False)
        self.toggle_table_action.triggered.connect(self._on_toggle_data_table)
        view_menu.addAction(self.toggle_table_action)

        toggle_curves_action = QAction("&Curve Panel", self)
        toggle_curves_action.setCheckable(True)
        toggle_curves_action.setChecked(True)
        toggle_curves_action.triggered.connect(self._on_toggle_curve_panel)
        view_menu.addAction(toggle_curves_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")
        fit_window_action = QAction("&Fitting...", self)
        fit_window_action.setShortcut("Ctrl+F")
        fit_window_action.triggered.connect(self._on_open_analysis_fit)
        analysis_menu.addAction(fit_window_action)
        analysis_menu.addSeparator()
        kmeans_action = QAction("&K-Means Clustering", self)
        kmeans_action.triggered.connect(self._on_run_clustering)
        analysis_menu.addAction(kmeans_action)
        elbow_action = QAction("K-Means &Elbow Method", self)
        elbow_action.triggered.connect(self._on_elbow_method)
        analysis_menu.addAction(elbow_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    # --- Toolbar ---
    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

    # --- Central widget ---
    def _setup_central_widget(self):
        # Canvas area
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        canvas_layout.addWidget(toolbar)
        canvas_layout.addWidget(self.canvas)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_layout.setSpacing(4)

        self.plot_controls = PlotControlsWidget()
        self.plot_controls.changed.connect(self._on_controls_changed)
        sidebar_layout.addWidget(self.plot_controls)

        self.tool_panel = ToolPanelWidget()
        self.tool_panel.fit_requested.connect(self._on_run_fitting)
        self.tool_panel.cluster_requested.connect(self._on_run_clustering)
        self.tool_panel.elbow_requested.connect(self._on_elbow_method)
        self.tool_panel.calculate_requested.connect(self._on_calculate)
        self.tool_panel.summarize_requested.connect(self._on_summarize)
        self.tool_panel.view_error_bars_toggled.connect(self._on_toggle_error_bars)
        sidebar_layout.addWidget(self.tool_panel)

        # Splitter: canvas | sidebar
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(canvas_widget)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    # --- Dock widgets ---
    def _setup_dock_widgets(self):
        # Curve panel as a dock on the left
        self.curve_panel = CurvePanelWidget()
        self.curve_panel.add_curve_requested.connect(self._on_add_curve)
        self.curve_panel.changed.connect(self._on_controls_changed)
        self.curve_panel.fit_requested.connect(self._on_open_fit_window)
        self.plot_controls.color_changed.connect(self.curve_panel.apply_color_to_all)

        self.curve_dock = QDockWidget("Curves", self)
        self.curve_dock.setWidget(self.curve_panel)
        self.curve_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.curve_dock)

    def _on_toggle_curve_panel(self, visible):
        if self.curve_dock:
            self.curve_dock.setVisible(visible)

    def _on_toggle_data_table(self, visible):
        if visible:
            self._show_data_table_window()
        else:
            if self._data_table_window:
                self._data_table_window.hide()

    def _show_data_table_window(self):
        if self._data_table_window is None:
            self._data_table_window = DataTableWindow()
            self._data_table_window.column_clicked.connect(self._on_column_clicked)
        self._data_table_window.show()
        self._data_table_window.raise_()
        self.toggle_table_action.setChecked(True)

    def _on_column_clicked(self, col_name):
        """Insert clicked column name into the calculator expression field."""
        calc_edit = self.tool_panel.calc_expr_edit
        cursor = calc_edit.cursorPosition()
        current = calc_edit.text()
        new_text = current[:cursor] + col_name + current[cursor:]
        calc_edit.setText(new_text)
        calc_edit.setFocus()
        calc_edit.setCursorPosition(cursor + len(col_name))
        self.status_label.setText(f"Inserted column: {col_name}")

    # --- Status bar ---
    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready — Open a CSV/Excel file to begin")
        self.status_bar.addWidget(self.status_label)

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith((".csv", ".xlsx", ".xls")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V:
            self._on_paste()
        else:
            super().keyPressEvent(event)

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".csv", ".xlsx", ".xls")):
                self._load_file_direct(path)
                break

    def _load_file_direct(self, path):
        """Load a CSV or Excel file directly (bypasses the import dialog)."""
        try:
            if path.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(path, header=0)
            else:
                df = pd.read_csv(path, header=0)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
            return
        if df is None or df.empty:
            return
        self._after_load(df, path)

    def _after_load(self, df, path=None):
        """Common post-load logic: update state, UI, watcher."""
        self.state.load_dataframe(df)
        self._show_data_table_window()
        self._refresh_columns_ui()
        self._sync_state_from_controls()
        self._redraw()
        self.status_label.setText(
            f"Loaded {len(df)} rows, {len(df.columns)} cols  |  {len(self.state.curves)} curve(s)"
        )
        # Set up file watcher if we have a source path
        if path:
            self._set_source_path(path)

    def _set_source_path(self, path):
        """Track the source file to enable watch & open-in-Excel."""
        if self._source_path:
            try:
                self._file_watcher.removePath(self._source_path)
            except Exception:
                pass
        self._source_path = path
        try:
            self._file_watcher.addPath(path)
        except Exception:
            pass

    def _on_source_file_changed(self, path):
        """File watcher callback: reload when source file changes on disk."""
        try:
            if path.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(path, header=0)
            else:
                df = pd.read_csv(path, header=0)
            self.state.load_dataframe(df)
            self._refresh_columns_ui()
            self._sync_state_from_controls()
            self._redraw()
            self.status_label.setText(f"Reloaded: {os.path.basename(path)} (file changed on disk)")
            # Re-add path (file watcher removes on change)
            self._file_watcher.addPath(path)
        except Exception as e:
            self.status_label.setText(f"Auto-reload failed: {e}")

    def _on_paste(self):
        """Paste tabular data from clipboard (e.g., copied from Excel)."""
        clipboard = QApplication.clipboard().text()
        if not clipboard.strip():
            QMessageBox.warning(self, "Empty Clipboard", "No text data on clipboard.")
            return
        try:
            df = pd.read_csv(io.StringIO(clipboard), sep="\t")
        except Exception:
            try:
                df = pd.read_csv(io.StringIO(clipboard), sep=None, engine="python")
            except Exception as e:
                QMessageBox.critical(self, "Paste Error",
                    f"Could not parse clipboard as tabular data.\n\n{e}")
                return
        if df.empty or len(df.columns) < 2:
            # Try comma-separated
            try:
                df = pd.read_csv(io.StringIO(clipboard))
            except Exception:
                pass
        if df is None or df.empty:
            QMessageBox.warning(self, "Parse Error", "Clipboard data could not be parsed.")
            return
        self._after_load(df, path=None)
        self.status_label.setText(
            f"Pasted {len(df)} rows, {len(df.columns)} cols from clipboard"
        )

    def _on_export_data(self):
        """Export the current dataframe to an Excel or CSV file."""
        if not self.state.has_data:
            QMessageBox.warning(self, "No Data", "No data to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Data", "",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            df = self.state.dataframe
            if path.lower().endswith((".xlsx", ".xls")):
                df.to_excel(path, index=False)
            else:
                df.to_csv(path, index=False)
            self.status_label.setText(f"Data exported: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _on_open_in_excel(self):
        """Open the source file (or export temp file) in Excel."""
        if self._source_path and os.path.exists(self._source_path):
            path = self._source_path
        else:
            # Export current data to a temp file and open it
            if not self.state.has_data:
                QMessageBox.warning(self, "No Data", "Load or paste data first.")
                return
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            self.state.dataframe.to_excel(tmp.name, index=False)
            tmp.close()
            path = tmp.name
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.run(["open", path])
            self.status_label.setText(f"Opened in Excel: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open in Excel: {e}")

    # --- Real-time controls changed ---
    def _on_controls_changed(self):
        self._sync_state_from_controls()
        self._redraw()

    def _sync_state_from_controls(self):
        pc = self.plot_controls
        self.state.title = pc.get_title()
        self.state.subtitle = pc.get_subtitle()
        self.state.x_label = pc.get_x_label()
        self.state.y_label = pc.get_y_label()
        self.state.show_legend = pc.get_show_legend()

        # Sync curves from curve_panel
        configs = self.curve_panel.get_curves_config()
        # Resize state curves to match panel
        while len(self.state.curves) > len(configs):
            self.state.curves.pop()
        while len(self.state.curves) < len(configs):
            self.state.add_curve()
        for i, cfg in enumerate(configs):
            c = self.state.curves[i]
            c.x_col = cfg["x_col"]
            c.y_col = cfg["y_col"]
            c.label = cfg["label"]
            c.color = cfg["color"]

    def _on_add_curve(self):
        self.state.add_curve()
        self._rebuild_curve_rows()
        self._sync_state_from_controls()
        self._redraw()

    def _rebuild_curve_rows(self):
        self.curve_panel.set_curves(self.state.curves)

    def _refresh_columns_ui(self):
        """Refresh column-dependent UI after dataframe changes."""
        self.curve_panel.load_columns(self.state.columns)
        self._rebuild_curve_rows()
        if self._data_table_window:
            self._data_table_window.load_dataframe(self.state.dataframe)
        self.tool_panel.set_summary_targets(self.state.columns, len(self.state.dataframe))

    # --- Slots ---
    def _on_open_file(self):
        from .dialogs.data_import import ImportDataDialog
        dialog = ImportDataDialog(self)
        if dialog.exec() != ImportDataDialog.DialogCode.Accepted:
            return
        df = dialog.get_dataframe()
        if df is None or df.empty:
            return
        path = dialog.path_edit.text()
        self._after_load(df, path)

    def _on_export(self):
        from .dialogs.export import ExportDialog
        dialog = ExportDialog(self)
        if dialog.exec() != ExportDialog.DialogCode.Accepted:
            return
        config = dialog.get_export_config()
        if not config["path"]:
            return
        self.canvas.figure.savefig(
            config["path"], dpi=config["dpi"],
            bbox_inches="tight",
            transparent=config["transparent"],
        )
        self.status_label.setText(f"Exported: {config['path']}")

    def _on_open_fit_window(self, curve):
        """Open a floating FitWindow for a specific curve."""
        curve_id = id(curve)
        if curve_id in self._fit_windows:
            win = self._fit_windows[curve_id]
        else:
            win = FitWindow(curve=curve, all_curves=self.state.curves, parent=self)
            win.fit_requested.connect(lambda cfg: self._on_fit_window_request(win, cfg))
            self._fit_windows[curve_id] = win
        win.show()
        win.raise_()

    def _on_open_analysis_fit(self):
        """Open the standalone analysis FitWindow from menu."""
        if not self.state.has_data:
            QMessageBox.warning(self, "No Data", "Load data first.")
            return
        if self._analysis_fit_win is None:
            self._analysis_fit_win = FitWindow(
                curve=self.state.first_curve,
                all_curves=self.state.curves,
                parent=self,
            )
            self._analysis_fit_win.setWindowTitle("Fit Analysis")
            self._analysis_fit_win.fit_requested.connect(
                lambda cfg: self._on_analysis_fit_requested(self._analysis_fit_win, cfg)
            )
        else:
            # Refresh curves in existing window
            self._analysis_fit_win._all_curves = self.state.curves
        self._analysis_fit_win.show()
        self._analysis_fit_win.raise_()

    def _on_fit_window_request(self, win, cfg):
        """Execute a fit requested from a FitWindow (per-curve or analysis)."""
        if not self.state.has_data:
            return
        from .analysis.fitting import (
            linear_regression, poly_fit, exp_fit,
            linear_regression_row, poly_fit_row, exp_fit_row,
        )
        try:
            fit_type = cfg["fit_type"]
            direction = cfg.get("direction", "column")
            if direction == "row":
                if fit_type == "linear":
                    result = linear_regression_row(self.state.dataframe, cfg["row_index"])
                elif fit_type == "poly":
                    result = poly_fit_row(self.state.dataframe, cfg["row_index"], degree=cfg["degree"])
                elif fit_type == "exp":
                    result = exp_fit_row(self.state.dataframe, cfg["row_index"])
                else:
                    return
            else:
                if fit_type == "linear":
                    result = linear_regression(self.state.dataframe, cfg["x_col"], cfg["y_col"])
                elif fit_type == "poly":
                    result = poly_fit(self.state.dataframe, cfg["x_col"], cfg["y_col"], degree=cfg["degree"])
                elif fit_type == "exp":
                    result = exp_fit(self.state.dataframe, cfg["x_col"], cfg["y_col"])
                else:
                    return
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", str(e))
            return
        result["curve_label"] = cfg.get("curve_label", "")
        result["curve_color"] = cfg.get("curve_color", "")
        self.state.analysis_results = [result]
        self._redraw()
        win.show_results(self._format_fit_result(result))
        self.status_label.setText(f"Fit applied: {cfg.get('curve_label', 'row')} ({fit_type})")

    def _on_analysis_fit_requested(self, win, cfg):
        """Handle fit from the standalone analysis FitWindow (may fit multiple curves)."""
        if not self.state.has_data:
            return
        from .analysis.fitting import (
            linear_regression, poly_fit, exp_fit,
            linear_regression_row, poly_fit_row, exp_fit_row,
        )
        direction = cfg.get("direction", "column")
        if direction == "row":
            try:
                fit_type = cfg["fit_type"]
                if fit_type == "linear":
                    result = linear_regression_row(self.state.dataframe, cfg["row_index"])
                elif fit_type == "poly":
                    result = poly_fit_row(self.state.dataframe, cfg["row_index"], degree=cfg["degree"])
                elif fit_type == "exp":
                    result = exp_fit_row(self.state.dataframe, cfg["row_index"])
                else:
                    return
                result["curve_label"] = f"Row {cfg['row_index']}"
                self.state.analysis_results = [result]
                self._redraw()
                win.show_results(self._format_fit_result(result))
            except Exception as e:
                QMessageBox.critical(self, "Analysis Error", str(e))
        else:
            # Column-wise: one result per curve
            try:
                fit_type = cfg["fit_type"]
                results = []
                curves_to_fit = cfg.get("curves") or []
                if not curves_to_fit and cfg.get("curve_obj"):
                    curves_to_fit = [cfg["curve_obj"]]
                elif not curves_to_fit:
                    curves_to_fit = [c for c in self.state.curves if c.visible]
                for curve in curves_to_fit:
                    if fit_type == "linear":
                        r = linear_regression(self.state.dataframe, curve.x_col, curve.y_col)
                    elif fit_type == "poly":
                        r = poly_fit(self.state.dataframe, curve.x_col, curve.y_col, degree=cfg["degree"])
                    elif fit_type == "exp":
                        r = exp_fit(self.state.dataframe, curve.x_col, curve.y_col)
                    else:
                        continue
                    r["curve_label"] = curve.label or curve.y_col
                    r["curve_color"] = curve.color
                    results.append(r)
                self.state.analysis_results = results
                self._redraw()
                # Show all results in fit window
                texts = [self._format_fit_result(r) for r in results]
                win.show_results("\n".join(texts))
                self.status_label.setText(f"Fit applied: {len(results)} curve(s)")
            except Exception as e:
                QMessageBox.critical(self, "Analysis Error", str(e))

    @staticmethod
    def _format_fit_result(result):
        atype = result.get("type", "")
        direction = result.get("direction", "column")
        clabel = result.get("curve_label", "")
        prefix = f"[{clabel}] " if clabel else ""
        dir_label = f" ({direction})"
        if atype == "linear":
            return (f"{prefix}Linear{dir_label}\n"
                    f"  Slope: {result['slope']:.4f}  Int: {result['intercept']:.4f}\n"
                    f"  R={result['r_value']:.4f}  P={result['p_value']:.4e}")
        elif atype == "polynomial":
            coeffs = " + ".join(f"{c:.4f}x^{i}" for i, c in enumerate(reversed(result['coefficients'])))
            return f"{prefix}Poly d={result['degree']}{dir_label}\n  {coeffs}\n  R2={result['r_squared']:.4f}"
        elif atype == "exponential":
            return (f"{prefix}Exp{dir_label}\n"
                    f"  a={result['a']:.4f}  b={result['b']:.4f}\n"
                    f"  R2={result['r_squared']:.4f}")
        return ""

    def _on_change_plot_type(self, plot_type):
        self.state.plot_type = plot_type
        self._redraw()

    def _on_run_fitting(self, fit_type):
        if not self.state.has_data:
            QMessageBox.warning(self, "No Data", "Load data first.")
            return
        from .analysis.fitting import (
            linear_regression, poly_fit, exp_fit,
            linear_regression_row, poly_fit_row, exp_fit_row,
        )
        try:
            cfg = self.tool_panel.get_fit_config()
            results = []
            if cfg["direction"] == "row":
                if fit_type == "linear":
                    results.append(linear_regression_row(self.state.dataframe, cfg["row_index"]))
                elif fit_type == "poly":
                    results.append(poly_fit_row(self.state.dataframe, cfg["row_index"], degree=cfg["degree"]))
                elif fit_type == "exp":
                    results.append(exp_fit_row(self.state.dataframe, cfg["row_index"]))
                else:
                    return
            else:
                visible = [c for c in self.state.curves if c.visible]
                if not visible:
                    QMessageBox.warning(self, "No Data", "Add at least one visible curve.")
                    return
                for curve in visible:
                    if fit_type == "linear":
                        r = linear_regression(self.state.dataframe, curve.x_col, curve.y_col)
                    elif fit_type == "poly":
                        r = poly_fit(self.state.dataframe, curve.x_col, curve.y_col, degree=cfg["degree"])
                    elif fit_type == "exp":
                        r = exp_fit(self.state.dataframe, curve.x_col, curve.y_col)
                    else:
                        return
                    r["curve_label"] = curve.label or curve.y_col
                    r["curve_color"] = curve.color
                    results.append(r)
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", str(e))
            return
        self.state.analysis_results = results
        self._redraw()
        self._show_analysis_results(results)

    def _on_calculate(self, expression, target, direction="column"):
        if not self.state.has_data:
            QMessageBox.warning(self, "No Data", "Load data first.")
            return
        from .analysis.calculator import evaluate, evaluate_rowwise
        try:
            if direction == "row":
                series = evaluate_rowwise(self.state.dataframe, expression)
            else:
                series = evaluate(self.state.dataframe, expression)
        except Exception as e:
            QMessageBox.critical(self, "Calculator Error", str(e))
            return
        self.state.add_calculated_column(target or expression, series)
        self._refresh_columns_ui()
        self.tool_panel.show_calc_results(
            f"Added column '{self.state.columns[-1]}'\n"
            f"Length: {len(series)}, Mean: {series.mean():.4f}"
        )
        self._redraw()
        self.status_label.setText(f"Calculated [{direction}]: {expression} -> {self.state.columns[-1]}")

    def _on_summarize(self, direction, target):
        if not self.state.has_data:
            QMessageBox.warning(self, "No Data", "Load data first.")
            return
        from .analysis.fitting import summarize_column, summarize_row
        color = self.plot_controls.get_selected_palette_color()
        try:
            if direction == "column":
                result = summarize_column(self.state.dataframe, target)
            else:
                result = summarize_row(self.state.dataframe, int(target))
        except Exception as e:
            QMessageBox.critical(self, "Summarize Error", str(e))
            return
        self.state.add_error_bar_point(
            label=result["label"], x=result["x"], y=result["y"],
            yerr=result["yerr"], color=color,
        )
        self.state.show_error_bars = True
        self.tool_panel.error_bar_toggle.setChecked(True)
        self.tool_panel.show_summary_results(
            f"{result['label']}\n"
            f"Mean: {result['y']:.4f}\n"
            f"Std:  {result['yerr']:.4f}\n"
            f"N:    {result['n']}"
        )
        self._redraw()
        self.status_label.setText(
            f"Summarized: {result['label']} mean={result['y']:.4f} +- {result['yerr']:.4f}"
        )

    def _on_toggle_error_bars(self, show):
        self.state.show_error_bars = show
        self._redraw()

    def _on_run_clustering(self):
        curve = self.state.first_curve
        if not self.state.has_data or curve is None:
            QMessageBox.warning(self, "No Data", "Load data and add at least one curve first.")
            return
        from .analysis.clustering import kmeans
        try:
            cfg = self.tool_panel.get_cluster_config()
            result = kmeans(self.state.dataframe, curve.x_col, curve.y_col,
                           n_clusters=cfg["n_clusters"])
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", str(e))
            return
        self.state.analysis_results = [result]
        self.state.plot_type = "scatter"
        self._redraw()
        self._show_analysis_results([result])

    def _on_elbow_method(self):
        curve = self.state.first_curve
        if not self.state.has_data or curve is None:
            QMessageBox.warning(self, "No Data", "Load data and add at least one curve first.")
            return
        from .analysis.clustering import elbow_method
        try:
            result = elbow_method(self.state.dataframe, curve.x_col, curve.y_col)
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", str(e))
            return
        self.state.analysis_results = [result]
        self.state.plot_type = "line"
        self._redraw()

    def _on_about(self):
        QMessageBox.about(self, "About GraphX",
                          "<h3>GraphX</h3>"
                          "<p>Graphing and data analysis application.</p>"
                          "<p>Built with PyQt6, matplotlib, pandas, scipy, and scikit-learn.</p>")

    # --- Redraw dispatch ---
    def _redraw(self):
        if not self.state.has_data or not self.state.curves:
            self.canvas.clear()
            self.canvas.draw_idle()
            return

        df = self.state.dataframe
        ptype = self.state.plot_type
        visible_curves = [c for c in self.state.curves if c.visible]

        from .plots.line import line_plot, scatter_plot
        from .plots.bar import bar_chart, histogram
        from .plots.categorical import pie_chart
        from .plots.surface import surface_3d

        plot_fns = {
            "line": (line_plot, False),
            "scatter": (scatter_plot, False),
            "bar": (bar_chart, False),
            "histogram": (histogram, False),
            "pie": (pie_chart, False),
            "surface_3d": (surface_3d, True),
        }

        plot_fn, is_3d = plot_fns.get(ptype, (line_plot, False))

        self.canvas._is_3d = is_3d
        self.canvas.clear()
        target = self.canvas.axes_3d if is_3d else self.canvas.axes

        try:
            for curve in visible_curves:
                kwargs = {"color": curve.color}
                if ptype == "histogram":
                    kwargs["bins"] = 20
                elif ptype == "surface_3d":
                    kwargs["cmap"] = "viridis"
                label = curve.label or curve.y_col
                if ptype not in ("pie", "histogram", "surface_3d"):
                    kwargs["label"] = label
                plot_fn(target, df, curve.x_col, curve.y_col, **kwargs)
        except Exception as e:
            self.status_label.setText(f"Plot error: {e}")
            return

        # Titles and labels
        if self.state.title:
            self.canvas.figure.suptitle(self.state.title, fontsize=13, fontweight="bold")
        if self.state.subtitle:
            target.set_title(self.state.subtitle, fontsize=10, loc="center", pad=12)
        if self.state.x_label:
            target.set_xlabel(self.state.x_label)
        if self.state.y_label:
            target.set_ylabel(self.state.y_label)
        if self.state.show_legend and ptype not in ("pie", "histogram", "surface_3d"):
            target.legend()

        self._draw_analysis_overlay(target, ptype)
        self._draw_error_bars(target)

        self.canvas.draw_idle()
        n_eb = len(self.state.error_bar_points) if self.state.show_error_bars else 0
        self.status_label.setText(
            f"Plot: {ptype}  |  {len(visible_curves)} curve(s)  |  {n_eb} error bar(s)"
        )

    def _draw_analysis_overlay(self, axes, plot_type):
        results = self.state.analysis_results
        if not results:
            return

        import numpy as np
        for idx, ar in enumerate(results):
            atype = ar.get("type")
            dash_color = FIT_DASH_COLORS[idx % len(FIT_DASH_COLORS)]

            if atype in ("linear", "polynomial", "exponential") and "fitted_fn" in ar:
                if ar.get("direction") == "row":
                    x_line = np.linspace(0, ar.get("row_index", 0) + 5, 200)
                    y_line = ar["fitted_fn"](x_line)
                    label = f"{atype} fit (row)"
                else:
                    curve_label = ar.get("curve_label", f"curve {idx}")
                    curve_color = ar.get("curve_color")
                    # Find matching curve to get x data
                    df = self.state.dataframe
                    curve = None
                    for c in self.state.curves:
                        if (c.label or c.y_col) == curve_label or c.color == curve_color:
                            curve = c
                            break
                    if curve is None and self.state.curves:
                        curve = self.state.curves[idx % len(self.state.curves)]
                    if curve is None:
                        continue
                    xdata = df[curve.x_col]
                    x_line = np.linspace(xdata.min(), xdata.max(), 200)
                    y_line = ar["fitted_fn"](x_line)
                    label = f"{atype} fit ({curve_label})"
                axes.plot(x_line, y_line, "--", color=dash_color, linewidth=2, label=label)

            elif atype == "kmeans":
                labels = ar["labels"]
                centroids = ar["centroids"]
                curve = self.state.first_curve
                if curve is None:
                    continue
                df = self.state.dataframe
                xdata = df[curve.x_col].values
                ydata = df[curve.y_col].values
                axes.scatter(xdata, ydata, c=labels, cmap="tab10", zorder=2)
                axes.scatter(centroids[:, 0], centroids[:, 1], c="red", marker="X", s=200,
                            edgecolors="black", linewidths=1, label="Centroids", zorder=3)

            elif atype == "elbow":
                axes.plot(ar["k_values"], ar["inertias"], "o-", color="blue")
                axes.set_xlabel("Number of clusters (k)")
                axes.set_ylabel("Inertia")
                axes.set_title("Elbow Method for Optimal k")
                if ar.get("optimal_k"):
                    axes.axvline(x=ar["optimal_k"], color="red", linestyle="--",
                               label=f'Optimal k = {ar["optimal_k"]}')
            if self.state.show_legend:
                axes.legend()

    def _draw_error_bars(self, axes):
        if not self.state.show_error_bars:
            return
        for eb in self.state.error_bar_points:
            axes.errorbar(
                eb.x, eb.y, yerr=eb.yerr, fmt="o",
                color=eb.color, capsize=5, capthick=1.5,
                markersize=8, label=eb.label,
            )
        if self.state.show_legend and self.state.error_bar_points:
            axes.legend()

    def _show_analysis_results(self, results):
        if not results:
            return
        lines = []
        for idx, result in enumerate(results):
            atype = result.get("type", "")
            direction = result.get("direction", "column")
            clabel = result.get("curve_label", f"#{idx}")
            if atype in ("linear", "polynomial", "exponential"):
                dir_label = f" ({direction})"
                if atype == "linear":
                    lines.append(
                        f"[{clabel}] Linear{dir_label}\n"
                        f"  Slope: {result['slope']:.4f}  "
                        f"Int: {result['intercept']:.4f}\n"
                        f"  R={result['r_value']:.4f}  P={result['p_value']:.4e}"
                    )
                elif atype == "polynomial":
                    coeffs = " + ".join(
                        f"{c:.4f}x^{i}" for i, c in enumerate(reversed(result['coefficients']))
                    )
                    lines.append(
                        f"[{clabel}] Poly d={result['degree']}{dir_label}\n"
                        f"  {coeffs}\n  R2={result['r_squared']:.4f}"
                    )
                elif atype == "exponential":
                    lines.append(
                        f"[{clabel}] Exp{dir_label}\n"
                        f"  a={result['a']:.4f} b={result['b']:.4f}\n"
                        f"  R2={result['r_squared']:.4f}"
                    )
            elif atype == "kmeans":
                lines.append(f"K-Means (k={result['n_clusters']}) Inertia: {result['inertia']:.4f}")
            elif atype == "elbow":
                lines.append(f"Elbow Method Optimal k = {result.get('optimal_k', '?')}")
        text = "\n".join(lines)
        if results[0]["type"] in ("kmeans", "elbow"):
            self.tool_panel.show_cluster_results(text)
        else:
            self.tool_panel.show_fit_results(text)
