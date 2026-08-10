#!/usr/bin/env python3
"""Split a Codex result into iMessage-sized, NUL-delimited chunks."""

from __future__ import annotations

import os
import sys


def split_text(text: str, size: int) -> list[str]:
    """Split without deleting any whitespace from the original message."""
    if len(text) <= size:
        return [text]

    parts: list[str] = []
    rest = text
    while len(rest) > size:
        paragraph = rest.rfind("\n\n", 0, size + 1)
        line = rest.rfind("\n", 0, size + 1)
        space = rest.rfind(" ", 0, size + 1)

        if paragraph >= size // 2 and paragraph + 2 <= size:
            cut = paragraph + 2
        elif line >= size // 2:
            cut = line + 1
        elif space >= size // 2:
            cut = space + 1
        else:
            cut = size

        parts.append(rest[:cut])
        rest = rest[cut:]

    parts.append(rest)
    return parts


def render_chunks(text: str, size: int, maximum: int) -> list[str]:
    parts = split_text(text, max(1, size))
    truncated = len(parts) > max(1, maximum)
    parts = parts[: max(1, maximum)]
    total = len(parts)

    rendered = []
    for index, part in enumerate(parts, 1):
        prefix = f"({index}/{total}) " if total > 1 else ""
        suffix = "\n\n…结果过长，后续内容已省略" if truncated and index == total else ""
        rendered.append(prefix + part + suffix)
    return rendered


def main() -> None:
    text = sys.stdin.read()
    size = int(os.environ.get("CHUNK_SIZE", "1200"))
    maximum = int(os.environ.get("MAX_CHUNKS", "20"))
    for chunk in render_chunks(text, size, maximum):
        sys.stdout.write(chunk + "\0")


if __name__ == "__main__":
    main()
