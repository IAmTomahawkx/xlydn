import configparser
import sys
import asyncio
import logging
import os
from logging import handlers
from concurrent.futures import ThreadPoolExecutor

import discord
import twitchio
import colorama
import prettify_exceptions


from utils.bot import System

prettify_exceptions.hook()
colorama.init()

__VERSION__ = "0.0.1"

config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
config.read("config.ini")

logger = logging.getLogger("xlydn")
dpylog = logging.getLogger("discord.py")
tiolog = logging.getLogger("twitchio")
if config.getboolean("developer", "dev_mode", fallback=False):
    logging.basicConfig()
else:
    if not os.path.exists("log"):
        os.mkdir("./log")

    handle = handlers.RotatingFileHandler("log/xlydn.log", maxBytes=30000)
    dpy_handle = handlers.RotatingFileHandler("log/discord.log", maxBytes=30000)
    tio_handle = handlers.RotatingFileHandler("log/twitch.log", maxBytes=30000)


executor = ThreadPoolExecutor(max_workers=config.getint("developer", "max_pool_workers", fallback=3))

asyncio.get_event_loop().set_default_executor(executor)

def startup_data():
    print(colorama.Fore.GREEN + "Starting")
    print(colorama.Fore.MAGENTA + f"Bot version: {__VERSION__}")
    print(colorama.Fore.CYAN + f"Python version: {sys.version}")
    print(colorama.Fore.YELLOW + f"Discord.py version: {discord.__version__}")
    print(colorama.Fore.YELLOW + f"TwitchIO version: {twitchio.__version__}")
    print(colorama.Fore.WHITE + "")


if __name__ == "__main__":
    startup_data()
    if "--ci" in sys.argv:
        bot = System(config, ci=True)
        # load the modules, but dont actually run the bots
        bot.twitch_bot.load(ci=True)
        bot.discord_bot.load(ci=True)

    else:
        bot = System(config)
        bot.run()

"https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=vcs989uc111bryinsv1bwps0qdgkis&redirect_uri=https://bot.idevision.net/auth/token&scope=chat:edit+chat:read+whispers:read+whispers:edit+user_read+channel_check_subscription+channel_commercial+channel_editor+channel_subscriptions&force_verify=true"