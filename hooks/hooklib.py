"""Helpers shared by the hook scripts in this folder."""
import re

FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
BLOCKQUOTE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
URL = re.compile(r"(?:https?://|www\.)\S+")


def is_emoji(ch):
    o = ord(ch)
    return (
        0x1F000 <= o <= 0x1FAFF
        or 0x2600 <= o <= 0x27BF
        or 0x2B00 <= o <= 0x2BFF
        or 0x1F1E6 <= o <= 0x1F1FF
        or o == 0xFE0F
    )


def project_slug(cwd):
    return re.sub(r"[^A-Za-z0-9]+", "-", cwd or "unknown").strip("-") or "unknown"


def strip_noise(text, quoted):
    text = FENCED_CODE.sub(" ", text)
    text = INLINE_CODE.sub(" ", text)
    text = BLOCKQUOTE.sub(" ", text)
    text = URL.sub(" ", text)
    text = quoted.sub(" ", text)
    return text
