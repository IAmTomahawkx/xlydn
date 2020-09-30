import os
import importlib
import json
import sys
import asyncio
import logging
import inspect
import traceback # use traceback instead of prettify.py
from typing import Optional

from discord.ext import commands as dpy_commands
import discord as dpy
import twitchio
from twitchio.ext import commands as tio_commands

from utils import commands, signals, common
from . import helpers, monitor

logger = logging.getLogger("xlydn.scripting")

class ScriptManager:
    def __init__(self, system):
        self.system = system
        self.scripts = {}
        self.errors = []
        self.logs = {}
        self.monitor = monitor.StackMonitor(system)
        self.monitor.start()

    async def search_and_load(self):
        scripts_path = os.path.abspath(os.path.join(".", "scripts"))
        if not os.path.exists(scripts_path) and not os.path.isdir(scripts_path):
            os.mkdir(scripts_path)

        for dirname in os.listdir(scripts_path):
            pth = os.path.join("scripts", dirname)
            if not os.path.isdir(pth):
                continue

            logger.debug(f"Scanning path {pth}")

            files = os.listdir(pth)
            if "script.json" not in files:
                logger.info(f"Missing script.json; skipping load of {pth}")
                continue

            try:
                await self.load_script(dirname)
            except ValueError as e:
                logger.debug(f"failed to load script at {pth}", exc_info=e)
                self.errors.append((pth, "".join(traceback.format_exception(type(e), e, e.__traceback__))))

    async def reload_all_scripts(self):
        logger.debug("Reloading all scripts : start unload")
        await self.unload_all()
        logger.debug("Reloading all scripts : start load")
        await self.search_and_load()
        logger.debug("Reloading all scripts : complete")

    async def load_script(self, directory) -> "ScriptHandler":
        handle = ScriptHandler(directory, self, self.system.loop)
        await handle.load()
        self.scripts[handle.identifier] = handle
        logger.debug(f"Loaded script {handle.name} in directory scripts/{directory}")
        return handle

    async def reload_script(self, identifier):
        if identifier not in self.scripts:
            raise ValueError(f"Script named {identifier} not found")

        script = self.scripts[identifier]
        logger.debug(f"Reloading script {script.name}")

        script.will_unload()
        await asyncio.sleep(1) # give time for the loop to run the emitters
        script.unload()
        del sys.modules[script.module_path]
        del self.scripts[identifier]

        directory = script.directory
        del script
        script = await self.load_script(directory)
        await script.load()

    async def unload_all(self):
        for handler in self.scripts.values():
            handler.will_unload() # notify the scripts that theyre going to be ejected

        for _ in range(5):
            await asyncio.sleep(0)
            # run through the loop a couple times to give the emitted coroutines a chance to run before teardown

        for handler in self.scripts.values():
            await handler.unload()

        self.scripts.clear()

    def dispatch_event(self, event_name, *args, **kwargs):
        for script in self.scripts.values():
            script.handle_dispatch(event_name, *args, **kwargs)


class ScriptHandler:
    def __init__(self, directory, manager, loop):
        self.directory = directory
        self.dispatcher = signals.MultiSignal(loop=loop, strict_async=True)
        self.__manager = manager
        self.system = manager.system
        self.config = {}
        self.enabled = False
        self.module = None
        self.module_path = None
        self.name = None
        self.author = None
        self.version = None
        self.communicator = Communicator(self)

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
        self.author = config['author']
        self.version = config['version']

        if identifier in self.__manager.scripts:
            raise ValueError(f"Bundle identifier already exists: {identifier}")

        find = await self.__manager.system.db.fetchrow("SELECT scriptname, state from scripts where identifier = ?", identifier)
        if not find:
            await self.__manager.system.db.execute("INSERT INTO scripts VALUES (?,?,0)", identifier, self.name)
        else:
            self.enabled = bool(find[1])

        try:
            self.module_path = f"scripts.{self.directory}.{config['loader'].replace('.py', '')}"
            self.module = importlib.import_module(self.module_path)
            if not hasattr(self.module, "setup") or not inspect.isfunction(self.module.setup):
                raise ValueError(f"{self.identifier} :: load :: missing setup function")

            self.module.setup(self.communicator)
        except ModuleNotFoundError:
            raise ValueError(f"script.json :: invalid loader key")

        except Exception as e:
            raise ValueError(f"failed to load {self.name}") from e

    async def enable(self):
        self.enabled = True
        await self.system.db.execute("UPDATE scripts SET state = true WHERE identifier = ?", self.identifier)
        self.dispatcher.emit("state_update", True)

    async def disable(self):
        self.enabled = False
        await self.system.db.execute("UPDATE scripts SET state = false WHERE identifier = ?", self.identifier)
        self.dispatcher.emit("state_update", False)

    def will_unload(self):
        self.dispatcher.emit("will_unload")

    async def unload(self):
        self.communicator._eject_all() # noqa

    def handle_dispatch(self, event_name: str, *args, **kwargs):
        if self.enabled:
            try:
                self.dispatcher.emit(event_name, *args, **kwargs)
            except Exception as e:
                logger.debug(f"listener error in script {self.name}::{self.identifier}", exc_info=e)

    async def wait_for(self, event, *, check, timeout=60):
        pass

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
        self.discord_user = handle.system.discord_bot.user

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, arg):
        self._module = arg

    def get_channel(self, channel_id: int) -> Optional[dpy.TextChannel]:
        return self.__system.discord_bot.guilds[0].get_channel(channel_id) # this assumes were only in one guild

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
        del self.__injections[injection]

    def _eject_all(self):
        for name, klass in self.__injections.items():
            klass._eject(self) # noqa

        self.__injections.clear()
