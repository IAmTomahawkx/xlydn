import traceback
from utils import commands
from discord.ext import commands as dpy_commands
from utils import paginators

def setup(bot):
    bot.add_cog(ScriptManager(bot))

class ScriptManager(dpy_commands.Cog):
    HELP_REQUIRES = ["owner"]
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system
        self.locale_bot = bot.system.locale("Script Manager")
        self.scripts = bot.system.scripts

    @commands.group("script", aliases=['scripts'], invoke_without_command=True)
    async def scripts(self, ctx):

        entries = []
        for script in self.scripts.scripts.values():
            entries.append(("\u200b", self.system.locale("Script name: {0}\nScript id: {1}\nEnabled: {2}\nAuthor: {3}\nVersion: {4}")
                            .format(script.name, script.identifier, script.enabled, script.author, script.version)))

        pages = paginators.FieldPages(ctx, entries=entries)
        await pages.paginate()

    @scripts.command()
    async def reload(self, ctx, script_id: str):
        if script_id not in self.scripts.scripts:
            return await ctx.send(self.system.locale("No script with that identifier found"))

        await ctx.send(self.system.locale("Reloading {0}").format(script_id))

        try:
            await self.scripts.reload_script(script_id)
        except Exception as e:
            pages = paginators.TextPages(ctx, "".join(traceback.format_exception(type(e), e, e.__traceback__)))