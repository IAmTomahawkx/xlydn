"""
Licensed under the Open Software License version 3.0
"""
import re
from typing import Optional

import discord
import yarl
from discord.ext import commands
from utils.commands import command, group

from addons.common import copypasta
from utils.checks import dpy_check_editor

regex = re.compile("(?:https?://)?discord(?:(?:app)?\.com/invite|\.gg)/?[a-zA-Z0-9]+/?")

def setup(bot):
    bot.add_cog(AutoModeration(bot))

class URLConverter(commands.Converter):
    async def convert(self, ctx, argument):
        resp = yarl.URL(argument)
        if not resp.is_absolute():
            raise commands.UserInputError(ctx.bot.system.locale("This is not a valid url"))

        return resp

class AutoModeration(commands.Cog):
    HELP_REQUIRES = ["editor"]

    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system
        self.locale_name = bot.system.locale("AutoModeration")
        self.short_map = commands.CooldownMapping.from_cooldown(7, 3, commands.BucketType.channel)
        self.long_map = commands.CooldownMapping.from_cooldown(27, 20, commands.BucketType.channel)

    @group()
    @dpy_check_editor()
    async def automod(self, ctx):
        """
        Controls automod for your server.
        Requires you to be a bot editor
        """
        pass

    @automod.group(invoke_without_command=True)
    @dpy_check_editor()
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def ads(self, ctx, state: bool=None):
        """
        Enable/disable ad protection.
        Ad protection will prevent users from posting links such as discord invites,
        and messages containing the blacklisted domains.
        Automod will give strikes, so be sure your moderation system is set up.
        """
        if state is not None:
            self.system.config.set("moderation", "automod_enable_ads", str(state))
            await ctx.send(self.system.locale("Ad protection is now {0}").format(self.system.locale("on") if state else self.system.locale("off")))

        else:
            if self.system.config.getboolean("moderation", "automod_enable_ads", fallback=False):
                fmt = self.system.locale("Ad protection is enabled")

            else:
                fmt = self.system.locale("Ad protection is not enabled")

            await ctx.send(fmt)

    @ads.command()
    @dpy_check_editor()
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def add(self, ctx, url: URLConverter):
        """
        Adds a domain to the blacklist.
        Blacklisted links will automatically be deleted
        """
        try:
            await self.system.db.execute("INSERT INTO automod_domains VALUES (?);", url.host)
        except:
            return await ctx.send(self.system.locale("This domain has already been blacklisted"))

        await self.system.build_automod_regex()
        await ctx.send(self.system.locale("Added {0} to the domain blacklist").format(url.host))

    @ads.command()
    @dpy_check_editor()
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def remove(self, ctx, url: URLConverter):
        """
        Removes a domain from the blacklist.
        Blacklisted links will automatically be deleted
        """
        if url.host not in self.system.automod_domains:
            return await ctx.send(self.system.locale("This domain is not blacklisted"))

        await self.system.db.execute("DELETE FROM automod_domains WHERE domain = ?", url.host)
        await self.system.build_automod_regex()
        await ctx.send(self.system.locale("{0} is no longer blacklisted").format(url.host))

    @automod.command()
    @dpy_check_editor()
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def spam(self, ctx, state: bool = None):
        """
        Enable/disable spam protection.
        Automod will give strikes, so be sure your moderation system is set up.
        """
        if state is not None:
            self.system.config.set("moderation", "automod_enable_spam", str(state))
            await ctx.send(self.system.locale("Spam protection is now {0}").format(self.system.locale("on") if state else self.system.locale("off")))

        else:
            if self.system.config.getboolean("moderation", "automod_enable_spam", fallback=False):
                fmt = self.system.locale("Spam protection is enabled")

            else:
                fmt = self.system.locale("Spam protection is not enabled")

            await ctx.send(fmt)

    @automod.command()
    @dpy_check_editor()
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def copypasta(self, ctx, state: bool = None):
        """
        Enable/disable copypasta protection.
        Prevents users from posting copypastas such as memecat or fake hacker warnings.
        Automod will give strikes, so be sure your moderation system is set up.
        """
        if state is not None:
            self.system.config.set("moderation", "automod_enable_copypasta", str(state))
            await ctx.send(self.system.locale("Copypasta protection is now {0}").format(self.system.locale("on") if state else self.system.locale("off")))

        else:
            if self.system.config.getboolean("moderation", "automod_enable_copypasta", fallback=False):
                fmt = self.system.locale("Copypasta protection is enabled")

            else:
                fmt = self.system.locale("Copypasta protection is not enabled")

            await ctx.send(fmt)

    @automod.command()
    @dpy_check_editor()
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def mentions(self, ctx, state: Optional[bool] = None, limit: int = None):
        """
        Enable/disable mention spam protection.
        The `limit` argument can passed the number of people that can be mentioned before automod kicks in.
        Automod will give strikes, so be sure your moderation system is set up.
        """
        if state is not None:
            self.system.config.set("moderation", "automod_enable_mentions", str(state))
            await ctx.send(self.system.locale("Mention spam protection is now {0}").format(self.system.locale("on") if state else self.system.locale("off")))

        if limit is not None:
            self.system.config.set("moderation", "automod_mention_cap", str(limit))
            await ctx.send(self.system.locale("Mentioning {0} people will now trigger automod").format(limit))

        if state is None and limit is None:
            if self.system.config.getboolean("moderation", "automod_enable_mentions", fallback=False):
                fmt = self.system.locale("Mention spam protection is enabled, and requres {0} mentions to trigger").format(
                    self.system.config.getint("moderation", "automod_mentions_cap", fallback=5)
                )

            else:
                fmt = self.system.locale("Mention spam protection is not enabled")

            await ctx.send(fmt)

    @commands.Cog.listener()
    async def on_message(self, message):
        usr = await self.system.get_user_discord_id(message.author.id)
        if usr.editor:
            return

        if self.system.config.getboolean("moderation", "automod_enable_mentions", fallback=False):
            await self.check_mentions(message)

        if self.system.config.getboolean("moderation", "automod_enable_copypasta", fallback=False):
            await self.check_copypasta(message)

        if self.system.config.getboolean("moderation", "automod_enable_spam", fallback=False):
            await self.check_spam(message)

        if self.system.config.getboolean("moderation", "automod_enable_ads", fallback=False):
            await self.check_ads(message)

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

            if message.channel.permissions_for(message.guild.me).manage_messages:
                await message.delete()
