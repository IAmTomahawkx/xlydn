import traceback
import logging
from utils import commands
from discord.ext import commands as dpy_commands
from utils import paginators

logger = logging.getLogger("xlydn.addons.discord.pluginManager")

def setup(bot):
    bot.add_cog(PluginManager(bot))

class PluginManager(dpy_commands.Cog):
    HELP_REQUIRES = ["owner"]
    def __init__(self, bot):
        self.bot = bot
        self.system = bot.system
        self.locale_bot = bot.system.locale("Plugin Manager")
        self.plugins = bot.system.scripts

    @commands.group("plugin", aliases=['plugins'], invoke_without_command=True)
    async def scripts(self, ctx):
        """
        Displays a list of your plugins, along with some information about them
        """
        entries = []
        for script in self.plugins.plugins.values():
            entries.append(("\u200b", self.system.locale("Plugin name: {0}\nPlugin id: {1}\nEnabled: {2}\nAuthor: {3}\nVersion: {4}")
                            .format(script.name, script.identifier, script.enabled, script.author, script.version)))

        pages = paginators.FieldPages(ctx, entries=entries)
        await pages.paginate()

    @scripts.command()
    async def reload(self, ctx, plugin_id: str):
        """
        Reloads the given plugin
        """
        if plugin_id not in self.plugins.scripts:
            return await ctx.send(self.system.locale("No plugin with that identifier found"))

        await ctx.send(self.system.locale("Reloading {0}").format(plugin_id))

        try:
            await self.plugins.reload_script(plugin_id)
        except Exception as e:
            pages = paginators.TextPages(ctx, "".join(traceback.format_exception(type(e), e, e.__traceback__)))
            await pages.paginate()

    @scripts.command()
    async def search(self, ctx, plugin_name: str):
        """
        Searches the api for plugins similar to the given name.
        For more control over search parameters, please use the dashboard to search
        """
        pass # do api stuff here

    @scripts.command()
    async def download(self, ctx, plugin_id: str):
        """
        Downloads the given plugin.
        Running this command for a plugin that is already installed will not do anything, if you wish to update a plugin, use the `plugin update` command
        """
        if plugin_id.lower() in self.plugins.plugins:
            return await ctx.send(self.system.locale("This plugin is already installed. Maybe you meant `{0}plugin update`").format(ctx.prefix))

        try:
            error = await self.plugins.download_plugin(plugin_id)
            if error:
                return await ctx.send(error)
        except Exception as e:
            logger.exception(f"Failed to download script: {plugin_id}", exc_info=e)
            await ctx.send(self.system.locale("Hmm, looks like something messed up while downloading that plugin. Details have been logged"))

        else:
            if plugin_id in self.plugins.plugins:
                await ctx.send(self.system.locale("Downloaded plugin {0}").format(self.plugins.plugins[plugin_id].name))
            else:
                await ctx.send(self.system.locale("Failed to download and install the plugin"))

    @scripts.command()
    async def update(self, ctx, plugin_id: str):
        """
        Updates the given plugin, if a newer version exists.
        Be aware that currently this replaces all files the plugin has, so the plugin data will be erased.
        """
        data = await self.plugins.update_plugin(plugin_id)
        await ctx.send(data)