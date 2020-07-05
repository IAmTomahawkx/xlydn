import discord
from discord.ext import commands

from utils.commands import GroupWithLocale, CommandWithLocale

def setup(bot):
    bot.help_command = Help()

class Help(commands.HelpCommand):
    verify_checks = True
    def command_not_found(self, string):
        return self.context.bot.system.locale("The command {0} does not exist").format(string)

    def subcommand_not_found(self, command: commands.Command, string):
        locale = self.context.bot.system.locale

        if isinstance(command, commands.Group) and len(command.all_commands) > 0:
            return locale('Command "{0}" has no subcommand named {1}').format(command.qualified_name, string)

        return locale('Command "{0}" has no subcommands.').format(command.qualified_name)

    async def check_cog_allowed_types(self, cog):
        user: discord.Member = self.context.author
        types = getattr(cog, "HELP_REQUIRES", None)
        if types is None:
            return False

        if "hide" in types:
            if self.context.bot.system.config.getboolean("developer", "dev_mode", fallback=False):
                return True

            return False

        if await self.context.bot.is_owner(user):
            return True

        if "editor" in types:
            usr = await self.context.bot.system.get_user_discord_id(user.id)
            if not usr.editor:
                return False

        if "mod" in types:
            if not self.context.guild:
                return False

            if not user.guild_permissions.ban_members:
                return False

        return True

    async def command_callback(self, ctx, *, command=None):
        await self.prepare_help_command(ctx, command)
        bot = ctx.bot

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        command = command.lower()

        # Check if it's a cog
        cogs = {x.lower(): y for x, y in bot.cogs.items()} # make it case insensitive
        cog = cogs.get(command)
        if cog is not None:
            return await self.send_cog_help(cog)

        maybe_coro = discord.utils.maybe_coroutine

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(' ')
        cmd = bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, self.remove_mentions(keys[0]))
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)

    def get_command_signature(self, command, dark=True):
        """Retrieves the signature portion of the help page.

        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        --------
        :class:`str`
            The signature for the command.
        """

        parent = command.full_parent_name
        alias = command.name if not parent else parent + ' ' + command.name

        if dark:
            return '`%s` %s' % (alias, command.signature)
        else:
            return '%s %s' % (alias, command.signature)

    async def send_bot_help(self, mapping):
        locale = self.context.bot.system.locale
        e = discord.Embed()

        e.title = locale("Xlydn help")
        fmt = locale("__Help Categories__\n")

        for cog in self.context.bot.cogs.values():
            if await self.check_cog_allowed_types(cog):
                fmt += getattr(cog, "locale_name", cog.qualified_name) + "\n"

        e.description = fmt

        await self.context.send(embed=e)

    async def send_cog_help(self, cog: commands.Cog):
        locale = self.context.bot.system.locale
        e = discord.Embed()

        fmt = locale("__{0} help__\n").format(getattr(cog, "locale_name", cog.qualified_name))

        cmds = await self.filter_commands(cog.get_commands())
        if not cmds:
            return await self.context.send(self.command_not_found(cog.qualified_name))

        for command in cmds:
            sig = self.get_command_signature(command)
            fmt += "|- " + sig + "\n"
            if command.short_doc:
                fmt += "|  | " + command.short_doc + "\n"

            if isinstance(command, GroupWithLocale):
                subs = command.commands
                for sub in subs:
                    fmt += "|  |- " + self.get_command_signature(sub) + "\n"

        e.description = fmt

        await self.context.send(embed=e)

    async def send_command_help(self, command):
        locale = self.context.bot.system.locale
        e = discord.Embed()

        fmt = locale("__{0} help__\n").format(command.qualified_name)
        fmt += locale("Command Usage:") + "\n"
        fmt += f"```\n{self.get_command_signature(command, dark=False)}\n```\n"

        if command.help:
            fmt += command.help + "\n"
        else:
            fmt += locale("No help given...")

        e.description = fmt
        await self.context.send(embed=e)

    async def send_group_help(self, group):
        locale = self.context.bot.system.locale
        e = discord.Embed()

        fmt = locale("__{0} help__\n").format(group.qualified_name)
        if group.help:
            fmt += group.help + "\n"
        else:
            fmt += locale("No help given...")

        fmt += "\n"

        cmds = await self.filter_commands(group.commands)

        if not cmds:
            return await self.send_command_help(group)

        fmt += "__" + locale("Subcommands") + "__\n"
        for command in cmds:
            sig = self.get_command_signature(command)
            if command.short_doc:
                doc = command.short_doc if len(command.short_doc) < 30 else command.short_doc[0:30] + "..."
            else:
                doc = locale("No help given...")

            fmt += "| " + sig + " - " + doc + "\n"

        e.description = fmt

        return await self.context.send(embed=e)
