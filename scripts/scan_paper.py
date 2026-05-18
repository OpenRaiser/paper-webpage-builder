#!/usr/bin/env python3
"""Extract a compact content inventory from a LaTeX paper.

Multi-file projects are supported: `\\input{...}` and `\\include{...}`
references inside the root .tex are read recursively (depth-limited) so
sectioned papers (`main.tex` + `sections/*.tex`) produce a complete
inventory.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{([^{}]+)\}")
MAX_INCLUDE_DEPTH = 6


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def read_text_with_warning(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(
            f"warning: {path} is not utf-8, decoded as latin-1 (some characters may be replaced)",
            file=sys.stderr,
        )
        return path.read_text(encoding="latin-1", errors="replace")


def read_with_inputs(root: Path) -> str:
    """Concatenate root tex with \\input/\\include children (depth-first)."""
    visited: set[Path] = set()
    chunks: list[str] = []

    def load(path: Path, depth: int) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in visited or depth > MAX_INCLUDE_DEPTH or not resolved.is_file():
            return
        visited.add(resolved)
        text = strip_comments(read_text_with_warning(resolved))
        chunks.append(f"%%% file: {resolved}\n{text}")
        for match in INPUT_RE.finditer(text):
            ref = match.group(1).strip()
            if not ref:
                continue
            candidate = resolved.parent / ref
            if candidate.suffix == "":
                candidate = candidate.with_suffix(".tex")
            load(candidate, depth + 1)

    load(root, 0)
    return "\n\n".join(chunks)


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


def approx_table_rows(table_body: str) -> int:
    """Return a rough count of data rows in a LaTeX table body."""
    tabular = re.search(
        r"\\begin\{(?:tabular|tabularx|array)\}(?:\{[^{}]*\}){1,2}(.*?)\\end\{(?:tabular|tabularx|array)\}",
        table_body,
        re.S,
    )
    if not tabular:
        return 0
    body = re.sub(r"\\(?:toprule|midrule|bottomrule|hline|cline\{[^{}]*\})", "", tabular.group(1))
    rows = [row for row in re.split(r"\\\\", body) if "&" in row and clean_latex(row)]
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_tex", type=Path)
    args = parser.parse_args()

    if not args.paper_tex.is_file():
        print(f"error: not a file: {args.paper_tex}", file=sys.stderr)
        return 2

    text = read_with_inputs(args.paper_tex)

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
    table_pattern = re.compile(r"\\begin\{(table\*?)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}", re.S)
    found_tables = False
    for index, table in enumerate(table_pattern.finditer(text), 1):
        found_tables = True
        body = table.group(2)
        captions = find_braced("caption", body)
        labels = find_braced("label", body)
        caption = clean_latex(captions[0])[:260] if captions else "(no caption)"
        label = clean_latex(labels[0]) if labels else "(no label)"
        line = text[: table.start()].count("\n") + 1
        rows = approx_table_rows(body)
        row_note = f", approx rows: {rows}" if rows else ""
        print(f"- Table {index} at line {line}, label: {label}{row_note}: {caption}")

    longtable_pattern = re.compile(r"\\begin\{longtable\}(?:\{[^{}]*\})?(.*?)\\end\{longtable\}", re.S)
    for index, table in enumerate(longtable_pattern.finditer(text), 1):
        found_tables = True
        body = table.group(1)
        captions = find_braced("caption", body)
        labels = find_braced("label", body)
        caption = clean_latex(captions[0])[:260] if captions else "(no caption)"
        label = clean_latex(labels[0]) if labels else "(no label)"
        line = text[: table.start()].count("\n") + 1
        print(f"- Longtable {index} at line {line}, label: {label}: {caption}")
    if not found_tables:
        print("- (none detected)")
    print()

    links = re.findall(r"\\href\{([^{}]+)\}\{([^{}]+)\}|\\url\{([^{}]+)\}", text)
    if links:
        print("Links:")
        for href, label, url in links:
            print(f"- {clean_latex(label) or url}: {href or url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
