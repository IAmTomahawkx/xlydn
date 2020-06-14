import json
import typing

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
        if self._limits is not None:
            self._limits = json.loads(self._limits)

        self.cooldown = None
        if self._raw_cd is not None:
            self.cooldown = CooldownMapping.from_cooldown(1, self._raw_cd, BucketType.default)

    @classmethod
    def new(cls, name, message, use_discord=True, use_twitch=True, cooldown=60.0, limits=None):
        self = cls.__new__(cls)
        self.name = name
        self._places = 0 if use_discord and use_twitch else (1 if use_twitch and not use_discord else 2)
        self.message = message
        self._raw_cd = cooldown
        self.cooldown = CooldownMapping.from_cooldown(1, self._raw_cd, BucketType.default)
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
        return self.name, self._places, self.message, self._raw_cd, json.dumps(self._limits) if self._limits is not None else None

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
        self._sys = system
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
            print(row)


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