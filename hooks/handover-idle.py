#!/usr/bin/env python3
"""Stop hook: arm a detached watcher that writes an automatic handover after the chat sits idle."""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from hooklib import project_slug

HOME = os.path.expanduser("~")
HANDOVER_ROOT = os.path.join(HOME, ".claude", "handover")
STATE_DIR = os.path.join(HANDOVER_ROOT, "state")
TEMPLATE = os.path.join(HANDOVER_ROOT, "TEMPLATE.md")
LOG_PATH = os.path.join(STATE_DIR, "idle.log")
DISABLE_ENV = "CLAUDE_HANDOVER_IDLE_DISABLE"
DEFAULT_IDLE_SECONDS = 600
MAX_WATCH_SECONDS = 12 * 3600
TRANSCRIPT_TAIL_CHARS = 60000
MIN_TRANSCRIPT_CHARS = 2000
TOOL_RESULT_CHARS = 300
CLAUDE_TIMEOUT = 300
STDERR_CHARS = 500
REQUIRED_HEADINGS = ("## 1. Goal", "## 8. Environment notes")
SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
FIRST_LINE = (
    "Automatic handover written by handover-idle.py at {when} after {minutes} idle minutes; "
    "a /hand handover replaces it."
)

PROMPT = """You are writing a handover file for a Claude Code session that has gone idle.
The reader starts with no memory of the session and cannot see the transcript.
The session worked in this folder: {cwd}

Follow this outline section by section and keep every heading exactly as written, numbers included:

<outline>
{template}
</outline>
{existing}
Below is a condensed transcript of the session: user and assistant messages, tool results cut to {tool_chars} characters, oldest parts dropped.

<transcript>
{transcript}
</transcript>

Rules:
- Name real file paths and real commands, not descriptions of them.
- Say plainly what was verified and what was not.
- A section with nothing in it gets one sentence saying so. Do not delete it.
- Each full sentence on its own line.
- English only, no emoji, never an em dash, plain dash only.
- Output only the Markdown content of the file, starting with the line "# Handover". No text before it and no text after the last section.
"""

EXISTING = """
An earlier handover for this folder was never delivered. Merge it into the new file: keep what is still true, update what changed, drop what is no longer true.

<earlier_handover>
{text}
</earlier_handover>
"""


def log(message):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("{} [{}] {}\n".format(stamp, os.getpid(), message))
    except Exception:
        pass


def state_path(session_id):
    return os.path.join(STATE_DIR, "{}.idle.json".format(session_id))


def load_state(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def write_atomic(path, text):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_state(path, data):
    write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def watcher_alive(pid, session_id):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        timeout=5,
    )
    command = result.stdout
    return "handover-idle.py" in command and "--watch" in command and session_id in command


def stop_mode():
    if os.environ.get(DISABLE_ENV):
        return 0
    payload = json.load(sys.stdin)
    session_id = payload.get("session_id") or ""
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return 0
    if not SESSION_ID.match(session_id):
        log("stop: refused session id {!r}".format(session_id))
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    os.makedirs(STATE_DIR, exist_ok=True)
    path = state_path(session_id)
    try:
        state = load_state(path)
    except FileNotFoundError:
        state = {}
    state["cwd"] = cwd
    state["transcript_path"] = transcript_path
    if watcher_alive(state.get("watcher_pid"), session_id):
        save_state(path, state)
        return 0
    save_state(path, state)
    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--watch", session_id],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            close_fds=True,
            start_new_session=True,
        )
    state["watcher_pid"] = proc.pid
    save_state(path, state)
    log("stop: session {} armed watcher pid {}".format(session_id, proc.pid))
    return 0


def idle_seconds():
    raw = os.environ.get("CLAUDE_HANDOVER_IDLE_SECONDS", "")
    try:
        value = float(raw) if raw.strip() else DEFAULT_IDLE_SECONDS
    except ValueError:
        log("watch: bad CLAUDE_HANDOVER_IDLE_SECONDS {!r}, using {}".format(raw, DEFAULT_IDLE_SECONDS))
        value = DEFAULT_IDLE_SECONDS
    return value if value > 0 else DEFAULT_IDLE_SECONDS


def block_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def condense_transcript(transcript_path):
    lines = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or entry.get("isSidechain") or entry.get("isMeta"):
                continue
            kind = entry.get("type")
            if kind not in ("user", "assistant"):
                continue
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, str):
                blocks = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                blocks = content
            else:
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = (block.get("text") or "").strip()
                    if text:
                        lines.append("{}: {}".format(kind, text))
                elif block.get("type") == "tool_result" and kind == "user":
                    text = block_text(block.get("content")).strip()[:TOOL_RESULT_CHARS]
                    if text:
                        lines.append("user: [tool result] {}".format(text))
    return "\n".join(lines)[-TRANSCRIPT_TAIL_CHARS:]


def claude_binary():
    override = os.environ.get("CLAUDE_HANDOVER_CLAUDE_BIN")
    if override:
        return override
    return shutil.which("claude") or os.path.join(HOME, ".local", "bin", "claude")


def generate(session_id, state, threshold):
    cwd = state.get("cwd") or ""
    slug = project_slug(cwd)
    target = os.path.join(HANDOVER_ROOT, slug, "HANDOVER.md")
    transcript = condense_transcript(state["transcript_path"])
    if len(transcript) < MIN_TRANSCRIPT_CHARS:
        log("watch: session {} skipped, condensed transcript is {} characters (minimum {})".format(
            session_id, len(transcript), MIN_TRANSCRIPT_CHARS))
        return False
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read().strip()
    existing = ""
    if os.path.isfile(target):
        with open(target, "r", encoding="utf-8") as f:
            earlier = f.read().strip()
        if earlier:
            existing = EXISTING.format(text=earlier)
    prompt = PROMPT.format(
        cwd=cwd,
        template=template,
        existing=existing,
        tool_chars=TOOL_RESULT_CHARS,
        transcript=transcript,
    )
    env = dict(os.environ)
    env[DISABLE_ENV] = "1"
    binary = claude_binary()
    command = [
        binary, "-p",
        "--model", "sonnet",
        "--tools", "",
        "--output-format", "text",
        "--no-session-persistence",
        "--settings", json.dumps({"disableAllHooks": True}),
    ]
    started = time.time()
    try:
        result = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=STATE_DIR,
            env=env,
            timeout=CLAUDE_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log("watch: session {} claude run failed after {:.0f}s ({}: {}), nothing written".format(
            session_id, time.time() - started, type(exc).__name__, exc))
        return False
    elapsed = time.time() - started
    output = (result.stdout or "").strip()
    if result.returncode != 0 or not output or not all(h in output for h in REQUIRED_HEADINGS):
        log("watch: session {} claude run rejected after {:.0f}s (exit code {}, {} output characters), "
            "nothing written; stderr: {!r}".format(
                session_id, elapsed, result.returncode, len(output), (result.stderr or "")[:STDERR_CHARS]))
        return False
    when = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    minutes = "{:g}".format(round(threshold / 60.0, 1))
    header = FIRST_LINE.format(when=when, minutes=minutes)
    write_atomic(target, header + "\n\n" + output + "\n")
    log("watch: session {} wrote {} after a {:.0f}s claude run".format(session_id, target, elapsed))
    return True


def watch_mode(session_id):
    threshold = idle_seconds()
    path = state_path(session_id)
    deadline = time.time() + MAX_WATCH_SECONDS
    armed_for = None
    log("watch: session {} started, idle threshold {:g}s".format(session_id, threshold))
    while True:
        if not os.path.isfile(path):
            log("watch: session {} state file gone, exiting".format(session_id))
            return 0
        state = load_state(path)
        transcript_path = state.get("transcript_path")
        if not transcript_path or not os.path.isfile(transcript_path):
            log("watch: session {} transcript gone, exiting".format(session_id))
            return 0
        mtime = os.path.getmtime(transcript_path)
        now = time.time()
        if now >= deadline:
            log("watch: session {} reached the 12 hour limit, exiting".format(session_id))
            return 0
        wake = mtime + threshold
        if now < wake:
            if armed_for is not None and armed_for != mtime:
                log("watch: session {} transcript changed, re-armed until {}".format(
                    session_id, time.strftime("%H:%M:%S", time.localtime(wake))))
            armed_for = mtime
            time.sleep(max(min(wake, deadline) - now, 0.05))
            continue
        if state.get("last_written_mtime") == mtime:
            log("watch: session {} handover already written for this transcript state, exiting".format(session_id))
            return 0
        if not generate(session_id, state, threshold):
            return 0
        state = load_state(path)
        state["last_written_mtime"] = mtime
        save_state(path, state)
        armed_for = mtime


def main():
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "--watch":
            return watch_mode(sys.argv[2])
        return stop_mode()
    except Exception as exc:
        log("{}: {}: {}".format("watch" if "--watch" in sys.argv else "stop", type(exc).__name__, exc))
        return 0


if __name__ == "__main__":
    sys.exit(main())
