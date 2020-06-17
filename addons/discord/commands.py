from typing import Optional
import json

import discord
from discord.ext import commands
from discord.ext.commands.view import StringView

from utils import parser, common, checks
from utils.converters import NoDiscordChecker, NoTwitchChecker

def setup(bot):
    bot.add_cog(CustomCommands(bot))

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system

    async def process_commands(self, msg, command, view):
        await parser.parse(self.bot, msg, view, command.message, True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.guild.id != self.system.config.getint("general", "server_id", fallback=None):
            return

        prefixes = await self.bot.get_prefix(message)
        view = StringView(message.content)
        if isinstance(prefixes, list):
            for prefix in prefixes:
                if view.skip_string(prefix):
                    cmd = view.get_word()
                    command = await self.system.get_command(cmd)
                    if command is not None:
                        user = await self.system.get_user_discord_id(message.author.id)
                        if command.can_run_discord(message, user):
                            return await self.process_commands(message, command, view)

        else:
            if view.skip_string(prefixes):
                cmd = view.get_word()
                command = await self.system.get_command(cmd)
                if command is not None:
                    user = await self.system.get_user_discord_id(message.author.id)
                    if command.can_run_discord(message, user):
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
    @checks.dpy_check_editor()
    async def add(self, ctx, name,
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
    @checks.dpy_check_editor()
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
    @checks.dpy_check_editor()
    async def edit(self, ctx, name, *, content):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        command.message = content
        await self.system.db.execute("UPDATE commands SET message = ? WHERE name = ?", content, name)
        await ctx.send(self.system.locale("Command updated successfully"))

    @command.command()
    @checks.dpy_check_editor()
    async def raw(self, ctx, name):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        await ctx.send(command.message)

    @command.group(invoke_without_command=True, aliases=['perms'])
    @checks.dpy_check_editor()
    async def permissions(self, ctx, name):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        resp = ""
        if perms['common']['ids']:
            resp += self.system.locale("__**Users**__:\n")
            for user in perms['common']['ids']:
                user = await self.system.get_user(user)
                duser = self.bot.get_user(user.discord_id)
                if user:
                    resp += str(duser)
                    if user.twitch_name is not None:
                        resp += " Twitch: " + user.twitch_name

                    resp += "\n"

            resp += "\n"

        if perms['discord']['roles']:
            resp += self.system.locale("__**Discord Permissions**__:\n")
            resp += self.system.locale("*Roles*:\n")
            for role in perms['discord']['roles']:
                role = ctx.guild.get_role(role)
                if role:
                    resp += str(role) + "\n"
            resp += "\n"

        if perms['discord']['channels']:
            if not perms['discord']['roles']:
                resp += self.system.locale("__**Discord Permissions**__:\n")

            resp += self.system.locale("*Channels*:\n")
            for channel in perms['discord']['channels']:
                channel = ctx.guild.get_channel(channel)
                if channel:
                    resp += channel.mention + "\n"
            resp += "\n"

        if perms['twitch']['roles']:
            resp += self.system.locale("__**Twitch Permissions**__:\n")
            resp += self.system.locale("*Roles*:\n")
            for role in perms['twitch']['roles']:
                resp += self.system.locale(role) + "\n"

        if not resp:
            return await ctx.send(self.system.locale("Anyone can use this command"))

        await ctx.paginate(resp)

    @permissions.command(aliases=['+user'])
    @checks.dpy_check_editor()
    async def adduser(self, ctx, name, user: discord.Member):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        usr = await self.system.get_user_discord_id(user.id)
        if usr.id in perms['common']['ids']:
            return await ctx.send(self.system.locale("This user has already been added to the whitelist"))

        perms['common']['ids'].append(usr.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Added {0} to the command whitelist").format(str(user)))

    @permissions.command(aliases=['-user'])
    @checks.dpy_check_editor()
    async def userremove(self, ctx, name, user: discord.Member):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        usr = await self.system.get_user_discord_id(user.id)
        if usr.id not in perms['common']['ids']:
            return await ctx.send(self.system.locale("This user has not been added to the whitelist"))

        perms['common']['ids'].remove(usr.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Removed {0} from the command list").format(str(user)))

    @permissions.command(aliases=["+role"])
    @checks.dpy_check_editor()
    async def addrole(self, ctx, name, role: discord.Role):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        if role.id in perms['discord']['roles']:
            return await ctx.send(self.system.locale("This role has already been added to the whitelist"))

        perms['discord']['roles'].append(role.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Added {0} to the command whitelist").format(role.name))

    @permissions.command(aliases=['-role'])
    @checks.dpy_check_editor()
    async def removerole(self, ctx, name, role: discord.Role):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        if role.id not in perms['discord']['roles']:
            return await ctx.send(self.system.locale("This role has not been added to the whitelist"))

        perms['discord']['roles'].remove(role.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Removed {0} from the command list").format(role.name))

    @permissions.command(aliases=['+channel'])
    @checks.dpy_check_editor()
    async def addchannel(self, ctx, name, channel: discord.TextChannel):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        if channel.id in perms['discord']['channels']:
            return await ctx.send(self.system.locale("This role has already been added to the whitelist"))

        perms['discord']['channels'].append(channel.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Added {0} to the command whitelist").format(channel.mention))

    @permissions.command(aliases=['-channel'])
    @checks.dpy_check_editor()
    async def removechannel(self, ctx, name, channel: discord.TextChannel):
        command = await self.system.get_command(name)
        if command is None:
            return await ctx.send(self.system.locale("Command `{0}` not found").format(name))

        perms = command._limits
        if channel.id not in perms['discord']['channels']:
            return await ctx.send(self.system.locale("This channel has not been added to the whitelist"))

        perms['discord']['channels'].remove(channel.id)
        await self.system.db.execute("UPDATE commands SET limits = ? WHERE name = ?", json.dumps(perms), name)
        await ctx.send(self.system.locale("Removed {0} from the command list").format(channel.mention))
