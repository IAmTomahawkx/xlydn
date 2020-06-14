import discord
from discord.ext import commands
import aiohttp

def setup(bot):
    bot.add_cog(Linker(bot))


class Linker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system

    @commands.command(aliases=['chat'])
    async def viewers(self, ctx):
        pass

    @commands.command()
    @commands.guild_only()
    async def link(self, ctx):
        user = await self.system.get_user_discord_id(ctx.author.id, create=False)
        if user is not None and user.twitch_name is not None:
            return await ctx.send(self.system.locale("You have already connected to {0}!").format(user.twitch_name))

        try:
            complete = await self.system.link_from_discord(ctx, ctx.author.id)
        except aiohttp.ClientResponseError as e:
            if e.status == 521:
                return await ctx.send(self.system.locale("Uh oh! Looks like the website is currently offline! Try again later"))
            else:
                raise

        if complete:
            user = await self.system.get_user_discord_id(ctx.author.id)
            name = user.twitch_name
            await ctx.send(self.system.locale("{0}, Successfully connected to {1} on twitch").format(ctx.author.mention, name))

        else:
            await ctx.send(self.system.locale("{0}, failed to connect to a twitch account"))