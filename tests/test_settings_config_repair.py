from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qfluentwidgets import qconfig, Theme
from secretmanager.settings_config import app_config, load_app_config, _config_items


class SettingsConfigRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="settings-repair-")
        self.data_dir = Path(self.temp_dir.name)
        self.items = _config_items()
        for item in self.items.values():
            qconfig.set(item, item.defaultValue, save=False)
        self.load_patch = patch(
            "secretmanager.settings_config.qconfig.load",
            autospec=True,
        )
        self.load_patch.start()
        self.data_dir_patch = patch(
            "secretmanager.settings_config.get_data_dir",
            return_value=self.data_dir,
        )
        self.data_dir_patch.start()

    def tearDown(self):
        self.data_dir_patch.stop()
        self.load_patch.stop()
        for item in self.items.values():
            qconfig.set(item, item.defaultValue, save=False)
        self.temp_dir.cleanup()

    def test_invalid_and_missing_values_are_repaired_to_declared_defaults(self):
        config_path = self.data_dir / "config.json"
        config_path.write_text(
            json.dumps({
                "SecretManager": {
                    "Language": "unknown-language",
                    "AutoLockMinutes": "5",
                    "LockShortcut": "L",
                    "UnknownFutureSetting": 17,
                },
                "QFluentWidgets": {"ThemeMode": "not-a-theme"},
            }),
            encoding="utf-8",
        )

        load_app_config()

        self.assertEqual(app_config.language.value, "es")
        self.assertEqual(app_config.autoLockMinutes.value, 5)
        self.assertEqual(app_config.lockShortcut.value, "Ctrl+Shift+L")
        self.assertEqual(app_config.themeMode.value, Theme.AUTO)

        repaired = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(repaired["SecretManager"]["Language"], "es")
        self.assertEqual(repaired["SecretManager"]["AutoLockMinutes"], 5)
        self.assertEqual(repaired["SecretManager"]["LockShortcut"], "Ctrl+Shift+L")
        self.assertEqual(repaired["QFluentWidgets"]["ThemeMode"], "Auto")
        self.assertEqual(repaired["SecretManager"]["UnknownFutureSetting"], 17)
        self.assertFalse(list(self.data_dir.glob("config.json.*.tmp")))

    def test_malformed_json_is_replaced_with_a_valid_default_configuration(self):
        config_path = self.data_dir / "config.json"
        config_path.write_text('{"SecretManager": ', encoding="utf-8")

        load_app_config()

        repaired = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(repaired["SecretManager"]["Language"], "es")
        self.assertEqual(repaired["SecretManager"]["ClipboardClearAfterSeconds"], 10)
        self.assertEqual(repaired["SecretManager"]["AutoLockMinutes"], 5)
        self.assertEqual(repaired["QFluentWidgets"]["ThemeMode"], "Auto")

    def test_non_object_json_is_replaced_instead_of_crashing(self):
        config_path = self.data_dir / "config.json"
        config_path.write_text("[]", encoding="utf-8")

        load_app_config()

        repaired = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIsInstance(repaired, dict)
        self.assertEqual(repaired["SecretManager"]["Language"], "es")


if __name__ == "__main__":
    unittest.main()
