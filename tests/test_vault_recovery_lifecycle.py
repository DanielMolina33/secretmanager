from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager.vault_manager import UnlockAttemptError, VaultManager


class VaultRecoveryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="vault-recovery-")
        self.data_dir = Path(self.temp_dir.name)
        self.manager = VaultManager(self.data_dir)
        self.old_password = "original-master-passphrase"
        self.new_password = "replacement-master-passphrase"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_recovery_kit_is_consumed_after_successful_recovery(self):
        self.manager.create(self.old_password)
        pending = self.manager.prepare_recovery_kit(self.old_password)
        self.manager.commit_recovery_kit(pending)
        self.assertTrue(self.manager.recovery_configured)

        recovered = self.manager.recover(pending.code, self.new_password)
        self.assertTrue(recovered.is_unlocked)
        self.assertFalse(self.manager.recovery_configured)

        with self.assertRaises(ValueError):
            self.manager.recover(pending.code, "third-master-passphrase")

        fresh_manager = VaultManager(self.data_dir)
        self.assertTrue(fresh_manager.unlock(self.new_password).is_unlocked)
        with self.assertRaises(UnlockAttemptError):
            VaultManager(self.data_dir).unlock(self.old_password)

    def test_password_change_keeps_recovery_kit_and_rewraps_same_vault_key(self):
        vault = self.manager.create(self.old_password)
        original_dek = vault.get_dek()
        pending = self.manager.prepare_recovery_kit(self.old_password)
        self.manager.commit_recovery_kit(pending)

        self.manager.change_master_password(self.old_password, self.new_password)

        self.assertTrue(self.manager.recovery_configured)
        self.assertEqual(vault.get_dek(), original_dek)
        self.assertEqual(
            VaultManager(self.data_dir).unlock(self.new_password).get_dek(),
            original_dek,
        )
        recovery_manager = VaultManager(self.data_dir)
        self.assertEqual(
            recovery_manager.recover(pending.code, "third-master-passphrase").get_dek(),
            original_dek,
        )


if __name__ == "__main__":
    unittest.main()
