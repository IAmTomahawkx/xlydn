import discord
from discord.ext import commands
import traceback
import logging

logger = logging.getLogger("amalna.discord.errors")

def setup(bot):
    bot.add_cog(Handler(bot))

class Handler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.CommandNotFound):
            return

        elif isinstance(exception, commands.MissingRequiredArgument):
            await ctx.send(self.bot.system.locale("Missing arguments! see `{0}`").format(f"{ctx.prefix}help {ctx.command.qualified_name}"))

        else:
            tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            logger.exception(f"command {ctx.command.qualified_name} | user {ctx.author} | guild {ctx.guild.id if ctx.guild else None}", exc_info=exception)
            await ctx.paginate(tb, codeblocks=True)