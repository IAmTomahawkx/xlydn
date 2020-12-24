import subprocess
import os

locales = os.listdir("./dev_locale")
locales.remove("all_files.py")

for locale in os.listdir("./dev_locale"):
    if locale.endswith('.py'):
        continue

    file = os.path.join("./dev_locale", locale, "LC_MESSAGES/xlydn.po")
    subprocess.call(["/usr/local/Cellar/gettext/0.20.2_1/bin/msgfmt", file, "-o",
                     os.path.join("./dev_locale", locale, "LC_MESSAGES/xlydn.mo")])

    if not os.path.exists(f"src/main/resources/base/locale/{locale}/LC_MESSAGES"):
        os.makedirs(f"src/main/resources/base/locale/{locale}/LC_MESSAGES")

    os.replace(os.path.join("./dev_locale", locale, "LC_MESSAGES/xlydn.mo"),
               os.path.join("src/main/resources/base/locale", locale, "LC_MESSAGES/xlydn.mo"))