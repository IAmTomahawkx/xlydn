"""
Licensed under the Open Software License version 3.0
"""
from typing import Optional
import json

import twitchio
from discord.ext import commands
from discord.ext.commands.view import StringView

from utils import parser, common, checks, contexts
from utils.converters import NoDiscordChecker, NoTwitchChecker


def setup(bot):
    bot.add_cog(CustomCommands(bot))

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system

    async def process_commands(self, msg, command, view):
        await parser.parse(self.bot, msg, view, command.message, False)

    @commands.Cog.listener()
    async def event_message(self, message: twitchio.Message):
        if not message.channel:
            return

        if message.channel.name != self.bot._ws.nick:
            return

        prefixes = await self.bot._get_prefixes(message)
        view = StringView(message.content)
        if isinstance(prefixes, list):
            for prefix in prefixes:
                if view.skip_string(prefix):
                    cmd = view.get_word()
                    command = await self.system.get_command(cmd)
                    if command is not None:
                        user = await self.system.get_user_twitch_name(message.author.name, id=message.author.id)
                        if command.can_run_twitch(message, user):
                            return await self.process_commands(message, command, view)

        else:
            if view.skip_string(prefixes):
                cmd = view.get_word()
                command = await self.system.get_command(cmd)
                if command is not None:
                    user = await self.system.get_user_twitch_name(message.author.name, id=message.author.id)
                    if command.can_run_twitch(message, user):
                        return await self.process_commands(message, command, view)

    @commands.group(invoke_without_command=True, aliases=['commands'])
    @checks.dpy_check_editor()
    async def command(self, ctx):
        cmd_names = await self.system.db.fetch("SELECT name FROM commands")
        if not cmd_names:
            return await ctx.send(self.system.locale("No custom commands"))

        resp = "\n".join([f"- {x[0]}" for x in cmd_names])
        await ctx.paginate(resp, codeblocks=True)

    @command.command()
    @checks.tio_check_editor()
    async def add(self, ctx: contexts.TwitchContext, name,
                  nodiscord: Optional[NoDiscordChecker],
                  notwitch: Optional[NoTwitchChecker],
                  *, content):
        command = common.CustomCommand.new(name, content, use_discord=not nodiscord, use_twitch=not notwitch)
        try:
            await self.system.add_command(*command.save)
        except ValueError as e:
            return await ctx.send(e.args[0])
        await ctx.send(self.system.locale("Added command `{0}`").format(name))

    @command.command()
    @checks.tio_check_editor()
    async def remove(self, ctx, name):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        try:
            await self.system.remove_command(name)
        except ValueError as e:
            return await ctx.send(e.args[0])

        await ctx.send(self.system.locale("Command `{0}` deleted").format(name))

    @command.command()
    @checks.tio_check_editor()
    async def edit(self, ctx, name, *, content):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        command.message = content
        await self.system.db.execute("UPDATE commands SET message = ? WHERE name = ?", content, name)
        await ctx.send(self.system.locale("Command updated successfully"))

    @command.command()
    @checks.tio_check_editor()
    async def raw(self, ctx, name):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        await ctx.send(command.message)

    @command.group(invoke_without_command=True, aliases=['perms'])
    @checks.tio_check_editor()
    async def permissions(self, ctx, name):
        pass

    @permissions.command(aliases=['+user'])
    @checks.tio_check_editor()
    async def adduser(self, ctx: contexts.TwitchContext, name, username: str):
        user = username.strip("@")
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        usr = await self.system.get_user_twitch_name(user)
        if usr.id in perms['common']['ids']:
            return await ctx.send(self.system.locale("This user has already been added to the whitelist"))

        perms['common']['ids'].append(usr.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Added {0} to the command whitelist").format(username))

    @permissions.command(aliases=['-user'])
    @checks.tio_check_editor()
    async def userremove(self, ctx, name, username: str):
        user = username.strip("@")
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        usr = await self.system.get_user_twitch_name(user)
        if usr.id not in perms['common']['ids']:
            return await ctx.send(self.system.locale("This user has not been added to the whitelist"))

        perms['common']['ids'].remove(usr.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Removed {0} from the command list").format(str(user)))

    @permissions.command(aliases=["+role"])
    @checks.tio_check_editor()
    async def addrole(self, ctx, name, role: str):
        if role not in common.ROLES:
            return await ctx.send(self.system.locale("{0} is not a valid role").format(role))

        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        if role in perms['twitch']['roles']:
            return await ctx.send(self.system.locale("This role has already been added to the whitelist"))

        perms['twitch']['roles'].append(role)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Added {0} to the command whitelist").format(role))

    @permissions.command(aliases=['-role'])
    @checks.tio_check_editor()
    async def removerole(self, ctx, name, role: str):
        if role not in common.ROLES:
            return await ctx.send(self.system.locale("{0} is not a valid role").format(role))

        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        if role not in perms['twitch']['roles']:
            return await ctx.send(self.system.locale("This role has not been added to the whitelist"))

        perms['twitch']['roles'].remove(role)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Removed {0} from the command list").format(role))
