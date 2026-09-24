#!/usr/bin/env python3
"""PreToolUse guard for Edit/Write/MultiEdit.

Enforces user code-hygiene rules on source-code files:
- No Chinese characters or CJK punctuation (i18n zh resource files are exempt).
- No em dash (U+2014); use a plain dash.
- No emoji.

Markdown and other prose files are not checked. To exempt a legitimate case,
edit CODE_EXT / the zh-path regex below.
"""
import json
import os
import re
import sys

from hooklib import is_emoji

CODE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".scss",
    ".json", ".sql", ".sh", ".py", ".rb", ".go", ".rs",
    ".yml", ".yaml", ".toml", ".html", ".vue", ".svelte",
}

CJK_RE = re.compile(
    "[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f"
    "\uff01\uff08\uff09\uff0c\uff1a\uff1b\uff1f]"
)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    ti = data.get("tool_input", {}) or {}
    path = (ti.get("file_path") or "").replace("\\", "/")
    if "/tmp/tpl/" in path or path.endswith("_pptx.py") or path.endswith("/hooks/cn-slop-check.py"):
        sys.exit(0)
    ext = os.path.splitext(path)[1].lower()
    if ext not in CODE_EXT:
        sys.exit(0)

    # SQL data seeds and migrations carry user-facing zh strings (topic names,
    # question bodies, bank titles), so CJK is legitimate there.
    sql_data_exempt = ext == ".sql" and bool(
        re.search(r"(^|/)scratch-[^/]*\.sql$", path)
        or "/migrations/" in path
        or "/seed" in path
    )

    zh_exempt = bool(
        re.search(r"(^|/)(zh|zh-[A-Za-z]+)(/|\.[^/]*$)", path)
        or "/locales/" in path
        or "/i18n/" in path
        or sql_data_exempt
    )

    texts = []
    if ti.get("content"):
        texts.append(ti["content"])
    if ti.get("new_string"):
        texts.append(ti["new_string"])
    for e in ti.get("edits") or []:
        if isinstance(e, dict) and e.get("new_string"):
            texts.append(e["new_string"])
    text = "\n".join(texts)
    if not text:
        sys.exit(0)

    problems = []
    if not zh_exempt:
        m = CJK_RE.search(text)
        if m:
            problems.append(f"Chinese characters/CJK punctuation (first: {m.group(0)!r})")
    if "\u2014" in text:
        problems.append("em dash (U+2014); use a plain dash")
    emo = next((ch for ch in text if is_emoji(ch)), None)
    if emo:
        problems.append(f"emoji ({emo!r})")

    if problems:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "User code-hygiene rule violated in "
                            + path
                            + ": "
                            + "; ".join(problems)
                            + ". Rewrite the content without these characters "
                            "(English only in code, no emoji, plain dash). "
                            "If this file legitimately needs them, ask the user to adjust "
                            "~/.claude/hooks/check-file-content.py."
                        ),
                    }
                }
            )
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
