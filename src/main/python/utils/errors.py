from discord.ext.commands import CheckFailure, CommandError

class GuildCheckFailed(CheckFailure):
    pass

class Error(Exception):
    def __init__(self, msg):
        self.message = msg
        super().__init__(msg)

class UserFriendlyError(Error):
    pass