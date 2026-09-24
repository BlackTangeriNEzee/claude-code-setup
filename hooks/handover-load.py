#!/usr/bin/env python3
"""SessionStart hook: hand the previous session's HANDOVER.md to a fresh session.

Looks for ~/.claude/handover/<project>/HANDOVER.md, injects it as extra context, then archives
it so the same handover is delivered once. If that file is not delivered, falls back to a fresh,
non-empty HANDOVER.md in the project folder and leaves it in place. Skips a resumed session, which
still has its context, and skips the project fallback for a compacted session.

Env overrides: CLAUDE_HANDOVER_MAX_AGE_DAYS.
"""

import json
import os
import sys
import time

from hooklib import project_slug

HOME = os.path.expanduser("~")
HANDOVER_ROOT = os.path.join(HOME, ".claude", "handover")
DEFAULT_MAX_AGE_DAYS = 30
SKIP_SOURCES = {"resume"}

HEADER = (
    "Handover from the previous session in this folder, written {age} ago.\n"
    "Continue that work from where it stopped. The file has been archived to {archive}.\n\n"
)
PROJECT_HEADER = (
    "This handover file was found in the project folder at {path}, last edited {age} ago.\n"
    "Treat it as the recorded state of earlier work in this folder. The file was left in place.\n\n"
)


def max_age_seconds():
    try:
        days = float(os.environ.get("CLAUDE_HANDOVER_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS))
    except ValueError:
        days = DEFAULT_MAX_AGE_DAYS
    return max(days, 0) * 86400


def describe_age(seconds):
    if seconds < 3600:
        return "{:.0f} minutes".format(max(seconds / 60, 1))
    if seconds < 86400:
        return "{:.0f} hours".format(seconds / 3600)
    return "{:.0f} days".format(seconds / 86400)


def read_candidate(path):
    if not os.path.isfile(path):
        return None
    age = time.time() - os.path.getmtime(path)
    if age > max_age_seconds():
        return None
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return None
    return text, age


def emit_context(context):
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(out, ensure_ascii=False))


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("source") in SKIP_SOURCES:
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        handover_dir = os.path.join(HANDOVER_ROOT, project_slug(cwd))
        path = os.path.join(handover_dir, "HANDOVER.md")
        candidate = read_candidate(path)
        if candidate:
            text, age = candidate
            archive_dir = os.path.join(handover_dir, "archive")
            os.makedirs(archive_dir, exist_ok=True)
            archive = os.path.join(
                archive_dir, "HANDOVER-{}.md".format(time.strftime("%Y%m%d-%H%M%S"))
            )
            os.replace(path, archive)
            emit_context(HEADER.format(age=describe_age(age), archive=archive) + text)
            return 0

        if payload.get("source") == "compact":
            return 0
        project_path = os.path.join(cwd, "HANDOVER.md")
        candidate = read_candidate(project_path)
        if candidate:
            text, age = candidate
            emit_context(PROJECT_HEADER.format(path=project_path, age=describe_age(age)) + text)
        return 0
    except Exception as exc:
        print("handover-load: skipped ({}: {})".format(type(exc).__name__, exc), file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
