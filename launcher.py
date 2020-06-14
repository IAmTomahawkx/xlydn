import configparser
import sys
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import discord
import twitchio
import colorama

from utils.bot import System

colorama.init()

__VERSION__ = "0.0.1 unstable"

def run_forever(**kwargs):
    bot = System(config, **kwargs)
    bot.run()

config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
config.read("config.ini")

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
    run_forever()

"https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=vcs989uc111bryinsv1bwps0qdgkis&redirect_uri=https://bot.idevision.net/auth/token&scope=chat:edit+chat:read+whispers:read+whispers:edit+user_read+channel_check_subscription+channel_commercial+channel_editor+channel_subscriptions&force_verify=true"