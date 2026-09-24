#!/usr/bin/env python3
"""Stop hook: block Chinese AI-slop buzzwords and formula sentences in the last assistant reply."""

import json
import re
import sys

from hooklib import strip_noise

# High-confidence slop only. These are deliberately excluded because they have
# legitimate technical uses: 对齐, 落地, 生态, 沉淀, 洞察, 壁垒, 场景, 价值.
BANNED_WORDS = [
    "赋能", "抓手", "闭环", "链路", "打法", "组合拳", "提效", "颗粒度",
    "心智占领", "值得注意的是", "不可否认", "众所周知", "归根结底",
    "毋庸置疑", "意义重大", "影响深远", "值得深思", "前景广阔",
    "潜力巨大", "在当今", "信息爆炸的时代", "进行一个", "做出一个",
    "赋予了", "不难发现",
]

BANNED_PATTERNS = [
    ("句式:不是...而是", re.compile(r"不是[^，。,]{1,14}，而是")),
    ("句式:表面...本质", re.compile(r"表面[上是][^，。,]{0,12}，?本质")),
    ("句式:为什么...因为", re.compile(r"为什么[^？?]{0,20}[？?]因为")),
]

# Quoted spans, so a reply that cites a banned word as an example passes.
QUOTED = re.compile("\u201c[^\u201d\n]*\u201d|\u300c[^\u300d\n]*\u300d|\uff08[^\uff09\n]*\uff09|\"[^\"\n]*\"")

REASON_TEMPLATE = (
    "中文黑话/AI 腔检查未通过，检测到: {hits}。"
    "上一条回复已经显示在屏幕上，不要整篇重发。"
    "只发一条简短的更正：把含这些词或句式的那几句换成具体、直接的表达，其余内容不要重复"
    "（规则见 ~/.claude/skills/stop-slop-cn）。"
)


def last_assistant_text(transcript_path):
    text = None
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
            text = "".join(parts)
    return text


def find_hits(text):
    hits = []
    for word in BANNED_WORDS:
        if word in text and word not in hits:
            hits.append(word)
    for label, pattern in BANNED_PATTERNS:
        if pattern.search(text) and label not in hits:
            hits.append(label)
    return hits


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("stop_hook_active"):
            return 0
        text = payload.get("last_assistant_message")
        if not text:
            transcript_path = payload.get("transcript_path")
            if not transcript_path:
                return 0
            text = last_assistant_text(transcript_path)
        if not text:
            return 0
        hits = find_hits(strip_noise(text, QUOTED))
        if not hits:
            return 0
        out = {
            "decision": "block",
            "reason": REASON_TEMPLATE.format(hits=", ".join(hits)),
        }
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Never block because of our own failure.
        print("cn-slop-check: skipped ({}: {})".format(type(exc).__name__, exc), file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
