import configparser
import shutil
import sys
import asyncio
import logging
import os
import pathlib
from logging import handlers
from concurrent.futures import ThreadPoolExecutor

import discord
import twitchio
import colorama
import prettify_exceptions


from utils.bot import System
from interface.main2 import Window

sys.path.append(".")
prettify_exceptions.hook()
colorama.init()

__VERSION__ = "0.0.2"


def startup_data():
    print(colorama.Fore.GREEN + "Starting")
    print(colorama.Fore.MAGENTA + f"Bot version: {__VERSION__}")
    print(colorama.Fore.CYAN + f"Python version: {sys.version}")
    print(colorama.Fore.YELLOW + f"Discord.py version: {discord.__version__}")
    print(colorama.Fore.YELLOW + f"TwitchIO version: {twitchio.__version__}")
    print(colorama.Fore.WHITE + "")

def create_paths(path):
    pths = [pathlib.Path(path, "tmp"), pathlib.Path(path, "services"), pathlib.Path(path, "plugins")]
    for p in pths:
        if not p.exists():
            p.mkdir()

    p = pathlib.Path(path, "locale")
    if not p.exists():
        l = window.app.get_resource("locale")
        shutil.copytree(l, p)


if __name__ == "__main__":
    config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
    window = Window()
    pth = window.get_data_location()
    if not pth.exists():
        pth.mkdir()

    p = pathlib.Path(pth, "config.ini")
    new = False
    if not p.exists():
        template = window.app.get_resource("config_template.ini")
        shutil.copy(template, p)
        create_paths(pth)
        new = True

    with open(p, encoding="utf8") as f:
        config.read_file(f)

    logger = logging.getLogger("xlydn")
    dpylog = logging.getLogger("discord")
    tiolog = logging.getLogger("twitchio")
    if config.getboolean("developer", "dev_mode", fallback=False):
        logging.basicConfig()
    else:
        if not pathlib.Path(pth, "log").exists():
            pathlib.Path(pth, "log").mkdir()

        log = pathlib.Path(pth, "log", "xlydn.log")
        handle = handlers.RotatingFileHandler(log, maxBytes=30000)
        log = pathlib.Path(pth, "log", "discord.log")
        dpy_handle = handlers.RotatingFileHandler(log, maxBytes=30000)
        log = pathlib.Path(pth, "log", "twitch.log")
        tio_handle = handlers.RotatingFileHandler(log, maxBytes=30000)

        logger.addHandler(handle)
        dpylog.addHandler(dpy_handle)
        tiolog.addHandler(tio_handle)

    executor = ThreadPoolExecutor(max_workers=config.getint("developer", "max_pool_workers", fallback=3))

    asyncio.get_event_loop().set_default_executor(executor)

    startup_data()

    if "--ci" in sys.argv:
        bot = System(config, window, ci=True)
        # load the modules, but dont actually run the bots
        bot.twitch_bot.load(ci=True)
        bot.discord_bot.load(ci=True)
        bot.loop.run_until_complete(bot.scripts.search_and_load())
        bot.loop.run_until_complete(bot.scripts.unload_all())

    else:
        bot = System(config, window)
        if new:
            window.new()
        else:
            window.normal()
        bot.interface.run()

"https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=vcs989uc111bryinsv1bwps0qdgkis&redirect_uri=https://bot.idevision.net/auth/token&scope=chat:edit+chat:read+whispers:read+whispers:edit+user_read+channel_check_subscription+channel_commercial+channel_editor+channel_subscriptions&force_verify=true"