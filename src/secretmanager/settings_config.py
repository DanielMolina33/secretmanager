"""Persistent application preferences backed by QFluentWidgets QConfig."""

from qfluentwidgets import (
    BoolValidator,
    ConfigItem,
    EnumSerializer,
    OptionsConfigItem,
    OptionsValidator,
    QConfig,
    Theme,
    qconfig,
)

from .paths import get_data_dir


class AppConfig(QConfig):
    """Settings with explicit defaults and QFluentWidgets validation."""

    themeMode = OptionsConfigItem(
        "QFluentWidgets",
        "ThemeMode",
        Theme.AUTO,
        OptionsValidator([Theme.LIGHT, Theme.DARK, Theme.AUTO]),
        EnumSerializer(Theme),
    )
    micaEnabled = ConfigItem(
        "SecretManager",
        "MicaEnabled",
        True,
        BoolValidator(),
    )


app_config = AppConfig()


def load_app_config():
    """Load preferences from the portable data directory."""
    qconfig.load(str(get_data_dir() / "config.json"), app_config)
