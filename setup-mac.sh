#!/bin/bash
# Connects Claude Code configuration in the local home to its iCloud copy.
# Flags: --dry-run reports changes; --link-settings links settings.json.

set -u

dry_run=0
link_settings=0
ok=0
linked=0
adopted=0
backed_up=0
skipped=0
problems=0

print_summary() {
    if [ "$dry_run" -eq 1 ]; then
        summary_prefix='Summary (dry run, nothing changed):'
    else
        summary_prefix='Summary:'
    fi
    printf '%s ok=%s linked=%s adopted=%s backed-up=%s skipped=%s problems=%s\n' \
        "$summary_prefix" \
        "$ok" "$linked" "$adopted" "$backed_up" "$skipped" "$problems"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --link-settings)
            link_settings=1
            ;;
        *)
            printf 'Error: unknown option: %s\n' "$1" >&2
            problems=$((problems + 1))
            print_summary
            exit 1
            ;;
    esac
    shift
done

if [ -z "${HOME:-}" ]; then
    printf 'Error: HOME is not set.\n' >&2
    problems=$((problems + 1))
    print_summary
    exit 1
fi

home_abs=$(cd "$HOME" 2>/dev/null && pwd -P)
if [ -z "$home_abs" ]; then
    printf 'Error: HOME does not exist or cannot be accessed: %s\n' "$HOME" >&2
    problems=$((problems + 1))
    print_summary
    exit 1
fi

icloud="$home_abs/Library/Mobile Documents/com~apple~CloudDocs/.claude"
local_root="$home_abs/.claude"
skill_path="$home_abs/Library/Mobile Documents/com~apple~CloudDocs/Skill_etc."
memory_key=$(printf '%s' "$skill_path" | LC_ALL=C tr -c 'A-Za-z0-9' '-')
memory_local="$local_root/projects/$memory_key/memory"
memory_icloud="$icloud/memory/Skill_etc"

printf 'Memory key: %s\n' "$memory_key"

if [ ! -d "$icloud" ]; then
    printf 'Error: iCloud Drive is not set up or not synced yet: %s\n' "$icloud" >&2
    problems=$((problems + 1))
    print_summary
    exit 1
fi

ensure_dir() {
    dir_path="$1"
    if [ -d "$dir_path" ]; then
        return 0
    fi
    if [ "$dry_run" -eq 1 ]; then
        printf 'would create directory: %s\n' "$dir_path"
        return 0
    fi
    if mkdir -p "$dir_path"; then
        return 0
    fi
    printf 'Error: failed to create directory: %s\n' "$dir_path" >&2
    problems=$((problems + 1))
    return 1
}

path_exists() {
    [ -e "$1" ] || [ -L "$1" ]
}

create_link() {
    link_source="$1"
    link_path="$2"
    link_label="$3"
    if [ "$dry_run" -eq 1 ]; then
        printf '%s: would link %s -> %s\n' "$link_label" "$link_path" "$link_source"
        return 0
    fi
    if ln -s "$link_source" "$link_path"; then
        return 0
    fi
    printf 'Error: %s: failed to create symlink %s -> %s\n' \
        "$link_label" "$link_path" "$link_source" >&2
    problems=$((problems + 1))
    return 1
}

link_item() {
    item_local="$1"
    item_icloud="$2"
    item_label="$3"
    item_required="$4"

    if [ -L "$item_local" ]; then
        item_current=$(readlink "$item_local" 2>/dev/null)
        item_readlink_status=$?
        if [ "$item_readlink_status" -ne 0 ]; then
            printf 'Error: %s: failed to read symlink: %s\n' "$item_label" "$item_local" >&2
            problems=$((problems + 1))
            return
        fi
        if [ "$item_current" = "$item_icloud" ]; then
            printf '%s: ok\n' "$item_label"
            ok=$((ok + 1))
        else
            printf '%s: points elsewhere, left alone: %s -> %s\n' \
                "$item_label" "$item_local" "$item_current" >&2
            problems=$((problems + 1))
        fi
        return
    fi

    if path_exists "$item_local"; then
        if ! ensure_dir "$(dirname "$item_icloud")"; then
            return
        fi
        if path_exists "$item_icloud"; then
            backup_dir="$local_root/backups"
            backup_path="$backup_dir/$item_label.$(date '+%Y%m%d-%H%M%S')"
            if ! ensure_dir "$backup_dir"; then
                return
            fi
            if path_exists "$backup_path"; then
                printf 'Error: %s: backup destination already exists: %s\n' \
                    "$item_label" "$backup_path" >&2
                problems=$((problems + 1))
                return
            fi
            if [ "$dry_run" -eq 1 ]; then
                printf '%s: would move local item to backup: %s\n' "$item_label" "$backup_path"
            elif ! mv "$item_local" "$backup_path"; then
                printf 'Error: %s: failed to move local item to backup: %s\n' \
                    "$item_label" "$backup_path" >&2
                problems=$((problems + 1))
                return
            fi
            if ! ensure_dir "$(dirname "$item_local")"; then
                return
            fi
            if create_link "$item_icloud" "$item_local" "$item_label"; then
                if [ "$dry_run" -eq 1 ]; then
                    printf '%s: would back up and link\n' "$item_label"
                else
                    printf '%s: backed-up and linked\n' "$item_label"
                fi
                backed_up=$((backed_up + 1))
            fi
        else
            if [ "$dry_run" -eq 1 ]; then
                printf '%s: would adopt local item into iCloud: %s\n' "$item_label" "$item_icloud"
            elif ! mv "$item_local" "$item_icloud"; then
                printf 'Error: %s: failed to move local item into iCloud: %s\n' \
                    "$item_label" "$item_icloud" >&2
                problems=$((problems + 1))
                return
            fi
            if ! ensure_dir "$(dirname "$item_local")"; then
                return
            fi
            if create_link "$item_icloud" "$item_local" "$item_label"; then
                if [ "$dry_run" -eq 1 ]; then
                    printf '%s: would adopt and link\n' "$item_label"
                else
                    printf '%s: adopted and linked\n' "$item_label"
                fi
                adopted=$((adopted + 1))
            fi
        fi
        return
    fi

    if path_exists "$item_icloud"; then
        if ! ensure_dir "$(dirname "$item_local")"; then
            return
        fi
        if create_link "$item_icloud" "$item_local" "$item_label"; then
            if [ "$dry_run" -eq 1 ]; then
                printf '%s: would link\n' "$item_label"
            else
                printf '%s: linked\n' "$item_label"
            fi
            linked=$((linked + 1))
        fi
    else
        printf '%s: missing in iCloud, skipped\n' "$item_label"
        skipped=$((skipped + 1))
        if [ "$item_required" -eq 1 ]; then
            problems=$((problems + 1))
        fi
    fi
}

copy_settings() {
    settings_local="$local_root/settings.json"
    settings_icloud="$icloud/settings.json"
    if path_exists "$settings_local"; then
        printf 'settings.json: ok (local copy kept)\n'
        ok=$((ok + 1))
        return
    fi
    if ! path_exists "$settings_icloud"; then
        printf 'settings.json: missing in iCloud, skipped\n'
        skipped=$((skipped + 1))
        return
    fi
    if ! ensure_dir "$local_root"; then
        return
    fi
    if [ "$dry_run" -eq 1 ]; then
        printf 'settings.json: would copy %s -> %s\n' "$settings_icloud" "$settings_local"
        ok=$((ok + 1))
        return
    fi
    if cp "$settings_icloud" "$settings_local"; then
        printf 'settings.json: copied\n'
        ok=$((ok + 1))
    else
        printf 'Error: settings.json: failed to copy %s -> %s\n' \
            "$settings_icloud" "$settings_local" >&2
        problems=$((problems + 1))
    fi
}

ensure_dir "$local_root"
ensure_dir "$icloud/memory"

link_item "$local_root/CLAUDE.md" "$icloud/CLAUDE.md" "CLAUDE.md" 1
link_item "$local_root/statusline.sh" "$icloud/statusline.sh" "statusline.sh" 1
link_item "$local_root/hooks" "$icloud/hooks" "hooks" 1
link_item "$local_root/skills" "$icloud/skills" "skills" 1
link_item "$local_root/agents" "$icloud/agents" "agents" 0
link_item "$memory_local" "$memory_icloud" "memory" 0

if [ "$link_settings" -eq 1 ]; then
    link_item "$local_root/settings.json" "$icloud/settings.json" "settings.json" 0
else
    copy_settings
fi

printf '\nTools check\n'
if command -v claude >/dev/null 2>&1; then
    printf 'claude: present\n'
else
    printf 'claude: missing - Claude Code command-line client.\n'
fi
if [ -f '/Applications/ChatGPT.app/Contents/Resources/codex' ]; then
    printf 'codex: present\n'
else
    printf 'codex: missing - command-line agent bundled with the ChatGPT app.\n'
fi
if command -v grok >/dev/null 2>&1 || [ -f "$home_abs/.local/bin/grok" ]; then
    printf 'grok: present\n'
else
    printf 'grok: missing - optional command-line assistant used by some workflows.\n'
fi
if command -v brew >/dev/null 2>&1 || [ -f '/opt/homebrew/bin/brew' ]; then
    printf 'brew: present\n'
else
    printf 'brew: missing - package manager for installing command-line tools.\n'
fi
if command -v python3 >/dev/null 2>&1; then
    printf 'python3: present\n'
else
    printf 'python3: missing - Python runtime used by scripts and skills.\n'
fi

print_summary
if [ "$problems" -eq 0 ]; then
    exit 0
fi
exit 1
