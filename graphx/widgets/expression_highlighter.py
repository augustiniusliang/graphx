"""Syntax highlighter for the calculator expression editor."""

import re
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


_FUNCTION_NAMES = [
    "log", "log10", "log2", "exp", "sqrt", "abs", "pow",
    "sin", "cos", "tan", "arcsin", "arccos", "arctan",
]

# -- colour palette --
_FUNC_COLOR = "#0066CC"
_NUM_COLOR = "#098658"
_OP_COLOR = "#888888"
_COL_COLOR = "#800000"
_CONST_COLOR = "#800080"
_PAREN_COLOR = "#333333"
_NP_COLOR = "#0066CC"


def _fmt(hex_color: str, *, bold: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(hex_color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    return f


class ExpressionHighlighter(QSyntaxHighlighter):
    """Regex-based syntax highlighter for calculator expressions.

    Applies layered rules — later rules override earlier ones on overlap.
    """

    def __init__(self, document):
        super().__init__(document)
        # Rules ordered lowest-priority first
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = [
            (re.compile(r"\b\w[\w.]*\b"), _fmt(_COL_COLOR)),
            (re.compile(r"\b\d+\.?\d*(?:[eE][+-]?\d+)?\b"), _fmt(_NUM_COLOR)),
            (re.compile(r"[+\-*/]"), _fmt(_OP_COLOR)),
            (re.compile(r"[()\[\]{}]"), _fmt(_PAREN_COLOR)),
            (re.compile(r"\bpi\b"), _fmt(_CONST_COLOR)),
            (re.compile(r"\be\b"), _fmt(_CONST_COLOR)),
            (re.compile(r"\bnp\b"), _fmt(_NP_COLOR)),
            (re.compile(
                r"\b(?:" + "|".join(_FUNCTION_NAMES) + r")\b"
            ), _fmt(_FUNC_COLOR, bold=True)),
        ]

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
