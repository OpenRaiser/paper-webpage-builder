#!/usr/bin/env python3
"""Build a best-effort BibTeX draft for the paper itself.

Reads the root .tex (expanding `\\input/\\include`) plus any sibling `.bib`
files referenced via `\\bibliography{...}` or `\\addbibresource{...}` and
emits a single BibTeX entry on stdout.

Always includes a leading comment listing what was inferred and what was
guessed, so downstream HTML generation can decide whether to surface a
"venue/year unverified" warning next to the bibtex block.

Sources of evidence, in order:
  1. arXiv URL — if `arxiv.org/abs/<id>` appears in the paper, year/venue are derived.
  2. \\title{...} / \\author{...} / \\date{...} from the root tex.
  3. PDF metadata — when `--pdf <file>` is provided and pymupdf is available.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{([^{}]+)\}")
BIB_RE = re.compile(r"\\(?:bibliography|addbibresource)\{([^{}]+)\}")
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            lines.append("")
            continue
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def read_with_inputs(root: Path, max_depth: int = 6) -> str:
    visited: set[Path] = set()
    chunks: list[str] = []

    def load(path: Path, depth: int) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in visited or depth > max_depth or not resolved.is_file():
            return
        visited.add(resolved)
        text = strip_comments(read_text(resolved))
        chunks.append(text)
        for ref in INPUT_RE.findall(text):
            candidate = resolved.parent / ref.strip()
            if candidate.suffix == "":
                candidate = candidate.with_suffix(".tex")
            load(candidate, depth + 1)

    load(root, 0)
    return "\n".join(chunks)


def find_braced(text: str, command: str) -> str | None:
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


def clean(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"\\(?:textbf|textit|textsc|texttt|emph|mathrm|mathbf)\*?\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\(?:thanks|footnote|orcidlink)\{[^{}]*\}", "", value)
    value = re.sub(r"\\and\b", " and ", value)
    value = re.sub(r"\\\\", " ", value)
    value = re.sub(r"\\,", " ", value)
    value = re.sub(r"\\[a-zA-Z@]+\*?", "", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"~", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value


def split_authors(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"\band\b|,(?=[^,]+,)|\\and|\n", raw, flags=re.IGNORECASE)
    out: list[str] = []
    for p in parts:
        p = clean(p)
        if not p:
            continue
        # Drop trailing affiliations / superscripts
        p = re.sub(r"[\d\*†‡§¶]+$", "", p).strip()
        if 2 <= len(p) <= 80 and re.search(r"[A-Za-z]", p):
            out.append(p)
    seen: list[str] = []
    for n in out:
        if n not in seen:
            seen.append(n)
    return seen


def slug_for_key(first_author: str, year: str, title: str) -> str:
    surname = first_author.split()[-1] if first_author else "anon"
    surname = re.sub(r"[^A-Za-z]", "", surname).lower() or "anon"
    word = ""
    for w in title.split():
        cleaned = re.sub(r"[^A-Za-z]", "", w).lower()
        if len(cleaned) >= 4 and cleaned not in {"with", "from", "into", "this", "that", "what", "when", "your"}:
            word = cleaned
            break
    if not word:
        word = "paper"
    return f"{surname}{year or 'XXXX'}{word}"


def maybe_pdf_meta(path: Path | None) -> dict[str, str]:
    if not path or not path.is_file():
        return {}
    try:
        import fitz  # type: ignore
    except Exception:
        return {}
    try:
        with fitz.open(path) as doc:
            return {k: v for k, v in (doc.metadata or {}).items() if v}
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_tex", type=Path, help="Root .tex file (or empty path '-' to skip).")
    parser.add_argument("--pdf", type=Path, default=None, help="Optional paper PDF for metadata fallback.")
    parser.add_argument("--bib-key", default=None, help="Override the generated cite key.")
    args = parser.parse_args()

    notes: list[str] = []
    title = ""
    authors: list[str] = []
    year = ""
    arxiv_id = ""
    bib_files: list[Path] = []

    text = ""
    tex_path = args.paper_tex
    if tex_path and str(tex_path) != "-" and tex_path.is_file():
        text = read_with_inputs(tex_path)
        title = clean(find_braced(text, "title")) or title
        author_blob = find_braced(text, "author")
        if author_blob:
            authors = split_authors(author_blob)
        date_raw = clean(find_braced(text, "date"))
        if date_raw:
            ymatch = re.search(r"(19|20)\d{2}", date_raw)
            if ymatch:
                year = ymatch.group(0)
        # arXiv
        amatch = ARXIV_RE.search(text)
        if amatch:
            arxiv_id = amatch.group(1)
        # collect referenced .bib files
        for ref in BIB_RE.findall(text):
            for piece in ref.split(","):
                piece = piece.strip()
                if not piece:
                    continue
                if not piece.endswith(".bib"):
                    piece = piece + ".bib"
                candidate = (tex_path.resolve().parent / piece).resolve()
                if candidate.is_file() and candidate not in bib_files:
                    bib_files.append(candidate)

    # PDF metadata fallback for missing fields.
    if not (title and authors and year):
        meta = maybe_pdf_meta(args.pdf)
        if meta:
            if not title and meta.get("title"):
                title = meta["title"].strip()
            if not authors and meta.get("author"):
                authors = split_authors(meta["author"])
            if not year:
                for k in ("creationDate", "modDate"):
                    raw = meta.get(k, "")
                    ym = re.search(r"D:(\d{4})", raw)
                    if ym:
                        year = ym.group(1)
                        break

    if arxiv_id and not year:
        # arXiv id 1701.xxxxx → 2017
        prefix = arxiv_id[:2]
        year = ("20" + prefix) if prefix.isdigit() and int(prefix) >= 7 else year

    if not year:
        notes.append("year missing — placeholder XXXX written; verify before publishing")
        year_value = "XXXX"
    else:
        year_value = year

    if not title:
        notes.append("title missing — placeholder used; verify before publishing")
        title = "Unknown Title"
    if not authors:
        notes.append("authors missing — placeholder used; verify before publishing")
        authors = ["Unknown"]
    if not arxiv_id:
        notes.append("no arXiv id detected — venue assumed unpublished/preprint")

    cite_key = args.bib_key or slug_for_key(authors[0], year, title)

    fields: list[tuple[str, str]] = [
        ("title", "{" + title + "}"),
        ("author", " and ".join(authors)),
        ("year", year_value),
    ]
    if arxiv_id:
        fields.append(("eprint", arxiv_id))
        fields.append(("archivePrefix", "arXiv"))
        fields.append(("url", f"https://arxiv.org/abs/{arxiv_id}"))
        entry_type = "@misc"
    else:
        entry_type = "@unpublished"

    print(f"% Draft generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} by extract_citation.py")
    for note in notes:
        print(f"% NOTE: {note}")
    if bib_files:
        print(f"% bib files referenced by the paper: {', '.join(str(p) for p in bib_files)}")
    print()
    print(f"{entry_type}{{{cite_key},")
    for index, (k, v) in enumerate(fields):
        comma = "," if index < len(fields) - 1 else ""
        print(f"  {k} = {{{v}}}{comma}")
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
