from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QDockWidget,
    QFileDialog, QMessageBox, QLabel, QScrollArea, QApplication,
    QComboBox, QPushButton,
)
from PyQt6.QtGui import QAction, QActionGroup, QDragEnterEvent, QDropEvent, QKeyEvent
from PyQt6.QtCore import Qt, QFileSystemWatcher, QTimer
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
import pandas as pd
import os
import subprocess
import io
import tempfile

from .state import PlotState
from .canvas import MplCanvas
from .widgets.plot_controls import PlotControlsWidget, CurvePanelWidget
from .widgets.tool_panel import ToolPanelWidget
from .dialogs.fit_window import FitWindow
from .excel_sync import ExcelSync

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
        self._temp_excel_path = None  # temp copy opened in Excel
        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.fileChanged.connect(self._on_source_file_changed)
        self._sheet_combo = None
        # Directory watcher — detects temp-file changes without opening file handles
        self._temp_dir_watcher = QFileSystemWatcher()
        self._temp_dir_watcher.directoryChanged.connect(self._on_temp_dir_changed)
        self._poll_mtime = 0
        # Use the system temp directory to avoid OneDrive / cloud-sync locks
        self._temp_dir = tempfile.gettempdir()
        self._temp_dir_watcher.addPath(self._temp_dir)
        self._cleanup_old_temp_files()
        self.excel_sync = ExcelSync()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_dock_widgets()
        self._setup_status_bar()
        self.setWindowTitle("GraphX")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

    # --- Temp file helpers ---
    def _cleanup_old_temp_files(self):
        """Remove leftover temp files from previous sessions."""
        import glob
        try:
            for f in glob.glob(os.path.join(self._temp_dir, "graphx_*")):
                try:
                    os.unlink(f)
                except Exception:
                    pass
        except Exception:
            pass

    def _arm_polling(self):
        """Record the current mtime after creating/opening a temp file."""
        if self._temp_excel_path and os.path.exists(self._temp_excel_path):
            self._poll_mtime = os.path.getmtime(self._temp_excel_path)

    def _disarm_polling(self):
        """Forget the current temp file."""
        self._poll_mtime = 0

    def _on_temp_dir_changed(self, _path):
        """Directory watcher callback: reload if the temp file's mtime changed."""
        if not self._temp_excel_path or not os.path.exists(self._temp_excel_path):
            return
        try:
            mtime = os.path.getmtime(self._temp_excel_path)
            if mtime != self._poll_mtime:
                self._poll_mtime = mtime
                self._reload_from_temp()
        except Exception:
            pass

    def _sync_temp_file(self, reload_excel=True):
        """Write all sheets to the temp file. If reload_excel, close & reopen in Excel."""
        self.excel_sync.sync(self._temp_excel_path, self.state.sheets, reload_excel)
        if self._temp_excel_path and os.path.exists(self._temp_excel_path):
            self._poll_mtime = os.path.getmtime(self._temp_excel_path)

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
        sync_action = QAction("&Sync to Excel", self)
        sync_action.setShortcut("Ctrl+Shift+S")
        sync_action.triggered.connect(self._on_sync_to_excel)
        file_menu.addAction(sync_action)
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

        # Sheet switcher
        sheet_bar = QWidget()
        sheet_layout = QHBoxLayout(sheet_bar)
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        sheet_layout.setSpacing(3)
        self._sheet_combo = QComboBox()
        self._sheet_combo.setMinimumWidth(150)
        self._sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        sheet_layout.addWidget(self._sheet_combo, 1)
        add_sheet_btn = QPushButton("+")
        add_sheet_btn.setFixedWidth(28)
        add_sheet_btn.setToolTip("Add empty sheet")
        add_sheet_btn.clicked.connect(self._on_add_sheet)
        sheet_layout.addWidget(add_sheet_btn)
        sidebar_layout.addWidget(sheet_bar)

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

    def _open_temp_in_excel(self):
        """Save current dataframe to a temp .xlsx and open it in Excel."""
        if not self.state.has_data:
            return
        try:
            # Clean up previous temp file
            if self._temp_excel_path and os.path.exists(self._temp_excel_path):
                try:
                    os.unlink(self._temp_excel_path)
                except Exception:
                    pass
            # Write all sheets to a temp file in trusted dir
            tmp = tempfile.NamedTemporaryFile(
                suffix=".xlsx", delete=False, prefix="graphx_",
                dir=self._temp_dir)
            tmp.close()  # release handle so ExcelWriter can open it
            with pd.ExcelWriter(tmp.name, engine="openpyxl") as writer:
                for name, sdf in self.state.sheets.items():
                    sdf.to_excel(writer, sheet_name=name, index=False)
            self._temp_excel_path = tmp.name
            self._arm_polling()
            if os.name == "nt":
                os.startfile(self._temp_excel_path)
            else:
                subprocess.run(["open", self._temp_excel_path])
            self.status_label.setText("Data opened in Excel — edit & save to update GraphX")
        except Exception as e:
            QMessageBox.warning(self, "Excel Error", f"Could not open Excel: {e}")

    def _open_existing_in_excel(self, path):
        """Open an existing temp file in Excel (used for dragged/dropped files)."""
        try:
            if self._temp_excel_path and os.path.exists(self._temp_excel_path):
                try:
                    os.unlink(self._temp_excel_path)
                except Exception:
                    pass
            self._temp_excel_path = path
            self._arm_polling()
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.run(["open", path])
            self.status_label.setText("Data opened in Excel — edit & save to update GraphX")
        except Exception as e:
            QMessageBox.warning(self, "Excel Error", f"Could not open Excel: {e}")

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
        """Copy the dropped file to a temp folder, then load the editable copy."""
        import shutil
        ext = os.path.splitext(path)[1]
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, prefix="graphx_",
                dir=self._temp_dir)
            tmp.close()
            shutil.copy2(path, tmp.name)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Could not copy file: {e}")
            return
        try:
            if path.lower().endswith((".xlsx", ".xls")):
                with pd.ExcelFile(tmp.name) as xls:
                    sheets = {}
                    for name in xls.sheet_names:
                        sheets[name] = pd.read_excel(tmp.name, sheet_name=name, header=0)
                self.state.load_sheets(sheets)
            else:
                df = pd.read_csv(tmp.name, header=0)
                if df is None or df.empty:
                    return
                self.state.load_dataframe(df)
            self._after_load(None, tmp.name)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
            return

    def _after_load(self, df, path=None):
        """Common post-load logic: update state, UI, watcher, open in Excel.
        *df* may be a DataFrame or a dict of {sheet_name: DataFrame}."""
        try:
            if df is not None:
                if isinstance(df, dict):
                    self.state.load_sheets(df)
                else:
                    self.state.load_dataframe(df)
            if not self.state.sheets:
                return
            self._rebuild_sheet_combo()
            self._refresh_columns_ui()
            self._sync_state_from_controls()
            self._redraw()
            dff = self.state.dataframe
            ns = len(self.state.sheets)
            if dff is not None:
                self.status_label.setText(
                    f"{ns} sheet(s) | {len(dff)} rows, {len(dff.columns)} cols  |  {len(self.state.curves)} curve(s)"
                )
            if path and "graphx_" in os.path.basename(path):
                self._open_existing_in_excel(path)
            else:
                self._open_temp_in_excel()
                if path:
                    self._set_source_path(path)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

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

    def _rebuild_sheet_combo(self):
        """Refresh the sheet combo to match state."""
        if self._sheet_combo is None:
            return
        self._sheet_combo.blockSignals(True)
        self._sheet_combo.clear()
        self._sheet_combo.addItems(self.state.sheet_names)
        if self.state.active_sheet:
            self._sheet_combo.setCurrentText(self.state.active_sheet)
        self._sheet_combo.blockSignals(False)

    def _on_sheet_changed(self, name):
        if name and name != self.state.active_sheet:
            self.state.set_active_sheet(name)
            self._refresh_columns_ui()
            self._sync_state_from_controls()
            self._redraw()
            self._rebuild_sheet_combo()

    def _on_add_sheet(self):
        import pandas as pd
        name = f"Sheet{len(self.state.sheets) + 1}"
        while name in self.state.sheets:
            name = f"Sheet{int(name.replace('Sheet', '')) + 1}"
        self.state.add_sheet(name, pd.DataFrame())
        self._rebuild_sheet_combo()
        self._sheet_combo.setCurrentText(name)
        self._sync_temp_file(reload_excel=True)

    def _on_source_file_changed(self, path):
        """File watcher callback: Excel uses safe-save (delete+rename), so we
        delay 500ms to let the new file land before reading."""
        QTimer.singleShot(500, lambda p=path: self._do_reload_file(p))

    def _do_reload_file(self, path):
        try:
            if path == self._temp_excel_path:
                self._reload_from_temp()
            else:
                if path.lower().endswith((".xlsx", ".xls")):
                    with pd.ExcelFile(path) as xls:
                        sheets = {n: pd.read_excel(path, sheet_name=n, header=0)
                                  for n in xls.sheet_names}
                    self.state.load_sheets(sheets)
                else:
                    df = pd.read_csv(path, header=0)
                    self.state.load_dataframe(df)
                self._rebuild_sheet_combo()
                self._refresh_columns_ui()
                self._sync_state_from_controls()
                self._redraw()
                dff = self.state.dataframe
                if dff is not None:
                    self.status_label.setText(
                        f"Reloaded: {os.path.basename(path)} ({len(dff)}r x {len(dff.columns)}c)"
                    )
                self._file_watcher.addPath(path)
        except Exception as e:
            self.status_label.setText(f"Auto-reload failed: {e}")

    def _reload_from_temp(self):
        """Reload data from the temp Excel file (edited by user in Excel)."""
        path = self._temp_excel_path
        if not path or not os.path.exists(path):
            return
        try:
            if path.lower().endswith((".xlsx", ".xls")):
                with pd.ExcelFile(path) as xls:
                    for name in xls.sheet_names:
                        df = pd.read_excel(path, sheet_name=name, header=0)
                        df = self.state._normalize_columns(df)
                        if name in self.state.sheets:
                            self.state.sheets[name] = df
                        else:
                            self.state.add_sheet(name, df)
            else:
                df = pd.read_csv(path, header=0)
                self.state.dataframe = df

            # Clean up curves referencing columns that no longer exist
            valid_cols = set(self.state.columns)
            self.state.curves = [c for c in self.state.curves
                                 if c.x_col in valid_cols and c.y_col in valid_cols]
            if not self.state.curves and self.state.columns:
                self.state.add_curve()

            self._rebuild_sheet_combo()
            self._refresh_columns_ui()
            self._sync_state_from_controls()
            self._redraw()

            dff = self.state.dataframe
            if dff is not None:
                self.status_label.setText(
                    f"Reloaded from Excel ({len(dff)}r x {len(dff.columns)}c)"
                )
            self._poll_mtime = os.path.getmtime(path)
        except Exception as e:
            self.status_label.setText(f"Reload failed: {e}")
            self._poll_mtime = 0  # force retry on next poll

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
        """Open the data in Excel (source file or temp copy)."""
        if self._source_path and os.path.exists(self._source_path):
            path = self._source_path
        elif self._temp_excel_path and os.path.exists(self._temp_excel_path):
            path = self._temp_excel_path
        else:
            QMessageBox.warning(self, "No Data", "Load or paste data first.")
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.run(["open", path])
            self.status_label.setText(f"Opened in Excel: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open in Excel: {e}")

    def _on_sync_to_excel(self):
        """Write current sheets to the temp file and reload in Excel via COM."""
        if not self._temp_excel_path:
            QMessageBox.warning(self, "No Excel", "Open data in Excel first (File → Open in Excel).")
            return
        if not self.state.has_data:
            return
        try:
            self._sync_temp_file(reload_excel=True)
            self.status_label.setText("Synced to Excel")
        except PermissionError:
            QMessageBox.warning(
                self, "File Locked",
                "Could not release the file lock. Close the file in Excel and try again."
            )
        except Exception as e:
            QMessageBox.critical(self, "Sync Error", str(e))

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
        nrows = len(self.state.dataframe) if self.state.dataframe is not None else 0
        self.tool_panel.set_summary_targets(self.state.columns, nrows)
        if self.state.has_data:
            self.tool_panel.set_calc_completions(self.state.sheets, self.state.active_sheet)

    # --- Slots ---
    def _on_open_file(self):
        from .dialogs.data_import import ImportDataDialog
        dialog = ImportDataDialog(self)
        if dialog.exec() != ImportDataDialog.DialogCode.Accepted:
            return
        path = dialog.path_edit.text()
        sheets = dialog.get_sheets()
        if sheets:
            self._after_load(sheets, path)
        else:
            df = dialog.get_dataframe()
            if df is None or df.empty:
                return
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
            win.extrapolation_requested.connect(lambda cfg: self._on_extrapolation_requested(win, cfg))
            win.save_fit_params_requested.connect(lambda: self._on_save_fit_params(win))
            win.save_predictions_requested.connect(lambda: self._on_save_predictions(win))
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
            self._analysis_fit_win.extrapolation_requested.connect(
                lambda cfg: self._on_extrapolation_requested(self._analysis_fit_win, cfg)
            )
            self._analysis_fit_win.save_fit_params_requested.connect(
                lambda: self._on_save_fit_params(self._analysis_fit_win)
            )
            self._analysis_fit_win.save_predictions_requested.connect(
                lambda: self._on_save_predictions(self._analysis_fit_win)
            )
        else:
            # Refresh curves in existing window
            self._analysis_fit_win._all_curves = self.state.curves
            self._analysis_fit_win.curve = self.state.first_curve
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

    def _on_extrapolation_requested(self, win, cfg):
        """Predict y for given x values using current fit results."""
        if not self.state.analysis_results:
            QMessageBox.warning(self, "No Fit", "Run a fit first before extrapolating.")
            return
        from .analysis.fitting import extrapolate
        x_values = cfg["x_values"]
        all_points = []
        for ar in self.state.analysis_results:
            if ar.get("fitted_fn"):
                try:
                    pts = extrapolate(ar, x_values)
                    for p in pts:
                        p["label"] = ar.get("curve_label", "")
                        p["color"] = ar.get("curve_color", "#e41a1c")
                    all_points.extend(pts)
                except Exception:
                    pass
        self.state.extrapolation_points = all_points
        self._redraw()
        win.show_extrapolation(all_points)

    def _on_save_fit_params(self, win):
        """Save fit parameters (slope, intercept, R², etc.) to a 'Fit Results' sheet."""
        results = self.state.analysis_results
        if not results:
            QMessageBox.warning(self, "No Fit", "Run a fit first.")
            return
        rows = []
        for ar in results:
            if ar.get("type") not in ("linear", "polynomial", "exponential"):
                continue
            row = {
                "curve": ar.get("curve_label", ""),
                "type": ar.get("type", ""),
            }
            for key in ("slope", "intercept", "r_value", "p_value",
                        "r_squared", "a", "b", "degree"):
                if key in ar:
                    row[key] = ar[key]
            rows.append(row)
        if not rows:
            return
        pdf = pd.DataFrame(rows)
        sheet_name = "Fit Results"
        if sheet_name in self.state.sheets:
            existing = self.state.sheets[sheet_name]
            pdf = pd.concat([existing, pdf], ignore_index=True)
            self.state.sheets[sheet_name] = pdf
        else:
            self.state.add_sheet(sheet_name, pdf)
        self._rebuild_sheet_combo()
        self.status_label.setText(f"Fit params saved to sheet '{sheet_name}'")
        self._sync_temp_file(reload_excel=True)

    def _on_save_predictions(self, win):
        """Save extrapolation predictions to a new sheet."""
        pts = self.state.extrapolation_points
        if not pts:
            QMessageBox.warning(self, "No Predictions", "Run extrapolation first.")
            return
        pdf = pd.DataFrame([{"x_pred": p["x"], "y_pred": p["y"]} for p in pts])
        base = "Predictions"
        name = base
        i = 1
        while name in self.state.sheets:
            i += 1
            name = f"{base}_{i}"
        self.state.add_sheet(name, pdf)
        self._rebuild_sheet_combo()
        self.status_label.setText(f"Predictions saved to sheet '{name}'")
        self._sync_temp_file(reload_excel=True)

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
        from .analysis.calculator import evaluate_cross_sheet, evaluate_rowwise
        try:
            if direction == "row":
                series = evaluate_rowwise(self.state.dataframe, expression)
            else:
                series = evaluate_cross_sheet(
                    self.state.sheets, self.state.active_sheet, expression)
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
        # Auto-sync the new column to Excel so the user sees it immediately
        try:
            self._sync_temp_file(reload_excel=True)
        except Exception:
            pass

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
            if (hasattr(self.canvas.figure, '_suptitle')
                    and self.canvas.figure._suptitle is not None):
                self.canvas.figure._suptitle.set_text("")
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

            # Titles and labels
            if self.state.title:
                self.canvas.figure.suptitle(self.state.title, fontsize=13, fontweight="bold")
            elif (hasattr(self.canvas.figure, '_suptitle')
                  and self.canvas.figure._suptitle is not None):
                self.canvas.figure._suptitle.set_text("")
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
        except Exception as e:
            self.status_label.setText(f"Plot error: {e}")

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

        # Extrapolation points
        for ep in self.state.extrapolation_points:
            axes.scatter(
                ep["x"], ep["y"], marker="D", s=100,
                color=ep.get("color", "#e41a1c"),
                edgecolors="black", linewidths=1.5,
                zorder=10,
                label=f"pred ({ep.get('label', '')}): x={ep['x']:.3f}, y={ep['y']:.3f}",
            )
        if self.state.extrapolation_points and self.state.show_legend:
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
