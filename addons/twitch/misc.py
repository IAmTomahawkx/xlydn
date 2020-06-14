import twitchio
from discord.ext import commands
import aiohttp

def setup(bot):
    bot.add_cog(Linker(bot))


class Linker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system

    @commands.command()
    @commands.guild_only()
    async def link(self, ctx: twitchio.Context):
        user = await self.system.get_user_twitch_name(ctx.author.id, create=False)
        if user is not None and user.discord_id is not None:
            return await ctx.send(self.system.locale("You have already connected to a discord user!"))

        try:
            complete = await self.system.link_from_twitch(ctx, ctx.author.name)
        except aiohttp.ClientResponseError as e:
            if e.status == 521:
                return await ctx.send(self.system.locale("Uh oh! Looks like the website is currently offline! Try again later"))
            else:
                raise

        if complete:
            user = await self.system.get_user_twitch_name(ctx.author.name, id=ctx.author.id)
            uid = user.discord_id
            u = self.system.discord_bot.get_user(uid)
            if u is None:
                u = await self.system.discord_bot.fetch_user(user)

            await ctx.send(self.system.locale("{0}, Successfully connected to {1} on discord").format(ctx.author.name, str(u)))

        else:
            await ctx.send(self.system.locale("{0}, failed to connect to a discord account"))