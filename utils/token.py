
BASE_URL = "https://bot.idevision.net/"
BASE_OAUTH_REDIRECT = "https://discord.com/api/oauth2/authorize?client_id=717915021534953472&redirect_uri=https%3A%2F%2bot.idevision.net%2Foauth%2Fdiscord&response_type=code&scope=identify%20connections"
#BASE_OAUTH_REDIRECT = "https://discord.com/api/oauth2/authorize?client_id=717915021534953472&redirect_uri=http%3A%2F%2F127.0.0.1%3A8334%2Foauth%2Fdiscord&response_type=code&scope=identify%20connections"

async def try_streamer_refresh(core, session):
    v = core.config.get("tokens", "twitch_streamer_refresh")
    if not v:
        return None # prompt the user to revalidate

    async with session.post(BASE_URL + "bot/refresh", headers={"Refresh": v}) as resp:
        if 200 > resp.status < 299:
            return None # prompt time

        data = await resp.json()
        core.config.set("tokens", "twitch_streamer_refresh", data['Refresh'])
        core.config.set("tokens", "twitch_streamer_token", data["Authorization"])
        return data['Authorization']

async def try_bot_refresh(core, session):
    v = core.config.get("tokens", "twitch_bot_refresh")
    if not v:
        return None  # prompt the user to revalidate

    async with session.post(BASE_URL + "bot/refresh", headers={"Refresh": v}) as resp:
        if 200 > resp.status < 299:
            return None  # prompt time

        data = await resp.json()
        core.config.set("tokens", "twitch_bot_refresh", data['Refresh'])
        core.config.set("tokens", "twitch_bot_token", data["Authorization"])
        return data['Authorization']

async def prompt_user_for_token(system, session, who="Streamer"):
    import webbrowser
    webbrowser.open_new("https://bot.idevision.net/user/token_warning?who="+who)
    import colorama
    print(colorama.Fore.RED + f"{who} token is invalid. disconnected." + colorama.Fore.RESET)
    if who == "Streamer":
        system.disconnect_twitch_streamer()
        system.interface.connections_swap_streamer_connect_state(False)
    else:
        system.disconnect_twitch_bot()
        system.interface.connections_swap_bot_connect_state(False)

async def prompt_user_for_discord_token(core, session, who="Discord Bot"):
    pass

async def get_refresh_token(system, token):
    async with system.session.get(BASE_URL + "bot/refresh", headers={"Authorization": token}) as resp:
        if resp.status != 200:
            print(resp.status)
            return None

        v = await resp.json()
        print(v)
        return v['token']