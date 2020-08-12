import threading
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

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
        self.system = system
        self.app = QtWidgets.QApplication([])
        self.window = QtWidgets.QTabWidget()
        self.window.setWindowTitle("Xlydn")
        self.thread = None

    def connectionstab(self):
        self.connections = QtWidgets.QWidget()
        self.window.addTab(self.connections, "Connections")
        layout = QtWidgets.QVBoxLayout()
        self.connections.setLayout(layout)

        # set up the discord bot token box
        stackV = QtWidgets.QVBoxLayout()
        stackV.addWidget(QtWidgets.QLabel(self.system.locale("Discord bot token")))
        self.discordtoken = QtWidgets.QLineEdit(self.system.config.get("tokens", "discord_bot", fallback=""))
        stackV.addWidget(self.discordtoken)
        stackH = QtWidgets.QHBoxLayout()
        self.discordtoken_connector = QtWidgets.QPushButton(self.system.locale("Connect"))
        self.discordtoken_connector.clicked.connect(self.token_connect_discord)
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
        self.bottoken = QtWidgets.QLineEdit(self.system.config.get("tokens", "twitch_bot", fallback=""))
        stackV.addWidget(self.bottoken)
        stackH = QtWidgets.QHBoxLayout()
        self.bottoken_connector = QtWidgets.QPushButton(self.system.locale("Connect"))
        self.bottoken_connector.clicked.connect(self.token_connect_bot)
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
        self.streamertoken = QtWidgets.QLineEdit(self.system.config.get("tokens", "twitch_streamer", fallback=""))
        stackV.addWidget(self.streamertoken)
        stackH = QtWidgets.QHBoxLayout()
        self.streamertoken_connector = QtWidgets.QPushButton(self.system.locale("Connect"))
        self.streamertoken_connector.clicked.connect(self.token_connect_streamer)
        stackH.addWidget(self.streamertoken_connector)
        self.streamertoken_disconnector = QtWidgets.QPushButton(self.system.locale("Disconnect"))
        self.streamertoken_disconnector.clicked.connect(self.token_disconnect_streamer)
        stackH.addWidget(self.streamertoken_disconnector)
        stackV.addLayout(stackH)

        layout.addLayout(stackV)
        layout.addSpacerItem(QtWidgets.QSpacerItem(1, 30))

    def token_connect_discord(self):
        self.discordtoken_connector.setEnabled(False)
        self.discordtoken_disconnector.setEnabled(True)
        self.discordtoken.setEnabled(False)
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
        self.system.connect_twitch_streamer()

    def token_disconnect_streamer(self):
        self.streamertoken_connector.setEnabled(True)
        self.streamertoken_disconnector.setEnabled(False)
        self.streamertoken.setEnabled(True)
        self.system.disconnect_twitch_streamer()

    def _run(self):
        self.window.show()
        try:
            self.app.exec()
        except:
            pass

    async def run(self):
        if self.thread is not None and self.thread.is_alive():
            self.app.close()

        self.thread = threading.Thread(target=self._run)

    def crash(self):
        try:
            self.app.close()
        except:
            pass

        if self.system.alive:
            self.system.alive = False

        win = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        lbl = QtWidgets.QLabel(self.system.locale("Whoops! Looks like the bot has crashed!"))
        lbl2 = QtWidgets.QLabel()
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
        win.setStyleSheet("background-color: black;")
        win.show()
        self.app.exec()
