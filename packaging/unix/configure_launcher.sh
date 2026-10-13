#!/usr/bin/env bash
set -euo pipefail

desktop_id="com.secretmanager.portable"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
application="$script_dir/app/SecretManager/SecretManager"

if [[ -n "${XDG_DATA_HOME:-}" ]]; then
    data_home="$XDG_DATA_HOME"
else
    data_home="${HOME:?HOME must be set}/.local/share"
fi

if [[ "$data_home" != /* ]]; then
    echo "XDG_DATA_HOME must be an absolute path." >&2
    exit 1
fi

applications_dir="$data_home/applications"
registered_entry="$applications_dir/$desktop_id.desktop"
legacy_bundle_entry="$script_dir/app/SecretManager/$desktop_id.desktop"

if [[ "${1:-}" == "--remove" ]]; then
    rm -f -- "$registered_entry" "$legacy_bundle_entry"
    echo "SecretManager application-menu entry removed."
    exit 0
elif [[ "$#" -gt 0 ]]; then
    echo "Usage: $0 [--remove]" >&2
    exit 2
fi

if [[ ! -x "$application" ]]; then
    echo "SecretManager executable was not found at app/SecretManager/SecretManager." >&2
    exit 1
fi

icon=""
for candidate in \
    "$script_dir/app/SecretManager/_internal/secretmanager/resources/icons/secretmanager.png" \
    "$script_dir/app/SecretManager/secretmanager/resources/icons/secretmanager.png"; do
    if [[ -f "$candidate" ]]; then
        icon="$candidate"
        break
    fi
done

if [[ -z "$icon" ]]; then
    echo "SecretManager icon was not found in the application bundle." >&2
    exit 1
fi

escape_desktop_string() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//$'\n'/\\n}"
    value="${value//$'\t'/\\t}"
    value="${value// /\\s}"
    printf '%s' "$value"
}

escape_exec_argument() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//\$/\\\$}"
    value="${value//\`/\\\`}"
    value="${value//%/%%}"
    printf '"%s"' "$value"
}

write_entry() {
    local destination="$1"
    local destination_dir temporary_file
    destination_dir="$(dirname -- "$destination")"
    mkdir -p -- "$destination_dir"
    temporary_file="$(mktemp "$destination_dir/.${desktop_id}.XXXXXX")"
    {
        printf '[Desktop Entry]\n'
        printf 'Version=1.0\n'
        printf 'Type=Application\n'
        printf 'Name=SecretManager\n'
        printf 'Comment=Portable offline secret manager for developers\n'
        printf 'Exec=%s\n' "$(escape_exec_argument "$application")"
        printf 'Icon=%s\n' "$(escape_desktop_string "$icon")"
        printf 'Terminal=false\n'
        printf 'StartupNotify=true\n'
    } >"$temporary_file"
    chmod 755 "$temporary_file"
    mv -f -- "$temporary_file" "$destination"
}

write_entry "$registered_entry"
rm -f -- "$legacy_bundle_entry"

echo "SecretManager launcher configured."
echo "Desktop integration: $registered_entry"
