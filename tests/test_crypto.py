from __future__ import annotations

import unittest

from cryptography.exceptions import InvalidTag

from secretmanager.crypto.key_encryption import decrypt_key, encrypt_key
from secretmanager.crypto.keys import generate_dek
from secretmanager.crypto.vault_keys import VaultKeyManager


class PhaseZeroCryptoTests(unittest.TestCase):
    def test_master_password_wraps_and_recovers_the_dek(self):
        dek, protected = VaultKeyManager.create("phase-zero test password")
        self.assertEqual(len(dek), 32)
        self.assertEqual(VaultKeyManager.unlock("phase-zero test password", protected), dek)
        with self.assertRaises(InvalidTag):
            VaultKeyManager.unlock("incorrect password", protected)

    def test_recovery_key_can_independently_wrap_the_same_dek(self):
        dek = generate_dek()
        recovery_key = generate_dek()
        nonce, encrypted_dek = encrypt_key(dek, recovery_key)
        self.assertEqual(decrypt_key(encrypted_dek, nonce, recovery_key), dek)
        with self.assertRaises(InvalidTag):
            decrypt_key(encrypted_dek, nonce, generate_dek())


if __name__ == "__main__":
    unittest.main()
