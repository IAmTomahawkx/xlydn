import re

import discord
from discord.ext import commands
from addons.common import copypasta

regex = re.compile("(?:https?://)?discord(?:(?:app)?\.com/invite|\.gg)/?[a-zA-Z0-9]+/?")

def setup(bot):
    bot.add_cog(Automod(bot))

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system
        self.short_map = commands.CooldownMapping.from_cooldown(7, 3, commands.BucketType.channel)
        self.long_map = commands.CooldownMapping.from_cooldown(27, 20, commands.BucketType.channel)

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.check_mentions(message)
        await self.check_copypasta(message)
        await self.check_spam(message)

    async def check_mentions(self, message: discord.Message):
        mentions = len(message.mentions)
        if mentions < self.system.config.getint("moderation", "automod_mention_cap", fallback=5):
            return

        user = await self.bot.system.get_user_discord_id(message.author.id)
        if user.editor:
            return

        mod = self.bot.get_cog("Moderation")
        if mod is None:
            return

        await mod.add_strike(message.guild.me, message.author, mentions, self.system.locale("Spamming {0} pings").format(mentions))
        try:
            await message.channel.send(self.system.locale("Added {0} strikes to {1} for spamming {2} mentions").format(mentions, str(message.author), mentions))
        except:
            pass

    async def check_spam(self, message: discord.Message):
        user = await self.bot.system.get_user_discord_id(message.author.id)
        if user.editor:
            return

        if self.short_map.update_rate_limit(message):
            mod = self.bot.get_cog("Moderation")
            if mod is None:
                return

            await mod.add_strike(message.guild.me, message.author, 1,
                                 self.system.locale("Spamming {0} messages in {1} seconds").format(7, 3))

            if message.channel.permissions_for(message.guild.me).manage_messages:
                await message.channel.purge(limit=10, check=lambda m: m.author.id==message.author.id)
            try:
                await message.channel.send(self.system.locale("Added 1 strike to {0} for spamming {1} messages").format(message.author, 7))
            except: pass

        if self.long_map.update_rate_limit(message):
            mod = self.bot.get_cog("Moderation")
            if mod is None:
                return

            await mod.add_strike(message.guild.me, message.author, 1,
                                 self.system.locale("Spamming {0} messages in {1} seconds").format(27, 20))

            try:
                await message.channel.send(
                    self.system.locale("Added 1 strike to {0} for spamming {1} messages").format(message.author, 27))
            except: pass

    async def check_copypasta(self, message):
        for pasta in copypasta.pasta:
            if pasta in message.content.lower():
                mod = self.bot.get_cog("Moderation")
                if mod is None:
                    return

                await mod.add_strike(message.guild.me, message.author, 1,
                                     self.system.locale("Copy pasta"))
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()
                return

    async def check_ads(self, message):
        r = regex.match(message.content)
        if r:
            mod = self.bot.get_cog("Moderation")
            if mod is None:
                return

            await mod.add_strike(message.guild.me, message.author, 1,
                                 self.system.locale("Advertising"))
