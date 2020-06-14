from .argparse import Adapter
from discord.ext.commands.view import StringView
import random

def parse(bot, msg, view: StringView, command: str, discord: bool):
    adapter = Adapter()

    vals = {
        "$username": msg.author.name,
        "$userid": str(msg.author.id),
        "$user": str(msg.author),
    }


    for a,b in vals.items():
        command = command.replace(a,b)

    args = adapter.parse(command, maxdepth=1)
    output = ""

    for arg in args:
        if isinstance(arg, str):
            output += arg

    return output


def parse_discord_specifics(ctx, view, args):
    pass

def parse_twitch_specifics(ctx, view, args):
    pass

def parse_math(arg: dict):
    equation = arg['params'][0]
    # noinspection PyBroadException
    try:
        resp = eval(equation, {}, {})
    except:
        resp = f"{{Invalid equation \"{equation}\"}}"

    return resp

def parse_random(arg: dict):
    choices = arg['params']
    if not choices:
        return ""

    return random.choice(choices)