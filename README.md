# SecretManager

SecretManager is a portable, offline secret manager for developers. It stores secrets in an encrypted local vault and provides a desktop interface and an optional command-line integration for supplying selected secrets to a process.

## Download

Portable pre-release builds are packaged separately for each operating system. Extract the matching archive and run the desktop application from its folder. Keep the whole folder together when moving the application.

The Windows build is currently unsigned, so Windows may show a SmartScreen warning for an unrecognized app. Download releases only from the project's official release page and compare the published SHA-256 checksum with the file you downloaded.

The macOS and Linux packages must be built on their native runners; see the `Build SecretManager v1.0.1-alpha` GitHub Actions workflow.

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

The output is `dist\SecretManager-v1.0.1-alpha\windows`. The package contains:

- `app\SecretManager\SecretManager.exe` — desktop application.
- `app\SecretManagerCLI\SecretManagerCLI.exe` — command-line launcher.

The build script performs isolated GUI and CLI smoke checks. The GUI and CLI executables both use the SecretManager icon, and the versioned ZIP is created beside the platform folder.

## Build for Linux and macOS

These builds must run on Linux and macOS hosts. The `Build SecretManager v1.0.1-alpha` workflow builds on native GitHub-hosted runners and uploads versioned archives. macOS has separate `arm64` and `x86_64` packages so each can include native dependencies for its target architecture.

## Source installation

Install the project dependencies with Poetry and launch the desktop application with:

```powershell
poetry install
poetry run secretmanager
```

The CLI entry point is `poetry run secretmanager run --use NAME -- COMMAND [ARGS ...]`.

## License

SecretManager is distributed under the GNU General Public License, version 3 only (`GPL-3.0-only`). See [LICENSE](LICENSE) for the complete license text.
