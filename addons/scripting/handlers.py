import os
import importlib
import json
import logging
import traceback # use traceback instead of prettify.py
from typing import Optional

from discord.ext import commands as dpy_commands
import discord as dpy
import twitchio
from twitchio.ext import commands as tio_commands

from utils import commands, signals, common
from . import helpers

logger = logging.getLogger("xlydn.scripting")

class ScriptManager:
    def __init__(self, system):
        self.system = system
        self.scripts = {}
        self.errors = []
        self.logs = {}

    async def search_and_load(self):
        scripts_path = os.path.abspath(os.path.join(".", "scripts"))
        if not os.path.exists(scripts_path) and not os.path.isdir(scripts_path):
            os.mkdir(scripts_path)

        for dirname in os.listdir(scripts_path):
            pth = os.path.join(scripts_path, dirname)
            if not os.path.isdir(pth):
                continue

            files = os.listdir(pth)
            if "script.json" not in files:
                logger.debug(f"Missing script.json; skipping load of {pth}")
                continue

            try:
                await self.load_script(pth)
            except ValueError as e:
                self.errors.append((pth, "".join(traceback.format_exception(type(e), e, e.__traceback__))))

    async def load_script(self, directory):
        handle = ScriptHandler(directory, self, self.system.loop)
        await handle.load()
        self.scripts[handle.name] = handle
        logger.debug(f"Loaded script {handle.name} in directory {directory}")

    def reload_script(self, name):
        if name not in self.scripts:
            raise ValueError(f"Script named {name} not found")


class ScriptHandler:
    def __init__(self, directory, manager, loop):
        self.directory = directory
        self.dispatcher = signals.MultiSignal(loop=loop, strict_async=True)
        self.__manager = manager
        self.system = manager.system
        self.config = {}
        self.enabled = False
        self.module = None
        self.name = None

    async def load(self):
        config_pth = os.path.join("scripts", self.directory, "script.json")
        if not os.path.exists(config_pth):
            raise FileNotFoundError(f"`{self.directory}` is missing a script.json")

        try:
            with open(config_pth) as f:
                config = self.config = json.load(f)

        except:
            raise ValueError("failed to load the script.json")

        self.check_config()

        identifier = config["identifier"]
        self.identifier = identifier
        self.name = config['name']

        if identifier in self.__manager.scripts:
            raise ValueError(f"Bundle identifier already exists: {identifier}")

        find = await self.__manager.db.fetchrow("SELECT scriptname, state from scripts where identifier = ?", identifier)
        if not find:
            await self.__manager.db.execute("INSERT INTO scripts VALUES (?,?,0)", identifier, self.name)

        try:
            self.module = importlib.import_module(f"scripts.{self.directory}.{config['loader']}")
        except ModuleNotFoundError:
            raise ValueError(f"script.json :: invalid loader key")

        except Exception as e:
            raise ValueError(f"failed to load {self.name}") from e

    async def enable(self):
        self.enabled = True
        self.dispatcher.emit("state_update", True)

    async def disable(self):
        self.enabled = False
        self.dispatcher.emit("state_update", False)

    async def message_recieved(self, event_name: str, *args, **kwargs):
        self.dispatcher.emit(event_name, *args, **kwargs)

    def check_config(self):
        cfg = self.config
        names = ["name", "description", "identifier", "version", "author", "loader"]
        for name in names:
            if name not in cfg or not cfg.get(name):
                raise ValueError(f"script.json :: missing or invalid {name} key")

class Communicator:
    """
    the class that actually interacts with the script
    """
    def __init__(self, handle: ScriptHandler):
        self.dispatcher = handle.dispatcher
        self.__system = handle.system
        self._module = None
        self.__injections = {}

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, arg):
        self._module = arg

    async def get_user(self, *,
                 id: int = None,
                 discord_id: int = None,
                 discord_name: str = None,
                 twitch_name: str = None
                 ) -> Optional[common.User]:
        """fetch a user by their discord id, their discord name, or their twitch name"""
        if id:
            return await self.__system.get_user(id)

        elif discord_id:
            return await self.__system.get_user_discord_id(discord_id)

        elif discord_name:
            usr = self.__system.discord_bot.guilds[0].get_member_named(discord_name)
            if not usr:
                return None

            return await self.__system.get_user_discord_id(usr.id)

        elif twitch_name:
            return await self.__system.get_user_twitch_name(twitch_name)

        else:
            raise ValueError("either id, discord_id, discord_name, or twitch_name must be provided.")

    def inject(self, injection: helpers.Injection):
        if not isinstance(injection, helpers.Injection):
            raise ValueError(f"expected Injection, got {injection!r}")

        name = injection.__class__.__name__
        if name in self.__injections:
            raise ValueError("An injector with this name already exists")

        injection._inject(self) # noqa
        self.__injections[name] = injection

    def eject(self, injection: str):
        if injection not in self.__injections:
            raise ValueError("This injector has not been injected")

        injection = self.__injections[injection]
        injection._eject(self) # noqa
