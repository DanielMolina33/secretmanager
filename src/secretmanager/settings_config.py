"""Persistent application preferences backed by QFluentWidgets QConfig."""

import json
import os
import tempfile
from enum import Enum
from pathlib import Path

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
    language = OptionsConfigItem(
        "SecretManager",
        "Language",
        "es",
        OptionsValidator(["es", "en", "system"]),
    )
    micaEnabled = ConfigItem(
        "SecretManager",
        "MicaEnabled",
        True,
        BoolValidator(),
    )
    clipboardHistoryAllowed = ConfigItem(
        "SecretManager",
        "ClipboardHistoryAllowed",
        False,
        BoolValidator(),
    )
    cliIntegrationEnabled = ConfigItem(
        "SecretManager",
        "CliIntegrationEnabled",
        False,
        BoolValidator(),
    )
    clipboardClearAfter = OptionsConfigItem(
        "SecretManager",
        "ClipboardClearAfterSeconds",
        10,
        OptionsValidator([0, 10, 20, 30, 60, 120, 300]),
    )

    autoLockMinutes = OptionsConfigItem(
        "SecretManager",
        "AutoLockMinutes",
        5,
        OptionsValidator([1, 5, 10, 15, 30]),
    )
    lockShortcut = ConfigItem(
        "SecretManager",
        "LockShortcut",
        "Ctrl+Shift+L",
    )


app_config = AppConfig()


def _config_items() -> dict[str, ConfigItem]:
    """Return application and inherited QFluentWidgets config items."""
    return {
        item.key: item
        for name in dir(AppConfig)
        if isinstance(item := getattr(AppConfig, name), ConfigItem)
    }


def _has_expected_type(default, value) -> bool:
    """Reject values of the wrong JSON type before a validator sees them."""
    if isinstance(default, bool):
        return type(value) is bool
    if isinstance(default, int):
        return type(value) is int
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, Enum):
        return type(value) is type(default)
    if isinstance(default, list):
        return (
            isinstance(value, list)
            and bool(value)
            and all(isinstance(item, str) for item in value)
        )
    return True


def _is_valid_value(item: ConfigItem, serialized_value) -> bool:
    """Check serialized data using the item's serializer and validator."""
    try:
        value = item.serializer.deserialize(serialized_value)
        if not _has_expected_type(item.defaultValue, value):
            return False
        if not item.validator.validate(value):
            return False

        if item.key == "SecretManager.LockShortcut":
            from PySide6.QtGui import QKeySequence

            sequence = QKeySequence.fromString(
                value,
                QKeySequence.SequenceFormat.PortableText,
            )
            portable_text = sequence.toString(
                QKeySequence.SequenceFormat.PortableText
            )
            modifiers = portable_text.split("+")[:-1]
            return not sequence.isEmpty() and bool(
                {"Ctrl", "Alt", "Meta"}.intersection(modifiers)
            )
    except (TypeError, ValueError, OverflowError):
        return False

    return True


def _read_config(path: Path) -> tuple[dict, bool]:
    """Read a JSON object; return an empty config for malformed files."""
    try:
        with path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
        if isinstance(config, dict):
            return config, False
    except (FileNotFoundError, UnicodeError, json.JSONDecodeError):
        pass

    return {}, True


def _write_config_atomically(path: Path, config: dict) -> None:
    """Replace a repaired config without leaving a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as config_file:
            temporary_path = Path(config_file.name)
            json.dump(config, config_file, ensure_ascii=False, indent=4)
            config_file.flush()
            os.fsync(config_file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_app_config():
    """Load preferences, replacing missing or invalid values with defaults."""
    config_path = get_data_dir() / "config.json"
    items = _config_items()

    # Missing keys use defaults even when this function is called again after
    # settings have already changed in the current process.
    for item in items.values():
        app_config.set(item, item.defaultValue, save=False)

    if config_path.exists():
        config, malformed = _read_config(config_path)
        repaired_config = config.copy()
        repair_needed = malformed

        for key, item in items.items():
            group = config.get(item.group)
            if isinstance(group, dict) and item.name in group:
                serialized_value = group[item.name]
                present = True
            elif key in config:
                serialized_value = config[key]
                present = True
            else:
                serialized_value = None
                present = False

            if present and _is_valid_value(item, serialized_value):
                item.deserializeFrom(serialized_value)
            else:
                if present or not malformed:
                    repair_needed = True
                app_config.set(item, item.defaultValue, save=False)

            repaired_group = repaired_config.get(item.group)
            if not isinstance(repaired_group, dict):
                repaired_group = {}
                repaired_config[item.group] = repaired_group
            repaired_group[item.name] = item.serialize()
            repaired_config.pop(key, None)

        if repair_needed:
            _write_config_atomically(config_path, repaired_config)

    qconfig.load(str(config_path), app_config)


def restore_app_config_defaults():
    """Restore all application-owned settings to their declared defaults."""
    for item in (
        app_config.themeMode,
        app_config.language,
        app_config.micaEnabled,
        app_config.clipboardHistoryAllowed,
        app_config.cliIntegrationEnabled,
        app_config.clipboardClearAfter,
        app_config.autoLockMinutes,
        app_config.lockShortcut,
    ):
        qconfig.set(item, item.defaultValue, save=False)
    qconfig.save()
