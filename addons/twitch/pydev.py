import twitchio
from twitchio.ext import commands
from discord.ext import commands as dpy

def setup(bot):
    bot.add_cog(PyDev(bot))

class PyDev(dpy.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.core = bot.system
