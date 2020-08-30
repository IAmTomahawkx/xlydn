import asyncio
import traceback

from discord.ext.commands.view import StringView
import pyk

from . import paginators

async def parse(bot, msg, view: StringView, command: str, discord: bool):
    args = []
    v = view.get_quoted_word()
    while v:
        args.append(v.strip())
        v = view.get_quoted_word()

    if discord:
        try:
            await parse_discord_specifics(bot, msg, command, args)
        except Exception as e:
            ctx = await bot.get_context(msg)
            await ctx.paginate("".join(traceback.format_exception(type(e), e, e.__traceback__)))
    return None


async def parse_discord_specifics(bot, msg, command, args):
    async def send(content):
        if content == pyk.PYK_NONE:
            return

        if not content:
            return

        await msg.channel.send(content)

    vals = {
        "username": (msg.author.name, True),
        "userid": (str(msg.author.id), True),
        "user": (str(msg.author), True),
        "send": (send, True)
    }

    for i in range(1, 10):
        try:
            vals[f"arg{i}"] = args[i-1], True
        except IndexError:
            vals[f"arg{i}"] = pyk.PYK_NONE, True


    n = pyk.PYKNamespace()
    n.update(vals)
    try:
        await pyk.eval(command, namespace=n, safe=True)
    except pyk.PYK_Error as e:
        await msg.channel.send("\n".join(e.format_stack()))

    except Exception as e:
        print(e)
        await msg.channel.send("Your script caused a python error...")


def parse_twitch_specifics(ctx, view, args):
    pass
