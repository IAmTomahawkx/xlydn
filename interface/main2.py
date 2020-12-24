import asyncio
import threading
import logging
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from fbs_runtime.application_context.PyQt5 import ApplicationContext

logger = logging.getLogger("xlydn.interface")

class App(ApplicationContext):
    @property
    def excepthook(self):
        return None

class Widget(QtWidgets.QTabWidget):
    error = QtCore.pyqtSignal()

class EmitterString:
    def __init__(self, initial=""):
        self.__string = initial
        self.__emitters = []

    def add_emitter(self, fn):
        self.__emitters.append(fn)

    def _run_emitters(self):
        for emitter in self.__emitters:
            emitter(self.__string)

    def get(self):
        return self.__string

    def set(self, rep):
        self.__string = rep
        self._run_emitters()

    def __getitem__(self, item):
        return self.__string.__getitem__(item)

    def __iadd__(self, other):
        self.__string += other
        self._run_emitters()

class Window:
    def __init__(self, system):
        self.crashing = False
        self.system = system
        self.app = App()
        self.main = QtWidgets.QMainWindow()
        self.window = Widget(self.main)
        self.window.error.connect(self.crash_handle)
        self.main.setWindowTitle("Xlydn")
        self.main.setCentralWidget(self.window)
        self.thread = None
        self.connections_tab()

    def home_tab(self):
        self.home = QtWidgets.QWidget(self.window)

    def connections_tab(self):
        self.connections = QtWidgets.QWidget(self.window)
        self.window.addTab(self.connections, "Connections")
        layout = QtWidgets.QVBoxLayout()
        self.connections.setLayout(layout)

        # set up the discord bot token box
        stackV = QtWidgets.QVBoxLayout()
        stackV.addWidget(QtWidgets.QLabel(self.system.locale("Discord bot token")))
        self.discordtoken = QtWidgets.QLineEdit(self.system.config.get("tokens", "discord_bot", fallback=""))
        self.discordtoken.setEnabled(False)
        stackV.addWidget(self.discordtoken)
        stackH = QtWidgets.QHBoxLayout()
        self.discordtoken_connector = QtWidgets.QPushButton(self.system.locale("Connect"))
        self.discordtoken_connector.clicked.connect(self.token_connect_discord)
        self.discordtoken_connector.setEnabled(False)
        stackH.addWidget(self.discordtoken_connector)
        self.discordtoken_disconnector = QtWidgets.QPushButton(self.system.locale("Disconnect"))
        self.discordtoken_disconnector.clicked.connect(self.token_disconnect_discord)
        stackH.addWidget(self.discordtoken_disconnector)
        stackV.addLayout(stackH)

        layout.addLayout(stackV)
        layout.addSpacerItem(QtWidgets.QSpacerItem(1, 30))

        # repeat for twitch bot
        stackV = QtWidgets.QVBoxLayout()
        stackV.addWidget(QtWidgets.QLabel(self.system.locale("Twitch bot token")))
        self.bottoken = QtWidgets.QLineEdit(self.system.config.get("tokens", "twitch_bot_token", fallback=""))
        self.bottoken.setEnabled(False)
        stackV.addWidget(self.bottoken)
        stackH = QtWidgets.QHBoxLayout()
        self.bottoken_connector = QtWidgets.QPushButton(self.system.locale("Connect"))
        self.bottoken_connector.clicked.connect(self.token_connect_bot)
        self.bottoken_connector.setEnabled(False)
        stackH.addWidget(self.bottoken_connector)
        self.bottoken_disconnector = QtWidgets.QPushButton(self.system.locale("Disconnect"))
        self.bottoken_disconnector.clicked.connect(self.token_disconnect_bot)
        stackH.addWidget(self.bottoken_disconnector)
        stackV.addLayout(stackH)

        layout.addLayout(stackV)
        layout.addSpacerItem(QtWidgets.QSpacerItem(1, 30))

        # repeat for twitch streamer
        stackV = QtWidgets.QVBoxLayout()
        stackV.addWidget(QtWidgets.QLabel(self.system.locale("Twitch streamer token")))
        self.streamertoken = QtWidgets.QLineEdit(self.system.config.get("tokens", "twitch_streamer_token", fallback=""))
        self.streamertoken.setEnabled(False)
        stackV.addWidget(self.streamertoken)
        stackH = QtWidgets.QHBoxLayout()
        self.streamertoken_connector = QtWidgets.QPushButton(self.system.locale("Connect"))
        self.streamertoken_connector.clicked.connect(self.token_connect_streamer)
        stackH.addWidget(self.streamertoken_connector)
        self.streamertoken_disconnector = QtWidgets.QPushButton(self.system.locale("Disconnect"))
        self.streamertoken_disconnector.clicked.connect(self.token_disconnect_streamer)
        self.streamertoken_connector.setEnabled(False)
        stackH.addWidget(self.streamertoken_disconnector)
        stackV.addLayout(stackH)

        layout.addLayout(stackV)
        layout.addSpacerItem(QtWidgets.QSpacerItem(1, 30))

    def token_connect_discord(self):
        self.discordtoken_connector.setEnabled(False)
        self.discordtoken_disconnector.setEnabled(True)
        self.discordtoken.setEnabled(False)
        self.system.config.set("tokens", "discord_bot", self.discordtoken.text())
        self.system.connect_discord_bot()

    def token_disconnect_discord(self):
        self.discordtoken_connector.setEnabled(True)
        self.discordtoken_disconnector.setEnabled(False)
        self.discordtoken.setEnabled(True)
        self.system.disconnect_discord_bot()

    def token_connect_bot(self):
        self.bottoken_connector.setEnabled(False)
        self.bottoken_disconnector.setEnabled(True)
        self.bottoken.setEnabled(False)
        self.system.config.set("tokens", "twitch_bot_token", self.bottoken.text())
        self.system.connect_twitch_bot()

    def token_disconnect_bot(self):
        self.bottoken_connector.setEnabled(True)
        self.bottoken_disconnector.setEnabled(False)
        self.bottoken.setEnabled(True)
        self.system.disconnect_twitch_bot()

    def token_connect_streamer(self):
        self.streamertoken_connector.setEnabled(False)
        self.streamertoken_disconnector.setEnabled(True)
        self.streamertoken.setEnabled(False)
        self.system.config.set("tokens", "twitch_streamer_token", self.streamertoken.text())
        self.system.connect_twitch_streamer()

    def token_disconnect_streamer(self):
        self.streamertoken_connector.setEnabled(True)
        self.streamertoken_disconnector.setEnabled(False)
        self.streamertoken.setEnabled(True)
        self.system.disconnect_twitch_streamer()

    def _run(self):
        self.main.show()
        try:
            self.app.app.exec()
        except Exception as e:
            logger.exception("Main window has crashed, details below", exc_info=e)
            self.crash()
        finally:
            if not self.crashing:
                asyncio.run_coroutine_threadsafe(self.system.close(), self.system.loop)

    def run(self):
        if self.thread is not None and self.thread.is_alive():
            raise ValueError

        self.thread = threading.Thread(target=self.system.run)
        self.thread.start()
        self._run()

    def crash(self):
        if self.crashing:
            self.crash_handle()
            return

        logger.error("Entering crash panic! Attempting a clean shutdown")
        async def _wrap():
            try:
                await self.system.close()
            except Exception as e:
                logger.exception("Failed to cleanly shut down: aborting!", exc_info=e)
            else:
                logger.warning("Confirm clean shutdown from crash panic")
            finally:
                self.system.loop.stop()

        self.crashing = True
        asyncio.run_coroutine_threadsafe(_wrap(), self.system.loop)
        self.window.error.emit()

    def _crashing(self):
        self.crash_handle()

    def crash_handle(self):
        win = self.crash_screen = QtWidgets.QWidget()
        self.main.setCentralWidget(win)
        self.main.resize(QtCore.QSize(100, 100))
        win.setStyleSheet("QWidget {background-color: black; } Qlabel { color: white; }")
        layout = QtWidgets.QVBoxLayout(win)
        #layout.setSpacing(0)
        lbl = QtWidgets.QLabel(self.system.locale("Whoops! Looks like the bot has crashed!"), win)
        lbl2 = QtWidgets.QLabel(win)
        lbl.setAlignment(Qt.AlignCenter)
        f = QtGui.QFont()
        f.setBold(True)
        f.setPixelSize(30)
        lbl.setStyleSheet("color: white;")
        lbl.setFont(f)
        pic = QtGui.QPixmap(os.path.join("assets", "broke.jpg"))
        lbl2.setPixmap(pic)
        layout.addWidget(lbl)
        layout.addWidget(lbl2)
        win.setLayout(layout)
