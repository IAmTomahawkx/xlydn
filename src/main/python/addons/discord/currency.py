"""
Licensed under the Open Software License version 3.0
"""
from typing import Any
import time
import discord
from discord.ext import commands
import humanize

from utils.commands import command, group
from utils.checks import dpy_check_editor

def setup(bot):
    bot.add_cog(Currency(bot))

class Bucket:
    def __init__(self, rate: int, per: int, bonus: bool=False):
        self._min_keys = rate
        self._decay = per
        self._bonus = bonus
        self.keys = []
        self._lock = None

    def update_setters(self, rate: int, per: int) -> None:
        self._min_keys = rate
        self._decay = per
        self._remove_decayed_keys(time.time())

    def _remove_decayed_keys(self, now: float) -> None:
        to_delete = [x for x in self.keys if x + self._decay < now]
        for key in to_delete:
            self.keys.remove(key)

    def update(self, now: float = None) -> bool:
        if now is None:
            now = time.time()

        if self._lock is not None:
            if now > self._lock:
                self._lock = None

        self._remove_decayed_keys(now)
        self.keys.append(now)
        if self.is_triggered:
            self._lock = time.time() + (self._decay if not self._bonus else 3600)
            return True

        return False

    def reset(self):
        self.keys = list()
        self._lock = None

    @property
    def is_locked(self) -> bool:
        return self._lock is not None

    @property
    def is_triggered(self) -> bool:
        self._remove_decayed_keys(time.time())
        return len(self.keys) > self._min_keys and not self.is_locked

    @property
    def is_empty(self) -> bool:
        return len(self.keys) is 0

class ActivityMapping:
    def __init__(self, rate: int, per: int):
        self._rate = rate
        self._per = per
        self._lower_cache = {}
        self._bonus_cache = {}

    def set_rates(self, rate: int, per: int) -> None:
        self._rate = rate
        self._per = per
        for bucket in self._lower_cache.values():
            bucket.update_setters(rate, per)

        for bucket in self._bonus_cache.values():
            bucket.update_setters(rate, per)

    def get_bucket(self, key: Any) -> (Bucket, Bucket):
        lower = self._lower_cache.get(key, None)
        higher = self._bonus_cache.get(key, None)

        if lower is None:
            lower = Bucket(self._rate, self._per)
            self._lower_cache[key] = lower

        if higher is None:
            higher = Bucket(self._rate * 3, self._per)
            self._bonus_cache[key] = higher

        return lower, higher

    def _clear_dead_keys(self, now: float) -> None:
        to_remove = []
        for key, bucket in self._lower_cache.items():
            bucket._remove_decayed_keys(now)
            if bucket.is_empty and not bucket.is_locked:
                to_remove.append(key)

        for key in to_remove:
            del self._lower_cache[key]

        to_remove = []
        for key, bucket in self._bonus_cache.items():
            bucket._remove_decayed_keys(now)
            if bucket.is_empty and not bucket.is_locked:
                to_remove.append(key)

        for key in to_remove:
            del self._bonus_cache[key]

    def update_limit(self, msg: discord.Message, now: float = None) -> (bool, bool):
        if now is None:
            now = time.time()

        self._clear_dead_keys(now)
        lower, higher = self.get_bucket(msg.author.id)
        lower.update(now)
        higher.update(now)
        return lower.is_triggered, higher.is_triggered


class Currency(commands.Cog):
    HELP_REQUIRES = []
    def __init__(self, bot):
        self.bot = bot
        self.locale_name = bot.system.locale("Currency")
        self.activity = ActivityMapping(
            bot.system.config.getint("currency", "activity_discord_payout_rate", fallback=5),
            bot.system.config.getint("currency", "activity_discord_payout_per", fallback=15) * 60
        )
        self.quick_ignore = []

    async def add_user_points(self, uid: int, amount: int):
        existing = await self.bot.system.db.fetchval("SELECT points FROM accounts WHERE discord_id = ?", uid)
        if existing is not None:
            await self.bot.db.execute("UPDATE accounts SET points = ? WHERE discord_id = ?", amount + existing, uid)
        else:
            await self.bot.db.execute("INSERT INTO accounts VALUES (null, null, ?, ?, 0.0);", uid, amount)

    async def award_buckets(self, user: discord.User, low: bool, high: bool):
        payout = self.bot.system.config.getint("currency", "discord_activity_payout")
        multi = self.bot.system.config.getint("currency", "discord_bonus_multiplier")

        if low and high:
            await self.add_user_points(user.id, payout +
                                       (payout * multi))
            return

        elif low:
            await self.add_user_points(user.id, payout)

        elif high:
            await self.add_user_points(user.id, payout * multi)


    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild or msg.author.bot:
            return

        a, b = self.activity.update_limit(msg)
        await self.award_buckets(msg.author, a, b)

    @command()
    @commands.guild_only()
    @dpy_check_editor()
    async def settings(self, ctx):
        """
        shows the currency settings
        """
        pass # TODO

    @command()
    @commands.guild_only()
    @dpy_check_editor()
    async def addpoints(self, ctx, target: discord.Member, amount: int):
        await self.add_user_points(target.id, amount)
        await ctx.message.add_reaction("\U0001f44c")

    @command()
    @commands.guild_only()
    @dpy_check_editor()
    async def removepoints(self, ctx, target: discord.Member, amount: int):
        await self.add_user_points(target.id, amount*-1)
        await ctx.message.add_reaction("\U0001f44c")
