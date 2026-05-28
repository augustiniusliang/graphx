from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QSpinBox, QDialogButtonBox, QFileDialog, QMessageBox,
)
import pandas as pd


class ImportDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Data")
        self.resize(700, 500)
        self._df = None

        layout = QVBoxLayout(self)

        # File path
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Options row
        opts_layout = QHBoxLayout()
        opts_layout.addWidget(QLabel("Sheet:"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.setEnabled(False)
        opts_layout.addWidget(self.sheet_combo)
        opts_layout.addWidget(QLabel("Header row:"))
        self.header_spin = QSpinBox()
        self.header_spin.setValue(0)
        opts_layout.addWidget(self.header_spin)
        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Preview table
        layout.addWidget(QLabel("Preview (first 100 rows):"))
        self.preview_table = QTableWidget()
        layout.addWidget(self.preview_table)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Data File", "",
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not path:
            return
        self.path_edit.setText(path)
        self._preview(path)

    def _preview(self, path):
        try:
            if path.lower().endswith((".xlsx", ".xls")):
                xl = pd.ExcelFile(path)
                self.sheet_combo.clear()
                self.sheet_combo.addItems(xl.sheet_names)
                self.sheet_combo.setEnabled(True)
                self._df = pd.read_excel(path, sheet_name=xl.sheet_names[0], header=self.header_spin.value())
            else:
                self.sheet_combo.setEnabled(False)
                self._df = pd.read_csv(path, header=self.header_spin.value())
            self._show_preview(self._df.head(100))
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _show_preview(self, df):
        self.preview_table.setRowCount(len(df))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(len(df)):
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                item = QTableWidgetItem(str(val) if val is not None else "")
                self.preview_table.setItem(r, c, item)
        self.preview_table.resizeColumnsToContents()

    def _on_accept(self):
        if self._df is not None:
            self.accept()
        else:
            QMessageBox.warning(self, "No Data", "Select a file first.")

    def get_dataframe(self):
        return self._df
