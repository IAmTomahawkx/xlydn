from discord.ext.commands.context import Context as dpy_context
from discord.ext.commands.core import _convert_to_bool
from twitchio import Context as tio_context
from twitchio.ext.commands import Bot
from .paginators import TextPages, Pages

class CompatContext(dpy_context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system = self.bot.system

    async def paginate(self, text, *, codeblocks=False):
        pages = TextPages(self, text, codeblocks=codeblocks)
        await pages.paginate()

    async def ask(self, q, return_bool=False, timeout=60):
        await self.send(q)
        def pred(msg):
            return msg.author.id == self.author.id and msg.channel.id == self.channel.id

        try:
            m = await self.bot.wait_for("message", check=pred, timeout=timeout)
        except:
            return None

        if return_bool:
            return _convert_to_bool(m.content)

        return m.content

class TwitchContext(tio_context):
    def __init__(self, bot: Bot=None, prefix=None, view=None, message=None, **kwargs):
        super().__init__(message, message.channel, message.author, **kwargs)
        self.message = message
        self.bot = bot
        self.args = []
        self.kwargs = {}
        self.prefix = prefix
        self.command = None
        self.view = view
        self.invoked_with = None
        self.invoked_subcommand = None
        self.subcommand_passed = None
        self.bot = bot
        self.system = bot.system

    async def send_as_streamer(self, message, me=False):
        channel = self.system.twitch_streamer.get_channel(self.channel.name)
        if channel is not None:
            if me:
                return await channel.send_me(message)

            return await channel.send(message)

        return None

    async def send_as_bot(self, message, me=False):
        channel = self.system.twitch_bot.get_channel(self.channel.name)
        if channel is not None:
            if me:
                return await channel.send_me(message)

            return await channel.send(message)

        return None
