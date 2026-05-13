#!/usr/bin/env python3
"""Extract a compact content inventory from a LaTeX paper."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def find_braced(command: str, text: str) -> list[str]:
    pattern = re.compile(r"\\" + re.escape(command) + r"(?:\[[^\]]*\])?\{", re.S)
    results = []
    for match in pattern.finditer(text):
        start = match.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            char = text[i]
            if char == "{" and (i == 0 or text[i - 1] != "\\"):
                depth += 1
            elif char == "}" and (i == 0 or text[i - 1] != "\\"):
                depth -= 1
            i += 1
        if depth == 0:
            results.append(text[start : i - 1].strip())
    return results


def clean_latex(value: str) -> str:
    value = value.replace(r"\times", "x")
    value = re.sub(r"\\textsc\{([^{}]+)\}", r"\1", value)
    value = re.sub(r"\\textbf\{([^{}]+)\}", r"\1", value)
    value = re.sub(r"\\emph\{([^{}]+)\}", r"\1", value)
    value = re.sub(r"\\[a-zA-Z]+", "", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_tex", type=Path)
    args = parser.parse_args()

    text = strip_comments(args.paper_tex.read_text(encoding="utf-8", errors="ignore"))

    print("# Paper Inventory\n")

    titles = find_braced("title", text)
    if titles:
        print(f"Title: {clean_latex(titles[0])}\n")

    authors = [clean_latex(author) for author in find_braced("author", text)]
    if authors:
        print("Authors:")
        for author in authors:
            print(f"- {author}")
        print()

    abstracts = find_braced("abstract", text)
    if not abstracts:
        match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.S)
        abstracts = [match.group(1)] if match else []
    if abstracts:
        print("Abstract:")
        print(clean_latex(abstracts[0])[:1800])
        print()

    print("Sections:")
    for level, title in re.findall(r"\\(section|subsection)\*?\{([^{}]+)\}", text):
        prefix = "-" if level == "section" else "  -"
        print(f"{prefix} {clean_latex(title)}")
    print()

    print("Figures:")
    for fig in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", text):
        print(f"- {fig}")
    print()

    print("Captions:")
    for caption in find_braced("caption", text)[:30]:
        print(f"- {clean_latex(caption)[:260]}")
    print()

    print("Tables:")
    for caption in re.finditer(r"\\begin\{table\*?\}.*?\\caption\{(.*?)\}.*?\\end\{table\*?\}", text, re.S):
        print(f"- {clean_latex(caption.group(1))[:260]}")
    print()

    links = re.findall(r"\\href\{([^{}]+)\}\{([^{}]+)\}|\\url\{([^{}]+)\}", text)
    if links:
        print("Links:")
        for href, label, url in links:
            print(f"- {clean_latex(label) or url}: {href or url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
