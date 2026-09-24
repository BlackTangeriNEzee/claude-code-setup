#!/usr/bin/env python3
"""Stop hook: block a closeout that describes work not done, hands work back, or repeats earlier points.

Patterns and the reason text live in <lang>/no-undone-restate.json next to this file.
The English set leaves handoff and permission-asking to checkpoint-guard.sh, which already covers them.
Also blocks a reply that restates the previous reply almost verbatim.
Honest blocker reports are allowed on purpose: the user's rules require them to be stated once.
"""

import json
import os
import re
import sys

from hooklib import strip_noise

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LANGS = ("zh", "en")
REPEAT_SHINGLE = 5
REPEAT_MIN_CHARS = 200
REPEAT_THRESHOLD = 0.6
REPEAT_REASON = (
    "\u4e0a\u4e00\u6761\u56de\u590d\u91cc {ratio} \u7684\u5185\u5bb9\u548c\u66f4\u65e9\u7684\u56de\u590d\u76f8\u540c\u3002"
    "\u53ea\u5199\u8fd9\u4e00\u8f6e\u65b0\u7684\u5185\u5bb9\uff0c\u4e0d\u8981\u628a\u5df2\u7ecf\u8bf4\u8fc7\u7684\u7b54\u6848\u518d\u8f93\u51fa\u4e00\u904d\u3002 "
    "{ratio} of this reply repeats the previous one. Write only what is new in this turn."
)

# Quoted spans: CJK double quotes (U+201C/U+201D), corner brackets (U+300C/U+300D), ASCII double quotes.
QUOTED = re.compile("\u201c[^\u201d\n]*\u201d|\u300c[^\u300d\n]*\u300d|\"[^\"\n]*\"")


def load_rules():
    rules = []
    for lang in LANGS:
        path = os.path.join(BASE_DIR, lang, "no-undone-restate.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        patterns = [(p["label"], re.compile(p["regex"])) for p in data["patterns"]]
        rules.append((patterns, data["reason"]))
    return rules


def assistant_texts(transcript_path, keep=2):
    texts = []
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
            content = (entry.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            parts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            texts.append("".join(parts))
    return texts[-keep:]


def shingles(text):
    packed = re.sub(r"\s+", "", text.lower())
    return {packed[i:i + REPEAT_SHINGLE] for i in range(len(packed) - REPEAT_SHINGLE + 1)}


def repeat_hit(clean_now, previous):
    if not previous or len(clean_now) < REPEAT_MIN_CHARS or len(previous) < REPEAT_MIN_CHARS:
        return None
    now = shingles(clean_now)
    before = shingles(strip_noise(previous, QUOTED))
    if not now or not before:
        return None
    ratio = len(now & before) / float(len(now))
    if ratio < REPEAT_THRESHOLD:
        return None
    return "{:.0%}".format(ratio)


def find_hits(text, patterns):
    hits = []
    for label, pattern in patterns:
        match = pattern.search(text)
        if match:
            hits.append("{} <{}>".format(label, match.group(0)))
    return hits


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("stop_hook_active"):
            return 0
        transcript_path = payload.get("transcript_path")
        texts = assistant_texts(transcript_path) if transcript_path else []
        text = payload.get("last_assistant_message") or (texts[-1] if texts else None)
        if not text:
            return 0
        if texts and texts[-1].strip() != text.strip():
            previous = texts[-1]
        else:
            previous = texts[-2] if len(texts) >= 2 else None
        clean = strip_noise(text, QUOTED)
        hits, reasons = [], []
        for patterns, reason in load_rules():
            found = find_hits(clean, patterns)
            if found:
                hits.extend(found)
                if reason not in reasons:
                    reasons.append(reason)
        reasons = [r.format(hits="; ".join(hits)) for r in reasons]
        ratio = repeat_hit(clean, previous)
        if ratio:
            reasons.append(REPEAT_REASON.format(ratio=ratio))
        if not reasons:
            return 0
        out = {
            "decision": "block",
            "reason": " ".join(reasons),
        }
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Never block because of our own failure.
        print("no-undone-restate: skipped ({}: {})".format(type(exc).__name__, exc), file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
