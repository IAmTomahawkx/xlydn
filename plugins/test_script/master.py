from addons.scripting import helpers, models

def setup(manager):
    manager.inject(Example(manager))

class Example(helpers.Injection):
    def __init__(self, manager):
        self.manager = manager

    @helpers.Injection.listen()
    async def on_state_update(self, state: bool):
        pass

    @helpers.Injection.listen()
    async def on_spec_update(self, spec: dict):
        self.settings = spec

    @helpers.Injection.listen("message")
    async def we_got_a_message(self, message: models.PartialMessage):
        if not message.author.bot:
            await message.channel.send(f"You are not a bot")

    @helpers.Injection.listen("will_unload")
    async def will_unload(self):
        print("will unload soon")

    @helpers.Injection.command("hello")
    async def command_shoutout(self, message: models.PartialMessage):
        await message.channel.send(f"Hello {message.author.name}")
