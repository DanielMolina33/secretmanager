#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
release_name="SecretManager-v1.0.1-alpha"
system_name="$(uname -s)"
requested_macos_arch="${1:-}"
if [[ "$#" -gt 1 ]]; then
    echo "Usage: $0 [macos-architecture]" >&2
    exit 2
fi

case "$system_name" in
    Linux)
        if [[ -n "$requested_macos_arch" ]]; then
            echo "A macOS architecture can only be selected on macOS." >&2
            exit 2
        fi
        platform="linux"
        macos_arch=""
        ;;
    Darwin)
        host_arch="$(uname -m)"
        macos_arch="${requested_macos_arch:-$host_arch}"
        case "$macos_arch" in
            arm64|x86_64) ;;
            *) echo "Unsupported macOS architecture: $macos_arch (expected arm64 or x86_64)" >&2; exit 2 ;;
        esac
        if [[ "$host_arch" != "$macos_arch" ]]; then
            echo "Build $macos_arch on a native $macos_arch runner; this runner is $host_arch." >&2
            exit 2
        fi
        platform="macos-$macos_arch"
        ;;
    *) echo "Unsupported build host: $system_name" >&2; exit 2 ;;
esac

release_root="$project_root/dist/$release_name"
output_root="$release_root/$platform"
app_output="$output_root/app"
build_root="$project_root/build/$release_name/$platform"
source_root="$project_root/src"
translation_dir="$source_root/secretmanager/localization/translations"
icon_dir="$source_root/secretmanager/resources/icons"
png_icon="$icon_dir/secretmanager.png"
mac_icon="$icon_dir/secretmanager.icns"

case "$output_root" in
    "$project_root"/*) ;;
    *) echo "Refusing to write outside the project: $output_root" >&2; exit 2 ;;
esac

if ! command -v poetry >/dev/null 2>&1; then
    echo "Poetry is required. Install Poetry and run: poetry install --with build" >&2
    exit 2
fi

pyinstaller_version="$(cd "$project_root" && poetry run pyinstaller --version)"
if [[ "$pyinstaller_version" != "6.22.3" ]]; then
    echo "Expected locked PyInstaller 6.22.3, found $pyinstaller_version" >&2
    exit 2
fi

for language in es en; do
    (cd "$project_root" && poetry run pyside6-lrelease \
        "$translation_dir/secretmanager_$language.ts" \
        -qm "$translation_dir/secretmanager_$language.qm")
done

rm -rf "$output_root" "$build_root"
mkdir -p "$app_output" "$build_root"

common_args=(
    --noconfirm
    --clean
    --onedir
    --paths "$source_root"
    --distpath "$app_output"
    --collect-data qfluentwidgets
    --add-data "$translation_dir/secretmanager_es.qm:secretmanager/localization/translations"
    --add-data "$translation_dir/secretmanager_en.qm:secretmanager/localization/translations"
    --add-data "$png_icon:secretmanager/resources/icons"
)

desktop_args=()
if [[ "$system_name" == "Darwin" ]]; then
    desktop_args+=(--windowed --icon "$mac_icon" --target-architecture "$macos_arch" --osx-bundle-identifier "com.secretmanager.portable")
fi

(cd "$project_root" && poetry run pyinstaller "${common_args[@]}" "${desktop_args[@]}" \
    --name SecretManager \
    --workpath "$build_root/desktop" \
    --specpath "$build_root/spec/desktop" \
    packaging/windows/entrypoints/desktop.py)

cli_args=("${common_args[@]}")
if [[ "$system_name" == "Darwin" ]]; then
    cli_args+=(--add-data "$mac_icon:secretmanager/resources/icons" --target-architecture "$macos_arch")
fi
cli_args+=(
    --name SecretManagerCLI
    --workpath "$build_root/cli"
    --specpath "$build_root/spec/cli"
    packaging/windows/entrypoints/cli.py
)
(cd "$project_root" && poetry run pyinstaller "${cli_args[@]}")
cli_exe="$app_output/SecretManagerCLI/SecretManagerCLI"
if [[ -f "$cli_exe" ]]; then
    mv "$cli_exe" "$app_output/SecretManagerCLI/secretmanager"
fi

if [[ "$system_name" == "Linux" ]]; then
    test -x "$app_output/SecretManager/SecretManager"
    test -x "$app_output/SecretManagerCLI/secretmanager"
    archive="$release_root/$release_name-linux.tar.gz"
    rm -f "$archive"
    tar -C "$release_root" -czf "$archive" "$platform"
else
    test -d "$app_output/SecretManager.app"
    test -x "$app_output/SecretManagerCLI/secretmanager"
    archive="$release_root/$release_name-$platform.zip"
    rm -f "$archive"
    ditto -c -k --sequesterRsrc --keepParent "$output_root" "$archive"
fi

echo "Portable $platform package ready: $output_root"
echo "Distribution archive ready: $archive"
