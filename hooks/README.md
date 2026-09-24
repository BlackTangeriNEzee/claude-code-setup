# Claude Code hooks

Small guard scripts that Claude Code runs around a session.
Two run before a tool call and can refuse it; four run after a reply and can send it back to be rewritten; one more runs after a reply only to arm a timer; one runs when a session starts.
`check-draft.sh` is not wired to any event - it runs the three text-checking reply hooks against a draft by hand.

All of them are registered in `~/.claude/settings.json` under `hooks`.
This folder is a symlink into iCloud Drive, so the scripts sync across machines while `settings.json` stays local to each machine.

| Script | Event | Blocks |
|---|---|---|
| `guard-git.py` | PreToolUse, Bash | pushing to a protected branch; AI attribution, emoji, or em dash in a commit message |
| `check-file-content.py` | PreToolUse, Edit / Write / MultiEdit | Chinese characters, em dashes, emoji inside source-code files |
| `cn-slop-check.py` | Stop | Chinese buzzwords and formula sentences in the reply |
| `no-undone-restate.py` | Stop | a closeout that describes work not done, pushes work back, asks permission, or repeats earlier points |
| `checkpoint-guard.sh` | Stop | a reply that ends by handing already-decided work back to the user |
| `context-watch.py` | Stop | nothing permanently; once the context window runs low it asks for a handover file before further work |
| `handover-idle.py` | Stop | nothing; arms a background timer that writes a handover file after 10 idle minutes |
| `handover-load.py` | SessionStart | nothing; feeds the previous session's handover into a fresh one |
| `check-draft.sh` | manual | nothing by itself; reports what the three text-checking Stop hooks would say about a draft |
| `hooklib.py` | none, imported by the other scripts | nothing; holds the shared helpers `is_emoji`, `project_slug` and `strip_noise` |

## Shared design rules

**Quoting passes, using does not.**
Every reply hook strips fenced code, inline backticks, blockquotes, URLs, and quoted spans before matching.
So a reply that cites a banned phrase as an example is fine; only plain use of it counts.
The stripping is done by `strip_noise` in `hooklib.py`, and each hook passes in its own pattern for quoted spans.
`cn-slop-check.py` also strips text inside full-width parentheses; `no-undone-restate.py` does not.
That difference is deliberate: parentheses often hold real content, so the closeout check keeps reading them.

**Fail open.**
Any parse error, missing file, or missing `jq` lets the turn through.
A broken guard must never trap a session.

**No loops.**
Every Stop hook returns immediately when `stop_hook_active` is set, so the rewrite after a block is not checked again.
`checkpoint-guard.sh` goes further: on the rewrite it accepts a plain sign-off or a re-stated real question, and only a fresh open offer blocks a second time.

**Block format.**
A hook prints `{"decision": "block", "reason": "..."}` on stdout and exits 0.
The reason text is what Claude reads, so it should say what to do, not only what is wrong.

## The scripts

### guard-git.py

Reads the Bash command about to run.
Refuses a push to `main`, `master`, `dev`, `develop`, `staging`, `production`, `prod`, including an implicit push of the current branch.
Refuses a commit message containing `Co-Authored-By`, "Generated with Claude", emoji, or an em dash.

The script matches on the text of the whole Bash command, not on a parsed command.
So a command that only mentions `git commit` or `git push` together with a refused string, for example inside a test script or a search, is refused too.
This is deliberate: matching only real invocations would miss a command wrapped in quotes, such as `zsh -lc 'git push origin main'`, and a missed push is worse than a false refusal.
To get such a command through, put the text in a file, or build the string in pieces.

### check-file-content.py

Reads the text about to be written.
Refuses Chinese characters and CJK punctuation, em dashes, and emoji in source-code files.
Markdown and other prose files are skipped, and i18n `zh` resource paths are exempt.
Adjust `CODE_EXT` and the zh-path regex in the file to change the scope.

### cn-slop-check.py

Word list and sentence patterns live at the top of the script.
`BANNED_WORDS` holds high-confidence slop only; words with real technical use are deliberately absent, and there is a comment listing which ones and why.
`BANNED_PATTERNS` holds sentence shapes, each with a label shown in the block message.

### no-undone-restate.py

Patterns live in JSON next to the script, one file per language:

- `zh/no-undone-restate.json` - five rules: work not done, pushing work back, permission-asking endings, stressing lack of access, restating earlier content.
- `en/no-undone-restate.json` - three rules: work not done, restating earlier content, stressing lack of access.
  Handoff and permission-asking are absent on purpose; `checkpoint-guard.sh` already covers those forms in English.

Each file carries its own `reason` text, and a block reports in the language of the rules that fired.
English regexes need `(?i)` at the very start of the string, since Python rejects an inline flag placed later.

The Chinese handoff rule excludes `留给你` after `判断`, `决定`, or `选择`, and before `自己` plus a writing, thinking, or decision verb.
It also excludes `需要你` when optional direction, `自己`, and `做` words lead directly to a decision verb.
Those cases describe who should make a judgment or decision, not unfinished work being handed back.

The Chinese lack-of-access rule matches `我没权限`, `我没办法`, `我没法` and similar, but not when the next word is a checking verb such as `核实`, `确认`, `验证`, `查证`, `测试`, `测`, `判断`, `保证`, or `复现`.
A sentence such as `我没法核实` is an honest report that a result could not be verified, which the user's rules require, not an excuse.

The script also compares the reply with the previous reply.
It packs both into 5-character pieces and measures how many of the new reply's pieces appeared in the old one.
At 60% overlap or higher, with both replies over 200 characters, the turn is blocked.
That catches a repeated answer even when no trigger phrase is present.
Tune `REPEAT_SHINGLE`, `REPEAT_MIN_CHARS`, and `REPEAT_THRESHOLD` at the top of the file.

### checkpoint-guard.sh

Matches form, not subject: a hollow ask and a real one look identical, so the block message hands back a test instead of a correction.

Three groups, all searched across the whole message rather than only the ending:

1. Open offers - `want me to`, `up to you`, `over to you`, `say the word`, `thoughts?`. These fire anywhere. `your call` and `your move` fire only at a clause boundary, so a backward-looking use survives.
2. Permission-asking for a settled action - needs a permission phrase plus an action word such as commit, push, apply, deploy, delete.
3. Quiet deferral - `separate fix`, `noted for later`, `out of scope for now`, `until it bites`, `watch item`.

On a hit it asks whether a real gate exists: a destructive or irreversible action, a settings change the user must approve, a fork with no sensible default, or information only the user has.
If none applies, the work should be finished and reported instead.

### context-watch.py

Adds up the token usage of the newest assistant entry in the transcript, which is the current context size.
Sub-agent entries and entries from other sessions are skipped.
When the share of the window still free drops to a threshold, it blocks once and asks for a handover file.

Thresholds default to 50% and 20% left; override with `CLAUDE_CONTEXT_THRESHOLDS` (comma-separated fractions).
The window size is `CLAUDE_CONTEXT_LIMIT` when that env var is a positive integer.
Otherwise the script reads the `model` value from `<cwd>/.claude/settings.local.json`, then `<cwd>/.claude/settings.json`, then `~/.claude/settings.json`, first match wins.
A model value containing `[1m]` means 1,000,000 tokens; any other model, or none, means 200,000.
If the tokens already used exceed that settings-based limit, 1,000,000 is used instead.

Each threshold fires once per session, tracked in `~/.claude/handover/state/<session-id>.json`.
State files older than 30 days are removed on the next run.
The handover itself is written by the reply, not by the script, following `~/.claude/handover/TEMPLATE.md`, and lands at `~/.claude/handover/<project>/HANDOVER.md`.

### handover-idle.py

Writes the handover automatically when the chat has been idle for 10 minutes, so a session that is simply walked away from still leaves a handover behind.
The script has two modes.

As a Stop hook it prints nothing and returns at once, so it never blocks or delays a reply.
It records the session's working directory and transcript path in `~/.claude/handover/state/<session-id>.idle.json`.
Then it starts one detached watcher, `handover-idle.py --watch <session-id>`, unless the state file names a watcher that is still running.

The watcher sleeps until the transcript has gone untouched for the idle time.
Any new message moves the transcript's modification time, and the watcher starts counting again from there.
When the idle time is reached, it builds a prompt from `~/.claude/handover/TEMPLATE.md`, any undelivered `HANDOVER.md` for the folder (to be merged), and a condensed transcript.
The condensed transcript keeps user and assistant text, the first 300 characters of each tool result, and the last 60,000 characters overall.
A transcript under 2,000 characters after condensing is skipped.
The handover is written by a separate read-only run: `claude -p --model sonnet --tools "" --output-format text --no-session-persistence --settings '{"disableAllHooks": true}'`, with a 300-second limit.
Its output is accepted only when it contains `## 1. Goal` and `## 8. Environment notes`.
The file gets one first line saying it is an automatic handover, and it is written to `~/.claude/handover/<project>/HANDOVER.md` by the same `project_slug` rule as everything else.
A later `/hand` overwrites it with the authoritative version.
After writing, the watcher exits; the next reply starts a new one.
A watcher also exits when its state file or the transcript disappears, and after 12 hours at most.

Every step and every failure goes to `~/.claude/handover/state/idle.log`: a skipped short transcript, a missing `claude` binary, or a rejected run with its exit code and the first 500 characters of its error output.
A failed run writes nothing.

**Recursion guard.**
The nested `claude -p` run gets the env var `CLAUDE_HANDOVER_IDLE_DISABLE=1`, and the Stop hook exits at once when that var is set.
The nested run also turns all hooks off and runs in `~/.claude/handover/state`, so `handover-load.py` finds no handover to consume there.

Env overrides:

- `CLAUDE_HANDOVER_IDLE_SECONDS` - idle time in seconds, default 600.
- `CLAUDE_HANDOVER_IDLE_DISABLE` - any value turns the hook off.
- `CLAUDE_HANDOVER_CLAUDE_BIN` - path to the `claude` binary; by default it is found on `PATH`, falling back to `~/.local/bin/claude`.

To turn the feature off for good, remove the `handover-idle.py` entry from the `Stop` list in `~/.claude/settings.json`.
To stop a running watcher, end the `handover-idle.py --watch` process, or move its state file out of `~/.claude/handover/state/`.

### handover-load.py

Runs when a session starts. Skips a resumed session, which still has its context.
Looks for `~/.claude/handover/<project>/HANDOVER.md`, where `<project>` is the working directory with non-alphanumeric characters turned into dashes.

If the file exists and is newer than 30 days, its text is injected as extra context and the file is moved to `archive/HANDOVER-<timestamp>.md`.
The move is what keeps a handover from being delivered twice.
If that file is missing, empty, or too old, the hook looks for `HANDOVER.md` directly in the session working directory and injects it when it is non-empty and within the same age window.
The project-folder file is left in place and is not changed.
Resumed sessions skip both locations, while compacted sessions still check the automatic location but skip the project-folder fallback.
Override the age window with `CLAUDE_HANDOVER_MAX_AGE_DAYS`.

Full loop: context runs low, `context-watch.py` blocks and asks for the handover, the reply writes it and says so, the user types `/clear`, `handover-load.py` gives the new session the file, work continues.
`handover-idle.py` starts the same loop after 10 idle minutes without asking.
The user can also start the loop on demand: typing `/hand` runs the `hand` skill in `~/.claude/skills/hand/`, which writes the same file at the same path, computed with `project_slug` from `hooklib.py` so the write path always matches the read path.
Because a handover is no longer written only when context runs low, the text this hook injects says when the handover was written and not why.

### check-draft.sh

    ~/.claude/hooks/check-draft.sh <draft-file>

Wraps the file as `{"last_assistant_message": ...}` and feeds it to the three Stop hooks.
Prints `OK` and exits 0, or prints one `BLOCK [hook] reason` line per hit and exits 1.

A Stop hook fires after the terminal has already drawn the message, so a blocked reply stays visible.
The block reasons therefore ask for a short correction of the flagged sentences, not a rewrite of the whole reply, so the answer is not printed twice.
Checking a draft before sending avoids even the correction.
The pre-check rule in `~/.claude/CLAUDE.md` (Communication style) asks for exactly that.

## Testing a change

Feed a payload straight into the hook:

    echo '{"last_assistant_message": "text to test"}' | python3 ~/.claude/hooks/no-undone-restate.py

Empty output means pass; a JSON block object means the reply would be refused.
For the repeat check, write a small JSONL file with two `{"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}` lines and pass `{"transcript_path": "..."}` instead.
For `checkpoint-guard.sh`, clear `CLAUDE_HEADLESS` and `CLAUDE_CODE_CHILD_SESSION` first, since it exits early in a nested or background run.
