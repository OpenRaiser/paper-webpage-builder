#!/usr/bin/env python3
"""Check local asset references in a generated single-page webpage."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


ATTR_RE = re.compile(r"""(?:src|href|data-figure)=["']([^"']+)["']""")


def is_local(value: str) -> bool:
    if value.startswith(("#", "mailto:", "tel:", "javascript:")):
        return False
    parsed = urlparse(value)
    return not parsed.scheme and not parsed.netloc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    args = parser.parse_args()

    html_path = args.html.resolve()
    root = html_path.parent
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    missing: list[str] = []

    for raw in sorted(set(ATTR_RE.findall(text))):
        if "${" in raw or not is_local(raw):
            continue
        path_part = unquote(raw.split("#", 1)[0].split("?", 1)[0])
        if not path_part:
            continue
        target = (root / path_part).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        if not target.exists():
            missing.append(raw)

    if missing:
        print("Missing local assets:")
        for item in missing:
            print(f"- {item}")
        return 1

    print("All local assets referenced by src/href/data-figure exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
