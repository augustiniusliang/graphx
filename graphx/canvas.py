from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QSizePolicy


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.figure.set_constrained_layout(True)
        self.axes = self.figure.add_subplot(111)
        self.axes_3d = None
        self._is_3d = False
        super().__init__(self.figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self):
        """Clear the canvas for replotting. Reuses existing axes when possible
        to avoid matplotlib constrained_layout instability from destroying and
        recreating axes on every redraw."""
        if self._is_3d:
            if self.axes_3d is not None:
                self.axes_3d.cla()
            else:
                self.figure.clear()
                self.axes = None
                self.axes_3d = self.figure.add_subplot(111, projection="3d")
        else:
            if self.axes is not None:
                self.axes.cla()
            else:
                self.figure.clear()
                self.axes_3d = None
                self.axes = self.figure.add_subplot(111)

    def draw_plot(self, plot_fn, df, x_col, y_col, is_3d=False, **kwargs):
        self._is_3d = is_3d
        self.clear()
        target = self.axes_3d if is_3d else self.axes
        plot_fn(target, df, x_col, y_col, **kwargs)
        self.draw_idle()

    def save(self, path, dpi=300):
        self.figure.savefig(path, dpi=dpi, bbox_inches="tight")
