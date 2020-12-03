import asyncio
import webbrowser
import logging
import os
from typing import Optional

import aiohttp
import colorama

BASE_URL = "https://bot.idevision.net/"
BASE_OAUTH_REDIRECT = "https://discord.com/api/oauth2/authorize?client_id=717915021534953472&redirect_uri=https%3A%2F%2bot.idevision.net%2Foauth%2Fdiscord&response_type=code&scope=identify%20connections"
#BASE_OAUTH_REDIRECT = "https://discord.com/api/oauth2/authorize?client_id=717915021534953472&redirect_uri=http%3A%2F%2F127.0.0.1%3A8334%2Foauth%2Fdiscord&response_type=code&scope=identify%20connections"

logger = logging.getLogger("xlydn.api")

class XlydnApi:
    def __init__(self, system):
        self.sys = system
        asyncio.get_event_loop().create_task(self._ainit())

    async def _ainit(self):
        self.session = aiohttp.ClientSession()

    async def try_streamer_refresh(self):
        core = self.sys
        v = core.config.get("tokens", "twitch_streamer_refresh")
        if not v:
            return None # prompt the user to revalidate

        async with self.session.post(BASE_URL + "api/v2/tokens/refresh", json={"refresh_token": v}) as resp:
            if 200 > resp.status or 299 < resp.status:
                return None # prompt time

            data = await resp.json()
            core.config.set("tokens", "twitch_streamer_refresh", data['refresh'])
            core.config.set("tokens", "twitch_streamer_token", data["token"])
            return data['token']

    async def try_bot_refresh(self):
        core = self.sys
        v = core.config.get("tokens", "twitch_bot_refresh")
        if not v:
            return None  # prompt the user to revalidate

        async with self.session.post(BASE_URL + "api/v2/tokens/refresh") as resp:
            if 200 > resp.status or 299 < resp.status:
                return None  # prompt time

            data = await resp.json()
            core.config.set("tokens", "twitch_bot_refresh", data['refresh'])
            core.config.set("tokens", "twitch_bot_token", data["token"])
            return data['token']

    async def prompt_user_for_token(self, who="Streamer"):
        system = self.sys
        webbrowser.open_new(BASE_URL + "user/token_warning?who="+who)
        print(colorama.Fore.RED + f"{who} token is invalid. disconnected." + colorama.Fore.RESET)
        if who == "Streamer":
            system.disconnect_twitch_streamer()
            system.interface.connections_swap_streamer_connect_state(False)
        else:
            system.disconnect_twitch_bot()
            system.interface.connections_swap_bot_connect_state(False)

    async def get_refresh_token(self, token: str) -> Optional[str]:
        async with self.session.post(BASE_URL + "api/v2/token/capture_refresh", json={"token": token}) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            return data['token']

    async def get_user(self, *, discord_id: int = None, twitch_name: str = None):
        pass

    async def do_hello(self):
        data = {
            "twitch_token": self.sys.config.get("tokens", "twitch_bot_token"),
            "discord_token": self.sys.config.get("tokens", "discord_bot"),
            "streamer_token": self.sys.config.get("tokens", "twitch_streamer_token"),
            "id": self.sys.id
        }
        async with self.session.post(BASE_URL + "api/v2/bot/identify", json=data) as resp:
            if resp.status == 200:
                logger.info("successfully done hello")

            elif resp.status == 201:
                data = await resp.json()
                logger.debug(f"Recieved new client id from the api: {data}")
                logger.warning(f"We have been assigned a new client id: {data['id']}, {data['given_id']}")
                self.sys.id = data['given_id']
                with open(os.path.join("services", ".dfuuid.lock"), "w") as f:
                    f.write(data['given_id'])

            elif 200 > resp.status or resp.status > 299:
                logger.error(f"The api encountered an issue. {resp.status} {await resp.text()}")