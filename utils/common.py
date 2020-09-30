import json
import typing
import time
import asyncio

import discord
import discord.utils
import discord.abc
from discord.enums import Enum
from discord.ext.commands import CooldownMapping as _base_cd_map, Cooldown as _base_cooldown
import twitchio

customcommands_limits = {
    "common": {
        "ids": typing.List[int],
        "editor": bool
    },
    "discord": {
        "channels": typing.List[int],
        "roles": typing.List[int]
    },
    "twitch": {
        "roles": typing.List[str] # mod, founder, sub etc
    }
}

ROLES = [
    "Editor",
    "Moderator",
    "Founder",
    "Subscriber",
    "VIP",
    "Broadcaster"
]

class CustomCommand:
    def __init__(self, row):
        self.name = row[0]
        self._places = row[1]
        self.message = row[2]
        self._raw_cd = row[3]
        self._limits = row[4]
        self.isscript = row[5]
        if self._limits is not None:
            self._limits = json.loads(self._limits)

        self.cooldown = None
        if self._raw_cd is not None:
            self.cooldown = CooldownMapping.from_cooldown(1, self._raw_cd, BucketType.default)

    @classmethod
    def new(cls, name, message, use_discord=True, use_twitch=True, cooldown=60.0, limits=None, isscript=False):
        self = cls.__new__(cls)
        self.name = name
        self._places = 0 if use_discord and use_twitch else (1 if use_twitch and not use_discord else 2)
        self.message = message
        self._raw_cd = cooldown
        self.cooldown = CooldownMapping.from_cooldown(1, self._raw_cd, BucketType.default)
        self.isscript = isscript
        self._limits = {
            "common": {
                "ids": [],
                "editor": False
            },
            "discord": {
                "roles": [],
                "channels": []
            },
            "twitch": {
                "roles": []
            }
        } if limits is None else limits
        return self

    @property
    def save(self):
        return self.name, self._places, self.message, self._raw_cd, json.dumps(self._limits) if self._limits is not None else None, self.isscript

    def can_run_discord(self, msg: discord.Message, usr:"User"):
        if self._places not in (0, 2):
            return False


        if self._limits is not None:
            if self._limits['common']['editor'] and not usr.editor:
                return False
            if self._limits['common']['ids']:
                if usr.id not in self._limits['common']['ids']:
                    return False

        if self._limits is not None and "discord" in self._limits:
            if "channels" in self._limits['discord'] and self._limits['discord']['channels']:
                if msg.channel.id not in self._limits['discord']['channels']:
                    return False

            if msg.author.guild_permissions.administrator:
                return True

            if "roles" in self._limits['discord'] and self._limits['discord']['roles']:
                if not discord.utils.find(lambda role: role.id in self._limits['discord']['roles'], msg.author.roles):
                    return False

        return True

    def can_run_twitch(self, msg: twitchio.Message, usr:"User"):
        if self._places not in (0, 1):
            return False

        if self._limits is not None:
            if self._limits['common']['editor'] and not usr.editor:
                return False
            if self._limits['common']['ids']:
                if usr.id not in self._limits['common']['ids']:
                    return False

        if self._limits is not None and "twitch" in self._limits:
            if "roles" in self._limits['twitch'] and self._limits['twitch']['roles']:
                if msg.author.badges.get('broadcaster', 0):
                    return True

                roles = self._limits['twitch']['roles']

                r = {
                    "Editor": usr.editor,
                    "Moderator": bool(msg.author.badges.get("moderator", 0)),
                    "Founder": bool(msg.author.badges.get("founder", 0)),
                    "Subscriber": bool(msg.author.badges.get("subscriber", 0)),
                    "VIP": bool(msg.author.badges.get("vip", 0))
                }

                if "Broadcaster" in roles:
                    return False

                for a, b in r.items():
                    if a in roles:
                        return b

        return True

    @property
    def discord(self):
        return self._places in (0, 2)

    @property
    def twitch(self):
        return self._places in (0, 1)


class User:
    def __init__(self, row, system):
        self._system = system
        self.twitch_id = row[0]
        self.twitch_name = row[1]
        self.discord_id = row[2]
        self.id = row[3]
        self.points = row[4]
        self.hours = row[5]
        self.editor = bool(row[6])
        try:
            self.badges = json.loads(row[7]) if row[7] else []
        except:
            self.badges = []

    @property
    def discord_user(self):
        serv = self._system.discord_bot.get_guild(self._system.config.getinteger("general", "server_id", fallback=0))
        if serv:
            return serv.get_member(self.discord_id)

    @property
    def twitch_user(self):
        chan = self._system.twitch_streamer.get_channel(self._system.twitch_streamer.nick)
        if chan:
            return discord.utils.get(chan.chatters, name=self.twitch_name)

class LineBucket:
    def __init__(self, trigger, shared=False):
        self.shared = shared
        self._trigger = trigger
        if shared:
            self.value = 0
        else:
            self.value = [0, 0]

    def inc(self, where: int, val=1):
        if self.shared:
            self.value += val
            if self.value >= self._trigger:
                return True

            return False

        else:
            self.value[where] += 1
            if self.value[where] > self._trigger:
                return True

    def triggered(self, where: int):
        if self.shared:
            return self.value >= self._trigger

        return self.value[where] >= self._trigger

    def reset(self):
        self.value = 0

class TimerLoop:
    """
    Binds multiple timers together to form one chain
    """
    def __init__(self, system, name, delay, minlines, place, channel):
        self.name = name
        self.system = system
        self.timers = []
        self.fire_index = [0, 0]
        self.delay = delay
        self.minlines = minlines
        self.channel = channel
        self.place = place
        self._bucket = LineBucket(self.minlines)
        self._task = None

    def start_task(self):
        self._task = asyncio.get_running_loop().create_task(self.send_loop())

    def end_task(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def __del__(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def add_timer(self, timer: "ChainTimer"):
        self.timers.append(timer)

    def remove_timer(self, timer: "ChainTimer"):
        ind = self.timers.index(timer)
        if self.fire_index[0] >= ind:
            self.fire_index[0] -= 1

        if self.fire_index[1] >= ind:
            self.fire_index[1] -= 1

        self.timers.remove(timer)

    async def send_loop(self):
        last_discord_send = time.time()
        last_twitch_send = time.time()
        while True:
            cur = time.time()

            if self.place in [1, 2] and self.channel is not None \
                    and cur - last_discord_send > self.delay \
                    and self._bucket.triggered(1):
                if len(self.timers) <= self.fire_index[1]:
                    self.fire_index[1] = 0

                chn = self.system.discord_bot.get_channel(self.channel)
                try:
                    await chn.send(self.timers[self.fire_index[1]].content)
                except:
                    pass

            if self.place in [0, 2] and cur - last_twitch_send > self.delay and self._bucket.triggered(0):
                chn = self.system.twitch_streamer._ws._nick
                chn = self.system.twitch_bot.get_channel(chn)
                if len(self.timers) <= self.fire_index[0]:
                    self.fire_index[1] = 0

                try:
                    await chn.send(self.timers[self.fire_index[0]].content)
                except:
                    pass

            await asyncio.sleep(0)


    async def on_twitch_message(self, message):
        if self.place is 1:
            return

        self._bucket.inc(0)

    async def on_discord_message(self, message):
        if self.place is 0:
            return

        self._bucket.inc(1)

class ChainTimer:
    def __init__(self, row, loop):
        self.loop = loop
        self.content = row[5]
        self.name = row[0]


class SoloTimer:
    def __init__(self, row, system):
        self.system = system
        self.name = row[0]
        self.delay = row[1]
        self.minlines = row[2]
        self.place = row[3]
        self.shared = bool(row[4])
        self.content = row[5]
        self.channel = row[6]
        self._bucket = LineBucket(self.minlines)
        self._task = None

    async def _send_loop(self):
        last_discord_send = time.time()
        last_twitch_send = time.time()
        while True:
            cur = time.time()
            if self.place in [1, 2] and self.channel is not None and cur - last_discord_send > self.delay and self._bucket.triggered(1):
                chn = self.system.discord_bot.get_channel(self.channel)
                try:
                    await chn.send(self.content)
                except:
                    pass

            if self.place in [0, 2] and cur - last_twitch_send > self.delay and self._bucket.triggered(0):
                chn = self.system.twitch_streamer._ws._nick
                chn = self.system.twitch_bot.get_channel(chn)
                try:
                    await chn.send(self.content)
                except:
                    pass

            await asyncio.sleep(1)


    def start_loop(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()

        self._task = asyncio.get_running_loop().create_task(self._send_loop())

    def stop_loop(self):
        if self._task is not None:
            self._task.cancel()

    def __del__(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def on_twitch_message(self, message):
        if self.place is 1:
            return

        self._bucket.inc(0)

    async def on_discord_message(self, message):
        if self.place is 0:
            return

        self._bucket.inc(1)


class BucketType(Enum):
    default  = 0
    user     = 1
    twitch   = 2
    discord  = 3

    def get_key(self, msg, usr):
        if self is BucketType.user:
            return usr.id
        elif self is BucketType.twitch:
            return "twitch"
        elif self is BucketType.discord:
            return "discord"


class Cooldown(_base_cooldown):
    def __init__(self, rate, per, type):
        self.rate = int(rate)
        self.per = float(per)
        self.type = type
        self._window = 0.0
        self._tokens = self.rate
        self._last = 0.0
        if not isinstance(self.type, BucketType):
            raise TypeError('Cooldown type must be a BucketType')

    def copy(self):
        return Cooldown(self.rate, self.per, self.type)

class CooldownMapping(_base_cd_map):
    def copy(self):
        ret = CooldownMapping(self._cooldown)
        ret._cache = self._cache.copy()
        return ret

    @classmethod
    def from_cooldown(cls, rate, per, type):
        return cls(Cooldown(rate, per, type))

    def _bucket_key(self, msg, usr):
        return self._cooldown.type.get_key(msg, usr)

    def get_bucket(self, message, usr, current=None):
        if self._cooldown.type is BucketType.default:
            return self._cooldown

        self._verify_cache_integrity(current)
        key = self._bucket_key(message, usr)
        if key not in self._cache:
            bucket = self._cooldown.copy()
            self._cache[key] = bucket
        else:
            bucket = self._cache[key]

        return bucket

    def update_rate_limit(self, message, usr, current=None):
        bucket = self.get_bucket(message, usr, current=current)
        return bucket.update_rate_limit(current)