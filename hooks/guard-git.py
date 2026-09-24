#!/usr/bin/env python3
"""PreToolUse guard for Bash git commands.

Enforces user rules that dcg does not cover:
- No direct push to protected branches (main/master/dev/develop/staging/production/prod),
  including implicit push of the current branch.
- No AI attribution (Co-Authored-By / "Generated with Claude") in commit messages.
- No emoji or em dash in commit messages.
"""
import json
import re
import subprocess
import sys

from hooklib import is_emoji

PROTECTED = {"main", "master", "dev", "develop", "staging", "production", "prod"}


def deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = data.get("tool_input", {}).get("command", "") or ""
    cwd = data.get("cwd") or "."

    if re.search(r"\bgit\b[^\n;|&]*\bcommit\b", cmd):
        if re.search(r"co-authored-by", cmd, re.I):
            deny(
                "User rule: commit messages must not include Co-Authored-By or any AI attribution. "
                "Rewrite the commit command without it."
            )
        if re.search(r"generated with[^\n\"']*claude", cmd, re.I):
            deny("User rule: commit messages must not include AI attribution.")
        if "\u2014" in cmd:
            deny("User rule: no em dash (U+2014) in commit messages; use a plain dash.")
        emo = next((ch for ch in cmd if is_emoji(ch)), None)
        if emo:
            deny(f"User rule: no emoji in commit messages (found {emo!r}).")

    for m in re.finditer(r"\bgit\s+((?:-[^\s]+\s+)*)push\b([^;|&\n]*)", cmd):
        rest = m.group(2)
        toks = rest.split()
        if "--dry-run" in toks or "-n" in toks:
            continue
        args = []
        skip = False
        for t in toks:
            if skip:
                skip = False
                continue
            if t.startswith("-"):
                if t in ("-o", "--push-option", "--receive-pack", "--exec", "--repo"):
                    skip = True
                continue
            args.append(t)
        refspecs = args[1:] if len(args) > 1 else []
        if refspecs:
            for r in refspecs:
                target = r.split(":")[-1].lstrip("+")
                name = target.split("/")[-1]
                if name in PROTECTED:
                    deny(
                        f"User rule: never push directly to protected branch '{name}'. "
                        "Push a feature branch and open a PR instead."
                    )
        else:
            try:
                br = subprocess.run(
                    ["git", "-C", cwd, "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()
            except Exception:
                br = ""
            if br in PROTECTED:
                deny(
                    f"User rule: current branch '{br}' is protected; pushing it directly is not allowed. "
                    "Create a feature branch first."
                )
    sys.exit(0)


if __name__ == "__main__":
    main()
