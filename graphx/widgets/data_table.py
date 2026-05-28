from PyQt6.QtCore import QAbstractTableModel, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QApplication,
)


class PandasTableModel(QAbstractTableModel):
    def __init__(self, df=None, parent=None):
        super().__init__(parent)
        self._df = df

    def load_dataframe(self, df):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=None):
        return 0 if self._df is None else len(self._df)

    def columnCount(self, parent=None):
        return 0 if self._df is None else len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            val = self._df.iloc[index.row(), index.column()]
            return str(val)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or self._df is None:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(self._df.index[section])


class DataTableWidget(QWidget):
    column_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.model = PandasTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        layout.addWidget(self.table)

    def _on_header_clicked(self, section):
        if self.model._df is not None and section < len(self.model._df.columns):
            col_name = str(self.model._df.columns[section])
            self.column_clicked.emit(col_name)

    def load_dataframe(self, df):
        self.model.load_dataframe(df)


class DataTableWindow(QWidget):
    """Standalone floating window for the data table."""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Data Table")
        self.resize(800, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table_widget = DataTableWidget(self)
        layout.addWidget(self.table_widget)

    @property
    def column_clicked(self):
        return self.table_widget.column_clicked

    def load_dataframe(self, df):
        self.table_widget.load_dataframe(df)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
