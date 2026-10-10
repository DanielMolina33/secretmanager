"""PyInstaller entry point for the visible console CLI."""

import sys

from secretmanager.cli import main


def run() -> int:
    arguments = sys.argv[1:]
    if not arguments or arguments[0] != "run":
        print(
            "Usage: secretmanager run --use KEY [KEY ...] -- COMMAND [ARGS ...]",
            file=sys.stderr,
        )
        return 2

    return main(arguments[1:])


if __name__ == "__main__":
    raise SystemExit(run())