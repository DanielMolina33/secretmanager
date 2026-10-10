# SecretManager

**Your secrets, on your device, ready when you need them.**

SecretManager is a portable, offline vault for developers. Keep API tokens, and other sensitive values encrypted locally, then copy them when needed or pass selected secrets directly to trusted command-line tools.

No account. No cloud sync. Your vault stays with you.

## Features

- **Encrypted local vault:** secret data is stored in a SQLCipher-encrypted database and protected by your master password.
- **Recovery kit:** configure an optional recovery kit so you can regain access if you forget your master password. Keep the recovery code somewhere safe and separate from your device.
- **Fast secret lookup:** search entries by name or note, and copy a name or value with one click.
- **Safer clipboard handling:** optionally clear copied secrets automatically after a timeout.
- **Automatic vault locking:** lock the vault after a period of inactivity.
- **Expiration tracking:** set expiration dates for secrets and see when they are expiring or expired. Expired secrets are not passed to CLI commands.
- **Developer-friendly CLI:** allow individual secrets for command-line use and inject approved values into a process environment without placing them in the command text.
- **Your preferred look and language:** choose light, dark, or system theme, and use the interface in English or Spanish.
- **Portable by design:** keep the application folder and its `data` directory together when moving your vault between locations.

## Download — v1.0.1-alpha

Choose the archive for your operating system from the **Releases** section of this GitHub repository:

| Platform | Release file | Status |
| --- | --- | --- |
| Windows | `SecretManager-v1.0.1-alpha-windows.zip` | Available; unsigned, so Windows may show a SmartScreen warning. |
| Linux | `SecretManager-v1.0.1-alpha-linux.tar.gz` | Available; extract the archive and launch the included application. |
| macOS (Apple Silicon) | `SecretManager-v1.0.1-alpha-macos-arm64.zip` | Available, but not yet tested on macOS. |
| macOS (Intel) | `SecretManager-v1.0.1-alpha-macos-x86_64.zip` | Available, but not yet tested on macOS. |

This is an **alpha release**. The vault format and interface are stable, but the macOS builds have not been tested on a Mac. Please keep a separate backup of important vault data and report any issues through the project's issue tracker.

For Windows, download only from the official releases page and compare the archive's SHA-256 checksum with the value published for that file.

### Launch on Linux

Extract the `.tar.gz`, open a terminal in the extracted `linux/app/SecretManager` folder, and run `./SecretManager`. Keep the extracted folder together; the executable relies on its bundled runtime and libraries. If needed, grant it execute permission first with `chmod +x SecretManager`.

### Launch on macOS

The macOS archives are untested. If Gatekeeper blocks the app, macOS may require you to approve it in **System Settings → Privacy & Security**. These builds are not signed or notarized by Apple.

## Command-line integration

SecretManager can make approved secrets available as environment variables to a command you launch. The desktop app must be open, the vault unlocked, CLI integration enabled, and CLI access allowed for each requested secret.

Windows PowerShell example:

```powershell
.\app\SecretManagerCLI\secretmanager.exe run --use API_TOKEN -- powershell
```

The CLI does not put secret values in the command line itself. The process you launch can read the environment variables, as can its child processes, so use this feature only with commands you trust.

## Portable vault and backups

The vault and application configuration live in the `data` directory beside the portable application. Keep this directory with the app and back it up securely. A recovery kit is useful if you forget the master password, but it is not a substitute for backing up the vault files.

## Build from source

The repository includes a Windows build script and a cross-platform GitHub Actions workflow for Windows, Linux, and macOS packaging. See [Windows packaging instructions](packaging/windows/README.md) and [the alpha build workflow](.github/workflows/build-alpha.yml).

To install the Python project for development:

```bash
poetry install --with build
poetry run secretmanager
```

The CLI entry point is `poetry run secretmanager run --use NAME -- COMMAND [ARGS ...]`.

**Release packaging note:** `data/` and `config/` are user-specific and must not be included in public release archives. Build release archives from a clean staging directory.

## License

SecretManager is free software distributed under **GNU GPLv3 only** (`GPL-3.0-only`). You are welcome to use, study, modify, and redistribute it under the terms of the [GNU General Public License v3](LICENSE).

