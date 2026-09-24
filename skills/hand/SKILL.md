---
name: hand
description: 结束当前聊天前生成交接文件。Writes the handover file that the next new session in this folder loads automatically. The user invokes it with /hand.
disable-model-invocation: true
---

# Hand over before ending the chat

Write the handover yourself, now, in this turn. Do not dispatch it
to a worker or a subagent: only the session model holds the
conversation. This is the user's standing instruction and it holds
in a Fable dispatch session too, where the handover counts with the
memory files and the final report as work the session model writes.

Finish or stop any in-flight worker task first and record its state
in the handover. Start no new work in this turn.

## 1. Compute the path

Use the session's primary working directory from the environment
information at the start of the session, not the shell's current
directory. Keep it in double quotes; it may contain spaces.

```bash
python3 -c "import os, sys; sys.path.insert(0, os.path.expanduser('~/.claude/hooks')); from hooklib import project_slug; print(os.path.join(os.path.expanduser('~/.claude/handover'), project_slug(sys.argv[1]), 'HANDOVER.md'))" "<primary working directory>"
```

Never derive the folder name by hand. Create the parent folder if it
is missing:

```bash
mkdir -p "<folder part of the computed path>"
```

## 2. Merge an undelivered handover

If a `HANDOVER.md` already exists at that path, it was never
delivered. Read it, keep what is still true, and fold it into the
new text. Do not overwrite it blindly.

## 3. Write the file

Read `~/.claude/handover/TEMPLATE.md` and follow its outline
section by section. Requirements:

- Written for a reader with no memory of this session and no
  transcript.
- Real file paths and real commands, not descriptions of them.
- Say plainly what was verified and what was not.
- Each full sentence on its own line.
- English, no emoji, never an em dash, plain dash only.
- A section with nothing in it gets one sentence saying so. Do not
  delete it.

## 4. Verify

```bash
ls -l "<computed path>"
```

The file must exist and be non-empty.

## 5. Tell the user

Two or three short plain sentences in Chinese: the handover is
saved (path in backticks), they can quit now, and the next new
session opened in this same folder loads it automatically, while a
resumed session still has its context and will not load it. No
question at the end, no offer of more help.

## Automatic handover

An automatic handover is also written by the `handover-idle.py` hook after 10 idle minutes, and its first line says so.
`/hand` still produces the authoritative handover and overwrites it, folding in anything still true as step 2 says.
