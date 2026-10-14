# SecretManager Portable

**A portable, offline secret manager for developers.**

SecretManager Portable helps you store and manage API keys, tokens, passwords, and other sensitive values locally, without relying on cloud services or online accounts.

Your vault is encrypted and stored alongside the application, making it suitable for portable use on supported desktop platforms.

> **Alpha release:** This software is still experimental. Some platform builds have not been verified on their target operating systems. Test with non-sensitive data before relying on it for critical secrets.

## Features

- **Local encrypted vault:** Keep your secrets in an encrypted local database.
- **Master password:** Protect access to your vault with a master password.
- **Recovery kit:** Recover access to your vault using the recovery mechanism provided by the application.
- **Portable design:** Keep the application and its data together in a folder.
- **Cross-platform:** Builds are provided for Windows, Linux, and macOS.
- **Command-line interface:** Access supported secret-management operations from the terminal.
- **Secret management:** Organize, search, view, and manage stored secrets.
- **Offline-first:** Designed to work without cloud synchronization or an online account.

## Download

Download the latest available release from:

**[GitHub Releases](https://github.com/danielmolina33/secretmanager/releases)**

For version `v1.0.1-alpha`, the available archives are:

| Platform | Download |
|---|---|
| Windows | `SecretManager-v1.0.1-alpha-windows.zip` |
| Linux | `SecretManager-v1.0.1-alpha-linux.tar.gz` |
| macOS — Apple Silicon | `SecretManager-v1.0.1-alpha-macos-arm64.zip` |
| macOS — Intel | `SecretManager-v1.0.1-alpha-macos-x86_64.zip` |

**Demo vaults:** `SecretManager-DemoVaults.zip` is available as a release asset. It contains synthetic test vaults with 100, 1,000, and 5,000 secrets. See the included README for the master password and instructions. Back up or rename your existing `data` folder before replacing it.

Choose the archive that matches your operating system and processor architecture.

### Verify the download

If a SHA-256 checksum is provided with the release, verify the downloaded archive before opening it.

**Windows (PowerShell):**

```powershell
Get-FileHash .\SecretManager-v1.0.1-alpha-windows.zip -Algorithm SHA256
```

**Linux:**

```bash
sha256sum SecretManager-v1.0.1-alpha-linux.tar.gz
```

**macOS:**

```bash
shasum -a 256 SecretManager-v1.0.1-alpha-macos-arm64.zip
```

For an Intel Mac, replace the filename with `SecretManager-v1.0.1-alpha-macos-x86_64.zip`.

Compare the result with the checksum published for the exact archive you downloaded. A checksum confirms that the file matches the published value; it does not independently establish the publisher's identity.

## Get Started

### Windows

#### 1. Download and extract

1. Download `SecretManager-v1.0.1-alpha-windows.zip` from the [Releases page](https://github.com/danielmolina33/secretmanager/releases).
2. Extract the archive to a folder of your choice.
3. Keep the extracted files together.

You can use a regular folder or a removable drive, provided the filesystem supports the required operations.

#### 2. Launch SecretManager

Open the extracted folder and launch the main SecretManager application.

If Windows displays a SmartScreen warning, verify that you downloaded the archive from the official repository and check its published checksum, if available. Do not bypass a warning if you cannot establish that the download is trustworthy.

#### 3. Create your vault

Follow the on-screen instructions to create your vault and set a master password.

Store your recovery kit securely if the application provides one.

### Linux

#### 1. Download and extract

Download `SecretManager-v1.0.1-alpha-linux.tar.gz` from the [Releases page](https://github.com/danielmolina33/secretmanager/releases).

Extract the archive:

```bash
tar -xzf SecretManager-v1.0.1-alpha-linux.tar.gz
```

Change into the extracted directory and locate the `app` folder.

#### 2. Launch SecretManager

The Linux archive contains the application and its supporting files. Keep the directory structure intact.

From the extracted release directory, navigate to the application folder and launch the provided `SecretManager` executable:

```bash
cd linux/app/SecretManager
./SecretManager
```

If the extracted directory structure differs from the example above, locate the corresponding `app/SecretManager` directory in the extracted archive.

If execution is denied, inspect the file permissions and the error message before making changes. Do not run the application as root simply to get it working.

#### 3. Create your vault

Follow the on-screen instructions to create your vault, choose a master password, and securely store your recovery kit if one is provided.

#### Linux compatibility

Linux desktop environments and distributions differ in their libraries, display systems, and security settings. If the application fails to start, include your distribution, desktop environment, display server (X11 or Wayland), and the complete error message when reporting the problem.

### macOS

**Status: Experimental.** These builds have not yet been verified on a Mac. The application may display security warnings because the release is not signed or notarized by Apple.

#### 1. Download the correct version

Open the [SecretManager Releases page](https://github.com/danielmolina33/secretmanager/releases) and download the archive matching your Mac:

- **Apple Silicon:** `SecretManager-v1.0.1-alpha-macos-arm64.zip`
- **Intel:** `SecretManager-v1.0.1-alpha-macos-x86_64.zip`

To identify your processor, open the Apple menu and select **About This Mac**.

#### 2. Extract the archive

1. Open **Downloads** in Finder.
2. Double-click the downloaded ZIP file.
3. Open the extracted folder.

The archive contains these components:

- `SecretManager.app` — the graphical application.
- `SecretManager/` — the separately packaged application executable and its supporting files.
- `SecretManagerCLI/` — the command-line interface and its supporting files.

Keep the extracted files and folders together. Do not move or delete individual components.

#### 3. Launch the graphical application

1. Locate `SecretManager.app` in the extracted folder.
2. Double-click `SecretManager.app`.
3. Follow the on-screen instructions to create or unlock your vault.

You do not need to install Python or Qt separately.

You normally do not need to open the contents of `SecretManager.app` or execute its internal binary manually.

#### 4. If macOS blocks the application

Because this is an experimental release and is not signed or notarized by Apple, macOS may display a security warning.

First, confirm that you downloaded the archive from the official [GitHub Releases page](https://github.com/danielmolina33/secretmanager) and verify its checksum if one is published.

If macOS offers an option to allow this specific application, review it under **System Settings → Privacy & Security**. Available options depend on your macOS version.

Do not disable Gatekeeper globally or run commands intended to bypass macOS security protections.

If macOS reports that the application is damaged or that its integrity cannot be verified, stop and report the exact message instead of bypassing the warning.

#### 5. Use the command-line interface (optional)

The `SecretManagerCLI/` directory is intended for command-line operations.

The CLI is separate from the graphical application and is not required to open the GUI. See [Command-Line Interface](#command-line-interface) for the supported command and requirements.

#### 6. Create your first vault

1. Follow the application's instructions to create a vault.
2. Choose a strong master password and store it safely.
3. Securely store your recovery kit if one is provided.
4. Create a test secret and verify that you can retrieve it.
5. Lock the vault and unlock it again to verify that your password works.

**Important:** These macOS builds have not yet been verified on actual Mac hardware. First-launch behavior and compatibility may vary by macOS version.

## Your First Vault

When you launch SecretManager for the first time:

1. Follow the setup instructions displayed by the application.
2. Create a strong master password.
3. Save your recovery kit securely if the application provides one.
4. Add a non-sensitive test secret.
5. Verify that you can view and retrieve the test secret.
6. Lock the vault and unlock it again.

Keep your master password and recovery kit safe. If both are lost, you may be unable to recover your encrypted secrets.

Do not use real production credentials until you have tested the application and understand its current alpha limitations.

## Command-Line Interface

The portable package includes a CLI for running a command with selected secrets available as environment variables. Secret names are stored in uppercase.

From the extracted package directory:

**Windows (PowerShell):**

```powershell
.\app\SecretManagerCLI\secretmanager.exe run --use API_KEY -- python script.py
```

**Linux and macOS:**

```bash
./app/SecretManagerCLI/secretmanager run --use API_KEY -- python3 script.py
```

Before using the CLI, open and unlock the vault, enable CLI integration in SecretManager settings, and allow CLI use for each requested secret.

Use `--use` once with one or more secret names. Put `--` before the command and its arguments. The child process inherits the existing environment, while requested secret values replace variables with matching names. An expired secret prevents the command from starting; a secret nearing expiration produces a warning.

Avoid passing secret values through shell history or command-line arguments. Do not paste real secrets into issue reports, terminal transcripts, or public logs.

## Portable Data and Backups

SecretManager is designed to keep its application and data together in a portable directory.

- Keep the application's supporting files together.
- Do not move individual runtime components out of the extracted folder.
- Avoid disconnecting a removable drive while the vault is open or being written to.
- Close the application before manually copying the vault for backup.
- Store backups securely because they contain encrypted vault data.

A manual copy is not a substitute for testing recovery. Verify that you understand how to restore your data before relying on a backup.

**Important:** Portability does not mean that every filesystem or removable drive is equally reliable. Use a filesystem supported by your operating system and keep an independent backup of important encrypted data.

## Security Notes

SecretManager is designed around local storage and encrypted secrets. However, this is an alpha release and has not been independently security-audited.

Please keep the following in mind:

- Use a strong master password.
- Protect your recovery kit.
- Keep the application and its data in a private location.
- Avoid storing production credentials until you have tested the release.
- Never publish your vault database, master password, recovery kit, or secret values.
- Report security-sensitive issues privately rather than publishing exploitable details in a public issue.

No software can guarantee protection against every threat, especially when a device or operating system is already compromised.

## Troubleshooting

If the application does not start or behaves unexpectedly, collect the following information:

- Operating system and version.
- Processor architecture.
- Release archive filename.
- Desktop environment and display server, if applicable on Linux.
- Exact error message.
- Steps required to reproduce the problem.

Do not run the application as an administrator or root unless a documented operation specifically requires it.

Do not disable operating-system security protections globally to make the application start.

## Report Bugs and Request Features

Feedback is particularly valuable during the alpha stage.

- **Report a bug:** [GitHub Issues](https://github.com/danielmolina33/secretmanager/issues)
- **Download a release:** [GitHub Releases](https://github.com/danielmolina33/secretmanager/releases)
- **Browse the source code:** [SecretManager Portable repository](https://github.com/danielmolina33/secretmanager)

When reporting a bug, include the environment details and reproduction steps described above.

Never attach real vaults, credentials, recovery kits, or other sensitive information.

## Build from Source

SecretManager is developed in Python. The project's source repository and build configuration are available on GitHub.

To build from source:

1. Install a compatible Python version and Poetry.
2. Clone the repository.
3. Review the project's dependency and build configuration.
4. Install the declared dependencies.
5. Follow the build workflow and platform-specific requirements defined in the repository.

Repository: [github.com/danielmolina33/secretmanager](https://github.com/danielmolina33/secretmanager)

The dependencies required for development may differ from the dependencies bundled in the portable releases.

## License

SecretManager Portable is distributed under the **GNU General Public License v3.0 only (GPL-3.0-only)**, as declared by the project.

See the repository's license file for the complete terms.

## Project Status

SecretManager Portable is under active development.

The alpha releases are intended to gather feedback, identify compatibility problems, and improve usability across supported platforms.

If you try the application, feedback about installation-free operation, first-run setup, platform compatibility, and CLI workflows is especially useful.