"""
Licensed under the Open Software License version 3.0
"""
import discord
import twitchio
from twitchio.ext import commands as tio_commands
from discord.ext import commands
import asyncio
import import_expression
import importlib
import inspect
import traceback
import textwrap

from utils.paginators import Timer
from utils.commands import command, group


def setup(bot):
    bot.add_cog(PyDev(bot))

class PyDev(commands.Cog):
    HELP_REQUIRES = ["hide"]
    def __init__(self, bot):
        self.bot = bot # type: commands.Bot
        self.core = bot.system
        self._env = {}
        self._evals = []
        self._timeout = 60
        self._send_in_codeblocks = True
        self.locale_name = bot.system.locale("PyDev")

    @group(invoke_without_command=True)
    @commands.is_owner()
    async def dev(self, ctx):
        jsk = self.bot.get_command("jishaku")
        await ctx.invoke(jsk)

    @dev.command(aliases=["r"])
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, *modules):
        if isinstance(modules, str):
            modules = [modules]

        modules = ["addons.discord."+m for m in modules]
        ret = []
        for module in modules:
            if module not in self.bot.extensions:
                try:
                    self.bot.load_extension(module)
                    ret.append(f"\N{INBOX TRAY} `{module}`")
                except:
                    ret.append(f"\N{WARNING SIGN} `{module}`")
                    traceback.print_exc()

            else:
                try:
                    self.bot.reload_extension(module)
                    ret.append(f"\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} `{module}`")
                except:
                    ret.append(f"\N{WARNING SIGN} `{module}`")

        await ctx.send("\n".join(ret))

    @dev.command()
    @commands.is_owner()
    async def invite(self, ctx, perms: int=0):
        """
        creates an invite link for the bot
        """
        ret = discord.utils.oauth_url((await self.bot.application_info()).id, permissions=discord.Permissions(perms))
        await ctx.send(ret)

    @dev.command()
    @commands.is_owner()
    async def eval(self, ctx, *, code_string):
        """
        evaluates some code. Do not run this unless you know what you are doing!
        """
        """
        The code used in this command is licensed under AGPLv3 clause.
        Modification or distribution without permission is not granted unless it works with the License.

        XuaTheGrate - the owner of this code - has granted explicit permission for me to use this code within amalna.

        The original source code can be located here: https://github.com/iDevision/MostDefinitelyGrant2/blob/master/cogs/dev.py
        A copy of the AGPLv3 License can be located here: https://github.com/iDevision/MostDefinitelyGrant2/blob/master/LICENSE.md
        """
        if not self._env:
            self._env.update({
                "discord": discord,
                "twitchio": twitchio,
                "bot": self.bot,
                "twitch_streamer": self.core.twitch_streamer,
                "twitch_bot": self.core.twitch_bot,
                "db": self.core.db,
                "commands": commands,
                '_': None,
                import_expression.constants.IMPORTER: importlib.import_module})

        self._env['ctx'] = ctx

        try:
            expr = import_expression.compile(code_string)
            ret = eval(expr, self._env)
        except SyntaxError:
            pass

        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            return await ctx.paginate("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), codeblocks=True)

        else:
            if inspect.isawaitable(ret):
                fut = asyncio.ensure_future(ret, loop=self.bot.loop)
                self._evals.append(fut)
                try:
                    with Timer(ctx.message):
                        ret = await asyncio.wait_for(fut, timeout=self._timeout)

                except Exception as exc:
                    await ctx.message.add_reaction(self.bot.tick_no)
                    return await ctx.paginate("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), codeblocks=True)

                finally:
                    self._evals.remove(fut)

            await ctx.message.add_reaction(self.bot.tick_yes)
            if ret is None:
                return

            self._env['_'] = ret
            if isinstance(ret, discord.Embed):
                return await ctx.send(embed=ret)

            if not isinstance(ret, str):
                ret = repr(ret)

            return await ctx.paginate(ret, codeblock=self._send_in_codeblocks)

        code = f"""async def __func__():
    try:
{textwrap.indent(code_string, '        ')}
    finally:
        globals().update(locals())"""
        try:
            import_expression.exec(code, self._env)
        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            return await ctx.paginate("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                                      codeblocks=True)

        func = self._env.pop('__func__')
        fut = asyncio.ensure_future(func(), loop=self.bot.loop)
        self._evals.append(fut)
        try:
            with Timer(ctx.message):
                await asyncio.wait_for(fut, timeout=self._timeout)

        except asyncio.CancelledError:
            await ctx.message.add_reaction('\U0001f6d1')
            return

        except asyncio.TimeoutError:
            await ctx.message.add_reaction('\u23f0')
            return

        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            return await ctx.paginate("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                                      codeblocks=True)

        else:
            ret = fut.result()
        finally:
            self._evals.remove(fut)

        await ctx.message.add_reaction(self.bot.tick_yes)

        if ret is None:
            return

        self._env['_'] = ret

        if isinstance(ret, discord.Embed):
            return await ctx.send(embed=ret)

        if not isinstance(ret, str):
            ret = repr(ret)

        return await ctx.paginate(ret, codeblocks=self._send_in_codeblocks)
