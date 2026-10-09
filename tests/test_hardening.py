from __future__ import annotations

import contextlib
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import secrets
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cryptography.exceptions import InvalidTag
from sqlcipher3 import dbapi2

from secretmanager import cli
from secretmanager.crypto.secret_encryption import decrypt_secret, encrypt_secret
from secretmanager.database.database import Database
from secretmanager.domain.expiry import VALID
from secretmanager.ipc import LocalSecretServer, MAX_SECRET_NAMES, SecretGrant
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService


class PayloadConnection:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.responses: list[bytes] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def poll(self, _timeout: float) -> bool:
        return True

    def recv_bytes(self, _maxsize: int) -> bytes:
        return self.payload

    def send_bytes(self, payload: bytes) -> None:
        self.responses.append(payload)


class PhaseSevenHardeningTests(unittest.TestCase):
    def test_corrupt_database_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="phase7-corrupt-") as directory:
            path = Path(directory) / "vault.db"
            path.write_bytes(b"corrupt-vault" + bytes(range(64)))
            database = Database(path, b"k" * 32)
            try:
                with self.assertRaises(dbapi2.DatabaseError):
                    database.create_tables()
            finally:
                database.close()

    def test_missing_data_path_fails_and_same_vault_returns_after_reconnect(self):
        with tempfile.TemporaryDirectory(prefix="phase7-disconnect-") as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            key = b"d" * 32
            database = Database(data_dir / "vault.db", key)
            database.create_tables()
            service = SecretService(SqliteSecretRepository(database.Session, lambda: key))
            service.create("RECONNECT_TEST", "persisted-marker", allow_cli=True)
            offline_dir = root / "offline-data"
            data_dir.rename(offline_dir)
            try:
                with self.assertRaises(dbapi2.OperationalError):
                    service.get("RECONNECT_TEST")
            finally:
                offline_dir.rename(data_dir)
            self.assertEqual(service.get("RECONNECT_TEST").value, "persisted-marker")
            database.close()

    def test_tampered_secret_ciphertext_fails_authentication(self):
        nonce, ciphertext = encrypt_secret("tamper-marker", b"t" * 32)
        altered = bytearray(ciphertext)
        altered[-1] ^= 1
        with self.assertRaises(InvalidTag):
            decrypt_secret(bytes(altered), nonce, b"t" * 32)

    def test_ipc_rejects_invalid_shapes_and_limits(self):
        server = LocalSecretServer(Path("."), lambda _name: None)
        requests = [None, [], {"operation": "bad", "names": ["A"]},
                    {"operation": "get", "names": []},
                    {"operation": "get", "names": ["A", "A"]},
                    {"operation": "get", "names": ["A", 3]},
                    {"operation": "get", "names": ["A"] * (MAX_SECRET_NAMES + 1)}]
        for request in requests:
            with self.subTest(request=str(request)[:64]):
                self.assertIn(server._handle_request(request)["error"],
                              {"invalid_request", "invalid_names"})

    def test_malformed_ipc_bytes_are_discarded_or_rejected_safely(self):
        server = LocalSecretServer(Path("."), lambda _name: None)
        for payload in (b"{", b"\xff"):
            connection = PayloadConnection(payload)
            server._serve_connection(connection)
            self.assertEqual(connection.responses, [])
        connection = PayloadConnection(b"[]")
        server._serve_connection(connection)
        self.assertEqual(connection.responses, [b'{"ok":false,"error":"invalid_request"}'])

    def test_concurrent_ipc_requests_do_not_cross_secret_values(self):
        values = {f"K{i}": SimpleNamespace(value=f"V{i}", allow_cli=True,
                  expires_on=None, expires_at_time=None) for i in range(32)}
        server = LocalSecretServer(Path("."), values.get)
        def request(index):
            return server._handle_request({"operation": "get", "names": [f"K{index}"]})
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(request, range(32)))
        self.assertEqual([r["secrets"][f"K{i}"]["value"] for i, r in enumerate(results)],
                         [f"V{i}" for i in range(32)])

    def test_hostile_unicode_value_survives_real_ipc_and_child_environment(self):
        value = "á漢字💥\nquotes'\";$(echo must-not-run)"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        child_code = ("import hashlib,os,sys; v=os.environ['PHASE7_HOSTILE']; "
                      "sys.exit(0 if hashlib.sha256(v.encode()).hexdigest()==sys.argv[1] "
                      "and v not in sys.argv else 41)")
        with tempfile.TemporaryDirectory(prefix="phase7-hostile-") as directory:
            data_dir = Path(directory)
            key = b"h" * 32
            database = Database(data_dir / "vault.db", key)
            database.create_tables()
            service = SecretService(SqliteSecretRepository(database.Session, lambda: key))
            service.create("PHASE7_HOSTILE", value, allow_cli=True)
            (data_dir / "config.json").write_text(
                '{"SecretManager":{"CliIntegrationEnabled":true}}',
                encoding="utf-8",
            )
            server = LocalSecretServer(data_dir, service.get)
            server.start()
            try:
                with patch.object(cli, "get_data_dir", return_value=data_dir):
                    result = cli.main(["--use", "PHASE7_HOSTILE", "--", sys.executable,
                                       "-c", child_code, digest])
                self.assertEqual(result, 0)
            finally:
                server.close()
                database.close()

    def test_cli_parser_handles_deterministic_random_arguments(self):
        rng = random.Random(70261)
        alphabet = "abcXYZ012_-/;\\\n\t💥\x00"
        cases = [["".join(rng.choice(alphabet) for _ in range(rng.randrange(30)))
                  for _ in range(rng.randrange(12))] for _ in range(1000)]
        def fake_request(_data_dir, names):
            return {name: SecretGrant("fuzz-safe", VALID) for name in names}
        from secretmanager import ipc
        with (patch.object(cli, "_cli_integration_enabled", return_value=True),
              patch.object(ipc, "request_secrets", side_effect=fake_request),
              patch.object(cli, "_run_child", return_value=0),
              contextlib.redirect_stderr(io.StringIO())):
            for args in cases:
                self.assertIsInstance(cli.main(args), int)

    def test_ipc_handler_handles_deterministic_random_bytes(self):
        rng = random.Random(70262)
        server = LocalSecretServer(Path("."), lambda _name: None)
        for _ in range(1000):
            server._serve_connection(PayloadConnection(secrets.token_bytes(rng.randrange(512))))

    def test_child_receives_secret_as_environment_data_not_argv(self):
        value = "parent-override-\n-💥"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        child_code = ("import hashlib,os,sys; v=os.environ['PHASE7_ENV']; "
                      "sys.exit(0 if hashlib.sha256(v.encode()).hexdigest()==sys.argv[1] "
                      "and v not in sys.argv else 43)")
        observed_command = []
        original_runner = cli._run_child
        def run_child(command, environment):
            observed_command.extend(command)
            return original_runner(command, environment)
        from secretmanager import ipc
        with (patch.object(cli, "_cli_integration_enabled", return_value=True),
              patch.object(ipc, "request_secrets",
                           return_value={"PHASE7_ENV": SecretGrant(value, VALID)}),
              patch.object(cli, "_run_child", side_effect=run_child)):
            result = cli.main(["--use", "PHASE7_ENV", "--", sys.executable,
                               "-c", child_code, digest])
        self.assertEqual(result, 0)
        self.assertNotIn(value, observed_command)
        self.assertNotIn("PHASE7_ENV", os.environ)


if __name__ == "__main__":
    unittest.main()



