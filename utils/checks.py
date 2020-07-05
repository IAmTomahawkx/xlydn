import discord
from discord.ext import commands

def dpy_check_editor():
    async def predicate(ctx):
        if ctx.bot.system.config.get("developer", "dev_mode", fallback=False):
            return True

        if await ctx.bot.is_owner(ctx.author):
            return True

        user = await ctx.bot.system.get_user_discord_id(ctx.author.id)
        return user.editor

    return commands.check(predicate)

def tio_check_editor():
    async def predicate(ctx):
        if ctx.bot.system.config.get("developer", "dev_mode", fallback=False):
            return True

        user = await ctx.bot.system.get_user_twitch_name(ctx.author.name, ctx.author.id)
        return user.editor

    return commands.check(predicate)