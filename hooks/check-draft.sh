#!/usr/bin/env bash
# Draft check: run the Stop hooks against a candidate reply BEFORE it is printed.
# The Stop hooks fire after the terminal already showed the message, so a blocked reply
# is always visible once; checking a draft file here is what keeps the output to one copy.
set -u
[ $# -eq 1 ] || { echo "usage: check-draft.sh <draft-file>" >&2; exit 2; }
draft="$1"
[ -f "$draft" ] || { echo "no such file: $draft" >&2; exit 2; }

payload=$(python3 -c 'import json,sys; print(json.dumps({"last_assistant_message": open(sys.argv[1], encoding="utf-8").read()}))' "$draft") || exit 2

read_reason='import json,sys
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)
if isinstance(data, dict) and data.get("decision") == "block":
    print(data.get("reason", ""))'

fail=0
for hook in "no-undone-restate.py" "cn-slop-check.py" "checkpoint-guard.sh"; do
  path="$HOME/.claude/hooks/$hook"
  [ -f "$path" ] || continue
  case "$hook" in
    *.py) out=$(printf '%s' "$payload" | python3 "$path" 2>/dev/null) ;;
    *)    out=$(printf '%s' "$payload" | env -u CLAUDE_HEADLESS -u CLAUDE_CODE_CHILD_SESSION bash "$path" 2>/dev/null) ;;
  esac
  reason=$(printf '%s' "$out" | python3 -c "$read_reason")
  if [ -n "$reason" ]; then
    echo "BLOCK [$hook] $reason"
    fail=1
  fi
done

[ $fail -eq 0 ] && echo "OK"
exit $fail
