import asyncio
import configparser
import datetime
import importlib
import importlib.util
import json
import logging
import os
import pathlib
import random
import sys
import traceback
import gzip
import re
from concurrent.futures import CancelledError
from typing import Optional

import aiohttp
import discord
import discord.utils
import twitchio
import twitchio.cooldowns
import twitchio.http
import twitchio.websocket
from discord.ext import commands
from discord.ext.commands.core import _CaseInsensitiveDict
from discord.ext.commands.view import StringView
from twitchio.ext import commands as tio_commands

from interface.main2 import Window as Interface
from . import api, errors, common, locale, websocket
from .contexts import CompatContext, TwitchContext
from .db import Database
from .commands import CommandWithLocale, GroupWithLocale
from .cooldowns import CooldownMapping
from addons.scripting import handlers

logger = logging.getLogger("xlydn")
logger.setLevel(logging.DEBUG)
hdl = logging.StreamHandler(sys.stderr)
hdl.setLevel(logging.DEBUG)
logger.addHandler(hdl)

logging.getLogger("aiosqlite3").addHandler(logging.NullHandler(100)) # aiosqlite warnings are annoying and useless

discord_log = logging.getLogger("xlydn.discord")
twitch_bot_log = logging.getLogger("xlydn.twitchBot")
twitch_streamer_log = logging.getLogger("xlydn.twitchStreamer")

class System:
    def __init__(self, config: configparser.ConfigParser, window: Interface, ci=False):
        self.config = config
        self.api = api.XlydnApi(self)
        self.discord_bot = discord_bot(self,
                                       command_prefix=self.get_dpy_prefix,
                                       activity=discord.Game(name=self.config.get("general", "discord_presence", fallback="Xlydn bot")),
                                       intents=discord.Intents.all())
        self.twitch_streamer = twitch_bot(self, self.get_tio_prefix, streamer=True) # noqa
        self.twitch_bot = twitch_bot(self, self.get_tio_prefix) # noqa

        self.db = Database()
        self.loop = asyncio.get_event_loop()
        self.alive = True
        self.bot_run_event = asyncio.Event()
        self.streamer_run_event = asyncio.Event()
        self.discord_run_event = asyncio.Event()
        self.scripts = handlers.ScriptManager(self)
        if not ci:
            self.loop.create_task(self.scripts.search_and_load())

        self.user_cache = {}

        self.solo_timer_cache = {}
        self.chain_timer_cache = {}
        self.timer_loop_cache = {}

        if not ci:
            self.timer_task = self.loop.create_task(self.timer_loop())
        self.command_cache = {}
        self.timer_cache = [] # note that this isnt for "timers". this is for delayed events
        self.oauth_waiting = {}

        self.locale = locale.LocaleTranslator(config)
        if not ci:
            self.interface = window
            window.system = self

        self.auth_ws = None
        self.auth_ws_session = None
        self.ws = websocket.Websocket(self)

        self.discord_appinfo = None
        self.pump_task = None
        self.connecting_count = 0

        self.twitch_automod_regex = None
        self.discord_automod_regex = None
        self.automod_domains = []

        if not ci:
            self.loop.create_task(self.build_automod_regex())

        if os.path.exists(os.path.join("services", ".dfuuid.lock")):
            with open(os.path.join("services", ".dfuuid.lock")) as f:
                self.id = f.read()

        else:
            self.id = None

    async def pump_auth_ws(self):
        while not self.auth_ws.closed:
            try:
                data = await self.auth_ws.receive_json(timeout=300)
                if data['u'] in self.oauth_waiting:
                    self.oauth_waiting[data['u']].set_result(data['d'])
                else:
                    pass # unsure why this would happen
            except:
                pass

    async def link_from_discord(self, ctx, user_id: int) -> bool:
        self.connecting_count += 1
        resp = await self._link(ctx, user_id, is_discord=True)
        self.connecting_count -= 1
        if self.connecting_count < 1:
            await self.auth_ws.close()
            self.auth_ws = None

        return resp

    async def link_from_twitch(self, ctx, username: str):
        self.connecting_count += 1
        try:
            resp = await self._link(ctx, username, is_discord=False)
        except:
            raise
        else:
            if self.connecting_count < 1:
                await self.auth_ws.close()
                self.auth_ws = None
        finally:
            self.connecting_count -= 1

        return resp

    async def _link(self, ctx, user_id, is_discord=False):
        if self.auth_ws is None or self.auth_ws.closed:
            if self.auth_ws_session is None:
                self.auth_ws_session = aiohttp.ClientSession()

                self.auth_ws = await self.auth_ws_session.ws_connect("https://bot.idevision.net/bot/link_ws")

            if self.pump_task is None:
                self.pump_task = self.loop.create_task(self.pump_auth_ws())

        await self.auth_ws.send_json({"Authorization": self.config.get("tokens", "twitch_streamer_token"), "u": user_id, "c": False}) # token will be used to verify with twitch, it wont be stored.

        future = self.loop.create_future()
        self.oauth_waiting[user_id] = future
        try:
            await asyncio.wait_for(future, timeout=5)
            resp = future.result()
            del self.oauth_waiting[user_id]
        except:
            resp = "$notfound"

        if resp == "$notfound":
            if self.discord_appinfo is None:
                if self.discord_run_event.is_set():
                    self.discord_appinfo: discord.AppInfo = await self.discord_bot.application_info()
                else:
                    raise commands.CommandError("This bot has no connected discord account")


            if is_discord:
                fmt = self.locale("Please go to {0} to establish a connection between discord and twitch for your user"
                                  " in this bot. You must have already linked your discord and twitch!").format(
                    f"[discord.com]({api.BASE_OAUTH_REDIRECT})")
                await ctx.send(embed=discord.Embed(description=fmt))
            else:
                fmt = self.locale("Please go to {0} to establish a connection between discord and twitch for your user"
                                  " in this bot. You must have already linked your discord and twitch!").format(
                    api.BASE_OAUTH_REDIRECT)
                await ctx.send(fmt)

            if self.auth_ws is None or self.auth_ws.closed:
                self.auth_ws = await self.auth_ws_session.ws_connect("https://bot.idevision.net/bot/link_ws")

            await self.auth_ws.send_json(
                {"Authorization": self.config.get("tokens", "twitch_streamer_token"), "u": user_id, "c": True}) # tell it to wait 5 minutes this time

            future = self.loop.create_future()
            self.oauth_waiting[user_id] = future
            try:
                await asyncio.wait_for(future, timeout=300)
                resp: dict = future.result()
                del self.oauth_waiting[user_id]
            except:
                return False

            if resp == "$notfound":
                return False

        twitchname = None
        twitchid = None
        discord_id = int(resp['id'])
        for connection in resp['connections']:
            if connection['type'] == "twitch":
                twitchname = connection['name']
                twitchid = int(connection['id'])

        if twitchname is None:
            return False

        twitchuser = await self.get_user_twitch_name(name=twitchname, create=False)
        discorduser = await self.get_user_discord_id(id=discord_id, create=False)

        if twitchuser is None and discorduser is None:
            await self.create_user(discord_id, twitchid, twitchname)
            return True

        if twitchuser is None:
            # quite simple, just put the twitch details in the same row
            await self.db.execute("UPDATE accounts SET twitch_userid = ? AND twitch_username = ? WHERE id = ?",
                                    twitchid, twitchname, discorduser.id)
            del self.user_cache[discorduser.id]
            return True

        elif discorduser is None:
            # quite simple, just put the discord details in the same row
            await self.db.execute("UPDATE accounts SET discord_id = ? WHERE twitch_userid = ?",
                                  discord_id, twitchid)
            del self.user_cache[twitchuser.id]
            return True

        else:
            points = twitchuser.points + discorduser.points
            editor = twitchuser.editor or discorduser.editor
            await self.db.execute("UPDATE accounts SET points = ? AND hours = ? AND editor = ? AND twitch_userid = ? AND twitch_username = ? WHERE id = ?",
                                  points, twitchuser.editor, int(editor), twitchid, twitchname, discorduser.id)
            await self.db.execute("DELETE FROM accounts WHERE id = ?", twitchuser.id)
            del self.user_cache[twitchuser.id]
            del self.user_cache[discorduser.id]
            return True

    async def get_command(self, name) -> common.CustomCommand:
        if name in self.command_cache:
            return self.command_cache[name]

        row = await self.db.fetchrow("SELECT * FROM commands WHERE name = ?", name)
        if row is None:
            return None

        self.command_cache[name] = resp = common.CustomCommand(row)
        return resp

    async def add_command(self, name: str, places: int, content: str, cooldown: int, limits: str, isscript: bool):
        if name in self.command_cache:
            raise ValueError(self.locale("Command `{0}` already exists").format(name))

        if self.discord_bot.get_command(name) or discord.utils.find(lambda c: c.name == name, self.twitch_bot.commands):
            raise ValueError(self.locale("Command name is a reserved word"))

        try:
            await self.db.execute("INSERT INTO commands VALUES (?,?,?,?,?,?)", name, places, content, cooldown, limits, int(isscript))
        except:
            raise ValueError(self.locale("Command `{0}` already exists").format(name))

    async def remove_command(self, name: str):
        if name not in self.command_cache:
            if (await self.db.fetchrow("SELECT * FROM commands WHERE name = ?", name)) is None:
                raise ValueError(self.locale("Command `{0}` does not exist").format(name))

        await self.db.execute("DELETE FROM commands WHERE name = ?", name)
        if name in self.command_cache:
            del self.command_cache[name]

    async def create_user(self, discord_id=None, twitch_id=None, twitch_username=None):
        userid = random.randint(10590208453, 90823972987079800) # yup, i did this.
        await self.db.execute("INSERT INTO accounts VALUES (?,?,?,?,0,0,0)", twitch_id, twitch_username, discord_id, userid)
        resp = common.User((twitch_id, twitch_username, discord_id, userid, 0, 0, 0), self)
        self.user_cache[resp.id] = resp
        return resp

    async def get_user(self, id):
        if id in self.user_cache:
            return self.user_cache[id]

        row = await self.db.fetchrow("SELECT * FROM accounts WHERE id = ?", id)
        if row is None:
            return None # rip

        self.user_cache[id] = resp = common.User(row, self)
        return resp

    async def get_user_discord_id(self, id, create=True):
        exists = discord.utils.get(self.user_cache.values(), discord_id=id)
        if exists:
            return exists

        row = await self.db.fetchrow("SELECT * FROM accounts WHERE discord_id = ?", id)
        if row is None:
            if not create:
                return None

            return await self.create_user(discord_id=id)

        resp = common.User(row, self)
        self.user_cache[resp.id] = resp
        return resp

    async def get_user_twitch_id(self, id, create=True):
        exists = discord.utils.get(self.user_cache.values(), twitch_id=id)
        if exists:
            return exists

        row = await self.db.fetchrow("SELECT * FROM accounts WHERE twitch_id = ?", id)
        if row is None:
            if not create:
                return None
            return self.create_user(twitch_id=id)

        resp = common.User(row, self)
        self.user_cache[resp.id] = resp
        return resp

    async def get_user_twitch_name(self, name, id=None, create=True) -> Optional[common.User]:
        name = name.lower()
        exists = discord.utils.get(self.user_cache.values(), twitch_name=name)
        if exists:
            return exists

        row = await self.db.fetchrow("SELECT * FROM accounts WHERE twitch_name = ?", name)
        if row is None:
            if not create:
                return None

            return await self.create_user(twitch_username=name, twitch_id=id)

        resp = common.User(row, self)
        self.user_cache[resp.id] = resp
        return resp

    async def build_automod_regex(self):
        words = await self.db.fetch("SELECT * FROM automod_words;")
        urls = await self.db.fetch("SELECT * FROM automod_domains;")
        self.automod_domains = [domain[0] for domain in urls]

        twitch_banned_words = [word[0] for word in words if word[1]]
        discord_banned_words = [word[0] for word in words if word[2]]

        self.twitch_automod_regex = re.compile((
                              r'(?i)'  # case insensitive
                              r'\b'  # word bound
                              r'(?:{})'  # non capturing group, to make sure that the word bound occurs before/after all words
                              r'\b'
                          ).format('|'.join(map(re.escape, twitch_banned_words))))

        self.discord_automod_regex = re.compile((
                              r'(?i)'  # case insensitive
                              r'\b'  # word bound
                              r'(?:{})'  # non capturing group, to make sure that the word bound occurs before/after all words
                              r'\b'
                          ).format('|'.join(map(re.escape, discord_banned_words))))

    async def schedule_timer(self, fire_at: datetime.datetime, event: str, **kwargs):
        d = {"fire": fire_at, "event": event, "data": kwargs}
        await self.db.execute("INSERT INTO timers VALUES (?,?,?)", event, fire_at.timestamp(), gzip.compress(json.dumps(kwargs)))
        id = await self.db.fetchval("SELECT id FROM timers WHERE fire_at=? AND event=?", fire_at.timestamp(), event)
        d['id'] = id
        self.timer_cache.append(d)

    async def timer_loop(self):
        timers = await self.db.fetch("SELECT * FROM timers")
        for timer in timers:
            self.timer_cache.append({"id": timer['id'], "fire": datetime.datetime.fromtimestamp(timer[1]), "event": timer[2], "data": json.loads(gzip.decompress(timer[3]))})

        while self.alive:
            await asyncio.sleep(0)
            removal = []
            now = datetime.datetime.now()
            for timer in self.timer_cache:
                if timer['fire'] <= now:
                    if self.discord_bot.is_ready():
                        self.discord_bot.dispatch(timer['event'], timer['data'])

                    if self.streamer_run_event.is_set():
                        self.twitch_streamer.dispatch(timer['event'], timer['data'])

                    if self.bot_run_event.is_set():
                        self.twitch_bot.dispatch(timer['event'], timer['data'])

                    removal.append((timer['id'],))

            if removal:
                await self.db.executemany("DELETE FROM timers WHERE id = ?", removal)
                removal.clear()

    def get_tio_prefix(self, *args):
        return self.config.get("general", "command_prefix", fallback="!")

    def get_dpy_prefix(self, bot, msg):
        mention = commands.when_mentioned(bot, msg)
        mention.append(self.config.get("general", "command_prefix", fallback="!"))
        return mention

    def run(self):
        if self.config.getboolean("general", "connect_on_start", fallback=False):
            self.discord_run_event.set()
            self.streamer_run_event.set()
            self.bot_run_event.set()

        self.end_event = self.loop.create_future()

        try:
            self.loop.create_task(self._run())
            self.loop.run_until_complete(self.end_event)
        except Exception as e:
            logger.exception("Encountered fatal error, panicking!", exc_info=e)
            self.interface.crash()
            self.loop.run_forever()

    def dispatch(self, event_name, *args, **kwargs):
        self.scripts.dispatch_event(event_name, *args, **kwargs)

    def connect_discord_bot(self):
        self.discord_run_event.set()

    def disconnect_discord_bot(self):
        self.discord_run_event.clear()

    def connect_twitch_bot(self):
        self.bot_run_event.set()

    def disconnect_twitch_bot(self):
        self.bot_run_event.clear()

    def connect_twitch_streamer(self):
        self.streamer_run_event.set()

    def disconnect_twitch_streamer(self):
        self.streamer_run_event.clear()

    async def _run(self):
        try:
            self.session = aiohttp.ClientSession()
            dbot = None
            streamer = None
            bot = None
            allow_starts = True
            fails = CooldownMapping.from_cooldown(5, 300)
            if not self.config.get("tokens", "twitch_bot_token", fallback=None) \
                or not self.config.get("tokens", "twitch_streamer_token", fallback=None) \
                or not self.config.get("tokens", "discord_bot", fallback=None):
                logger.error("Refusing to start clients: must have tokens to start!")
                allow_starts = False

            else:
                await self.api.do_hello()

            try:
                while self.alive:
                    if not allow_starts and self.config.get("tokens", "twitch_bot_token", fallback=None) \
                            and self.config.get("tokens", "twitch_streamer_token", fallback=None) \
                            and self.config.get("tokens", "discord_bot", fallback=None):
                        allow_starts = True
                        await self.api.do_hello()

                    elif not allow_starts:
                        await asyncio.sleep(1)
                        continue

                    if self.bot_run_event.is_set() and (bot is None or bot.done()):
                        if fails.update_rate_limit("bot.twitch"):
                            self.bot_run_event.clear()
                            self.interface.token_disconnect_bot()
                            logger.warning("Failed to start Twitch Bot Client")
                            continue

                        bot = self.loop.create_task(self.twitch_bot.try_start(self.config.get("tokens", "twitch_bot_token")))

                    if not self.bot_run_event.is_set() and bot is not None and not bot.done():
                        bot.cancel()

                    if self.streamer_run_event.is_set() and (streamer is None or streamer.done()):
                        if fails.update_rate_limit("streamer.twitch"):
                            self.streamer_run_event.clear()
                            self.interface.token_disconnect_streamer()
                            logger.warning("Failed to start Twitch Streamer Client")
                            continue

                        streamer = self.loop.create_task(self.twitch_streamer.try_start(self.config.get("tokens", "twitch_streamer_token")))

                    if not self.streamer_run_event.is_set() and streamer is not None and not streamer.done():
                        streamer.cancel()

                    if self.discord_run_event.is_set() and (dbot is None or dbot.done()):
                        if fails.update_rate_limit("bot.discord"):
                            self.discord_run_event.clear()
                            self.interface.token_disconnect_discord()
                            logger.error("Failed to start Discord Bot", exc_info=dbot.exception() if dbot else None)
                            continue

                        # for whatever reason, attempting to reuse the bot object causes a variety of asyncio issues
                        self.discord_bot = discord_bot(self,
                                           command_prefix=self.get_dpy_prefix,
                                           activity=discord.Game(name=self.config.get("general", "discord_presence", fallback="Xlydn bot")),
                                           intents=discord.Intents.all())
                        import gc
                        gc.collect()
                        dbot = self.loop.create_task(self.discord_bot.try_start(self.config.get("tokens", "discord_bot")))

                    if not self.discord_run_event.is_set() and dbot is not None and not dbot.done():
                        await self.discord_bot.close()
                        logger.debug("Closed discord client")

                    await asyncio.sleep(0)

            except KeyboardInterrupt:
                pass
        except Exception as e:
            self.end_event.set_exception(e)

    async def close(self):
        self.alive = False
        logger.debug("Shutting down")

        import async_timeout
        async with async_timeout.timeout(5):
            await self.discord_bot.logout()

        await self.twitch_bot.stop()
        await self.twitch_streamer.stop()

        with pathlib.Path(Interface.get_data_location(), "config.ini").open("w", encoding="utf8") as f:
            self.config.write(f)

        logger.debug("Goodbye!")
        try:
            self.end_event.set_result(None)
        except:
            pass

class discord_bot(commands.Bot):
    def __init__(self, system, *args, **kwargs):
        self.system = system
        self.tick_yes = "<:GreenTick:609893073216077825>"
        self.tick_no = "<:RedTick:609893040328409108>"
        super().__init__(*args, **kwargs)
        self.loaded = False
        self.add_check(self.guild_check)

    async def guild_check(self, ctx):
        try:
            if ctx.guild is not None and ctx.guild.id != self.system.config.getint("general", "server_id", fallback=None):
                raise errors.GuildCheckFailed()
        except:
            pass

        return True

    async def start(self, *args, **kwargs):
        self.load()
        await super().start(*args, **kwargs)

    def dispatch(self, event_name, *args, **kwargs):
        self.system.dispatch(event_name, *args, **kwargs, platform="discord")
        super(discord_bot, self).dispatch(event_name, *args, **kwargs)

    async def locale_updated(self):
        new_commands = {}
        for command in self.commands:
            try:
                command.inject_locale(self)
            except: pass

            new_commands[command.name] = command
            for al in command.aliases:
                new_commands[al] = command

        self.all_commands.clear()
        self.all_commands.update(new_commands)

    def load(self, ci=False):
        if self.loaded:
            return

        self.loaded = True

        self.load_extension("jishaku")
        import addons.discord
        for mod in dir(addons.discord):
            if mod.startswith("_"):
                continue

            try:
                self.load_extension("addons.discord." + mod)
            except:
                if ci:
                    raise
                else:
                    traceback.print_exc()

    def get_context(self, message, **kwargs):
        return super().get_context(message, cls=CompatContext)

    async def try_start(self, token):
        try:
            return await self.start(token)
        except Exception as e:
            if isinstance(e, CancelledError):
                discord_log.error("Cancelled", exc_info=e)
                await self.logout()

            elif isinstance(e, errors.UserFriendlyError):
                raise
            else:
                logger.exception("uncaught error in discord.bot.start: ", exc_info=e)
                raise errors.UserFriendlyError("Whoops! something happened while running the discord bot!") from e

        finally:
            await self.close()

class TioHTTP(twitchio.http.HTTPSession):
    def __init__(self, loop, streamer: bool, client):
        self.client_id = "q7rc2eb3m8n6u9q6mqmtrnr1x1cf2c"
        self.client_secret = None
        self.token = None
        self._refresh_token = None
        self._bucket = twitchio.cooldowns.RateBucket(method='http')
        self._session = aiohttp.ClientSession(loop=loop)
        self._refresh_token = None
        self.streamer = streamer
        self.client = client
        self.loop = loop

    async def request(self, method, url, *, params=None, limit=None, **kwargs):
        count = kwargs.pop('count', False)

        data = []

        params = params or []
        url = f'{self.BASE}{url}'


        headers = kwargs.pop('headers', {})

        if self.client_id is not None:
            headers['Client-ID'] = str(self.client_id)

        if self.client_secret and self.client_id and not self.token:
            logging.info("No token passed, generating new token under client id {0} and client secret {1}")
            await self.generate_token()

        if self.token is not None:
            headers['Authorization'] = "Bearer " + self.token

        #else: we'll probably get a 401, but we can check this in the response

        cursor = None

        def reached_limit():
            return limit and len(data) >= limit

        def get_limit():
            if limit is None:
                return '100'

            to_get = limit - len(data)
            return str(to_get) if to_get < 100 else '100'

        is_finished = False
        try:
            while not is_finished:
                if limit is not None:
                    if cursor is not None:
                        params.append(('after', cursor))

                    params.append(('first', get_limit()))

                body, is_text = await self._request(method, url, params=params, headers=headers, **kwargs)
                if is_text:
                    return body

                if count:
                    return body['total']

                params.pop()  # remove the first param

                if cursor is not None:
                    params.pop()

                data += body['data']

                try:
                    cursor = body['pagination'].get('cursor', None)
                except KeyError:
                    break
                else:
                    if not cursor:
                        break

                is_finished = reached_limit() if limit is not None else True

            return data
        except twitchio.Unauthorized:
            if self.streamer:
                self.token = await self.client.system.api.try_streamer_refresh()
            else:
                self.token = await self.client.system.api.try_bot_refresh()

            if self.token is None:
                self.loop.create_task(self.client.system.api.prompt_user_for_token("Streamer" if self.streamer else "Bot"))
            else:
                return await self.request(method, url, params=params, limit=limit, **kwargs)


def _is_submodule(parent, child):
    return parent == child or child.startswith(parent + ".")

class GroupMixin(commands.GroupMixin):
    def __init__(self, case_insensitive=True):
        self.all_commands = _CaseInsensitiveDict() if case_insensitive else {}
        self.case_insensitive = case_insensitive

class twitch_bot(tio_commands.Bot, GroupMixin):
    def __init__(self, system, prefix, streamer=False):
        self.loop = asyncio.get_event_loop()
        self.nick = ""
        self.initial_channels = []
        self.http = TioHTTP(self.loop, streamer, self)
        self._ws = twitchio.websocket.WebsocketConnection(bot=self, loop=self.loop, http=self.http, irc_token="",
                                       nick="", initial_channels=[])

        self.system = system
        self.loop.create_task(self._prefix_setter(prefix))
        self.user_id = None
        self._checks = []
        self.__cogs = {}
        self.__extensions = {}
        self.__dict__.update(GroupMixin().__dict__)
        self.streamer = streamer
        self.loaded = False
        self._checks = []
        self._check_once = []
        self.extra_listeners = {}
        self._before_invoke = None
        self._after_invoke = None
        self._webhook_server = None
        self._pump = None

    def load(self, ci=False):
        if not self.streamer and not self.loaded:
            import addons.twitch
            for ext in dir(addons.twitch):
                if ext.startswith("_"):
                    continue

                try:
                    self.load_extension("addons.twitch." + ext)
                except:
                    if ci:
                        raise
                    else:
                        traceback.print_exc()

            self.loaded = True

    async def stop(self):
        if self._pump and not self._pump.done():
            self._pump.cancel()

        if self._ws.is_connected:
            await self._ws._websocket.close()

    async def locale_updated(self):
        new_commands = {}
        for command in self.commands:
            try:
                command.inject_locale(self)
            except: pass

            new_commands[command.name] = command
            for al in command.aliases:
                new_commands[al] = command

        self.all_commands.clear()
        self.all_commands.update(new_commands)

    def add_command(self, command):
        GroupMixin.add_command(self, command)

    def dispatch(self, event, *args, **kwargs):
        self.loop.create_task(self._dispatch(event, *args, **kwargs))
        ev = 'event_' + event
        self.system.dispatch(event, *args, **kwargs, platform="twitch")
        for evt in self.extra_listeners.get(ev, []):
            self.loop.create_task(evt(*args, **kwargs))

    async def validate(self, token_):
        self._ws._token = "oauth:"+token_
        self.http.token = token_
        async with self.system.session.get("https://id.twitch.tv/oauth2/validate",
                                           headers={"Authorization": f"OAuth {token_}", "Client-ID": self.http.client_id}) as resp:

            if 200 > resp.status > 299:
                if self.streamer:
                    self.system.disconnect_twitch_streamer()
                else:
                    self.system.disconnect_twitch_bot()

                raise errors.UserFriendlyError("Error while authenticating, try again later.")

            data = await resp.json()
            if resp.status == 401:
                if self.streamer:
                    token_ = await self.system.api.try_streamer_refresh()
                    if token_ is None:
                        await self.system.api.prompt_user_for_token()
                else:
                    token_ = await self.system.api.try_bot_refresh()
                    if token_ is None:
                        await self.system.api.prompt_user_for_token("Bot")

                raise KeyboardInterrupt

            self._ws.nick = data['login']
            self.user_id = int(data['user_id'])

    async def try_start(self, _token: str):
        self.load()
        try:
            await self.start(_token)
        except Exception as e:
            if isinstance(e, CancelledError):
                return

            elif isinstance(e, errors.UserFriendlyError):
                raise
            else:
                logger.exception("uncaught error in tio.bot.start: ", exc_info=e)
                raise errors.UserFriendlyError("Whoops! something happened while running the bot!") from e

    def _remove_module_references(self, name):
        # find all references to the module
        # remove the cogs registered from the module
        for cogname, cog in self.__cogs.copy().items():
            if _is_submodule(name, cog.__module__):
                self.remove_cog(cogname)

        # remove all the commands from the module
        for cmd in self.all_commands.copy().values():
            if cmd.module is not None and _is_submodule(name, cmd.module):
                if isinstance(cmd, commands.GroupMixin):
                    cmd.recursively_remove_all_commands()
                self.remove_command(cmd.name)

        # remove all the listeners from the module
        for event_list in self.extra_listeners.copy().values():
            remove = []
            for index, event in enumerate(event_list):
                if event.__module__ is not None and _is_submodule(name, event.__module__):
                    remove.append(index)

            for index in reversed(remove):
                del event_list[index]

    def _call_module_finalizers(self, lib, key):
        try:
            func = getattr(lib, 'teardown')
        except AttributeError:
            pass
        else:
            try:
                func(self)
            except Exception:
                pass
        finally:
            self.__extensions.pop(key, None)
            sys.modules.pop(key, None)
            name = lib.__name__
            for module in list(sys.modules.keys()):
                if _is_submodule(name, module):
                    del sys.modules[module]

    def _load_from_module_spec(self, spec, key):
        # precondition: key not in self.__extensions
        lib = importlib.util.module_from_spec(spec)
        sys.modules[key] = lib
        try:
            spec.loader.exec_module(lib)
        except Exception as e:
            del sys.modules[key]
            raise commands.ExtensionFailed(key, e) from e

        try:
            setup = getattr(lib, 'setup')
        except AttributeError:
            del sys.modules[key]
            raise commands.NoEntryPointError(key)

        try:
            setup(self)
        except Exception as e:
            del sys.modules[key]
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, key)
            raise commands.ExtensionFailed(key, e) from e
        else:
            self.__extensions[key] = lib

    def load_extension(self, name):

        if name in self.__extensions:
            raise commands.ExtensionAlreadyLoaded(name)

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise commands.ExtensionNotFound(name)

        self._load_from_module_spec(spec, name)

    def unload_extension(self, name):
        lib = self.__extensions.get(name)
        if lib is None:
            raise commands.ExtensionNotLoaded(name)

        self._remove_module_references(lib.__name__)
        self._call_module_finalizers(lib, name)

    def reload_extension(self, name):
        lib = self.__extensions.get(name)
        if lib is None:
            raise commands.ExtensionNotLoaded(name)

        # get the previous module states from sys modules

        modules = {
            name: module
            for name, module in sys.modules.items()


            if _is_submodule(lib.__name__, name)
        }

        try:
            # Unload and then load the module...
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, name)
            self.load_extension(name)
        except Exception as e:
            # if the load failed, the remnants should have been
            # cleaned from the load_extension function call
            # so let's load it from our old compiled library.
            lib.setup(self)
            self.__extensions[name] = lib

            # revert sys.modules back to normal and raise back to caller
            sys.modules.update(modules)
            raise


    async def start(self, _token: str):
        try:
            await self.validate(_token)
        except KeyboardInterrupt:
            return

        await self._ws._connect()
        try:
            self._pump = self.loop.create_task(self._ws._listen())
            while not self._pump.done():
                if self.system.twitch_streamer._ws._websocket is not None and not self.system.twitch_streamer._ws._websocket.closed \
                        and self.system.twitch_streamer._ws.nick not in self._ws._channel_cache:
                    await self.join_channels([self.system.twitch_streamer._ws.nick])
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()

    async def event_message(self, message: twitchio.Message):
        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def event_command(self, ctx):
        pass

    async def event_command_completion(self, ctx):
        pass

    async def event_userstate(self, user: twitchio.User):
        usr = await self.system.get_user_twitch_name(user.name, user.id)
        change = False
        if user.is_mod and "moderator" not in usr.badges:
            change = True
            usr.badges.append("moderator")

        if not user.is_mod and "moderator" in usr.badges:
            change = True
            usr.badges.remove("moderator")

        if user.is_subscriber and "subscriber" not in usr.badges:
            change = True
            usr.badges.append("subscriber")

        if not user.is_subscriber and "subscriber" in usr.badges:
            change = True
            usr.badges.remove("subscriber")

        if user.badges.get("vip", 0) and "vip" not in usr.badges:
            change = True
            usr.badges.append("vip")

        if not user.badges.get("vip", 0) and "vip" in usr.badges:
            change = True
            usr.badges.remove("vip")

        if change:
            await self.system.db.execute("UPDATE accounts SET badges = ? WHERE id = ?", json.dumps(usr.badges), usr.id)

    async def event_command_error(self, ctx, error):
        if isinstance(error, (tio_commands.CommandNotFound, commands.CommandNotFound)):
            return
        traceback.print_exception(type(error), error, error.__traceback__)

    def add_cog(self, cog):
        if not isinstance(cog, commands.Cog):
            raise TypeError('cogs must derive from Cog')

        cog = cog._inject(self)
        self.__cogs[cog.__cog_name__] = cog

    def get_cog(self, name):
        """Gets the cog instance requested.

        If the cog is not found, ``None`` is returned instead.

        Parameters
        -----------
        name: :class:`str`
            The name of the cog you are requesting.
            This is equivalent to the name passed via keyword
            argument in class creation or the class name if unspecified.
        """
        return self.__cogs.get(name)

    def remove_cog(self, name):
        """Removes a cog from the bot.

        All registered commands and event listeners that the
        cog has registered will be removed as well.

        If no cog is found then this method has no effect.

        Parameters
        -----------
        name: :class:`str`
            The name of the cog to remove.
        """

        cog = self.__cogs.pop(name, None)
        if cog is None:
            return

        cog._eject(self)

    async def can_run(self, ctx, *, call_once=False):
        data = self._check_once if call_once else self._checks

        if len(data) == 0:
            return True

        return await discord.utils.async_all(f(ctx) for f in data)

    async def get_context(self, message, *, cls=TwitchContext) -> TwitchContext:
        view = StringView(message.content)
        ctx = cls(prefix=None, view=view, bot=self, message=message)

        prefix = await self._get_prefixes(message)
        invoked_prefix = prefix

        if isinstance(prefix, str):
            if not view.skip_string(prefix):
                return ctx
        else:
            try:
                # if the context class' __init__ consumes something from the view this
                # will be wrong.  That seems unreasonable though.
                if message.content.startswith(tuple(prefix)):
                    invoked_prefix = discord.utils.find(view.skip_string, prefix)
                else:
                    return ctx

            except TypeError:
                if not isinstance(prefix, list):
                    raise TypeError("get_prefix must return either a string or a list of string, "
                                    "not {}".format(prefix.__class__.__name__))

                # It's possible a bad command_prefix got us here.
                for value in prefix:
                    if not isinstance(value, str):
                        raise TypeError("Iterable command_prefix or list returned from get_prefix must "
                                        "contain only strings, not {}".format(value.__class__.__name__))

                # Getting here shouldn't happen
                raise

        invoker = view.get_word()
        ctx.invoked_with = invoker
        ctx.prefix = invoked_prefix
        ctx.command = self.all_commands.get(invoker)
        return ctx

    async def invoke(self, ctx):
        if ctx.command is not None:
            self.dispatch('command', ctx)
            try:
                await ctx.command.invoke(ctx)
            except commands.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch('command_completion', ctx)
        elif ctx.invoked_with:
            exc = tio_commands.CommandNotFound('Command "{}" is not found'.format(ctx.invoked_with))
            self.dispatch('command_error', ctx, exc)

    async def fetch_chatters(self):
        if not self._ws.nick:
            return None

        async with self.system.session.get(f"https://tmi.twitch.tv/group/user/{self._ws.nick}/chatters", headers={"User-Agent": "a user agent"}) as resp:
            if resp.status == 404:
                return None

            r = await resp.json()

        return r['chatters']
