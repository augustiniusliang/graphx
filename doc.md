# GraphX — Application Documentation

## Overview

GraphX is a PyQt6-based desktop application for interactive data visualization and analysis. It supports importing CSV and Excel files, plotting data with various chart types (line, scatter, bar, histogram, pie, 3D surface), performing curve fitting (linear, polynomial, exponential), K-Means clustering, evaluating custom expressions across columns and sheets, and exporting results — all with live Excel synchronization via COM automation.

---

## Table of Contents

1. [Entry Point: `main.py`](#entry-point-mainpy)
2. [Package: `graphx`](#package-graphx)
   - [`app.py` — `GraphXApp`](#graphxapppy--graphxapp)
   - [`canvas.py` — `MplCanvas`](#graphxcanvaspy--mplcanvas)
   - [`excel_sync.py` — `ExcelSync`](#graphxexcel_syncpy--excelsync)
   - [`state.py` — `CurveConfig`, `ErrorBarPoint`, `PlotState`](#graphxstatepy--curveconfig-errorbarpoint-plotstate)
3. [Subpackage: `graphx.analysis`](#subpackage-graphxanalysis)
   - [`calculator.py`](#graphxanalysiscalculatorpy)
   - [`clustering.py`](#graphxanalysisclusteringpy)
   - [`fitting.py`](#graphxanalysisfittingpy)
4. [Subpackage: `graphx.dialogs`](#subpackage-graphxdialogs)
   - [`data_import.py` — `ImportDataDialog`](#graphxdialogsdata_importpy--importdatadialog)
   - [`export.py` — `ExportDialog`](#graphxdialogsexportpy--exportdialog)
   - [`fit_window.py` — `FitWindow`](#graphxdialogsfit_windowpy--fitwindow)
5. [Subpackage: `graphx.plots`](#subpackage-graphxplots)
   - [`bar.py` — `bar_chart`, `histogram`](#graphxplotsbarpy--bar_chart-histogram)
   - [`categorical.py` — `pie_chart`, `heatmap`](#graphxplotscategoricalpy--pie_chart-heatmap)
   - [`line.py` — `line_plot`, `scatter_plot`](#graphxplotslinepy--line_plot-scatter_plot)
   - [`surface.py` — `surface_3d`, `contour`](#graphxplotssurfacepy--surface_3d-contour)
6. [Subpackage: `graphx.widgets`](#subpackage-graphxwidgets)
   - [`data_table.py`](#graphxwidgetsdata_tablepy)
   - [`expression_highlighter.py` — `ExpressionHighlighter`](#graphxwidgetsexpression_highlighterpy--expressionhighlighter)
   - [`plot_controls.py`](#graphxwidgetsplot_controlspy)
   - [`tool_panel.py`](#graphxwidgetstool_panelpy)
7. [Tests](#tests)
8. [Architecture Summary](#architecture-summary)

---

## Entry Point: `main.py`

### Function: `main()`

```python
def main() -> None
```

Application entry point. Configures matplotlib for CJK (Chinese/Japanese/Korean) font support, then creates and runs the PyQt6 application.

**Behavior:**
1. Calls `matplotlib.rc()` to set:
   - `font.sans-serif`: `Microsoft YaHei`, `SimHei`, `WenQuanYi Micro Hei`, `WenQuanYi Zen Hei`, `Noto Sans CJK SC`, plus standard matplotlib fallbacks.
   - `font.family`: `sans-serif`.
   - `axes.unicode_minus`: `False` (avoids Unicode minus rendering issues with CJK fonts).
2. Creates `QApplication(sys.argv)`.
3. Instantiates `GraphXApp`, the main application window.
4. Calls `app.show()`.
5. Enters the Qt event loop via `app.exec()`.
6. Calls `sys.exit()` with the application's return code.

---

## Package: `graphx`

### `graphx/__init__.py`

Re-exports the `GraphXApp` class:

```python
from .app import GraphXApp
```

---

### `graphx/app.py` — `GraphXApp`

**Module-level constant:**

```python
FIT_DASH_COLORS = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
    "#ff7f00", "#a65628", "#f781bf", "#999999",
]
```

Eight hex color strings cycled through for fit overlay lines on the plot.

---

#### Class: `GraphXApp(QMainWindow)`

The primary application window. Owns all application state (`PlotState`), the matplotlib canvas (`MplCanvas`), the Excel synchronizer (`ExcelSync`), all UI panels and dock widgets, and mediates all user interactions. Acts as the central coordinator between data model, view, and analysis modules.

**Constructor:**

##### `__init__(self)`

Initialization order:
1. Creates `PlotState()` as the central data model.
2. Creates `MplCanvas(self)`.
3. Initializes `_data_table_window = None` (lazy-created floating data table).
4. Initializes `_fit_windows = {}` (dict mapping curve `id()` → `FitWindow`).
5. Initializes `_analysis_fit_win = None` (lazy-created menu-triggered FitWindow).
6. Initializes `_source_path = None` (tracked source file for watcher).
7. Initializes `_temp_excel_path = None` (temp copy opened in Excel).
8. Creates `QFileSystemWatcher` (`_file_watcher`) connected to `_on_source_file_changed`.
9. Creates `_sheet_combo = None`.
10. Creates a second `QFileSystemWatcher` (`_temp_dir_watcher`) connected to `_on_temp_dir_changed` for directory-level change detection.
11. Initializes `_poll_mtime = 0` for debouncing temp file changes.
12. Sets `_temp_dir = tempfile.gettempdir()` (uses system temp to avoid OneDrive/cloud-sync locks).
13. Adds `_temp_dir` to `_temp_dir_watcher`.
14. Calls `_cleanup_old_temp_files()` to remove leftover session files.
15. Creates `ExcelSync()`.
16. Calls UI setup methods: `_setup_menu_bar()`, `_setup_toolbar()`, `_setup_central_widget()`, `_setup_dock_widgets()`, `_setup_status_bar()`.
17. Sets window title to `"GraphX"`, default geometry to `1200×800`, and enables drag-and-drop via `setAcceptDrops(True)`.

---

**Drag & Drop / Keyboard:**

##### `dragEnterEvent(self, event: QDragEnterEvent)`

Accepts drag events for files with `.csv`, `.xlsx`, or `.xls` extensions.

##### `dropEvent(self, event: QDropEvent)`

Handles file drops. Extracts the first local file URL and passes it to `_load_file_direct()`.

##### `keyPressEvent(self, event: QKeyEvent)`

Intercepts `Ctrl+V` to trigger `_on_paste()`. All other keys delegate to the parent class.

---

**Private Methods — Temp File & Polling:**

##### `_cleanup_old_temp_files(self)`

Removes all files matching `graphx_*` in the system temp directory via `glob.glob()` + `os.unlink()`. Silently ignores any errors.

##### `_arm_polling(self)`

Records the current mtime of `_temp_excel_path` as `_poll_mtime`. Used as a baseline so the directory watcher ignores writes that the application itself performed.

##### `_disarm_polling(self)`

Resets `_poll_mtime` to `0`.

##### `_on_temp_dir_changed(self, _path)`

Directory watcher callback. If `_temp_excel_path` exists and its mtime differs from `_poll_mtime`, calls `_reload_from_temp()` and updates the stored mtime.

##### `_sync_temp_file(self, reload_excel=True)`

Writes all state sheets to the temp Excel file via `ExcelSync.sync()`. If `reload_excel` is `True`, Excel reloads the workbook. Updates `_poll_mtime` after writing.

---

**Private Methods — Menu Bar, Toolbar, Central Widget, Docks, Status Bar:**

##### `_setup_menu_bar(self)`

Builds the full menu bar:

| Menu | Action | Shortcut | Slot |
|------|--------|----------|------|
| **File** | Open… | Ctrl+O | `_on_open_file` |
| | Paste from Clipboard | Ctrl+V | `_on_paste` |
| | — | | (separator) |
| | Export Plot… | Ctrl+E | `_on_export` |
| | Export Data… | Ctrl+Shift+E | `_on_export_data` |
| | — | | (separator) |
| | Open in Excel | | `_on_open_in_excel` |
| | Sync to Excel | Ctrl+Shift+S | `_on_sync_to_excel` |
| | — | | (separator) |
| | Exit | Ctrl+Q | `self.close` |
| **Plot** | Line | | `_on_change_plot_type("line")` |
| | Scatter | | `_on_change_plot_type("scatter")` |
| | Bar | | `_on_change_plot_type("bar")` |
| | Histogram | | `_on_change_plot_type("histogram")` |
| | Pie | | `_on_change_plot_type("pie")` |
| | 3D Surface | | `_on_change_plot_type("surface_3d")` |
| **View** | Curve Panel | | `_on_toggle_curve_panel` (checkable, default checked) |
| **Analysis** | Fitting… | Ctrl+F | `_on_open_analysis_fit` |
| | — | | (separator) |
| | K-Means Clustering | | `_on_run_clustering` |
| | K-Means Elbow Method | | `_on_elbow_method` |
| **Help** | About | | `_on_about` |

The Plot menu uses a `QActionGroup` (exclusive) so only one plot type is checked at a time.

##### `_setup_toolbar(self)`

Creates an empty `QToolBar("Main Toolbar")` — reserved for future use.

##### `_setup_central_widget(self)`

Constructs the main layout:
1. **Canvas area** (`QWidget` + `QVBoxLayout`):
   - `NavigationToolbar2QT` (matplotlib toolbar) at top.
   - `MplCanvas` below it.
2. **Sidebar** (`QWidget`, fixed width 300px, `QVBoxLayout`):
   - Sheet switcher row: `QComboBox` (`_sheet_combo`, min width 150px) + `QPushButton` (`+`, width 28px, tooltip "Add empty sheet").
   - `PlotControlsWidget` (plot appearance + color picker).
   - `ToolPanelWidget` (analysis tabs).
3. **Splitter:** `QSplitter(Qt.Horizontal)` with canvas area (stretch 1) and sidebar (stretch 0).

Signal connections:
- `_sheet_combo.currentTextChanged` → `_on_sheet_changed`
- `add_sheet_btn.clicked` → `_on_add_sheet`
- `plot_controls.changed` → `_on_controls_changed`
- `tool_panel.fit_requested` → `_on_run_fitting`
- `tool_panel.cluster_requested` → `_on_run_clustering`
- `tool_panel.elbow_requested` → `_on_elbow_method`
- `tool_panel.calculate_requested` → `_on_calculate`
- `tool_panel.summarize_requested` → `_on_summarize`
- `tool_panel.view_error_bars_toggled` → `_on_toggle_error_bars`

##### `_setup_dock_widgets(self)`

Creates the "Curves" dock widget:
1. Creates `CurvePanelWidget` (`self.curve_panel`).
2. Wraps it in `QDockWidget("Curves", self)` docked on the left.
3. Allows docking on left and right sides only.
4. Connects signals:
   - `curve_panel.add_curve_requested` → `_on_add_curve`
   - `curve_panel.changed` → `_on_controls_changed`
   - `curve_panel.fit_requested` → `_on_open_fit_window`
   - `plot_controls.color_changed` → `curve_panel.apply_color_to_all`

##### `_on_toggle_curve_panel(self, visible: bool)`

Shows or hides the curves dock widget via `curve_dock.setVisible(visible)`.

##### `_setup_status_bar(self)`

Creates a `QStatusBar` with a `QLabel` (`self.status_label`) showing the initial text `"Ready — Open a CSV/Excel file to begin"`.

---

**Private Methods — File Loading:**

##### `_load_file_direct(self, path: str)`

Loads a file dropped or opened by URL:
1. Copies the original file to the system temp directory with a `graphx_` prefix using `shutil.copy2()`.
2. For Excel files (`.xlsx`/`.xls`): reads all sheets via `pd.ExcelFile`, then calls `state.load_sheets(sheets)`.
3. For CSV files: reads via `pd.read_csv(header=0)`, then calls `state.load_dataframe(df)`.
4. Calls `_after_load(None, tmp.name)`.

On failure, shows a `QMessageBox.critical`.

##### `_after_load(self, df, path=None)`

Common post-load handler for all data ingestion paths:
1. If `df` is a dict (multi-sheet), calls `state.load_sheets(df)`. If it's a DataFrame, calls `state.load_dataframe(df)`.
2. If state has no sheets after loading, returns early.
3. Calls `_rebuild_sheet_combo()`.
4. Calls `_refresh_columns_ui()`.
5. Calls `_sync_state_from_controls()`.
6. Calls `_redraw()`.
7. Updates `status_label` with sheet count, row count, column count, and curve count.
8. If `path` contains `"graphx_"`, calls `_open_existing_in_excel(path)`. Otherwise calls `_open_temp_in_excel()` and then `_set_source_path(path)` if a path was given.
9. On any exception, shows `QMessageBox.critical`.

##### `_set_source_path(self, path: str)`

Registers a file path with `_file_watcher` for auto-reload detection. Removes any previously watched path first.

##### `_on_source_file_changed(self, path: str)`

Debounced file watcher callback. Waits 500ms via `QTimer.singleShot` (Excel uses safe-save: delete + rename), then calls `_do_reload_file(path)`.

##### `_do_reload_file(self, path: str)`

Reloads data from a modified file:
1. If `path` matches `_temp_excel_path`, delegates to `_reload_from_temp()`.
2. Otherwise, re-reads the source file (Excel or CSV), updates state, rebuilds UI, redraws, and updates the status label.
3. Re-adds the path to the file watcher (required after each change notification on some platforms).

##### `_reload_from_temp(self)`

Reloads data from the temp Excel file after user edits in Excel:
1. For Excel: reads all sheets, updates existing sheets in state, adds new sheets. CSV: updates the active sheet.
2. Filters out curves whose x_col or y_col no longer exist in the dataframe.
3. If no curves remain and columns exist, auto-creates one.
4. Rebuilds UI and redraws.
5. Updates `_poll_mtime` to the file's current mtime.
6. On failure, resets `_poll_mtime` to `0` to force retry on next poll.

##### `_on_open_file(self)`

Opens the `ImportDataDialog`:
1. Creates the dialog and executes it modally.
2. On acceptance, reads the file path, gets sheets (multi-sheet Excel) or dataframe (CSV), and passes to `_after_load()`.

##### `_on_paste(self)`

Parses tabular data from the system clipboard:
1. Reads clipboard text via `QApplication.clipboard().text()`.
2. Tries parsing as tab-separated (`pd.read_csv(sep="\t")`).
3. Falls back to `pd.read_csv(sep=None, engine="python")` for auto-detection.
4. If the result has fewer than 2 columns, tries comma-separated.
5. Calls `_after_load(df, path=None)` on success.
6. Shows a warning on failure.

---

**Private Methods — Excel Integration:**

##### `_open_temp_in_excel(self)`

Opens the current data in Excel via a temp file:
1. Cleans up any previous temp file.
2. Creates a `NamedTemporaryFile` with `prefix="graphx_"`, `suffix=".xlsx"` in `_temp_dir`.
3. Writes all state sheets via `pd.ExcelWriter(engine="openpyxl")`.
4. Stores the temp path and arms polling.
5. Opens in the default application: `os.startfile(path)` on Windows, `subprocess.run(["open", path])` on macOS.
6. Updates the status label.

##### `_open_existing_in_excel(self, path: str)`

Opens an existing temp file (from drag-and-drop) in Excel:
1. Cleans up any previous temp file.
2. Stores the new path and arms polling.
3. Opens via `os.startfile()` (Windows) or `subprocess.run(["open", path])` (macOS).

##### `_on_open_in_excel(self)`

Opens data in Excel. Prefers `_source_path` if available, falls back to `_temp_excel_path`. Shows a warning if neither exists.

##### `_on_sync_to_excel(self)`

Syncs current state sheets to the temp Excel file and reloads in Excel via COM:
1. Validates that `_temp_excel_path` exists.
2. Calls `_sync_temp_file(reload_excel=True)`.
3. Handles `PermissionError` with a specific warning about file locks.

---

**Private Methods — Sheet Management:**

##### `_rebuild_sheet_combo(self)`

Refreshes the sheet selection combo:
1. Blocks signals, clears items.
2. Adds items from `state.sheet_names`.
3. Sets current text to `state.active_sheet`.
4. Unblocks signals.

##### `_on_sheet_changed(self, name: str)`

Handles sheet selection change:
1. If `name` is non-empty and differs from `state.active_sheet`, calls `state.set_active_sheet(name)`.
2. Refreshes columns UI, syncs controls, redraws, and rebuilds the combo.

##### `_on_add_sheet(self)`

Adds a new empty sheet:
1. Generates a name as `"Sheet{n}"` where n = `len(state.sheets) + 1`, incrementing if the name exists.
2. Calls `state.add_sheet(name, pd.DataFrame())`.
3. Rebuilds the combo, selects the new sheet, and syncs to Excel.

---

**Private Methods — Curve Management:**

##### `_on_add_curve(self)`

Adds a curve via `state.add_curve()`, rebuilds curve rows UI, syncs controls to state, and redraws.

##### `_rebuild_curve_rows(self)`

Calls `curve_panel.set_curves(state.curves)`.

##### `_refresh_columns_ui(self)`

Updates column-dependent UI:
1. Calls `curve_panel.load_columns(state.columns)`.
2. Calls `_rebuild_curve_rows()`.
3. Calls `tool_panel.set_summary_targets(state.columns, nrows)` where `nrows = len(state.dataframe)`.
4. If state has data, calls `tool_panel.set_calc_completions(state.sheets, state.active_sheet)`.

---

**Private Methods — Plot Controls & State Sync:**

##### `_on_controls_changed(self)`

Slot for any control change: calls `_sync_state_from_controls()` then `_redraw()`.

##### `_sync_state_from_controls(self)`

Copies UI values into `PlotState`:
- `state.title`, `state.subtitle`, `state.x_label`, `state.y_label`, `state.show_legend` from `plot_controls`.
- Syncs curves: reads configs from `curve_panel.get_curves_config()`, resizes `state.curves` to match (popping/adding as needed), then updates each curve's `x_col`, `y_col`, `label`, `color`.

---

**Private Methods — Fitting & Analysis:**

##### `_on_open_fit_window(self, curve)`

Opens or raises a floating `FitWindow` for a specific curve:
1. Checks `_fit_windows` cache by `id(curve)`. If exists, shows and raises.
2. Otherwise, creates new `FitWindow(curve=curve, all_curves=state.curves, parent=self)`, caches it, connects signals (`fit_requested`, `extrapolation_requested`, `save_fit_params_requested`, `save_predictions_requested`), and shows.
3. Windows are not cleaned up from cache on close (they persist for the session).

##### `_on_open_analysis_fit(self)`

Opens the standalone fitting window from the Analysis menu:
1. Validates state has data.
2. On first call, creates `FitWindow(curve=state.first_curve, all_curves=state.curves, parent=self)` with title `"Fit Analysis"`, connects all four signals.
3. On subsequent calls, refreshes `_all_curves` and `curve` attributes directly and shows/raises the existing window.

##### `_on_fit_window_request(self, win, cfg: dict)`

Executes a fit requested from a per-curve `FitWindow`:
- **cfg keys:** `fit_type` (`"linear"`, `"poly"`, `"exp"`), `direction` (`"column"` or `"row"`), `degree`, `x_col`, `y_col`, `row_index`, `curve_label`, `curve_color`.
- **Column mode:** calls `linear_regression`, `poly_fit`, or `exp_fit`.
- **Row mode:** calls `linear_regression_row`, `poly_fit_row`, or `exp_fit_row`.
- Stores the single result in `state.analysis_results = [result]`.
- Annotates result with `curve_label` and `curve_color`.
- Redraws and shows formatted results via `win.show_results()`.
- On error, shows `QMessageBox.critical`.

##### `_on_extrapolation_requested(self, win, cfg: dict)`

Predicts y values for user-provided x values:
1. Validates that `state.analysis_results` is non-empty.
2. For each analysis result that has a `fitted_fn`, calls `extrapolate(ar, x_values)`.
3. Annotates each point with `label` and `color` from the analysis result.
4. Stores all points in `state.extrapolation_points`.
5. Redraws and shows results via `win.show_extrapolation(all_points)`.

##### `_on_save_fit_params(self, win)`

Saves fit parameters to a "Fit Results" sheet:
1. Validates that `state.analysis_results` is non-empty.
2. Builds a list of row dicts, each containing `curve`, `type`, and whichever of `slope`, `intercept`, `r_value`, `p_value`, `r_squared`, `a`, `b`, `degree` are present.
3. Creates a DataFrame from the rows.
4. If "Fit Results" sheet already exists, concatenates with `pd.concat([existing, pdf])`. Otherwise, adds a new sheet.
5. Rebuilds the sheet combo, updates status, and syncs to Excel.

##### `_on_save_predictions(self, win)`

Saves extrapolation predictions to a new sheet:
1. Validates that `state.extrapolation_points` is non-empty.
2. Creates a DataFrame with columns `x_pred` and `y_pred`.
3. Adds a new sheet named `"Predictions"` (or `"Predictions_2"`, `"Predictions_3"`, etc. if the name is taken).
4. Rebuilds the sheet combo, updates status, and syncs to Excel.

##### `_on_analysis_fit_requested(self, win, cfg: dict)`

Handles fitting from the standalone analysis `FitWindow`:
- **cfg keys:** `fit_type`, `direction`, `degree`, `row_index`, optionally `curves` (list of `CurveConfig`), `curve_obj`.
- **Row mode:** single fit via `*_row()` functions, labels result as `"Row {row_index}"`.
- **Column mode:** iterates over selected curves (from `cfg["curves"]`, `cfg["curve_obj"]`, or all visible curves as fallback), runs the specified fit on each, and aggregates results.
- Stores all results in `state.analysis_results`.
- Formats and displays all results joined by newlines.
- On error, shows `QMessageBox.critical`.

##### `_format_fit_result(result: dict) -> str` *(static method)*

Formats a fit result dictionary into a human-readable multi-line string:

- **Linear:** `"[{label}] Linear ({direction})\n  Slope: {slope:.4f}  Int: {intercept:.4f}\n  R={r_value:.4f}  P={p_value:.4e}"`
- **Polynomial:** `"[{label}] Poly d={degree} ({direction})\n  {coeffs}\n  R2={r_squared:.4f}"`
- **Exponential:** `"[{label}] Exp ({direction})\n  a={a:.4f}  b={b:.4f}\n  R2={r_squared:.4f}"`

The `[{label}]` prefix is omitted if `curve_label` is empty.

##### `_on_run_fitting(self, fit_type: str)`

Runs fitting from the tool panel's Fitting tab:
1. Gets fit config from `tool_panel.get_fit_config()`.
2. **Row mode:** runs the specified row-wise fit on the configured row index.
3. **Column mode:** fits all visible curves. Warns if none are visible.
4. Stores results in `state.analysis_results`, redraws, and displays via `_show_analysis_results()`.
5. On error, shows `QMessageBox.critical`.

##### `_on_calculate(self, expression: str, target: str, direction="column")`

Evaluates a calculator expression:
1. **Column mode:** calls `evaluate_cross_sheet(state.sheets, state.active_sheet, expression)`.
2. **Row mode:** calls `evaluate_rowwise(state.dataframe, expression)`.
3. Adds the result as a new column via `state.add_calculated_column(target or expression, series)`.
4. Refreshes columns UI, shows calc results (new column name, length, mean), redraws, and auto-syncs to Excel.
5. On error, shows `QMessageBox.critical`.

##### `_on_summarize(self, direction: str, target: str)`

Computes summary statistics (mean ± std) and adds an error bar point:
1. Gets the selected color from `plot_controls.get_selected_palette_color()`.
2. **Column mode:** calls `summarize_column(df, target)`.
3. **Row mode:** calls `summarize_row(df, int(target))`.
4. Appends an `ErrorBarPoint` to state via `state.add_error_bar_point()`.
5. Enables error bar display (`state.show_error_bars = True`), checks the toggle button.
6. Shows results in the summarize tab and redraws.
7. On error, shows `QMessageBox.critical`.

##### `_on_toggle_error_bars(self, show: bool)`

Sets `state.show_error_bars = show` and redraws.

##### `_on_run_clustering(self)`

Runs K-Means clustering:
1. Validates state has data and `first_curve` exists.
2. Gets `n_clusters` from `tool_panel.get_cluster_config()`.
3. Calls `kmeans(df, curve.x_col, curve.y_col, n_clusters)`.
4. Stores the single result in `state.analysis_results`.
5. Switches plot type to `"scatter"` and redraws.
6. Shows results via `_show_analysis_results()`.

##### `_on_elbow_method(self)`

Runs the elbow method for optimal K:
1. Validates state has data and `first_curve` exists.
2. Calls `elbow_method(df, curve.x_col, curve.y_col)`.
3. Stores the result in `state.analysis_results`.
4. Switches plot type to `"line"` and redraws.
5. Results are drawn by `_draw_analysis_overlay()`.

##### `_on_about(self)`

Shows About dialog: `"GraphX — Graphing and data analysis application. Built with PyQt6, matplotlib, pandas, scipy, and scikit-learn."`

---

**Private Methods — Export:**

##### `_on_export(self)`

Opens `ExportDialog`, gets config (`path`, `dpi`, `transparent`), saves the figure via `canvas.figure.savefig()`, and updates status.

##### `_on_export_data(self)`

Opens a `QFileDialog.getSaveFileName` filtered for Excel/CSV, then saves via `df.to_excel()` or `df.to_csv()`.

---

**Private Methods — Redraw:**

##### `_on_change_plot_type(self, plot_type: str)`

Sets `state.plot_type` to the given type and calls `_redraw()`. Valid types: `"line"`, `"scatter"`, `"bar"`, `"histogram"`, `"pie"`, `"surface_3d"`.

##### `_redraw(self)`

The core redraw dispatcher:
1. If state has no data or no curves, clears the canvas (including suptitle text if present) and calls `draw_idle()`, then returns.
2. Gets the active dataframe, plot type, and visible curves.
3. Looks up the plot function and `is_3d` flag from a dict mapping:
   - `"line"` → `(line_plot, False)`
   - `"scatter"` → `(scatter_plot, False)`
   - `"bar"` → `(bar_chart, False)`
   - `"histogram"` → `(histogram, False)`
   - `"pie"` → `(pie_chart, False)`
   - `"surface_3d"` → `(surface_3d, True)`
4. Sets `canvas._is_3d` and clears the canvas.
5. For each visible curve, calls `plot_fn(target, df, curve.x_col, curve.y_col, **kwargs)` where kwargs includes `color` and, depending on plot type, `label`, `bins`, or `cmap`.
6. Sets title (via `figure.suptitle`), subtitle (via `axes.set_title`), axis labels, and legend from state.
7. Calls `_draw_analysis_overlay(target, ptype)`.
8. Calls `_draw_error_bars(target)`.
9. Calls `canvas.draw_idle()` and updates the status bar with plot type, curve count, and error bar count.

##### `_draw_analysis_overlay(self, axes, plot_type: str)`

Draws analysis overlays from `state.analysis_results`:

- **Fit results** (`type` in `"linear"`, `"polynomial"`, `"exponential"`): Draws the fitted function as a dashed line. For column-wise fits, uses the matching curve's X data range. For row-wise fits, generates x range from 0 to `row_index + 5`. Colors cycle through `FIT_DASH_COLORS`.

- **K-Means results** (`type == "kmeans"`): Draws data points colored by cluster label (scatter, `cmap="tab10"`), and centroids as red X markers (`marker="X", s=200, edgecolors="black"`).

- **Elbow results** (`type == "elbow"`): Draws the inertia-vs-k curve as a blue line with circle markers. Adds axis labels ("Number of clusters (k)", "Inertia") and title ("Elbow Method for Optimal k"). Draws a vertical dashed red line at the optimal k value.

- **Extrapolation points** (`state.extrapolation_points`): Draws diamond markers (`marker="D", s=100`) with black edges at each prediction point, labeled with x and y values.

If `state.show_legend` is `True`, calls `axes.legend()`.

##### `_draw_error_bars(self, axes)`

If `state.show_error_bars` is `True`, iterates over `state.error_bar_points` and draws each with `axes.errorbar()` (marker `"o"`, capsize 5, markersize 8).

##### `_show_analysis_results(self, results: list[dict])`

Formats analysis results as text and displays in the appropriate tool panel tab:
- Fit results → `tool_panel.show_fit_results(text)`.
- K-Means / elbow results → `tool_panel.show_cluster_results(text)`.

---

### `graphx/canvas.py` — `MplCanvas`

#### Class: `MplCanvas(FigureCanvasQTAgg)`

A PyQt6-compatible matplotlib canvas widget wrapping `matplotlib.figure.Figure`.

**Constructor:**

##### `__init__(self, parent=None, width=5, height=4, dpi=100)`

1. Creates `Figure(figsize=(width, height), dpi=dpi)` with `constrained_layout=True`.
2. Creates a 2D subplot: `figure.add_subplot(111)` → `self.axes`.
3. Initializes `self.axes_3d = None` and `self._is_3d = False`.
4. Calls parent `FigureCanvasQTAgg.__init__`.
5. Sets the Qt parent and size policy to `Expanding` in both directions.

**Methods:**

##### `clear(self)`

Clears the canvas for replotting, reusing existing axes when possible to avoid matplotlib constrained_layout instability:

- **If `_is_3d`:** calls `axes_3d.cla()` if it exists; otherwise clears the figure, sets `axes = None`, and creates a new 3D subplot.
- **If not `_is_3d`:** calls `axes.cla()` if it exists; otherwise clears the figure, sets `axes_3d = None`, and creates a new 2D subplot.

##### `draw_plot(self, plot_fn, df, x_col, y_col, is_3d=False, **kwargs)`

Sets `_is_3d = is_3d`, calls `clear()`, then calls `plot_fn(target, df, x_col, y_col, **kwargs)` where `target` is `axes_3d` (for 3D) or `axes` (for 2D). Finishes with `draw_idle()`.

##### `save(self, path: str, dpi=300)`

Saves the figure to a file via `figure.savefig(path, dpi=dpi, bbox_inches="tight")`.

---

### `graphx/excel_sync.py` — `ExcelSync`

**Module-level docstring:**
> *Excel synchronisation via COM automation. Writes dataframe sheets to a temp .xlsx file and reloads the workbook in Excel without visual flicker (ScreenUpdating suppressed, active sheet preserved).*

#### Class: `ExcelSync`

Manages Excel synchronization via Windows COM automation. Writes pandas DataFrames to `.xlsx` files and reloads them in an open Excel instance with minimal visual disruption.

**Methods:**

##### `sync(self, path: str, sheets: dict[str, pd.DataFrame], reload_excel: bool = True)`

**Public API.** The main entry point:
1. Initializes COM via `_init_com()`.
2. If `reload_excel` is `True`:
   - Closes the workbook at `path` in Excel (if open), recording the active sheet name.
   - Writes all sheets via `pd.ExcelWriter(engine="openpyxl")`.
   - Reopens the workbook in Excel, restoring the previously active sheet.
3. If `reload_excel` is `False`: writes sheets without touching Excel.

##### `_init_com()` *(static method)*

Initializes COM threading via `pythoncom.CoInitialize()`.

##### `_get_excel_app(self)`

Returns the running Excel Application COM object, or starts a new one via `win32com.client.Dispatch("Excel.Application")`.

##### `_find_workbook(self, excel, path: str)`

Finds an open workbook whose `FullName` matches `path`. Returns the Workbook COM object or `None`.

##### `_close_workbook(self, path: str) -> str | None`

Closes the workbook at `path` in Excel. Suppresses `ScreenUpdating`, records the active sheet name, closes (saving), and restores `ScreenUpdating`. Returns the previously active sheet name or `None`.

##### `_open_workbook(self, path: str, active_sheet: str | None = None)`

Opens `path` in Excel, activates the given sheet, re-enables `ScreenUpdating`, and makes Excel visible.

---

### `graphx/state.py` — `CurveConfig`, `ErrorBarPoint`, `PlotState`

**Module-level constant:**

```python
DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]
```

Ten hex color strings used as the default color cycle for curves.

---

#### Class: `CurveConfig` *(dataclass)*

Configuration for a single plotted curve.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x_col` | `str` | `""` | Column name for X-axis data. |
| `y_col` | `str` | `""` | Column name for Y-axis data. |
| `label` | `str` | `""` | Legend label. |
| `color` | `str` | `"#1f77b4"` | Hex color string. |
| `visible` | `bool` | `True` | Whether the curve is drawn. |

---

#### Class: `ErrorBarPoint` *(dataclass)*

Represents a single error bar data point.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `label` | `str` | `""` | Legend label. |
| `x` | `object` | `None` | X-axis position (numeric or categorical). |
| `y` | `float` | `0.0` | Y-axis value (mean). |
| `yerr` | `float` | `0.0` | Y-axis error (standard deviation). |
| `color` | `str` | `"#d62728"` | Hex color string. |

---

#### Class: `PlotState` *(dataclass)*

Central application state container — the single source of truth.

**Data Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sheets` | `dict[str, pd.DataFrame]` | `{}` | All data sheets keyed by name. |
| `active_sheet` | `str` | `""` | Currently selected sheet name. |
| `curves` | `list[CurveConfig]` | `[]` | All curve configurations. |
| `plot_type` | `str` | `"line"` | Active plot type: `"line"`, `"scatter"`, `"bar"`, `"histogram"`, `"pie"`, `"surface_3d"`. |
| `title` | `str` | `""` | Plot title. |
| `subtitle` | `str` | `""` | Plot subtitle. |
| `x_label` | `str` | `""` | X-axis label. |
| `y_label` | `str` | `""` | Y-axis label. |
| `show_legend` | `bool` | `False` | Whether legend is displayed. |
| `analysis_results` | `list[dict]` | `[]` | Unified list of analysis result dicts (fit, kmeans, elbow). |
| `error_bar_points` | `list[ErrorBarPoint]` | `[]` | Error bar data points. |
| `show_error_bars` | `bool` | `False` | Whether error bars are drawn. |
| `extrapolation_points` | `list[dict]` | `[]` | Extrapolation prediction points (`{"x": float, "y": float, ...}`). |

**Properties:**

##### `dataframe` → `pd.DataFrame | None`

Returns the DataFrame for the active sheet: `self.sheets.get(self.active_sheet)`.

**Setter:** `dataframe(self, df)` — Assigns `df` (normalized) to the active sheet if one exists, or calls `add_sheet("Data", df)`.

##### `columns` → `list[str]`

Returns column names of the active dataframe as strings. Returns `[]` if no dataframe.

**Setter:** No-op (columns are always derived from the dataframe).

##### `has_data` → `bool`

`True` if the active sheet has a non-empty, non-None dataframe.

##### `sheet_names` → `list[str]`

Returns `list(self.sheets.keys())`.

##### `first_curve` → `CurveConfig | None`

Returns `self.curves[0]` if curves exist, else `None`.

**Methods:**

##### `_normalize_columns(df: pd.DataFrame) -> pd.DataFrame` *(static)*

Ensures all column names are strings: `df.columns = [str(c) for c in df.columns]`.

##### `add_sheet(self, name: str, df: pd.DataFrame) -> str`

Adds a sheet. Disambiguates the name by appending `_2`, `_3`, etc. if the name already exists. Sets as active if it's the first sheet. Returns the final (possibly disambiguated) name.

##### `remove_sheet(self, name: str)`

Removes a sheet. Refuses if it would leave zero sheets. If removing the active sheet, activates the first remaining sheet.

##### `rename_sheet(self, old: str, new: str)`

Renames a sheet (no-op if `old` doesn't exist, `new` exists, or names are equal). Preserves the dataframe and updates `active_sheet` if needed.

##### `set_active_sheet(self, name: str)`

Sets the active sheet and clears `analysis_results` and `extrapolation_points` (since they are sheet-specific).

##### `load_dataframe(self, df: pd.DataFrame)`

Legacy entry point for single-dataframe loading:
1. Adds a sheet named `"Data"` and sets it as active.
2. Auto-creates one curve: X = first column, Y = first numeric column (excluding X). Color cycles via `DEFAULT_COLORS[len(curves) % len(DEFAULT_COLORS)]`.

##### `load_sheets(self, sheets: dict[str, pd.DataFrame])`

Loads multiple named sheets:
1. Clears existing sheets.
2. Adds each sheet via `add_sheet()`.
3. Sets active to the first sheet.
4. Clears curves and auto-creates one curve with `DEFAULT_COLORS[0]`.

##### `add_curve(self)`

Adds a new curve:
- No-op if there are no columns.
- Avoids duplicate colors by checking `used_colors` and preferring an unused `DEFAULT_COLORS` entry. Falls back to round-robin.
- X = first column, Y = first numeric column excluding X.

##### `add_calculated_column(self, name: str, series: pd.Series)`

Adds a column to the active sheet's dataframe. Generates a default name like `"calc_3"` if `name` is empty.

##### `add_error_bar_point(self, label, x, y, yerr, color="#d62728")`

Appends a new `ErrorBarPoint` to `error_bar_points`.

##### `clear_error_bar_points(self)`

Clears `error_bar_points`.

---

## Subpackage: `graphx.analysis`

### `graphx/analysis/calculator.py`

Safe expression evaluator using `eval()` with `__builtins__` disabled. Supports column-wise, cross-sheet, and row-wise evaluation.

**Module-level constant:**

```python
_ALLOWED_NAMES = {
    "np": np, "log": np.log, "log10": np.log10, "log2": np.log2,
    "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs, "pow": np.power,
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "arcsin": np.arcsin, "arccos": np.arccos, "arctan": np.arctan,
    "pi": np.pi, "e": np.e,
}
```

---

#### Function: `_sanitize(name: str) -> str`

Converts a string to a valid Python identifier: replaces non-alphanumeric/non-underscore characters with `_`, prepends `_` if starting with a digit, returns `"_col"` if empty.

---

#### Function: `evaluate(df: pd.DataFrame, expression: str) -> pd.Series`

Safely evaluates an expression using dataframe columns and numpy functions.

1. Builds a namespace from `_ALLOWED_NAMES` plus each column exposed both as a sanitized name and (if valid) its original name.
2. Replaces column names in the expression with sanitized versions (longest-first to avoid partial matches).
3. Evaluates with `eval(expression, {"__builtins__": {}}, ns)`.
4. Returns a `pd.Series` aligned to the dataframe index. Handles scalar, ndarray, and Series results.

Raises `ValueError` on any evaluation error or unsupported result type.

---

#### Function: `evaluate_cross_sheet(sheets: dict[str, pd.DataFrame], active_sheet: str, expression: str) -> pd.Series`

Evaluates an expression with cross-sheet column references:

**Syntax:** Bare column names refer to the active sheet. `SheetName.ColumnName` refers to another sheet.

1. Exposes all columns from all sheets as `_{sanitized_sheet}_{sanitized_col}` variables.
2. Replaces `SheetName.ColumnName` patterns in the expression with the corresponding safe variable names. Handles both raw sheet names and sanitized versions.
3. Replaces bare column names (from the active sheet only) using regex with lookahead/lookbehind to avoid matching substrings in already-replaced cross-sheet variable names.
4. Evaluates and returns a `pd.Series` aligned to the active sheet's index.

---

#### Function: `evaluate_rowwise(df: pd.DataFrame, expression: str) -> pd.Series`

Evaluates an expression row-wise. Each row's numeric columns are exposed as a numpy array `r`. The expression should reference `r` (e.g., `"np.mean(r)"`, `"r[0] + r[1]"`).

Raises `ValueError` if there are no numeric columns.

---

### `graphx/analysis/clustering.py`

#### Function: `kmeans(df: pd.DataFrame, x_col: str, y_col: str, n_clusters: int = 3, random_state: int = 42) -> dict`

Runs scikit-learn `KMeans` on two columns. Drops NaN rows before fitting.

**Returns:** `dict` with keys `type` (`"kmeans"`), `labels` (ndarray), `centroids` (ndarray of shape (k, 2)), `inertia` (float), `n_clusters` (int).

---

#### Function: `elbow_method(df: pd.DataFrame, x_col: str, y_col: str, max_k: int = 10) -> dict`

Runs K-Means for k = 1..max_k and determines the optimal k as the point furthest from the line connecting the first and last points on the inertia curve (perpendicular distance method).

**Returns:** `dict` with keys `type` (`"elbow"`), `k_values` (list of ints), `inertias` (list of floats), `optimal_k` (int).

---

### `graphx/analysis/fitting.py`

**Module-level helpers:**

- `_get_row_series(df, row_index)` — Extracts numeric values from a row (skipping non-numeric columns). Returns `(x, values)` where `x = np.arange(len(values))`. Raises `ValueError` if the row has no numeric values.
- `_exp_model(x, a, b)` — Exponential model: `a * exp(b * x)`.

---

#### Column-wise fitting functions

##### `linear_regression(df, x_col, y_col) -> dict`

Linear regression via `scipy.stats.linregress`. Returns `type` (`"linear"`), `slope`, `intercept`, `r_value`, `p_value`, `std_err`, `fitted_fn` (callable), `direction` (`"column"`).

##### `poly_fit(df, x_col, y_col, degree=2) -> dict`

Polynomial regression via `numpy.polyfit`. Returns `type` (`"polynomial"`), `coefficients` (list), `degree`, `r_squared`, `fitted_fn` (`np.poly1d`), `direction` (`"column"`).

##### `exp_fit(df, x_col, y_col) -> dict`

Exponential fit via `scipy.optimize.curve_fit`. Returns `type` (`"exponential"`), `a`, `b`, `r_squared`, `fitted_fn` (callable), `direction` (`"column"`).

---

#### Row-wise fitting functions

Each extracts numeric values from a single row via `_get_row_series()` and applies the same fitting algorithm. Return dicts are identical to their column-wise counterparts except `direction` is `"row"` and an additional `row_index` key is included.

- `linear_regression_row(df, row_index) -> dict`
- `poly_fit_row(df, row_index, degree=2) -> dict`
- `exp_fit_row(df, row_index) -> dict`

---

#### Function: `extrapolate(fit_result: dict, x_values: list[float]) -> list[dict]`

Predicts y for given x values using `fit_result["fitted_fn"]`. Returns `[{"x": float, "y": float}, ...]`. Raises `ValueError` if no fitted function is available.

---

#### Function: `summarize_column(df: pd.DataFrame, col: str) -> dict`

Computes mean and std (ddof=1) for a column. Returns `type` (`"summary"`), `label`, `x` (column name), `y` (mean), `yerr` (std), `n` (count), `direction` (`"column"`).

---

#### Function: `summarize_row(df: pd.DataFrame, row_index: int) -> dict`

Computes mean and std across a row's numeric columns. Returns same structure as `summarize_column` but with `direction` (`"row"`), `x` set to the row's index label, label as `"Row {label}"`, and `row_index`.

---

## Subpackage: `graphx.dialogs`

### `graphx/dialogs/data_import.py` — `ImportDataDialog`

#### Class: `ImportDataDialog(QDialog)`

A modal dialog for browsing, previewing, and importing CSV or Excel data.

**Constructor:**

##### `__init__(self, parent=None)`

Builds the dialog (700×500):
1. **File path row:** read-only `QLineEdit` (`self.path_edit`) + "Browse…" `QPushButton`.
2. **Options row:** Sheet `QComboBox` (disabled for CSV) + Header row `QSpinBox` (default 0).
3. **Preview table:** `QTableWidget` showing first 100 rows.
4. **Buttons:** OK / Cancel (`QDialogButtonBox`).

**Methods:**

##### `_on_browse(self)`

Opens a file dialog for CSV/XLSX/XLS files. Sets the path and calls `_preview(path)`.

##### `_preview(self, path: str)`

Reads the file:
- **Excel:** Uses `pd.ExcelFile` context manager, reads all sheets with the configured header row. Populates `_sheets` dict and enables the sheet combo. Sets `_df` to the first sheet.
- **CSV:** Reads with `pd.read_csv(header=...)`. Disables sheet combo, sets `_sheets = None`.
- Shows the first 100 rows in the preview table via `_show_preview()`.
- On error, shows `QMessageBox.critical`.

##### `_on_sheet_changed(self, name: str)`

Switches `_df` to the selected sheet and refreshes the preview.

##### `_show_preview(self, df: pd.DataFrame)`

Fills the preview table: sets row/column counts, headers, cell values (str, empty for None), and resizes columns to contents.

##### `_on_accept(self)`

Accepts the dialog if `_df` is not None. Otherwise shows a warning.

##### `get_dataframe(self) -> pd.DataFrame`

Returns the currently selected DataFrame.

##### `get_sheets(self) -> dict | None`

Returns `{name: DataFrame}` for multi-sheet Excel, or `None` for CSV.

---

### `graphx/dialogs/export.py` — `ExportDialog`

#### Class: `ExportDialog(QDialog)`

A modal dialog for configuring plot export (format, DPI, transparency).

**Constructor:**

##### `__init__(self, parent=None)`

Builds the dialog:
1. Format `QComboBox`: `"PNG (*.png)"`, `"SVG (*.svg)"`, `"PDF (*.pdf)"`.
2. DPI `QSpinBox`: 72–1200, default 300.
3. Transparent background `QCheckBox`.
4. File path `QLineEdit` + "Browse…" button.
5. OK / Cancel buttons.

**Methods:**

##### `_on_browse(self)`

Opens a save dialog filtered by the selected format.

##### `get_export_config(self) -> dict`

Returns `{"path": str, "format": str, "dpi": int, "transparent": bool}`.

---

### `graphx/dialogs/fit_window.py` — `FitWindow`

#### Class: `FitWindow(QWidget)`

**Module-level docstring:**
> *Floating fit window for per-curve or menu-triggered fitting. Supports both column-wise and row-wise fitting with direction toggle.*

**Signals:**

| Signal | Emitted Type | When |
|--------|-------------|------|
| `fit_requested` | `dict` | "Apply Fit" clicked |
| `extrapolation_requested` | `dict` | "Predict" clicked |
| `save_fit_params_requested` | (none) | "Save Fit Params" clicked |
| `save_predictions_requested` | (none) | "Save Predictions" clicked |

**Constructor:**

##### `__init__(self, curve=None, all_curves=None, parent=None)`

- `curve`: The specific `CurveConfig` this window is for (or `None` for the standalone analysis window).
- `all_curves`: List of all `CurveConfig` objects for the curve selector.
- Uses `parent.windowFlags()` so the window inherits the parent's window flags for proper floating behavior.
- Window size: 380×420.
- Calls `_build_ui()`.

**Methods:**

##### `_build_ui(self)`

Creates the UI in sections:

1. **Curve selection** (`QGroupBox`):
   - If `len(all_curves) > 1`: Shows a `QComboBox` with "All visible curves" plus each curve's label. Pre-selects the current curve if set.
   - If a single curve is set: Shows an info label with `"X: {x_col}  |  Y: {y_col}"`.
   - Otherwise: Shows `"Select curve(s) to fit"` and sets window title to `"Fit Analysis"`.

2. **Direction** (`QGroupBox`): `QComboBox` (By Column / By Row) + `QSpinBox` (Row 0–9999, hidden in column mode).

3. **Fit type:** `QComboBox` (Linear / Polynomial / Exponential).

4. **Polynomial degree:** `QSpinBox` (1–10, default 2) in a horizontal layout.

5. **Apply Fit:** `QPushButton` → `_on_apply()`.

6. **Results:** Read-only `QTextEdit`.

7. **Extrapolation** (`QGroupBox`):
   - `QLineEdit` with placeholder `"e.g. 1.5, 2.0, 3.0"` (Enter triggers extrapolation).
   - "Predict" `QPushButton`.
   - Result `QLabel` (monospace font).

8. **Save to Sheet** (`QGroupBox`):
   - "Save Fit Params" button → emits `save_fit_params_requested`.
   - "Save Predictions" button → emits `save_predictions_requested`.

##### `_get_selected_curves(self) -> list`

Returns the list of curves to operate on:
- If ≤1 curves available: returns `[self.curve]` (or `[]` if None).
- If combo shows "All visible curves": returns all visible curves.
- Otherwise: returns the curve matching the selected label.

##### `_on_apply(self)`

Builds a base config dict (`fit_type`, `degree`, `direction`, `row_index`) and emits `fit_requested`:
- **Row mode:** Emits one signal with `curves` key added.
- **Column mode:** Emits one signal per curve, each with `x_col`, `y_col`, `curve_label`, `curve_color`, and `curve_obj`.

##### `show_results(self, text: str)`

Sets the results text view content (replaces existing).

##### `append_results(self, text: str)`

Appends text to the results view (newline-separated from existing content).

##### `_on_extrapolate(self)`

Parses comma-separated floats from the input, validates, and emits `extrapolation_requested` with `{"x_values": [float, ...]}`.

##### `show_extrapolation(self, points: list[dict])`

Displays extrapolation results as `"x={x:.4f} -> y={y:.4f}"` lines.

---

## Subpackage: `graphx.plots`

All plot functions share the same interface: `fn(axes, df, x_col, y_col, **kwargs)`. Extra keyword arguments (`label`, `color`, `cmap`, etc.) are passed through to the underlying matplotlib function.

### `graphx/plots/bar.py`

#### `bar_chart(axes, df, x_col, y_col, **kwargs)`

Draws a vertical bar chart. X values are converted to strings. X tick labels are rotated 45 degrees.

#### `histogram(axes, df, x_col, y_col=None, **kwargs)`

Draws a histogram of the x column. `y_col` is accepted but ignored. Default bins=10, edgecolor="white".

---

### `graphx/plots/categorical.py`

#### `pie_chart(axes, df, x_col, y_col, **kwargs)`

Draws a pie chart with x column values as labels, y column values as data. Shows percentage labels (`autopct="%1.1f%%"`).

#### `heatmap(axes, df, x_col, y_col, **kwargs)`

Draws a heatmap: attempts a pivot table; falls back to the correlation matrix of numeric columns. Uses `imshow` with a colorbar.

---

### `graphx/plots/line.py`

#### `line_plot(axes, df, x_col, y_col, **kwargs)`

Draws a line plot with circular markers (`marker="o", markersize=3`).

#### `scatter_plot(axes, df, x_col, y_col, **kwargs)`

Draws a scatter plot with `alpha=0.7`.

---

### `graphx/plots/surface.py`

#### `surface_3d(axes, df, x_col, y_col, **kwargs)`

Draws a 3D surface plot. Attempts a pivot table for `plot_surface`; falls back to a 3D scatter plot (third column as Z, or zeros). Sets axis labels from column names. Pops `cmap` from kwargs (default `"viridis"`).

#### `contour(axes, df, x_col, y_col, **kwargs)`

Draws a filled contour plot via `contourf`. Falls back to `tricontourf` if pivoting fails. Sets axis labels. Pops `cmap` from kwargs.

---

## Subpackage: `graphx.widgets`

### `graphx/widgets/data_table.py`

#### Class: `PandasTableModel(QAbstractTableModel)`

Qt model/view adapter for a pandas DataFrame.

**Methods:**

- `__init__(self, df=None, parent=None)` — Stores the DataFrame.
- `load_dataframe(self, df)` — Resets the model with a new DataFrame via `beginResetModel()` / `endResetModel()`.
- `rowCount(self, parent=None) -> int` — Returns `len(df)` or `0`.
- `columnCount(self, parent=None) -> int` — Returns `len(df.columns)` or `0`.
- `data(self, index, role) -> str | None` — Returns the cell value as a string for `DisplayRole`.
- `headerData(self, section, orientation, role) -> str | None` — Returns column names (horizontal) or row index labels (vertical).

---

#### Class: `CopyableTableView(QTableView)`

A `QTableView` that supports Ctrl+C to copy selected cells as tab-separated text.

**Methods:**

- `keyPressEvent(self, event)` — Intercepts Ctrl+C to call `_copy_selection()`.
- `_copy_selection(self)` — Organizes selected cells by row/column, builds tab/newline-separated text, sets clipboard.

---

#### Class: `DataTableWidget(QWidget)`

A composite widget containing `PandasTableModel` + `CopyableTableView`.

**Signals:**

| Signal | Type |
|--------|------|
| `column_clicked` | `str` |

**Methods:**

- `__init__(self, parent=None)` — Creates model, table (stretch columns, select items), connects header click to `_on_header_clicked`.
- `_on_header_clicked(self, section)` — Emits `column_clicked` with the column name.
- `load_dataframe(self, df)` — Delegates to `model.load_dataframe(df)`.

---

#### Class: `DataTableWindow(QWidget)`

A standalone floating window containing a `DataTableWidget`. Minimizes to hide instead of closing.

**Properties:** `column_clicked` — delegates to the inner `DataTableWidget.column_clicked`.

**Methods:**

- `__init__(self, parent=None)` — Creates window (800×400) with `DataTableWidget`.
- `load_dataframe(self, df)` — Delegates to the inner widget.
- `closeEvent(self, event)` — Ignores close and hides instead.

---

### `graphx/widgets/expression_highlighter.py` — `ExpressionHighlighter`

**Module-level docstring:**
> *Syntax highlighter for the calculator expression editor.*

**Module-level constants:**

- `_FUNCTION_NAMES`: List of recognized function names (`log`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `pow`, `sin`, `cos`, `tan`, `arcsin`, `arccos`, `arctan`).
- Color palette: `_FUNC_COLOR = "#0066CC"`, `_NUM_COLOR = "#098658"`, `_OP_COLOR = "#888888"`, `_COL_COLOR = "#800000"`, `_CONST_COLOR = "#800080"`, `_PAREN_COLOR = "#333333"`, `_NP_COLOR = "#0066CC"`.

#### Helper: `_fmt(hex_color: str, *, bold: bool = False) -> QTextCharFormat`

Creates a `QTextCharFormat` with the given foreground color and optional bold weight.

---

#### Class: `ExpressionHighlighter(QSyntaxHighlighter)`

**Module-level docstring:**
> *Regex-based syntax highlighter for calculator expressions. Applies layered rules — later rules override earlier ones on overlap.*

**Constructor:**

##### `__init__(self, document)`

Defines highlighting rules as `list[tuple[re.Pattern, QTextCharFormat]]` in priority order (lowest first):

| Priority | Pattern | Color | Style |
|----------|---------|-------|-------|
| 1 | Words with dots (column refs) | Maroon (`#800000`) | Normal |
| 2 | Numbers (int/float/sci notation) | Green (`#098658`) | Normal |
| 3 | Operators (`+`, `-`, `*`, `/`) | Gray (`#888888`) | Normal |
| 4 | Parentheses/brackets/braces | Dark gray (`#333333`) | Normal |
| 5 | Constant `pi` | Purple (`#800080`) | Normal |
| 6 | Constant `e` | Purple (`#800080`) | Normal |
| 7 | `np` prefix | Blue (`#0066CC`) | Normal |
| 8 | Function names | Blue (`#0066CC`) | Bold |

**Methods:**

##### `highlightBlock(self, text: str)`

Applies each rule's compiled regex to the text, calling `setFormat(start, length, format)` for each match. Later rules override earlier ones where patterns overlap.

---

### `graphx/widgets/plot_controls.py`

**Module-level constant:**

```python
DEFAULT_RECENT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f",
]
```

---

#### Class: `RecentColorSwatch(QPushButton)`

A small (26×26) clickable color swatch for the recent-colors grid.

**Signals:** `clicked_with_color(str)`

**Methods:**

- `__init__(self, color, parent=None)` — Sets size, tooltip, style, and connects `clicked` to emit `clicked_with_color`.
- `set_color(self, color)` — Updates color and tooltip.
- `_update_style(self, selected)` — Sets stylesheet: 3px black border when selected, 1px gray otherwise.
- `set_selected(self, selected)` — Updates selection visual.

---

#### Class: `CurveRow(QFrame)`

A single curve definition row in the curve panel.

**Signals:** `changed()`, `remove_requested(CurveRow)`, `fit_requested(CurveConfig)`

**Constructor:**

##### `__init__(self, index: int, columns: list[str], curve: CurveConfig, parent=None)`

Builds a two-row layout in a styled-panel frame:

**Row 1:** Color button (24×24, shows curve color), X column combo, Y column combo, "Fit" button (32px wide), "✕" remove button (24×24).

**Row 2:** "Label:" + `QLineEdit` (placeholder `"Curve {n}"`).

**Methods:**

- `_on_color_clicked(self)` — Opens `QColorDialog`, updates curve color and button style, emits `changed`.
- `_on_field_changed(self)` — Syncs combo and label values to the curve object, emits `changed`.
- `set_color(self, color)` — Sets curve color and emits `changed`.
- `refresh_columns(self, columns)` — Refreshes combo items while preserving current selections (blocking signals during update), then syncs curve config.

---

#### Class: `CurvePanelWidget(QWidget)`

**Module-level docstring:**
> *Standalone panel for the list of curves.*

**Signals:** `add_curve_requested()`, `changed()`, `fit_requested(CurveConfig)`

**Methods:**

- `__init__(self, parent=None)` — Creates layout with curves list area, "+ Add Curve" button, and stretch.
- `_on_add_curve(self)` — Emits `add_curve_requested`.
- `_on_curve_changed(self)` — Emits `changed`.
- `_on_remove_curve(self, row)` — Removes row from list and layout, calls `deleteLater()`, reindexes, emits `changed`.
- `_reindex_rows(self)` — Updates each row's index and placeholder text.
- `load_columns(self, columns)` — Calls `refresh_columns()` on each row.
- `set_curves(self, curves)` — Rebuilds all curve rows from a list of `CurveConfig` objects (removes old, creates new, connects signals).
- `get_curves_config(self) -> list[dict]` — Returns `[{x_col, y_col, label, color}, ...]` for all rows.
- `set_all_colors(self, color)` — Sets the same color on all rows.
- `apply_color_to_all(self, color)` — Calls `set_all_colors()` and emits `changed`.

---

#### Class: `PlotControlsWidget(QWidget)`

Widget for plot appearance controls (titles, axis labels, legend) and a color picker.

**Signals:** `changed()` (debounced 150ms), `color_changed(str)`

**Constructor:**

##### `__init__(self, parent=None)`

Builds two sections:

**Labels section** (`QFrame`, styled panel):
- Title `QLineEdit` (placeholder "Title")
- Subtitle `QLineEdit` (placeholder "Subtitle")
- X Label `QLineEdit` (placeholder "X axis label")
- Y Label `QLineEdit` (placeholder "Y axis label")
- "Show Legend" `QCheckBox`

All text fields use debounced emit (150ms timer).

**Color picker section** (`QFrame`, styled panel):
- Color preview button (40×26, disabled — visual only)
- "Pick RGB Color…" button → opens `QColorDialog`
- "Recent:" label + 8-swatch grid (`RecentColorSwatch`), first swatch pre-selected

**Methods:**

- `_update_color_preview(self)` — Updates preview button background.
- `_add_to_recent(self, color)` — Deduplicates and prepends to recent list (max 8).
- `_refresh_recent_swatches(self)` — Syncs swatch colors/selections/visibility.
- `_on_pick_custom_color(self)` — Opens `QColorDialog`, calls `_on_color_selected()`.
- `_on_recent_color_clicked(self, color)` — Calls `_on_color_selected()`.
- `_on_color_selected(self, color)` — Sets selected color, adds to recent, updates preview, emits `color_changed` and `changed`.
- `_debounced_emit(self)` — Starts/restarts 150ms debounce timer.
- `needs_add_curve(self) -> bool` — Returns `False` (stub for backward compat).
- `clear_pending_add_curve(self)` — No-op (stub).
- `get_selected_palette_color(self) -> str` — Returns current selected hex color.
- `get_title(self) -> str` — Returns title text.
- `get_subtitle(self) -> str` — Returns subtitle text.
- `get_x_label(self) -> str` — Returns X label text.
- `get_y_label(self) -> str` — Returns Y label text.
- `get_show_legend(self) -> bool` — Returns legend checkbox state.
- `get_curves_config(self) -> list` — Returns `[]` (curve config comes from `CurvePanelWidget`).

---

### `graphx/widgets/tool_panel.py`

#### Class: `ExprEdit(QPlainTextEdit)`

**Module-level docstring:**
> *Single-line QPlainTextEdit whose keyPressEvent blocks Enter/Return so a new paragraph is never inserted (which would destroy content when `setMaximumBlockCount(1)` is active).*

**Signals:** `enter_pressed()`

**Methods:**

##### `keyPressEvent(self, event: QKeyEvent)`

If the key is Enter or Return, emits `enter_pressed()` and returns (blocking the newline). Otherwise delegates to the parent class.

---

#### Class: `ExpressionCompleter(QCompleter)`

**Module-level docstring:**
> *QCompleter that splits on expression operators so completion is based on the current token, not the whole expression text.*

**Class attribute:** `_TOKEN_RE = re.compile(r'[\w.]+$')`

**Methods:**

##### `splitPath(self, path: str) -> list[str]`

Extracts the last word (alphanumeric + dots) from the expression text using `_TOKEN_RE`. Returns it as a single-element list, or `[""]` if no match.

---

#### Class: `ToolPanelWidget(QWidget)`

The main sidebar widget containing four analysis tool tabs.

**Signals:**

| Signal | Emitted Type | When |
|--------|-------------|------|
| `fit_requested` | `str` | "Apply Fit" clicked (fit_type) |
| `cluster_requested` | (none) | "Run K-Means" clicked |
| `elbow_requested` | (none) | "Show Elbow Method" clicked |
| `calculate_requested` | `str, str, str` | "Compute" clicked (expression, target, direction) |
| `summarize_requested` | `str, str` | "Summarize as Error Bar Point" (direction, target) |
| `view_error_bars_toggled` | `bool` | "Show Error Bar Points" toggled |

**Constructor:**

##### `__init__(self, parent=None)`

Builds four tabs:

**Tab 1 — Fitting:**
- Direction combo (By Column / By Row) + Row spin (0–9999, prefix "Row ", hidden in column mode).
- Fit type combo (Linear / Polynomial / Exponential).
- Polynomial degree spin (1–10, default 2).
- "Apply Fit" button → emits `fit_requested(fit_type.lower())`.
- Results: read-only `QTextEdit` (max height 120px).

**Tab 2 — Calculator:**
- Direction combo (By Column / By Row).
- Expression editor: `ExprEdit` with `ExpressionHighlighter`, `ExpressionCompleter`, `setMaximumBlockCount(1)`, `setTabChangesFocus(True)`, no scrollbars, fixed height 32px, no wrap.
  - Enter key → if popup visible, accepts completion; otherwise triggers Compute and clears the editor.
  - Ctrl+Space → force-show completions.
  - Popup navigation: Up/Down/PgUp/PgDown/Escape.
  - Auto bracket pairing: `()`, `[]`, `{}` with smart skip/delete.
  - `_TOKEN_RE`-based token replacement on completion activation.
  - `_completing` flag prevents recursive popup updates.
- "Type to autocomplete | Ctrl+Space to browse all columns" hint label.
- Row mode hint: `"Row mode: use 'r' for the row vector, e.g. np.mean(r)"` (visible only in row mode).
- Quick-op buttons row 1: `+`, `-`, `*`, `/`.
- Quick-op buttons row 2: `log₁₀`, `ln`, `eˣ`, `xʸ`, `√`, `|x|` — each inserts the corresponding function call at cursor.
- Target column name `QLineEdit` (placeholder "new_column").
- "Compute" button → `_on_calculate()`.
- Results: read-only `QTextEdit` (max height 80px).

**Tab 3 — Summarize (Error Bars):**
- Direction combo (Column / Row).
- Target combo (editable).
- "Summarize as Error Bar Point" button → `_on_summarize()`.
- "Show Error Bar Points" toggle button (checkable) → emits `view_error_bars_toggled`.
- Results: read-only `QTextEdit` (max height 100px).

**Tab 4 — Clustering:**
- K spin (2–20, default 3).
- "Run K-Means" button → emits `cluster_requested`.
- "Show Elbow Method" button → emits `elbow_requested`.
- Results: read-only `QTextEdit` (max height 120px).

---

**Bracket Helpers:**

##### `_handle_bracket_open(self, open_b: str) -> bool`

Inserts the matching bracket pair. If text is selected, wraps the selection. Otherwise inserts both brackets and places the cursor between them. Returns `True`.

##### `_handle_bracket_close(self, close_b: str) -> bool`

If the character immediately after the cursor is the same closing bracket, moves the cursor past it (skips duplicate). Returns `True` if skipped, `False` otherwise.

##### `_handle_bracket_backspace(self) -> bool`

If the cursor is between an empty bracket pair (e.g., `(|)`), deletes both brackets. Returns `True` if deleted.

##### `_navigate_popup(self, key, popup)`

Moves the popup selection: Up (row-1), Down (row+1), PgUp (row-5), PgDown (row+5), clamped to valid range.

---

**Event Filter:**

##### `eventFilter(self, obj, event) -> bool`

Handles `KeyPress` events for `calc_expr_edit`:
- `Ctrl+Space` → forces completion popup.
- When popup is visible: `Escape` hides it; `Up`/`Down`/`PgUp`/`PgDown` navigate.
- `(` / `[` / `{` → `_handle_bracket_open()`.
- `)` / `]` / `}` → `_handle_bracket_close()`.
- `Backspace` → `_handle_bracket_backspace()` (if applicable).

Delegates unhandled events to `super().eventFilter()`.

---

**Other Methods:**

##### `_on_expr_text_changed(self)`

Updates the completer popup (skipped during `_completing` to avoid recursion).

##### `_on_cursor_position_changed(self)`

Repositions the popup when cursor moves without text change (e.g., arrow keys).

##### `_update_completer_popup(self)`

Sets the completion prefix to `_current_token()`, triggers completion. If matches exist, repositions and highlights the first item. Otherwise hides the popup.

##### `_current_token(self) -> str`

Returns the word at cursor position using `[\w.]*$` regex on text left of cursor.

##### `_set_cursor_pos(self, pos: int)`

Sets the text cursor to absolute position `pos`.

##### `_reposition_popup(self)`

Moves the completer popup to sit just below the cursor rectangle (minimum width 320px, max height 260px).

##### `_on_enter_pressed(self)`

If the completion popup is visible, accepts the current selection. Otherwise triggers `_on_calculate()` and clears the expression editor.

##### `_on_popup_activated(self, idx: QModelIndex)`

Extracts display text from the model index and calls `_on_completion_activated(text)`.

##### `_on_completion_activated(self, text: str)`

Replaces only the current token (not the whole expression) using cursor operations: finds the token start with regex, selects from start to cursor, inserts the completion text. Sets `_completing = True` during the operation.

##### `_insert_op(self, text: str)`

Inserts text at the current cursor position and moves the cursor past the inserted text.

##### `_on_calculate(self)`

Reads expression, target, and direction; emits `calculate_requested`. Warns if expression is empty.

##### `_on_summary_direction_changed(self, text: str)`

Refreshes summary target items via `set_summary_targets()` if columns are cached.

##### `_on_summarize(self)`

Reads direction and target, emits `summarize_requested`. Warns if target is empty.

---

**Public Methods:**

##### `set_calc_completions(self, sheets: dict, active_sheet: str)`

Populates the autocomplete model:
1. Function names: `log(`, `log10(`, `log2(`, `exp(`, `sqrt(`, `abs(`, `pow(`, `sin(`, `cos(`, `tan(`, `arcsin(`, `arccos(`, `arctan(`.
2. Raw column names from the active sheet.
3. `SheetName.ColumnName` references for all sheets (using sanitized sheet names, only if no spaces in the reference).

Items are deduplicated and sorted.

##### `set_summary_targets(self, columns: list[str], row_count: int)`

Caches column list and row count. Populates the summary target combo with column names (column mode) or row indices 0..row_count-1 (row mode).

##### `show_fit_results(self, text: str)`

Sets the fitting tab's results text.

##### `show_cluster_results(self, text: str)`

Sets the clustering tab's results text.

##### `show_calc_results(self, text: str)`

Sets the calculator tab's results text.

##### `show_summary_results(self, text: str)`

Sets the summarize tab's results text.

##### `get_fit_config(self) -> dict`

```python
{
    "fit_type": str,      # "linear", "polynomial", or "exponential"
    "degree": int,         # Polynomial degree
    "direction": str,      # "column" or "row"
    "row_index": int,      # Row index for row-wise fitting
}
```

##### `get_cluster_config(self) -> dict`

```python
{"n_clusters": int}  # 2–20
```

---

## Tests

### `tests/test_clustering.py`

**Helper:** `_make_blob_data(n_samples=150) -> pd.DataFrame` — Generates 3 well-separated Gaussian clusters via `sklearn.datasets.make_blobs`.

**5 test functions:**

| Test | What it verifies |
|------|-----------------|
| `test_kmeans_returns_correct_shape()` | For k=3, labels length=150, centroids shape=(3,2), n_clusters=3. |
| `test_kmeans_keys()` | Result contains `type`, `labels`, `centroids`, `inertia`, `n_clusters`. |
| `test_elbow_method_length()` | `k_values` and `inertias` each have length `max_k` (10). |
| `test_elbow_optimal_k_in_range()` | `optimal_k` is between 1 and `max_k` inclusive. |
| `test_inertias_decreasing()` | Inertias are monotonically non-increasing as k increases. |

---

### `tests/test_fitting.py`

**Helpers:**
- `_make_linear_data()` — `y = 2.5x + 1.0 + noise`.
- `_make_quadratic_data()` — `y = 0.5x² - 3x + 5 + noise`.
- `_make_exp_data()` — `y = 2.0 * exp(0.5x) + noise`.

**6 test functions:**

| Test | What it verifies |
|------|-----------------|
| `test_linear_regression_slope()` | Slope ≈ 2.5 (±0.5), intercept ≈ 1.0 (±0.5). |
| `test_linear_regression_keys()` | All expected keys present; `fitted_fn` is callable. |
| `test_poly_fit_quadratic()` | Degree-2 fit: 3 coefficients, R² > 0.8. |
| `test_poly_fit_keys()` | All expected keys present; degree matches input. |
| `test_exp_fit()` | `a` ≈ 2.0 (±1.0), `b` ≈ 0.5 (±0.5). |
| `test_fitted_fn_callable()` | All three fit types return callable `fitted_fn` producing correct-length output. |

---

## Architecture Summary

### Data Flow

```
User Input (File / Paste / Drag-Drop)
  │
  ▼
ImportDataDialog / _load_file_direct / _on_paste
  │
  ▼
PlotState.load_dataframe() / load_sheets()
  │
  ├──► _rebuild_sheet_combo()
  ├──► _refresh_columns_ui()
  ├──► _sync_state_from_controls()
  ├──► _redraw()
  └──► ExcelSync.sync() / _open_temp_in_excel()
```

### Redraw Pipeline

```
_redraw()
  │
  ├──► canvas.clear()  (reuses existing axes via cla())
  ├──► For each visible curve:
  │      └──► plot_fn (from plot_fns dict) with x_col, y_col, color, label
  ├──► Set suptitle, subtitle, axis labels, legend from PlotState
  ├──► _draw_analysis_overlay(target, ptype)
  │      ├──► Fit lines (dashed, colored by FIT_DASH_COLORS cycle)
  │      ├──► K-Means scatter + centroid stars
  │      ├──► Elbow curve + optimal-k vertical line
  │      └──► Extrapolation diamond markers
  ├──► _draw_error_bars(target)
  │      └──► axes.errorbar() for each ErrorBarPoint
  └──► canvas.draw_idle()
```

### Analysis Pipeline

```
User action (fit / cluster / calculate)
  │
  ▼
GraphXApp handler
  │
  ▼
Analysis module (fitting.py / clustering.py / calculator.py)
  │
  ▼
Result stored in PlotState.analysis_results (unified list) or extrapolation_points
  │
  ▼
_redraw() overlays results via _draw_analysis_overlay()
  │
  ▼
Results formatted and displayed in UI (_format_fit_result / _show_analysis_results)
```

### Widget Hierarchy

```
GraphXApp (QMainWindow) — 1200×800
├── MenuBar
├── QToolBar ("Main Toolbar") — empty, reserved
├── StatusBar
│   └── status_label (QLabel)
├── QSplitter (central widget)
│   ├── Canvas container (stretch 1)
│   │   ├── NavigationToolbar2QT
│   │   └── MplCanvas
│   └── Sidebar (fixed 300px, stretch 0)
│       ├── Sheet bar: QComboBox + add button (+)
│       ├── PlotControlsWidget
│       │   ├── Labels frame (title, subtitle, x/y labels, legend checkbox)
│       │   └── Color picker frame (preview, RGB picker, recent swatches)
│       └── ToolPanelWidget (QTabWidget)
│           ├── Fitting tab
│           ├── Calculator tab
│           ├── Summarize tab
│           └── Clustering tab
└── Curves Dock (left side)
    └── CurvePanelWidget
        └── [CurveRow, CurveRow, ...]
            └── Each: color btn, X combo, Y combo, Fit btn, Remove btn, Label edit
```

### Key Design Decisions

- **Unified analysis results:** All analysis output (fit, kmeans, elbow) is stored in a single `analysis_results: list[dict]` on `PlotState`. The overlay drawing function dispatches on each item's `type` field.
- **Excel round-trip:** Data is written to a temp `.xlsx` in the system temp directory (avoids OneDrive/cloud-sync locks). A directory-level `QFileSystemWatcher` detects external saves. `ExcelSync` handles COM-based reload with `ScreenUpdating` suppression for flicker-free updates.
- **Safe eval sandbox:** Calculator expressions are evaluated with `__builtins__` set to an empty dict. Only explicit numpy math functions and dataframe columns are accessible.
- **Debounced UI:** Text field changes in `PlotControlsWidget` use a 150ms debounce timer so that `changed` fires once after the user stops typing, preventing excessive redraws.
- **Token-aware autocomplete:** `ExpressionCompleter.splitPath()` extracts only the current token via regex, enabling context-aware completion within complex expressions like `log10(Sheet1.col_`.
- **Smart bracket handling:** The expression editor auto-inserts matching brackets, skips over existing closing brackets, and deletes empty bracket pairs with a single backspace.
