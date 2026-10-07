"""Qt-free command-line entry point for the portable vault."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from .domain.expiry import EXPIRED, EXPIRING
from .ipc import CliPermissionDeniedError, IpcRequestCancelledError, request_secrets
from .paths import get_data_dir


_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secretmanager run")
    parser.add_argument(
        "--use",
        nargs="+",
        required=True,
        metavar="KEY",
        help="secret name(s) to inject into the child process environment",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        separator = arguments.index("--")
    except ValueError:
        print("Usage: secretmanager run --use KEY [KEY ...] -- COMMAND [ARGS ...]", file=sys.stderr)
        return 2

    try:
        options = _parser().parse_args(arguments[:separator])
    except SystemExit as error:
        return int(error.code)
    command = arguments[separator + 1:]
    if not command:
        print("A command must follow --.", file=sys.stderr)
        return 2

    names = options.use
    if len(set(names)) != len(names):
        print("Secret names in --use must be unique.", file=sys.stderr)
        return 2
    invalid = [name for name in names if not _ENVIRONMENT_NAME.fullmatch(name)]
    if invalid:
        print("A requested secret name is not a valid environment variable name.", file=sys.stderr)
        return 2

    try:
        grants = request_secrets(get_data_dir(), names)
    except IpcRequestCancelledError:
        print(
            "The vault was locked or closed; command not started.",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError:
        print("The vault GUI must be open and unlocked before using the CLI.", file=sys.stderr)
        return 1
    except KeyError as error:
        print(f"Secret not found: {error.args[0]}.", file=sys.stderr)
        return 1
    except CliPermissionDeniedError as error:
        print(f"CLI use is not permitted for secret(s): {error}.", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        # Never include returned secret material or request payloads in errors.
        print(f"Unable to get secrets from the unlocked vault: {error}", file=sys.stderr)
        return 1

    expired = [name for name in names if grants[name].status == EXPIRED]
    if expired:
        print(
            "Command not started; expired secret(s): " + ", ".join(expired) + ".",
            file=sys.stderr,
        )
        return 1

    expiring = [name for name in names if grants[name].status == EXPIRING]
    if expiring:
        print(
            "Warning: secret(s) are expiring soon: "
            + ", ".join(expiring)
            + ".",
            file=sys.stderr,
        )

    environment = os.environ.copy()
    environment.update({name: grants[name].value for name in names})
    try:
        return _run_child(command, environment)
    except (OSError, ValueError) as error:
        print(f"Unable to start the requested command: {error}", file=sys.stderr)
        return 1


def _interrupt_child(process: subprocess.Popen[bytes]) -> None:
    """Forward Ctrl+C to the isolated child process or process group."""
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGINT)
    except OSError:
        # The child may have exited while the interrupt was being handled.
        pass


def _run_child(command: list[str], environment: dict[str, str]) -> int:
    # Resolve command names using PATH and, on Windows, PATHEXT. This allows
    # direct execution of registered executables and command scripts without
    # adding per-tool cases or asking a shell to parse the command line.
    search_path = os.environ.get("PATH") if os.name == "nt" else environment.get("PATH")
    executable = shutil.which(command[0], path=search_path)
    resolved_command = [executable or command[0], *command[1:]]

    process_options: dict[str, object] = {}
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        process_options["start_new_session"] = True

    with subprocess.Popen(
        resolved_command,
        env=environment,
        shell=False,
        **process_options,
    ) as process:
        try:
            return process.wait()
        except KeyboardInterrupt:
            _interrupt_child(process)
            # A second Ctrl+C should be forwarded too, while still reaping the
            # child before this CLI exits.
            while True:
                try:
                    process.wait()
                    return 130
                except KeyboardInterrupt:
                    _interrupt_child(process)
