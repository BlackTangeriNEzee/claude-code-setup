#!/usr/bin/env python3
"""Stop hook: warn when the session context runs low and ask for a handover file.

Reads token usage from the transcript, compares it with the context limit, and blocks once per
threshold so the reply writes ~/.claude/handover/<project>/HANDOVER.md and tells the user to
run /clear. handover-load.py feeds that file into the next session.

The context limit is CLAUDE_CONTEXT_LIMIT when that env var is a positive integer. Otherwise the
"model" string is read from <cwd>/.claude/settings.local.json, then <cwd>/.claude/settings.json,
then ~/.claude/settings.json (first match). A value containing [1m] means 1,000,000 tokens; any
other model, or no model, means 200,000. If used tokens already exceed that settings-based limit,
1,000,000 is used instead.

Env overrides: CLAUDE_CONTEXT_LIMIT (tokens), CLAUDE_CONTEXT_THRESHOLDS (fractions left).
"""

import json
import os
import sys
import time

from hooklib import project_slug

HOME = os.path.expanduser("~")
HANDOVER_ROOT = os.path.join(HOME, ".claude", "handover")
STATE_DIR = os.path.join(HANDOVER_ROOT, "state")
TEMPLATE = os.path.join(HANDOVER_ROOT, "TEMPLATE.md")
LIMIT_1M = 1000000
LIMIT_200K = 200000
DEFAULT_THRESHOLDS = "0.5,0.2"
STATE_MAX_AGE = 30 * 86400
NOTICE_FRESH_SECONDS = 300
NOTICE = (
    "Handover saved: {path}\n"
    "Type /clear - press Tab to complete it, Enter to run it. The next session loads the handover."
)
USAGE_KEYS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)

REASON = (
    "Context check: about {left:.0%} of the window is left ({used:,} of {limit:,} tokens). "
    "Before anything else, write the handover at {path} following the outline in {template}: "
    "goal, what is finished, what is in flight, files touched, decisions and why, next steps, open questions. "
    "Write enough that someone starting cold can continue without this transcript. "
    "Then tell the user in one short message that the handover is saved and that typing /clear, completed with "
    "Tab, starts a fresh session which loads it automatically. Start no new work in this turn."
)


def context_limit(cwd, used):
    try:
        value = int(os.environ.get("CLAUDE_CONTEXT_LIMIT", "").strip())
    except ValueError:
        value = 0
    if value > 0:
        return value

    model = None
    for path in (
        os.path.join(cwd or "", ".claude", "settings.local.json"),
        os.path.join(cwd or "", ".claude", "settings.json"),
        os.path.join(HOME, ".claude", "settings.json"),
    ):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        found = data.get("model")
        if isinstance(found, str) and found:
            model = found
            break

    if model and "[1m]" in model.lower():
        limit = LIMIT_1M
    else:
        limit = LIMIT_200K
    if used > limit:
        return LIMIT_1M
    return limit


def thresholds():
    found = []
    for part in os.environ.get("CLAUDE_CONTEXT_THRESHOLDS", DEFAULT_THRESHOLDS).split(","):
        try:
            value = float(part)
        except ValueError:
            continue
        if 0 < value < 1:
            found.append(value)
    return sorted(found, reverse=True) or [0.5]


def used_tokens(transcript_path, session_id):
    used = 0
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "assistant":
                continue
            if entry.get("isSidechain"):
                continue
            if session_id and entry.get("sessionId") and entry["sessionId"] != session_id:
                continue
            usage = (entry.get("message") or {}).get("usage") or {}
            total = sum(int(usage.get(key) or 0) for key in USAGE_KEYS)
            if total:
                used = total
    return used


def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [float(v) for v in data.get("fired", [])]
    except Exception:
        return []


def save_state(path, fired):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"fired": fired, "updated": time.time()}, f)


def prune_state():
    cutoff = time.time() - STATE_MAX_AGE
    for name in os.listdir(STATE_DIR):
        path = os.path.join(STATE_DIR, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def clear_notice(payload):
    """Remind the user to type /clear, once per session, only after a fresh handover was written."""
    cwd = payload.get("cwd") or os.getcwd()
    handover_path = os.path.join(HANDOVER_ROOT, project_slug(cwd), "HANDOVER.md")
    if not os.path.isfile(handover_path):
        return None
    if time.time() - os.path.getmtime(handover_path) > NOTICE_FRESH_SECONDS:
        return None
    os.makedirs(STATE_DIR, exist_ok=True)
    marker = os.path.join(STATE_DIR, "{}.notice".format(payload.get("session_id") or "unknown"))
    if os.path.exists(marker):
        return None
    with open(marker, "w") as f:
        f.write("")
    return NOTICE.format(path=handover_path)


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("stop_hook_active"):
            notice = clear_notice(payload)
            if notice:
                print(json.dumps({"systemMessage": notice}, ensure_ascii=False))
            return 0
        transcript_path = payload.get("transcript_path")
        if not transcript_path or not os.path.isfile(transcript_path):
            return 0
        session_id = payload.get("session_id") or ""
        used = used_tokens(transcript_path, session_id)
        if not used:
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        limit = context_limit(cwd, used)
        left = 1.0 - (used / float(limit))
        crossed = [t for t in thresholds() if left <= t]
        if not crossed:
            return 0

        os.makedirs(STATE_DIR, exist_ok=True)
        prune_state()
        state_path = os.path.join(STATE_DIR, "{}.json".format(session_id or "unknown"))
        fired = load_state(state_path)
        pending = [t for t in crossed if t not in fired]
        if not pending:
            return 0

        handover_dir = os.path.join(HANDOVER_ROOT, project_slug(cwd))
        os.makedirs(handover_dir, exist_ok=True)
        handover_path = os.path.join(handover_dir, "HANDOVER.md")

        save_state(state_path, sorted(set(fired + pending), reverse=True))
        out = {
            "decision": "block",
            "reason": REASON.format(
                left=max(left, 0.0),
                used=used,
                limit=limit,
                path=handover_path,
                template=TEMPLATE,
            ),
        }
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as exc:
        print("context-watch: skipped ({}: {})".format(type(exc).__name__, exc), file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
