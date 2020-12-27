"""
Licensed under the Open Software License version 3.0
"""
import discord
from discord.ext import commands
import traceback
import logging

from utils import errors

logger = logging.getLogger("xlydn.discord.errors")

def setup(bot):
    bot.add_cog(Handler(bot))

class Handler(commands.Cog):
    HELP_REQUIRES = ["hide"]
    def __init__(self, bot):
        self.bot = bot
        self.locale_name = bot.system.locale("Handler")

    @commands.Cog.listener()
    async def on_error(self, exception):
        logger.exception("something went wrong", exc_info=exception)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.CommandNotFound):
            return

        if isinstance(exception, commands.CommandInvokeError):
            if isinstance(exception, discord.Forbidden):
                return # rip

        if isinstance(exception, errors.GuildCheckFailed):
            return await ctx.send(self.bot.system.locale("You may not use commands in this server"))

        if isinstance(exception, commands.MissingRequiredArgument):
            return await ctx.send(self.bot.system.locale("Missing arguments! see `{0}`").format(f"{ctx.prefix}help {ctx.command.qualified_name}"))

        if isinstance(exception, commands.BotMissingPermissions):
            missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in exception.missing_perms]
            return await ctx.send(self.bot.system.locale("I'm missing permissions to run this command! I need {0}!").format(", ".join(missing)))

        if isinstance(exception, commands.CheckFailure):
            return await ctx.send(self.bot.system.locale("You do not have permission to use this command"))

        if isinstance(exception, commands.MaxConcurrencyReached):
            return await ctx.send(self.bot.system.locale("Too many people are using this command at once"))

        if isinstance(exception, commands.CommandOnCooldown):
            return await ctx.send(self.bot.system.locale("This command is on cooldown for another {0} seconds").format(round(exception.retry_after)))

        if isinstance(exception, commands.NotOwner):
            return await ctx.send(self.bot.system.locale("You must own this bot to use this command"))

        if isinstance(exception, commands.NoPrivateMessage):
            return await ctx.send(self.bot.system.locale("This command can not be used in dms"))

        tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        logger.exception(f"command {ctx.command.qualified_name} | user {ctx.author} | guild {ctx.guild.id if ctx.guild else None}", exc_info=exception)
        await ctx.paginate(tb, codeblocks=True)
