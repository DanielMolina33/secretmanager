"""PyInstaller entry point for the Fluent desktop application."""

if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()

    from secretmanager.app import main

    main()