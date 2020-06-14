import time
import random

from discord.ext import commands
import discord

def setup(bot):
    bot.add_cog(Quotes(bot))

class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system

    @commands.command()
    async def addquote(self, ctx, *, quote):
        await self.system.db.execute("INSERT INTO quotes VALUES (?,?);", quote, int(time.time()))
        await ctx.send(self.system.locale("Added quote"))

    @commands.command(aliases=['removequote', 'rmquote'])
    async def deletequote(self, ctx, num: int):
        if num < 1:
            return await ctx.send(self.system.locale("Please input a valid quote"))

        num -= 1
        quotes = await self.system.db.fetch("SELECT * FROM quotes ORDER BY insert_time;")
        if len(quotes) <= num:
            return await ctx.send(self.system.locale("Please input a valid quote"))

        quote = quotes[num]
        await self.system.db.execute("DELETE FROM quotes WHERE insert_time = ?", quote[1])
        await ctx.send(self.system.locale("Removed quote {0}").format(num+1))

    @commands.command()
    async def quote(self, ctx, num: int = None):
        if num:
            if num < 1:
                return await ctx.send(self.system.locale("Please input a valid quote"))

            num -= 1
            quotes = await self.system.db.fetch("SELECT * FROM quotes ORDER BY insert_time;")
            if len(quotes) <= num:
                return await ctx.send(self.system.locale("Please input a valid quote"))

            await ctx.send(f"#{num}: {quotes[num][0]}")

        else:
            quotes = await self.system.db.fetch("SELECT * FROM quotes ORDER BY insert_time;")
            if not quotes:
                return await ctx.send(self.system.locale("No quotes found"))
            num = random.randint(1, len(quotes))

            await ctx.send(f"#{num}: {quotes[num-1][0]}")
