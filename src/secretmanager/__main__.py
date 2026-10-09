"""Dispatch to the Qt-free CLI or the desktop application."""

import sys


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "run":
        from .cli import main as cli_main

        return cli_main(arguments[1:])
    if arguments:
        print("Usage: secretmanager [run --use KEY [KEY ...] -- COMMAND [ARGS ...]]", file=sys.stderr)
        return 2

    from .app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())