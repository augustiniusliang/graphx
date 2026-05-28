from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QComboBox,
    QSpinBox, QPushButton, QTextEdit, QPlainTextEdit, QLineEdit, QMessageBox, QCompleter,
)
from PyQt6.QtCore import pyqtSignal, Qt, QStringListModel
from PyQt6.QtGui import QTextCursor, QKeyEvent
from .expression_highlighter import ExpressionHighlighter
import re


class ExprEdit(QPlainTextEdit):
    """Single-line QPlainTextEdit whose keyPressEvent blocks Enter/Return
    so a new paragraph is never inserted (which would destroy content when
    ``setMaximumBlockCount(1)`` is active)."""
    enter_pressed = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            return
        super().keyPressEvent(event)


class ExpressionCompleter(QCompleter):
    """QCompleter that splits on expression operators so completion
    is based on the current token, not the whole expression text."""

    _TOKEN_RE = re.compile(r'[\w.]+$')

    def splitPath(self, path):
        m = self._TOKEN_RE.search(path)
        token = m.group() if m else ""
        return [token]


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
        self.calc_expr_edit = ExprEdit()
        self.calc_expr_edit.setPlaceholderText(
            "e.g. col_A + col_B, Sheet.col_C * col_D, log(col_A)")
        self.calc_expr_edit.setMaximumBlockCount(1)
        self.calc_expr_edit.setTabChangesFocus(True)
        self.calc_expr_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.calc_expr_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.calc_expr_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.calc_expr_edit.setFixedHeight(32)
        self.calc_expr_edit.enter_pressed.connect(self._on_enter_pressed)
        self._highlighter = ExpressionHighlighter(self.calc_expr_edit.document())
        calc_layout.addWidget(self.calc_expr_edit)

        # IDE-style autocomplete — popup follows cursor, replaces only current token
        self._completer_model = QStringListModel()
        self._completer = ExpressionCompleter(self._completer_model, self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        # Connect popup's activated (gives model index) instead of completer's
        # (which may emit with empty/wrong text when used with QPlainTextEdit).
        self._completer.popup().activated.connect(self._on_popup_activated)
        # setWidget (not setCompleter) → no QLineEdit built-in replacement logic
        self._completer.setWidget(self.calc_expr_edit)
        self._completing = False
        self.calc_expr_edit.textChanged.connect(self._on_expr_text_changed)
        self.calc_expr_edit.cursorPositionChanged.connect(
            self._on_cursor_position_changed)
        self.calc_expr_edit.installEventFilter(self)

        # Cross-sheet hint
        self.cross_sheet_hint = QLabel(
            "Type to autocomplete | Ctrl+Space to browse all columns"
        )
        self.cross_sheet_hint.setStyleSheet("color: #888; font-size: 11px;")
        calc_layout.addWidget(self.cross_sheet_hint)

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

        self._summary_columns = []
        self._summary_row_count = 0

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

    _BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.calc_expr_edit and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

            # Ctrl+Space — force-show completions
            if key == Qt.Key.Key_Space and ctrl:
                self._completer.setCompletionPrefix("")
                self._completer.complete()
                self._reposition_popup()
                return True

            # Popup navigation keys — delegate to completer
            popup = self._completer.popup()
            if popup and popup.isVisible():
                if key == Qt.Key.Key_Escape:
                    popup.hide()
                    return True
                if key in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                           Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                    self._navigate_popup(key, popup)
                    return True

            # Opening brackets — auto-insert closing pair
            if key == Qt.Key.Key_ParenLeft:
                return self._handle_bracket_open("(")
            if key == Qt.Key.Key_BracketLeft:
                return self._handle_bracket_open("[")
            if key == Qt.Key.Key_BraceLeft:
                return self._handle_bracket_open("{")

            # Closing brackets — smart skip if already present
            if key == Qt.Key.Key_ParenRight:
                return self._handle_bracket_close(")")
            if key == Qt.Key.Key_BracketRight:
                return self._handle_bracket_close("]")
            if key == Qt.Key.Key_BraceRight:
                return self._handle_bracket_close("}")

            # Backspace between empty pair — delete both
            if key == Qt.Key.Key_Backspace:
                if self._handle_bracket_backspace():
                    return True

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Bracket helpers
    # ------------------------------------------------------------------

    def _handle_bracket_open(self, open_b: str) -> bool:
        close_b = self._BRACKET_PAIRS[open_b]
        cursor = self.calc_expr_edit.textCursor()
        if cursor.hasSelection():
            sel = cursor.selectedText()
            cursor.insertText(open_b + sel + close_b)
        else:
            cursor.insertText(open_b + close_b)
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 1)
        self.calc_expr_edit.setTextCursor(cursor)
        return True

    def _handle_bracket_close(self, close_b: str) -> bool:
        cursor = self.calc_expr_edit.textCursor()
        pos = cursor.position()
        text = self.calc_expr_edit.toPlainText()
        if pos < len(text) and text[pos] == close_b:
            cursor.setPosition(pos + 1)
            self.calc_expr_edit.setTextCursor(cursor)
            return True
        return False

    def _handle_bracket_backspace(self) -> bool:
        cursor = self.calc_expr_edit.textCursor()
        if cursor.hasSelection():
            return False

        pos = cursor.position()
        if pos == 0:
            return False

        text = self.calc_expr_edit.toPlainText()
        if pos >= len(text):
            return False

        before = text[pos - 1]
        after = text[pos]
        for open_b, close_b in self._BRACKET_PAIRS.items():
            if before == open_b and after == close_b:
                cursor.setPosition(pos - 1)
                cursor.setPosition(pos + 1, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.calc_expr_edit.setTextCursor(cursor)
                return True

        return False

    def _navigate_popup(self, key, popup):
        """Move the popup selection in response to arrow keys."""
        model = popup.model()
        if model is None or model.rowCount() == 0:
            return
        idx = popup.currentIndex()
        row = idx.row() if idx.isValid() else 0
        last = model.rowCount() - 1
        if key == Qt.Key.Key_Up:
            row = max(row - 1, 0)
        elif key == Qt.Key.Key_Down:
            row = min(row + 1, last)
        elif key == Qt.Key.Key_PageUp:
            row = max(row - 5, 0)
        elif key == Qt.Key.Key_PageDown:
            row = min(row + 5, last)
        popup.setCurrentIndex(model.index(row, 0))

    def _on_expr_text_changed(self):
        if self._completing:
            return
        self._update_completer_popup()

    def _on_cursor_position_changed(self):
        """Reposition popup when cursor moves (e.g., arrow keys) without text change."""
        if self._completing:
            return
        self._update_completer_popup()

    def _update_completer_popup(self):
        token = self._current_token()
        self._completer.setCompletionPrefix(token)
        if token:
            self._completer.complete()
            if self._completer.completionCount() > 0:
                self._reposition_popup()
                # Highlight the first item so the user sees what Enter will insert
                popup = self._completer.popup()
                if popup:
                    popup.setCurrentIndex(popup.model().index(0, 0))
            else:
                popup = self._completer.popup()
                if popup:
                    popup.hide()
        else:
            popup = self._completer.popup()
            if popup:
                popup.hide()

    def _current_token(self):
        """Return the word at the cursor position."""
        expr = self.calc_expr_edit.toPlainText()
        cursor = self.calc_expr_edit.textCursor().position()
        m = re.search(r'[\w.]*$', expr[:cursor])
        return m.group() if m else ""

    def _set_cursor_pos(self, pos):
        """Set the text cursor to absolute position *pos*."""
        cursor = self.calc_expr_edit.textCursor()
        cursor.setPosition(pos)
        self.calc_expr_edit.setTextCursor(cursor)

    def _reposition_popup(self):
        """Move the already-visible popup to sit just below the cursor."""
        popup = self._completer.popup()
        if popup is None:
            return
        cr = self.calc_expr_edit.cursorRect()
        pos = self.calc_expr_edit.mapToGlobal(cr.bottomLeft())
        popup.move(pos)
        popup.setMinimumWidth(320)
        popup.setMaximumHeight(260)

    def _on_enter_pressed(self):
        """Handle Enter key: if the popup is visible, complete the current
        selection; otherwise trigger calculation, then clear the editor."""
        popup = self._completer.popup()
        if popup and popup.isVisible():
            idx = popup.currentIndex()
            if idx.isValid():
                text = idx.data(Qt.ItemDataRole.DisplayRole)
                if text:
                    popup.hide()
                    self._on_completion_activated(text)
        else:
            self._on_calculate()
            self.calc_expr_edit.clear()

    def _on_popup_activated(self, idx):
        """Handle popup item activation (mouse click / keyboard) — extract
        text from the model index and complete the current token."""
        text = idx.data(Qt.ItemDataRole.DisplayRole)
        if text:
            self._completer.popup().hide()
            self._on_completion_activated(text)

    def _on_completion_activated(self, text):
        """Replace only the current token using cursor operations."""
        if not text:
            return
        self._completing = True
        popup = self._completer.popup()
        if popup:
            popup.hide()

        expr = self.calc_expr_edit.toPlainText()
        cursor_pos = self.calc_expr_edit.textCursor().position()
        prefix = expr[:cursor_pos]
        m = re.search(r'[\w.]*$', prefix)
        token_start = m.start() if m else cursor_pos

        cursor = self.calc_expr_edit.textCursor()
        cursor.setPosition(token_start)
        cursor.setPosition(cursor_pos, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self.calc_expr_edit.setTextCursor(cursor)
        self._completing = False

    # --- Calculator helpers ---
    def _insert_op(self, text):
        cursor = self.calc_expr_edit.textCursor().position()
        current = self.calc_expr_edit.toPlainText()
        new_text = current[:cursor] + text + current[cursor:]
        self.calc_expr_edit.setPlainText(new_text)
        self.calc_expr_edit.setFocus()
        self._set_cursor_pos(cursor + len(text))

    def _on_calculate(self):
        expr = self.calc_expr_edit.toPlainText().strip()
        if not expr:
            QMessageBox.warning(self, "Empty Expression", "Enter an expression first.")
            return
        target = self.calc_target_edit.text().strip() or None
        direction = "row" if self.calc_direction_combo.currentText() == "By Row" else "column"
        self.calculate_requested.emit(expr, target, direction)

    # --- Summarize helpers ---
    def _on_summary_direction_changed(self, text):
        if self._summary_columns:
            self.set_summary_targets(self._summary_columns, self._summary_row_count)

    def _on_summarize(self):
        direction = self.summary_direction.currentText().lower()
        target = self.summary_target.currentText().strip()
        if not target:
            QMessageBox.warning(self, "No Target", "Select a column name or row index.")
            return
        self.summarize_requested.emit(direction, target)

    def set_calc_completions(self, sheets: dict, active_sheet: str):
        """Populate autocomplete with column names and SheetName.ColumnName patterns."""
        from graphx.analysis.calculator import _sanitize
        items = []
        # Function names
        items.extend([
            "log(", "log10(", "log2(", "exp(", "sqrt(", "abs(", "pow(",
            "sin(", "cos(", "tan(", "arcsin(", "arccos(", "arctan(",
        ])
        # Column names from all sheets (use raw names — the evaluator
        # matches against raw column names, not sanitized ones)
        for sheet_name, df in sheets.items():
            s_sheet = _sanitize(sheet_name)
            for col in df.columns:
                col_str = str(col)
                if sheet_name == active_sheet:
                    items.append(col_str)
                ref = f"{s_sheet}.{col_str}"
                if " " not in ref:
                    items.append(ref)
        self._completer_model.setStringList(sorted(set(items)))

    def set_summary_targets(self, columns, row_count):
        """Populate the summary target combo with column names or row indices."""
        self._summary_columns = columns
        self._summary_row_count = row_count
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
