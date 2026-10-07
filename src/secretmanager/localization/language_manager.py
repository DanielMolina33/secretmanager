"""Resolve and install selected interface translations before UI creation."""

from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from qfluentwidgets import FluentTranslator


_LANGUAGE_LOCALES = {
    "es": QLocale("es_ES"),
    "en": QLocale("en_US"),
}


def resolve_language(preference: str) -> str:
    """Resolve a saved preference to one of the application languages."""
    if preference in _LANGUAGE_LOCALES:
        return preference

    if preference == "system":
        for ui_language in QLocale.system().uiLanguages():
            language_code = ui_language.replace("_", "-").split("-", 1)[0].lower()
            if language_code in _LANGUAGE_LOCALES:
                return language_code

    return "es"


class LanguageManager:
    """Owns QFluentWidgets and SecretManager Qt translators."""

    def __init__(self, application, preference: str):
        self.language = resolve_language(preference)
        locale = _LANGUAGE_LOCALES[self.language]

        self.fluent_translator = FluentTranslator(locale, application)
        application.installTranslator(self.fluent_translator)

        self.application_translator = QTranslator(application)
        translation_path = (
            Path(__file__).parent
            / "translations"
            / f"secretmanager_{self.language}.qm"
        )
        if not self.application_translator.load(str(translation_path)):
            raise RuntimeError(
                f"Could not load application translations: {translation_path}"
            )
        application.installTranslator(self.application_translator)
