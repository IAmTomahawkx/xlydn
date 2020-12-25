# xlydn
An in-the-works Discord and Twitch bot, run locally by the streamer

Before you try to run this, heres a good idea if it'll work or not: [![Build Status](https://travis-ci.org/IAmTomahawkx/xlydn.svg?branch=master)](https://travis-ci.org/IAmTomahawkx/xlydn) \
As for how to run it, You'll need python 3.7 (**not** 3.6, **not** 3.8, **not** 3.9).\
Install the requirements with
```
py -3.7 -m pip install -r requirements.txt
```
if you're on windows, or 
```
python3.7 -m pip install -r requirements.txt
```
on MacOS/Linux. 

Xlydn uses the `fbs` package to run and compile. To run the source, use
```
fbs run
```
~~alternatively, install the binary releases~~
(just kidding, no binary releases have been made yet. SoonTm)

## Plugins

As of right now, the plugin api is very much in the works. The functions available for plugins are viewable in
`src/main/python/addons/scripting/helpers.py` and `src/.../scripting/models.py`. A very basic script would look something like

```python
from addons.scripting import helpers, models

def setup(manager):
    manager.inject(Hello(manager))

class Hello(helpers.Injection):
    def __init__(self, manager):
        self.manager = manager

    @helpers.Injection.listen()
    async def on_state_update(self, state: bool):
        # state_update is called when the user toggles the script on or off
        pass

    @helpers.Injection.listen() # the spec_update event, specified by the function name
    async def on_spec_update(self, spec: dict):
        self.settings = spec
        # this event currently wont be called, it is for future dashboard integration

    @helpers.Injection.listen("message") # the message event, specified in the decorator
    async def we_got_a_message(self, message: models.PartialMessage):
        pass

    @helpers.Injection.listen("will_unload")
    async def will_unload(self):
        # this function will be called when the plugin is about to be unloaded, giving you time to do some cleanup
        pass

    @helpers.Injection.command("hello") # creates a command that will be fired when someone types <prefix>hello
    async def command_hello(self, message: models.PartialMessage):
        message.channel.send(f"Hello, {message.author.name}!")
        print("hello!")
```

You may upload your plugin to the xlydn servers using the `plugin upload` command on discord.
To do so, you must first register as a plugin dev. There is no easy public-facing way to do this currently,
simply hopping into the [discord server](https://discord.gg/cEAxG8A) and pinging Tom will be the easiest way for now.
Once you've uploaded your plugin, anyone can download it using the `plugin download` command.
I will make proper documentation for the plugin api once I've created a more solid system.
