"""Excel synchronisation via COM automation.

Writes dataframe sheets to a temp .xlsx file and reloads the workbook in
Excel without visual flicker (ScreenUpdating suppressed, active sheet preserved).
"""

import os
import pandas as pd


class ExcelSync:
    """Writes sheet data to an Excel file and reloads it in Excel via COM."""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def sync(self, path: str, sheets: dict[str, pd.DataFrame],
             reload_excel: bool = True):
        """Write all *sheets* to *path*.

        When *reload_excel* is True the Excel workbook is closed and
        re-opened with ``ScreenUpdating`` suppressed so there is no flicker.
        """
        if not path or not sheets:
            return

        active_sheet = None
        if reload_excel:
            active_sheet = self._close_workbook(path)

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, sdf in sheets.items():
                sdf.to_excel(writer, sheet_name=name, index=False)

        if reload_excel:
            self._open_workbook(path, active_sheet)

    # ------------------------------------------------------------------
    # COM internals
    # ------------------------------------------------------------------

    @staticmethod
    def _init_com():
        import pythoncom
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

    def _get_excel_app(self):
        """Return the running Excel Application, or start a new one."""
        self._init_com()
        import win32com.client
        try:
            return win32com.client.GetObject(Class="Excel.Application")
        except Exception:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            return excel

    def _find_workbook(self, excel, path: str):
        """Return the workbook whose *FullName* matches *path*, or None."""
        norm = os.path.normpath(path)
        for wb in excel.Workbooks:
            try:
                if os.path.normpath(wb.FullName) == norm:
                    return wb
            except Exception:
                continue
        return None

    def _close_workbook(self, path: str) -> str | None:
        """Close the workbook at *path* in Excel.

        Returns the name of the previously active sheet so it can be
        restored after re-opening, or None if the workbook wasn't found.
        """
        self._init_com()
        import win32com.client
        try:
            excel = win32com.client.GetObject(Class="Excel.Application")
        except Exception:
            return None

        wb = self._find_workbook(excel, path)
        if wb is None:
            return None

        try:
            active_sheet = wb.ActiveSheet.Name
        except Exception:
            active_sheet = None

        try:
            excel.ScreenUpdating = False
        except Exception:
            pass

        try:
            wb.Close(SaveChanges=False)
        except Exception:
            pass

        return active_sheet

    def _open_workbook(self, path: str, active_sheet: str | None = None):
        """Open *path* in Excel, restoring *active_sheet* if given."""
        excel = self._get_excel_app()
        wb = excel.Workbooks.Open(path)

        if active_sheet:
            try:
                for sheet in wb.Sheets:
                    if sheet.Name == active_sheet:
                        sheet.Activate()
                        break
            except Exception:
                pass

        try:
            excel.ScreenUpdating = True
        except Exception:
            pass

        excel.Visible = True
