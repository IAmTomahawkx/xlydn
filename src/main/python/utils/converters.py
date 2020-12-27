"""
Licensed under the Open Software License version 3.0
"""
from discord.ext import commands


class PositionalArgumentChecker(commands.Converter):
    def __init__(self, word, value=None):
        self.word = word
        self.value = value

    async def convert(self, ctx, argument):
        if self.word in argument.lower():
            return self.value if self.value is not None else argument

        raise ValueError

class NoDiscordChecker(PositionalArgumentChecker):
    word = "nodiscord"
    value = True
    def __init__(self):
        pass

class NoTwitchChecker(PositionalArgumentChecker):
    word = "notwitch"
    value = True
    def __init__(self):
        pass