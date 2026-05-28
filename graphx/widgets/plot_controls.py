from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QFrame, QGridLayout,
    QColorDialog,
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal, QTimer

DEFAULT_RECENT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f",
]


class RecentColorSwatch(QPushButton):
    """A small clickable color swatch for recently used colors."""
    clicked_with_color = pyqtSignal(str)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(26, 26)
        self._update_style(False)
        self.setToolTip(color)
        self.clicked.connect(lambda: self.clicked_with_color.emit(self.color))

    def set_color(self, color):
        self.color = color
        self.setToolTip(color)
        self._update_style(False)

    def _update_style(self, selected):
        border = "3px solid #000" if selected else "1px solid #999"
        self.setStyleSheet(
            f"background-color: {self.color}; border: {border}; border-radius: 3px;"
        )

    def set_selected(self, selected):
        self._update_style(selected)


class CurveRow(QFrame):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)  # self
    fit_requested = pyqtSignal(object)     # curve

    def __init__(self, index, columns, curve, parent=None):
        super().__init__(parent)
        self.index = index
        self.curve = curve
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Row 1: color button, X, Y, fit, remove
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.setStyleSheet(
            f"background-color: {curve.color}; border: 1px solid #999; border-radius: 3px;"
        )
        self.color_btn.clicked.connect(self._on_color_clicked)
        row1.addWidget(self.color_btn)

        self.x_combo = QComboBox()
        self.x_combo.addItems(columns)
        if curve.x_col in columns:
            self.x_combo.setCurrentText(curve.x_col)
        self.x_combo.currentTextChanged.connect(self._on_field_changed)
        row1.addWidget(self.x_combo)

        self.y_combo = QComboBox()
        self.y_combo.addItems(columns)
        if curve.y_col in columns:
            self.y_combo.setCurrentText(curve.y_col)
        self.y_combo.currentTextChanged.connect(self._on_field_changed)
        row1.addWidget(self.y_combo)

        fit_btn = QPushButton("Fit")
        fit_btn.setFixedWidth(32)
        fit_btn.setToolTip(f"Fit curve {index + 1}")
        fit_btn.clicked.connect(lambda: self.fit_requested.emit(self.curve))
        row1.addWidget(fit_btn)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setToolTip(f"Remove curve {index + 1}")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        row1.addWidget(remove_btn)

        layout.addLayout(row1)

        # Row 2: legend label
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addWidget(QLabel("Label:"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(f"Curve {index + 1}")
        self.label_edit.setText(curve.label)
        self.label_edit.textChanged.connect(self._on_field_changed)
        row2.addWidget(self.label_edit)
        layout.addLayout(row2)

    def _on_color_clicked(self):
        color = QColorDialog.getColor(QColor(self.curve.color), self, "Pick Curve Color")
        if color.isValid():
            self.curve.color = color.name()
            self.color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #999; border-radius: 3px;"
            )
            self.changed.emit()

    def _on_field_changed(self):
        self.curve.x_col = self.x_combo.currentText()
        self.curve.y_col = self.y_combo.currentText()
        self.curve.label = self.label_edit.text()
        self.changed.emit()

    def set_color(self, color):
        self.curve.color = color
        self.color_btn.setStyleSheet(
            f"background-color: {color}; border: 1px solid #999; border-radius: 3px;"
        )
        self.changed.emit()

    def refresh_columns(self, columns):
        current_x = self.x_combo.currentText()
        current_y = self.y_combo.currentText()
        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        self.x_combo.clear()
        self.y_combo.clear()
        self.x_combo.addItems(columns)
        self.y_combo.addItems(columns)
        if current_x in columns:
            self.x_combo.setCurrentText(current_x)
        if current_y in columns:
            self.y_combo.setCurrentText(current_y)
        self.x_combo.blockSignals(False)
        self.y_combo.blockSignals(False)
        self.curve.x_col = self.x_combo.currentText()
        self.curve.y_col = self.y_combo.currentText()


class CurvePanelWidget(QWidget):
    """Standalone panel for the list of curves."""
    add_curve_requested = pyqtSignal()
    changed = pyqtSignal()
    fit_requested = pyqtSignal(object)  # curve

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns = []
        self._curve_rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.curves_layout = QVBoxLayout()
        self.curves_layout.setSpacing(2)
        layout.addLayout(self.curves_layout)

        self.add_curve_btn = QPushButton("+ Add Curve")
        self.add_curve_btn.clicked.connect(self._on_add_curve)
        layout.addWidget(self.add_curve_btn)
        layout.addStretch()

    def _on_add_curve(self):
        self.add_curve_requested.emit()

    def _on_curve_changed(self):
        self.changed.emit()

    def _on_remove_curve(self, row):
        self._curve_rows.remove(row)
        self.curves_layout.removeWidget(row)
        row.deleteLater()
        self._reindex_rows()
        self.changed.emit()

    def _reindex_rows(self):
        for i, row in enumerate(self._curve_rows):
            row.index = i
            row.label_edit.setPlaceholderText(f"Curve {i + 1}")

    def load_columns(self, columns):
        self._columns = columns
        for row in self._curve_rows:
            row.refresh_columns(columns)

    def set_curves(self, curves):
        for row in self._curve_rows:
            self.curves_layout.removeWidget(row)
            row.deleteLater()
        self._curve_rows.clear()
        for i, curve in enumerate(curves):
            row = CurveRow(i, self._columns, curve)
            row.changed.connect(self._on_curve_changed)
            row.remove_requested.connect(self._on_remove_curve)
            row.fit_requested.connect(self.fit_requested)
            self._curve_rows.append(row)
            self.curves_layout.addWidget(row)

    def get_curves_config(self):
        return [
            {
                "x_col": row.x_combo.currentText(),
                "y_col": row.y_combo.currentText(),
                "label": row.label_edit.text(),
                "color": row.curve.color,
            }
            for row in self._curve_rows
        ]

    def set_all_colors(self, color):
        for row in self._curve_rows:
            row.set_color(color)

    def apply_color_to_all(self, color):
        self.set_all_colors(color)
        self.changed.emit()


class PlotControlsWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_color = DEFAULT_RECENT_COLORS[0]
        self._recent_colors = list(DEFAULT_RECENT_COLORS)
        self._max_recent = 8

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(4)

        # --- Labels section ---
        lbl_frame = QFrame()
        lbl_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        lbl_layout = QVBoxLayout(lbl_frame)
        lbl_layout.setSpacing(2)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title")
        self.title_edit.textChanged.connect(self._debounced_emit)
        lbl_layout.addWidget(QLabel("Title"))
        lbl_layout.addWidget(self.title_edit)

        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.setPlaceholderText("Subtitle")
        self.subtitle_edit.textChanged.connect(self._debounced_emit)
        lbl_layout.addWidget(QLabel("Subtitle"))
        lbl_layout.addWidget(self.subtitle_edit)

        self.x_label_edit = QLineEdit()
        self.x_label_edit.setPlaceholderText("X axis label")
        self.x_label_edit.textChanged.connect(self._debounced_emit)
        lbl_layout.addWidget(QLabel("X Label"))
        lbl_layout.addWidget(self.x_label_edit)

        self.y_label_edit = QLineEdit()
        self.y_label_edit.setPlaceholderText("Y axis label")
        self.y_label_edit.textChanged.connect(self._debounced_emit)
        lbl_layout.addWidget(QLabel("Y Label"))
        lbl_layout.addWidget(self.y_label_edit)

        self.legend_check = QCheckBox("Show Legend")
        self.legend_check.toggled.connect(self.changed)
        lbl_layout.addWidget(self.legend_check)

        main.addWidget(lbl_frame)

        # --- Color picker (RGB free selection) ---
        color_frame = QFrame()
        color_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        color_outer = QVBoxLayout(color_frame)
        color_outer.setSpacing(4)

        color_outer.addWidget(QLabel("Curve Color"))

        picker_row = QHBoxLayout()
        picker_row.setSpacing(6)

        self.current_color_preview = QPushButton()
        self.current_color_preview.setFixedSize(40, 26)
        self.current_color_preview.setEnabled(False)
        self._update_color_preview()
        picker_row.addWidget(self.current_color_preview)

        self.pick_color_btn = QPushButton("Pick RGB Color...")
        self.pick_color_btn.clicked.connect(self._on_pick_custom_color)
        picker_row.addWidget(self.pick_color_btn)

        color_outer.addLayout(picker_row)

        # Recent colors strip
        color_outer.addWidget(QLabel("Recent:"))
        self._recent_swatches = []
        recent_grid = QGridLayout()
        recent_grid.setSpacing(2)
        for i, color in enumerate(self._recent_colors):
            swatch = RecentColorSwatch(color)
            swatch.clicked_with_color.connect(self._on_recent_color_clicked)
            recent_grid.addWidget(swatch, 0, i)
            self._recent_swatches.append(swatch)
        self._recent_swatches[0].set_selected(True)
        color_outer.addLayout(recent_grid)

        main.addWidget(color_frame)

        # Debounce timer for text changes
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self.changed)

        main.addStretch()

    # Signals to notify the curve panel about color changes
    color_changed = pyqtSignal(str)

    def _update_color_preview(self):
        self.current_color_preview.setStyleSheet(
            f"background-color: {self._selected_color}; border: 1px solid #999; border-radius: 3px;"
        )

    def _add_to_recent(self, color):
        if color in self._recent_colors:
            self._recent_colors.remove(color)
        self._recent_colors.insert(0, color)
        self._recent_colors = self._recent_colors[:self._max_recent]
        self._refresh_recent_swatches()

    def _refresh_recent_swatches(self):
        for i, swatch in enumerate(self._recent_swatches):
            if i < len(self._recent_colors):
                swatch.set_color(self._recent_colors[i])
                swatch.set_selected(self._recent_colors[i] == self._selected_color)
                swatch.setVisible(True)
            else:
                swatch.setVisible(False)

    def _on_pick_custom_color(self):
        color = QColorDialog.getColor(QColor(self._selected_color), self, "Choose Curve Color")
        if color.isValid():
            self._on_color_selected(color.name())

    def _on_recent_color_clicked(self, color):
        self._on_color_selected(color)

    def _on_color_selected(self, color):
        self._selected_color = color
        self._add_to_recent(color)
        self._update_color_preview()
        self.color_changed.emit(color)
        self.changed.emit()

    def _debounced_emit(self):
        self._debounce.start()

    def needs_add_curve(self):
        return False  # now handled by CurvePanelWidget directly

    def clear_pending_add_curve(self):
        pass

    def get_selected_palette_color(self):
        return self._selected_color

    def get_title(self):
        return self.title_edit.text()

    def get_subtitle(self):
        return self.subtitle_edit.text()

    def get_x_label(self):
        return self.x_label_edit.text()

    def get_y_label(self):
        return self.y_label_edit.text()

    def get_show_legend(self):
        return self.legend_check.isChecked()

    def get_curves_config(self):
        return []  # curve config now comes from CurvePanelWidget
