#!/bin/bash
# Prints the status line, and caches the quota numbers to ~/.claude/quota.json
# so the quota-check skill can read them. Reads the payload JSON from stdin.

usage_refresh_after=60
usage_refresh_retry=60
usage_refresh_timeout=20
usage_refresh_dir="$HOME/.claude/usage-refresh"
usage_refresh_stamp="$usage_refresh_dir/last-attempt"

refresh_usage() {
  local claude_bin
  claude_bin=$(command -v claude 2>/dev/null)
  if [ -z "$claude_bin" ] && [ -x "$HOME/.local/bin/claude" ]; then
    claude_bin="$HOME/.local/bin/claude"
  fi
  [ -n "$claude_bin" ] || return 127
  mkdir -p "$usage_refresh_dir" || return
  cd "$usage_refresh_dir" || return
  exec env CLAUDE_USAGE_REFRESH=1 "$claude_bin" -p "/usage" --no-session-persistence </dev/null >/dev/null 2>&1
}

fable_jq='
  .cachedUsageUtilization as $cache
  | $cache.utilization.limits[]
  | select(.kind == "weekly_scoped" and .scope.model.display_name == "Fable")
  | select(.percent != null and .resets_at != null)
  | [
      .percent,
      (.resets_at | sub("\\.[0-9]+"; "") | sub("\\+00:00$"; "Z") | fromdateiso8601),
      (($cache.fetchedAtMs // null) | if . == null then null else (. / 1000 | floor) end)
    ]
  | @tsv
'

read_fable() {
  jq -r "$fable_jq" "$HOME/.claude.json" 2>/dev/null
}

if [ "${1:-}" = "--fable" ]; then
  read_fable
  exit 0
fi

if [ "${1:-}" = "--refresh-usage" ]; then
  mkdir -p "$usage_refresh_dir" || exit 1
  touch "$usage_refresh_stamp" || exit 1
  (refresh_usage) &
  refresh_pid=$!
  (
    sleep "$usage_refresh_timeout" &
    sleep_pid=$!
    trap 'kill "$sleep_pid" 2>/dev/null; wait "$sleep_pid" 2>/dev/null; exit 0' TERM INT
    wait "$sleep_pid"
    kill "$refresh_pid" 2>/dev/null
  ) </dev/null >/dev/null 2>&1 &
  timer_pid=$!
  wait "$refresh_pid" 2>/dev/null
  refresh_status=$?
  kill "$timer_pid" 2>/dev/null
  wait "$timer_pid" 2>/dev/null
  exit "$refresh_status"
fi

input=$(cat)
cache="$HOME/.claude/quota.json"

model=$(printf '%s' "$input" | jq -r '.model.display_name // empty')

bar_width=8

bar() {
  local remain=$1 filled i out=""
  filled=$(printf '%.0f' "$(echo "$remain * $bar_width / 100" | bc -l)")
  [ "$filled" -lt 0 ] && filled=0
  [ "$filled" -gt "$bar_width" ] && filled=$bar_width
  for ((i = 0; i < bar_width; i++)); do
    if [ "$i" -lt "$filled" ]; then out="${out}█"; else out="${out}░"; fi
  done
  printf '%s' "$out"
}

color() {
  local remain=$1
  if [ "$remain" -ge 50 ]; then printf '\033[38;5;39m'
  elif [ "$remain" -ge 20 ]; then printf '\033[38;5;208m'
  else printf '\033[38;5;196m'; fi
}

render_window() {
  local label=$1 used=$2 resets=$3 remain when now diff
  remain=$(printf '%.0f' "$(echo "100 - $used" | bc -l)")
  when=""
  if [ -n "$resets" ]; then
    now=$(date +%s); diff=$(( resets - now ))
    if [ "$diff" -lt 86400 ]; then when=" ($(date -r "$resets" '+%H:%M'))"
    else when=" ($(date -r "$resets" '+%-m/%-d %H:%M'))"; fi
  fi
  printf '%s %s%s %s%%\033[0m%s' "$label" "$(color "$remain")" "$(bar "$remain")" "$remain" "$when"
}

fmt_window() {
  local label=$1 key=$2 used resets
  used=$(printf '%s' "$input" | jq -r ".rate_limits.${key}.used_percentage // empty")
  [ -z "$used" ] && return
  resets=$(printf '%s' "$input" | jq -r ".rate_limits.${key}.resets_at // empty")
  render_window "$label" "$used" "$resets"
}

parts=()
[ -n "$model" ] && parts+=("$model")
five=$(fmt_window "5h" five_hour); [ -n "$five" ] && parts+=("$five")
week=$(fmt_window "7d" seven_day); [ -n "$week" ] && parts+=("$week")
fable_data=$(read_fable)
fable_used="" fable_resets="" fable_fetched=""
if [ -n "$fable_data" ]; then
  IFS=$'\t' read -r fable_used fable_resets fable_fetched <<< "$fable_data"
  if [ -n "$fable_used" ] && [ -n "$fable_resets" ]; then
    fable=$(render_window "Fable" "$fable_used" "$fable_resets")
    if [ -n "$fable" ]; then
      if [ -n "$fable_fetched" ] && [ "$fable_fetched" != "null" ]; then
        fable_age=$(( $(date +%s) - fable_fetched ))
        if [ "$fable_age" -gt 3600 ]; then
          fable_hours=$(( fable_age / 3600 ))
          fable="${fable} ~${fable_hours}h old"
        fi
      fi
      parts+=("$fable")
    fi
  fi
fi
if [ -z "${CLAUDE_USAGE_REFRESH:-}" ]; then
  now=$(date +%s)
  refresh_due=0
  case "$fable_fetched" in
    ''|*[!0-9]*) refresh_due=1 ;;
    *) [ $(( now - fable_fetched )) -gt "$usage_refresh_after" ] && refresh_due=1 ;;
  esac
  if [ "$refresh_due" -eq 1 ]; then
    stamp_mtime=$(stat -f %m "$usage_refresh_stamp" 2>/dev/null)
    case "$stamp_mtime" in
      ''|*[!0-9]*) retry_due=1 ;;
      *)
        retry_due=0
        [ $(( now - stamp_mtime )) -ge "$usage_refresh_retry" ] && retry_due=1
        ;;
    esac
    if [ "$retry_due" -eq 1 ] && mkdir -p "$usage_refresh_dir" && touch "$usage_refresh_stamp"; then
      (
        (refresh_usage) </dev/null >/dev/null 2>&1 &
      )
    fi
  fi
fi
printf '%s' "$input" | jq -c \
'{
  model:   (.model.display_name // null),
  dir:     (.workspace.current_dir // .cwd // null),
  five_hour: .rate_limits.five_hour,
  seven_day: .rate_limits.seven_day,
  context_remaining: (.context_window.remaining_percentage // null),
  written_at: now
}' > "$cache" 2>/dev/null
ctx=$(printf '%s' "$input" | jq -r '.context_window.remaining_percentage // empty')
[ -n "$ctx" ] && parts+=("ctx $(printf '%.0f' "$ctx")%")
(IFS=$'\x1f'; joined="${parts[*]}"; printf '%s\n' "${joined//$'\x1f'/ | }")
