import asyncio
import pathlib
import threading
import logging
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from fbs_runtime.platform import name as os_name

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

class NewBot(QtWidgets.QWidget):
    def __init__(self, main):
        super(NewBot, self).__init__(main)
        self.add_items()

    def add_items(self):
        self.lay = QtWidgets.QVBoxLayout()
        f = QtGui.QFont()
        f.setBold(True)
        f.setPixelSize(30)

        title = QtWidgets.QLabel("Welcome to xlydn", self)
        title.setFont(f)
        self.lay.addWidget(title)
        panels = [
            "Hey there, thanks for using my bot!\nThis little welcome window doesn't do much, but it will guide you through the process of setting up xlydn.\n"
            "The first thing to note is that this bot is very much in development. This UI doesn't do much, it will only help you manage your credentials.\n"
            "In the future, the web dashboard will let you manage your plugins, commands, and so forth. For now however, we're stuck with discord and twitch commands.",
            "To get started, head on over to https://discord.com/developers and create an application. Name it, open it, and select the Bot tab on the left.\n"
            "Click create a bot, confirm, and then copy the OAuth token.\nClick the Connections tab of this window, and paste that token into the Discord Bot tab.",
            "Next, head on over to https://bot.idevision.net, and press Get a Token. Log in with your twitch account, and then copy the given token into the "
            "Twitch Streamer section of the Connections tab.",
            "If you wish to use a different account as your bot account, repeat this process, but log in with your bot account instead of your streaming account,"
            " and copy this token into the Twitch Bot section of the Connections tab.\nIf you wish to use your streaming account as the bot account too, "
            "just copy the token from the Twitch Streamer section, and paste it into the Twitch Bot section.",
            "Now you should invite your new discord bot into your discord server!\n"
            "Go back to your application at https://discord.com/developers, and click the OAuth tab. Scroll to the bottom, and select the bot scope.\n"
            "Pick the permissions you wish to grant your bot, and copy the link the website gives you. Go to this link, and invite it to your server!",
            "Now, click connect on all 3 sections in the connections tab, and your bot should connect to the xlydn server, discord, and twitch.",
            "The default prefix is '!', test out your bot by using the !help command on discord! If you have any troubles, feel free to ask in my discord server. "
            "https://discord.gg/cEAxG8A"
        ]
        for p in panels:
            l = QtWidgets.QLabel(p, self)
            l.setOpenExternalLinks(True)
            self.lay.addWidget(l)


class Window:
    def __init__(self):
        self.crashing = False
        self.system = None
        self.app = App()
        self.main = QtWidgets.QMainWindow()
        self.window = Widget(self.main)
        self.window.error.connect(self.crash_handle)
        self.main.setWindowTitle("Xlydn")
        self.main.setCentralWidget(self.window)
        self.thread = None

    def home_tab(self):
        self.home = QtWidgets.QWidget(self.window)

    def new(self):
        self.new_bot = NewBot(self.main)
        self.window.addTab(self.new_bot, "Welcome")
        self.connections_tab()

    def normal(self):
        self.connections_tab()

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

    async def capture_refresh(self, streamer: bool):
        try:
            if streamer:
                token = self.system.config.get("tokens", "twitch_streamer_token")
            else:
                token = self.system.config.get("tokens", "twitch_bot_token")

            refresh = await self.system.api.get_refresh_token(token)
            if refresh is None:
                raise ValueError("Api rejected us")

            self.system.config.set("tokens", f"twitch_{'streamer' if streamer else 'bot'}_refresh", refresh)
            logger.debug(f"Captured refresh token! streamer: {streamer}")
        except Exception as e:
            logger.exception(f"Failed to capture refresh! streamer: {streamer}", exc_info=e)

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
        asyncio.run_coroutine_threadsafe(self.capture_refresh(False), self.system.loop)
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
        asyncio.run_coroutine_threadsafe(self.capture_refresh(True), self.system.loop)
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

    @staticmethod
    def get_data_location():
        name = os_name()
        if name == "Windows":
            return pathlib.Path(os.getenv("APPDATA"), "Xlydn")
        elif name == "Linux":
            return "~/Xlydn/"
        elif name == "Mac":
            return "~/Library/Application Support/Xlydn"

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
