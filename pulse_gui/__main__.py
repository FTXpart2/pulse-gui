"""Entry point: python -m pulse_gui"""

import sys

from PyQt5 import QtWidgets

from pulse_gui.main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Pulse-UI")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
