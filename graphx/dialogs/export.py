from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QCheckBox, QDialogButtonBox,
    QFileDialog,
)


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Plot")

        layout = QVBoxLayout(self)

        # Format
        layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "SVG", "PDF"])
        layout.addWidget(self.format_combo)

        # DPI (only relevant for PNG)
        layout.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        layout.addWidget(self.dpi_spin)

        # Transparent background
        self.transparent_check = QCheckBox("Transparent background")
        layout.addWidget(self.transparent_check)

        # File path
        layout.addWidget(QLabel("Save to:"))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_browse(self):
        fmt = self.format_combo.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot As", "",
            f"{fmt.upper()} (*.{fmt})"
        )
        if path:
            self.path_edit.setText(path)

    def get_export_config(self):
        return {
            "path": self.path_edit.text(),
            "format": self.format_combo.currentText().lower(),
            "dpi": self.dpi_spin.value(),
            "transparent": self.transparent_check.isChecked(),
        }
