import gettext
import os.path
from glob import glob

BASE_DIR = "./"

LOCALE_DEFAULT = 'English'
LOCALE_DIR = "locale"
locales = frozenset(map(os.path.basename, filter(os.path.isdir, glob(os.path.join(BASE_DIR, LOCALE_DIR, '*')))))

gettext_translations = {
    locale: gettext.translation(
        "xlydn",
        languages=(locale,),
        localedir=os.path.join(BASE_DIR, LOCALE_DIR), fallback=False)
    for locale in locales}

gettext_translations['English'] = gettext.NullTranslations()
locales |= {'English'}


class LocaleTranslator:
    normals = {
        "English": "English",
        "English_Vulgar": "English Vulgar",
        "de": "Deutsch"
    }
    def __init__(self, cfg):
        self._config = cfg

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

    def __call__(self, text: str) -> str:
        return self.get(text)
