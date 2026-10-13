from __future__ import annotations

from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager.system_events import linux


class LinuxLogindSessionResolutionTests(unittest.TestCase):
    def test_resolves_session_by_pid_first(self):
        with patch.object(
            linux.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout='o "/org/freedesktop/login1/session/_7"\n'
            ),
        ) as run:
            self.assertEqual(
                linux._session_path_for_pid(83664),
                "/org/freedesktop/login1/session/_7",
            )

        command = run.call_args.args[0]
        self.assertEqual(command[-2:], ["u", "83664"])

    def test_uses_xdg_session_id_when_pid_is_not_in_a_logind_session(self):
        pid_error = subprocess.CalledProcessError(
            1,
            ["busctl", "GetSessionByPID"],
            stderr="PID does not belong to any known session",
        )
        replies = [
            pid_error,
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout='o "/org/freedesktop/login1/session/_7"\n'
            ),
        ]
        with (
            patch.dict(linux.os.environ, {"XDG_SESSION_ID": "7"}),
            patch.object(linux.subprocess, "run", side_effect=replies) as run,
        ):
            self.assertEqual(
                linux._session_path_for_pid(83664),
                "/org/freedesktop/login1/session/_7",
            )

        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][-2:], ["s", "7"])

    def test_finds_unique_active_graphical_session_when_session_id_is_missing(self):
        sessions = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                'a(susso) 3 '
                '"6" 2000 "other" "seat1" "/org/freedesktop/login1/session/_6" '
                '"7" 1000 "development" "seat0" "/org/freedesktop/login1/session/_7" '
                '"8" 1000 "development" "" "/org/freedesktop/login1/session/_8"'
            ),
        )

        def run_session_query(command, **_kwargs):
            if command[1:4] == ["--system", "call", linux._SERVICE]:
                return sessions
            if command[-1] == "Active":
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="b true\n")
            if command[-1] == "Type":
                return subprocess.CompletedProcess(args=[], returncode=0, stdout='s "wayland"\n')
            raise AssertionError(f"Unexpected busctl command: {command!r}")

        pid_error = subprocess.CalledProcessError(
            1,
            ["busctl", "GetSessionByPID"],
            stderr="PID does not belong to any known session",
        )

        call_count = 0

        def run_busctl(command, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise pid_error
            return run_session_query(command, **kwargs)

        with (
            patch.dict(linux.os.environ, {"XDG_SESSION_ID": ""}),
            patch.object(linux.os, "getuid", return_value=1000),
            patch.object(linux.subprocess, "run", side_effect=run_busctl) as run,
        ):
            self.assertEqual(
                linux._session_path_for_pid(83664),
                "/org/freedesktop/login1/session/_7",
            )

        self.assertEqual(run.call_count, 4)

    def test_does_not_choose_between_multiple_active_graphical_sessions(self):
        list_reply = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                'a(susso) 2 '
                '"7" 1000 "development" "seat0" "/org/freedesktop/login1/session/_7" '
                '"9" 1000 "development" "seat1" "/org/freedesktop/login1/session/_9"'
            ),
        )

        def run_busctl(command, **_kwargs):
            if command[-1] == "Active":
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="b true\n")
            if command[-1] == "Type":
                return subprocess.CompletedProcess(args=[], returncode=0, stdout='s "x11"\n')
            if command[-1] == "ListSessions":
                return list_reply
            raise AssertionError(f"Unexpected busctl command: {command!r}")

        with patch.object(linux.subprocess, "run", side_effect=run_busctl):
            self.assertIsNone(linux._active_graphical_session_path(1000))


if __name__ == "__main__":
    unittest.main()
