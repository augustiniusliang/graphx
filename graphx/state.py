from dataclasses import dataclass, field

DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


@dataclass
class CurveConfig:
    x_col: str = ""
    y_col: str = ""
    label: str = ""
    color: str = "#1f77b4"
    visible: bool = True


@dataclass
class ErrorBarPoint:
    label: str = ""
    x: object = None
    y: float = 0.0
    yerr: float = 0.0
    color: str = "#d62728"


@dataclass
class PlotState:
    sheets: dict[str, "pd.DataFrame"] = field(default_factory=dict)
    active_sheet: str = ""
    curves: list[CurveConfig] = field(default_factory=list)
    plot_type: str = "line"
    title: str = ""
    subtitle: str = ""
    x_label: str = ""
    y_label: str = ""
    show_legend: bool = False
    analysis_results: list[dict] = field(default_factory=list)
    error_bar_points: list[ErrorBarPoint] = field(default_factory=list)
    show_error_bars: bool = False
    extrapolation_points: list[dict] = field(default_factory=list)

    # --- Active-sheet derived properties ---

    @property
    def dataframe(self) -> "pd.DataFrame | None":
        return self.sheets.get(self.active_sheet)

    @staticmethod
    def _normalize_columns(df: "pd.DataFrame") -> "pd.DataFrame":
        """Ensure all column names are strings (pandas may leave them as ints)."""
        if df is not None and not df.empty:
            df.columns = [str(c) for c in df.columns]
        return df

    @dataframe.setter
    def dataframe(self, df: "pd.DataFrame"):
        """Assign a dataframe to the active sheet (backward-compat setter)."""
        df = self._normalize_columns(df)
        if self.active_sheet:
            self.sheets[self.active_sheet] = df
        elif df is not None:
            self.add_sheet("Data", df)

    @property
    def columns(self) -> list[str]:
        df = self.dataframe
        if df is None:
            return []
        return [str(c) for c in df.columns]

    @columns.setter
    def columns(self, cols: list[str]):
        """No-op setter for backward compat — columns are derived from dataframe."""

    @property
    def has_data(self) -> bool:
        return self.dataframe is not None and not self.dataframe.empty

    @property
    def sheet_names(self) -> list[str]:
        return list(self.sheets.keys())

    @property
    def first_curve(self) -> CurveConfig | None:
        return self.curves[0] if self.curves else None

    # --- Sheet management ---

    def add_sheet(self, name: str, df: "pd.DataFrame") -> str:
        """Add a sheet; returns its name (may be disambiguated)."""
        base = name or "Sheet1"
        final = base
        i = 1
        while final in self.sheets:
            i += 1
            final = f"{base}_{i}"
        self.sheets[final] = self._normalize_columns(df)
        if not self.active_sheet:
            self.active_sheet = final
        return final

    def remove_sheet(self, name: str):
        if name not in self.sheets or len(self.sheets) <= 1:
            return
        del self.sheets[name]
        if self.active_sheet == name:
            self.active_sheet = next(iter(self.sheets))

    def rename_sheet(self, old: str, new: str):
        if old not in self.sheets or new in self.sheets or new == old:
            return
        df = self.sheets.pop(old)
        self.sheets[new] = df
        if self.active_sheet == old:
            self.active_sheet = new

    def set_active_sheet(self, name: str):
        if name in self.sheets:
            self.active_sheet = name
            self.analysis_results.clear()
            self.extrapolation_points.clear()

    # --- Data loading ---

    def load_dataframe(self, df: "pd.DataFrame"):
        """Load a single dataframe as a sheet (backward-compat entry point)."""
        name = self.add_sheet("Data", df)
        self.active_sheet = name
        if self.columns:
            x = self.columns[0]
            numeric = [c for c in self.columns if c != x]
            y = numeric[0] if numeric else x
            color_idx = len(self.curves) % len(DEFAULT_COLORS)
            self.curves = [CurveConfig(x_col=x, y_col=y, color=DEFAULT_COLORS[color_idx])]

    def load_sheets(self, sheets: dict[str, "pd.DataFrame"]):
        """Load multiple named sheets at once (e.g., from a multi-sheet Excel)."""
        self.sheets.clear()
        for name, df in sheets.items():
            self.add_sheet(name, df)
        if sheets:
            self.active_sheet = next(iter(self.sheets))
            self.curves.clear()
            if self.columns:
                x = self.columns[0]
                numeric = [c for c in self.columns if c != x]
                y = numeric[0] if numeric else x
                self.curves = [CurveConfig(x_col=x, y_col=y, color=DEFAULT_COLORS[0])]

    # --- Curve management ---

    def add_curve(self):
        if not self.columns:
            return
        used_colors = {c.color for c in self.curves}
        available = [c for c in DEFAULT_COLORS if c not in used_colors]
        color = available[0] if available else DEFAULT_COLORS[len(self.curves) % len(DEFAULT_COLORS)]
        x = self.columns[0]
        numeric = [c for c in self.columns if c != x]
        y = numeric[0] if numeric else x
        self.curves.append(CurveConfig(x_col=x, y_col=y, color=color))

    def add_calculated_column(self, name: str, series: "pd.Series"):
        if self.dataframe is None:
            return
        col_name = name or f"calc_{len(self.columns)}"
        self.dataframe[col_name] = series

    def add_error_bar_point(self, label, x, y, yerr, color="#d62728"):
        self.error_bar_points.append(ErrorBarPoint(label=label, x=x, y=y, yerr=yerr, color=color))

    def clear_error_bar_points(self):
        self.error_bar_points.clear()
