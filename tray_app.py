"""
PyQt5 system tray app for FBGroupPosterPro.
Starts the aiohttp backend server and opens browser to localhost:3080.
"""

import sys
import threading
import webbrowser
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QSystemTrayIcon

APP_NAME = "FBGroupPosterPro"
SERVER_PORT = 3080
BASE_DIR = Path(__file__).parent


def start_server():
    """Start aiohttp server in background thread."""
    sys.path.insert(0, str(BASE_DIR))
    from backend.server import create_app
    from aiohttp import web

    app = create_app()
    web.run_app(app, host="127.0.0.1", port=SERVER_PORT, print=None)


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # System tray
        self.tray = QSystemTrayIcon()
        icon_path = BASE_DIR / "icons" / "icon.png"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))

        # Context menu
        menu = QMenu()
        open_action = QAction("開啟控制台")
        open_action.triggered.connect(self.open_browser)
        quit_action = QAction("退出")
        quit_action.triggered.connect(self.quit)

        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.show()

        # Start server in background
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

        # Open browser after 2s startup delay
        QTimer.singleShot(2000, self.open_browser)

    def open_browser(self):
        webbrowser.open(f"http://localhost:{SERVER_PORT}")

    def quit(self):
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    TrayApp().run()
