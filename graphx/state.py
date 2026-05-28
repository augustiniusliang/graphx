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
    dataframe: "pd.DataFrame | None" = None
    columns: list[str] = field(default_factory=list)
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

    @property
    def has_data(self) -> bool:
        return self.dataframe is not None and not self.dataframe.empty

    @property
    def first_curve(self) -> CurveConfig | None:
        return self.curves[0] if self.curves else None

    def load_dataframe(self, df: "pd.DataFrame"):
        self.dataframe = df
        self.columns = list(df.columns)
        if not self.columns:
            return
        x = self.columns[0]
        numeric = [c for c in self.columns if c != x]
        y = numeric[0] if numeric else x
        color_idx = len(self.curves) % len(DEFAULT_COLORS)
        self.curves = [CurveConfig(x_col=x, y_col=y, color=DEFAULT_COLORS[color_idx])]

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
        self.columns = list(self.dataframe.columns)

    def add_error_bar_point(self, label, x, y, yerr, color="#d62728"):
        self.error_bar_points.append(ErrorBarPoint(label=label, x=x, y=y, yerr=yerr, color=color))

    def clear_error_bar_points(self):
        self.error_bar_points.clear()
