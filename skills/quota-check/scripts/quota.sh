#!/bin/bash
# Prints remaining quota and the current folder. Quota comes from
# ~/.claude/quota.json, which the status line writes on every render.
cache="$HOME/.claude/quota.json"

echo "当前文件夹 / current folder"
echo "  $(pwd)"
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) && [ -n "$branch" ] && echo "  git 分支 / branch: $branch"

if [ ! -f "$cache" ]; then
  echo
  echo "额度未知 / quota unknown: $cache 不存在。状态栏还没有跑过一次。"
  exit 0
fi

age=$(( $(date +%s) - $(jq -r '.written_at // 0' "$cache" | cut -d. -f1) ))
echo
echo "剩余额度 / quota left   (数据 ${age} 秒前写入 / cached ${age}s ago)"

show() {
  local label=$1 used=$2 resets=${3:-} fetched=${4:-} kind=${5:-quota} remain fetched_age fetched_hours note=""
  printf -v label '%-5s' "$label"
  if [ -z "$used" ]; then printf '  %s 无数据 / no data\n' "$label"; return; fi
  if [ "$kind" = "context" ]; then
    printf '  %s %.0f%% 上下文窗口剩余 / of the context window left\n' "$label" "$used"
    return
  fi
  remain=$(printf '%.0f' "$(echo "100 - $used" | bc -l)")
  if [ -n "$fetched" ]; then
    fetched_age=$(( $(date +%s) - fetched ))
    if [ "$fetched_age" -gt 3600 ]; then
      fetched_hours=$(( fetched_age / 3600 ))
      note="，数据 ${fetched_hours} 小时前；自动刷新未成功 / data ${fetched_hours}h old; automatic refresh did not succeed"
    fi
  fi
  if [ -n "$resets" ]; then
    printf '  %s %s%% 剩余，%s 重置 / %s%% left, resets %s%s\n' \
      "$label" "$remain" "$(date -r "$resets" '+%-m/%-d %H:%M')" "$remain" "$(date -r "$resets" '+%-m/%-d %H:%M')" "$note"
  else
    printf '  %s %s%% 剩余 / %s%% left%s\n' "$label" "$remain" "$remain" "$note"
  fi
}

five_used=$(jq -r '.five_hour.used_percentage // empty' "$cache")
five_resets=$(jq -r '.five_hour.resets_at // empty' "$cache")
week_used=$(jq -r '.seven_day.used_percentage // empty' "$cache")
week_resets=$(jq -r '.seven_day.resets_at // empty' "$cache")
fable_data=$("$HOME/.claude/statusline.sh" --fable)
fable_used="" fable_resets="" fable_fetched=""
if [ -n "$fable_data" ]; then
  IFS=$'\t' read -r fable_used fable_resets fable_fetched <<< "$fable_data"
fi
refresh_fable=0
if [ -z "$fable_data" ]; then
  refresh_fable=1
else
  case "$fable_fetched" in
    ''|*[!0-9]*) ;;
    *) [ $(( $(date +%s) - fable_fetched )) -gt 60 ] && refresh_fable=1 ;;
  esac
fi
if [ "$refresh_fable" -eq 1 ]; then
  "$HOME/.claude/statusline.sh" --refresh-usage >/dev/null 2>&1
  fable_data=$("$HOME/.claude/statusline.sh" --fable)
  fable_used="" fable_resets="" fable_fetched=""
  if [ -n "$fable_data" ]; then
    IFS=$'\t' read -r fable_used fable_resets fable_fetched <<< "$fable_data"
  fi
fi
show "5h" "$five_used" "$five_resets"
show "7d" "$week_used" "$week_resets"
show "Fable" "$fable_used" "$fable_resets" "$fable_fetched"
ctx=$(jq -r '.context_remaining // empty' "$cache")
[ -n "$ctx" ] && show "ctx" "$ctx" "" "" context
