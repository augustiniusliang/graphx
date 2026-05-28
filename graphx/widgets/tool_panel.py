from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QComboBox,
    QSpinBox, QPushButton, QTextEdit, QLineEdit, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal


class ToolPanelWidget(QWidget):
    fit_requested = pyqtSignal(str)    # fit_type
    cluster_requested = pyqtSignal()
    elbow_requested = pyqtSignal()
    calculate_requested = pyqtSignal(str, str, str)  # expression, target_column, direction
    summarize_requested = pyqtSignal(str, str)  # direction (column/row), identifier
    view_error_bars_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        tabs = QTabWidget()

        # ---- Fitting tab ----
        fit_tab = QWidget()
        fit_layout = QVBoxLayout(fit_tab)

        self.fit_direction_combo = QComboBox()
        self.fit_direction_combo.addItems(["By Column", "By Row"])
        fit_layout.addWidget(QLabel("Direction:"))
        fit_layout.addWidget(self.fit_direction_combo)

        self.fit_row_spin = QSpinBox()
        self.fit_row_spin.setRange(0, 9999)
        self.fit_row_spin.setValue(0)
        self.fit_row_spin.setPrefix("Row ")
        self.fit_row_spin.setVisible(False)
        self.fit_direction_combo.currentTextChanged.connect(
            lambda t: self.fit_row_spin.setVisible(t == "By Row")
        )
        fit_layout.addWidget(self.fit_row_spin)

        fit_layout.addWidget(QLabel("Fit type:"))
        self.fit_type_combo = QComboBox()
        self.fit_type_combo.addItems(["Linear", "Polynomial", "Exponential"])
        fit_layout.addWidget(self.fit_type_combo)

        fit_layout.addWidget(QLabel("Polynomial degree:"))
        self.degree_spin = QSpinBox()
        self.degree_spin.setRange(1, 10)
        self.degree_spin.setValue(2)
        fit_layout.addWidget(self.degree_spin)

        self.fit_btn = QPushButton("Apply Fit")
        self.fit_btn.clicked.connect(
            lambda: self.fit_requested.emit(self.fit_type_combo.currentText().lower())
        )
        fit_layout.addWidget(self.fit_btn)

        fit_layout.addWidget(QLabel("Results:"))
        self.fit_results = QTextEdit()
        self.fit_results.setReadOnly(True)
        self.fit_results.setMaximumHeight(120)
        fit_layout.addWidget(self.fit_results)
        fit_layout.addStretch()
        tabs.addTab(fit_tab, "Fitting")

        # ---- Calculator tab ----
        calc_tab = QWidget()
        calc_layout = QVBoxLayout(calc_tab)

        calc_layout.addWidget(QLabel("Direction:"))
        self.calc_direction_combo = QComboBox()
        self.calc_direction_combo.addItems(["By Column", "By Row"])
        calc_layout.addWidget(self.calc_direction_combo)

        calc_layout.addWidget(QLabel("Expression:"))
        self.calc_expr_edit = QLineEdit()
        self.calc_expr_edit.setPlaceholderText("e.g. col_A + col_B, log(col_A), col_A ** 2")
        calc_layout.addWidget(self.calc_expr_edit)

        # Row hint
        self.calc_row_hint = QLabel("Row mode: use 'r' for the row vector, e.g. np.mean(r)")
        self.calc_row_hint.setStyleSheet("color: #888; font-size: 11px;")
        self.calc_row_hint.setVisible(False)
        self.calc_direction_combo.currentTextChanged.connect(
            lambda t: self.calc_row_hint.setVisible(t == "By Row")
        )
        calc_layout.addWidget(self.calc_row_hint)

        # Quick-operation buttons
        btn_row1 = QHBoxLayout()
        for op, expr_hint in [("+", "+"), ("-", "-"), ("*", "*"), ("/", "/")]:
            btn = QPushButton(op)
            btn.setFixedWidth(30)
            btn.clicked.connect(lambda checked, o=op: self._insert_op(o))
            btn_row1.addWidget(btn)
        calc_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        for label, func in [("log₁₀", "log10("), ("ln", "log("), ("eˣ", "exp("),
                            ("xʸ", "pow("), ("√", "sqrt("), ("|x|", "abs(")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, f=func: self._insert_op(f))
            btn_row2.addWidget(btn)
        calc_layout.addLayout(btn_row2)

        calc_layout.addWidget(QLabel("Target column name:"))
        self.calc_target_edit = QLineEdit()
        self.calc_target_edit.setPlaceholderText("new_column")
        calc_layout.addWidget(self.calc_target_edit)

        self.calc_btn = QPushButton("Compute")
        self.calc_btn.clicked.connect(self._on_calculate)
        calc_layout.addWidget(self.calc_btn)

        calc_layout.addWidget(QLabel("Result:"))
        self.calc_results = QTextEdit()
        self.calc_results.setReadOnly(True)
        self.calc_results.setMaximumHeight(80)
        calc_layout.addWidget(self.calc_results)
        calc_layout.addStretch()
        tabs.addTab(calc_tab, "Calculator")

        # ---- Summarize tab (error bars) ----
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)

        summary_layout.addWidget(QLabel("Summarize direction:"))
        self.summary_direction = QComboBox()
        self.summary_direction.addItems(["Column", "Row"])
        summary_layout.addWidget(self.summary_direction)

        self.summary_target = QComboBox()
        self.summary_target.setEditable(True)
        summary_layout.addWidget(QLabel("Target:"))
        summary_layout.addWidget(self.summary_target)

        self.summarize_btn = QPushButton("Summarize as Error Bar Point")
        self.summarize_btn.clicked.connect(self._on_summarize)
        summary_layout.addWidget(self.summarize_btn)

        self.summary_direction.currentTextChanged.connect(self._on_summary_direction_changed)

        self.error_bar_toggle = QPushButton("Show Error Bar Points")
        self.error_bar_toggle.setCheckable(True)
        self.error_bar_toggle.toggled.connect(self.view_error_bars_toggled)
        summary_layout.addWidget(self.error_bar_toggle)

        summary_layout.addWidget(QLabel("Results:"))
        self.summary_results = QTextEdit()
        self.summary_results.setReadOnly(True)
        self.summary_results.setMaximumHeight(100)
        summary_layout.addWidget(self.summary_results)
        summary_layout.addStretch()
        tabs.addTab(summary_tab, "Summarize")

        # ---- Clustering tab ----
        cluster_tab = QWidget()
        cluster_layout = QVBoxLayout(cluster_tab)
        cluster_layout.addWidget(QLabel("Number of clusters (k):"))
        self.k_spin = QSpinBox()
        self.k_spin.setRange(2, 20)
        self.k_spin.setValue(3)
        cluster_layout.addWidget(self.k_spin)

        self.cluster_btn = QPushButton("Run K-Means")
        self.cluster_btn.clicked.connect(self.cluster_requested)
        cluster_layout.addWidget(self.cluster_btn)

        self.elbow_btn = QPushButton("Show Elbow Method")
        self.elbow_btn.clicked.connect(self.elbow_requested)
        cluster_layout.addWidget(self.elbow_btn)

        cluster_layout.addWidget(QLabel("Results:"))
        self.cluster_results = QTextEdit()
        self.cluster_results.setReadOnly(True)
        self.cluster_results.setMaximumHeight(120)
        cluster_layout.addWidget(self.cluster_results)
        cluster_layout.addStretch()
        tabs.addTab(cluster_tab, "Clustering")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(tabs)

    # --- Calculator helpers ---
    def _insert_op(self, text):
        cursor = self.calc_expr_edit.cursorPosition()
        current = self.calc_expr_edit.text()
        new_text = current[:cursor] + text + current[cursor:]
        self.calc_expr_edit.setText(new_text)
        self.calc_expr_edit.setFocus()
        self.calc_expr_edit.setCursorPosition(cursor + len(text))

    def _on_calculate(self):
        expr = self.calc_expr_edit.text().strip()
        if not expr:
            QMessageBox.warning(self, "Empty Expression", "Enter an expression first.")
            return
        target = self.calc_target_edit.text().strip() or None
        direction = "row" if self.calc_direction_combo.currentText() == "By Row" else "column"
        self.calculate_requested.emit(expr, target, direction)

    # --- Summarize helpers ---
    def _on_summary_direction_changed(self, text):
        self.summary_target.clear()

    def _on_summarize(self):
        direction = self.summary_direction.currentText().lower()
        target = self.summary_target.currentText().strip()
        if not target:
            QMessageBox.warning(self, "No Target", "Select a column name or row index.")
            return
        self.summarize_requested.emit(direction, target)

    def set_summary_targets(self, columns, row_count):
        """Populate the summary target combo with column names or row indices."""
        direction = self.summary_direction.currentText().lower()
        self.summary_target.clear()
        if direction == "column":
            self.summary_target.addItems(columns)
        else:
            self.summary_target.addItems([str(i) for i in range(row_count)])

    # --- Public getters ---
    def show_fit_results(self, text):
        self.fit_results.setText(text)

    def show_cluster_results(self, text):
        self.cluster_results.setText(text)

    def show_calc_results(self, text):
        self.calc_results.setText(text)

    def show_summary_results(self, text):
        self.summary_results.setText(text)

    def get_fit_config(self):
        return {
            "fit_type": self.fit_type_combo.currentText().lower(),
            "degree": self.degree_spin.value(),
            "direction": "row" if self.fit_direction_combo.currentText() == "By Row" else "column",
            "row_index": self.fit_row_spin.value(),
        }

    def get_cluster_config(self):
        return {
            "n_clusters": self.k_spin.value(),
        }
