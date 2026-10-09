# SecretManager

SecretManager is a portable, offline secret manager for developers. It stores secrets in an encrypted local vault and provides a desktop interface and an optional command-line integration for supplying selected secrets to a process.

## Download

Portable Windows builds are published as ZIP files in GitHub Releases. Extract the ZIP and run the desktop application from the extracted folder. Keep the whole folder together when moving the application.

The Windows build is currently unsigned, so Windows may show a SmartScreen warning for an unrecognized app. Download releases only from the project's official release page and compare the published SHA-256 checksum with the file you downloaded.

Builds for macOS and Linux are not published yet. The source includes platform-specific code, but each platform needs its own packaged build and release checks.

## Portable data and backups

The vault and application configuration are stored in a `data` directory beside the portable application. Back up that directory to preserve your vault. Treat it as sensitive data.

**Do not include `data` or `config` in a public source archive or release ZIP.** The Windows build script preserves existing data when rebuilding, so create release archives from a clean staging copy that contains only the application files.

## Command-line integration

The CLI can start a process with selected vault secrets added to its environment. The desktop app must be running with the vault unlocked, CLI integration must be enabled in settings, and CLI access must be allowed for each requested secret.

Example on Windows PowerShell:

```powershell
.\app\SecretManagerCLI\SecretManagerCLI.exe run --use API_TOKEN -- powershell
```

Use the secret's name as the environment variable name. The command after `--` starts only if the requested secrets are available and permitted. A secret added to a process environment can be read by that process and its child processes; use the CLI only with trusted commands.

## Build for Windows

Build from the project root in PowerShell with Python 3.12–3.14 and Poetry installed:

```powershell
poetry install --with build
.\packaging\windows\build_windows.ps1
```

The output is `dist\SecretManager`. The package contains:

- `app\SecretManager\SecretManager.exe` — desktop application.
- `app\SecretManagerCLI\SecretManagerCLI.exe` — command-line launcher.

The build script performs isolated GUI and CLI smoke checks. It replaces generated executable folders and build caches while preserving `dist\SecretManager\data`.

## Source installation

Install the project dependencies with Poetry and launch the desktop application with:

```powershell
poetry install
poetry run secretmanager
```

The CLI entry point is `poetry run secretmanager run --use NAME -- COMMAND [ARGS ...]`.

## License

SecretManager is distributed under the GNU General Public License, version 3 only (`GPL-3.0-only`). See [LICENSE](LICENSE) for the complete license text.
