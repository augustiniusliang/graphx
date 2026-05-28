import sys
import matplotlib
matplotlib.use("QtAgg")

# Configure matplotlib font fallback: default fonts for Latin, SimSun for CJK
matplotlib.rcParams["font.sans-serif"] = [
    "DejaVu Sans", "Liberation Sans", "Arial",
    "SimSun", "Microsoft YaHei", "SimHei",
]
matplotlib.rcParams["axes.unicode_minus"] = False

from PyQt6.QtWidgets import QApplication
from graphx import GraphXApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GraphX")
    window = GraphXApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
