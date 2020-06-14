import gettext
import os.path
from glob import glob
import tkinter

BASE_DIR = "./"

LOCALE_DEFAULT = 'English'
LOCALE_DIR = "locale"
locales = frozenset(map(os.path.basename, filter(os.path.isdir, glob(os.path.join(BASE_DIR, LOCALE_DIR, '*')))))

gettext_translations = {
    locale: gettext.translation(
        "xlydn",
        languages=(locale,),
        localedir=os.path.join(BASE_DIR, LOCALE_DIR))
    for locale in locales}

gettext_translations['English'] = gettext.NullTranslations()
locales |= {'English'}


class LocaleTranslator:
    def __init__(self, cfg):
        self._config = cfg
        #self.tk_var = tkinter.StringVar(master=None, value=cfg.get("general", "locale", fallback=LOCALE_DEFAULT))

    def get(self, text: str) -> str:
        if not gettext_translations:
            return gettext.gettext(text)

        locale = self._config.get("general", "locale", fallback=LOCALE_DEFAULT)
        return (
            gettext_translations.get(
                locale,
                gettext_translations[locale]
            ).gettext(text)
        )

    def set(self, locale: str):
        if locale not in gettext_translations:
            raise ValueError(self("Invalid locale"))

        self._config.set("general", "locale", locale)
        #self.tk_var.set(locale)

    def __call__(self, text: str) -> str:
        return self.get(text)