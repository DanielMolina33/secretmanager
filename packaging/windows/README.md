# Windows portable build

This build produces a portable folder containing two executables:

- app\SecretManager\SecretManager.exe: Fluent desktop application, without a console window.
- app\SecretManagerCLI\SecretManagerCLI.exe: console launcher for the run command.

The vault is stored in the data directory beside app. Keep and back up that directory with the portable build. The build script only replaces its own generated executable folders and build cache; it leaves data intact.

Build from the project root in PowerShell:

~~~powershell
poetry install --with build
.\packaging\windows\build_windows.ps1
~~~

The resulting folder is dist\SecretManager. Copy the whole folder to move the application; do not copy only an .exe, because the one-folder package also needs its bundled runtime files.

Example CLI use:

~~~powershell
.\dist\SecretManager\app\SecretManagerCLI\SecretManagerCLI.exe run --use A_TEST -- powershell
~~~

The build script runs GUI and CLI smoke checks against a temporary copy of the package and temporary IPC data.