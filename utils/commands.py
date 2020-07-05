from discord.ext import commands


class CommandWithLocale(commands.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = self.name
        self.original_aliases = self.aliases.copy()
        self.original_doc = self.help

    def inject_locale(self, bot):
        self.name = bot.system.locale(self.original_name)
        self.help = bot.system.locale(self.original_doc)
        if self.original_aliases:
            self.aliases = [bot.system.locale(x) for x in self.original_aliases]


class GroupWithLocale(commands.Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aliases = []
        self.original_name = self.name
        self.original_doc = self.help
        self.original_aliases = self.aliases.copy()

    def inject_locale(self, bot):
        self.name = bot.system.locale(self.original_name)
        self.help = bot.system.locale(self.original_doc)
        if self.original_aliases:
            self.aliases = [bot.system.locale(x) for x in self.original_aliases]

        new_commands = {}
        for cmd in self.commands:
            if isinstance(cmd, GroupWithLocale):
                cmd.inject_locale(bot)
                new_commands[cmd.name] = cmd
                for al in cmd.aliases:
                    new_commands[al] = cmd

            else:
                cmd.inject_locale(bot)
                self.all_commands[cmd.name] = cmd
                for al in cmd.aliases:
                    new_commands[al] = cmd

        self.all_commands.clear()
        self.all_commands.update(new_commands)

    def command(self, *args, **kwargs):
        """A shortcut decorator that invokes :func:`.command` and adds it to
        the internal command list via :meth:`~.GroupMixin.add_command`.
        """
        def decorator(func):
            kwargs.setdefault('parent', self)
            result = command(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    def group(self, *args, **kwargs):
        """A shortcut decorator that invokes :func:`.group` and adds it to
        the internal command list via :meth:`~.GroupMixin.add_command`.
        """
        def decorator(func):
            kwargs.setdefault('parent', self)
            result = group(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator


def command(*args, **kwargs):
    return commands.command(*args, cls=CommandWithLocale, **kwargs)


def group(*args, **kwargs):
    return commands.group(*args, cls=GroupWithLocale, **kwargs)
