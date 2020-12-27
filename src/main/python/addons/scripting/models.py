"""
Licensed under the Open Software License version 3.0
"""
import discord
import twitchio

class PartialChannel:
    __slots__ = "name", "id", "location", "_sender"
    def __init__(self, messagable):
        self._sender = messagable.send
        self.name = getattr(messagable, "name", None)
        self.id = getattr(messagable, "id", None)

        self.location = "discord" if isinstance(messagable, discord.abc.Messageable) else "twitch"

    async def send(self, content: str, embed: discord.Embed=None):
        if self.location == "twitch":
            await self._sender(content)

        else:
            await self._sender(content, embed=embed)

class PartialUser:
    __slots__ = "name", "id", "display_name", "_sender", "bot"
    def __init__(self, user):
        self.name: str = user.name
        self.id: int = user.id
        self.display_name: str = user.display_name
        self.bot = getattr(user, "bot", False)

        if isinstance(user, discord.abc.User) and not isinstance(user, discord.ClientUser):
            self._sender = user.send

        else:
            self._sender = None

    async def send(self, message: str, embed: discord.Embed=None):
        if self._sender:
            await self._sender(message, embed=embed)

    @property
    def can_dm(self):
        return self._sender is not None

class PartialMessage:
    __slots__ = "channel", "author", "embeds", "files", "content", "tags", "view"
    @classmethod
    def from_discord(cls, message: discord.Message):
        self = cls.__new__(cls)

        self.channel = PartialChannel(message.channel)
        self.author = PartialUser(message.author)
        self.embeds = message.embeds
        self.files = message.attachments
        self.content = message.clean_content
        self.tags = None

        return self

    @classmethod
    def from_twitch(cls, message: twitchio.Message):
        self = cls.__new__(cls)

        self.channel = PartialChannel(message.channel)
        self.author = PartialUser(message.author)
        self.tags = message.tags
        self.embeds = None
        self.files = None
        self.content = message.clean_content

        return self

