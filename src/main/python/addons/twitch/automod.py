"""
Licensed under the Open Software License version 3.0
"""
import discord
from discord.ext import commands


def setup(bot):
    bot.add_cog(Automod(bot))

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system

    @commands.Cog.listener()
    async def on_message(self, message):
        pass

