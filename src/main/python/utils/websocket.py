"""
Licensed under the Open Software License version 3.0
"""
import asyncio
import aiohttp
import time
import prettify_exceptions
import logging

fmt = prettify_exceptions.DefaultFormatter()

try:
    import orjson as json
except:
    import json

logger = logging.getLogger("xlydn.gateway")

class Websocket:
    def __init__(self, system):
        self.system = system
        self.closing = False
        self._ping = None
        self._pump = None
        self._latency = time.monotonic()

    async def async_init(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        self.closing = True
        if self.ws and not self.ws.closed:
            await self.ws.close(code=1000)

    async def connect(self):
        backoff = 2
        while True:
            try:
                self.ws = await self.session.ws_connect("https://bot.idevision.net/gateway/v1")
                logger.debug("Connected to the gateway")
                await self.send_op_1()
                self._pump = self.system.loop.create_task(self.pump_socket())
            except aiohttp.ClientError:
                backoff *= 2
                logger.warning(f"Failed to connect to the gateway, retrying in {backoff} seconds")
                await asyncio.sleep(backoff)

    async def send(self, *args, **kwargs):
        await self.ws.send_json(*args, **kwargs, dumps=json.dumps)

    async def pump_socket(self):
        while not self.ws.closed:
            msg = await self.ws.receive_json(loads=json.loads)
            handler = getattr(self, f"handle_op_{msg['op']}", None)
            if not handler:
                continue
            try:
                await handler(msg)
            except Exception as e:
                print("".join(fmt.format_traceback(e.__traceback__)))

        logger.debug("disconnected from the gateway")
        if not self.closing:
            await self.connect()

    async def ping_task(self):
        while not self.ws.closed:
            self._latency = time.monotonic()
            await self.send({"op": 3})
            await asyncio.sleep(20)

    async def send_op_1(self): # IDENTIFY
        from __main__ import __VERSION__ # noqa
        if self.system.discord_appinfo is None:
            if self.system.discord_run_event.is_set():
                self.system.discord_appinfo = await self.system.discord_bot.application_info()
            else:
                # uh oh
                raise ValueError("This bot has no connected discord account")

        data = {
            "version": __VERSION__,
            "token": self.system.config.get("tokens", "twitch_streamer_token"), # this is used to verify with twitch that the bot is legit
            "twitch_bot_id": self.system.twitch_bot.user_id,
            "discord_id": self.system.discord_bot.user.id,
            "bot_id": self.system.id
        }
        await self.send(data)
        self._ping = self.system.loop.create_task(self.ping_task())

    async def handle_op_1(self, msg):
        await self.send_op_2()

    async def send_op_2(self):
        data = {}
        plugin_list = self.system.scripts

    async def handle_op_4(self, msg): # PONG
        self.latency = time.monotonic() - self._latency


