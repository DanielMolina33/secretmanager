[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$projectPrefix = $projectRoot.TrimEnd("\") + "\"
$outputRoot = Join-Path $projectRoot "dist\SecretManager"
$appOutput = Join-Path $outputRoot "app"
$buildRoot = Join-Path $projectRoot "build\windows-packaging"
$sourceRoot = Join-Path $projectRoot "src"
$translationSources = @("es", "en") | ForEach-Object { Join-Path $sourceRoot "secretmanager\localization\translations\secretmanager_$_.ts" }
$translationBinaries = @("es", "en") | ForEach-Object { Join-Path $sourceRoot "secretmanager\localization\translations\secretmanager_$_.qm" }
$desktopEntry = Join-Path $PSScriptRoot "entrypoints\desktop.py"
$cliEntry = Join-Path $PSScriptRoot "entrypoints\cli.py"

$poetry = Get-Command poetry -ErrorAction SilentlyContinue
if ($null -eq $poetry) {
    throw "Poetry is required. Install Poetry and run this script again."
}

$pythonLines = @(& $poetry.Source -C $projectRoot env info --executable 2>$null)
if ($LASTEXITCODE -ne 0 -or $pythonLines.Count -eq 0) {
    throw "Could not locate the project's Poetry environment. Run: poetry install --with build"
}
$python = [string]$pythonLines[-1]
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "The Poetry interpreter was not found at: $python"
}

$pyinstallerVersion = (& $python -m PyInstaller --version 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing. Run: poetry install --with build"
}
if ([string]$pyinstallerVersion -ne "6.22.3") {
    throw "Expected locked PyInstaller 6.22.3, found $pyinstallerVersion."
}

$lrelease = Join-Path (Split-Path -Parent $python) "pyside6-lrelease.exe"
if (-not (Test-Path -LiteralPath $lrelease -PathType Leaf)) {
    throw "Qt Linguist compiler was not found in the Poetry environment: $lrelease"
}
Write-Host "Compiling the UI translation catalogs..."
for ($index = 0; $index -lt $translationSources.Count; $index++) {
    & $lrelease $translationSources[$index] -qm $translationBinaries[$index]
    if ($LASTEXITCODE -ne 0) {
        throw "Qt Linguist catalog compilation failed with exit code $LASTEXITCODE."
    }
}

function Remove-OwnedOutput([string] $path) {
    $fullPath = [System.IO.Path]::GetFullPath($path)
    if (-not $fullPath.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the project: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
}

# Remove only generated app/build folders. Keep dist\SecretManager\data intact
# so rebuilding can never erase the user's portable vault.
Remove-OwnedOutput (Join-Path $appOutput "SecretManager")
Remove-OwnedOutput (Join-Path $appOutput "SecretManagerCLI")
Remove-OwnedOutput (Join-Path $buildRoot "desktop")
Remove-OwnedOutput (Join-Path $buildRoot "cli")
Remove-OwnedOutput (Join-Path $buildRoot "spec\desktop")
Remove-OwnedOutput (Join-Path $buildRoot "spec\cli")

$null = New-Item -ItemType Directory -Path $appOutput -Force
$null = New-Item -ItemType Directory -Path $buildRoot -Force

$commonArguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--paths", $sourceRoot,
    "--distpath", $appOutput
)

$desktopArguments = $commonArguments + @(
    "--windowed",
    "--name", "SecretManager",
    "--hidden-import", "winaccent",
    "--collect-data", "qfluentwidgets",
    "--add-data", "$($translationBinaries[0]);secretmanager/localization/translations",
    "--add-data", "$($translationBinaries[1]);secretmanager/localization/translations",
    "--workpath", (Join-Path $buildRoot "desktop"),
    "--specpath", (Join-Path $buildRoot "spec\desktop"),
    $desktopEntry
)
# Keep PyInstaller from collecting unrelated native DLLs from the host tool runtime.
$originalPath = $env:PATH
$env:PATH = (($env:PATH -split [System.IO.Path]::PathSeparator | Where-Object { $_ -notmatch '(?i)codex-runtimes.*codex-primary-runtime.*dependencies.*native' }) -join [System.IO.Path]::PathSeparator)
Write-Host "Building the Fluent desktop executable..."
& $python @desktopArguments
if ($LASTEXITCODE -ne 0) {
    throw "The desktop executable build failed with exit code $LASTEXITCODE."
}

$cliArguments = $commonArguments + @(
    "--console",
    "--name", "SecretManagerCLI",
    "--workpath", (Join-Path $buildRoot "cli"),
    "--specpath", (Join-Path $buildRoot "spec\cli"),
    $cliEntry
)
Write-Host "Building the CLI executable..."
& $python @cliArguments
if ($LASTEXITCODE -ne 0) {
    throw "The CLI executable build failed with exit code $LASTEXITCODE."
}

$desktopExe = Join-Path $appOutput "SecretManager\SecretManager.exe"
$cliExe = Join-Path $appOutput "SecretManagerCLI\SecretManagerCLI.exe"
if (-not (Test-Path -LiteralPath $desktopExe -PathType Leaf)) {
    throw "The desktop executable was not generated: $desktopExe"
}
if (-not (Test-Path -LiteralPath $cliExe -PathType Leaf)) {
    throw "The CLI executable was not generated: $cliExe"
}

$env:PATH = $originalPath

Write-Host "Running isolated GUI and CLI smoke checks..."
& $python (Join-Path $PSScriptRoot "smoke_bundle.py") $outputRoot
if ($LASTEXITCODE -ne 0) {
    throw "The isolated bundle smoke checks failed with exit code $LASTEXITCODE."
}

Write-Host "Portable Windows package ready: $outputRoot"
