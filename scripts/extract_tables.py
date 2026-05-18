#!/usr/bin/env python3
"""Extract every LaTeX table into a JSON ledger for the central-table check.

Emits one JSON document with a list of entries, each containing:
- file: source .tex file (relative to root)
- line: line number in that file
- environment: `table`, `table*`, `longtable`, ...
- label: contents of `\\label{...}` (or null)
- caption: cleaned `\\caption{...}` text (or null)
- column_spec: the alignment spec `\\begin{tabular}{...}` (or null)
- header_rows / data_rows: lists of cell-lists, surface text only
- raw_rows: number of `\\\\` separated rows including header
- notes: list of warning strings (e.g. detected \\multicolumn / \\multirow)

Designed so an LLM (or a downstream check) can reconcile the page against
every table in the paper without re-reading the .tex itself.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{([^{}]+)\}")
TABLE_ENVS = ("table", "table*", "longtable", "sidewaystable", "table**")
ROW_TABULAR_ENV_RE = re.compile(
    r"\\begin\{(tabular|tabular\*|tabularx|tabulary|array|longtable)\}"
    r"(?:\[[^\]]*\])?"          # optional positional arg
    r"(?:\{[^{}]*\})?"          # optional width arg
    r"\{([^{}]*)\}"             # column spec
    r"(.*?)"
    r"\\end\{\1\}",
    re.S,
)
RULE_RE = re.compile(
    r"\\(?:toprule|midrule|bottomrule|hline|cline\{[^{}]*\}|specialrule\{[^{}]*\}\{[^{}]*\}\{[^{}]*\})"
)
COMMENT_LINE_RE = re.compile(r"(?<!\\)%.*")
LATEX_CMD_RE = re.compile(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?")
MULTICOL_RE = re.compile(r"\\multicolumn\{(\d+)\}\{[^{}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}")
MULTIROW_RE = re.compile(r"\\multirow\{(\d+)\}\{[^{}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}")


def strip_comments(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            out_lines.append("")
            continue
        out_lines.append(COMMENT_LINE_RE.sub("", line))
    return "\n".join(out_lines)


@dataclass
class Source:
    path: Path
    text: str
    # Map (offset_in_combined, offset_in_combined+len) → (path, line_in_path)
    offset: int = 0


def read_with_inputs(root: Path, max_depth: int = 6) -> list[Source]:
    """Read root tex, expand \\input/\\include into a flat per-file list."""
    visited: set[Path] = set()
    sources: list[Source] = []

    def load(path: Path, depth: int) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in visited or depth > max_depth or not resolved.is_file():
            return
        visited.add(resolved)
        try:
            raw = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = resolved.read_text(encoding="latin-1", errors="replace")
            print(
                f"warning: {resolved} is not utf-8, decoded as latin-1",
                file=sys.stderr,
            )
        text = strip_comments(raw)
        sources.append(Source(path=resolved, text=text))
        for match in INPUT_RE.finditer(text):
            ref = match.group(1).strip()
            if not ref:
                continue
            candidate = (resolved.parent / ref)
            if candidate.suffix == "":
                candidate = candidate.with_suffix(".tex")
            load(candidate, depth + 1)

    load(root, 0)
    return sources


def find_braced_arg(text: str, command: str) -> str | None:
    pattern = re.compile(r"\\" + re.escape(command) + r"\*?(?:\[[^\]]*\])?\{")
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def clean_text(value: str) -> str:
    if value is None:
        return ""
    value = value.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
    value = value.replace(r"\#", "#").replace(r"\$", "$")
    value = value.replace(r"\textbackslash", "\\")
    # textbf{x} / textsc{x} / emph{x} / mathrm{x}: keep inner.
    inner_re = re.compile(
        r"\\(?:textbf|textit|textsc|texttt|emph|mathbf|mathrm|mathit|operatorname|"
        r"textrm|textsf|underline|uline|bm)\*?\{((?:[^{}]|\{[^{}]*\})*)\}"
    )
    for _ in range(4):
        new = inner_re.sub(r"\1", value)
        if new == value:
            break
        value = new
    # Replace \cite/\ref/\label with placeholders so they don't pollute cells.
    value = re.sub(r"\\cite[a-zA-Z]*\*?\{[^{}]*\}", "[cite]", value)
    value = re.sub(r"\\ref\*?\{[^{}]*\}", "[ref]", value)
    value = re.sub(r"\\label\{[^{}]*\}", "", value)
    value = re.sub(r"\\(?:checkmark|xmark|cmark)\b", "✓", value)
    value = LATEX_CMD_RE.sub("", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\$([^$]*)\$", r"\1", value)
    value = re.sub(r"~", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_top_level_cells(row: str) -> list[str]:
    cells: list[str] = []
    depth = 0
    buf: list[str] = []
    i = 0
    while i < len(row):
        c = row[i]
        if c == "\\" and i + 1 < len(row):
            buf.append(row[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
            buf.append(c)
        elif c == "}":
            depth -= 1
            buf.append(c)
        elif c == "&" and depth == 0:
            cells.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    cells.append("".join(buf))
    return cells


def expand_multicolumn(cell: str) -> tuple[str, int]:
    """Return (visible text, span). Non-multicol cells span 1."""
    m = MULTICOL_RE.search(cell)
    if m:
        return clean_text(m.group(2)), int(m.group(1))
    m2 = MULTIROW_RE.search(cell)
    if m2:
        return clean_text(m2.group(2)), 1
    return clean_text(cell), 1


def split_rows(body: str) -> list[str]:
    body = RULE_RE.sub("", body)
    raw_rows = re.split(r"\\\\(?:\s*\[[^\]]*\])?", body)
    rows = []
    for row in raw_rows:
        cleaned = row.strip()
        if not cleaned:
            continue
        if "&" not in cleaned and not clean_text(cleaned):
            continue
        rows.append(cleaned)
    return rows


def split_into_header_and_data(body: str) -> tuple[list[list[str]], list[list[str]], list[str]]:
    """Use \\midrule (or \\hline if no midrule) as the boundary."""
    notes: list[str] = []
    if "\\multicolumn" in body:
        notes.append("contains \\multicolumn — header alignment is approximate")
    if "\\multirow" in body:
        notes.append("contains \\multirow — vertical merges are flattened")

    # Find midrule split (prefer first midrule; fallback to first hline after first row)
    boundary = None
    for marker in (r"\midrule", r"\hline"):
        idx = body.find(marker)
        if idx != -1:
            boundary = idx
            break

    def parse_rows(segment: str) -> list[list[str]]:
        rows = []
        for row in split_rows(segment):
            cells = []
            for cell in split_top_level_cells(row):
                text, span = expand_multicolumn(cell)
                cells.append(text)
                for _ in range(span - 1):
                    cells.append("")
            rows.append(cells)
        return rows

    if boundary is None:
        all_rows = parse_rows(body)
        header_rows = all_rows[:1]
        data_rows = all_rows[1:]
    else:
        header_rows = parse_rows(body[:boundary])
        data_rows = parse_rows(body[boundary:])
    return header_rows, data_rows, notes


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


@dataclass
class TableEntry:
    file: str
    line: int
    environment: str
    label: str | None = None
    caption: str | None = None
    column_spec: str | None = None
    header_rows: list[list[str]] = field(default_factory=list)
    data_rows: list[list[str]] = field(default_factory=list)
    raw_rows: int = 0
    notes: list[str] = field(default_factory=list)


def find_table_blocks(text: str) -> list[tuple[str, int, int]]:
    """Return (env_name, start_offset_of_inner_body, end_offset_of_inner_body)."""
    results: list[tuple[str, int, int]] = []
    for env in TABLE_ENVS:
        begin = re.compile(r"\\begin\{" + re.escape(env) + r"\}(?:\[[^\]]*\])?", re.S)
        end_re = re.compile(r"\\end\{" + re.escape(env) + r"\}")
        for match in begin.finditer(text):
            inner_start = match.end()
            end_match = end_re.search(text, inner_start)
            if not end_match:
                continue
            results.append((env, inner_start, end_match.start()))
    return results


def extract_from_source(src: Source, root_dir: Path) -> list[TableEntry]:
    entries: list[TableEntry] = []
    for env, start, end in find_table_blocks(src.text):
        block = src.text[start:end]
        caption_raw = find_braced_arg(block, "caption")
        label_raw = find_braced_arg(block, "label")
        tabular = ROW_TABULAR_ENV_RE.search(block)

        if tabular:
            column_spec = tabular.group(2).strip()
            body = tabular.group(3)
            header_rows, data_rows, notes = split_into_header_and_data(body)
            raw_rows = len(split_rows(body))
        else:
            column_spec = None
            header_rows, data_rows, notes = [], [], ["no tabular/longtable body found"]
            raw_rows = 0

        rel = src.path.relative_to(root_dir) if root_dir in src.path.parents or src.path == root_dir / src.path.name else src.path
        entries.append(
            TableEntry(
                file=str(rel),
                line=line_for_offset(src.text, start),
                environment=env,
                label=clean_text(label_raw) if label_raw else None,
                caption=clean_text(caption_raw) if caption_raw else None,
                column_spec=column_spec,
                header_rows=header_rows,
                data_rows=data_rows,
                raw_rows=raw_rows,
                notes=notes,
            )
        )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_tex", type=Path, help="Root .tex file (\\input/\\include is expanded).")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=200,
        help="Truncate header_rows+data_rows to this many entries per table (default 200).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "summary"),
        default="json",
        help="json: full ledger; summary: human-readable list with row/col counts.",
    )
    args = parser.parse_args()

    if not args.paper_tex.is_file():
        print(f"error: not a file: {args.paper_tex}", file=sys.stderr)
        return 2

    sources = read_with_inputs(args.paper_tex)
    if not sources:
        print("error: nothing to scan", file=sys.stderr)
        return 2

    root_dir = args.paper_tex.resolve().parent
    all_entries: list[TableEntry] = []
    for src in sources:
        all_entries.extend(extract_from_source(src, root_dir))

    if args.format == "summary":
        if not all_entries:
            print("(no tables detected)")
            return 0
        for index, entry in enumerate(all_entries, 1):
            cols = max((len(r) for r in entry.header_rows + entry.data_rows), default=0)
            data_n = len(entry.data_rows)
            head_n = len(entry.header_rows)
            label = entry.label or "(no label)"
            cap = entry.caption or "(no caption)"
            print(
                f"[{index}] {entry.file}:{entry.line} env={entry.environment} "
                f"label={label} cols={cols} header_rows={head_n} data_rows={data_n}"
            )
            print(f"     caption: {cap[:200]}")
            for note in entry.notes:
                print(f"     note: {note}")
        return 0

    payload = []
    for entry in all_entries:
        rows_kept = entry.data_rows[: max(0, args.max_rows - len(entry.header_rows))]
        truncated = len(entry.data_rows) > len(rows_kept)
        item = {
            "file": entry.file,
            "line": entry.line,
            "environment": entry.environment,
            "label": entry.label,
            "caption": entry.caption,
            "column_spec": entry.column_spec,
            "header_rows": entry.header_rows,
            "data_rows": rows_kept,
            "data_rows_truncated": truncated,
            "raw_rows": entry.raw_rows,
            "notes": entry.notes,
        }
        payload.append(item)
    json.dump({"tables": payload}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
