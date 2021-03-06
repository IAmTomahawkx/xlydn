"""
Licensed under the Open Software License version 3.0
"""
import sys
import shutil
import subprocess
import re
import os
from contextlib import suppress
import configparser

locales = [
    "en_US_Vulgar",
    "de"
]
if True:
    from utils import bot

    config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
    config.read("config.ini")

    system = bot.System(config)
    bt = system.discord_bot
    bt.load()
    bt.unload_extension("jishaku")
    nl = "\n"  # :peepee:
    nnl = "\\n"
    dummy = "\n".join([f"locale(\"{x.name}\")" for x in bt.walk_commands()]) + "\n"
    dummy = "\n".join(
        ["\n".join([f"locale(\"{y}\")" for y in x.aliases]) for x in bt.walk_commands() if x.aliases]) + "\n"
    dummy += "\n".join(
        [f"locale(\"\"\"{x.help.replace(nl, nnl)}\"\"\")" for x in bt.walk_commands() if x.help is not None]) + "\n"
    tb = system.twitch_bot
    tb.load()
    dummy += "\n".join([f"locale(\"{x.name}\")" for x in tb.walk_commands()]) + "\n"
    dummy = "\n".join(
        ["\n".join([f"locale(\"{y}\")" for y in x.aliases]) for x in tb.walk_commands() if x.aliases]) + "\n"
    dummy += "\n".join(
        [f"locale(\"\"\"{x.help.replace(nl, nnl)}\"\"\")" for x in tb.walk_commands() if x.help is not None]) + "\n"

    with open("utils/dummy_locale.py", "w") as f:
        f.write(dummy)  # this is just here for xgettext to find

locale = "template"

file = f'template.pot'

with suppress(FileNotFoundError):
    shutil.copy(file, file + ".bak")

with suppress(FileNotFoundError):
    os.remove(file)

all_files = """import os.path

for dir, subdirs, files in os.walk("."):
    if 'venv' in dir or 'locale' in dir or 'dev_locale' in dir:
        continue
    for file in files:
        if file.endswith('.py'):
            fname = os.path.join(dir, file)
            print(fname)"""

if not os.path.isfile('./dev_locale/all_files.py'):
    with open('./dev_locale/all_files.py', 'w') as f:
        f.write(all_files)

stuff = subprocess.run([sys.executable, './dev_locale/all_files.py'], capture_output=True)
content = stuff.stdout

subprocess.run(
    ['/usr/local/Cellar/gettext/0.20.2_1/bin/xgettext', '--files-from=-', '--from-code=UTF-8', '--keyword',
     '--keyword=locale', '-o', file],
    input=content)

with open(file) as f:
    data = f.read()

data = re.sub(r'^"Language: \\n"$', fr'"Language: English\\n"', data, flags=re.MULTILINE)
data = re.sub(r'^"Content-Type: text/plain; charset=CHARSET\\n"$', r'"Content-Type: text/plain; charset=UTF-8\\n"',
              data, flags=re.MULTILINE)

with open(file, "w") as f:
    f.write(data)

subprocess.run([r'/usr/local/Cellar/gettext/0.20.2_1/bin/msgcat', file, file + '.bak', '-o', file + '.cat'])

with suppress(FileNotFoundError):
    os.rename(file + '.cat', file)
