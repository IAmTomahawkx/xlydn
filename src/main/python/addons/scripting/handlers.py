import os
import importlib
import sys
import asyncio
import logging
import inspect
import tarfile
import pathlib
import zlib
import shutil
import traceback # use traceback instead of prettify.py
from typing import Optional
try:
    import orjson as json
except:
    import json

import aiosqlite3
import discord as dpy
import twitchio as tio
import yarl
from discord.ext.commands.view import StringView

from utils import signals, common, db, api
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
        self.plugins = {}
        self.errors = []
        self.logs = {}
        self.monitor = monitor.StackMonitor(system)
        self.monitor.start()
        self.db = ScriptDB()
        self.download_lock = asyncio.Lock()

    async def handle_gateway_update(self, msg):
        pass

    async def handle_update_requested(self, msg):
        pass

    async def assemble_spec(self) -> list:
        data = []
        for plugin in self.plugins:
            data.append(plugin.get_spec())

        return data

    async def search_and_load(self):
        scripts_path = os.path.abspath(os.path.join(".", "plugins"))
        if not os.path.exists(scripts_path) and not os.path.isdir(scripts_path):
            os.mkdir(scripts_path)

        for dirname in os.listdir(scripts_path):
            pth = os.path.join("plugins", dirname)
            if not os.path.isdir(pth):
                continue

            logger.debug(f"Scanning path {pth}")

            files = os.listdir(pth)
            if "plugin.json" not in files:
                logger.info(f"Missing plugin.json; skipping load of {pth}")
                continue

            try:
                await self.load_script(dirname)
            except ValueError as e:
                logger.debug(f"failed to load script at {pth}", exc_info=e)
                self.errors.append((pth, "".join(traceback.format_exception(type(e), e, e.__traceback__))))

    async def reload_all_scripts(self):
        logger.debug("Reloading all plugins : start unload")
        await self.unload_all()
        logger.debug("Reloading all plugins : start load")
        await self.search_and_load()
        logger.debug("Reloading all plugins : complete")

    async def load_script(self, directory) -> "ScriptHandler":
        handle = ScriptHandler(directory, self, self.system.loop)
        await handle.load()
        self.plugins[handle.identifier] = handle
        logger.debug(f"Loaded plugin {handle.name} in directory plugins/{directory}")
        return handle

    async def reload_script(self, identifier):
        if identifier not in self.plugins:
            raise ValueError(f"Plugin named {identifier} not found")

        script = self.plugins[identifier]
        logger.debug(f"Reloading Plugin {script.name}")

        script.will_unload()
        await asyncio.sleep(1) # give time for the loop to run the emitters
        await script.unload()
        del sys.modules[script.module_path]
        del self.plugins[identifier]

        directory = script.directory
        del script
        script = await self.load_script(directory)
        await script.load()

    async def unload_all(self):
        for handler in self.plugins.values():
            handler.will_unload() # notify the scripts that theyre going to be ejected

        for _ in range(5):
            await asyncio.sleep(0)
            # run through the loop a couple times to give the emitted coroutines a chance to run before teardown

        for handler in self.plugins.values():
            await handler.unload()

        self.plugins.clear()

    def dispatch_event(self, event_name, *args, platform=None, **kwargs):
        if event_name == "message":
            if isinstance(args[0], dpy.Message):
                msg = models.PartialMessage.from_discord(args[0])
                for script in self.plugins.values():
                    script.handle_dispatch("discord_message", *args, **kwargs)

            else:
                msg = models.PartialMessage.from_twitch(args[0])
                for script in self.plugins.values():
                    script.handle_dispatch("twitch_message", *args, **kwargs)

            args = msg,

        for script in self.plugins.values():
            script.handle_dispatch(event_name, *args, **kwargs)

    async def download_plugin(self, plugin_id: str):
        try:
            await self._download_plugin(plugin_id)
        except ValueError as e:
            return e.args[0]

        await self.load_script(plugin_id.replace('.', '_').replace('-', '_'))

    async def _download_plugin(self, plugin_id: str):
        logger.debug(f"requesting download for plugin {plugin_id}")
        url = yarl.URL(api.BASE_URL + "api/v2/plugins/download").with_query(plugin_id=plugin_id)
        if not os.path.exists("./tmp"):
            os.mkdir("./tmp")

        async with self.system.session.get(url) as resp:
            if resp.status != 200: # if this returns anything other than 200 theres something wrong
                if resp.status == 400:
                    logger.debug(f"aborted plugin download ({plugin_id}). Script was not found")
                    raise ValueError(self.system.locale("The requested script was not found"))

                logger.debug(f"aborted plugin download ({plugin_id}). {resp.reason}, {resp.status}")
                raise ValueError(f"An unknown error occured: {resp.reason} ({resp.status})")

            with open(f"./tmp/{plugin_id}.tar.gz", "wb") as f:
                while True:
                    chunk = await resp.content.read(32)
                    if not chunk:
                        break
                    f.write(chunk)

        if not tarfile.is_tarfile(f"./tmp/{plugin_id}.tar.gz"):
            os.remove(f"./tmp/{plugin_id}.tar.gz")
            logger.debug(f"aborted plugin unpackaging ({plugin_id}). Downloaded file was an invalid tar file")
            raise ValueError(self.system.locale("There was an error downloading the script (was not a gzipped tar archive)"))

        # extract from the tar archive
        async with self.download_lock: # lock to prevent the plugin path being overwritten by concurrent downloads
            file = tarfile.open(f"./tmp/{plugin_id}.tar.gz", mode="r:gz")
            file.extractall("./plugins")
            os.rename("./plugins/plugin", f"./plugins/{plugin_id.replace('.', '_').replace('-', '_')}")
            os.rename("./plugins/plugin.plug", f"./plugins/{plugin_id}.plug")
            os.remove(f"./tmp/{plugin_id}.tar.gz")

        logger.debug(f"Downloaded plugin {plugin_id}")

    async def update_plugin(self, plugin_id: str):
        if plugin_id not in self.plugins:
            return self.system.locale("Plugin does not exist, or is not installed")

        plugin = self.plugins[plugin_id]
        if not plugin.plugin_info:
            return self.system.locale("This plugin does not appear to have been downloaded from the xlydn api")

        numeric_version = plugin.plugin_info['numeric_version']
        version = plugin.version

        async with self.system.session.get(f"{api.BASE_URL}api/v2/plugins?id={plugin_id}") as resp:
            data = await resp.json()
            if resp.status == 400:
                return data['error']

            if resp.status != 200:
                return self.system.locale("The api is broken, please try again later")

        if numeric_version >= data['numeric_version']:
            return self.system.locale("This plugin is up to date!")

        plugin.will_unload()
        await plugin.unload()
        del self.plugins[plugin.identifier]
        shutil.rmtree(os.path.join("plugins", plugin.directory))
        os.remove(os.path.join("plugins", plugin_id + ".plug"))

        await self._download_plugin(plugin.identifier)
        importlib.reload(plugin.module)
        del sys.modules[plugin.module_path]
        del plugin
        plugin = await self.load_script(plugin_id.replace(".", "_").replace("-", "_"))
        return self.system.locale("Successfully updated from version {0} ({1}) -> version {2} ({3}").format(version,
                                                                                                            numeric_version, plugin.version, plugin.plugin_info['numeric_version'])


    async def upload_plugin(self, plugin: "ScriptHandler", targets: list=None):
        logger.debug(f"User requests upload for script {plugin.name} ({plugin.identifier})")
        errors = []
        id = plugin.identifier
        if any(x in id for x in " /\\'*&"):
            errors.append(self.system.locale("Plugin ID contains invalid characters"))

        if plugin.plugin_info and plugin.plugin_info['id'] != plugin.identifier:
            errors.append(self.system.locale("Script identifier cannot change"))

        if targets:
            if any(type(t) != int for t in targets):
                errors.append(self.system.locale("Targets must be discord ids"))

        if errors:
            logger.debug(f"Aborted due to the following errors: {', '.join(errors)}")
            raise ValueError("\n".join(errors))

        if not os.path.exists("./tmp"):
            os.mkdir("./tmp")

        tar = tarfile.open(f"./tmp/{plugin.identifier}.tar.gz", mode="w:gz")
        tar.add(os.path.join("plugins", plugin.directory), arcname="plugin")
        tar.close()

        data = {
            "id": id,
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description
        }
        if self.system.discord_appinfo:
            data['discord_id'] = self.system.discord_appinfo.owner.id
        else:
            if not self.system.discord_bot._ready.is_set():
                logger.debug("Aborted due to no discord id being obtainable")
                raise ValueError(self.system.locale("The discord bot is not connected"))

            self.system.discord_appinfo = await self.system.discord_bot.application_info()
            data['discord_id'] = self.system.discord_appinfo.owner.id

        if targets:
            data['targets'] = targets

        url = yarl.URL(api.BASE_URL + "api/v2/plugins")
        async with self.system.session.post(url, json=data, headers={"Authorization": self.system.config.get("tokens", "twitch_streamer_token")}) as resp:
            data = await resp.json()

            if 200 > resp.status or resp.status > 299:
                logger.debug(f"Aborted due to api rejection: {data} ({resp.status})")
                raise ValueError(data['error'])

            upload_to = data['upload_to']

        logger.debug(f"Recieved a request to upload file to {upload_to}")

        try:
            async with self.system.session.post(upload_to, data={"file": open(tar.name, "rb")}) as resp:
                data = await resp.json()
                if 200 > resp.status or resp.status > 299:
                    logger.debug(f"Aborted file upload due to api rejection: {data} ({resp.status})")
                    raise ValueError(str(data))
                else:
                    logger.debug(f"successfully uploaded {plugin.name} ({plugin.identifier})")
        finally:
            os.remove(tar.name)


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
        self.plugin_info = None
        self.communicator = Communicator(self)

        self.dispatcher.add_listener("message", self.find_commands_on_message)

    async def load(self):
        config_pth = os.path.join("plugins", self.directory, "plugin.json")
        if not os.path.exists(config_pth):
            raise FileNotFoundError(f"`{self.directory}` is missing a plugin.json")

        try:
            with open(config_pth) as f:
                config = self.config = json.loads(f.read()) # orjson doesnt have a load

        except:
            raise ValueError("failed to load the plugin.json")

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
            self.save_file = os.path.join("plugins", self.directory, self.save_file)
            try:
                with open(self.save_file) as f:
                    self.current_spec = json.loads(f.read())
            except:
                self.current_spec = {}

        else:
            self.current_spec = {}

        try:
            with open(os.path.join("plugins", self.directory, self.ui_file)) as f:
                self.ui_spec = json.loads(f.read())

        except FileNotFoundError:
            raise ValueError(f"{self.identifier} :: load :: ui :: specified ui file not found")

        except json.JSONDecodeError:
            raise ValueError(f"{self.identifier} :: load :: ui :: invalid json file")

        if identifier in self.__manager.plugins:
            raise ValueError(f"Bundle identifier already exists: {identifier}")

        find = await self.__manager.system.db.fetchrow("SELECT scriptname, state from scripts where identifier = ?", identifier)
        if not find:
            await self.__manager.system.db.execute("INSERT INTO scripts VALUES (?,?,0)", identifier, self.name)
        else:
            self.enabled = bool(find[1])

        if self.schema:
            try:
                file = os.path.join("plugins", self.directory, self.schema['database_file'])
                await self.__manager.db._connect_script(self.schema['name'], file)
                await self.__manager.db.executescript(self.schema['creation'])
            except KeyError:
                raise ValueError(f"{self.identifier} :: load :: schema :: missing required key(s): database_file, name, creation")

            except aiosqlite3.OperationalError as e:
                raise
                raise ValueError(f"{self.identifier} :: load :: schema :: create :: bad SQL statement. {e}")

        try:
            self.module_path = f"plugins.{self.directory}.{config['loader'].replace('.py', '')}"
            self.module = importlib.import_module(self.module_path)
            if not hasattr(self.module, "setup") or not inspect.isfunction(self.module.setup):
                raise ValueError(f"{self.identifier} :: load :: missing setup function")

            self.module.setup(self.communicator)
        except ModuleNotFoundError:
            raise ValueError(f"script.json :: invalid loader key")

        except Exception as e:
            raise ValueError(f"failed to load {self.name}") from e

        pth = pathlib.Path("plugins", f"{self.identifier}.plug")
        if pth.exists():
            with pth.open("rb") as f:
                data = f.read()
                try:
                    data = zlib.decompress(data)
                except: # noqa
                    pass
                else:
                    self.plugin_info = json.loads(data)

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
                "display_name": self.author['display'],
                "discord_id": self.author['discord_id'],
                "email": self.author['email']
            },
            "description": self.description,
            "version": self.version,
            "commands": self.command_spec(),
            "existing_settings": self.current_spec
        }

    async def command_spec(self):
        pass


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
