from typing import Optional

import discord
from discord.ext import commands
from utils.commands import group, command
from utils.checks import dpy_check_editor
from utils import common
from utils.converters import NoDiscordChecker, NoTwitchChecker


def setup(bot):
    pass

class Timers(commands.Cog):
    HELP_REQUIRES = ["editor"]
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system
        self.chains: dict = self.system.timer_loop_cache
        self.looped: dict = self.system.chain_timer_cache
        self.solos: dict = self.system.solo_timer_cache
        self.locale_name = self.system.locale("Timers")
        self.system.loop.create_task(self.create_timers())
        self.flag = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.flag:
            return

        self.flag = True

        for chain in self.chains:
            chain.start_task()

        for timer in self.solos:
            timer.start_task()

    async def create_timers(self):
        chains = await self.system.db.fetch("SELECT * FROM chat_timer_loops")
        if chains:
            for chain in chains:
                obj = common.TimerLoop(self.system, *chain)
                self.chains[obj.name] = obj

        timers = self.system.db.fetch("SELECT * FROM chat_timers")
        if timers:
            for timer in timers:
                if timer[7] is not None: # its on a loop circuit
                    loop = self.chains.get(timer[7])
                    if not loop:
                        continue

                    obj = common.ChainTimer(timer, loop)
                    self.looped[obj.name] = obj

                else:
                    obj = common.SoloTimer(timer, self.system)
                    self.solos[obj.name] = obj


    @group(invoke_without_command=True, aliases=['timers'])
    @dpy_check_editor()
    async def timer(self, ctx):
        pass

    @timer.group()
    @dpy_check_editor()
    async def loops(self, ctx):
        pass

    @loops.command("edit")
    async def loop_edit(self, ctx, loop, delay: int, minlines: Optional[int]):
        pass

    @loops.command("add")
    async def loop_add(self, ctx, name, delay: int, minlines: Optional[int],
                       noTwitch: Optional[NoTwitchChecker], noDiscord: Optional[NoDiscordChecker],
                       discordChannel: Optional[discord.TextChannel]):
        if not noTwitch and not noDiscord:
            raise commands.CommandError(self.system.locale("You must use at least one platform to send timers to"))

        if noDiscord:
            place = 0

        elif noTwitch:
            place = 1

        else:
            place = 2

        if not noDiscord and not discordChannel:
            raise commands.CommandError(self.system.locale("You must specify a channel in discord for the loop to send to"))

        await self.system.db.execute("INSERT INTO chat_timer_loops VALUES (?,?,?,?,?)", name, delay, minlines, place, discordChannel.id)

    @timer.command()
    @dpy_check_editor()
    async def solos(self, ctx):
        pass