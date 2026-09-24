---
name: quota-check
description: 查看还剩多少额度，以及当前在哪个文件夹。Shows how much of the 5-hour, 7-day and Fable weekly quota is left, how much of the context window is left, and which folder the session is working in. Use when the user asks about 额度, 还剩多少, quota, usage limit, how much is left, when the limit resets, or which folder they are in.
---

# Quota check

Run the script and show its output to the user as it is:

```bash
bash ~/.claude/skills/quota-check/scripts/quota.sh
```

It prints the current folder, the git branch when there is one, and the
remaining 5-hour quota, 7-day quota, Fable weekly quota and context window.

## Where the numbers come from

Claude Code hands the 5-hour and 7-day quota numbers to the status line command.
`~/.claude/statusline.sh` writes them to `~/.claude/quota.json` every time it
renders, and this skill reads that file.

The Fable weekly quota does not come from the status line payload. It comes from a cache in `~/.claude.json`.
The status line refreshes that cache in the background every minute by running `claude -p "/usage"`.
This skill also refreshes it on demand when it is over a minute old, so the Fable row is normally current.
The age note appears only when an automatic refresh failed.

Two consequences to tell the user about when they matter:

- The numbers are as fresh as the last status line render, and the script
  prints that age in seconds. A few seconds old is normal.
- If `~/.claude/quota.json` is missing, the status line has never run. Check
  that `statusLine` is set in `~/.claude/settings.json` and points at
  `$HOME/.claude/statusline.sh`.
