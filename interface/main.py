import tkinter
import tkinter.ttk
import tkinter.dnd
import tkinter.messagebox
import logging
import asyncio

from utils import token

logger = logging.getLogger("amalna.ui")


class App(tkinter.Tk):
    def __init__(self, core, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.system = core
        self.setup()

    def setup(self):
        self.title("Xlydn")
        self.geometry('600x400')
        self.wm_minsize(400, 200)
        self.notebook = tkinter.ttk.Notebook(self)
        self.setup_home()
        self.setup_connections()
        self.notebook.pack(expand=1, fill="both")

    def setup_home(self):
        frame = tkinter.ttk.Frame(self.notebook)
        self.notebook.add(frame, text=self.system.locale("Dashboard"))

        self.dash_prefix = tkinter.StringVar(value=self.system.config.get("general", "command_prefix"))
        tkinter.ttk.Label(frame, text=self.system.locale("command prefix")).grid(column=1, row=1)
        tkinter.ttk.Entry(frame, textvariable=self.dash_prefix, validate="focusout", validatecommand=self.home_prefix_is_modified).grid(column=1, row=2)

    def setup_connections(self):
        frame = tkinter.ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Connections")

        initial_connect_state = tkinter.NORMAL if not self.system.config.getboolean("general", "connect_on_start", fallback=False) else tkinter.DISABLED
        initial_disconnect_state = tkinter.NORMAL if self.system.config.getboolean("general", "connect_on_start", fallback=False) else tkinter.DISABLED


        self.token_discord = tkinter.StringVar(value=self.system.config.get("tokens", "discord_bot"))
        self.token_streamer = tkinter.StringVar(value=self.system.config.get("tokens", "twitch_streamer_token"))
        self.token_bot = tkinter.StringVar(value=self.system.config.get("tokens", "twitch_bot_token"))
        self.server_name = tkinter.StringVar(value=self.system.config.get("general", "server_name"))
        self.serversearch_text = tkinter.StringVar(value=self.system.config.get("general", "server_about",
                                  fallback=self.system.locale("Not connected to a server")) or self.system.locale("Not connected to a server"))

        tkinter.ttk.Checkbutton(frame)

        tkinter.ttk.Label(frame, text=self.system.locale("Discord bot token")).grid(column=1, row=1)
        self.connections_discordtoken = dtoken = tkinter.ttk.Entry(frame, width=30, textvar=self.token_discord)
        dtoken.grid(column=1, row=2)
        subframe1 = tkinter.ttk.Frame(frame)
        self.connections_discordtoken_connect = dtc = tkinter.ttk.Button(subframe1, text="Connect", command=self.click_discordconnect, state=initial_connect_state)
        self.connections_discordtoken_disconnect = dtdc = tkinter.ttk.Button(subframe1, text="Disconnect", command=self.click_discorddisconnect, state=initial_disconnect_state)
        dtc.grid(column=1, row=1)
        dtdc.grid(column=2, row=1)
        subframe1.grid(column=1, row=3)

        tkinter.ttk.Separator(frame).grid(row=4, pady=5)

        tkinter.ttk.Label(frame, text=self.system.locale("Twitch Streamer token")).grid(column=1, row=5)
        self.connections_twitchstreamer = tstoken = tkinter.ttk.Entry(frame, width=30, textvar=self.token_streamer)
        tstoken.grid(column=1, row=6)
        subframe2 = tkinter.ttk.Frame(frame)
        self.connections_streamertoken_connect = stc = tkinter.ttk.Button(subframe2, text=self.system.locale("Connect"), command=self.click_streamerconnect, state=initial_connect_state)
        self.connections_streamertoken_disconnect = stdc = tkinter.ttk.Button(subframe2, text=self.system.locale("Disconnect"), command=self.click_streamerdisconnect, state=initial_disconnect_state)
        stc.grid(column=1, row=1)
        stdc.grid(column=2, row=1)
        subframe2.grid(column=1, row=7)

        tkinter.ttk.Separator(frame).grid(row=8, pady=5)

        tkinter.ttk.Label(frame, text=self.system.locale("Twitch Bot token")).grid(column=1, row=9)
        self.connections_twitchbot = tbtoken = tkinter.ttk.Entry(frame, width=30, textvar=self.token_bot)
        tbtoken.grid(column=1, row=10)
        subframe3 = tkinter.ttk.Frame(frame)
        self.connections_bottoken_connect = btc = tkinter.ttk.Button(subframe3, text=self.system.locale("Connect"), command=self.click_botconnect, state=initial_connect_state)
        self.connections_bottoken_disconnect = btdc = tkinter.ttk.Button(subframe3, text=self.system.locale("Disconnect"), command=self.click_botdisconnect, state=initial_disconnect_state)
        btc.grid(column=1, row=1)
        btdc.grid(column=2, row=1)
        subframe3.grid(column=1, row=11)

        tkinter.ttk.Separator(frame).grid(row=12, pady=10)

        self.connections_servername = sname = tkinter.ttk.Entry(frame, width=30, textvar=self.server_name)
        sname.grid(row=13, column=1)
        self.connections_serversearch = srvsrch = tkinter.ttk.Button(frame, text=self.system.locale("Search servers"), command=self.connections_search_guild_name, state=initial_disconnect_state)
        srvsrch.grid(row=13, column=2)
        self.connections_serversearch_label = tkinter.ttk.Label(frame, textvar=self.serversearch_text)
        self.connections_serversearch_label.grid(row=14, column=1)

    def home_prefix_is_modified(self):
        self.system.config.set("general", "command_prefix", self.dash_prefix.get())
        return True

    def home_status_is_modified(self):
        self.system.config.set("general", "discord_presence", self.dash_prefix.get())
        return True

    def connections_search_guild_name(self):
        pre = self.serversearch_text.get()
        def resetlabel():
            self.serversearch_text.set(pre)

        if not self.system.discord_bot.is_ready():
            self.serversearch_text.set(self.system.locale("Failed: Discord Bot is not connected!"))
            self.after(2000, resetlabel)
            return

        bot = self.system.discord_bot
        name = self.server_name.get()
        for guild in bot.guilds:
            if guild.name == name.strip():
                fmt = self.system.locale("Server name: {0}\nServer id: {2}\nServer Owner: {2}").format(guild.name, guild.id, guild.owner)
                self.serversearch_text.set(self.system.locale("Connected to a server\n{0}").format(fmt))
                self.system.config.set("general", "server_about", fmt)
                self.system.config.set("general", "server_id", str(guild.id))
                self.system.config.set("general", "server_name", guild.name)
                return

        self.serversearch_text.set(self.system.locale("No server found with the name \"{0}\"").format(name))


    def connections_swap_discord_connect_state(self, connected: bool):
        self.connections_discordtoken_connect['state'] = tkinter.DISABLED if connected else tkinter.NORMAL
        self.connections_discordtoken_disconnect['state'] = tkinter.NORMAL if connected else tkinter.DISABLED
        self.connections_serversearch['state'] = tkinter.NORMAL if connected else tkinter.DISABLED

    def connections_swap_streamer_connect_state(self, connected: bool):
        self.connections_streamertoken_connect['state'] = tkinter.DISABLED if connected else tkinter.NORMAL
        self.connections_streamertoken_disconnect['state'] = tkinter.NORMAL if connected else tkinter.DISABLED

    def connections_swap_bot_connect_state(self, connected: bool):
        self.connections_bottoken_connect['state'] = tkinter.DISABLED if connected else tkinter.NORMAL
        self.connections_bottoken_disconnect['state'] = tkinter.NORMAL if connected else tkinter.DISABLED

    def click_discordconnect(self):
        logger.debug("(DISCORD CLIENT) attempting to connect...")
        self.connections_swap_discord_connect_state(True)
        self.system.config.set("tokens", "discord_bot", self.token_discord.get())
        self.system.connect_discord_bot()

    def click_discorddisconnect(self):
        logger.debug("(DISCORD CLIENT) disconnecting...")
        self.connections_swap_discord_connect_state(False)
        self.system.disconnect_discord_bot()

    def click_streamerconnect(self):
        logger.debug("(STREAMER CLIENT) attempting to connect...")
        self.connections_swap_streamer_connect_state(True)
        v = self.system.config.get("tokens", "twitch_streamer_token")
        if v != self.token_streamer.get():
            self.system.loop.create_task(self.grab_refresh_streamer())

        self.system.config.set("tokens", "twitch_streamer_token", self.token_streamer.get())
        self.system.connect_twitch_streamer()

    def click_streamerdisconnect(self):
        logger.debug("(STREAMER CLIENT) disconnecting...")
        self.connections_swap_streamer_connect_state(False)
        self.system.disconnect_twitch_streamer()

    def click_botconnect(self):
        logger.debug("(BOT CLIENT) attempting to connect...")
        self.connections_swap_bot_connect_state(True)
        v = self.system.config.get("tokens", "twitch_bot_token")
        if v != self.token_bot.get():
            self.system.loop.create_task(self.grab_refresh_bot())

        self.system.config.set("tokens", "twitch_bot_token", self.token_bot.get())
        self.system.connect_twitch_bot()

    def click_botdisconnect(self):
        logger.debug("(BOT CLIENT) disconnecting...")
        self.connections_swap_bot_connect_state(False)
        self.system.disconnect_twitch_bot()

    async def grab_refresh_streamer(self):
        t = self.system.config.get("tokens", "twitch_streamer_token")

        refresh = await token.get_refresh_token(self.system, t)
        if refresh is not None:
            self.system.config.set("tokens", "twitch_streamer_refresh", refresh)

    async def grab_refresh_bot(self):
        t = self.system.config.get("tokens", "twitch_bot_token")

        refresh = await token.get_refresh_token(self.system, t)
        if refresh is not None:
            self.system.config.set("tokens", "twitch_bot_refresh", refresh)

    async def mainloop(self):
        while self.system.alive:
            try:
                self.update()
                await asyncio.sleep(1/120)
            except tkinter.TclError:
                return


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    class _fakeconfig:
        def get(self, a, b, fallback=None):
            return fallback or "testing"

    class c:
        alive = True
        config = _fakeconfig()
        def close(self):
            pass


    app = App(c())
    test = tkinter.Label(app, text="test")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.mainloop())