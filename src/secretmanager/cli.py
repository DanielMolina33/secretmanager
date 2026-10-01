"""Qt-free command-line entry point for the portable vault."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from .ipc import request_secrets
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
        values = request_secrets(get_data_dir(), names)
    except FileNotFoundError:
        print("The vault GUI must be open and unlocked before using the CLI.", file=sys.stderr)
        return 1
    except KeyError as error:
        print(f"Secret not found: {error.args[0]}.", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        # Never include returned secret material or request payloads in errors.
        print(f"Unable to get secrets from the unlocked vault: {error}", file=sys.stderr)
        return 1

    environment = os.environ.copy()
    environment.update(values)
    try:
        completed = subprocess.run(
            command,
            env=environment,
            shell=False,
            check=False,
        )
    except (OSError, ValueError) as error:
        print(f"Unable to start the requested command: {error}", file=sys.stderr)
        return 1
    return completed.returncode
