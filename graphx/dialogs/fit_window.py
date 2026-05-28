from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QTextEdit, QGroupBox,
)
from PyQt6.QtCore import pyqtSignal


class FitWindow(QWidget):
    """Floating fit window for per-curve or menu-triggered fitting.

    Supports both column-wise and row-wise fitting with direction toggle.
    """
    fit_requested = pyqtSignal(dict)  # {fit_type, degree, direction, x_col, y_col, row_index, curve_label, curve_color}

    def __init__(self, curve=None, all_curves=None, parent=None):
        super().__init__(parent, parent.windowFlags() if parent else 0)
        self.curve = curve
        self._all_curves = all_curves or []
        self.resize(380, 420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Curve selection (if multiple curves available)
        if len(self._all_curves) > 1:
            curve_group = QGroupBox("Curve")
            cg_layout = QVBoxLayout(curve_group)
            self.curve_combo = QComboBox()
            labels = [c.label or c.y_col for c in self._all_curves]
            self.curve_combo.addItems(["All visible curves"] + labels)
            if self.curve:
                cur_label = self.curve.label or self.curve.y_col
                if cur_label in labels:
                    self.curve_combo.setCurrentText(cur_label)
            cg_layout.addWidget(self.curve_combo)
            layout.addWidget(curve_group)
        elif self.curve:
            info = QGroupBox("Curve")
            info_layout = QHBoxLayout(info)
            info_layout.addWidget(QLabel(
                f"X: {self.curve.x_col}  |  Y: {self.curve.y_col}"
            ))
            layout.addWidget(info)
        else:
            self.setWindowTitle("Fit Analysis")
            info = QGroupBox("Curve")
            info_layout = QHBoxLayout(info)
            info_layout.addWidget(QLabel("Select curve(s) to fit"))
            layout.addWidget(info)

        # Direction
        dir_group = QGroupBox("Direction")
        dir_layout = QHBoxLayout(dir_group)
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["By Column", "By Row"])
        dir_layout.addWidget(self.direction_combo)

        self.row_spin = QSpinBox()
        self.row_spin.setRange(0, 9999)
        self.row_spin.setValue(0)
        self.row_spin.setPrefix("Row ")
        self.row_spin.setVisible(False)
        self.direction_combo.currentTextChanged.connect(
            lambda t: self.row_spin.setVisible(t == "By Row")
        )
        dir_layout.addWidget(self.row_spin)
        layout.addWidget(dir_group)

        # Fit type
        layout.addWidget(QLabel("Fit type:"))
        self.fit_type_combo = QComboBox()
        self.fit_type_combo.addItems(["Linear", "Polynomial", "Exponential"])
        layout.addWidget(self.fit_type_combo)

        # Polynomial degree
        deg_layout = QHBoxLayout()
        deg_layout.addWidget(QLabel("Polynomial degree:"))
        self.degree_spin = QSpinBox()
        self.degree_spin.setRange(1, 10)
        self.degree_spin.setValue(2)
        deg_layout.addWidget(self.degree_spin)
        deg_layout.addStretch()
        layout.addLayout(deg_layout)

        # Apply button
        self.fit_btn = QPushButton("Apply Fit")
        self.fit_btn.clicked.connect(self._on_apply)
        layout.addWidget(self.fit_btn)

        # Results
        layout.addWidget(QLabel("Results:"))
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        layout.addWidget(self.results_view)

    def _get_selected_curves(self):
        """Return list of curves to fit based on selection."""
        if len(self._all_curves) <= 1:
            return [self.curve] if self.curve else []
        sel = self.curve_combo.currentText()
        if sel == "All visible curves":
            return [c for c in self._all_curves if c.visible]
        for c in self._all_curves:
            if (c.label or c.y_col) == sel:
                return [c]
        return []

    def _on_apply(self):
        direction = "row" if self.direction_combo.currentText() == "By Row" else "column"
        base_cfg = {
            "fit_type": self.fit_type_combo.currentText().lower(),
            "degree": self.degree_spin.value(),
            "direction": direction,
            "row_index": self.row_spin.value(),
        }
        curves = self._get_selected_curves()
        if direction == "row":
            base_cfg["curves"] = curves
            self.fit_requested.emit(base_cfg)
        else:
            for curve in curves:
                cfg = dict(base_cfg)
                cfg["x_col"] = curve.x_col
                cfg["y_col"] = curve.y_col
                cfg["curve_label"] = curve.label or curve.y_col
                cfg["curve_color"] = curve.color
                cfg["curve_obj"] = curve
                self.fit_requested.emit(cfg)

    def show_results(self, text):
        self.results_view.setText(text)

    def append_results(self, text):
        current = self.results_view.toPlainText()
        if current:
            self.results_view.setText(current + "\n" + text)
        else:
            self.results_view.setText(text)
