#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
release_name="SecretManager-v1.0.1-alpha"
system_name="$(uname -s)"
case "$system_name" in
    Linux) platform="linux" ;;
    Darwin) platform="macos" ;;
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
if [[ "$platform" == "macos" ]]; then
    desktop_args+=(--windowed --icon "$mac_icon" --target-architecture universal2 --osx-bundle-identifier "com.secretmanager.portable")
fi

(cd "$project_root" && poetry run pyinstaller "${common_args[@]}" "${desktop_args[@]}" \
    --name SecretManager \
    --workpath "$build_root/desktop" \
    --specpath "$build_root/spec/desktop" \
    packaging/windows/entrypoints/desktop.py)

cli_args=("${common_args[@]}")
if [[ "$platform" == "macos" ]]; then
    cli_args+=(--add-data "$mac_icon:secretmanager/resources/icons" --target-architecture universal2)
fi
cli_args+=(
    --name SecretManagerCLI
    --workpath "$build_root/cli"
    --specpath "$build_root/spec/cli"
    packaging/windows/entrypoints/cli.py
)
(cd "$project_root" && poetry run pyinstaller "${cli_args[@]}")

if [[ "$platform" == "linux" ]]; then
    test -x "$app_output/SecretManager/SecretManager"
    test -x "$app_output/SecretManagerCLI/SecretManagerCLI"
    archive="$release_root/$release_name-linux.tar.gz"
    rm -f "$archive"
    tar -C "$release_root" -czf "$archive" "$platform"
else
    test -d "$app_output/SecretManager.app"
    test -x "$app_output/SecretManagerCLI/SecretManagerCLI"
    archive="$release_root/$release_name-macos.zip"
    rm -f "$archive"
    ditto -c -k --sequesterRsrc --keepParent "$output_root" "$archive"
fi

echo "Portable $platform package ready: $output_root"
echo "Distribution archive ready: $archive"
