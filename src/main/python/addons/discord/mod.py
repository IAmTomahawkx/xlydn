from typing import Optional, Union
import gzip
import json
import time
import os
import datetime

import discord
from discord.ext import commands

from utils import time as timeutil
from utils.commands import command, group


def setup(bot):
    bot.add_cog(Moderation(bot))

class ActionConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower()
        if argument in ("tempmute", "temp mute", "temporary mute", "mute"):
            return 1
        if argument in ("kick", "boot"):
            return 2
        if argument in ("tempban", "temp ban", "temporary ban"):
            return 3
        if argument in ("ban",):
            return 4

        try:
            return int(argument)
        except:
            pass

        raise commands.UserInputError(ctx.bot.system.locale("Invalid action! Try 'tempmute', 'kick', 'tempban' or 'ban'"))

class StrikesValues:
    def __init__(self, config):
        self.config = config
        self.actions = {
            1: self.punish_tempmute,
            2: self.punish_kick,
            3: self.punish_softban,
            4: self.punish_tempban,
            5: self.punish_ban
        }
        if os.path.exists(os.path.join(os.curdir, "services", "modstriking.bin")):
            with open(os.path.join(os.curdir, "services", "modstriking.bin"), "rb") as f:
                self._value = json.loads(gzip.decompress(f.read()).decode())

        else:
            self._value = {
                "levels": {},
                "temp_lengths": {}
            }
            try:
                with open(os.path.join(os.curdir, "services", "modstriking.bin"), "wb") as f:
                    f.write(gzip.compress(json.dumps(self._value).encode()))

            except FileNotFoundError: # travisCI is stupid
                pass


    def save(self):
        with open(os.path.join(os.curdir, "services", "modstriking.bin"), "wb") as f:
            f.write(gzip.compress(json.dumps(self._value).encode()))

    def punishment(self, n: int):
        try:
            value = self._value['levels'][str(n)]
        except KeyError:
            max_level = max([int(x) for x in self._value['levels'].keys()])
            if max_level < n:
                return self.punish_ban

            return None

        return self.actions[value]

    async def pardon(self, bot, mod, target, prev, after, case, reason):
        return bot.system.locale(
            "`[{0}]` \U0001f4f0 **{1}** removed {7} strikes from *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given"),
                                                    prev - after)

    async def punish_none(self, bot, mod, target, prev, after, case, reason):
        return bot.system.locale("`[{0}]` \U0001f5de **{1}** gave {7} strikes to *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given"), after-prev)

    async def punish_tempmute(self, bot, mod, target: discord.Member, prev: int, after: int, case: int, reason):
        length = self._value['temp_lengths'][str(after)]
        await bot.system.schedule_timer(datetime.datetime.fromtimestamp(time.time() + length), "member_strike_unmute",
                                        userid=target.id)
        mid = self.config.getint("moderation", "mute_role", fallback=0)
        m = target.guild.get_role(mid)
        if not m:
            return bot.system.locale("**Warning: failed to tempmute, invalid mute role**\n`[{0}]` \U0001f910 **{1}** tempmuted *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
                case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given")
            )

        await target.add_roles(m, reason="tempmute")
        return bot.system.locale(
            "`[{0}]` \U0001f910 **{1}** tempmuted *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given")
        )

    async def punish_kick(self, bot, mod, target: discord.Member, prev: int, after: int, case: int, reason):
        await target.kick(reason=reason)
        return bot.system.locale(
            "`[{0}]` \U0001f462 **{1}** kicked *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given"))

    async def punish_softban(self, bot, mod, target: discord.Member, prev: int, after: int, case: int, reason):
        await target.ban(reason=reason)
        await target.unban(reason=reason)
        return bot.system.locale(
            "`[{0}]` \U0001fa93 **{1}** kicked *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given"))

    async def punish_tempban(self, bot, mod, target: discord.Member, prev: int, after: int, case: int, reason):
        length = self._value['temp_lengths'][str(after)]
        await target.ban(reason=reason)
        await bot.system.schedule_timer(datetime.datetime.fromtimestamp(time.time()+length), "member_strike_unban", userid=target.id)
        return bot.system.locale("`[{0}]` \U0001f528 **{1}** tempbanned *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given"))

    async def punish_ban(self, bot, mod, target: discord.Member, prev: int, after: int, case: int, reason):
        await target.ban()
        return bot.system.locale(
            "`[{0}]` \U0001f528 **{1}** banned *{2}* ({3})\n[{4} → {5} Strikes] ` Reason ` {6}").format(
            case, str(mod), str(target), target.id, prev or 0, after, reason or bot.system.locale("None given"))

class Moderation(commands.Cog):
    HELP_REQUIRES = ["mod"]

    def __init__(self, bot):
        self.bot = bot
        self.locale_name = bot.system.locale("Moderation")
        self.system = bot.system
        self.db = self.system.db
        self.value = StrikesValues(self.system.config)
        self.levels = {
            1: self.system.locale("temp mute"),
            2: self.system.locale("kick"),
            3: self.system.locale("soft ban"),
            4: self.system.locale("temp ban"),
            5: self.system.locale("ban")
        }

    async def add_strike(self, mod, target, strikes, reason):
        user = await self.system.get_user_discord_id(target.id)
        modu = await self.system.get_user_discord_id(mod.id)

        prev = await self.db.fetchval("SELECT amount FROM strikes WHERE user_id = ?", user.id) or 0
        await self.db.execute("INSERT INTO strikes VALUES (?,?) ON CONFLICT (user_id) DO UPDATE SET amount = amount + ? WHERE user_id = ?", user.id, strikes, strikes, user.id)
        await self.db.execute("INSERT INTO mod_cases VALUES (?,?,?)", user.id, modu.id, reason)

        rid = await self.db.fetchval("SELECT last_insert_rowid()")
        new_strikes = prev + strikes if prev is not None else strikes
        pun=None
        if strikes > 0:
            pun = self.value.punishment(new_strikes)
        else:
            pun = self.value.pardon
        if pun is None:
            pun = self.value.punish_none


        resp = await pun(self.bot, mod, target, prev, new_strikes, rid, reason)
        channel = self.bot.get_channel(self.system.config.getint("moderation", "mod_channel", fallback=0))
        try:
            await channel.send(resp)
        except:
            pass

    @command()
    @commands.bot_has_permissions(ban_members=True, kick_members=True, manage_roles=True)
    async def strike(self, ctx, amount: Optional[int]=1, targets: commands.Greedy[discord.Member]=None, *, reason=None):
        if not targets:
            return await ctx.send(self.system.locale("No targets given to strike"))
        for target in targets:
            await self.add_strike(ctx.author, target, amount, reason)

        await ctx.send(self.system.locale("Added {0} strikes to {1}").format(amount, ", ".join([str(x) for x in targets])))

    @command()
    async def pardon(self, ctx, amount: Optional[int]=1, targets: commands.Greedy[discord.Member]=None, *, reason=None):
        if not targets:
            return await ctx.send(self.system.locale("No targets given to strike"))
        for target in targets:
            await self.add_strike(ctx.author, target, amount*-1, reason)

        await ctx.send(self.system.locale("Removed {0} strikes from {1}").format(amount, ", ".join([str(x) for x in targets])))

    @group("strike-config", invoke_without_command=True)
    async def strikecfg(self, ctx):
        pass

    @strikecfg.command()
    async def action(self, ctx, strikes: int, *, action: ActionConverter):
        arg = None
        if action in (1, 4):
            resp = await ctx.ask(self.system.locale("Please respond with the duration this should last for"))
            arg = await timeutil.UserFriendlyTime(default="e", now=True).convert(ctx, resp)
            self.value._value['temp_lengths'][str(strikes)] = (arg.dt - datetime.datetime.utcnow()).total_seconds()

        self.value._value['levels'][str(strikes)] = action
        self.value.save()
        r = self.system.locale("`{0}` strikes will now be punished with a {1}").format(strikes, self.levels[action])
        if arg is not None:
            t = timeutil.human_timedelta(self.system.locale, arg.dt, )
            r += self.system.locale(", lasting ") + t

        await ctx.send(r)

    @strikecfg.command()
    async def remove(self, ctx, strikes: int):
        if str(strikes) not in self.value._value['levels']:
            return await ctx.send(self.system.locale("Strike level {0} does not have a punishment").format(strikes))

        del self.value._value['levels'][str(strikes)]
        if str(strikes) in self.value._value['temp_lengths']:
            del self.value._value['temp_lengths'][str(strikes)]

        self.value.save()
        await ctx.send(self.system.locale("Removed punishment for strike level {0}").format(strikes))

    @command()
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, targets: commands.Greedy[Union[discord.Member, int]], *, reason=None):
        reason = reason or self.system.locale("None given")
        channel = self.bot.get_channel(self.system.config.getint("moderation", "mod_channel", fallback=0))
        for target in targets:
            if isinstance(target, int):
                trg = discord.Object(id=target)
            else:
                trg = target

            await ctx.guild.ban(trg, reason=reason)
            user = await self.system.get_user_discord_id(target.id)
            modu = await self.system.get_user_discord_id(ctx.author.id)
            await self.db.execute("INSERT INTO mod_cases VALUES (?,?,?)", user.id, modu.id, reason)
            if channel is None:
                continue

            rid = await self.db.fetchval("SELECT last_insert_rowid()")

            if isinstance(target, int):
                e = self.system.locale(
                    "`[{0}]` \U0001f528 **{1}** banned user with id `{2}`\n` Reason ` {3}").format(
                    rid, str(ctx.author), id, reason)
            else:
                e =  self.system.locale(
                "`[{0}]` \U0001f528 **{1}** banned *{2}* ({3})\n` Reason ` {4}").format(
                rid, str(ctx.author), str(target), target.id, reason)

            try:
                await channel.send(e)
            except:
                pass

    @command()
    @commands.bot_has_permissions(ban_members=True)
    async def softban(self, ctx, targets: commands.Greedy[Union[discord.Member, int]], *, reason):
        reason = reason or self.system.locale("None given")
        channel = self.bot.get_channel(self.system.config.getint("moderation", "mod_channel", fallback=0))
        for target in targets:
            if target.highest_role.position >= ctx.guild.me.highest_role.position:
                await ctx.send(self.system.locale("Couldn't ban {0} due to role hierarchy").format(str(target)))
                continue

            await target.ban()
            await target.unban()

            user = await self.system.get_user_discord_id(target.id)
            modu = await self.system.get_user_discord_id(ctx.author.id)
            await self.db.execute("INSERT INTO mod_cases VALUES (?,?,?)", user.id, modu.id, reason)
            if channel is None:
                continue

            rid = await self.db.fetchval("SELECT last_insert_rowid()")

            e = self.system.locale(
                "`[{0}]` \U0001fa93 **{1}** soft banned *{2}* ({3})\n` Reason ` {4}").format(
                rid, str(ctx.author), str(target), target.id, reason)

            try:
                await channel.send(e)
            except:
                pass

    @command()
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, targets: commands.Greedy[Union[discord.Member, int]], *, reason):
        reason = reason or self.system.locale("None given")
        channel = self.bot.get_channel(self.system.config.getint("moderation", "mod_channel", fallback=0))
        for target in targets:
            if target.highest_role.position >= ctx.guild.me.highest_role.position:
                await ctx.send(self.system.locale("Couldn't ban {0} due to role hierarchy").format(str(target)))
                continue

            await target.kick()

            user = await self.system.get_user_discord_id(target.id)
            modu = await self.system.get_user_discord_id(ctx.author.id)
            await self.db.execute("INSERT INTO mod_cases VALUES (?,?,?)", user.id, modu.id, reason)
            if channel is None:
                continue

            rid = await self.db.fetchval("SELECT last_insert_rowid()")

            e = self.system.locale(
                "`[{0}]` \U0001fa93 **{1}** soft banned *{2}* ({3})\n` Reason ` {4}").format(
                rid, str(ctx.author), str(target), target.id, reason)

            try:
                await channel.send(e)
            except:
                pass
