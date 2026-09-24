# Personal Claude Code Configuration

这是一套个人 Claude Code 配置，包含会把工作分派给 worker models 的 CLAUDE.md、六个 skills、一组 hooks、三个 agent 定义、一个交接模板、状态栏脚本和 Mac 安装脚本。

This repository contains a personal Claude Code configuration.

| Skill | Description |
| --- | --- |
| `fable-dispatch` | Fable delegates tasks to worker models, checks their work, and reports the result. |
| `hand` | Writes a handover file for the next session. |
| `interview-helper` | Helps students prepare for oral interviews about their own coding work. |
| `karpathy-guidelines` | Gives behavioral guidelines for simpler, safer code changes. |
| `quota-check` | Shows remaining quota, context, and the current folder. |
| `stop-slop-cn` | Removes generic, formulaic, and unnatural phrasing from Chinese text. |

| Hook | Event | Purpose |
| --- | --- | --- |
| `guard-git.py` | PreToolUse, Bash | Blocks pushes to protected branches and commit messages with prohibited attribution or punctuation. |
| `check-file-content.py` | PreToolUse, Edit / Write / MultiEdit | Blocks Chinese characters, CJK punctuation, em dashes, and emoji in source files. |
| `cn-slop-check.py` | Stop | Checks Chinese replies for listed buzzwords and formula sentences. |
| `no-undone-restate.py` | Stop | Checks replies for unfinished-work handoffs and repeated content. |
| `checkpoint-guard.sh` | Stop | Blocks open offers and permission requests for settled actions. |
| `context-watch.py` | Stop | Requests a handover when the context window reaches configured thresholds. |
| `handover-idle.py` | Stop | Arms a timer that writes a handover after an idle period. |
| `handover-load.py` | SessionStart | Loads a handover from the previous session. |
| `check-draft.sh` | Manual | Runs the three reply checks against a draft file. |
| `hooklib.py` | Imported helper | Provides shared functions used by other hooks. |

## Installation

Clone this repository, then copy or symlink the folders and files you need into `~/.claude` while keeping their relative paths.

The `setup-mac.sh` script serves a different purpose: it connects `~/.claude` to the iCloud `.claude` directory under your home folder.

It creates links for `CLAUDE.md`, `statusline.sh`, `hooks`, `skills`, `agents`, and a memory directory, while keeping an existing local `settings.json` or copying the iCloud settings file when no local copy exists.

When a local item already exists, the script adopts it into iCloud if no iCloud copy exists, or backs it up before linking if an iCloud copy already exists.

Run `bash setup-mac.sh --dry-run` to preview changes; `--link-settings` links settings instead of copying them.

`settings.json` is an example to merge into your own settings, not a file to overwrite your existing settings with.

Some skills and hooks assume Codex CLI, Grok CLI, and specific model names are available.

The `karpathy-guidelines` skill adapts material from [ponytail](https://github.com/DietrichGebert/ponytail), which is licensed under MIT, and refers to Andrej Karpathy's observations.
The ponytail copyright notice is included in `LICENSE`.

The `stop-slop-cn` skill includes its upstream MIT license and copyright notice in `skills/stop-slop-cn/LICENSE`.

## License

This repository is licensed under the MIT License. Copyright (c) 2026 Ray.
