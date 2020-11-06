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
                self.ws = await self.session.ws_connect("https://bot.idevision.net/api/v1/websocket")
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
            await self.send({"op": 2})
            await asyncio.sleep(10)

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
            "streamer": self.system.config.get("tokens", "twitch_streamer_token"),
            "bot": self.system.config.get("tokens", "discord_bot"),
            "client_id": self.system.discord_appinfo.id
        }
        await self.send(data)
        self._ping = self.system.loop.create_task(self.ping_task())

    async def handle_op_3(self, msg): # PONG
        self.latency = time.monotonic() - self._latency

    async def handle_op_4(self, msg): # panel update
        data = msg['d']
        script = msg.get("s")

        if script:
            await self.system.scripts.handle_gateway_update(data)

        else:
            # ...
            pass

    async def handle_op_6(self, msg): # panel update requested
        script = msg.get("s")

        if script:
            await self.system.scripts.handle_update_requested(msg['d'])

    async def send_panel_update(self, payload, script=None):
        data = {
            "op": 5,
            "s": script,
            "d": payload
        }
        await self.send(data)
