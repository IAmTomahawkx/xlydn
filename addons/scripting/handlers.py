import os
import importlib
import sys
import asyncio
import logging
import inspect
import traceback # use traceback instead of prettify.py
from typing import Optional
try:
    import orjson as json
except:
    import json

import aiosqlite3
import discord as dpy
import twitchio as tio
from discord.ext.commands.view import StringView

from utils import signals, common, db
from . import helpers, monitor, models

logger = logging.getLogger("xlydn.scripting")

class ScriptDB(db.Database):
    def __init__(self):
        self.connection = None
        self.lock = asyncio.Lock()

    async def setup(self):
        self.connection = await aiosqlite3.connect(":memory:")

    async def _connect_script(self, name, file):
        await self.execute("ATTACH DATABASE ? AS ?;", file, name)

    async def _detach_script(self, name):
        await self.execute("DETACH DATABASE ?", name)


class ScriptManager:
    def __init__(self, system):
        self.system = system
        self.scripts = {}
        self.errors = []
        self.logs = {}
        self.monitor = monitor.StackMonitor(system)
        self.monitor.start()
        self.db = ScriptDB()

    async def handle_gateway_update(self, msg):
        pass

    async def handle_update_requested(self, msg):
        pass

    async def push_spec(self):
        data = {
            "op": 6,
            "d": [
                script.get_spec() for script in self.scripts.values()
            ]
        }

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
        await script.unload()
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

    def dispatch_event(self, event_name, *args, platform=None, **kwargs):
        if event_name == "message":
            if isinstance(args[0], dpy.Message):
                msg = models.PartialMessage.from_discord(args[0])

            else:
                msg = models.PartialMessage.from_twitch(args[0])

            args = msg,

        for script in self.scripts.values():
            script.handle_dispatch(event_name, *args, **kwargs)


class ScriptHandler:
    def __init__(self, directory: str, manager: ScriptManager, loop: asyncio.AbstractEventLoop):
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

        self.dispatcher.add_listener("message", self.find_commands_on_message)

    async def load(self):
        config_pth = os.path.join("scripts", self.directory, "script.json")
        if not os.path.exists(config_pth):
            raise FileNotFoundError(f"`{self.directory}` is missing a script.json")

        try:
            with open(config_pth) as f:
                config = self.config = json.loads(f.read()) # orjson doesnt have a load

        except:
            raise ValueError("failed to load the script.json")

        self.check_config()

        self.identifier = identifier = config["identifier"]
        self.name = config['name']
        self.description = config['description']
        self.author = config['author']
        self.version = config['version']
        self.schema = config.get("schema")
        self.ui_file = config.get("ui_file")
        self.save_file = config.get("save_file")
        if self.save_file:
            self.save_file = os.path.join("scripts", self.directory, self.save_file)
            try:
                with open(self.save_file) as f:
                    self.current_spec = json.loads(f.read())
            except:
                self.current_spec = {}

        else:
            self.current_spec = {}

        try:
            with open(os.path.join("scripts", self.directory, self.ui_file)) as f:
                self.ui_spec = json.loads(f.read())

        except FileNotFoundError:
            raise ValueError(f"{self.identifier} :: load :: ui :: specified ui file not found")

        except json.JSONDecodeError:
            raise ValueError(f"{self.identifier} :: load :: ui :: invalid json file")

        if identifier in self.__manager.scripts:
            raise ValueError(f"Bundle identifier already exists: {identifier}")

        find = await self.__manager.system.db.fetchrow("SELECT scriptname, state from scripts where identifier = ?", identifier)
        if not find:
            await self.__manager.system.db.execute("INSERT INTO scripts VALUES (?,?,0)", identifier, self.name)
        else:
            self.enabled = bool(find[1])

        if self.schema:
            try:
                file = os.path.join("scripts", self.directory, self.schema['database_file'])
                await self.__manager.db._connect_script(self.schema['name'], file)
                await self.__manager.db.executescript(self.schema['creation'])
            except KeyError:
                raise ValueError(f"{self.identifier} :: load :: schema :: missing required key(s): database_file, name, creation")

            except aiosqlite3.OperationalError as e:
                raise
                raise ValueError(f"{self.identifier} :: load :: schema :: create :: bad SQL statement. {e}")

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
        if self.schema:
            await self.__manager.db._detach_script(self.schema['name'])

        self.communicator._eject_all() # noqa

    def handle_dispatch(self, event_name: str, *args, **kwargs):
        if self.enabled:
            try:
                self.dispatcher.emit(event_name, *args, **kwargs)
            except Exception as e:
                logger.debug(f"listener error in script {self.name}::{self.identifier}", exc_info=e)
                raise

    async def wait_for(self, event, *, check, timeout=60):
        pass

    def check_config(self):
        cfg = self.config
        names = ["name", "description", "identifier", "version", "author", "loader"]
        for name in names:
            if name not in cfg or not cfg.get(name):
                raise ValueError(f"script.json :: missing or invalid {name} key")

    def get_spec(self):
        return {
            "id": self.identifier,
            "name": self.name,
            "author": {
                "display": self.author['display'],
                "id": self.author['discord_id']
            },
            "description": self.description,
            "spec": self.ui_spec,
            "existing_settings": self.current_spec
        }

    async def set_spec(self, spec: dict):
        self.current_spec = spec.copy() # just in case the user messes with it
        if self.save_file:
            with open(self.save_file, "w") as f:
                json.dump(spec, f)

        self.dispatcher.emit("spec_update", spec)

    async def find_commands_on_message(self, message: models.PartialMessage):
        prefixes = self.system.get_dpy_prefix(self.system.discord_bot, message)
        if message.content.startswith(tuple(prefixes)):
            for pref in prefixes:
                if message.content.startswith(pref):
                    message.view = StringView(message.content.replace(pref, "", 1))
                    name = message.view.get_word()
                    if name in self.communicator.commands:
                        if not self.current_spec.get("commands", {}).get(name, {"enabled": False}).get("enabled"):
                            return

                        try:
                            await self.communicator.commands[name](message)
                        except Exception as e:
                            logger.error(f"Error in script {self.name} ({self.identifier})", exc_info=e)

                    return

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
        self.commands = {}

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, arg):
        self._module = arg

    def get_discord_channel(self, channel_id: int) -> Optional[dpy.TextChannel]:
        return self.__system.discord_bot.guilds[0].get_channel(channel_id) # this assumes were only in one guild

    def get_twitch_channel(self) -> Optional[tio.Channel]:
        name = self.__system.twitch_streamer._ws.nick
        return self.__system.twitch_bot.get_channel(name)

    async def get_user(self, *,
                 id: int = None,
                 discord_id: int = None,
                 discord_name: str = None,
                 twitch_name: str = None
                 ) -> Optional[common.User]:
        """fetch a user by their system id, discord id, their discord name, or their twitch name"""
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
